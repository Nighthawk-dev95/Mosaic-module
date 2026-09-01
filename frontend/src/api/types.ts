export interface MosaicIntelligenceSnapshot {
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
  pct_rpce_reporting: number | null;
  pct_rpce_drafting: number | null;
  mosaic_exam_ct: number;
  drafting_exam_ct: number;
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

export interface DeploymentRadiologistItem {
  npi: number;
  radiologist_name: string | null;
  home_practice: string | null;
  working_subspecialty: string | null;
  xr_ct_head_status: string | null;
  ct_abdpel_status: string | null;
  ct_chest_status: string | null;
  ct_head_drafts_last_14d: number;
  xr_drafts_last_14d: number;
  ct_abdpel_drafts_last_14d: number;
  ct_chest_drafts_last_14d: number | null;
}

export interface DeploymentPracticeRollup {
  practice: string | null;
  total_rads: number;
  xr_ct_head_enabled_rads: number;
  ct_abdpel_enabled_rads: number;
  ct_chest_enabled_rads: number | null;
  ct_head_cases_last_14d: number;
  xr_cases_last_14d: number;
  ct_abdpel_cases_last_14d: number;
  ct_chest_cases_last_14d: number | null;
}

export interface DeploymentFunnelStage {
  stage: string;
  rank: number;
  count: number;
}

export interface DeploymentFunnel {
  domain: string;
  stages: DeploymentFunnelStage[];
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
  exam_category: string | null;
  reporting_tbwu_per_min: number | null;
  drafting_tbwu_per_min: number | null;
  full_mosaic_tbwu_per_min: number | null;
  reporting_pct_change: number | null;
  drafting_pct_change: number | null;
  full_mosaic_pct_change: number | null;
  reporting_rad_count: number;
  drafting_rad_count: number;
  reporting_exam_count: number;
  drafting_exam_count: number;
}

export interface EfficiencyTrendRpAvgPoint {
  period: string;
  drafting_tbwu_per_min: number | null;
  full_mosaic_tbwu_per_min: number | null;
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
