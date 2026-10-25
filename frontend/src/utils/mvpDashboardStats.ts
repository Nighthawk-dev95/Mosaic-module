import type { MvpRadiologistItem } from "../api/types";

// Mirrors backend/app/data/mvp_dashboard_stats.py exactly - kept in sync by hand (no shared
// code between the two runtimes; that module's own docstring explains the status-stage mapping
// in full, confirmed live 2026-10-20 against rad_onboarding's real
// mosaic_optimization_support_status vocabulary). This is the version the UI actually renders;
// the Python copy exists only to ground the precomputed AI narrative in matching numbers.

export type FunnelStage = "Outreached" | "Scheduled" | "Solutioning" | "Monitoring" | "Closed";
export const FUNNEL_STAGES: FunnelStage[] = ["Outreached", "Scheduled", "Solutioning", "Monitoring", "Closed"];

export interface FunnelBucket {
  on_track: number;
  escalated: number;
  declined: number;
}

const ESCALATION_OWNER_MAP: Record<string, string> = {
  Mentorship: "Mentorship",
  IT: "IT",
  "Program Specific": "Development",
};

function stageBucket(status: string | null | undefined): FunnelStage | null {
  if (!status) return null;
  if (status === "1 Identified" || status === "2 Confirmed") return null;
  if (status.startsWith("3 Outreached") || status.startsWith("4 Outreached")) return "Outreached";
  if (status.startsWith("5 Scheduled")) return "Scheduled";
  if (status.startsWith("6 Solutioning") || status.startsWith("7 Solutioning")) return "Solutioning";
  if (status.startsWith("8 Monitoring")) return "Monitoring";
  if (status.startsWith("9 Closed")) return "Closed";
  return null;
}

function isDeclinedOutcome(status: string): boolean {
  return ["Declined Support", "Resigning", "Mentor Declined", "Not Progressing"].some((kw) => status.includes(kw));
}

export function getEffLossPrograms(r: MvpRadiologistItem): string {
  const programs: string[] = [];
  if (r.xr_drafting_efficiency_change_pct != null && r.xr_drafting_efficiency_change_pct < 0) programs.push("XR");
  if (r.ct_head_efficiency_change_pct != null && r.ct_head_efficiency_change_pct < 0) programs.push("CT");
  if (r.us_capture_efficiency_change_pct != null && r.us_capture_efficiency_change_pct < 0) programs.push("US");
  if (programs.length === 0 && r.drafting_captured_efficiency_change_pct != null && r.drafting_captured_efficiency_change_pct < 0) {
    programs.push("D&C");
  }
  return programs.join(", ") || "—";
}

export function getOutreachEscalationRows(rows: MvpRadiologistItem[]): MvpRadiologistItem[] {
  return rows.filter((r) => {
    const stage = stageBucket(r.optimization_support_status);
    const status = r.optimization_support_status ?? "";
    return (stage === "Outreached" || stage === "Solutioning") && status.includes("Escalated");
  });
}

export function getRadsDecliningSupportRows(rows: MvpRadiologistItem[]): MvpRadiologistItem[] {
  return rows.filter((r) => {
    const stage = stageBucket(r.optimization_support_status);
    return stage === "Closed" && isDeclinedOutcome(r.optimization_support_status ?? "");
  });
}

// Overview/Mammo scope split - mirrors backend/app/data/mvp_dashboard_stats.py's scope_rows
// exactly (same "no shared code between runtimes" convention as everything else in this file).
// Previously duplicated inline as MvpOverview.tsx's isDraftingCaptureCohort and an equivalent in
// MvpMammo.tsx; both now call this one definition instead.
export function scopeRows(rows: MvpRadiologistItem[], scope: "overview" | "mammo"): MvpRadiologistItem[] {
  if (scope === "mammo") {
    return rows.filter((r) => r.mvp_cohort && r.mvp_cohort.includes("(Mammo)"));
  }
  return rows.filter((r) => r.mvp_cohort && !r.mvp_cohort.includes("(Mammo)") && !r.mvp_cohort.includes("(Ops or Self Referred)"));
}

// Click-to-drill-down helpers (MVP interactivity pass) - each mirrors the exact classification
// logic its corresponding compute*() function already uses, returning the matching rows instead
// of counts, so a chart/tile click and its own displayed number are always provably consistent.

export function getFunnelBucketRows(
  rows: MvpRadiologistItem[],
  stage: FunnelStage,
  bucket: "on_track" | "escalated" | "declined"
): MvpRadiologistItem[] {
  return rows.filter((r) => {
    const status = r.optimization_support_status;
    if (stageBucket(status) !== stage || !status) return false;
    if (stage === "Closed") {
      return bucket === "declined" ? isDeclinedOutcome(status) : bucket === "on_track" ? !isDeclinedOutcome(status) : false;
    }
    const escalated = status.includes("Escalated");
    return bucket === "escalated" ? escalated : bucket === "on_track" ? !escalated : false;
  });
}

export function getEscalationOwnerRows(rows: MvpRadiologistItem[], owner: string): MvpRadiologistItem[] {
  return rows.filter((r) => {
    const status = r.optimization_support_status ?? "";
    if (!status.startsWith("7 Solutioning (Escalated - ")) return false;
    const suffix = status.replace("7 Solutioning (Escalated - ", "").replace(/\)$/, "");
    return ESCALATION_OWNER_MAP[suffix] === owner;
  });
}

// Mirrors backend/app/data/mvp_dashboard_stats.py's _IMPLAUSIBLE_PCT_MAGNITUDE exactly - confirmed
// live (2026-10-22) that drafting_captured_efficiency_change_pct/full_mosaic_change_l30d_pct
// range as high as +916%/+1724% on 7-11 of 643 rows (tiny-denominator blowups, not real
// efficiency gains). Unfiltered, a single +1724% artifact gets classified "At/Above Baseline" -
// treated as insufficient_data instead, same as a missing value, in every function below.
const IMPLAUSIBLE_PCT_MAGNITUDE = 100;

function isImplausible(value: number | null | undefined): boolean {
  return value != null && Math.abs(value) > IMPLAUSIBLE_PCT_MAGNITUDE;
}

export type ImpactBucketKey = "at_above_baseline" | "improving" | "not_improving" | "insufficient_data";

export function getImpactBucketRows(rows: MvpRadiologistItem[], bucket: ImpactBucketKey): MvpRadiologistItem[] {
  return rows.filter((r) => {
    const stage = stageBucket(r.optimization_support_status);
    if (stage !== "Solutioning" && stage !== "Monitoring" && stage !== "Closed") return false;
    const bl = r.drafting_captured_efficiency_change_pct;
    const post = r.full_mosaic_change_l30d_pct;
    if (bl == null || post == null || isImplausible(bl) || isImplausible(post)) return bucket === "insufficient_data";
    if (post >= 0) return bucket === "at_above_baseline";
    if (post > bl) return bucket === "improving";
    return bucket === "not_improving";
  });
}

export function computeStatusFunnel(rows: MvpRadiologistItem[]): Record<FunnelStage, FunnelBucket> {
  const funnel: Record<FunnelStage, FunnelBucket> = {
    Outreached: { on_track: 0, escalated: 0, declined: 0 },
    Scheduled: { on_track: 0, escalated: 0, declined: 0 },
    Solutioning: { on_track: 0, escalated: 0, declined: 0 },
    Monitoring: { on_track: 0, escalated: 0, declined: 0 },
    Closed: { on_track: 0, escalated: 0, declined: 0 },
  };
  for (const r of rows) {
    const status = r.optimization_support_status;
    const stage = stageBucket(status);
    if (!stage || !status) continue;
    if (stage === "Closed") {
      funnel[stage][isDeclinedOutcome(status) ? "declined" : "on_track"] += 1;
    } else if (status.includes("Escalated")) {
      funnel[stage].escalated += 1;
    } else {
      funnel[stage].on_track += 1;
    }
  }
  return funnel;
}

export function computeEscalationsByOwner(rows: MvpRadiologistItem[]): Record<string, number> {
  const counts: Record<string, number> = { Development: 0, IT: 0, Mentorship: 0 };
  for (const r of rows) {
    const status = r.optimization_support_status ?? "";
    if (!status.startsWith("7 Solutioning (Escalated - ")) continue;
    const suffix = status.replace("7 Solutioning (Escalated - ", "").replace(/\)$/, "");
    const owner = ESCALATION_OWNER_MAP[suffix];
    if (owner) counts[owner] += 1;
  }
  return counts;
}

export type ImpactStatus = "At/Above Baseline" | "Improving Towards Baseline" | "Not Improving" | null;

export function getImpactStatus(r: MvpRadiologistItem): ImpactStatus {
  const stage = stageBucket(r.optimization_support_status);
  if (stage !== "Solutioning" && stage !== "Monitoring" && stage !== "Closed") return null;
  const bl = r.drafting_captured_efficiency_change_pct;
  // efficiency_change_last_30d_pct is confirmed live (2026-10-21) to be 100% NULL across the
  // entire post-engagement population - full_mosaic_change_l30d_pct is the rolling figure
  // that's actually populated and serves the same "how is this radiologist doing right now" role.
  const post = r.full_mosaic_change_l30d_pct;
  if (bl == null || post == null || isImplausible(bl) || isImplausible(post)) return null;
  if (post >= 0) return "At/Above Baseline";
  if (post > bl) return "Improving Towards Baseline";
  return "Not Improving";
}

export interface ImpactBreakdown {
  post_engagement_rads: number;
  at_above_baseline: number;
  improving: number;
  not_improving: number;
  insufficient_data: number;
}

export function computeImpactBreakdown(rows: MvpRadiologistItem[]): ImpactBreakdown {
  const counts: ImpactBreakdown = {
    post_engagement_rads: 0,
    at_above_baseline: 0,
    improving: 0,
    not_improving: 0,
    insufficient_data: 0,
  };
  for (const r of rows) {
    const stage = stageBucket(r.optimization_support_status);
    if (stage !== "Solutioning" && stage !== "Monitoring" && stage !== "Closed") continue;
    counts.post_engagement_rads += 1;
    const bl = r.drafting_captured_efficiency_change_pct;
    const post = r.full_mosaic_change_l30d_pct;
    if (bl == null || post == null || isImplausible(bl) || isImplausible(post)) counts.insufficient_data += 1;
    else if (post >= 0) counts.at_above_baseline += 1;
    else if (post > bl) counts.improving += 1;
    else counts.not_improving += 1;
  }
  return counts;
}

// Mirrors backend/app/data/mvp_dashboard_stats.py's diff_counts exactly. Used by
// MvpWeeklyReport.tsx to compute week-over-week deltas client-side from two history-endpoint
// snapshots - the history endpoint only ever returns persisted columns (funnel/impact/
// escalations/narrative), never a precomputed "deltas" field (that only exists transiently in
// the POST /generate response, grounding its AI narrative), so the page can't assume any
// snapshot object carries its own deltas and must derive them from its neighbor in the list.
export function diffCounts<T extends Record<string, any>>(current: T, previous: T | null): T {
  const result: Record<string, any> = {};
  for (const [key, value] of Object.entries(current)) {
    const prevValue = previous ? previous[key] : null;
    if (value && typeof value === "object") {
      result[key] = diffCounts(value, prevValue ?? null);
    } else {
      result[key] = prevValue !== null && prevValue !== undefined ? (value as number) - (prevValue as number) : null;
    }
  }
  return result as T;
}

export interface WeeklyEngagementPoint {
  week: string;
  not_yet_outreached: number;
  engaged: number;
}

// Approximated from optimization_last_updated ("last touched", not a true stage-transition log -
// see 016_add_optimization_last_updated_to_mvp_rad_onboarding.sql for full provenance). Must
// always be captioned as an approximation wherever it's rendered.
export function computeWeeklyEngagementTrend(rows: MvpRadiologistItem[], weeks = 6): WeeklyEngagementPoint[] {
  const byWeek = new Map<string, { engaged: number; not_yet: number }>();
  for (const r of rows) {
    if (!r.optimization_last_updated) continue;
    const parsed = new Date(r.optimization_last_updated);
    if (isNaN(parsed.getTime())) continue;
    // Monday-start week bucket, as a stable sortable key.
    const day = parsed.getDay();
    const diff = (day === 0 ? -6 : 1) - day;
    const monday = new Date(parsed);
    monday.setDate(parsed.getDate() + diff);
    monday.setHours(0, 0, 0, 0);
    const key = monday.toISOString().slice(0, 10);
    const entry = byWeek.get(key) ?? { engaged: 0, not_yet: 0 };
    const stage = stageBucket(r.optimization_support_status);
    if (stage) entry.engaged += 1;
    else entry.not_yet += 1;
    byWeek.set(key, entry);
  }
  return Array.from(byWeek.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-weeks)
    .map(([week, v]) => ({ week, not_yet_outreached: v.not_yet, engaged: v.engaged }));
}
