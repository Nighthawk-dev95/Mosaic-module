import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import { Badge } from "../components/Badge";
import { TrendDelta } from "../components/TrendDelta";
import { RpceTrendChart } from "../components/RpceTrendChart";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { BlockerStackedChart } from "../components/BlockerStackedChart";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import { CARD_STYLE } from "../styles/glassCard";
import { AIHoverCard } from "../components/AIHoverCard";
import type { RadSummaryStat, ThemeStat, LikertDistribution, PracticeNpsStat } from "../api/types";

// Ranked horizontal bars for magnitude comparison (same pattern/reasoning as ScorecardDetail's
// Modality/Priority Mix bars: one sequential hue, rank+label already carry identity).
function ThemeBarCard({ title, themes }: { title: string; themes: ThemeStat[] }) {
  const sorted = [...themes].sort((a, b) => b.pct - a.pct);
  const maxPct = sorted.length ? sorted[0].pct : 0;
  return (
    <div style={{ ...CARD_STYLE, flex: "1 1 280px" }}>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>{title}</div>
      {sorted.map((t) => (
        <div key={t.theme} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
          <span style={{ color: "var(--text-secondary)", fontSize: 12, width: 140, flexShrink: 0 }}>{t.theme}</span>
          <div style={{ flex: 1, background: "var(--gridline)", height: 16, position: "relative" }}>
            <div style={{ width: `${maxPct ? (t.pct / maxPct) * 100 : 0}%`, height: "100%", background: "var(--series-5-magenta)", borderRadius: "0 4px 4px 0" }} />
          </div>
          <span style={{ color: "var(--text-primary)", fontSize: 12, fontWeight: 600, width: 42, textAlign: "right", flexShrink: 0 }}>{t.pct.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

function LikertRow({ stat }: { stat: LikertDistribution }) {
  const top2 = (stat.distribution["4"] || 0) + (stat.distribution["5"] || 0);
  const total = Object.values(stat.distribution).reduce((a, b) => a + b, 0);
  const top2Pct = total ? (top2 / total) * 100 : 0;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 }}>
      <span style={{ color: "var(--text-secondary)" }}>{stat.label}</span>
      <span style={{ color: "var(--text-primary)" }}>
        {stat.mean.toFixed(2)} avg · {top2Pct.toFixed(0)}% top-2-box
        {stat.na_count ? ` · ${stat.na_count} N/A` : ""}
      </span>
    </div>
  );
}

function fmt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

const DRAFTING_GROUP_COLORS: Record<string, string> = {
  "XR/CXR-ABD-MSK": "var(--domain-deployment)",
  "CT Head": "var(--domain-capacity)",
  "CT Abd/Pel": "var(--domain-utilization)",
  "Not on Drafting": "var(--text-muted)",
};

const RAD_COLUMNS: DataTableColumn<RadSummaryStat>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  // `home_practice` is provider_local_practice_name_curr - the rad's home practice, which
  // this product calls Team. Labelling it "Practice" put the site's name on the home
  // column, and the two differ for every rad who reads outside their own practice.
  { key: "home_practice", label: "Team" },
  {
    key: "drafting_groups",
    label: "Drafting Group",
    render: (r) => (
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {r.drafting_groups.map((g) => (
          <Badge key={g} label={g} color={DRAFTING_GROUP_COLORS[g] ?? "var(--text-secondary)"} />
        ))}
      </div>
    ),
  },
  { key: "mosaic_go_live_date", label: "Mosaic Go-Live", render: (r) => fmtDate(r.mosaic_go_live_date) },
  { key: "total_mosaic_exams", label: "Total Mosaic Exams", render: (r) => fmt(r.total_mosaic_exams) },
  { key: "pct_mosaic", label: "% Mosaic", render: (r) => fmtPct(r.pct_mosaic) },
  { key: "pct_mammo", label: "% Mammo", render: (r) => fmtPct(r.pct_mammo) },
  { key: "total_xr_drafted", label: "XR Drafted", render: (r) => fmt(r.total_xr_drafted) },
  { key: "pct_xr_drafted", label: "% XR Drafted", render: (r) => fmtPct(r.pct_xr_drafted) },
  { key: "ct_head_drafted", label: "CT Head Drafted", render: (r) => fmt(r.ct_head_drafted) },
  { key: "pct_ct_head_drafted", label: "% CT Head Drafted", render: (r) => fmtPct(r.pct_ct_head_drafted) },
  { key: "ct_abdpel_drafted", label: "CT Abd/Pel Drafted", render: (r) => fmt(r.ct_abdpel_drafted) },
  { key: "pct_ct_abdpel_drafted", label: "% CT Abd/Pel Drafted", render: (r) => fmtPct(r.pct_ct_abdpel_drafted) },
  { key: "ct_chest_drafted", label: "CT Chest Drafted", render: (r) => fmt(r.ct_chest_drafted) },
  { key: "pct_ct_chest_drafted", label: "% CT Chest Drafted", render: (r) => fmtPct(r.pct_ct_chest_drafted) },
  { key: "captured_us", label: "Captured US", render: (r) => fmt(r.captured_us) },
  { key: "pct_captured", label: "% Captured", render: (r) => fmtPct(r.pct_captured) },
];

export function MosaicIntelligence() {
  const [groupFilter, setGroupFilter] = useState("");
  const filters = useFilters();

  const snapshot = useFetch(() => mosaicApi.getMosaicIntelligence(filters.practice || undefined), [filters.practice]);
  const trend = useFetch(() => mosaicApi.getRpceTrend(filters.practice || undefined), [filters.practice]);
  const radStats = useFetch(() => mosaicApi.getRadSummaryStats(), []);
  const survey = useFetch(() => mosaicApi.getRadSentiment(), []);
  // Folded in from the retired Deployment tab (see memory/tab audit) - the enablement-blocker
  // breakdown was the one piece of that tab not duplicated elsewhere; its waterfalls/tables
  // were cut since Today's own stat tiles + RPCE-split block already covered that ground.
  const blockersDrafting = useFetch(() => mosaicApi.getDeploymentBlockersDrafting(), []);
  const blockersCtAbdpel = useFetch(() => mosaicApi.getDeploymentBlockersCtAbdpel(), []);

  const anyError = snapshot.error || trend.error || radStats.error || blockersDrafting.error || blockersCtAbdpel.error;

  const practices = useMemo(() => {
    if (!radStats.data) return [];
    return Array.from(new Set(radStats.data.map((r) => r.home_practice).filter(Boolean) as string[])).sort();
  }, [radStats.data]);

  const filteredRadStats = useMemo(() => {
    if (!radStats.data) return [];
    return radStats.data.filter(
      (r) =>
        matchesPractice(filters, r.home_practice) &&
        matchesRadiologistSearch(filters, r.radiologist_name, r.npi) &&
        (!groupFilter || r.drafting_groups.includes(groupFilter))
    );
  }, [radStats.data, filters, groupFilter]);

  const filteredBlockersDrafting = useMemo(
    () => (blockersDrafting.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [blockersDrafting.data, filters]
  );
  const filteredBlockersCtAbdpel = useMemo(
    () => (blockersCtAbdpel.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [blockersCtAbdpel.data, filters]
  );

  const filteredTrend = useMemo(() => {
    if (!trend.data) return [];
    if (!filters.month) return trend.data;
    return trend.data.filter((t) => t.period.startsWith(filters.month));
  }, [trend.data, filters.month]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Mosaic Intelligence</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Enterprise-wide overview of Mosaic AI reporting, drafting, and capture adoption
        </div>
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      {/* Built from `home_practice` on the rad summary stats, so this filters Team. */}
      <FilterBar practices={practices} showLocal={false} entityLabel="Team" />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="Rads Live on Mosaic"
          value={snapshot.data ? fmt(snapshot.data.rads_live_on_mosaic) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="Rads Live on Mosaic" value={snapshot.data ? fmt(snapshot.data.rads_live_on_mosaic) : "…"} accent="var(--color-primary)" />
        </AIHoverCard>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="Rads Live on AI Drafting"
          value={snapshot.data ? fmt(snapshot.data.rads_live_on_ai_drafting) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="Rads Live on AI Drafting" value={snapshot.data ? fmt(snapshot.data.rads_live_on_ai_drafting) : "…"} accent="var(--color-primary)" />
        </AIHoverCard>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="% RPCE Reporting"
          value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_reporting) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="% RPCE Reporting"
            value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_reporting) : "…"}
            accent="var(--domain-efficiency)"
            trend={trend.data?.map((t) => t.pct_rpce_reporting ?? 0)}
          />
        </AIHoverCard>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="% RPCE Drafting"
          value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_drafting) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="% RPCE Drafting"
            value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_drafting) : "…"}
            accent="var(--domain-efficiency)"
            trend={trend.data?.map((t) => t.pct_rpce_drafting ?? 0)}
          />
        </AIHoverCard>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="Rads Live on Capture"
          value={snapshot.data ? fmt(snapshot.data.rads_live_on_capture) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="Rads Live on Capture" value={snapshot.data ? fmt(snapshot.data.rads_live_on_capture) : "…"} accent="var(--domain-capture)" />
        </AIHoverCard>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="Rads Capture Enabled"
          value={snapshot.data ? fmt(snapshot.data.rads_capture_enabled) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="Rads Capture Enabled" value={snapshot.data ? fmt(snapshot.data.rads_capture_enabled) : "…"} accent="var(--domain-capture)" />
        </AIHoverCard>
      </div>

      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Practices on RPCE
        </div>
        <div style={{ display: "flex", gap: 32 }}>
          <AIHoverCard
            feature="adoption_rollout"
            entityLabel="Enterprise-wide"
            metricLabel="Practices fully on RPCE"
            value={snapshot.data ? String(snapshot.data.practices_fully_on_rpce) : "…"}
            extra={{
              split_integration: snapshot.data ? String(snapshot.data.practices_split_integration) : "…",
              not_on_rpce: snapshot.data ? String(snapshot.data.practices_not_on_rpce) : "…",
            }}
            underline={false}
          >
            <div>
              <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-primary)" }}>
                {snapshot.data ? snapshot.data.practices_fully_on_rpce : "…"}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Fully on RPCE</div>
            </div>
          </AIHoverCard>
          <AIHoverCard
            feature="adoption_rollout"
            entityLabel="Enterprise-wide"
            metricLabel="Practices with split RPCE integration"
            value={snapshot.data ? String(snapshot.data.practices_split_integration) : "…"}
            underline={false}
          >
            <div>
              <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-secondary)" }}>
                {snapshot.data ? snapshot.data.practices_split_integration : "…"}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Split Integration</div>
            </div>
          </AIHoverCard>
          <AIHoverCard
            feature="adoption_rollout"
            entityLabel="Enterprise-wide"
            metricLabel="Practices not on RPCE"
            value={snapshot.data ? String(snapshot.data.practices_not_on_rpce) : "…"}
            underline={false}
          >
            <div>
              <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-muted)" }}>
                {snapshot.data ? snapshot.data.practices_not_on_rpce : "…"}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Not on RPCE</div>
            </div>
          </AIHoverCard>
        </div>
      </div>

      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          % RPCE Reporting &amp; Drafting Trend
        </div>
        {trend.data && <RpceTrendChart data={filteredTrend} />}
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 480px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            <AIHoverCard
              feature="adoption_rollout"
              entityLabel={filters.practice || "Enterprise-wide"}
              metricLabel="Drafting enablement blockers - total blocked rads"
              value={String(filteredBlockersDrafting.reduce((acc, r) => acc + r.count, 0))}
            >
              Drafting: Rads Blocked by Practice
            </AIHoverCard>
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
            Eligible-but-not-yet-live rads only, stacked by blocker reason.
          </div>
          {blockersDrafting.data && <BlockerStackedChart data={filteredBlockersDrafting} />}
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 480px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            <AIHoverCard
              feature="adoption_rollout"
              entityLabel={filters.practice || "Enterprise-wide"}
              metricLabel="CT Abd/Pel enablement blockers - total blocked rads"
              value={String(filteredBlockersCtAbdpel.reduce((acc, r) => acc + r.count, 0))}
            >
              CT Abd/Pel: Rads Blocked by Practice
            </AIHoverCard>
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
            Eligible-but-not-yet-enabled rads only, stacked by blocker reason.
          </div>
          {blockersCtAbdpel.data && <BlockerStackedChart data={filteredBlockersCtAbdpel} />}
        </div>
      </div>

      {survey.data && (
        <>
          <div>
            <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>Rad Sentiment</div>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 2 }}>
              Mosaic General Survey · {survey.data.responses.toLocaleString()} respondents ({(survey.data.response_rate * 100).toFixed(1)}% response
              rate) · fielded Aug 7 – Sep 2, 2026
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <AIHoverCard
              feature="sentiment"
              entityLabel="Enterprise-wide"
              metricLabel="Net Promoter Score"
              value={survey.data.nps.toFixed(1)}
              extra={{
                promoters: String(survey.data.promoters),
                passives: String(survey.data.passives),
                detractors: String(survey.data.detractors),
              }}
              underline={false}
              style={{ flex: "1 1 200px", minWidth: 180 }}
            >
              <StatTile
                label="Net Promoter Score"
                value={survey.data.nps.toFixed(1)}
                accent="var(--status-critical)"
                sublabel={`${survey.data.promoters} promoters · ${survey.data.passives} passives · ${survey.data.detractors} detractors`}
              />
            </AIHoverCard>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <ThemeBarCard title="Top Frustration Themes" themes={survey.data.top_frustration_themes} />
            <ThemeBarCard title="Top Praised Themes" themes={survey.data.top_praised_themes} />
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <div style={{ ...CARD_STYLE, flex: "1 1 320px" }}>
              <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Feature Satisfaction (1-5)
              </div>
              {survey.data.feature_satisfaction.map((s) => (
                <LikertRow key={s.label} stat={s} />
              ))}
            </div>
            <div style={{ ...CARD_STYLE, flex: "1 1 320px" }}>
              <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Agreement Statements (1-5)
              </div>
              {survey.data.agreement_statements.map((s) => (
                <LikertRow key={s.label} stat={s} />
              ))}
            </div>
          </div>

          <div style={CARD_STYLE}>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              NPS by Practice (n≥15 respondents) — every practice is net-negative
            </div>
            <DataTable
              columns={
                [
                  { key: "practice", label: "Practice" },
                  { key: "n", label: "Respondents" },
                  { key: "nps", label: "NPS", render: (r: PracticeNpsStat) => <TrendDelta value={r.nps / 100} /> },
                  { key: "mean", label: "Avg Score (0-10)" },
                ] as DataTableColumn<PracticeNpsStat>[]
              }
              rows={survey.data.by_practice}
              rowKey={(r) => r.practice}
            />
          </div>
        </>
      )}

      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Rad Summary Stats
        </div>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <select
            value={groupFilter}
            onChange={(e) => setGroupFilter(e.target.value)}
            style={{
              fontSize: 13,
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface-raised)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">All Drafting Groups</option>
            {Object.keys(DRAFTING_GROUP_COLORS).map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div style={{ maxHeight: 640, overflowY: "auto", overflowX: "auto" }}>
          {radStats.data && (
            <DataTable columns={RAD_COLUMNS} rows={filteredRadStats} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>
    </div>
  );
}
