from fastapi import APIRouter, BackgroundTasks, Query

from app.models.mosaic import (
    BlockerByPractice,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    DeploymentFunnel,
    DeploymentPracticeRollup,
    DeploymentRadiologistItem,
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    MosaicIntelligenceSnapshot,
    PopulationEfficiency,
    RadiologistRosterItem,
    RadSummaryStat,
    RpceTrendPoint,
    UtilizationPracticeRollup,
)
from app.services import cache_service, refresh_service

router = APIRouter(prefix="/api/mosaic", tags=["mosaic"])


# Every route below reads from the local SQLite cache (app/services/cache_service.py),
# never from EDW directly - see app/services/refresh_service.py for why: EDW queries here
# were observed to take anywhere from ~2s to 800+s depending on warehouse-side conditions
# outside this app's control, which is unworkable for an interactively-loaded dashboard.
# The cache is populated by a background refresh loop plus the manual /refresh endpoint.


@router.get("/mosaic-intelligence", response_model=MosaicIntelligenceSnapshot)
async def mosaic_intelligence():
    return cache_service.get_mosaic_intelligence_snapshot()


@router.get("/rpce-trend", response_model=list[RpceTrendPoint])
async def rpce_trend():
    return cache_service.get_rpce_trend()


@router.get("/rad-summary-stats", response_model=list[RadSummaryStat])
async def rad_summary_stats(practice: str | None = None, drafting_group: str | None = None):
    return cache_service.get_rad_summary_stats(practice, drafting_group)


@router.get("/roster", response_model=list[RadiologistRosterItem])
async def roster(
    practice: str | None = None,
    subspecialty: str | None = None,
    deployment_status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return cache_service.get_radiologist_roster(practice, subspecialty, deployment_status, limit, offset)


@router.get("/utilization/by-practice", response_model=list[UtilizationPracticeRollup])
async def utilization_by_practice(days_back: int = Query(30, ge=1, le=365)):
    return cache_service.get_utilization_by_practice(days_back)


@router.get("/deployment/by-radiologist", response_model=list[DeploymentRadiologistItem])
async def deployment_by_radiologist(limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return cache_service.get_deployment_by_radiologist(limit, offset)


@router.get("/deployment/by-practice", response_model=list[DeploymentPracticeRollup])
async def deployment_by_practice():
    return cache_service.get_deployment_by_practice()


@router.get("/deployment/funnel/reporting", response_model=DeploymentFunnel)
async def deployment_funnel_reporting():
    return cache_service.get_deployment_funnel_reporting()


@router.get("/deployment/funnel/drafting", response_model=DeploymentFunnel)
async def deployment_funnel_drafting():
    return cache_service.get_deployment_funnel_drafting()


@router.get("/deployment/blockers/drafting", response_model=list[BlockerByPractice])
async def deployment_blockers_drafting():
    return cache_service.get_drafting_blockers_by_practice()


@router.get("/efficiency", response_model=EfficiencyDetail)
async def efficiency_detail(mode: str = Query("full_mosaic")):
    return cache_service.get_efficiency_detail(mode)


@router.get("/efficiency/population", response_model=PopulationEfficiency)
async def efficiency_population(
    mode: str = Query("full_mosaic"),
    practice: str | None = None,
    subspecialty: str | None = None,
    modality_code: str | None = None,
    parent_procedure_name: str | None = None,
    exam_category: str | None = None,
):
    return cache_service.get_efficiency_population(
        mode, practice, subspecialty, modality_code, parent_procedure_name, exam_category
    )


@router.get("/efficiency/filters", response_model=EfficiencyFilterOptions)
async def efficiency_filters():
    return cache_service.get_efficiency_filter_options()


@router.get("/efficiency/trend", response_model=list[EfficiencyTrendPoint])
async def efficiency_trend(exam_category: str | None = None):
    return cache_service.get_efficiency_trend(exam_category)


@router.get("/efficiency/trend/rp-avg", response_model=list[EfficiencyTrendRpAvgPoint])
async def efficiency_trend_rp_avg():
    return cache_service.get_efficiency_trend_rp_avg()


@router.get("/capacity/by-radiologist", response_model=list[CapacityRadiologistItem])
async def capacity_by_radiologist(limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return cache_service.get_capacity_by_radiologist(limit, offset)


@router.get("/capacity/by-practice", response_model=list[CapacityPracticeRollup])
async def capacity_by_practice():
    return cache_service.get_capacity_by_practice()


@router.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Kick off an EDW refresh in the background and return immediately - this can take
    several minutes to tens of minutes depending on warehouse conditions."""
    background_tasks.add_task(refresh_service.refresh_all)
    return {"status": "refresh started"}


@router.get("/refresh/status")
async def get_refresh_status():
    return refresh_service.refresh_status()
