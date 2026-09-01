import type {
  BlockerByPractice,
  CapacityPracticeRollup,
  CapacityRadiologistItem,
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
  RadSummaryStat,
  RpceTrendPoint,
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
  getMosaicIntelligence: () => get<MosaicIntelligenceSnapshot>("/mosaic-intelligence"),
  getRpceTrend: () => get<RpceTrendPoint[]>("/rpce-trend"),
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
  getEfficiencyTrend: (examCategory?: string) =>
    get<EfficiencyTrendPoint[]>(`/efficiency/trend${examCategory ? `?exam_category=${encodeURIComponent(examCategory)}` : ""}`),
  getEfficiencyTrendRpAvg: () => get<EfficiencyTrendRpAvgPoint[]>("/efficiency/trend/rp-avg"),
  getCapacityByRadiologist: () => get<CapacityRadiologistItem[]>("/capacity/by-radiologist"),
  getCapacityByPractice: () => get<CapacityPracticeRollup[]>("/capacity/by-practice"),
  getRefreshStatus: () => get<RefreshStatus>("/refresh/status"),
  triggerRefresh: () => post<{ status: string }>("/refresh"),
};
