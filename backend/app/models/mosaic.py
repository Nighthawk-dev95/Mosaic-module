from datetime import date

from pydantic import BaseModel


class RadiologistRosterItem(BaseModel):
    npi: int
    radiologist_name: str | None
    home_practice: str | None
    working_subspecialty: str | None
    deployment_status: str | None
    deployment_launch_group: str | None
    current_team: str | None
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


class DeploymentRadiologistItem(BaseModel):
    npi: int
    radiologist_name: str | None
    home_practice: str | None
    working_subspecialty: str | None
    xr_ct_head_status: str | None
    ct_abdpel_status: str | None
    ct_chest_status: str | None = None
    ct_head_drafts_last_14d: int
    xr_drafts_last_14d: int
    ct_abdpel_drafts_last_14d: int
    ct_chest_drafts_last_14d: int | None = None


class DeploymentPracticeRollup(BaseModel):
    practice: str | None
    total_rads: int
    xr_ct_head_enabled_rads: int
    ct_abdpel_enabled_rads: int
    ct_chest_enabled_rads: int | None = None
    ct_head_cases_last_14d: int
    xr_cases_last_14d: int
    ct_abdpel_cases_last_14d: int
    ct_chest_cases_last_14d: int | None = None


class DeploymentFunnelStage(BaseModel):
    stage: str
    rank: int
    count: int


class DeploymentFunnel(BaseModel):
    domain: str
    stages: list[DeploymentFunnelStage]


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
    drafting_tbwu_per_min: float | None
    full_mosaic_tbwu_per_min: float | None
    reporting_pct_change: float | None
    drafting_pct_change: float | None
    full_mosaic_pct_change: float | None
    reporting_rad_count: int
    drafting_rad_count: int
    reporting_exam_count: int
    drafting_exam_count: int


class EfficiencyTrendRpAvgPoint(BaseModel):
    period: str
    drafting_tbwu_per_min: float | None
    full_mosaic_tbwu_per_min: float | None


class FocusRadiologistItem(BaseModel):
    """A radiologist flagged by the real Mosaic Value Project (MVP) methodology: a fixed
    baseline period (May-Jul 2026) vs. the most recent full month, gated by a minimum D&C
    exam-volume floor and tiered by baseline capacity x efficiency-loss severity. Does not
    model MVP's Dynamics-CRM-only exclusions ("Q3 go-live practice", "Do Not Revisit" flags) -
    those live in a manually-maintained CRM export, not EDW."""

    npi: int
    radiologist_name: str | None
    practice: str | None
    subspecialty: str | None
    priority_tier: str  # "Tier 1" | "Tier 2" | "Tier 3"
    baseline_capacity_per_shift: float | None
    dc_efficiency_change_pct: float | None
    capacity_change_pct: float | None
    ct_drafting_change_pct: float | None
    xr_drafting_change_pct: float | None
    us_capture_change_pct: float | None
    current_dc_exam_count: int


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


class ScorecardMetrics(BaseModel):
    top_n: str  # "5" | "10" | "15" | "20" | "25" | "30" | "all"
    shifts_worked: int
    case_count: int
    addl_capacity_per_shift: float | None
    efficiency: float | None
    shift_utilization: float | None
    avg_units_per_shift: float | None
    ct_cases: int
    xr_cases: int
    us_cases: int
    mr_cases: int
    nm_cases: int
    pt_cases: int
    mg_cases: int
    ir_cases: int
    other_modality_cases: int
    routine_cases: int
    stat_cases: int
    stroke_cases: int
    trauma_cases: int
    otherp_cases: int


class RadiologistScorecard(BaseModel):
    npi: int
    radiologist_name: str | None
    team: str | None
    practice: str | None
    mosaic_go_live_date: date | None
    metrics: list[ScorecardMetrics]


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


class ExternalFeedbackItem(BaseModel):
    """One record pushed through the speculative /api/mosaic/ingest/external_feedback_demo
    endpoint (routes/mosaic.py) - the real shape for that placeholder, now that it has one.
    Deliberately a sibling of RadSurveySummary above (same positive/neutral/negative framing
    the Rad Sentiment page already uses) rather than a new taxonomy - this is meant to read as
    a *live* counterpart to that static survey snapshot, not an unrelated concept."""

    practice: str | None = None
    radiologist_name: str | None = None
    sentiment: str  # "positive" | "neutral" | "negative"
    category: str | None = None
    comment: str | None = None
    submitted_at: str


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
