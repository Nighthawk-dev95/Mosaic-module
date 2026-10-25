import { useMemo, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { StatTile } from "../../components/StatTile";
import { AIHoverCard } from "../../components/AIHoverCard";
import { StackedBarChart } from "../../components/StackedBarChart";
import { ComboTrendChart } from "../../components/ComboTrendChart";
import { RadiologistListDrawer } from "../../components/RadiologistListDrawer";
import { MethodologyCheckPanel } from "../../components/MethodologyCheckPanel";
import { FilterBar } from "../../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../../context/FilterContext";
import { getLocalRegion } from "../../utils/localRegion";
import { CARD_STYLE } from "../../styles/glassCard";
import { computeImpactBreakdown, computeWeeklyEngagementTrend, scopeRows, getImpactBucketRows, type ImpactBucketKey } from "../../utils/mvpDashboardStats";
import type { MvpRadiologistItem } from "../../api/types";

interface DrawerState {
  title: string;
  rows: MvpRadiologistItem[];
}

export function MvpMammo() {
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);
  const context = useFetch(() => mosaicApi.getMvpContext(), []);
  const rpTrend = useFetch(() => mosaicApi.getMammoScreeningTrend(), []);
  const mvpTrend = useFetch(() => mosaicApi.getMvpMammoScreeningTrend(), []);
  const filters = useFilters();
  const [drawer, setDrawer] = useState<DrawerState | null>(null);

  const practices = useMemo(() => {
    if (!radiologists.data) return [];
    return Array.from(new Set(radiologists.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [radiologists.data]);

  const scoped = useMemo(() => {
    const cohortScoped = scopeRows(radiologists.data ?? [], "mammo");
    return cohortScoped.filter(
      (r) =>
        matchesPractice(filters, r.practice) &&
        (!filters.local || getLocalRegion(r.practice) === filters.local) &&
        matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
    );
  }, [radiologists.data, filters]);
  const impact = useMemo(() => computeImpactBreakdown(scoped), [scoped]);
  const weeklyTrend = useMemo(() => computeWeeklyEngagementTrend(scoped), [scoped]);

  const rpComboData = useMemo(
    () => (rpTrend.data ?? []).map((p) => ({ period: p.period, volume: p.screening_volume, efficiencyChangePct: p.screening_efficiency_change_pct })),
    [rpTrend.data]
  );
  const mvpComboData = useMemo(
    () => (mvpTrend.data ?? []).map((p) => ({ period: p.period, volume: p.screening_volume, efficiencyChangePct: p.screening_efficiency_change_pct })),
    [mvpTrend.data]
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16 }}>MVP Dashboard: Mammo Screening</h2>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          {scoped.length} radiologists signaling Mammo-screening efficiency loss, currently in the MVP pipeline.
        </div>
      </div>

      {(radiologists.error || context.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({radiologists.error ?? context.error})
        </div>
      )}

      {context.data?.mammo_narrative && (
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            ✨ Key insights this week — refreshes every 30 min
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{context.data.mammo_narrative}</div>
        </div>
      )}

      <FilterBar practices={practices} showMonth={false} showCaptureEnabled={false} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mammo_screening_trend" entityLabel="RP Overall" metricLabel="Screening Mammo Efficiency Change" value="trend" underline={false}>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Screening Mammo Efficiency Change (RP Overall)
            </div>
          </AIHoverCard>
          {rpTrend.data && <ComboTrendChart data={rpComboData} volumeLabel="Screening Volume" efficiencyLabel="Screening Eff Change" />}
        </div>
        <div style={CARD_STYLE}>
          <AIHoverCard feature="mammo_screening_trend" entityLabel="MVP Mammo Rads Only" metricLabel="Screening Mammo Efficiency Change" value="trend" underline={false}>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Screening Mammo Efficiency Change (MVP Mammo Rads Only)
            </div>
          </AIHoverCard>
          {mvpTrend.data && <ComboTrendChart data={mvpComboData} volumeLabel="Screening Volume" efficiencyLabel="Screening Eff Change" />}
        </div>
      </div>

      <div style={CARD_STYLE}>
        <AIHoverCard feature="mvp_impact" entityLabel="Mammo cohort" metricLabel="Impact on MVP Mammo Rads" value={String(impact.post_engagement_rads)} underline={false}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Impact on MVP Mammo Rads (click a tile for the radiologist list)
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

      <MethodologyCheckPanel scope="mammo" />

      <div style={CARD_STYLE}>
        <AIHoverCard feature="mvp_weekly_trend" entityLabel="Mammo cohort" metricLabel="MVP Engaged Weekly" value="trend" underline={false}>
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
