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

/** One row of the mix-vs-rate waterfall.
 *
 * The two nullable rates mean different things and the UI must not collapse them: on a folded
 * "All other" row neither side has a meaningful blended rate, while on an imputed row the peers
 * simply never touched that bucket. `imputed_peer_rate` tells them apart. */
export interface MoversBucket {
  bucket: string;
  target_share: number;
  peer_share: number | null;
  target_rate: number | null;
  peer_rate: number | null;
  mix: number;
  rate: number;
  total: number;
  imputed_peer_rate: boolean;
  is_tail: boolean;
}

/** Shift-share split of an efficiency gap into case-mix and within-bucket rate.
 *
 * Carries a refusal shape: when `available` is false every numeric field is null and `reason`
 * says why. Branch on `available` - a waterfall of zeros reads as "no difference found", which
 * is a different and wrong claim. */
export interface MoversDecomposition {
  comparison: string;
  available: boolean;
  reason: string | null;
  group_col: string | null;
  group_value: string | null;
  mode: string | null;
  bucket_label: string | null;
  target_rate: number | null;
  comparison_rate: number | null;
  gap: number | null;
  mix_effect: number | null;
  rate_effect: number | null;
  /** True only vs baseline, where both rates cover the same exams so the weights cancel.
   * Say so rather than drawing a bar that is permanently empty. */
  mix_is_structurally_zero: boolean;
  buckets: MoversBucket[];
  methodology: string;
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
// compute_escalations_by_owner currently return. This is the *persisted* half of what
// GET /mvp/weekly-report and /mvp/weekly-report/history return - the Postgres columns. Those
// routes also attach the scope-neutral `sections`/`deltas`/`scope_label`/`has_previous` fields
// (see BriefingSnapshot below), which this interface deliberately omits: a caller typed to
// WeeklyReportSnapshot is one that knows what the three blocks mean and reads them by name.
// MvpWeeklyReport.tsx is that caller, and still derives its own deltas client-side
// (utils/mvpDashboardStats.ts's diffCounts) from two adjacent entries in the fetched history.
export interface WeeklyReportSnapshot {
  scope: MvpBriefingScope;
  week_ending: string;
  funnel: Record<string, { on_track: number; escalated: number; declined: number }>;
  impact: Record<string, number>;
  escalations: Record<string, number>;
  key_insights: string;
  focus_next_week: string;
  generated_at: string;
}

// Every scope `backend/app/services/mvp_weekly_report_service._SCOPES` declares. Kept in sync by
// test_briefing_scopes.test_the_typescript_scope_union_matches_the_registry, which reads this
// line - adding a scope on the backend and not here fails that test rather than 422-ing in a
// browser. The MVP pages' two cohorts are a strict subset, below.
export type BriefingScope = "overview" | "mammo" | "drafting";

// The subset whose *persisted* shape is the MVP one above: `funnel` nested one level into
// on_track/escalated/declined. This is deliberately narrower than BriefingScope rather than the
// same type. Every scope writes to the same three Postgres columns, but what those columns hold
// is the scope's own business - the Drafting scope's `funnel` is a flat Record<string, number>
// of TBWU. Typing WeeklyReportSnapshot.scope as BriefingScope would tell MvpWeeklyReport.tsx
// that `funnel[stage].on_track` is a number for a snapshot where it is `undefined`, and the page
// renders NaN rather than failing.
export type MvpBriefingScope = "overview" | "mammo";

// The scope-neutral view of the same three blocks, returned by all three briefing routes. Any
// scope can be rendered from this without the renderer knowing what the blocks mean: `label` is
// what a reader sees, `values` is flat or one level nested, `deltas` has the same keys as
// `values` with null where there is no prior snapshot to compare against.
//
// `label` and `description` are not stored - they come from the scope declaration in
// mvp_weekly_report_service._SCOPES at read time. That is why a renderer must not cache a
// section's label against its slot: editing a scope's wording changes what every past week is
// called, which is correct, because the slot is the identity and the label is just the caption.
export interface BriefingSection {
  slot: "funnel" | "impact" | "escalations";
  label: string;
  description: string;
  values: Record<string, number | Record<string, number>>;
  deltas: Record<string, number | null | Record<string, number | null>>;
}

export interface BriefingSnapshot {
  scope: BriefingScope;
  scope_label: string;
  week_ending: string;
  sections: BriefingSection[];
  key_insights: string;
  focus_next_week: string;
  has_previous: boolean;
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

/**
 * One (week, practice, region, leakage-category) cell of the Non-Drafted chart.
 *
 * `local_practice` is the *managing* site - where the exam was read - which is what the page's
 * "Practice" filter has always claimed to mean. `local_region` is one of the six fixed Local
 * buckets, already resolved server-side from the reading radiologist's home practice; do not
 * run it through `getLocalRegion` again (that maps a practice name, not a region name, and
 * would silently collapse every region to "Matrix").
 */
export interface UndraftedCategoryPoint {
  week_start: string;
  local_practice: string | null;
  local_region: string | null;
  category: string;
  category_sort_order: number;
  exam_count: number;
  tbwu: number;
}

/**
 * One row of the Drafting worklist. Re-grouped from the same cached leakage rows that feed
 * `UndraftedCategoryPoint` - no new dataset, no new query.
 *
 * `team` is the radiologist's home practice (`provider_local_practice_name_curr`), not the
 * site the exam was read at. The leakage rows are grouped on the provider column, so a row
 * here names a group of radiologists, not a location.
 *
 * `expected_unlock_tbwu` is the ranking key and the only number on this row that is a claim
 * rather than a measurement: (peer benchmark draft rate - this team's rate) x its addressable
 * draftable TBWU. Render it beside `gap_to_benchmark_pct`, because a team 4 points off the
 * benchmark on a huge book outranking one 60 points off on a small one is correct and looks
 * wrong until both numbers are visible at once.
 */
export interface NextBestAction {
  team: string;
  action: string;
  primary_blocker: string;
  rationale: string;
  expected_unlock_tbwu: number;
  gap_to_benchmark_pct: number;
  draft_rate: number;
  addressable_tbwu: number;
  drafted_tbwu: number;
  not_enrolled_tbwu: number;
  workflow_gap_tbwu: number;
  /** Share of this team's draftable gap sitting behind `primary_blocker`. */
  blocker_share_of_gap: number;
  gap_exams: number;
  // Excluded from the rate - not convertible by whoever works this list - but carried so it
  // can be escalated to the owner who can act on it.
  deployment_blocked_tbwu: number;
  procedure_not_covered_tbwu: number;
  not_on_mosaic_tbwu: number;
}

export interface NextBestActionList {
  actions: NextBestAction[];
  benchmark_draft_rate: number;
  benchmark_pctile: number;
  benchmark_team_count: number;
  excluded_low_volume_teams: number;
  undated_rows_skipped: number;
  min_addressable_tbwu: number;
  window_start: string;
  window_end: string;
  weeks: number;
  total_expected_unlock_tbwu: number;
  /** Prose built from the numbers above. Render verbatim - do not paraphrase in the UI. */
  basis: string;
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
  // target_shift stays non-null because the service drops rows without one - it is the half
  // of the (npi, target_shift) decision key. proxy_shift can legitimately be absent: that is a
  // row the scorer found no acceptable match for, which is a reviewable state, not a bad row.
  target_shift: string;
  proxy_shift: string | null;
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

/**
 * `GET /api/mosaic/registry` - the governed metric registry, mirrored from
 * backend/app/semantics/registry.py's `snapshot()`.
 *
 * This is the one import that lets TSX stop hardcoding methodology prose. Before it, the same
 * read-time coverage methodology was written out four times: as the threshold that actually
 * suppresses a value (`mosaic_service._MIN_READ_TIME_COVERAGE`), as AI prompt grounding
 * (`ai_context_service`), as a ~60-word string literal in `utils/coverage.tsx`, and as an EDW
 * column comment - with nothing keeping the four equal.
 *
 * Fetched once per browser session and held, so `version` is how a cached copy knows it went
 * stale. The payload is deliberately open at the edges on the backend (Waves 2-3 add whole
 * sections), so every field here is read defensively rather than assumed present.
 */
export interface RegistryDimensionRef {
  key: string;
  label: string;
  /** Team = the rad's home practice; Practice = the site where the exam was performed. */
  note: string;
}

export interface RegistryMetric {
  key: string;
  label: string;
  /**
   * The column this metric arrives in on an API payload, which is not always its `key`.
   *
   * Two domains ship a column called `pct_mosaic` over different denominators - Volume's divides
   * by all exams, Capacity's by on-shift cases only (~25% fewer). Resolving a response field back
   * to a definition by key alone would silently hand you the wrong one, so the key is globally
   * unique and this is the deployed name. Match on `column` within a known domain, never across.
   */
  column: string;
  domain: string;
  solutions: string[];
  definition: string;
  caveats: string[];
  grain: string;
  is_rate: boolean;
  trust: string;
  source: string;
  owner: string;
  version: string;
  /**
   * "" when ungated; otherwise the `RegistryCoverage.key` whose threshold suppresses this value.
   * Set means a null here is a *policy* decision - the data was insufficient and the number was
   * withheld - not a missing field. A surface can say "withheld below 75% coverage" instead of
   * rendering a bare "—" that reads as an outage.
   */
  gated_by: string;
  /** Empty for shift-grain Capacity metrics, whose entity columns are not the cube's dimensions. */
  allowed_dims: RegistryDimensionRef[];
}

/**
 * One solution of the product: Reporting, AI Drafting, Capture, or all Mosaic.
 *
 * This is the axis that makes Mosaic a cube rather than a metric list - crossed with the metrics
 * above, it answers "how is Drafting doing" as a first-class question instead of a filter someone
 * remembers to apply. `full_mosaic` is Reporting + Drafting and deliberately excludes Capture,
 * mirroring the upstream ETL's `Is_Mosaic_Row` so the app and the warehouse agree on the word.
 */
export interface RegistryMode {
  key: string;
  label: string;
  description: string;
}

export interface RegistryDimension {
  key: string;
  label: string;
  note: string;
  required_filter: string | null;
  /** Metric keys that may be grouped by this dimension. */
  metrics: string[];
}

export interface RegistryCoverage {
  key: string;
  label: string;
  min_ratio: number;
  /** Pre-formatted ("75%") so the percentage is never re-derived on this side. */
  min_pct_label: string;
  /**
   * Which side of the threshold is the bad side: `"min"` is a floor under an instrumentation
   * ratio (read-time coverage), `"max"` is a ceiling on the magnitude of the value itself (MVP's
   * efficiency-change plausibility test). The two are opposites, and until this field existed
   * this side could only render the first one.
   */
  direction: "min" | "max";
  /** The threshold with its comparator attached: "below 75%" / "above 100%". */
  threshold_label: string;
  /**
   * The whole rule, rendered server-side. Prefer this over composing a sentence from
   * `suppresses` / `shows_anyway` / `min_pct_label` - that is what this component used to do,
   * and the template it used hardcoded the direction, so a `max`-shaped spec described itself
   * exactly backwards. The lists below remain for callers that want to group by them.
   */
  sentence: string;
  measured_by: string;
  suppresses: string[];
  shows_anyway: string[];
  caveat: string;
  note: string;
}

export interface RegistryFeature {
  /** The `feature` string an `AIHoverCard` is keyed by. */
  feature: string;
  /** May be empty while a domain is still awaiting its registry fold-in; `coverage` then
   * carries the whole story. Both empty only when `unregistered_reason` is set. */
  metrics: RegistryMetric[];
  coverage: RegistryCoverage | null;
  grounding: string;
  /**
   * Why this feature will never have a governed definition - `""` for every feature that has
   * one, or is still waiting on its wave.
   *
   * The point of serving it: `useRegistryFeature` returns `null` for a feature the snapshot
   * does not carry, which is also what it returns for a typo in a `feature` prop. Four features
   * are deliberately undefined (a taxonomy, a survey, a workflow state, a free-text summary),
   * and before this field they were indistinguishable from the typo - the card rendered bare AI
   * text either way. A reason here lets the card say which.
   */
  unregistered_reason: string;
}

export interface RegistrySnapshot {
  version: string;
  generated_from: string;
  waves_folded_in: string[];
  /** The single declaration of the "no context available" string, shared with Python. */
  ai_fallback_text: string;
  metrics: RegistryMetric[];
  modes: RegistryMode[];
  dimensions: RegistryDimension[];
  coverage: RegistryCoverage[];
  features: RegistryFeature[];
}

/**
 * One term the resolver would not resolve, and what it offers instead.
 *
 * Returned as *data* on a 200, never as an error status. A question naming one good metric and
 * one unsupported breakdown is mostly answerable; a 4xx would throw away the part that worked.
 * Render these as a prompt to refine, not as a failure.
 *
 * `alternatives` holds registry keys, and is empty when the resolver genuinely has nothing to
 * offer - a metric available enterprise-wide only has no legal breakdown to suggest. Empty means
 * "no alternative exists", not "the suggester broke"; `reason` carries the explanation either way.
 */
export interface ScopeRefusal {
  term: string;
  reason: string;
  alternatives: string[];
}

/**
 * The resolved scope behind an answer - what the question was taken to mean.
 *
 * `notes` and `refusals` are different claims and must not be merged in the UI. A refusal means
 * something was dropped. A note means nothing was dropped but the answer carries a condition:
 * a coverage gate may withhold a value, or the Team/Practice distinction applies to the
 * breakdown that was used.
 */
export interface ResolvedScope {
  metrics: RegistryMetric[];
  solution: RegistryMode;
  group_by: RegistryDimension[];
  entity: string;
  period: string;
  refusals: ScopeRefusal[];
  notes: string[];
  is_answerable: boolean;
  registry_version: string;
}

export interface AskRequest {
  question: string;
  /** The surface's current filters. A default the question overrides, never the reverse.
   *  Also carries `entity_kind` ("practice" | "team" | "local_region") when the user has used
   *  the entity chip's switch - the same question re-asked against the other column. */
  page_scope?: Record<string, string>;
}

export interface AskResponse {
  question: string;
  /** "model" | "keywords" | "keywords (model unavailable)" - show it; a degraded answer should
   *  look degraded rather than quietly worse. */
  resolved_by: string;
  scope: ResolvedScope;
  entity_match: EntityMatch;
  /** The grounded question actually put to Genie. Empty when the scope is unanswerable, which
   *  is the point: with no resolved metrics there are no definitions to ground on. */
  genie_prompt: string;
  /** Set by an ambiguous metric or an unanswerable scope only - never by `entity_match.assumed`,
   *  which is a default the answer shows rather than a question it has to ask first. */
  needs_clarification: boolean;
  /** The governed Drafting ranking, attached only when the question asked *where to act* rather
   *  than what to measure.
   *
   *  Three states, and the difference between the last two is load-bearing:
   *    - `null` - the question carried no action intent. Not that kind of question.
   *    - `{ actions: [] }` - it did, and no team is behind the benchmark. That is good news and
   *      a real, reportable answer; rendering it as nothing makes it read as silence.
   *    - `{ actions: [...] }` - the ranking.
   *
   *  So branch on the object (`worklist && <Block …/>`), never on `worklist?.actions?.length`,
   *  which collapses the first two into one. Over the wire this is explicitly `null` rather
   *  than an absent key - `ask_service.ask()` omits it from its dict, and `AskResponse` then
   *  serializes the unset field as null. `tests/test_ask_worklist.py` pins both halves. */
  worklist?: AskWorklist | null;
}

/**
 * The action half of an answer - the ranking, alongside the scope and never instead of it.
 *
 * `actions` are the same rows the Next Best Action panel ranks, capped at five here because a
 * chat reply is read rather than scanned. `basis` is carried verbatim from the ranking and must
 * be rendered that way: it holds this run's live benchmark, team count and window, and a second
 * paraphrase of it is how the chat answer and the on-screen panel end up describing different
 * rankings to the same person.
 *
 * `scoped_to` is empty when the full enterprise ranking came back - either the question named no
 * entity, or it named a *Practice* (the site the exam was read at) while this list is grouped on
 * Team (the radiologist's home practice). Those are different columns, so the ranking is shown
 * unfiltered rather than filtered to nothing; say "across all teams" when this is empty.
 */
export interface AskWorklist {
  scoped_to: string;
  actions: NextBestAction[];
  basis: string;
  benchmark_draft_rate: number;
  window_start: string;
  window_end: string;
}

/**
 * Which column answers the entity the question named.
 *
 * The distinction the user has stated twice: `team` is `provider_local_practice_name_curr`, the
 * radiologist's *home* practice; `practice` is `managing_local_practice_name_curr`, the *site*
 * they read the exam at. One rad has one Team and up to seventy Practices, so the two give
 * genuinely different numbers for the same name.
 */
export interface EntityMatch {
  /** "practice" | "team" | "local_region" | "unknown", or "" when no entity was named. */
  kind: string;
  /** The vocabulary's own casing - "BOCA" asked about comes back as "Boca". */
  value: string;
  /** The other readings, present only when there is a real choice. */
  candidates: { kind: string; value: string }[];
  /** True when the name was in more than one list and `kind` is the default rather than a
   *  choice. Render it as a stated default with a switch, never as a blocker: practice and
   *  team names overlap almost entirely, so this fires on most real questions. */
  assumed: boolean;
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
  pct_exams_with_valid_read_time: number | null;
  // 0/1 flag at single-shift grain, not a share - 1 means this shift is RPCE-sourced.
  pct_shifts_rpce_source: number | null;
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

/* ------------------------------------------------------------------------- *
 * The cube - POST /api/mosaic/cube
 *
 * One scope in, one grid out. These mirror `CubeRequest` in backend/app/routes/cube.py and
 * `cube_service.query`'s return shape; the two are hand-synced, so a field added there needs
 * adding here. Note the verb: a GET to this path hits the SPA catch-all and returns index.html
 * with HTTP 200, which looks exactly like success until you parse it.
 * ------------------------------------------------------------------------- */

export interface CubeRequest {
  /** Registry metric keys. At least one. An unknown key is a 404, not an empty grid. */
  metrics: string[];
  /** Registry dimension keys: practice | team | local_region | month. */
  group_by?: string[];
  /**
   * Names the entity grain directly, including grains that are not group-by dimensions -
   * `radiologist` rows exist in the cube but rolling a rate across the ~70 managing practices
   * one radiologist reads at has no governed definition, so it is reachable only this way.
   */
  entity_type?: string | null;
  entity_id?: string | null;
  /** 'YYYY-MM-DD'. The day is ignored; months are the grain. */
  period_from?: string | null;
  period_to?: string | null;
  limit?: number | null;
}

export interface CubeCell {
  measure: string;
  label: string;
  solution: string;
  is_rate: boolean;
  /**
   * Stored un-divided. `value` is num/den with the registry's offset applied exactly once, and
   * is null when the denominator is zero or absent - a rate of "no data" and a rate of "zero
   * percent" are different answers, and only one of them is safe to render as 0%.
   */
  num: number | null;
  den: number | null;
  value: number | null;
  fact_rows?: number;
  /** Present only when the grid was grouped by month. */
  period_start?: string;
  /** Present only when the grid was grouped by, or filtered to, an entity. */
  entity_id?: string;
  entity_label?: string;
  /** Present only where the metric carries a coverage denominator. */
  coverage_pct?: number;
}

export interface CubeScopeEcho {
  metrics: string[];
  group_by: string[];
  entity_type: string;
  entity_id: string | null;
  period_from: string | null;
  period_to: string | null;
}

export interface CubeResponse {
  /** What the server actually answered, which may be narrower than what was asked. */
  scope: CubeScopeEcho;
  rows: CubeCell[];
  /** Keyed by metric key. Same shape the registry serves, so no definition is typed into TSX. */
  definitions: Record<string, RegistryMetric>;
  grain: string;
}

export interface CubeStatus {
  rows: number;
  measures: number;
  entity_types: number;
  first_period: string | null;
  last_period: string | null;
  measure_keys: string[];
  entity_type_keys: string[];
  wave_1_metrics: string[];
  lookback_months: number;
  registry_version: string;
}
