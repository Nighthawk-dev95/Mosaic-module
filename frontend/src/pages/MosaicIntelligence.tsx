import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import { RpceTrendChart } from "../components/RpceTrendChart";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import type { RadSummaryStat } from "../api/types";

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
  { key: "home_practice", label: "Practice" },
  {
    key: "drafting_groups",
    label: "Drafting Group",
    render: (r) => (
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {r.drafting_groups.map((g) => (
          <span
            key={g}
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 999,
              border: `1px solid ${DRAFTING_GROUP_COLORS[g] ?? "var(--border)"}`,
              color: DRAFTING_GROUP_COLORS[g] ?? "var(--text-secondary)",
            }}
          >
            {g}
          </span>
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

  const anyError = snapshot.error || trend.error || radStats.error;

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

      <FilterBar practices={practices} showLocal={false} />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <StatTile label="Rads Live on Mosaic" value={snapshot.data ? fmt(snapshot.data.rads_live_on_mosaic) : "…"} />
        <StatTile
          label="Rads Live on AI Drafting"
          value={snapshot.data ? fmt(snapshot.data.rads_live_on_ai_drafting) : "…"}
        />
        <StatTile
          label="% RPCE Reporting"
          value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_reporting) : "…"}
        />
        <StatTile
          label="% RPCE Drafting"
          value={snapshot.data ? fmtPct(snapshot.data.pct_rpce_drafting) : "…"}
        />
        <StatTile
          label="Rads Live on Capture"
          value={snapshot.data ? fmt(snapshot.data.rads_live_on_capture) : "…"}
        />
        <StatTile
          label="Rads Capture Enabled"
          value={snapshot.data ? fmt(snapshot.data.rads_capture_enabled) : "…"}
        />
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
          <div>
            <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-primary)" }}>
              {snapshot.data ? snapshot.data.practices_fully_on_rpce : "…"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Fully on RPCE</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-secondary)" }}>
              {snapshot.data ? snapshot.data.practices_split_integration : "…"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Split Integration</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text-muted)" }}>
              {snapshot.data ? snapshot.data.practices_not_on_rpce : "…"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Not on RPCE</div>
          </div>
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
