export interface MosaicIntelligenceSnapshot {
  practice: string | null;
  rads_live_on_mosaic: number;
  rads_live_on_ai_drafting: number;
  pct_rpce_reporting: number | null;
  pct_rpce_drafting: number | null;
  rads_live_on_capture: number;
  rads_capture_enabled: number;
  practices_fully_on_rpce: number;
  practices_split_integration: number;
  practices_not_on_rpce: number;
}

export interface RpceTrendPoint {
  period: string;
  practice: string | null;
  pct_rpce_reporting: number | null;
  pct_rpce_drafting: number | null;
  mosaic_exam_ct: number;
  drafting_exam_ct: number;
}

export interface CaptureOverview {
  capturable_exams_all: number;
  captured_exams_all: number;
  pct_captured_all: number | null;
  capturable_exams_enabled: number;
  captured_exams_enabled: number;
  pct_captured_enabled: number | null;
  rads_live_on_capture: number;
  rads_capture_enabled: number;
  capture_mosaic_tbwu_per_min: number | null;
  capture_baseline_tbwu_per_min: number | null;
  capture_pct_change_vs_baseline: number | null;
}

export interface CapturePracticeRollup {
  practice: string | null;
  capturable_exams_all: number;
  captured_exams_all: number;
  pct_captured_all: number | null;
  capturable_exams_enabled: number;
  captured_exams_enabled: number;
  pct_captured_enabled: number | null;
  rads_live_on_capture: number;
  rads_capture_enabled: number;
  enablement_date: string | null;
  pct_change_since_enablement: number | null;
  opted_out: boolean;
}

export interface CaptureRadiologistItem {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  capture_enabled: boolean | null;
  capturable_exams: number;
  captured_exams: number;
  pct_captured: number | null;
}

export interface CaptureUtilizationTrendPracticePoint {
  period: string;
  granularity: string;
  practice: string | null;
  capturable_exams_all: number;
  captured_exams_all: number;
  pct_captured_all: number | null;
  capturable_exams_enabled: number;
  captured_exams_enabled: number;
  pct_captured_enabled: number | null;
  pct_change_all: number | null;
  pct_change_enabled: number | null;
}

export interface CaptureUtilizationTrendRadiologistPoint {
  period: string;
  granularity: string;
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  capture_enabled: boolean | null;
  capturable_exams: number;
  captured_exams: number;
  pct_captured: number | null;
  pct_change: number | null;
}

export interface CaptureEfficiencyTrendPracticePoint {
  period: string;
  granularity: string;
  practice: string | null;
  capture_tbwu_per_min: number | null;
  capture_baseline_tbwu_per_min: number | null;
  pct_change: number | null;
}

export interface CaptureEfficiencyTrendRadiologistPoint {
  period: string;
  granularity: string;
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  capture_tbwu_per_min: number | null;
  capture_baseline_tbwu_per_min: number | null;
  pct_change: number | null;
}

export interface LikertDistribution {
  label: string;
  distribution: Record<string, number>;
  mean: number;
  top2box_pct: number | null;
  na_count: number | null;
}

export interface ThemeStat {
  theme: string;
  pct: number;
}

export interface PracticeNpsStat {
  practice: string;
  n: number;
  nps: number;
  mean: number;
}

export interface RadSurveySummary {
  sent: number;
  responses: number;
  response_rate: number;
  median_completion_minutes: number;
  nps: number;
  nps_distribution: Record<string, number>;
  promoters: number;
  passives: number;
  detractors: number;
  agreement_statements: LikertDistribution[];
  feature_satisfaction: LikertDistribution[];
  problem_frequency: LikertDistribution[];
  top_frustration_themes: ThemeStat[];
  top_praised_themes: ThemeStat[];
  by_practice: PracticeNpsStat[];
}

export interface Note {
  entity_type: "radiologist" | "practice";
  entity_key: string;
  note_text: string;
  created_at: string;
}

export interface RadiologistLookupMatch {
  npi: number;
  radiologist_name: string | null;
  home_practice: string | null;
}

export interface RadiologistLookupEfficiencyRow {
  exam_category: string | null;
  reporting_tbwu: number | null;
  reporting_time: number | null;
  drafting_tbwu: number | null;
  drafting_time: number | null;
  capture_tbwu: number | null;
  capture_time: number | null;
  full_mosaic_tbwu_per_min: number | null;
}

export interface RadiologistLookupDetail {
  npi: number;
  roster: Record<string, unknown> | null;
  capacity: Record<string, unknown> | null;
  scorecard: Record<string, unknown> | null;
  efficiency_by_category: RadiologistLookupEfficiencyRow[];
}

export interface RadSummaryStat {
  npi: number;
  radiologist_name: string | null;
  home_practice: string | null;
  mosaic_go_live_date: string | null;
  total_mosaic_exams: number;
  pct_mosaic: number | null;
  pct_mammo: number | null;
  total_xr_drafted: number;
  pct_xr_drafted: number | null;
  ct_head_drafted: number;
  pct_ct_head_drafted: number | null;
  ct_abdpel_drafted: number;
  pct_ct_abdpel_drafted: number | null;
  ct_chest_drafted: number;
  pct_ct_chest_drafted: number | null;
  captured_us: number;
  pct_captured: number | null;
  drafting_groups: string[];
}

export interface RadiologistRosterItem {
  npi: number;
  radiologist_name: string | null;
  home_practice: string | null;
  primary_site: string | null;
  site_count: number | null;
  working_subspecialty: string | null;
  deployment_status: string | null;
  deployment_launch_group: string | null;
  current_team: string | null;
  reporting_cases_read: number | null;
  total_drafting_cases: number | null;
  total_mosaic_exams: number | null;
  capture_enabled: boolean | null;
}

export interface UtilizationPracticeRollup {
  practice: string | null;
  total_exams: number | null;
  mosaic_exams: number | null;
  pct_mosaic: number | null;
  drafting_exams: number | null;
  pct_drafting: number | null;
  capture_exams: number | null;
  mammo_exams: number | null;
  mammo_mosaic_exams: number | null;
  pct_mammo_mosaic: number | null;
  rads_live: number | null;
  rads_drafting: number | null;
}

export interface VolumeSummary {
  total_exams: number;
  mosaic_exams: number;
  pct_mosaic: number | null;
  drafting_exams: number;
  pct_drafting: number | null;
  pct_rpce_reporting: number | null;
  pct_rpce_drafting: number | null;
}

export interface VolumeGroupRollup {
  group: string | null;
  total_exams: number;
  mosaic_exams: number;
  pct_mosaic: number | null;
  drafting_exams: number;
  pct_drafting: number | null;
  pct_rpce_reporting: number | null;
  pct_rpce_drafting: number | null;
}

export interface VolumeTrendPoint {
  period: string;
  total_exams: number;
  mosaic_exams: number;
  pct_mosaic: number | null;
  drafting_exams: number;
  pct_drafting: number | null;
}

export interface VolumeFilterOptions {
  practices: string[];
  teams: string[];
  local_regions: string[];
}

export interface BlockerByPractice {
  practice: string | null;
  blocker: string;
  count: number;
}

export type EfficiencyMode = "full_mosaic" | "reporting" | "drafting" | "capture";

export interface EfficiencyRadiologistItem {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  subspecialty: string | null;
  mosaic_tbwu_per_min: number | null;
  baseline_tbwu_per_min: number | null;
  pct_change_vs_baseline: number | null;
  read_time_change_pct: number | null;
}

export interface EfficiencyPracticeRollup {
  practice: string | null;
  mosaic_tbwu_per_min: number | null;
  baseline_tbwu_per_min: number | null;
  pct_change_vs_baseline: number | null;
  read_time_change_pct: number | null;
}

export interface EfficiencyDetail {
  mode: EfficiencyMode;
  rp_benchmark_mosaic_tbwu_per_min: number | null;
  rp_benchmark_baseline_tbwu_per_min: number | null;
  by_radiologist: EfficiencyRadiologistItem[];
  by_practice: EfficiencyPracticeRollup[];
}

export interface PopulationEfficiency {
  mode: EfficiencyMode;
  practice: string | null;
  subspecialty: string | null;
  modality_code: string | null;
  parent_procedure_name: string | null;
  exam_category: string | null;
  mosaic_tbwu_per_min: number | null;
  baseline_tbwu_per_min: number | null;
  pct_change_vs_baseline: number | null;
  read_time_change_pct: number | null;
}

export interface EfficiencyFilterOptions {
  practices: string[];
  subspecialties: string[];
  modalities: string[];
  procedures: string[];
  exam_categories: string[];
}

export interface EfficiencyTrendPoint {
  period: string;
  practice: string | null;
  exam_category: string | null;
  reporting_tbwu_per_min: number | null;
  drafting_tbwu_per_min: number | null; // "Drafting + Capture" - Capture (US/BD) is a subset of Drafting
  full_mosaic_tbwu_per_min: number | null;
  drafting_only_tbwu_per_min: number | null; // Drafting excluding Capture-modality rows
  reporting_pct_change: number | null;
  drafting_pct_change: number | null;
  full_mosaic_pct_change: number | null;
  drafting_only_pct_change: number | null;
  reporting_rad_count: number;
  drafting_rad_count: number;
  reporting_exam_count: number;
  drafting_exam_count: number;
}

export interface MammoScreeningTrendPoint {
  period: string;
  screening_volume: number;
  screening_efficiency_change_pct: number | null;
}

export interface EfficiencyTrendRpAvgPoint {
  period: string;
  drafting_tbwu_per_min: number | null;
  full_mosaic_tbwu_per_min: number | null;
}

// Loosely typed (not exact nested shapes) - mirrors whatever
// backend/app/data/mvp_dashboard_stats.py's compute_status_funnel/compute_impact_breakdown/
// compute_escalations_by_owner currently return. This is the shape GET /mvp/weekly-report and
// /mvp/weekly-report/history actually return (the persisted Postgres columns only) - NOT the
// same shape as the POST /generate response, which additionally includes transient `deltas`/
// `has_previous` fields used only to ground that one request's AI narrative generation server-
// side. The frontend never reads deltas off a snapshot object - MvpWeeklyReport.tsx always
// derives them client-side (utils/mvpDashboardStats.ts's diffCounts) from two adjacent entries
// in the fetched history list, since that's the only data source this page actually uses.
export interface WeeklyReportSnapshot {
  scope: "overview" | "mammo";
  week_ending: string;
  funnel: Record<string, { on_track: number; escalated: number; declined: number }>;
  impact: Record<string, number>;
  escalations: Record<string, number>;
  key_insights: string;
  focus_next_week: string;
  generated_at: string;
}

// Loosely typed - mirrors backend/app/data/mvp_methodology_checks.py's compute_methodology_check
// return shape exactly (an internal/analytical payload, no response_model on its own route
// either, same precedent as /capacity/review-activity).
export interface MvpMethodologyCheck {
  outlier_summary: {
    per_field: Record<string, number>;
    total_radiologists_affected: number;
    total_radiologists: number;
  };
  outreach_week_reliability: {
    future_dated_count: number;
    already_past_outreached_count: number;
    contamination_rate: number | null;
  };
  baseline_severity_by_stage: Record<string, { median_baseline_pct: number | null; n: number }>;
}

export interface MentorMatchStatus {
  matching_status: string;
  mentors_identified: string | null;
  matching_notes: string | null;
  mentorship_meeting_date: string | null;
}

export interface MvpRadiologistItem {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  mvp_cohort: string | null;
  exclusion_reason: string | null;
  mvp_target_outreach_week: string | null;
  reads_500_plus_dx_cases: string | null;
  baseline_capacity_tbwu_9h: number | null;
  full_mosaic_efficiency_change_pct: number | null;
  xr_drafting_efficiency_change_pct: number | null;
  ct_head_efficiency_change_pct: number | null;
  us_capture_efficiency_change_pct: number | null;
  drafting_captured_efficiency_change_pct: number | null;
  efficiency_change_last_30d_pct: number | null;
  full_mosaic_change_l7d_pct: number | null;
  full_mosaic_change_l14d_pct: number | null;
  full_mosaic_change_l30d_pct: number | null;
  xr_drafting_change_l7d_pct: number | null;
  xr_drafting_change_l14d_pct: number | null;
  xr_drafting_change_l30d_pct: number | null;
  ct_head_change_l7d_pct: number | null;
  ct_head_change_l14d_pct: number | null;
  ct_head_change_l30d_pct: number | null;
  us_capture_change_l7d_pct: number | null;
  us_capture_change_l14d_pct: number | null;
  us_capture_change_l30d_pct: number | null;
  mosaic_mentor: string | null;
  mosaic_mentor_status: string | null;
  optimization_support_status: string | null;
  optimization_support_notes: string | null;
  utilization_plan_notes: string | null;
  optimization_last_updated: string | null;
  mentor_match: MentorMatchStatus | null;
}

export interface EngagementCapacityPlan {
  source_date: string;
  radiologists_on_list: number;
  already_engaged_at_plan_time: number;
  left_to_go_at_plan_time: number;
  realistic_target: number;
  hours_per_radiologist_all_in: number;
  total_hours_of_work: number;
  cols_today: number;
  people_needed_at_full_col_hours: number;
  people_to_add: number;
  trainers_to_borrow_at_16hrs_week: number;
  throughput_per_week_current_team: number;
  start_date: string;
  finish_by_date: string;
  engaged_by_finish_by_date: number;
  projected_finish_date_if_unaided: string;
  summary: string;
}

export interface MvpProgramContext {
  program_narrative: string;
  program_history: string;
  priority_tier_definitions: Record<string, string>;
  exclusion_reason_glossary: Record<string, string>;
  engagement_process_steps: string[];
  mentorship_program_summary: string;
  current_status_notes: string;
  ai_generated_narrative: string;
  engagement_capacity_plan: EngagementCapacityPlan;
  overview_narrative: string;
  mammo_narrative: string;
}

interface CapacityMeasures {
  total_shifts: number;
  total_hours: number | null;
  capacity_rvu: number | null;
  capacity_rpwu: number | null;
  baseline_rvu: number | null;
  baseline_rpwu: number | null;
  utilization_rvu_pct: number | null;
  utilization_rpwu_pct: number | null;
  efficiency_rvu_per_min: number | null;
  efficiency_rpwu_per_min: number | null;
  capacity_rvu_per_hour: number | null;
  baseline_rvu_per_hour: number | null;
  on_shift_cases: number | null;
  mosaic_cases: number | null;
  drafting_cases: number | null;
  pct_mosaic: number | null;
  pct_drafting: number | null;
  avg_rvu_per_case: number | null;
  ct_cases: number | null;
  xr_cases: number | null;
  us_cases: number | null;
  mr_cases: number | null;
  ir_cases: number | null;
  adjustment_rvu: number | null;
  adjustment_tbwu: number | null;
  pct_exams_with_valid_read_time: number | null;
  pct_shifts_rpce_source: number | null;
}

export interface CapacityRadiologistItem extends CapacityMeasures {
  npi: number;
  radiologist_name: string | null;
  team: string | null;
  practice: string | null;
  shift_names: string | null;
}

export interface CapacityPracticeRollup extends CapacityMeasures {
  practice: string | null;
}

// week_start is the Monday the week begins; category_sort_order 0 is "Drafted" - included
// so a % Undrafted total can be computed as 1 - (Drafted / week total), but never rendered
// as its own stacked segment (see UndraftedStackedChart).
export interface UndraftedFilterOptions {
  exam_categories: string[];
  sites: string[];
}

export interface UndraftedCategoryPoint {
  week_start: string;
  local_practice: string | null;
  team: string | null;
  category: string;
  category_sort_order: number;
  exam_count: number;
  tbwu: number;
}

// Draft vs Final: AI-assessed comparison of Mosaic draft findings against the radiologist's
// final signed report, over a bounded recent sample (see
// tools/draft_insights/001_build_draft_insights_sample.sql) - not the full drafted population.
export interface DraftInsightOverview {
  n: number;
  avg_retention_pct: number | null;
  overall_assessment_distribution: Record<string, number>;
}

export interface DraftInsightModalityStat {
  modality: string | null;
  n: number;
  avg_retention_pct: number | null;
}

export interface DraftInsightPracticeStat {
  practice: string | null;
  n: number;
  avg_retention_pct: number | null;
}

export interface DraftInsightCategoryStat {
  category: string;
  count: number;
  pct: number;
}

export interface DraftInsightCategoryGroup {
  dimension: string;
  categories: DraftInsightCategoryStat[];
}

export interface DraftInsightSampleItem {
  accession_number: string;
  overall_assessment: string | null;
  retention_pct: number | null;
  added_by_radiologist: string | null;
  removed_from_draft: string | null;
}

// Capacity = TBWU/hour scheduled, per RP's Mosaic Impact Report methodology. Baseline
// Capacity comes from a real pre-computed baseline table (edw_dev.bipa_analytics.
// stg_mosaic_baseline_master), not a simple proxy - pct_exact/pct_proxy/pct_manual_review/
// pct_no_baseline show how much of a practice's shift volume actually got a real baseline,
// since additional_capacity_pct is only meaningful when coverage is decent.
export interface CapacityBaselineScorecard {
  practice: string | null;
  total_shifts: number;
  total_hours: number | null;
  baseline_capacity_tbwu_per_hour: number | null;
  avg_capacity_tbwu_per_hour: number | null;
  capacity_change_tbwu_per_hour: number | null;
  additional_capacity_pct: number | null;
  pct_exact: number | null;
  pct_proxy: number | null;
  pct_manual_review: number | null;
  pct_no_baseline: number | null;
}

// One row per (NPI, target shift) that lacked its own baseline history and got a borrowed
// one from the best-scoring similar shift (stg_mosaic_proxy_all_candidates_2026, rank=1).
export interface BaselineProxyDetail {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  target_shift: string;
  proxy_shift: string;
  total_match_score: number | null;
  score_subspecialty: number | null;
  score_interventional: number | null;
  score_modality: number | null;
  score_tbwu: number | null;
  score_shift_duration: number | null;
  score_location: number | null;
  score_weekday_weekend: number | null;
  score_time_of_day: number | null;
  score_work_type: number | null;
  baseline_type: string | null;
}

export interface BaselineProxyCandidate extends BaselineProxyDetail {
  rank: number;
  baseline_tbwu_per_hour: number | null;
}

export type ReviewDecisionStatus = "accepted" | "overridden" | "rejected_no_match";

export interface BaselineReviewDecision {
  npi: number;
  target_shift: string;
  status: ReviewDecisionStatus;
  chosen_proxy_shift: string | null;
  chosen_rank: number | null;
  note: string | null;
  reviewed_at: string;
}

export interface ReviewActivityItem extends BaselineReviewDecision {
  radiologist_name: string | null;
  practice: string | null;
  capacity_impact_tbwu_per_hour: number | null;
}

export interface AiContextRequest {
  feature: string;
  entity_label: string;
  metric_label: string;
  value: string;
  extra?: Record<string, string>;
}

export interface AiContextResponse {
  explanation: string;
}

export interface ShiftUtilizationItem {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  shift_date: string;
  utilization_pct: number | null;
  pct_mosaic_read: number | null;
  pct_ai_drafted: number | null;
  reading_minutes: number | null;
  shift_total_minutes: number | null;
}

export interface GenieAskRequest {
  question: string;
  conversation_id?: string | null;
}

export interface GenieAskResponse {
  conversation_id: string;
  message_id: string;
}

export type GenieMessageStatus =
  | "SUBMITTED"
  | "FILTERING_CONTEXT"
  | "ASKING_AI"
  | "EXECUTING_QUERY"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface GenieResultTable {
  columns: string[];
  rows: (string | number | null)[][];
}

export interface GenieMessageResponse {
  status: GenieMessageStatus;
  text: string | null;
  sql: string | null;
  error: string | null;
  suggested_questions: string[];
  result: GenieResultTable | null;
}
