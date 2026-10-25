from datetime import date

from pydantic import BaseModel


class Note(BaseModel):
    """A freeform note attached to a radiologist (entity_key = NPI as string) or a practice
    (entity_key = practice name) - see app/db/postgres_client.py's mosaic.notes table."""

    entity_type: str
    entity_key: str
    note_text: str
    created_at: str


class RadiologistLookupMatch(BaseModel):
    """Minimal search-result shape for the Radiologist Lookup page - deliberately not the
    full roster/scorecard payload, matching PCC's own "no endpoint that lists a roster" rule."""

    npi: int
    radiologist_name: str | None
    home_practice: str | None


class RadiologistRosterItem(BaseModel):
    npi: int
    radiologist_name: str | None
    home_practice: str | None
    working_subspecialty: str | None
    deployment_status: str | None
    deployment_launch_group: str | None
    current_team: str | None
    # Where the rad actually reads, as opposed to where they belong. Optional so cached
    # roster payloads written before these two fields existed still deserialize.
    primary_site: str | None = None
    site_count: int | None = None
    reporting_cases_read: float | None = None
    total_drafting_cases: float | None = None
    total_mosaic_exams: int | None = None
    capture_enabled: bool | None = None


class UtilizationPracticeRollup(BaseModel):
    practice: str | None
    total_exams: float | None
    mosaic_exams: float | None
    pct_mosaic: float | None
    drafting_exams: float | None
    pct_drafting: float | None
    capture_exams: float | None
    mammo_exams: float | None
    mammo_mosaic_exams: float | None
    pct_mammo_mosaic: float | None
    rads_live: int | None
    rads_drafting: int | None


class BlockerByPractice(BaseModel):
    practice: str | None
    blocker: str
    count: int


class EfficiencyRadiologistItem(BaseModel):
    npi: int
    radiologist_name: str | None
    practice: str | None
    subspecialty: str | None
    mosaic_tbwu_per_min: float | None
    baseline_tbwu_per_min: float | None
    pct_change_vs_baseline: float | None
    read_time_change_pct: float | None


class EfficiencyPracticeRollup(BaseModel):
    practice: str | None
    mosaic_tbwu_per_min: float | None
    baseline_tbwu_per_min: float | None
    pct_change_vs_baseline: float | None
    read_time_change_pct: float | None


class EfficiencyDetail(BaseModel):
    mode: str
    rp_benchmark_mosaic_tbwu_per_min: float | None
    rp_benchmark_baseline_tbwu_per_min: float | None
    by_radiologist: list[EfficiencyRadiologistItem]
    by_practice: list[EfficiencyPracticeRollup]


class PopulationEfficiency(BaseModel):
    mode: str
    practice: str | None
    subspecialty: str | None
    modality_code: str | None
    parent_procedure_name: str | None
    exam_category: str | None
    mosaic_tbwu_per_min: float | None
    baseline_tbwu_per_min: float | None
    pct_change_vs_baseline: float | None
    read_time_change_pct: float | None


class EfficiencyFilterOptions(BaseModel):
    practices: list[str]
    subspecialties: list[str]
    modalities: list[str]
    procedures: list[str]
    exam_categories: list[str]


class EfficiencyTrendPoint(BaseModel):
    period: str
    practice: str | None = None
    exam_category: str | None
    reporting_tbwu_per_min: float | None
    drafting_tbwu_per_min: float | None  # "Drafting + Capture" - Capture (US/BD) rows are a subset of Drafting
    full_mosaic_tbwu_per_min: float | None
    drafting_only_tbwu_per_min: float | None = None  # Drafting excluding Capture-modality (US/BD) rows
    reporting_pct_change: float | None
    drafting_pct_change: float | None
    full_mosaic_pct_change: float | None
    drafting_only_pct_change: float | None = None
    reporting_rad_count: int
    drafting_rad_count: int
    reporting_exam_count: int
    drafting_exam_count: int


class EfficiencyTrendRpAvgPoint(BaseModel):
    period: str
    drafting_tbwu_per_min: float | None
    full_mosaic_tbwu_per_min: float | None


class VolumeSummary(BaseModel):
    """Company-wide (no grouping) volume snapshot - same measure set as the governed
    mosaic_volume_metric_view's company-wide roll-up, reconciled by construction since it reuses
    mosaic_service.py's own _RPCE_SOURCE_SYSTEMS_SQL/_RPCE_PCT_ADJUSTMENT constants."""

    total_exams: int
    mosaic_exams: int
    pct_mosaic: float | None
    drafting_exams: int
    pct_drafting: float | None
    pct_rpce_reporting: float | None
    pct_rpce_drafting: float | None


class VolumeGroupRollup(BaseModel):
    """One row per group (Managing Practice, Team, or Local Region, depending on which /volume/by-*
    route returned it) - same shape as VolumeSummary plus the group label."""

    group: str | None
    total_exams: int
    mosaic_exams: int
    pct_mosaic: float | None
    drafting_exams: int
    pct_drafting: float | None
    pct_rpce_reporting: float | None
    pct_rpce_drafting: float | None


class VolumeTrendPoint(BaseModel):
    period: str
    total_exams: int
    mosaic_exams: int
    pct_mosaic: float | None
    drafting_exams: int
    pct_drafting: float | None


class VolumeFilterOptions(BaseModel):
    practices: list[str]
    teams: list[str]
    local_regions: list[str]


class MentorMatchStatus(BaseModel):
    """One radiologist's entry on the real Mosaic Mentors / peer-coach "Matching Status" sheet -
    see app/data/mvp_mentor_matching.py for provenance. Distinct from (and much more specific
    than) MvpRadiologistItem's own mosaic_mentor/mosaic_mentor_status fields, which are
    populated for almost none of the MVP cohort."""

    matching_status: str
    mentors_identified: str | None = None
    matching_notes: str | None = None
    mentorship_meeting_date: str | None = None


class MvpRadiologistItem(BaseModel):
    """One radiologist from the real Mosaic Value Project program, read directly from
    edw_prod.dataverse_m365-vra-dynamics-prod.rad_onboarding (the Dynamics-synced CRM table the
    MVP Clinical Transformation team themselves maintain) rather than approximated from EDW -
    supersedes the old from-scratch Focus Rads heuristic, which couldn't see the program's own
    cohort/exclusion/outreach fields at all. current_dc_exam_count/current_exam_count omitted -
    not meaningful at the universe level this endpoint returns (includes excluded rads)."""

    npi: int
    radiologist_name: str | None
    practice: str | None
    mvp_cohort: str | None  # "Cohort 1".."Cohort 4", optionally "(Mammo)"/"(Ops or Self Referred)"
    exclusion_reason: str | None  # None = actively tracked; populated = why this rad isn't engaged
    mvp_target_outreach_week: str | None
    reads_500_plus_dx_cases: str | None  # raw "Yes"/"No" from rad_onboarding's `500_dx_cases`
    baseline_capacity_tbwu_9h: float | None  # mvp_tbwus_9h_shift_may_jul_26
    full_mosaic_efficiency_change_pct: float | None  # vs the fixed May-Jul 2026 baseline
    xr_drafting_efficiency_change_pct: float | None
    ct_head_efficiency_change_pct: float | None
    us_capture_efficiency_change_pct: float | None
    drafting_captured_efficiency_change_pct: float | None
    efficiency_change_last_30d_pct: float | None
    full_mosaic_change_l7d_pct: float | None
    full_mosaic_change_l14d_pct: float | None
    full_mosaic_change_l30d_pct: float | None
    xr_drafting_change_l7d_pct: float | None
    xr_drafting_change_l14d_pct: float | None
    xr_drafting_change_l30d_pct: float | None
    ct_head_change_l7d_pct: float | None
    ct_head_change_l14d_pct: float | None
    ct_head_change_l30d_pct: float | None
    us_capture_change_l7d_pct: float | None
    us_capture_change_l14d_pct: float | None
    us_capture_change_l30d_pct: float | None
    mosaic_mentor: str | None
    mosaic_mentor_status: str | None
    optimization_support_status: str | None
    optimization_support_notes: str | None
    utilization_plan_notes: str | None
    optimization_last_updated: str | None = None  # "last touched" proxy, not a stage-transition log - see 016_*.sql
    mentor_match: MentorMatchStatus | None = None


class EngagementCapacityPlan(BaseModel):
    """A dated, one-time staffing/timeline planning snapshot (see
    mvp_context.ENGAGEMENT_CAPACITY_PLAN for full provenance) - NOT a live forecast. Its own
    finish_by_date has already passed as of when this was extracted; shown in the UI purely as
    planning context, clearly labeled as such. projected_finish_date_if_unaided, unlike
    finish_by_date, was still genuinely near-term as of this extraction - worth surfacing on its
    own, not just as a stale historical figure."""

    source_date: str
    radiologists_on_list: int
    already_engaged_at_plan_time: int
    left_to_go_at_plan_time: int
    realistic_target: int
    hours_per_radiologist_all_in: float
    total_hours_of_work: int
    cols_today: int
    people_needed_at_full_col_hours: int
    people_to_add: int
    trainers_to_borrow_at_16hrs_week: int
    throughput_per_week_current_team: float
    start_date: str
    finish_by_date: str
    engaged_by_finish_by_date: int
    projected_finish_date_if_unaided: str
    summary: str


class MvpProgramContext(BaseModel):
    """Static program narrative/glossary - see app/data/mvp_context.py for provenance. No EDW/
    cache dependency, same pattern as RadSurveySummary - also used as AI hover-context grounding."""

    program_narrative: str
    program_history: str
    priority_tier_definitions: dict[str, str]
    exclusion_reason_glossary: dict[str, str]
    engagement_process_steps: list[str]
    mentorship_program_summary: str
    current_status_notes: str
    ai_generated_narrative: str
    engagement_capacity_plan: EngagementCapacityPlan
    overview_narrative: str = ""
    mammo_narrative: str = ""


class CapacityRadiologistItem(BaseModel):
    npi: int
    radiologist_name: str | None
    team: str | None
    practice: str | None
    shift_names: str | None = None
    total_shifts: int
    total_hours: float | None
    capacity_rvu: float | None
    capacity_rpwu: float | None
    baseline_rvu: float | None
    baseline_rpwu: float | None
    utilization_rvu_pct: float | None
    utilization_rpwu_pct: float | None
    efficiency_rvu_per_min: float | None
    efficiency_rpwu_per_min: float | None
    capacity_rvu_per_hour: float | None
    baseline_rvu_per_hour: float | None
    on_shift_cases: float | None
    mosaic_cases: float | None
    drafting_cases: float | None
    pct_mosaic: float | None
    pct_drafting: float | None
    avg_rvu_per_case: float | None
    ct_cases: float | None
    xr_cases: float | None
    us_cases: float | None
    mr_cases: float | None
    ir_cases: float | None
    adjustment_rvu: float | None
    adjustment_tbwu: float | None
    pct_exams_with_valid_read_time: float | None = None
    pct_shifts_rpce_source: float | None = None


class MosaicIntelligenceSnapshot(BaseModel):
    practice: str | None = None
    rads_live_on_mosaic: int
    rads_live_on_ai_drafting: int
    pct_rpce_reporting: float | None
    pct_rpce_drafting: float | None
    rads_live_on_capture: int
    rads_capture_enabled: int
    practices_fully_on_rpce: int
    practices_split_integration: int
    practices_not_on_rpce: int


class RpceTrendPoint(BaseModel):
    period: str
    practice: str | None = None
    pct_rpce_reporting: float | None
    pct_rpce_drafting: float | None
    mosaic_exam_ct: int
    drafting_exam_ct: int


class CaptureOverview(BaseModel):
    capturable_exams_all: int
    captured_exams_all: int
    pct_captured_all: float | None
    capturable_exams_enabled: int
    captured_exams_enabled: int
    pct_captured_enabled: float | None
    rads_live_on_capture: int
    rads_capture_enabled: int
    capture_mosaic_tbwu_per_min: float | None
    capture_baseline_tbwu_per_min: float | None
    capture_pct_change_vs_baseline: float | None


class CapturePracticeRollup(BaseModel):
    practice: str | None
    capturable_exams_all: int
    captured_exams_all: int
    pct_captured_all: float | None
    capturable_exams_enabled: int
    captured_exams_enabled: int
    pct_captured_enabled: float | None
    rads_live_on_capture: int
    rads_capture_enabled: int
    enablement_date: date | None
    pct_change_since_enablement: float | None
    opted_out: bool = False


class CaptureRadiologistItem(BaseModel):
    npi: int
    radiologist_name: str | None
    practice: str | None
    capture_enabled: bool | None
    capturable_exams: int
    captured_exams: int
    pct_captured: float | None


class CaptureUtilizationTrendPracticePoint(BaseModel):
    period: str
    granularity: str
    practice: str | None
    capturable_exams_all: int
    captured_exams_all: int
    pct_captured_all: float | None
    capturable_exams_enabled: int
    captured_exams_enabled: int
    pct_captured_enabled: float | None
    pct_change_all: float | None
    pct_change_enabled: float | None


class CaptureUtilizationTrendRadiologistPoint(BaseModel):
    period: str
    granularity: str
    npi: int
    radiologist_name: str | None
    practice: str | None
    capture_enabled: bool | None
    capturable_exams: int
    captured_exams: int
    pct_captured: float | None
    pct_change: float | None


class CaptureEfficiencyTrendPracticePoint(BaseModel):
    period: str
    granularity: str
    practice: str | None
    capture_tbwu_per_min: float | None
    capture_baseline_tbwu_per_min: float | None
    pct_change: float | None


class CaptureEfficiencyTrendRadiologistPoint(BaseModel):
    period: str
    granularity: str
    npi: int
    radiologist_name: str | None
    practice: str | None
    capture_tbwu_per_min: float | None
    capture_baseline_tbwu_per_min: float | None
    pct_change: float | None


class RadSummaryStat(BaseModel):
    npi: int
    radiologist_name: str | None
    home_practice: str | None
    mosaic_go_live_date: date | None
    total_mosaic_exams: int
    pct_mosaic: float | None
    pct_mammo: float | None
    total_xr_drafted: int
    pct_xr_drafted: float | None
    ct_head_drafted: int
    pct_ct_head_drafted: float | None
    ct_abdpel_drafted: int
    pct_ct_abdpel_drafted: float | None
    ct_chest_drafted: int
    pct_ct_chest_drafted: float | None
    captured_us: int
    pct_captured: float | None
    drafting_groups: list[str]


class UndraftedCategoryPoint(BaseModel):
    week_start: date
    local_practice: str | None
    team: str | None
    category: str
    category_sort_order: int
    exam_count: int
    tbwu: float


class UndraftedFilterOptions(BaseModel):
    exam_categories: list[str]
    sites: list[str]


class LikertDistribution(BaseModel):
    label: str
    distribution: dict[str, int]  # "1".."5" -> respondent count
    mean: float
    top2box_pct: float | None = None  # agreement statements only
    na_count: int | None = None  # feature satisfaction only (option 6 = N/A)


class ThemeStat(BaseModel):
    theme: str
    pct: float


class PracticeNpsStat(BaseModel):
    practice: str
    n: int
    nps: float
    mean: float


class RadSurveySummary(BaseModel):
    sent: int
    responses: int
    response_rate: float
    median_completion_minutes: float
    nps: float
    nps_distribution: dict[str, int]  # "0".."10" -> respondent count
    promoters: int
    passives: int
    detractors: int
    agreement_statements: list[LikertDistribution]
    feature_satisfaction: list[LikertDistribution]
    problem_frequency: list[LikertDistribution]
    top_frustration_themes: list[ThemeStat]
    top_praised_themes: list[ThemeStat]
    by_practice: list[PracticeNpsStat]


class DraftInsightOverview(BaseModel):
    """Aggregate stats over the AI-assessed draft-vs-final sample (see
    tools/draft_insights/001_build_draft_insights_sample.sql - a bounded, stratified recent
    sample, not the full drafted population)."""

    n: int
    avg_retention_pct: float | None
    overall_assessment_distribution: dict[str, int]  # "Highly Useful" -> count, etc.


class DraftInsightModalityStat(BaseModel):
    modality: str | None
    n: int
    avg_retention_pct: float | None


class DraftInsightPracticeStat(BaseModel):
    practice: str | None
    n: int
    avg_retention_pct: float | None


class DraftInsightCategoryStat(BaseModel):
    category: str
    count: int
    pct: float


class DraftInsightCategoryGroup(BaseModel):
    dimension: str  # "added_by_radiologist" | "removed_from_draft" | "formatting" | "clinical_interpretation" | "additional_findings"
    categories: list[DraftInsightCategoryStat]


class DraftInsightSampleItem(BaseModel):
    accession_number: str
    overall_assessment: str | None
    retention_pct: int | None
    added_by_radiologist: str | None
    removed_from_draft: str | None


class CapacityPracticeRollup(BaseModel):
    practice: str | None
    total_shifts: int
    total_hours: float | None
    capacity_rvu: float | None
    capacity_rpwu: float | None
    baseline_rvu: float | None
    baseline_rpwu: float | None
    utilization_rvu_pct: float | None
    utilization_rpwu_pct: float | None
    efficiency_rvu_per_min: float | None
    efficiency_rpwu_per_min: float | None
    capacity_rvu_per_hour: float | None
    baseline_rvu_per_hour: float | None
    on_shift_cases: float | None
    mosaic_cases: float | None
    drafting_cases: float | None
    pct_mosaic: float | None
    pct_drafting: float | None
    avg_rvu_per_case: float | None
    ct_cases: float | None
    xr_cases: float | None
    us_cases: float | None
    mr_cases: float | None
    ir_cases: float | None
    adjustment_rvu: float | None
    adjustment_tbwu: float | None
    pct_exams_with_valid_read_time: float | None = None
    pct_shifts_rpce_source: float | None = None


class CapacityBaselineScorecard(BaseModel):
    """Practice-level Capacity = TBWU/hour scheduled, per RP's Mosaic Impact Report
    methodology. Baseline Capacity comes from edw_dev.bipa_analytics.stg_mosaic_baseline_master
    (the pre-computed per-shift-type baseline table), attached via a two-tier join (exact
    NPI+Task_ID, falling back to NPI+normalized Shift_Name) that recovers the majority of
    shifts the live view's exact-only join misses. pct_exact/pct_proxy/pct_manual_review/
    pct_no_baseline show what fraction of a practice's shifts actually got a real baseline
    vs. a proxy/manual-review/nothing at all - low coverage means additional_capacity_pct
    is not trustworthy for that practice (it's nulled out below a materiality floor rather
    than shown as a distorted number)."""

    practice: str | None
    total_shifts: int
    total_hours: float | None
    baseline_capacity_tbwu_per_hour: float | None
    avg_capacity_tbwu_per_hour: float | None
    capacity_change_tbwu_per_hour: float | None
    additional_capacity_pct: float | None
    pct_exact: float | None
    pct_proxy: float | None
    pct_manual_review: float | None
    pct_no_baseline: float | None


class BaselineProxyDetail(BaseModel):
    """One row per (NPI, target shift) that lacked its own baseline history and got a
    borrowed one - the chosen match (rank=1), from the live 8-component similarity scoring in
    mosaic_service._CAPACITY_PROXY_CTE_SQL. Matching is same-radiologist-only: a shift-type a
    rad didn't do enough of pre-Mosaic is matched against that same NPI's own other
    baseline-period shift-types (subspecialty/interventional/modality/TBWU/duration/location/
    weekday-weekend/time-of-day/work-type), picking the best total_match_score."""

    npi: int
    radiologist_name: str | None
    practice: str | None
    target_shift: str
    proxy_shift: str
    total_match_score: float | None
    score_subspecialty: float | None
    score_interventional: float | None
    score_modality: float | None
    score_tbwu: float | None
    score_shift_duration: float | None
    score_location: float | None
    score_weekday_weekend: float | None
    score_time_of_day: float | None
    score_work_type: float | None
    baseline_type: str | None


class BaselineProxyCandidate(BaseModel):
    """Every candidate shift-type considered for a (NPI, target shift) pair, not just the
    rank=1 winner BaselineProxyDetail shows - same scoring, top 5 by total_match_score. Powers
    the Baseline Review Queue, where a reviewer can see and pick among the alternatives the
    algorithm didn't choose."""

    npi: int
    radiologist_name: str | None
    practice: str | None
    target_shift: str
    rank: int
    proxy_shift: str
    total_match_score: float | None
    score_subspecialty: float | None
    score_interventional: float | None
    score_modality: float | None
    score_tbwu: float | None
    score_shift_duration: float | None
    score_location: float | None
    score_weekday_weekend: float | None
    score_time_of_day: float | None
    score_work_type: float | None
    # The implied TBWU/hour rate this candidate's shift-type carries - exposed specifically so
    # baseline_overrides.py can recompute a shift's capacity rate when a reviewer picks a
    # non-rank-1 candidate, without a second EDW round-trip.
    baseline_tbwu_per_hour: float | None


class ShiftUtilizationItem(BaseModel):
    """One row per (radiologist, shift date) - how much of the shift was reading time, and how
    much of that reading was Mosaic-assisted or AI-drafted. Source:
    edw_dev.bipa_analytics.presentation_deneb_vw (RP's own Deneb/shift-timeline source) joined to
    tbl_exam_inventory's mosaic_read_flag/mosaic_draft_flag via accession number."""

    npi: int
    radiologist_name: str | None
    practice: str | None
    shift_date: date
    utilization_pct: float | None  # fraction 0-1, reading_minutes/shift_total_minutes
    pct_mosaic_read: float | None  # fraction 0-1 of that shift's exams read on Mosaic
    pct_ai_drafted: float | None  # fraction 0-1 of that shift's exams AI-drafted
    reading_minutes: float | None
    shift_total_minutes: float | None


class GenieAskRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class GenieAskResponse(BaseModel):
    conversation_id: str
    message_id: str


class GenieResultTable(BaseModel):
    columns: list[str]
    rows: list[list]


class GenieMessageResponse(BaseModel):
    status: str
    text: str | None
    sql: str | None
    error: str | None
    suggested_questions: list[str]


# ===========================================================================================
# MVP Weekly Update dashboard rebuild (see declarative-dancing-willow.md plan, "MVP module
# rebuild: reproduce the real Weekly Update report"). Status funnel / impact breakdown /
# escalations-by-owner / weekly trend are all derived client-side from the existing
# /mvp/radiologists payload (mirrors the computePriorities() pattern already in Mvp.tsx) - these
# models exist only for the two pieces that genuinely need a new backend computation: the
# Mammo-screening volume+efficiency combo chart, and the precomputed AI narrative per dashboard.

class MammoScreeningTrendPoint(BaseModel):
    period: str
    screening_volume: int
    screening_efficiency_change_pct: float | None


class MvpDashboardNarrative(BaseModel):
    """Precomputed (refresh-cycle) AI narrative for one MVP dashboard scope - mirrors
    MvpProgramContext.ai_generated_narrative's exact pattern (never generated live on page
    load, static fallback on failure)."""

    scope: str  # "overview" | "mammo"
    narrative: str
    result: GenieResultTable | None
