import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { useFilters } from "../context/FilterContext";
import { FilterBar } from "../components/FilterBar";
import { AIHoverCard } from "../components/AIHoverCard";
import { Drawer } from "../components/Drawer";
import { StatTile } from "../components/StatTile";
import { DataTable, fmtPct, type DataTableColumn } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";
import type { CapacityRadiologistItem, CapacityPracticeRollup } from "../api/types";

// Replaces the old Top-N-shift-window Scorecard tab. Built entirely on the existing
// /capacity/by-radiologist + /capacity/by-practice endpoints (zero new backend work) - adds one
// thing PCC's own productivity scorecards do that the old page didn't: every figure is shown
// next to its practice average, so "am I ahead or behind my peers" is answered directly rather
// than left to the reader to infer from a bare number.

interface MetricDef {
  key: "efficiency_rpwu_per_min" | "capacity_rpwu" | "pct_mosaic" | "pct_drafting";
  label: string;
  format: (v: number | null) => string;
  feature: string;
}

const METRICS: MetricDef[] = [
  { key: "efficiency_rpwu_per_min", label: "Efficiency (RPWU/min)", format: (v) => (v === null ? "—" : v.toFixed(3)), feature: "efficiency_metric" },
  { key: "capacity_rpwu", label: "Capacity (RPWU)", format: (v) => (v === null ? "—" : v.toFixed(1)), feature: "capacity_figure" },
  { key: "pct_mosaic", label: "% Mosaic", format: fmtPct, feature: "adoption_rollout" },
  { key: "pct_drafting", label: "% Drafting", format: fmtPct, feature: "adoption_rollout" },
];

function deltaColor(value: number | null, avg: number | null): string {
  if (value === null || avg === null || avg === 0) return "var(--text-muted)";
  const relDiff = (value - avg) / Math.abs(avg);
  if (relDiff > 0) return "var(--status-good)";
  if (relDiff > -0.05) return "var(--status-warning)";
  return "var(--status-critical)";
}

function fmtDelta(value: number | null, avg: number | null, format: (v: number | null) => string): string {
  if (value === null || avg === null) return "";
  const diff = value - avg;
  const sign = diff >= 0 ? "+" : "";
  return `${sign}${format(diff).replace(/^-/, "-")} vs practice avg`;
}

interface Row extends CapacityRadiologistItem {
  practiceAvg: CapacityPracticeRollup | null;
}

export function RadMosaicScorecard() {
  const { practice, radiologistSearch } = useFilters();
  const filterOptions = useFetch(() => mosaicApi.getEfficiencyFilters(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCapacityByRadiologist(), []);
  const byPractice = useFetch(() => mosaicApi.getCapacityByPractice(), []);
  const [selected, setSelected] = useState<number | null>(null);

  const practiceAvgByName = useMemo(() => {
    const map = new Map<string, CapacityPracticeRollup>();
    for (const p of byPractice.data ?? []) {
      if (p.practice) map.set(p.practice, p);
    }
    return map;
  }, [byPractice.data]);

  const rows: Row[] = useMemo(() => {
    let data = byRadiologist.data ?? [];
    if (practice) data = data.filter((r) => r.practice === practice);
    if (radiologistSearch) {
      const needle = radiologistSearch.toLowerCase();
      data = data.filter((r) => r.radiologist_name?.toLowerCase().includes(needle) || String(r.npi).includes(needle));
    }
    return data.map((r) => ({ ...r, practiceAvg: r.practice ? practiceAvgByName.get(r.practice) ?? null : null }));
  }, [byRadiologist.data, practice, radiologistSearch, practiceAvgByName]);

  const selectedRow = rows.find((r) => r.npi === selected) ?? null;

  const columns: DataTableColumn<Row>[] = [
    { key: "radiologist_name", label: "Radiologist", render: (r) => r.radiologist_name ?? `NPI ${r.npi}` },
    { key: "practice", label: "Practice" },
    ...METRICS.map((m): DataTableColumn<Row> => ({
      key: m.key,
      label: m.label,
      render: (r) => (
        <div>
          <span>{m.format(r[m.key])}</span>
          {r.practiceAvg && (
            <div style={{ fontSize: 10, color: deltaColor(r[m.key], r.practiceAvg[m.key]) }}>
              {fmtDelta(r[m.key], r.practiceAvg[m.key], m.format)}
            </div>
          )}
        </div>
      ),
    })),
  ];

  const loading = byRadiologist.loading || byPractice.loading;
  const error = byRadiologist.error || byPractice.error;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        Efficiency, capacity, % Mosaic, and % drafting per radiologist - each figure shown next to
        its practice average so you can see who's ahead of or behind their peers. Click a row for
        detail.
      </div>

      <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />

      {error && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({error})</div>}
      {loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}

      {!loading && rows.length > 0 && (
        <div style={{ ...CARD_STYLE, padding: 0, overflow: "auto" }}>
          <DataTable columns={columns} rows={rows} rowKey={(r) => r.npi} onRowClick={(r) => setSelected(r.npi)} />
        </div>
      )}

      {!loading && rows.length === 0 && !error && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>No radiologists match the current filters.</div>
      )}

      <Drawer open={selected !== null} onClose={() => setSelected(null)} title={selectedRow?.radiologist_name ?? undefined}>
        {selectedRow && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{selectedRow.practice}</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {METRICS.map((m) => (
                <AIHoverCard
                  key={m.key}
                  feature={m.feature}
                  entityLabel={selectedRow.radiologist_name ?? `NPI ${selectedRow.npi}`}
                  metricLabel={m.label}
                  value={m.format(selectedRow[m.key])}
                  extra={{ practice_avg: m.format(selectedRow.practiceAvg?.[m.key] ?? null) }}
                  underline={false}
                  style={{ flex: "1 1 160px", minWidth: 160 }}
                >
                  <StatTile
                    label={m.label}
                    value={m.format(selectedRow[m.key])}
                    sublabel={selectedRow.practiceAvg ? `practice avg ${m.format(selectedRow.practiceAvg[m.key])}` : undefined}
                  />
                </AIHoverCard>
              ))}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
