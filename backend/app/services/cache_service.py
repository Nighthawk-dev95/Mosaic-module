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
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyPracticeRollup,
    EfficiencyRadiologistItem,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    MosaicIntelligenceSnapshot,
    PopulationEfficiency,
    RadiologistRosterItem,
    RadiologistScorecard,
    ScorecardMetrics,
    RadSummaryStat,
    RpceTrendPoint,
    UndraftedCategoryPoint,
    UndraftedFilterOptions,
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


def _empty_mosaic_intelligence_snapshot(practice: str | None) -> MosaicIntelligenceSnapshot:
    return MosaicIntelligenceSnapshot(
        practice=practice,
        rads_live_on_mosaic=0,
        rads_live_on_ai_drafting=0,
        pct_rpce_reporting=None,
        pct_rpce_drafting=None,
        rads_live_on_capture=0,
        rads_capture_enabled=0,
        practices_fully_on_rpce=0,
        practices_split_integration=0,
        practices_not_on_rpce=0,
    )


def get_mosaic_intelligence_snapshot(practice: str | None = None) -> MosaicIntelligenceSnapshot:
    if practice:
        payload, _ = cache_store.load("mosaic_intelligence_by_practice")
        match = next((row for row in (payload or []) if row.get("practice") == practice), None)
        if match is None:
            return _empty_mosaic_intelligence_snapshot(practice)
        return MosaicIntelligenceSnapshot(**match)

    payload, _ = cache_store.load("mosaic_intelligence_snapshot")
    if payload is None:
        return _empty_mosaic_intelligence_snapshot(None)
    return MosaicIntelligenceSnapshot(**payload)


def get_rpce_trend(practice: str | None = None) -> list[RpceTrendPoint]:
    if practice:
        payload, _ = cache_store.load("rpce_trend_by_practice")
        return [RpceTrendPoint(**row) for row in (payload or []) if row.get("practice") == practice]
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

    # total_mosaic_exams comes from the already-cached rad_summary_stats dataset instead of a
    # second EDW join, since it's already computed there per NPI.
    summary_payload, _ = cache_store.load("rad_summary_stats")
    exams_by_npi = {row["npi"]: row.get("total_mosaic_exams") for row in (summary_payload or [])}
    items = [item.model_copy(update={"total_mosaic_exams": exams_by_npi.get(item.npi)}) for item in items]

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


def get_deployment_funnel_ct_abdpel() -> DeploymentFunnel:
    payload, _ = cache_store.load("deployment_funnel_ct_abdpel")
    return DeploymentFunnel(**payload) if payload else DeploymentFunnel(domain="CT Abd/Pel", stages=[])


def get_ct_abdpel_blockers_by_practice() -> list[BlockerByPractice]:
    payload, _ = cache_store.load("ct_abdpel_blockers_by_practice")
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


def get_efficiency_trend(exam_category: str | None = None, practice: str | None = None) -> list[EfficiencyTrendPoint]:
    cache_key = "efficiency_trend_by_practice_category" if practice else "efficiency_trend_by_category"
    payload, _ = cache_store.load(cache_key)
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]
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
                practice=practice,
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


def get_capture_overview() -> CaptureOverview:
    payload, _ = cache_store.load("capture_overview")
    if payload is None:
        return CaptureOverview(
            capturable_exams_all=0, captured_exams_all=0, pct_captured_all=None,
            capturable_exams_enabled=0, captured_exams_enabled=0, pct_captured_enabled=None,
            rads_live_on_capture=0, rads_capture_enabled=0,
            capture_mosaic_tbwu_per_min=None, capture_baseline_tbwu_per_min=None,
            capture_pct_change_vs_baseline=None,
        )
    # Efficiency fields are filled in live from efficiency_store, the same "Capture Only"
    # mode machinery that already powers /efficiency?mode=capture - not cached separately.
    eff = efficiency_store.aggregate(mode="capture")
    data = dict(payload)
    data.update(
        capture_mosaic_tbwu_per_min=eff["mosaic_tbwu_per_min"],
        capture_baseline_tbwu_per_min=eff["baseline_tbwu_per_min"],
        capture_pct_change_vs_baseline=_pct_change(eff["mosaic_tbwu_per_min"], eff["baseline_tbwu_per_min"]),
    )
    return CaptureOverview(**data)


def _capture_baseline_period(enablement_date) -> str | None:
    """First full calendar month after a practice's derived enablement date (the following
    month if enablement didn't land on the 1st, to avoid a partial-month understatement)."""
    if not enablement_date:
        return None
    if isinstance(enablement_date, str):
        year, month = int(enablement_date[:4]), int(enablement_date[5:7])
        day = int(enablement_date[8:10])
    else:
        year, month, day = enablement_date.year, enablement_date.month, enablement_date.day
    if day > 1:
        month += 1
        if month > 12:
            month = 1
            year += 1
    return f"{year:04d}-{month:02d}"


def get_capture_by_practice(practice: str | None = None) -> list[CapturePracticeRollup]:
    payload, _ = cache_store.load("capture_by_practice")
    items = [CapturePracticeRollup(**row) for row in (payload or [])]

    trend_payload, _ = cache_store.load("capture_utilization_trend_monthly_by_practice")
    by_practice_period: dict[str, dict[str, dict]] = {}
    for row in trend_payload or []:
        by_practice_period.setdefault(row["practice"], {})[row["period"][:7]] = row

    result = []
    for item in items:
        periods = by_practice_period.get(item.practice, {})
        baseline_period = _capture_baseline_period(item.enablement_date)
        pct_change = None
        if baseline_period and periods:
            latest_period = max(periods)
            baseline_row = periods.get(baseline_period)
            latest_row = periods.get(latest_period)
            if baseline_row and latest_row and latest_period != baseline_period:
                baseline_capturable = baseline_row.get("capturable_exams_enabled") or 0
                latest_capturable = latest_row.get("capturable_exams_enabled") or 0
                baseline_rate = (
                    (baseline_row.get("captured_exams_enabled") or 0) / baseline_capturable
                    if baseline_capturable
                    else None
                )
                latest_rate = (
                    (latest_row.get("captured_exams_enabled") or 0) / latest_capturable if latest_capturable else None
                )
                pct_change = _pct_change(latest_rate, baseline_rate)
        result.append(item.model_copy(update={"pct_change_since_enablement": pct_change}))

    if practice:
        result = [r for r in result if r.practice == practice]
    return result


def get_capture_by_radiologist(practice: str | None = None) -> list[CaptureRadiologistItem]:
    payload, _ = cache_store.load("capture_by_radiologist")
    items = [CaptureRadiologistItem(**row) for row in (payload or [])]
    if practice:
        items = [r for r in items if r.practice == practice]
    return items


def get_capture_utilization_trend_by_practice(
    granularity: str = "week", practice: str | None = None
) -> list[CaptureUtilizationTrendPracticePoint]:
    cache_key = (
        "capture_utilization_trend_weekly_by_practice"
        if granularity == "week"
        else "capture_utilization_trend_monthly_by_practice"
    )
    payload, _ = cache_store.load(cache_key)
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]

    by_practice: dict[str, list[dict]] = {}
    for row in rows:
        by_practice.setdefault(row["practice"], []).append(row)

    points = []
    for prac, prac_rows in by_practice.items():
        prac_rows.sort(key=lambda r: r["period"])
        prev_pct_all = None
        prev_pct_enabled = None
        for row in prac_rows:
            capturable_all = row.get("capturable_exams_all") or 0
            captured_all = row.get("captured_exams_all") or 0
            capturable_enabled = row.get("capturable_exams_enabled") or 0
            captured_enabled = row.get("captured_exams_enabled") or 0
            pct_all = (captured_all / capturable_all) if capturable_all else None
            pct_enabled = (captured_enabled / capturable_enabled) if capturable_enabled else None
            points.append(
                CaptureUtilizationTrendPracticePoint(
                    period=row["period"],
                    granularity=granularity,
                    practice=prac,
                    capturable_exams_all=capturable_all,
                    captured_exams_all=captured_all,
                    pct_captured_all=pct_all,
                    capturable_exams_enabled=capturable_enabled,
                    captured_exams_enabled=captured_enabled,
                    pct_captured_enabled=pct_enabled,
                    pct_change_all=_pct_change(pct_all, prev_pct_all),
                    pct_change_enabled=_pct_change(pct_enabled, prev_pct_enabled),
                )
            )
            prev_pct_all = pct_all
            prev_pct_enabled = pct_enabled
    points.sort(key=lambda p: (p.practice or "", p.period))
    return points


def get_capture_utilization_trend_by_radiologist(
    granularity: str = "week", practice: str | None = None, npi: int | None = None
) -> list[CaptureUtilizationTrendRadiologistPoint]:
    cache_key = (
        "capture_utilization_trend_weekly_by_radiologist"
        if granularity == "week"
        else "capture_utilization_trend_monthly_by_radiologist"
    )
    payload, _ = cache_store.load(cache_key)
    rows = payload or []

    dim_payload, _ = cache_store.load("capture_by_radiologist")
    dim_by_npi = {row["npi"]: row for row in (dim_payload or [])}

    if practice:
        rows = [r for r in rows if dim_by_npi.get(r["npi"], {}).get("practice") == practice]
    if npi:
        rows = [r for r in rows if r["npi"] == npi]

    by_npi: dict[int, list[dict]] = {}
    for row in rows:
        by_npi.setdefault(row["npi"], []).append(row)

    points = []
    for rad_npi, npi_rows in by_npi.items():
        npi_rows.sort(key=lambda r: r["period"])
        dim = dim_by_npi.get(rad_npi, {})
        prev_pct = None
        for row in npi_rows:
            capturable = row.get("capturable_exams") or 0
            captured = row.get("captured_exams") or 0
            pct = (captured / capturable) if capturable else None
            points.append(
                CaptureUtilizationTrendRadiologistPoint(
                    period=row["period"],
                    granularity=granularity,
                    npi=rad_npi,
                    radiologist_name=dim.get("radiologist_name"),
                    practice=dim.get("practice"),
                    capture_enabled=dim.get("capture_enabled"),
                    capturable_exams=capturable,
                    captured_exams=captured,
                    pct_captured=pct,
                    pct_change=_pct_change(pct, prev_pct),
                )
            )
            prev_pct = pct
    points.sort(key=lambda p: (p.practice or "", p.radiologist_name or "", p.period))
    return points


def get_capture_efficiency_trend_by_practice(
    granularity: str = "week", practice: str | None = None
) -> list[CaptureEfficiencyTrendPracticePoint]:
    cache_key = (
        "capture_efficiency_trend_weekly_by_practice"
        if granularity == "week"
        else "capture_efficiency_trend_monthly_by_practice"
    )
    payload, _ = cache_store.load(cache_key)
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]

    by_practice: dict[str, list[dict]] = {}
    for row in rows:
        by_practice.setdefault(row["practice"], []).append(row)

    points = []
    for prac, prac_rows in by_practice.items():
        prac_rows.sort(key=lambda r: r["period"])
        prev_rate = None
        for row in prac_rows:
            tbwu = row.get("capture_tbwu") or 0
            time_sec = row.get("capture_time") or 0
            baseline_contrib = row.get("capture_baseline_contrib") or 0
            rate = _rate(tbwu, time_sec)
            baseline_rate = (baseline_contrib / time_sec) if time_sec else None
            points.append(
                CaptureEfficiencyTrendPracticePoint(
                    period=row["period"],
                    granularity=granularity,
                    practice=prac,
                    capture_tbwu_per_min=rate,
                    capture_baseline_tbwu_per_min=baseline_rate,
                    pct_change=_pct_change(rate, prev_rate),
                )
            )
            prev_rate = rate
    points.sort(key=lambda p: (p.practice or "", p.period))
    return points


def get_capture_efficiency_trend_by_radiologist(
    granularity: str = "week", practice: str | None = None, npi: int | None = None
) -> list[CaptureEfficiencyTrendRadiologistPoint]:
    cache_key = (
        "capture_efficiency_trend_weekly_by_radiologist"
        if granularity == "week"
        else "capture_efficiency_trend_monthly_by_radiologist"
    )
    payload, _ = cache_store.load(cache_key)
    rows = payload or []

    dim_payload, _ = cache_store.load("capture_by_radiologist")
    dim_by_npi = {row["npi"]: row for row in (dim_payload or [])}

    if practice:
        rows = [r for r in rows if dim_by_npi.get(r["npi"], {}).get("practice") == practice]
    if npi:
        rows = [r for r in rows if r["npi"] == npi]

    by_npi: dict[int, list[dict]] = {}
    for row in rows:
        by_npi.setdefault(row["npi"], []).append(row)

    points = []
    for rad_npi, npi_rows in by_npi.items():
        npi_rows.sort(key=lambda r: r["period"])
        dim = dim_by_npi.get(rad_npi, {})
        prev_rate = None
        for row in npi_rows:
            tbwu = row.get("capture_tbwu") or 0
            time_sec = row.get("capture_time") or 0
            baseline_contrib = row.get("capture_baseline_contrib") or 0
            rate = _rate(tbwu, time_sec)
            baseline_rate = (baseline_contrib / time_sec) if time_sec else None
            points.append(
                CaptureEfficiencyTrendRadiologistPoint(
                    period=row["period"],
                    granularity=granularity,
                    npi=rad_npi,
                    radiologist_name=dim.get("radiologist_name"),
                    practice=dim.get("practice"),
                    capture_tbwu_per_min=rate,
                    capture_baseline_tbwu_per_min=baseline_rate,
                    pct_change=_pct_change(rate, prev_rate),
                )
            )
            prev_rate = rate
    points.sort(key=lambda p: (p.practice or "", p.radiologist_name or "", p.period))
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


# Metric names on ScorecardMetrics that come straight off the wide cached row (suffixed
# `_top5`/.../`_all`) - must match mosaic_service._SCORECARD_METRICS' output names exactly.
_SCORECARD_METRIC_NAMES = [
    "shifts_worked", "case_count", "addl_capacity_per_shift", "efficiency", "shift_utilization",
    "avg_units_per_shift", "ct_cases", "xr_cases", "us_cases", "mr_cases", "nm_cases", "pt_cases",
    "mg_cases", "ir_cases", "other_modality_cases", "routine_cases", "stat_cases", "stroke_cases",
    "trauma_cases", "otherp_cases",
]
_SCORECARD_WINDOWS = ["5", "10", "15", "20", "25", "30", "all"]


def get_radiologist_scorecard(practice: str | None = None) -> list[RadiologistScorecard]:
    payload, _ = cache_store.load("radiologist_scorecard")
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]

    items = []
    for row in rows:
        metrics = [
            ScorecardMetrics(
                top_n=window,
                **{name: row.get(f"{name}_top{window}" if window != "all" else f"{name}_all") for name in _SCORECARD_METRIC_NAMES},
            )
            for window in _SCORECARD_WINDOWS
        ]
        items.append(
            RadiologistScorecard(
                npi=row["npi"],
                radiologist_name=row.get("radiologist_name"),
                team=row.get("team"),
                practice=row.get("practice"),
                mosaic_go_live_date=row.get("mosaic_go_live_date"),
                metrics=metrics,
            )
        )
    return items


def get_undrafted_filter_options() -> UndraftedFilterOptions:
    payload, _ = cache_store.load("undrafted_analysis")
    rows = payload or []
    return UndraftedFilterOptions(
        exam_categories=sorted({r["exam_category"] for r in rows if r.get("exam_category")}),
        sites=sorted({r["site"] for r in rows if r.get("site")}),
    )


def get_undrafted_analysis(
    practice: str | None = None, exam_category: str | None = None, site: str | None = None
) -> list[UndraftedCategoryPoint]:
    payload, _ = cache_store.load("undrafted_analysis")
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("local_practice") == practice]
    if exam_category:
        rows = [r for r in rows if r.get("exam_category") == exam_category]
    if site:
        rows = [r for r in rows if r.get("site") == site]

    # Collapse site/exam_category away after filtering - they're only ever used as filter
    # criteria; shipping every (week, practice, team, site, exam_category, category)
    # combination to the browser would be ~845K rows / 120MB+ for the unfiltered case, far
    # more than the chart (which only ever groups by week/practice/team/category) needs.
    collapsed: dict[tuple, dict] = {}
    for row in rows:
        key = (row["week_start"], row.get("local_practice"), row.get("team"), row["category"], row["category_sort_order"])
        acc = collapsed.setdefault(key, {"exam_count": 0, "tbwu": 0.0})
        acc["exam_count"] += row.get("exam_count") or 0
        acc["tbwu"] += row.get("tbwu") or 0

    return [
        UndraftedCategoryPoint(
            week_start=key[0],
            local_practice=key[1],
            team=key[2],
            category=key[3],
            category_sort_order=key[4],
            exam_count=acc["exam_count"],
            tbwu=acc["tbwu"],
        )
        for key, acc in collapsed.items()
    ]
