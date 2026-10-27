"""Public read API the routes call. Every function here reads from the local SQLite cache
(populated by app.services.refresh_service) instead of querying EDW live, so dashboard loads
are instant and independent of the Databricks warehouse's performance. Any filtering,
pagination, or windowing a route needs is applied here in Python over the cached dataset,
since the underlying EDW queries in app.services.mosaic_service are no longer called
per-request - only by the background/manual refresh job.
"""

from app.data import capture_enablement, local_region, mvp_context, mvp_dashboard_stats, mvp_mentor_matching, mvp_methodology_checks, rad_survey
from app.db import cache_store, efficiency_store
from app.services import movers_service, next_best_action_service
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
    DraftInsightCategoryGroup,
    DraftInsightCategoryStat,
    DraftInsightModalityStat,
    DraftInsightOverview,
    DraftInsightPracticeStat,
    DraftInsightSampleItem,
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyPracticeRollup,
    EfficiencyRadiologistItem,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    EngagementCapacityPlan,
    MammoScreeningTrendPoint,
    MentorMatchStatus,
    MosaicIntelligenceSnapshot,
    MoversDecomposition,
    MvpProgramContext,
    MvpRadiologistItem,
    NextBestActionList,
    PopulationEfficiency,
    RadiologistRosterItem,
    LikertDistribution,
    PracticeNpsStat,
    RadiologistLookupMatch,
    RadSurveySummary,
    RadSummaryStat,
    RpceTrendPoint,
    ShiftUtilizationItem,
    ThemeStat,
    UndraftedCategoryPoint,
    UndraftedFilterOptions,
    UtilizationPracticeRollup,
    VolumeFilterOptions,
    VolumeGroupRollup,
    VolumeSummary,
    VolumeTrendPoint,
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


def get_drafting_blockers_by_practice() -> list[BlockerByPractice]:
    payload, _ = cache_store.load("drafting_blockers_by_practice")
    return [BlockerByPractice(**row) for row in (payload or [])]


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


def get_efficiency_movers(
    group_col: str,
    group_value: str,
    decompose_by: str = "exam_category",
    mode: str = "full_mosaic",
    comparison: str = "peers",
) -> MoversDecomposition:
    """Why is this group's efficiency different - harder work, or slower reading?

    Reads per-bucket num/den from the efficiency matrix and hands the division to
    `movers_service`, which splits the gap into mix and rate exactly. Raises ValueError for an
    unknown column; the route turns that into a 400 rather than guessing a column, because a
    silently substituted group-by renders a plausible number for the wrong question.
    """
    safe_mode = mode if mode in VALID_MODES else "full_mosaic"
    safe_comparison = "baseline" if comparison == "baseline" else "peers"
    rows = efficiency_store.decomposition_rows(
        group_col=group_col,
        group_value=group_value,
        decompose_by=decompose_by,
        mode=safe_mode,
    )
    result = movers_service.decompose(rows, comparison=safe_comparison, bucket_label=decompose_by)
    return MoversDecomposition(
        group_col=group_col,
        group_value=str(group_value),
        mode=safe_mode,
        **result,
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


def _aggregate_trend_rows(rows: list[dict], practice: str | None, exam_category: str | None) -> list[EfficiencyTrendPoint]:
    """Shared by get_efficiency_trend (practice/category filtered) and
    get_efficiency_trend_by_local_team (grouped by Local team) - rolls arbitrary raw
    efficiency_trend_by_practice_category rows up to one point per month and computes every
    rate/pct_change, including the "Drafting Only" vs "Drafting + Capture" split."""
    by_period: dict[str, dict] = {}
    for row in rows:
        acc = by_period.setdefault(
            row["period"],
            {
                "reporting_tbwu": 0.0, "reporting_time": 0.0, "reporting_baseline_contrib": 0.0,
                "reporting_rad_count": 0, "reporting_exam_count": 0,
                "drafting_tbwu": 0.0, "drafting_time": 0.0, "drafting_baseline_contrib": 0.0,
                "drafting_rad_count": 0, "drafting_exam_count": 0,
                "capture_tbwu": 0.0, "capture_time": 0.0, "capture_baseline_contrib": 0.0,
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
        # "Drafting Only" = Drafting excluding Capture-modality (US/BD) rows - Capture is a
        # subset of Drafting by modality, not a separate Period_Type (confirmed live
        # 2026-10-20) - so this is just Drafting's totals minus Capture's.
        drafting_only_eff = _rate(d["drafting_tbwu"] - d["capture_tbwu"], d["drafting_time"] - d["capture_time"])
        # baseline_contrib is already per-minute weighted by time (seconds), so divide by
        # raw seconds directly - see efficiency_store._baseline_rate for the derivation.
        reporting_baseline = (d["reporting_baseline_contrib"] / d["reporting_time"]) if d["reporting_time"] else None
        drafting_baseline = (d["drafting_baseline_contrib"] / d["drafting_time"]) if d["drafting_time"] else None
        full_mosaic_baseline = (
            (d["reporting_baseline_contrib"] + d["drafting_baseline_contrib"]) / (d["reporting_time"] + d["drafting_time"])
            if (d["reporting_time"] + d["drafting_time"])
            else None
        )
        drafting_only_time = d["drafting_time"] - d["capture_time"]
        drafting_only_baseline = (
            (d["drafting_baseline_contrib"] - d["capture_baseline_contrib"]) / drafting_only_time
            if drafting_only_time
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
                drafting_only_tbwu_per_min=drafting_only_eff,
                reporting_pct_change=_pct_change(reporting_eff, reporting_baseline),
                drafting_pct_change=_pct_change(drafting_eff, drafting_baseline),
                full_mosaic_pct_change=_pct_change(full_mosaic_eff, full_mosaic_baseline),
                drafting_only_pct_change=_pct_change(drafting_only_eff, drafting_only_baseline),
                reporting_rad_count=int(d["reporting_rad_count"]),
                drafting_rad_count=int(d["drafting_rad_count"]),
                reporting_exam_count=int(d["reporting_exam_count"]),
                drafting_exam_count=int(d["drafting_exam_count"]),
            )
        )
    return points


def get_efficiency_trend(exam_category: str | None = None, practice: str | None = None) -> list[EfficiencyTrendPoint]:
    cache_key = "efficiency_trend_by_practice_category" if practice else "efficiency_trend_by_category"
    payload, _ = cache_store.load(cache_key)
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]
    if exam_category:
        rows = [r for r in rows if r.get("exam_category") == exam_category]
    return _aggregate_trend_rows(rows, practice, exam_category)


def get_efficiency_trend_by_local_team() -> dict[str, list[EfficiencyTrendPoint]]:
    """MVP Area Detail dashboard's 4-line "Efficiency Change, Time Series" chart - all 6 Local
    teams computed in one call (there are only 6, and the dashboard needs instant switching
    between them) from the same already-cached efficiency_trend_by_practice_category rows,
    grouped via local_region.get_local_region() instead of raw practice. No new EDW query."""
    payload, _ = cache_store.load("efficiency_trend_by_practice_category")
    by_team: dict[str, list[dict]] = {team: [] for team in local_region.LOCAL_REGIONS}
    for row in payload or []:
        team = local_region.get_local_region(row.get("practice"))
        by_team[team].append(row)
    return {team: _aggregate_trend_rows(rows, None, None) for team, rows in by_team.items()}


def get_mammo_screening_trend() -> list[MammoScreeningTrendPoint]:
    """RP-wide + MVP-mammo-cohort-only Screening-Mammo volume/efficiency, monthly - see
    mosaic_service.get_mammo_screening_trend for the EDW query. Returns RP-wide points; the
    MVP-mammo-only series is returned as a second, separately-keyed list from the same cached
    rows so the frontend can render both combo charts without a second fetch."""
    payload, _ = cache_store.load("mammo_screening_trend")
    points = []
    for row in payload or []:
        eff = _rate(row.get("screening_tbwu"), row.get("screening_time"))
        baseline = (row["screening_baseline_contrib"] / row["screening_time"]) if row.get("screening_time") else None
        points.append(
            MammoScreeningTrendPoint(
                period=row["period"],
                screening_volume=int(row.get("screening_volume") or 0),
                screening_efficiency_change_pct=_pct_change(eff, baseline),
            )
        )
    return points


def get_mvp_mammo_screening_trend() -> list[MammoScreeningTrendPoint]:
    """Same cached rows as get_mammo_screening_trend, reshaped to the MVP-mammo-cohort-only
    columns instead of the RP-wide ones."""
    payload, _ = cache_store.load("mammo_screening_trend")
    points = []
    for row in payload or []:
        eff = _rate(row.get("mvp_mammo_screening_tbwu"), row.get("mvp_mammo_screening_time"))
        baseline = (
            row["mvp_mammo_screening_baseline_contrib"] / row["mvp_mammo_screening_time"]
            if row.get("mvp_mammo_screening_time")
            else None
        )
        points.append(
            MammoScreeningTrendPoint(
                period=row["period"],
                screening_volume=int(row.get("mvp_mammo_screening_volume") or 0),
                screening_efficiency_change_pct=_pct_change(eff, baseline),
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


def get_mvp_radiologists() -> list[MvpRadiologistItem]:
    """Every radiologist the real Mosaic Value Project program has tiered or excluded, read
    straight from rad_onboarding (see mosaic_service.get_mvp_rad_onboarding) - no EDW
    re-derivation needed, the cached row already has everything the model wants. Attaches
    mentor_match from the separate, hand-extracted peer-coach matching snapshot (see
    app/data/mvp_mentor_matching.py) when this radiologist's NPI appears there - a real,
    actively-worked status, unlike rad_onboarding's own near-always-empty mentor fields."""
    payload, _ = cache_store.load("mvp_rad_onboarding_raw")
    results = []
    for row in payload or []:
        npi = row.get("npi")
        match = mvp_mentor_matching.MENTOR_MATCH_BY_NPI.get(int(npi)) if npi is not None else None
        results.append(
            MvpRadiologistItem(
                radiologist_name=row.get("rad_name"),
                mentor_match=MentorMatchStatus(**match) if match else None,
                **{k: v for k, v in row.items() if k != "rad_name"},
            )
        )
    results.sort(key=lambda r: ((r.mvp_cohort or "zzz"), r.radiologist_name or ""))
    return results


def get_mvp_methodology_check(scope: str) -> dict:
    """Honest, live-recomputed checks on whether the Impact classification's before/after
    comparison can be trusted for this scope - see app/data/mvp_methodology_checks.py's own
    docstring for what each of the three checks means and why they exist. Operates on the raw
    cache_store rows directly (same as mvp_weekly_report_service.py), not the Pydantic-validated
    MvpRadiologistItem list, since the checks need the exact same string/float-mixed values
    mvp_dashboard_stats.compute_impact_breakdown itself reads."""
    rows, _ = cache_store.load("mvp_rad_onboarding_raw")
    scoped = mvp_dashboard_stats.scope_rows(rows or [], scope)
    return mvp_methodology_checks.compute_methodology_check(scoped)


def get_mvp_context() -> MvpProgramContext:
    """Static program narrative/glossary (see app/data/mvp_context.py for provenance) plus one
    live field - ai_generated_narrative, precomputed on the normal 30-minute refresh cycle (see
    refresh_service.DATASETS -> ai_context_service.generate_mvp_program_narrative), never
    generated live on page load. Falls back to the static CURRENT_STATUS_NOTES text if the
    narrative dataset hasn't refreshed yet (e.g. right after a fresh deploy)."""
    payload, _ = cache_store.load("mvp_program_narrative")
    overview_payload, _ = cache_store.load("mvp_overview_narrative")
    mammo_payload, _ = cache_store.load("mvp_mammo_narrative")
    return MvpProgramContext(
        program_narrative=mvp_context.PROGRAM_NARRATIVE,
        program_history=mvp_context.PROGRAM_HISTORY,
        priority_tier_definitions=mvp_context.PRIORITY_TIER_DEFINITIONS,
        exclusion_reason_glossary=mvp_context.EXCLUSION_REASON_GLOSSARY,
        engagement_process_steps=mvp_context.ENGAGEMENT_PROCESS_STEPS,
        mentorship_program_summary=mvp_context.MENTORSHIP_PROGRAM_SUMMARY,
        current_status_notes=mvp_context.CURRENT_STATUS_NOTES,
        ai_generated_narrative=payload or mvp_context.CURRENT_STATUS_NOTES,
        engagement_capacity_plan=EngagementCapacityPlan(**mvp_context.ENGAGEMENT_CAPACITY_PLAN),
        overview_narrative=overview_payload or "",
        mammo_narrative=mammo_payload or "",
    )


def get_rad_survey_summary() -> RadSurveySummary:
    """Static, hand-compiled snapshot - see app/data/rad_survey.py for provenance. No EDW/cache
    dependency, unlike everything else in this file."""
    return RadSurveySummary(
        sent=rad_survey.SENT,
        responses=rad_survey.RESPONSES,
        response_rate=rad_survey.RESPONSE_RATE,
        median_completion_minutes=rad_survey.MEDIAN_COMPLETION_MINUTES,
        nps=rad_survey.NPS,
        nps_distribution=rad_survey.NPS_DISTRIBUTION,
        promoters=rad_survey.PROMOTERS,
        passives=rad_survey.PASSIVES,
        detractors=rad_survey.DETRACTORS,
        agreement_statements=[LikertDistribution(**row) for row in rad_survey.AGREEMENT_STATEMENTS],
        feature_satisfaction=[LikertDistribution(**row) for row in rad_survey.FEATURE_SATISFACTION],
        problem_frequency=[LikertDistribution(**row) for row in rad_survey.PROBLEM_FREQUENCY],
        top_frustration_themes=[ThemeStat(**row) for row in rad_survey.TOP_FRUSTRATION_THEMES],
        top_praised_themes=[ThemeStat(**row) for row in rad_survey.TOP_PRAISED_THEMES],
        by_practice=[PracticeNpsStat(**row) for row in rad_survey.BY_PRACTICE],
    )


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
        # Prefer the real practice-level enablement date from the Capture Deployment/Phase 3
        # trackers (see app/data/capture_enablement.py) over the derived "first captured exam"
        # proxy, when a real one is known.
        real_date, opted_out = capture_enablement.capture_enablement_for(item.practice)
        if real_date:
            item = item.model_copy(update={"enablement_date": real_date})
        item = item.model_copy(update={"opted_out": opted_out})

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


def get_shift_utilization_by_radiologist(practice: str | None = None) -> list[ShiftUtilizationItem]:
    payload, _ = cache_store.load("shift_utilization_by_radiologist")
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]
    return [ShiftUtilizationItem(**row) for row in rows]


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
    # more than the chart (which only ever groups by week/practice/region/category) needs.
    #
    # `team` collapses to its six-bucket Local Region rather than shipping as a full practice
    # name, because the Local filter is the only thing the page ever does with it (the team
    # name is never rendered on this surface). That choice is what keeps the two hierarchies
    # affordable now that `local_practice` is the managing site rather than a duplicate of
    # `team`: measured on prod, week x managing x provider x category is 131,492 collapsed
    # rows (4.51x the old 29,130), while week x managing x region x category is 72,175 (2.48x).
    # Callers that need the real team read the raw cache rows instead - see
    # `next_best_action_service.rank` and `mvp_weekly_report_service`.
    collapsed: dict[tuple, dict] = {}
    for row in rows:
        # Finalized exams with no final_datetime land in the cache with a null `week_start`,
        # which JSON-serializes to the *string* "None" (~2,700 of 2.97M rows today). The
        # model types this field as a `date`, so one such row used to fail validation and
        # 500 the whole endpoint - taking the chart down over 0.09% of the data.
        # `next_best_action_service.rank` drops the same rows for its own reason (str(None)
        # sorts after every ISO date, so an undated row would be admitted as the newest
        # week); keep the two treatments in step.
        week_start = row.get("week_start")
        if not week_start or str(week_start) == "None":
            continue
        key = (
            week_start,
            row.get("local_practice"),
            local_region.get_local_region(row.get("team")),
            row["category"],
            row["category_sort_order"],
        )
        acc = collapsed.setdefault(key, {"exam_count": 0, "tbwu": 0.0})
        acc["exam_count"] += row.get("exam_count") or 0
        acc["tbwu"] += row.get("tbwu") or 0

    return [
        UndraftedCategoryPoint(
            week_start=key[0],
            local_practice=key[1],
            local_region=key[2],
            category=key[3],
            category_sort_order=key[4],
            exam_count=acc["exam_count"],
            tbwu=acc["tbwu"],
        )
        for key, acc in collapsed.items()
    ]


def get_next_best_actions(
    weeks: int = 8, min_addressable_tbwu: float = 500.0, benchmark_pctile: float = 0.75, limit: int = 25
) -> NextBestActionList:
    """Drafting worklist ranked by expected TBWU unlock (plan item E-4).

    Reads the same cached `undrafted_analysis` payload the Non-Drafted chart uses - no second
    dataset, no EDW round trip - and hands it to the pure ranking function, which is where the
    arithmetic and its justification live.
    """
    payload, _ = cache_store.load("undrafted_analysis")
    result = next_best_action_service.rank(
        payload or [],
        weeks=weeks,
        min_addressable_tbwu=min_addressable_tbwu,
        benchmark_pctile=benchmark_pctile,
        limit=limit,
    )
    return NextBestActionList(**result)


def _load_draft_insights_raw() -> list[dict]:
    payload, _ = cache_store.load("draft_insights_raw")
    return payload or []


def _split_categories(value: str | None) -> list[str]:
    if not value:
        return []
    return [c.strip() for c in value.split(",") if c.strip() and c.strip().lower() != "none"]


def _avg_retention(rows: list[dict]) -> float | None:
    values = [r["retention_pct"] for r in rows if r.get("retention_pct") is not None]
    return sum(values) / len(values) if values else None


def get_draft_insight_overview() -> DraftInsightOverview:
    rows = _load_draft_insights_raw()
    distribution: dict[str, int] = {}
    for row in rows:
        label = row.get("overall_assessment") or "Unknown"
        distribution[label] = distribution.get(label, 0) + 1
    return DraftInsightOverview(
        n=len(rows),
        avg_retention_pct=_avg_retention(rows),
        overall_assessment_distribution=distribution,
    )


def get_draft_insight_by_modality() -> list[DraftInsightModalityStat]:
    rows = _load_draft_insights_raw()
    grouped: dict[str | None, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("modality"), []).append(row)
    return [
        DraftInsightModalityStat(modality=modality, n=len(group), avg_retention_pct=_avg_retention(group))
        for modality, group in sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]


def get_draft_insight_by_practice() -> list[DraftInsightPracticeStat]:
    rows = _load_draft_insights_raw()
    grouped: dict[str | None, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("practice"), []).append(row)
    return [
        DraftInsightPracticeStat(practice=practice, n=len(group), avg_retention_pct=_avg_retention(group))
        for practice, group in sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]


_CATEGORY_DIMENSIONS = [
    ("added_by_radiologist", "added_by_radiologist_categories"),
    ("removed_from_draft", "removed_from_draft_categories"),
    ("formatting", "formatting_categories"),
    ("clinical_interpretation", "clinical_interpretation_categories"),
    ("additional_findings", "additional_findings_categories"),
]


def get_draft_insight_categories() -> list[DraftInsightCategoryGroup]:
    rows = _load_draft_insights_raw()
    groups = []
    for dimension, column in _CATEGORY_DIMENSIONS:
        tally: dict[str, int] = {}
        for row in rows:
            for category in _split_categories(row.get(column)):
                tally[category] = tally.get(category, 0) + 1
        total = sum(tally.values())
        categories = [
            DraftInsightCategoryStat(category=category, count=count, pct=(count / total * 100) if total else 0.0)
            for category, count in sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
        ]
        groups.append(DraftInsightCategoryGroup(dimension=dimension, categories=categories))
    return groups


def get_draft_insight_samples(overall_assessment: str | None = None, limit: int = 50) -> list[DraftInsightSampleItem]:
    rows = _load_draft_insights_raw()
    if overall_assessment:
        rows = [r for r in rows if r.get("overall_assessment") == overall_assessment]
    safe_limit = max(1, min(int(limit), 500))
    return [
        DraftInsightSampleItem(
            accession_number=row["accession_number"],
            overall_assessment=row.get("overall_assessment"),
            retention_pct=row.get("retention_pct"),
            added_by_radiologist=row.get("added_by_radiologist"),
            removed_from_draft=row.get("removed_from_draft"),
        )
        for row in rows[:safe_limit]
    ]


# Below this floor, additional_capacity_pct is a division by a near-zero/unreliable baseline
# (e.g. a practice with almost no shifts matched to a real baseline still averages to some
# tiny non-zero value from a handful of stragglers) and blows up to absurd magnitudes (verified
# live: Matrix showed +59,020,209% at a baseline of 0.0000173 TBWU/hr) rather than a real
# signal - null it out instead of shipping a distorted number the UI would have to explain.
_MIN_RELIABLE_BASELINE_TBWU_PER_HOUR = 0.5


def get_capacity_baseline_scorecard() -> list[CapacityBaselineScorecard]:
    # Prefer the review-overridden merge (baseline_overrides.recompute_capacity_with_overrides)
    # so an accepted/overridden Baseline Review Queue decision actually changes this number -
    # falls back to the pristine EDW rows only in the brief window right after a fresh deploy,
    # before the first merge has run.
    payload, _ = cache_store.load("capacity_with_baseline_merged")
    if payload is None:
        payload, _ = cache_store.load("capacity_with_baseline_raw")
    rows = payload or []
    grouped: dict[str, dict] = {}
    for row in rows:
        practice = row.get("practice")
        if not practice:
            continue
        acc = grouped.setdefault(
            practice,
            {"total_shifts": 0, "total_hours": 0.0, "sum_baseline": 0.0, "sum_capacity": 0.0,
             "exact": 0, "proxy": 0, "manual_review": 0, "no_baseline": 0},
        )
        hours = row.get("no_hours") or 0.0
        acc["total_shifts"] += 1
        acc["total_hours"] += hours
        acc["sum_capacity"] += row.get("on_shift_capacity_rpwu") or 0.0
        baseline_type = row.get("baseline_type")
        if baseline_type == "Exact":
            acc["exact"] += 1
        elif baseline_type == "Proxy":
            acc["proxy"] += 1
        elif baseline_type == "Manual Review":
            acc["manual_review"] += 1
        else:
            acc["no_baseline"] += 1
        if row.get("shift_baseline_rpwu_fixed") is not None:
            acc["sum_baseline"] += row["shift_baseline_rpwu_fixed"]

    results = []
    for practice, acc in grouped.items():
        total_shifts = acc["total_shifts"]
        total_hours = acc["total_hours"]
        baseline_capacity = acc["sum_baseline"] / total_hours if total_hours else None
        avg_capacity = acc["sum_capacity"] / total_hours if total_hours else None
        reliable = baseline_capacity is not None and baseline_capacity >= _MIN_RELIABLE_BASELINE_TBWU_PER_HOUR
        capacity_change = (avg_capacity - baseline_capacity) if reliable and avg_capacity is not None else None
        additional_pct = (capacity_change / baseline_capacity * 100) if reliable and capacity_change is not None else None
        results.append(
            CapacityBaselineScorecard(
                practice=practice,
                total_shifts=total_shifts,
                total_hours=total_hours,
                baseline_capacity_tbwu_per_hour=baseline_capacity,
                avg_capacity_tbwu_per_hour=avg_capacity,
                capacity_change_tbwu_per_hour=capacity_change,
                additional_capacity_pct=additional_pct,
                pct_exact=(acc["exact"] / total_shifts * 100) if total_shifts else None,
                pct_proxy=(acc["proxy"] / total_shifts * 100) if total_shifts else None,
                pct_manual_review=(acc["manual_review"] / total_shifts * 100) if total_shifts else None,
                pct_no_baseline=(acc["no_baseline"] / total_shifts * 100) if total_shifts else None,
            )
        )
    return sorted(results, key=lambda r: r.total_shifts, reverse=True)


def get_baseline_proxy_detail(practice: str | None = None) -> list[BaselineProxyDetail]:
    payload, _ = cache_store.load("baseline_proxy_detail_raw")
    rows = payload or []
    if practice:
        rows = [r for r in rows if r.get("practice") == practice]
    return [
        BaselineProxyDetail(
            npi=row["npi"],
            radiologist_name=row.get("radiologist_name"),
            practice=row.get("practice"),
            target_shift=row["target_shift"],
            proxy_shift=row["proxy_shift"],
            total_match_score=row.get("total_match_score"),
            score_subspecialty=row.get("score_subspecialty"),
            score_interventional=row.get("score_interventional"),
            score_modality=row.get("score_modality"),
            score_tbwu=row.get("score_tbwu"),
            score_shift_duration=row.get("score_shift_duration"),
            score_location=row.get("score_location"),
            score_weekday_weekend=row.get("score_weekday_weekend"),
            score_time_of_day=row.get("score_time_of_day"),
            score_work_type=row.get("score_work_type"),
            baseline_type=row.get("baseline_type"),
        )
        for row in rows
    ]


def get_baseline_proxy_candidates(npi: int | None = None, target_shift: str | None = None) -> list[BaselineProxyCandidate]:
    payload, _ = cache_store.load("baseline_proxy_candidates_raw")
    rows = payload or []
    if npi is not None:
        rows = [r for r in rows if r.get("npi") == npi]
    if target_shift:
        rows = [r for r in rows if r.get("target_shift") == target_shift]
    return [
        BaselineProxyCandidate(
            npi=row["npi"],
            radiologist_name=row.get("radiologist_name"),
            practice=row.get("practice"),
            target_shift=row["target_shift"],
            rank=row["rank"],
            proxy_shift=row["proxy_shift"],
            total_match_score=row.get("total_match_score"),
            score_subspecialty=row.get("score_subspecialty"),
            score_interventional=row.get("score_interventional"),
            score_modality=row.get("score_modality"),
            score_tbwu=row.get("score_tbwu"),
            score_shift_duration=row.get("score_shift_duration"),
            score_location=row.get("score_location"),
            score_weekday_weekend=row.get("score_weekday_weekend"),
            score_time_of_day=row.get("score_time_of_day"),
            score_work_type=row.get("score_work_type"),
            baseline_tbwu_per_hour=row.get("baseline_tbwu_per_hour"),
        )
        for row in rows
    ]


def search_radiologist_lookup(query: str) -> list[RadiologistLookupMatch]:
    """Minimal search-result shape, deliberately not the full roster payload - matches PCC's
    own "no endpoint that lists a roster" rule for this exact kind of gated drilldown. Caller
    (the route) is responsible for enforcing the 3-character minimum before calling this."""
    payload, _ = cache_store.load("radiologist_roster")
    needle = query.strip().lower()
    matches = [
        row for row in (payload or [])
        if row.get("radiologist_name") and needle in row["radiologist_name"].lower()
    ]
    return [
        RadiologistLookupMatch(
            npi=row["npi"],
            radiologist_name=row.get("radiologist_name"),
            home_practice=row.get("home_practice"),
        )
        for row in matches[:25]
    ]


def get_radiologist_lookup_detail(npi: int) -> dict:
    """Aggregated detail payload for one radiologist, assembled purely from already-cached
    data (zero new EDW queries) - roster entry, per-category efficiency breakdown, capacity
    rollup, and scorecard. Returns a plain dict (display-only composite, no single Pydantic
    model fits all four shapes cleanly)."""
    roster_payload, _ = cache_store.load("radiologist_roster")
    roster_row = next((r for r in (roster_payload or []) if r.get("npi") == npi), None)

    capacity_payload, _ = cache_store.load("capacity_by_radiologist")
    capacity_row = next((r for r in (capacity_payload or []) if r.get("npi") == npi), None)

    scorecard_payload, _ = cache_store.load("radiologist_scorecard")
    scorecard_row = next((r for r in (scorecard_payload or []) if r.get("npi") == npi), None)

    return {
        "npi": npi,
        "roster": roster_row,
        "capacity": capacity_row,
        "scorecard": scorecard_row,
        "efficiency_by_category": efficiency_store.rows_for_npi(npi),
    }


_EMPTY_VOLUME_SUMMARY = {
    "total_exams": 0,
    "mosaic_exams": 0,
    "pct_mosaic": None,
    "drafting_exams": 0,
    "pct_drafting": None,
    "pct_rpce_reporting": None,
    "pct_rpce_drafting": None,
}


def get_volume_summary() -> VolumeSummary:
    payload, _ = cache_store.load("volume_summary")
    return VolumeSummary(**(payload or _EMPTY_VOLUME_SUMMARY))


def get_volume_by_practice() -> list[VolumeGroupRollup]:
    payload, _ = cache_store.load("volume_by_practice")
    return [VolumeGroupRollup(**row) for row in (payload or [])]


def get_volume_by_team() -> list[VolumeGroupRollup]:
    payload, _ = cache_store.load("volume_by_team")
    return [VolumeGroupRollup(**row) for row in (payload or [])]


def get_volume_by_local_region() -> list[VolumeGroupRollup]:
    payload, _ = cache_store.load("volume_by_local_region")
    return [VolumeGroupRollup(**row) for row in (payload or [])]


def get_volume_trend() -> list[VolumeTrendPoint]:
    payload, _ = cache_store.load("volume_trend")
    return [VolumeTrendPoint(**row) for row in (payload or [])]


def get_volume_filter_options() -> VolumeFilterOptions:
    payload, _ = cache_store.load("volume_filter_options")
    return VolumeFilterOptions(**(payload or {"practices": [], "teams": [], "local_regions": []}))
