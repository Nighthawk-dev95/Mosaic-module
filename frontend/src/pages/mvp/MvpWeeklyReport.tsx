import { useMemo, useRef, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { StatTile } from "../../components/StatTile";
import { AIHoverCard } from "../../components/AIHoverCard";
import { StackedBarChart } from "../../components/StackedBarChart";
import { DonutChart } from "../../components/DonutChart";
import { RadiologistListDrawer } from "../../components/RadiologistListDrawer";
import { CARD_STYLE } from "../../styles/glassCard";
import { diffCounts, FUNNEL_STAGES, scopeRows, getImpactBucketRows, type ImpactBucketKey } from "../../utils/mvpDashboardStats";
import { downloadElementAsPdf } from "../../utils/exportPdf";
import type { MvpRadiologistItem, WeeklyReportSnapshot } from "../../api/types";

// The actual "reproduce this weekly" artifact (see declarative-dancing-willow.md's "MVP Weekly
// Report" plan) - a manual-trigger button computes + persists this week's Overview/Mammo
// snapshot (mosaic.mvp_weekly_snapshots via backend/app/services/mvp_weekly_report_service.py),
// diffs it against whatever was last generated, and renders both scopes as one printable report
// that can be exported client-side to a dated PDF - no scheduled job, no server-side PDF
// dependency, per the user's own scoping choices.

const STATUS_COLORS = {
  on_track: "var(--status-good)",
  escalated: "var(--status-warning)",
  declined: "var(--status-critical)",
};

const ESCALATION_OWNER_COLORS: Record<string, string> = {
  Development: "var(--domain-deployment)",
  IT: "var(--status-warning)",
  Mentorship: "var(--domain-capture)",
};

const IMPACT_LABELS: Record<string, string> = {
  post_engagement_rads: "Post-Engagement Rads",
  at_above_baseline: "At/Above Baseline",
  improving: "Improving Toward Baseline",
  not_improving: "Not Improving",
  insufficient_data: "Insufficient Data",
};

const IMPACT_ACCENTS: Record<string, string | undefined> = {
  post_engagement_rads: undefined,
  at_above_baseline: "var(--status-good)",
  improving: "var(--domain-deployment)",
  not_improving: "var(--status-critical)",
  insufficient_data: "var(--text-muted)",
};

function fmtDelta(n: number | null | undefined): string | undefined {
  if (n === null || n === undefined) return undefined;
  if (n === 0) return "No change vs last week";
  return `${n > 0 ? "+" : ""}${n} vs last week`;
}

function sectionHeader(label: string) {
  return (
    <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
      {label}
    </div>
  );
}

interface ScopeSectionProps {
  title: string;
  snapshot: WeeklyReportSnapshot;
  // The history endpoint does now return a `deltas` field, but this page deliberately ignores
  // it and derives its own from `previous`. The server's deltas are always against the
  // immediately preceding week; this page has a "Compare against" picker, so the baseline is
  // whichever week the user chose - a comparison the server's always-adjacent deltas cannot
  // express. `previous` is that chosen neighbor in the fetched history list, and null when
  // there's no older week to compare against.
  previous: WeeklyReportSnapshot | null;
  // Per-radiologist drill-down is only honest for the latest week - older snapshots persist
  // only aggregate counts, never which radiologists make them up (see plan's "one real
  // constraint" note). `isLatest` gates whether the Impact tiles are clickable at all.
  isLatest: boolean;
  onImpactClick: (bucket: ImpactBucketKey, label: string) => void;
}

function ScopeSection({ title, snapshot, previous, isLatest, onImpactClick }: ScopeSectionProps) {
  const funnelData = useMemo(
    () => FUNNEL_STAGES.map((stage) => ({ stage, ...snapshot.funnel[stage] })),
    [snapshot.funnel]
  );
  const escalationData = useMemo(
    () =>
      Object.entries(snapshot.escalations).map(([owner, value]) => ({
        key: owner,
        label: owner,
        value,
        color: ESCALATION_OWNER_COLORS[owner] ?? "var(--text-secondary)",
      })),
    [snapshot.escalations]
  );
  const impactDeltas = useMemo(
    () => diffCounts(snapshot.impact, previous?.impact ?? null),
    [snapshot.impact, previous]
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h3 style={{ margin: 0, fontSize: 15 }}>{title}</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20 }}>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mvp_status_funnel" entityLabel={title} metricLabel="MVP Rads by Status" value={snapshot.week_ending} underline={false}>
            {sectionHeader("MVP Rads by Status")}
          </AIHoverCard>
          <StackedBarChart
            data={funnelData}
            categoryKey="stage"
            series={[
              { key: "on_track", label: "On Track", color: STATUS_COLORS.on_track },
              { key: "escalated", label: "Escalated", color: STATUS_COLORS.escalated },
              { key: "declined", label: "Declined", color: STATUS_COLORS.declined },
            ]}
          />
        </div>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mvp_status_funnel" entityLabel={title} metricLabel="Solutioning Escalations by Owner" value={snapshot.week_ending} underline={false}>
            {sectionHeader("Solutioning Escalations by Owner")}
          </AIHoverCard>
          <DonutChart data={escalationData} />
        </div>
      </div>

      <div style={CARD_STYLE}>
        <AIHoverCard feature="mvp_impact" entityLabel={title} metricLabel="Impact on MVP Rads with Eff. Loss" value={String(snapshot.impact.post_engagement_rads ?? 0)} underline={false}>
          {sectionHeader(isLatest ? "Impact on MVP Rads with Eff. Loss (click a tile for the current radiologist list)" : "Impact on MVP Rads with Eff. Loss")}
        </AIHoverCard>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {Object.entries(IMPACT_LABELS).map(([key, label]) => (
            <StatTile
              key={key}
              label={label}
              value={String(snapshot.impact[key] ?? 0)}
              accent={IMPACT_ACCENTS[key]}
              sublabel={fmtDelta(impactDeltas[key])}
              disabled={key !== "post_engagement_rads" && !isLatest}
              onClick={key === "post_engagement_rads" ? undefined : () => onImpactClick(key as ImpactBucketKey, label)}
              title={
                key === "post_engagement_rads"
                  ? undefined
                  : isLatest
                  ? "Click for the current radiologist list"
                  : "Per-radiologist detail isn't available for past weeks - only aggregate counts are stored"
              }
            />
          ))}
        </div>
      </div>

      <div style={CARD_STYLE}>
        {sectionHeader("Key Insights This Week")}
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{snapshot.key_insights}</div>
      </div>
      <div style={CARD_STYLE}>
        {sectionHeader("Focus Next Week")}
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{snapshot.focus_next_week}</div>
      </div>
    </div>
  );
}

export function MvpWeeklyReport() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null); // null = latest
  const [compareWeek, setCompareWeek] = useState<string | null>(null); // null = default (immediately-previous week)
  const [drawer, setDrawer] = useState<{ title: string; rows: MvpRadiologistItem[] } | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  const overviewHistory = useFetch(() => mosaicApi.getMvpWeeklyReportHistory("overview", 12), [refreshKey]);
  const mammoHistory = useFetch(() => mosaicApi.getMvpWeeklyReportHistory("mammo", 12), [refreshKey]);
  // Current live roster - the only thing honest per-radiologist drill-down can be built from
  // (see ScopeSection's isLatest gating above).
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);

  // History is already ordered newest-first (backend ORDER BY week_ending DESC). "previous" for
  // whichever week is selected is the next entry in that same list by default, or whichever
  // week the "Compare against" picker chose.
  const [overviewSnapshot, overviewPrevious] = useMemo(() => {
    const list = overviewHistory.data ?? [];
    if (!list.length) return [null, null] as const;
    const idx = selectedWeek ? list.findIndex((s) => s.week_ending === selectedWeek) : 0;
    const snap = idx >= 0 ? list[idx] : list[0];
    const prev = compareWeek
      ? list.find((s) => s.week_ending === compareWeek) ?? null
      : idx >= 0 && idx + 1 < list.length
      ? list[idx + 1]
      : null;
    return [snap, prev] as const;
  }, [overviewHistory.data, selectedWeek, compareWeek]);

  const [mammoSnapshot, mammoPrevious] = useMemo(() => {
    const list = mammoHistory.data ?? [];
    if (!list.length) return [null, null] as const;
    const idx = selectedWeek ? list.findIndex((s) => s.week_ending === selectedWeek) : 0;
    const snap = idx >= 0 ? list[idx] : list[0];
    const prev = compareWeek
      ? list.find((s) => s.week_ending === compareWeek) ?? null
      : idx >= 0 && idx + 1 < list.length
      ? list[idx + 1]
      : null;
    return [snap, prev] as const;
  }, [mammoHistory.data, selectedWeek, compareWeek]);

  const weekOptions = useMemo(() => {
    const weeks = new Set<string>();
    (overviewHistory.data ?? []).forEach((s) => weeks.add(s.week_ending));
    (mammoHistory.data ?? []).forEach((s) => weeks.add(s.week_ending));
    return Array.from(weeks).sort().reverse();
  }, [overviewHistory.data, mammoHistory.data]);

  const isOverviewLatest = Boolean(overviewSnapshot && overviewSnapshot.week_ending === (overviewHistory.data ?? [])[0]?.week_ending);
  const isMammoLatest = Boolean(mammoSnapshot && mammoSnapshot.week_ending === (mammoHistory.data ?? [])[0]?.week_ending);

  function handleImpactClick(scope: "overview" | "mammo", bucket: ImpactBucketKey, label: string) {
    const scoped = scopeRows(radiologists.data ?? [], scope);
    setDrawer({ title: label, rows: getImpactBucketRows(scoped, bucket) });
  }

  async function handleGenerate() {
    setGenerating(true);
    setGenError(null);
    try {
      await Promise.all([mosaicApi.generateMvpWeeklyReport("overview"), mosaicApi.generateMvpWeeklyReport("mammo")]);
      setSelectedWeek(null); // jump to the just-generated (now latest) week
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Failed to generate this week's snapshot");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownloadPdf() {
    if (!reportRef.current) return;
    setExporting(true);
    try {
      const weekLabel = overviewSnapshot?.week_ending ?? mammoSnapshot?.week_ending ?? "latest";
      await downloadElementAsPdf(reportRef.current, `MVP_Weekly_Report_${weekLabel}.pdf`);
    } finally {
      setExporting(false);
    }
  }

  const hasAnySnapshot = Boolean(overviewSnapshot || mammoSnapshot);
  const buttonStyle = {
    background: "var(--rp-moss, var(--domain-deployment))",
    border: "none",
    borderRadius: "var(--radius)",
    color: "white",
    padding: "8px 14px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 16 }}>MVP Weekly Report</h2>
          <div style={{ color: "var(--text-muted)", fontSize: 13, maxWidth: 560 }}>
            Computes and persists this week's funnel/impact/escalations snapshot with real week-over-week deltas, matching the
            program's own Friday cadence. Nothing runs on a schedule — click Generate when you're ready to produce this week's
            version.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {weekOptions.length > 0 && (
            <select
              value={selectedWeek ?? weekOptions[0]}
              onChange={(e) => {
                setSelectedWeek(e.target.value);
                setCompareWeek(null); // selecting a new week resets to its default (immediately-previous) comparison
              }}
              style={{
                background: "var(--surface-raised)",
                border: "var(--glass-border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                padding: "6px 10px",
                fontSize: 13,
              }}
            >
              {weekOptions.map((w) => (
                <option key={w} value={w}>
                  Week ending {w}
                </option>
              ))}
            </select>
          )}
          {weekOptions.length > 1 && (
            <select
              value={compareWeek ?? ""}
              onChange={(e) => setCompareWeek(e.target.value || null)}
              title="Compare against a specific week instead of the default immediately-previous one"
              style={{
                background: "var(--surface-raised)",
                border: "var(--glass-border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                padding: "6px 10px",
                fontSize: 13,
              }}
            >
              <option value="">Compare vs. previous week</option>
              {weekOptions
                .filter((w) => w !== (selectedWeek ?? weekOptions[0]))
                .map((w) => (
                  <option key={w} value={w}>
                    Compare vs. {w}
                  </option>
                ))}
            </select>
          )}
          <button onClick={handleGenerate} disabled={generating} style={buttonStyle}>
            {generating ? "Generating…" : "Generate This Week's Snapshot"}
          </button>
          <button onClick={handleDownloadPdf} disabled={exporting || !hasAnySnapshot} style={buttonStyle}>
            {exporting ? "Exporting…" : "Download PDF"}
          </button>
        </div>
      </div>

      {genError && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>{genError}</div>}

      {!hasAnySnapshot && !overviewHistory.loading && !mammoHistory.loading && (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          No weekly snapshot has been generated yet. Click "Generate This Week's Snapshot" to create the first one — deltas vs
          last week will be available starting with the second snapshot.
        </div>
      )}

      <div ref={reportRef} style={{ display: "flex", flexDirection: "column", gap: 24, padding: 8 }}>
        <div style={{ textAlign: "center" }}>
          <h2 style={{ margin: 0 }}>MVP Weekly Update</h2>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Week ending {overviewSnapshot?.week_ending ?? mammoSnapshot?.week_ending ?? "—"}
          </div>
        </div>
        {overviewSnapshot && (
          <ScopeSection
            title="MVP Dashboard: Drafting/Capture"
            snapshot={overviewSnapshot}
            previous={overviewPrevious}
            isLatest={isOverviewLatest}
            onImpactClick={(bucket, label) => handleImpactClick("overview", bucket, label)}
          />
        )}
        {mammoSnapshot && (
          <ScopeSection
            title="MVP Dashboard: Mammo Screening"
            snapshot={mammoSnapshot}
            previous={mammoPrevious}
            isLatest={isMammoLatest}
            onImpactClick={(bucket, label) => handleImpactClick("mammo", bucket, label)}
          />
        )}
      </div>

      <RadiologistListDrawer
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title}
        rows={drawer?.rows ?? []}
        caption="Current live roster for this bucket, not frozen to the snapshot's week-ending date."
      />
    </div>
  );
}
