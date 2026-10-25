import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { useFilters } from "../context/FilterContext";
import { FilterBar } from "../components/FilterBar";
import { AIHoverCard } from "../components/AIHoverCard";
import { Drawer } from "../components/Drawer";
import { StatTile } from "../components/StatTile";
import { fmtPct } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";
import type { ShiftUtilizationItem } from "../api/types";

// Radiologist x day heatmap - how much of each shift was reading time, and how much of that
// reading was Mosaic-assisted or AI-drafted. Source: edw_dev.bipa_analytics.presentation_deneb_vw
// joined to tbl_exam_inventory's mosaic_read_flag/mosaic_draft_flag (see
// mosaic_service.get_shift_utilization_by_radiologist). Given radiologist-level granularity
// (thousands of rows across the whole company), a practice selection is required before
// rendering any grid - otherwise this would be an unreadable wall of rows.

type Metric = "utilization" | "drafting";

const METRIC_LABEL: Record<Metric, string> = {
  utilization: "Shift Utilization %",
  drafting: "AI Drafting %",
};

function metricValue(row: ShiftUtilizationItem, metric: Metric): number | null {
  return metric === "utilization" ? row.utilization_pct : row.pct_ai_drafted;
}

// Sequential (not diverging) single-hue ramp from the app's own surface color up to its primary
// accent, via color-mix - matches the dataviz convention of varying lightness for a magnitude
// scale, reuses existing tokens rather than inventing a new palette.
function heatColor(pct: number | null): string {
  if (pct === null) return "var(--surface-raised)";
  const clamped = Math.max(0, Math.min(1, pct));
  return `color-mix(in srgb, var(--color-primary) ${(clamped * 85).toFixed(0)}%, var(--surface-raised))`;
}

function fmtMinutes(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(0)} min`;
}

export function ShiftUtilization() {
  const { practice, radiologistSearch } = useFilters();
  const [metric, setMetric] = useState<Metric>("utilization");
  const [selected, setSelected] = useState<{ npi: number; shift_date: string } | null>(null);

  const filterOptions = useFetch(() => mosaicApi.getEfficiencyFilters(), []);
  const shifts = useFetch(
    () => (practice ? mosaicApi.getShiftUtilizationByRadiologist(practice) : Promise.resolve([] as ShiftUtilizationItem[])),
    [practice]
  );

  const filteredRows = useMemo(() => {
    if (!radiologistSearch) return shifts.data ?? [];
    const needle = radiologistSearch.toLowerCase();
    return (shifts.data ?? []).filter((r) => r.radiologist_name?.toLowerCase().includes(needle) || String(r.npi).includes(needle));
  }, [shifts.data, radiologistSearch]);

  const dates = useMemo(() => {
    const set = new Set(filteredRows.map((r) => r.shift_date));
    return [...set].sort().slice(-30);
  }, [filteredRows]);

  const radiologists = useMemo(() => {
    const byNpi = new Map<number, string>();
    for (const r of filteredRows) {
      if (!byNpi.has(r.npi)) byNpi.set(r.npi, r.radiologist_name ?? `NPI ${r.npi}`);
    }
    return [...byNpi.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [filteredRows]);

  const cellByKey = useMemo(() => {
    const map = new Map<string, ShiftUtilizationItem>();
    for (const r of filteredRows) map.set(`${r.npi}|${r.shift_date}`, r);
    return map;
  }, [filteredRows]);

  const selectedRow = selected ? cellByKey.get(`${selected.npi}|${selected.shift_date}`) : null;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        How much of each shift was reading time, and how much of that reading was Mosaic-assisted
        or AI-drafted. Select a practice to load its radiologists - this view is per-radiologist,
        so it stays deliberately filtered rather than loading every radiologist company-wide.
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />
        <div style={{ display: "flex", gap: 4, borderRadius: 999, border: "1px solid var(--border)", padding: 2 }}>
          {(Object.keys(METRIC_LABEL) as Metric[]).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              style={{
                padding: "6px 14px",
                borderRadius: 999,
                border: "none",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                background: metric === m ? "var(--color-primary)" : "transparent",
                color: metric === m ? "#0a0a0a" : "var(--text-secondary)",
                transition: "background var(--dur-card) var(--ease-standard)",
              }}
            >
              {METRIC_LABEL[m]}
            </button>
          ))}
        </div>
      </div>

      {!practice && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>
          Select a practice above to load its shift-utilization heatmap.
        </div>
      )}

      {practice && shifts.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({shifts.error})</div>
      )}

      {practice && shifts.loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}

      {practice && !shifts.loading && radiologists.length === 0 && !shifts.error && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>
          No shift data for "{practice}" in the last 90 days.
        </div>
      )}

      {practice && radiologists.length > 0 && (
        <div style={{ ...CARD_STYLE, overflow: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr>
                <th style={{ position: "sticky", left: 0, background: "var(--surface-1)", textAlign: "left", padding: "4px 10px", zIndex: 1 }}>
                  Radiologist
                </th>
                {dates.map((d) => (
                  <th key={d} style={{ padding: "4px 6px", color: "var(--text-muted)", fontWeight: 400, whiteSpace: "nowrap" }}>
                    {d.slice(5)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {radiologists.map(([npi, name]) => (
                <tr key={npi}>
                  <td style={{ position: "sticky", left: 0, background: "var(--surface-1)", padding: "4px 10px", whiteSpace: "nowrap" }}>
                    {name}
                  </td>
                  {dates.map((d) => {
                    const row = cellByKey.get(`${npi}|${d}`);
                    const value = row ? metricValue(row, metric) : null;
                    return (
                      <td key={d} style={{ padding: 2 }}>
                        <AIHoverCard
                          feature="shift_utilization"
                          entityLabel={name}
                          metricLabel={METRIC_LABEL[metric]}
                          value={value !== null ? fmtPct(value) : "—"}
                          extra={{ shift_date: d }}
                          underline={false}
                        >
                          <div
                            onClick={() => row && setSelected({ npi, shift_date: d })}
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: 4,
                              background: heatColor(value),
                              cursor: row ? "pointer" : "default",
                              transition: "background var(--dur-card) var(--ease-standard)",
                            }}
                          />
                        </AIHoverCard>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selectedRow?.radiologist_name ?? undefined}>
        {selectedRow && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{selectedRow.shift_date}</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <AIHoverCard
                feature="shift_utilization"
                entityLabel={selectedRow.radiologist_name ?? `NPI ${selectedRow.npi}`}
                metricLabel="Shift utilization"
                value={fmtPct(selectedRow.utilization_pct)}
                underline={false}
                style={{ flex: "1 1 140px", minWidth: 140 }}
              >
                <StatTile label="Shift utilization" value={fmtPct(selectedRow.utilization_pct)} />
              </AIHoverCard>
              <AIHoverCard
                feature="shift_utilization"
                entityLabel={selectedRow.radiologist_name ?? `NPI ${selectedRow.npi}`}
                metricLabel="% Mosaic read"
                value={fmtPct(selectedRow.pct_mosaic_read)}
                underline={false}
                style={{ flex: "1 1 140px", minWidth: 140 }}
              >
                <StatTile label="% Mosaic read" value={fmtPct(selectedRow.pct_mosaic_read)} />
              </AIHoverCard>
              <AIHoverCard
                feature="shift_utilization"
                entityLabel={selectedRow.radiologist_name ?? `NPI ${selectedRow.npi}`}
                metricLabel="% AI drafted"
                value={fmtPct(selectedRow.pct_ai_drafted)}
                underline={false}
                style={{ flex: "1 1 140px", minWidth: 140 }}
              >
                <StatTile label="% AI drafted" value={fmtPct(selectedRow.pct_ai_drafted)} />
              </AIHoverCard>
            </div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              {fmtMinutes(selectedRow.reading_minutes)} reading out of {fmtMinutes(selectedRow.shift_total_minutes)} scheduled.
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
