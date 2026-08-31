"""Public read API the routes call. Every function here reads from the local SQLite cache
(populated by app.services.refresh_service) instead of querying EDW live, so dashboard loads
are instant and independent of the Databricks warehouse's performance. Any filtering,
pagination, or windowing a route needs is applied here in Python over the cached dataset,
since the underlying EDW queries in app.services.mosaic_service are no longer called
per-request - only by the background/manual refresh job.
"""

from app.db import cache_store, efficiency_store
from app.models.mosaic import (
    BlockerByPractice,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    DeploymentFunnel,
    DeploymentPracticeRollup,
    DeploymentRadiologistItem,
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyPracticeRollup,
    EfficiencyRadiologistItem,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    MosaicIntelligenceSnapshot,
    PopulationEfficiency,
    RadiologistRosterItem,
    RadSummaryStat,
    RpceTrendPoint,
    UtilizationPracticeRollup,
)


def _pct_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None or baseline == 0:
        return None
    return (current - baseline) / baseline


def _read_time_change(current: float | None, baseline: float | None) -> float | None:
    # "Implied RTS": how much more/less time it takes to do the same unit of work, derived
    # purely from the efficiency ratio (baseline TBWU/min ÷ Mosaic TBWU/min) - 1. Negative
    # means less time needed (a read-time saving); matches Parameter[Implied_RTS_Opt].
    if current is None or baseline is None or current == 0:
        return None
    return (baseline / current) - 1


def get_mosaic_intelligence_snapshot() -> MosaicIntelligenceSnapshot:
    payload, _ = cache_store.load("mosaic_intelligence_snapshot")
    if payload is None:
        return MosaicIntelligenceSnapshot(
            rads_live_on_mosaic=0,
            rads_live_on_ai_drafting=0,
            pct_rpce_reporting=None,
            pct_rpce_drafting=None,
            rads_live_on_capture=0,
            practices_fully_on_rpce=0,
            practices_split_integration=0,
            practices_not_on_rpce=0,
        )
    return MosaicIntelligenceSnapshot(**payload)


def get_rpce_trend() -> list[RpceTrendPoint]:
    payload, _ = cache_store.load("rpce_trend")
    return [RpceTrendPoint(**row) for row in (payload or [])]


def get_rad_summary_stats(practice: str | None = None, drafting_group: str | None = None) -> list[RadSummaryStat]:
    payload, _ = cache_store.load("rad_summary_stats")
    items = [RadSummaryStat(**row) for row in (payload or [])]
    if practice:
        items = [r for r in items if r.home_practice == practice]
    if drafting_group:
        items = [r for r in items if drafting_group in r.drafting_groups]
    return items


def get_radiologist_roster(
    practice: str | None = None,
    subspecialty: str | None = None,
    deployment_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RadiologistRosterItem]:
    payload, _ = cache_store.load("radiologist_roster")
    items = [RadiologistRosterItem(**row) for row in (payload or [])]
    if practice:
        items = [r for r in items if r.home_practice == practice]
    if subspecialty:
        items = [r for r in items if r.working_subspecialty == subspecialty]
    if deployment_status:
        items = [r for r in items if r.deployment_status == deployment_status]
    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(int(limit), 500))
    return items[safe_offset : safe_offset + safe_limit]


def get_utilization_by_practice(days_back: int = 30) -> list[UtilizationPracticeRollup]:
    # Cache always holds the 30-day rollup regardless of the requested window; the
    # underlying EDW view isn't queried live per-request anymore.
    payload, _ = cache_store.load("utilization_by_practice")
    return [UtilizationPracticeRollup(**row) for row in (payload or [])]


def get_deployment_by_radiologist(limit: int = 500, offset: int = 0) -> list[DeploymentRadiologistItem]:
    payload, _ = cache_store.load("deployment_by_radiologist")
    items = [DeploymentRadiologistItem(**row) for row in (payload or [])]
    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(int(limit), 1000))
    return items[safe_offset : safe_offset + safe_limit]


def get_deployment_by_practice() -> list[DeploymentPracticeRollup]:
    payload, _ = cache_store.load("deployment_by_practice")
    return [DeploymentPracticeRollup(**row) for row in (payload or [])]


def get_deployment_funnel_reporting() -> DeploymentFunnel:
    payload, _ = cache_store.load("deployment_funnel_reporting")
    return DeploymentFunnel(**payload) if payload else DeploymentFunnel(domain="Reporting", stages=[])


def get_deployment_funnel_drafting() -> DeploymentFunnel:
    payload, _ = cache_store.load("deployment_funnel_drafting")
    return DeploymentFunnel(**payload) if payload else DeploymentFunnel(domain="Drafting", stages=[])


def get_drafting_blockers_by_practice() -> list[BlockerByPractice]:
    payload, _ = cache_store.load("drafting_blockers_by_practice")
    return [BlockerByPractice(**row) for row in (payload or [])]


VALID_MODES = ("full_mosaic", "reporting", "drafting", "capture")


def get_efficiency_detail(mode: str = "full_mosaic") -> EfficiencyDetail:
    safe_mode = mode if mode in VALID_MODES else "full_mosaic"

    benchmark = efficiency_store.aggregate(mode=safe_mode)

    by_radiologist = []
    for row in efficiency_store.rollup_by("npi", mode=safe_mode):
        by_radiologist.append(
            EfficiencyRadiologistItem(
                npi=row["npi"],
                radiologist_name=row["radiologist_name"],
                practice=row["practice"],
                subspecialty=row["subspecialty"],
                mosaic_tbwu_per_min=row["mosaic_tbwu_per_min"],
                baseline_tbwu_per_min=row["baseline_tbwu_per_min"],
                pct_change_vs_baseline=_pct_change(row["mosaic_tbwu_per_min"], row["baseline_tbwu_per_min"]),
                read_time_change_pct=_read_time_change(row["mosaic_tbwu_per_min"], row["baseline_tbwu_per_min"]),
            )
        )

    by_practice = []
    for row in efficiency_store.rollup_by("practice", mode=safe_mode):
        by_practice.append(
            EfficiencyPracticeRollup(
                practice=row["practice"],
                mosaic_tbwu_per_min=row["mosaic_tbwu_per_min"],
                baseline_tbwu_per_min=row["baseline_tbwu_per_min"],
                pct_change_vs_baseline=_pct_change(row["mosaic_tbwu_per_min"], row["baseline_tbwu_per_min"]),
                read_time_change_pct=_read_time_change(row["mosaic_tbwu_per_min"], row["baseline_tbwu_per_min"]),
            )
        )

    return EfficiencyDetail(
        mode=safe_mode,
        rp_benchmark_mosaic_tbwu_per_min=benchmark["mosaic_tbwu_per_min"],
        rp_benchmark_baseline_tbwu_per_min=benchmark["baseline_tbwu_per_min"],
        by_radiologist=by_radiologist,
        by_practice=by_practice,
    )


def get_efficiency_population(
    mode: str = "full_mosaic",
    practice: str | None = None,
    subspecialty: str | None = None,
    modality_code: str | None = None,
    parent_procedure_name: str | None = None,
    exam_category: str | None = None,
) -> PopulationEfficiency:
    safe_mode = mode if mode in VALID_MODES else "full_mosaic"
    result = efficiency_store.aggregate(
        mode=safe_mode,
        practice=practice,
        subspecialty=subspecialty,
        modality_code=modality_code,
        parent_procedure_name=parent_procedure_name,
        exam_category=exam_category,
    )
    return PopulationEfficiency(
        mode=safe_mode,
        practice=practice,
        subspecialty=subspecialty,
        modality_code=modality_code,
        parent_procedure_name=parent_procedure_name,
        exam_category=exam_category,
        mosaic_tbwu_per_min=result["mosaic_tbwu_per_min"],
        baseline_tbwu_per_min=result["baseline_tbwu_per_min"],
        pct_change_vs_baseline=_pct_change(result["mosaic_tbwu_per_min"], result["baseline_tbwu_per_min"]),
        read_time_change_pct=_read_time_change(result["mosaic_tbwu_per_min"], result["baseline_tbwu_per_min"]),
    )


def get_efficiency_filter_options() -> EfficiencyFilterOptions:
    return EfficiencyFilterOptions(
        practices=efficiency_store.distinct_values("practice"),
        subspecialties=efficiency_store.distinct_values("subspecialty"),
        modalities=efficiency_store.distinct_values("modality_code"),
        procedures=efficiency_store.distinct_values("parent_procedure_name"),
        exam_categories=efficiency_store.distinct_values("exam_category"),
    )


def _rate(tbwu: float | None, time_sec: float | None) -> float | None:
    if not time_sec:
        return None
    return (tbwu or 0) / (time_sec / 60.0)


def get_efficiency_trend(exam_category: str | None = None) -> list[EfficiencyTrendPoint]:
    payload, _ = cache_store.load("efficiency_trend_by_category")
    rows = payload or []
    if exam_category:
        rows = [r for r in rows if r.get("exam_category") == exam_category]

    # Roll multiple exam-category rows for the same month back up to one point per month
    # when no specific category is selected ("All categories").
    by_period: dict[str, dict] = {}
    for row in rows:
        acc = by_period.setdefault(
            row["period"],
            {
                "reporting_tbwu": 0.0, "reporting_time": 0.0, "reporting_baseline_contrib": 0.0,
                "reporting_rad_count": 0, "reporting_exam_count": 0,
                "drafting_tbwu": 0.0, "drafting_time": 0.0, "drafting_baseline_contrib": 0.0,
                "drafting_rad_count": 0, "drafting_exam_count": 0,
            },
        )
        for key in acc:
            acc[key] += row.get(key) or 0

    points = []
    for period in sorted(by_period):
        d = by_period[period]
        reporting_eff = _rate(d["reporting_tbwu"], d["reporting_time"])
        drafting_eff = _rate(d["drafting_tbwu"], d["drafting_time"])
        full_mosaic_eff = _rate(d["reporting_tbwu"] + d["drafting_tbwu"], d["reporting_time"] + d["drafting_time"])
        # baseline_contrib is already per-minute weighted by time (seconds), so divide by
        # raw seconds directly - see efficiency_store._baseline_rate for the derivation.
        reporting_baseline = (d["reporting_baseline_contrib"] / d["reporting_time"]) if d["reporting_time"] else None
        drafting_baseline = (d["drafting_baseline_contrib"] / d["drafting_time"]) if d["drafting_time"] else None
        full_mosaic_baseline = (
            (d["reporting_baseline_contrib"] + d["drafting_baseline_contrib"]) / (d["reporting_time"] + d["drafting_time"])
            if (d["reporting_time"] + d["drafting_time"])
            else None
        )
        points.append(
            EfficiencyTrendPoint(
                period=period,
                exam_category=exam_category,
                reporting_tbwu_per_min=reporting_eff,
                drafting_tbwu_per_min=drafting_eff,
                full_mosaic_tbwu_per_min=full_mosaic_eff,
                reporting_pct_change=_pct_change(reporting_eff, reporting_baseline),
                drafting_pct_change=_pct_change(drafting_eff, drafting_baseline),
                full_mosaic_pct_change=_pct_change(full_mosaic_eff, full_mosaic_baseline),
                reporting_rad_count=int(d["reporting_rad_count"]),
                drafting_rad_count=int(d["drafting_rad_count"]),
                reporting_exam_count=int(d["reporting_exam_count"]),
                drafting_exam_count=int(d["drafting_exam_count"]),
            )
        )
    return points


def get_efficiency_trend_rp_avg() -> list[EfficiencyTrendRpAvgPoint]:
    payload, _ = cache_store.load("efficiency_trend_rp_avg")
    points = []
    for row in payload or []:
        drafting_eff = _rate(row["drafting_tbwu"], row["drafting_time"])
        full_mosaic_eff = _rate(row["reporting_tbwu"] + row["drafting_tbwu"], row["reporting_time"] + row["drafting_time"])
        points.append(
            EfficiencyTrendRpAvgPoint(
                period=row["period"],
                drafting_tbwu_per_min=drafting_eff,
                full_mosaic_tbwu_per_min=full_mosaic_eff,
            )
        )
    return points


def get_capacity_by_radiologist(limit: int = 500, offset: int = 0) -> list[CapacityRadiologistItem]:
    payload, _ = cache_store.load("capacity_by_radiologist")
    items = [CapacityRadiologistItem(**row) for row in (payload or [])]
    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(int(limit), 1000))
    return items[safe_offset : safe_offset + safe_limit]


def get_capacity_by_practice() -> list[CapacityPracticeRollup]:
    payload, _ = cache_store.load("capacity_by_practice")
    return [CapacityPracticeRollup(**row) for row in (payload or [])]
