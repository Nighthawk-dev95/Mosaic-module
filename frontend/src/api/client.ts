import type {
  BaselineProxyCandidate,
  BaselineProxyDetail,
  BaselineReviewDecision,
  ReviewActivityItem,
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
  DraftInsightModalityStat,
  DraftInsightOverview,
  DraftInsightPracticeStat,
  DraftInsightSampleItem,
  EfficiencyDetail,
  Note,
  RadiologistLookupDetail,
  RadiologistLookupMatch,
  EfficiencyFilterOptions,
  EfficiencyMode,
  EfficiencyTrendPoint,
  MammoScreeningTrendPoint,
  EfficiencyTrendRpAvgPoint,
  MvpRadiologistItem,
  MvpProgramContext,
  AiContextRequest,
  AiContextResponse,
  RegistrySnapshot,
  MosaicIntelligenceSnapshot,
  MoversDecomposition,
  PopulationEfficiency,
  RadiologistRosterItem,
  RadSummaryStat,
  RadSurveySummary,
  RpceTrendPoint,
  ShiftUtilizationItem,
  UndraftedCategoryPoint,
  NextBestActionList,
  UndraftedFilterOptions,
  UtilizationPracticeRollup,
  VolumeFilterOptions,
  VolumeGroupRollup,
  VolumeSummary,
  VolumeTrendPoint,
  AskRequest,
  AskResponse,
  GenieAskRequest,
  GenieAskResponse,
  GenieMessageResponse,
  WeeklyReportSnapshot,
  BriefingScope,
  BriefingSnapshot,
  MvpBriefingScope,
  MvpMethodologyCheck,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/mosaic";

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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface RefreshStatus {
  refreshed_at: Record<string, string>;
  errors: Record<string, string>;
  in_progress: boolean;
  total_datasets: number;
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
  getVolumeSummary: () => get<VolumeSummary>("/volume/summary"),
  getVolumeByPractice: () => get<VolumeGroupRollup[]>("/volume/by-practice"),
  getVolumeByTeam: () => get<VolumeGroupRollup[]>("/volume/by-team"),
  getVolumeByLocalRegion: () => get<VolumeGroupRollup[]>("/volume/by-local-region"),
  getVolumeTrend: () => get<VolumeTrendPoint[]>("/volume/trend"),
  getVolumeFilters: () => get<VolumeFilterOptions>("/volume/filters"),
  getShiftUtilizationByRadiologist: (practice?: string) =>
    get<ShiftUtilizationItem[]>(`/shift-utilization${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getDeploymentBlockersDrafting: () => get<BlockerByPractice[]>("/blockers/drafting"),
  getDeploymentBlockersCtAbdpel: () => get<BlockerByPractice[]>("/blockers/ct-abdpel"),
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
  getEfficiencyMovers: (params: {
    group_col: string;
    group_value: string;
    decompose_by?: string;
    mode?: EfficiencyMode;
    comparison?: "peers" | "baseline";
  }) => {
    const search = new URLSearchParams();
    search.set("group_col", params.group_col);
    search.set("group_value", params.group_value);
    search.set("decompose_by", params.decompose_by ?? "exam_category");
    search.set("mode", params.mode ?? "full_mosaic");
    search.set("comparison", params.comparison ?? "peers");
    return get<MoversDecomposition>(`/efficiency/movers?${search.toString()}`);
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
  getMvpRadiologists: () => get<MvpRadiologistItem[]>("/mvp/radiologists"),
  getMvpContext: () => get<MvpProgramContext>("/mvp/context"),
  getMvpAreaDetail: () => get<Record<string, EfficiencyTrendPoint[]>>("/mvp/area-detail"),
  getMammoScreeningTrend: () => get<MammoScreeningTrendPoint[]>("/mvp/mammo-screening-trend"),
  getMvpMammoScreeningTrend: () => get<MammoScreeningTrendPoint[]>("/mvp/mammo-screening-trend/mvp-only"),
  // These three take MvpBriefingScope, not BriefingScope: they are typed to the MVP-shaped
  // `WeeklyReportSnapshot`, and a non-MVP scope returns the same keys holding a different shape.
  // Use generateBriefing below for any scope.
  generateMvpWeeklyReport: (scope: MvpBriefingScope) =>
    post<WeeklyReportSnapshot>(`/mvp/weekly-report/generate?scope=${scope}`),
  getMvpWeeklyReport: (scope: MvpBriefingScope) =>
    get<WeeklyReportSnapshot>(`/mvp/weekly-report?scope=${scope}`),
  getMvpWeeklyReportHistory: (scope: MvpBriefingScope, limit = 12) =>
    get<WeeklyReportSnapshot[]>(`/mvp/weekly-report/history?scope=${scope}&limit=${limit}`),
  // The same three endpoints, read through their scope-neutral `sections` view. Every response
  // carries both views; which one you ask for is a choice about whether the caller knows what a
  // scope's three blocks mean. Anything that renders a scope it was not written for - the
  // Drafting briefing on /non-drafted - reads `sections` and stays correct when a fourth scope
  // appears, because the labels arrive with the data instead of being typed into the component.
  generateBriefing: (scope: BriefingScope) =>
    post<BriefingSnapshot>(`/mvp/weekly-report/generate?scope=${scope}`),
  getBriefing: (scope: BriefingScope) =>
    get<BriefingSnapshot>(`/mvp/weekly-report?scope=${scope}`),
  getBriefingHistory: (scope: BriefingScope, limit = 12) =>
    get<BriefingSnapshot[]>(`/mvp/weekly-report/history?scope=${scope}&limit=${limit}`),
  // Cohort-definition check against the published MVP methodology. Stays MvpBriefingScope on
  // purpose - there is no cohort string to check for an enterprise scope, and the backend route
  // rejects one rather than answering a question it never asked.
  getMvpMethodologyCheck: (scope: MvpBriefingScope) =>
    get<MvpMethodologyCheck>(`/mvp/methodology-check?scope=${scope}`),
  getAiContext: (req: AiContextRequest) => postJson<AiContextResponse>("/ai-context", req),
  // Static, in-memory on the backend (frozen dataclasses, no EDW, no cache) - safe to call
  // eagerly. AIHoverCard fetches it once per browser session and holds it.
  getRegistry: () => get<RegistrySnapshot>("/registry"),
  getRadSentiment: () => get<RadSurveySummary>("/survey/rad-sentiment"),
  searchRadiologistLookup: (q: string) => get<RadiologistLookupMatch[]>(`/radiologist-lookup/search?q=${encodeURIComponent(q)}`),
  getRadiologistLookup: (npi: number, q?: string) =>
    get<RadiologistLookupDetail>(`/radiologist-lookup/${npi}${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getNotes: (entityType: "radiologist" | "practice", entityKey: string) =>
    get<Note[]>(`/notes?entity_type=${entityType}&entity_key=${encodeURIComponent(entityKey)}`),
  postNote: (entityType: "radiologist" | "practice", entityKey: string, noteText: string) =>
    postJson<{ status: string }>("/notes", { entity_type: entityType, entity_key: entityKey, note_text: noteText }),
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
  getUndraftedAnalysis: (params: { practice?: string; exam_category?: string; site?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.practice) search.set("practice", params.practice);
    if (params.exam_category) search.set("exam_category", params.exam_category);
    if (params.site) search.set("site", params.site);
    const qs = search.toString();
    return get<UndraftedCategoryPoint[]>(`/undrafted-analysis${qs ? `?${qs}` : ""}`);
  },
  getUndraftedAnalysisFilters: () => get<UndraftedFilterOptions>("/undrafted-analysis/filters"),
  /**
   * The Drafting worklist. Every parameter is a lever on the *benchmark*, not on the data:
   * `benchmark_pctile` is how ambitious "achievable" is, `min_addressable_tbwu` is how small a
   * book may still set the frontier. Left unset, the backend's defaults apply (8 weeks, p75,
   * 500 TBWU) - pass them only from a control the user can see, never silently.
   */
  getNextBestActions: (
    params: { weeks?: number; min_addressable_tbwu?: number; benchmark_pctile?: number; limit?: number } = {},
  ) => {
    const search = new URLSearchParams();
    if (params.weeks !== undefined) search.set("weeks", String(params.weeks));
    if (params.min_addressable_tbwu !== undefined)
      search.set("min_addressable_tbwu", String(params.min_addressable_tbwu));
    if (params.benchmark_pctile !== undefined) search.set("benchmark_pctile", String(params.benchmark_pctile));
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    const qs = search.toString();
    return get<NextBestActionList>(`/next-best-actions${qs ? `?${qs}` : ""}`);
  },
  getDraftInsightOverview: () => get<DraftInsightOverview>("/draft-insights/overview"),
  getDraftInsightByModality: () => get<DraftInsightModalityStat[]>("/draft-insights/by-modality"),
  getDraftInsightByPractice: () => get<DraftInsightPracticeStat[]>("/draft-insights/by-practice"),
  getDraftInsightCategories: () => get<DraftInsightCategoryGroup[]>("/draft-insights/categories"),
  getDraftInsightSamples: (params: { overall_assessment?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.overall_assessment) search.set("overall_assessment", params.overall_assessment);
    if (params.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return get<DraftInsightSampleItem[]>(`/draft-insights/samples${qs ? `?${qs}` : ""}`);
  },
  getCapacityBaselineScorecard: () => get<CapacityBaselineScorecard[]>("/capacity/baseline-scorecard"),
  getBaselineProxyDetail: (practice?: string) =>
    get<BaselineProxyDetail[]>(`/capacity/baseline-proxy-detail${practice ? `?practice=${encodeURIComponent(practice)}` : ""}`),
  getBaselineProxyCandidates: (npi: number, targetShift: string) =>
    get<BaselineProxyCandidate[]>(
      `/capacity/baseline-proxy-candidates?npi=${npi}&target_shift=${encodeURIComponent(targetShift)}`
    ),
  getBaselineReviewDecisions: () => get<BaselineReviewDecision[]>("/capacity/baseline-review-decisions"),
  postBaselineReviewDecision: (decision: {
    npi: number;
    target_shift: string;
    status: string;
    chosen_proxy_shift?: string | null;
    chosen_rank?: number | null;
    note?: string | null;
  }) => postJson<{ saved: boolean }>("/capacity/baseline-review-decisions", decision),
  getReviewActivity: (limit = 20) => get<ReviewActivityItem[]>(`/capacity/review-activity?limit=${limit}`),
  // Resolves a question to a governed scope; it does not answer it. The companion to askGenie,
  // not a replacement - run this first and hand `genie_prompt` to askGenie, so Genie answers
  // with the registry's definitions attached instead of inventing its own denominator.
  ask: (req: AskRequest) => postJson<AskResponse>("/ask", req),
  askGenie: (req: GenieAskRequest) => postJson<GenieAskResponse>("/genie/ask", req),
  getGenieMessage: (conversationId: string, messageId: string) =>
    get<GenieMessageResponse>(`/genie/message?conversation_id=${conversationId}&message_id=${messageId}`),
  getRefreshStatus: () => get<RefreshStatus>("/refresh/status"),
  triggerRefresh: () => post<{ status: string }>("/refresh"),
};
