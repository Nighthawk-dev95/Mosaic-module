import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from pydantic import BaseModel

from app.models.mosaic import (
    BaselineProxyCandidate,
    BaselineProxyDetail,
    BlockerByPractice,
    CapacityBaselineScorecard,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    CaptureEfficiencyTrendPracticePoint,
    CaptureEfficiencyTrendRadiologistPoint,
    CaptureOverview,
    CapturePracticeRollup,
    CaptureRadiologistItem,
    CaptureUtilizationTrendPracticePoint,
    CaptureUtilizationTrendRadiologistPoint,
    DeploymentFunnel,
    DeploymentPracticeRollup,
    DeploymentRadiologistItem,
    DraftInsightCategoryGroup,
    DraftInsightModalityStat,
    DraftInsightOverview,
    DraftInsightPracticeStat,
    DraftInsightSampleItem,
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    ExternalFeedbackItem,
    FocusRadiologistItem,
    MosaicIntelligenceSnapshot,
    PopulationEfficiency,
    RadiologistRosterItem,
    RadiologistScorecard,
    RadSummaryStat,
    RadSurveySummary,
    RpceTrendPoint,
    UndraftedCategoryPoint,
    UndraftedFilterOptions,
    UtilizationPracticeRollup,
)
from app.db import cache_store, postgres_client
from app.services import baseline_overrides, cache_service, refresh_service

router = APIRouter(prefix="/api/mosaic", tags=["mosaic"])


# Every route below reads from the local SQLite cache (app/services/cache_service.py),
# never from EDW directly - see app/services/refresh_service.py for why: EDW queries here
# were observed to take anywhere from ~2s to 800+s depending on warehouse-side conditions
# outside this app's control, which is unworkable for an interactively-loaded dashboard.
# The cache is populated by a background refresh loop plus the manual /refresh endpoint.


@router.get("/mosaic-intelligence", response_model=MosaicIntelligenceSnapshot)
async def mosaic_intelligence(practice: str | None = None):
    return cache_service.get_mosaic_intelligence_snapshot(practice)


@router.get("/rpce-trend", response_model=list[RpceTrendPoint])
async def rpce_trend(practice: str | None = None):
    return cache_service.get_rpce_trend(practice)


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


@router.get("/deployment/funnel/ct-abdpel", response_model=DeploymentFunnel)
async def deployment_funnel_ct_abdpel():
    return cache_service.get_deployment_funnel_ct_abdpel()


@router.get("/deployment/blockers/ct-abdpel", response_model=list[BlockerByPractice])
async def deployment_blockers_ct_abdpel():
    return cache_service.get_ct_abdpel_blockers_by_practice()


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
async def efficiency_trend(exam_category: str | None = None, practice: str | None = None):
    return cache_service.get_efficiency_trend(exam_category, practice)


@router.get("/efficiency/trend/rp-avg", response_model=list[EfficiencyTrendRpAvgPoint])
async def efficiency_trend_rp_avg():
    return cache_service.get_efficiency_trend_rp_avg()


@router.get("/efficiency/focus-radiologists", response_model=list[FocusRadiologistItem])
async def efficiency_focus_radiologists():
    return cache_service.get_focus_radiologists()


@router.get("/survey/rad-sentiment", response_model=RadSurveySummary)
async def survey_rad_sentiment():
    # Static, hand-compiled from an offline survey export (see app/data/rad_survey.py) -
    # not EDW-derived, so no cache_store/refresh_service involvement, same as rpce_audit.py.
    return cache_service.get_rad_survey_summary()


@router.get("/capture/overview", response_model=CaptureOverview)
async def capture_overview():
    return cache_service.get_capture_overview()


@router.get("/capture/by-practice", response_model=list[CapturePracticeRollup])
async def capture_by_practice(practice: str | None = None):
    return cache_service.get_capture_by_practice(practice)


@router.get("/capture/by-radiologist", response_model=list[CaptureRadiologistItem])
async def capture_by_radiologist(practice: str | None = None):
    return cache_service.get_capture_by_radiologist(practice)


@router.get("/capture/trend/utilization/by-practice", response_model=list[CaptureUtilizationTrendPracticePoint])
async def capture_trend_utilization_by_practice(
    granularity: str = Query("week", pattern="^(week|month)$"), practice: str | None = None
):
    return cache_service.get_capture_utilization_trend_by_practice(granularity, practice)


@router.get("/capture/trend/utilization/by-radiologist", response_model=list[CaptureUtilizationTrendRadiologistPoint])
async def capture_trend_utilization_by_radiologist(
    granularity: str = Query("week", pattern="^(week|month)$"),
    practice: str | None = None,
    npi: int | None = None,
):
    return cache_service.get_capture_utilization_trend_by_radiologist(granularity, practice, npi)


@router.get("/capture/trend/efficiency/by-practice", response_model=list[CaptureEfficiencyTrendPracticePoint])
async def capture_trend_efficiency_by_practice(
    granularity: str = Query("week", pattern="^(week|month)$"), practice: str | None = None
):
    return cache_service.get_capture_efficiency_trend_by_practice(granularity, practice)


@router.get("/capture/trend/efficiency/by-radiologist", response_model=list[CaptureEfficiencyTrendRadiologistPoint])
async def capture_trend_efficiency_by_radiologist(
    granularity: str = Query("week", pattern="^(week|month)$"),
    practice: str | None = None,
    npi: int | None = None,
):
    return cache_service.get_capture_efficiency_trend_by_radiologist(granularity, practice, npi)


@router.get("/capacity/by-radiologist", response_model=list[CapacityRadiologistItem])
async def capacity_by_radiologist(limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return cache_service.get_capacity_by_radiologist(limit, offset)


@router.get("/capacity/by-practice", response_model=list[CapacityPracticeRollup])
async def capacity_by_practice():
    return cache_service.get_capacity_by_practice()


@router.get("/radiologist-scorecard", response_model=list[RadiologistScorecard])
async def radiologist_scorecard(practice: str | None = None):
    return cache_service.get_radiologist_scorecard(practice)


@router.get("/undrafted-analysis", response_model=list[UndraftedCategoryPoint])
async def undrafted_analysis(practice: str | None = None, exam_category: str | None = None, site: str | None = None):
    return cache_service.get_undrafted_analysis(practice, exam_category, site)


@router.get("/undrafted-analysis/filters", response_model=UndraftedFilterOptions)
async def undrafted_analysis_filters():
    return cache_service.get_undrafted_filter_options()


@router.get("/draft-insights/overview", response_model=DraftInsightOverview)
async def draft_insights_overview():
    return cache_service.get_draft_insight_overview()


@router.get("/draft-insights/by-modality", response_model=list[DraftInsightModalityStat])
async def draft_insights_by_modality():
    return cache_service.get_draft_insight_by_modality()


@router.get("/draft-insights/by-practice", response_model=list[DraftInsightPracticeStat])
async def draft_insights_by_practice():
    return cache_service.get_draft_insight_by_practice()


@router.get("/draft-insights/categories", response_model=list[DraftInsightCategoryGroup])
async def draft_insights_categories():
    return cache_service.get_draft_insight_categories()


@router.get("/draft-insights/samples", response_model=list[DraftInsightSampleItem])
async def draft_insights_samples(overall_assessment: str | None = None, limit: int = Query(50, ge=1, le=500)):
    return cache_service.get_draft_insight_samples(overall_assessment, limit)


@router.get("/capacity/baseline-scorecard", response_model=list[CapacityBaselineScorecard])
async def capacity_baseline_scorecard():
    return cache_service.get_capacity_baseline_scorecard()


@router.get("/capacity/baseline-proxy-detail", response_model=list[BaselineProxyDetail])
async def capacity_baseline_proxy_detail(practice: str | None = None):
    return cache_service.get_baseline_proxy_detail(practice)


@router.get("/capacity/baseline-proxy-candidates", response_model=list[BaselineProxyCandidate])
async def capacity_baseline_proxy_candidates(npi: int | None = None, target_shift: str | None = None):
    return cache_service.get_baseline_proxy_candidates(npi, target_shift)


class BaselineReviewDecisionIn(BaseModel):
    npi: int
    target_shift: str
    status: str
    chosen_proxy_shift: str | None = None
    chosen_rank: int | None = None
    note: str | None = None


@router.get("/capacity/baseline-review-decisions")
async def get_baseline_review_decisions():
    # Durable on the dev-bhargav Lakebase Postgres branch (app/db/postgres_client.py), same
    # resource as /refresh/history - empty list if Postgres is unavailable, never an error.
    return postgres_client.list_review_decisions()


@router.post("/capacity/baseline-review-decisions")
async def post_baseline_review_decision(decision: BaselineReviewDecisionIn):
    saved = postgres_client.save_review_decision(
        npi=decision.npi,
        target_shift=decision.target_shift,
        status=decision.status,
        chosen_proxy_shift=decision.chosen_proxy_shift,
        chosen_rank=decision.chosen_rank,
        note=decision.note,
        reviewed_at=datetime.now(timezone.utc),
    )
    if saved:
        # Closes the loop live, not just on the next 30-min refresh - this is what makes
        # accepting/overriding a review actually change the Capacity tab within seconds.
        try:
            baseline_overrides.recompute_capacity_with_overrides()
        except Exception as exc:  # noqa: BLE001 - the decision is already saved either way
            print(f"[baseline-review] recompute_capacity_with_overrides failed: {exc}", flush=True)
    return {"saved": saved}


@router.get("/capacity/review-activity")
async def get_review_activity(limit: int = Query(20, ge=1, le=100)):
    """Enriches the raw decision log with each decision's real capacity-rate impact (chosen
    candidate's rate minus the algorithm's own rank-1 rate) - powers the Baseline Review
    Queue's live activity ticker. Computed on read, not stored, so it's always consistent with
    whatever's currently cached in baseline_proxy_candidates_raw."""
    decisions = postgres_client.list_review_decisions()[:limit]
    enriched = []
    for d in decisions:
        candidates = cache_service.get_baseline_proxy_candidates(d["npi"], d["target_shift"])
        by_rank = {c.rank: c for c in candidates}
        default_candidate = by_rank.get(1)
        chosen_candidate = by_rank.get(d.get("chosen_rank")) if d.get("chosen_rank") else None
        impact = None
        if d["status"] != "rejected_no_match" and default_candidate and chosen_candidate:
            default_rate = default_candidate.baseline_tbwu_per_hour
            chosen_rate = chosen_candidate.baseline_tbwu_per_hour
            if default_rate is not None and chosen_rate is not None:
                impact = chosen_rate - default_rate
        anchor = chosen_candidate or default_candidate
        enriched.append(
            {
                **d,
                "radiologist_name": anchor.radiologist_name if anchor else None,
                "practice": anchor.practice if anchor else None,
                "capacity_impact_tbwu_per_hour": impact,
            }
        )
    return enriched


# Speculative push-ingestion endpoint - a best-guess mirror of practice-command-dev's apparent
# resource shape (DATABRICKS_TOKEN / FEEDBACK_QUEUE_WEBHOOK_URL / INGEST_SHARED_SECRET), inferred
# from `databricks apps list` metadata only - their actual source isn't visible to us, so this is
# NOT a confirmed replica of their design. Deliberately sandboxed: the allowlist below is the only
# thing stopping an external caller from overwriting one of the real EDW-sourced cache keys the
# rest of this app depends on - do not widen it without equally deliberate thought.
_INGEST_ALLOWED_DATASETS = {"external_feedback_demo"}


def _check_ingest_secret(x_ingest_secret: str | None) -> None:
    expected = os.environ.get("INGEST_SHARED_SECRET")
    if not expected:
        # Fail closed: an unset secret must never be treated as "accept anything" - this is
        # the normal/expected state in local dev, where the resource isn't bound.
        raise HTTPException(status_code=503, detail="ingest endpoint not configured")
    if x_ingest_secret != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-Ingest-Secret")


@router.post("/ingest/{dataset_name}")
async def post_ingest(
    dataset_name: str, rows: list[ExternalFeedbackItem], x_ingest_secret: str | None = Header(default=None)
):
    _check_ingest_secret(x_ingest_secret)
    if dataset_name not in _INGEST_ALLOWED_DATASETS:
        raise HTTPException(status_code=404, detail=f"{dataset_name!r} is not an ingestable dataset")
    cache_store.save(dataset_name, [row.model_dump() for row in rows])
    return {"status": "ingested", "row_count": len(rows)}


@router.get("/ingest/{dataset_name}")
async def get_ingest(dataset_name: str, x_ingest_secret: str | None = Header(default=None)):
    _check_ingest_secret(x_ingest_secret)
    if dataset_name not in _INGEST_ALLOWED_DATASETS:
        raise HTTPException(status_code=404, detail=f"{dataset_name!r} is not an ingestable dataset")
    rows, refreshed_at = cache_store.load(dataset_name)
    if rows is None:
        raise HTTPException(status_code=404, detail="no data ingested yet")
    return {"rows": rows, "refreshed_at": refreshed_at}


@router.get("/external-feedback", response_model=list[ExternalFeedbackItem])
async def get_external_feedback():
    # Internal read path for the dashboard - no X-Ingest-Secret needed here, same as every
    # other GET route; the secret only gates the external-facing ingest path above.
    return cache_service.get_external_feedback()


@router.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Kick off an EDW refresh in the background and return immediately - this can take
    several minutes to tens of minutes depending on warehouse conditions."""
    background_tasks.add_task(refresh_service.refresh_all)
    return {"status": "refresh started"}


@router.get("/refresh/status")
async def get_refresh_status():
    return refresh_service.refresh_status()


@router.get("/refresh/history")
async def get_refresh_history(limit: int = Query(100, ge=1, le=500)):
    # Durable log on the dev-bhargav Lakebase Postgres branch (app/db/postgres_client.py) -
    # separate from /refresh/status above, which stays in-memory/SQLite and is lost on restart.
    return postgres_client.recent_refresh_log(limit)
