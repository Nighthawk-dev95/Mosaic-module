import { useMemo, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { StatTile } from "../../components/StatTile";
import { AIHoverCard } from "../../components/AIHoverCard";
import { StackedBarChart } from "../../components/StackedBarChart";
import { DonutChart } from "../../components/DonutChart";
import { RadiologistListDrawer } from "../../components/RadiologistListDrawer";
import { MethodologyCheckPanel } from "../../components/MethodologyCheckPanel";
import { FilterBar } from "../../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../../context/FilterContext";
import { getLocalRegion } from "../../utils/localRegion";
import { CARD_STYLE } from "../../styles/glassCard";
import {
  FUNNEL_STAGES,
  computeStatusFunnel,
  computeEscalationsByOwner,
  computeImpactBreakdown,
  computeWeeklyEngagementTrend,
  scopeRows,
  getFunnelBucketRows,
  getEscalationOwnerRows,
  getImpactBucketRows,
  type ImpactBucketKey,
} from "../../utils/mvpDashboardStats";
import type { MvpRadiologistItem } from "../../api/types";

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

interface DrawerState {
  title: string;
  rows: MvpRadiologistItem[];
}

export function MvpOverview() {
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);
  const context = useFetch(() => mosaicApi.getMvpContext(), []);
  const filters = useFilters();
  const [drawer, setDrawer] = useState<DrawerState | null>(null);

  const practices = useMemo(() => {
    if (!radiologists.data) return [];
    return Array.from(new Set(radiologists.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [radiologists.data]);

  // Enterprise-wide by default, scoped down by the FilterBar's practice/Local-team/search
  // controls - previously this dashboard had no filtering at all.
  const scoped = useMemo(() => {
    const cohortScoped = scopeRows(radiologists.data ?? [], "overview");
    return cohortScoped.filter(
      (r) =>
        matchesPractice(filters, r.practice) &&
        (!filters.local || getLocalRegion(r.practice) === filters.local) &&
        matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
    );
  }, [radiologists.data, filters]);

  const funnel = useMemo(() => computeStatusFunnel(scoped), [scoped]);
  const funnelData = useMemo(
    () => FUNNEL_STAGES.map((stage) => ({ stage, ...funnel[stage] })),
    [funnel]
  );
  const funnelTotal = useMemo(
    () => FUNNEL_STAGES.reduce((sum, s) => sum + funnel[s].on_track + funnel[s].escalated + funnel[s].declined, 0),
    [funnel]
  );

  const impact = useMemo(() => computeImpactBreakdown(scoped), [scoped]);
  const escalations = useMemo(() => computeEscalationsByOwner(scoped), [scoped]);
  const escalationData = useMemo(
    () =>
      Object.entries(escalations).map(([owner, value]) => ({
        key: owner,
        label: owner,
        value,
        color: ESCALATION_OWNER_COLORS[owner] ?? "var(--text-secondary)",
      })),
    [escalations]
  );
  const weeklyTrend = useMemo(() => computeWeeklyEngagementTrend(scoped), [scoped]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16 }}>MVP Dashboard: Drafting/Capture</h2>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          n={funnelTotal} radiologists signaling Drafting/Capture efficiency loss, currently in the MVP pipeline.
        </div>
      </div>

      {(radiologists.error || context.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({radiologists.error ?? context.error})
        </div>
      )}

      {context.data?.overview_narrative && (
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            ✨ Key insights this week — refreshes every 30 min
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{context.data.overview_narrative}</div>
        </div>
      )}

      <FilterBar practices={practices} showMonth={false} showCaptureEnabled={false} />

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20 }}>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mvp_status_funnel" entityLabel="Enterprise-wide" metricLabel="MVP Rads by Status" value={String(funnelTotal)} underline={false}>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
              MVP Rads by Status (click a segment for the radiologist list)
            </div>
          </AIHoverCard>
          <StackedBarChart
            data={funnelData}
            categoryKey="stage"
            series={[
              { key: "on_track", label: "On Track", color: STATUS_COLORS.on_track },
              { key: "escalated", label: "Escalated", color: STATUS_COLORS.escalated },
              { key: "declined", label: "Declined", color: STATUS_COLORS.declined },
            ]}
            onSegmentClick={(stage, bucket) =>
              setDrawer({
                title: `${stage} — ${bucket.replace("_", " ")}`,
                rows: getFunnelBucketRows(scoped, stage as (typeof FUNNEL_STAGES)[number], bucket as "on_track" | "escalated" | "declined"),
              })
            }
          />
        </div>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mvp_status_funnel" entityLabel="Enterprise-wide" metricLabel="Solutioning Escalations by Owner" value={String(escalations)} underline={false}>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Solutioning Escalations by Owner (click a slice for the radiologist list)
            </div>
          </AIHoverCard>
          <DonutChart
            data={escalationData}
            onSliceClick={(owner) => setDrawer({ title: `Solutioning escalations — ${owner}`, rows: getEscalationOwnerRows(scoped, owner) })}
          />
        </div>
      </div>

      <div style={CARD_STYLE}>
        <AIHoverCard
          feature="mvp_impact"
          entityLabel="Enterprise-wide"
          metricLabel="Impact on MVP Rads with Eff. Loss"
          value={String(impact.post_engagement_rads)}
          underline={false}
        >
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Impact on MVP Rads with Eff. Loss on Drafting/Capture (click a tile for the radiologist list)
          </div>
        </AIHoverCard>
        <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 12, fontStyle: "italic" }}>
          See Methodology Check below for what this comparison can and can't tell you.
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <StatTile label="Post-Engagement Rads" value={String(impact.post_engagement_rads)} />
          {(
            [
              ["at_above_baseline", "At/Above Baseline", "var(--status-good)"],
              ["improving", "Improving Toward Baseline", "var(--domain-deployment)"],
              ["not_improving", "Not Improving", "var(--status-critical)"],
              ["insufficient_data", "Insufficient Data", "var(--text-muted)"],
            ] as [ImpactBucketKey, string, string][]
          ).map(([key, label, accent]) => (
            <StatTile
              key={key}
              label={label}
              value={String(impact[key])}
              accent={accent}
              onClick={() => setDrawer({ title: label, rows: getImpactBucketRows(scoped, key) })}
            />
          ))}
        </div>
      </div>

      <MethodologyCheckPanel scope="overview" />

      <div style={CARD_STYLE}>
        <AIHoverCard feature="mvp_weekly_trend" entityLabel="Enterprise-wide" metricLabel="MVP Engaged Weekly" value="trend" underline={false}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>
            MVP Engaged Weekly (last {weeklyTrend.length} weeks)
          </div>
        </AIHoverCard>
        <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, fontStyle: "italic" }}>
          Approximated from last-updated timestamps, not exact engagement dates.
        </div>
        <StackedBarChart
          data={weeklyTrend}
          categoryKey="week"
          series={[
            { key: "engaged", label: "Engaged", color: "var(--status-good)" },
            { key: "not_yet_outreached", label: "Not Yet Outreached", color: "var(--text-muted)" },
          ]}
        />
      </div>

      <RadiologistListDrawer
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title}
        rows={drawer?.rows ?? []}
      />
    </div>
  );
}
