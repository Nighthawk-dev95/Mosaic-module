import type {
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
  EfficiencyMode,
  EfficiencyTrendPoint,
  EfficiencyTrendRpAvgPoint,
  MosaicIntelligenceSnapshot,
  PopulationEfficiency,
  RadiologistRosterItem,
  RadiologistScorecard,
  RadSummaryStat,
  RpceTrendPoint,
  UndraftedCategoryPoint,
  UndraftedFilterOptions,
  UtilizationPracticeRollup,
} from "./types";

const BASE_URL = "http://127.0.0.1:8000/api/mosaic";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`Request to ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface RefreshStatus {
  refreshed_at: Record<string, string>;
  errors: Record<string, string>;
  in_progress: boolean;
}

export const mosaicApi = {
  getMosaicIntelligence: (practice?: string) =>
    get<MosaicIntelligenceSnapshot>(`/mosaic-intelligence${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getRpceTrend: (practice?: string) =>
    get<RpceTrendPoint[]>(`/rpce-trend${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getRadSummaryStats: (params: { practice?: string; drafting_group?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.practice) search.set("practice", params.practice);
    if (params.drafting_group) search.set("drafting_group", params.drafting_group);
    const qs = search.toString();
    return get<RadSummaryStat[]>(`/rad-summary-stats${qs ? `?${qs}` : ""}`);
  },
  getRoster: (params: { practice?: string; subspecialty?: string; deployment_status?: string; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.practice) search.set("practice", params.practice);
    if (params.subspecialty) search.set("subspecialty", params.subspecialty);
    if (params.deployment_status) search.set("deployment_status", params.deployment_status);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const qs = search.toString();
    return get<RadiologistRosterItem[]>(`/roster${qs ? `?${qs}` : ""}`);
  },
  getUtilizationByPractice: (daysBack = 30) =>
    get<UtilizationPracticeRollup[]>(`/utilization/by-practice?days_back=${daysBack}`),
  getDeploymentByRadiologist: () => get<DeploymentRadiologistItem[]>("/deployment/by-radiologist"),
  getDeploymentByPractice: () => get<DeploymentPracticeRollup[]>("/deployment/by-practice"),
  getDeploymentFunnelReporting: () => get<DeploymentFunnel>("/deployment/funnel/reporting"),
  getDeploymentFunnelDrafting: () => get<DeploymentFunnel>("/deployment/funnel/drafting"),
  getDeploymentBlockersDrafting: () => get<BlockerByPractice[]>("/deployment/blockers/drafting"),
  getDeploymentFunnelCtAbdpel: () => get<DeploymentFunnel>("/deployment/funnel/ct-abdpel"),
  getDeploymentBlockersCtAbdpel: () => get<BlockerByPractice[]>("/deployment/blockers/ct-abdpel"),
  getEfficiencyDetail: (mode: EfficiencyMode = "full_mosaic") => get<EfficiencyDetail>(`/efficiency?mode=${mode}`),
  getEfficiencyPopulation: (params: {
    mode?: EfficiencyMode;
    practice?: string;
    subspecialty?: string;
    modality_code?: string;
    parent_procedure_name?: string;
    exam_category?: string;
  } = {}) => {
    const search = new URLSearchParams();
    search.set("mode", params.mode ?? "full_mosaic");
    if (params.practice) search.set("practice", params.practice);
    if (params.subspecialty) search.set("subspecialty", params.subspecialty);
    if (params.modality_code) search.set("modality_code", params.modality_code);
    if (params.parent_procedure_name) search.set("parent_procedure_name", params.parent_procedure_name);
    if (params.exam_category) search.set("exam_category", params.exam_category);
    return get<PopulationEfficiency>(`/efficiency/population?${search.toString()}`);
  },
  getEfficiencyFilters: () => get<EfficiencyFilterOptions>("/efficiency/filters"),
  getEfficiencyTrend: (examCategory?: string, practice?: string) => {
    const search = new URLSearchParams();
    if (examCategory) search.set("exam_category", examCategory);
    if (practice) search.set("practice", practice);
    const qs = search.toString();
    return get<EfficiencyTrendPoint[]>(`/efficiency/trend${qs ? `?${qs}` : ""}`);
  },
  getEfficiencyTrendRpAvg: () => get<EfficiencyTrendRpAvgPoint[]>("/efficiency/trend/rp-avg"),
  getCaptureOverview: () => get<CaptureOverview>("/capture/overview"),
  getCaptureByPractice: (practice?: string) =>
    get<CapturePracticeRollup[]>(`/capture/by-practice${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getCaptureByRadiologist: (practice?: string) =>
    get<CaptureRadiologistItem[]>(`/capture/by-radiologist${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getCaptureTrendUtilizationByPractice: (granularity: "week" | "month", practice?: string) => {
    const search = new URLSearchParams({ granularity });
    if (practice) search.set("practice", practice);
    return get<CaptureUtilizationTrendPracticePoint[]>(`/capture/trend/utilization/by-practice?${search.toString()}`);
  },
  getCaptureTrendUtilizationByRadiologist: (granularity: "week" | "month", practice?: string) => {
    const search = new URLSearchParams({ granularity });
    if (practice) search.set("practice", practice);
    return get<CaptureUtilizationTrendRadiologistPoint[]>(`/capture/trend/utilization/by-radiologist?${search.toString()}`);
  },
  getCaptureTrendEfficiencyByPractice: (granularity: "week" | "month", practice?: string) => {
    const search = new URLSearchParams({ granularity });
    if (practice) search.set("practice", practice);
    return get<CaptureEfficiencyTrendPracticePoint[]>(`/capture/trend/efficiency/by-practice?${search.toString()}`);
  },
  getCaptureTrendEfficiencyByRadiologist: (granularity: "week" | "month", practice?: string) => {
    const search = new URLSearchParams({ granularity });
    if (practice) search.set("practice", practice);
    return get<CaptureEfficiencyTrendRadiologistPoint[]>(`/capture/trend/efficiency/by-radiologist?${search.toString()}`);
  },
  getCapacityByRadiologist: () => get<CapacityRadiologistItem[]>("/capacity/by-radiologist"),
  getCapacityByPractice: () => get<CapacityPracticeRollup[]>("/capacity/by-practice"),
  getRadiologistScorecard: (practice?: string) =>
    get<RadiologistScorecard[]>(`/radiologist-scorecard${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getUndraftedAnalysis: (params: { practice?: string; exam_category?: string; site?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.practice) search.set("practice", params.practice);
    if (params.exam_category) search.set("exam_category", params.exam_category);
    if (params.site) search.set("site", params.site);
    const qs = search.toString();
    return get<UndraftedCategoryPoint[]>(`/undrafted-analysis${qs ? `?${qs}` : ""}`);
  },
  getUndraftedAnalysisFilters: () => get<UndraftedFilterOptions>("/undrafted-analysis/filters"),
  getRefreshStatus: () => get<RefreshStatus>("/refresh/status"),
  triggerRefresh: () => post<{ status: string }>("/refresh"),
};
