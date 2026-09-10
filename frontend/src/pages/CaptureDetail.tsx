import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { StatTile } from "../components/StatTile";
import { TrendDelta } from "../components/TrendDelta";
import { CaptureTrendChart } from "../components/CaptureTrendChart";
import { TABLE_SECTION_STYLE, TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import type {
  CapturePracticeRollup,
  CaptureRadiologistItem,
  CaptureUtilizationTrendPracticePoint,
  CaptureUtilizationTrendRadiologistPoint,
} from "../api/types";

type Granularity = "week" | "month";

const CARD_STYLE = { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 } as const;

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            fontSize: 12,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: value === opt.value ? "var(--surface-raised)" : "transparent",
            color: value === opt.value ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

export function CaptureDetail() {
  const [granularity, setGranularity] = useState<Granularity>("week");
  const filters = useFilters();

  const overview = useFetch(() => mosaicApi.getCaptureOverview(), []);
  const byPractice = useFetch(() => mosaicApi.getCaptureByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCaptureByRadiologist(), []);
  const utilTrendByPractice = useFetch(() => mosaicApi.getCaptureTrendUtilizationByPractice(granularity), [granularity]);
  const utilTrendByRadiologist = useFetch(
    () => mosaicApi.getCaptureTrendUtilizationByRadiologist(granularity),
    [granularity]
  );
  const effTrendByPractice = useFetch(() => mosaicApi.getCaptureTrendEfficiencyByPractice(granularity), [granularity]);

  const anyError = overview.error || byPractice.error || byRadiologist.error || utilTrendByPractice.error || effTrendByPractice.error;

  const practices = useMemo(() => {
    if (!byPractice.data) return [];
    return Array.from(new Set(byPractice.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [byPractice.data]);

  const filteredByPractice = useMemo(
    () => (byPractice.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [byPractice.data, filters]
  );
  const filteredByRadiologist = useMemo(
    () =>
      (byRadiologist.data ?? []).filter(
        (r) =>
          matchesPractice(filters, r.practice) &&
          matchesRadiologistSearch(filters, r.radiologist_name, r.npi) &&
          (!filters.captureEnabledOnly || r.capture_enabled === true)
      ),
    [byRadiologist.data, filters]
  );

  const selectedPracticeUtilTrend = useMemo(
    () => (filters.practice ? (utilTrendByPractice.data ?? []).filter((r) => r.practice === filters.practice) : []),
    [utilTrendByPractice.data, filters.practice]
  );
  const selectedPracticeEffTrend = useMemo(
    () => (filters.practice ? (effTrendByPractice.data ?? []).filter((r) => r.practice === filters.practice) : []),
    [effTrendByPractice.data, filters.practice]
  );

  const topPracticeMoves = useMemo(() => {
    const rows = utilTrendByPractice.data ?? [];
    const latestByPractice = new Map<string, CaptureUtilizationTrendPracticePoint>();
    for (const r of rows) {
      if (!r.practice) continue;
      const existing = latestByPractice.get(r.practice);
      if (!existing || r.period > existing.period) latestByPractice.set(r.practice, r);
    }
    const getDelta = (r: CaptureUtilizationTrendPracticePoint) =>
      filters.captureEnabledOnly ? r.pct_change_enabled : r.pct_change_all;
    const withDelta = Array.from(latestByPractice.values()).filter((r) => getDelta(r) !== null);
    const sorted = [...withDelta].sort((a, b) => (getDelta(b) ?? 0) - (getDelta(a) ?? 0));
    return { improving: sorted.slice(0, 5), declining: sorted.slice(-5).reverse() };
  }, [utilTrendByPractice.data, filters.captureEnabledOnly]);

  const topRadiologistMoves = useMemo(() => {
    const rows = utilTrendByRadiologist.data ?? [];
    const latestByNpi = new Map<number, CaptureUtilizationTrendRadiologistPoint>();
    for (const r of rows) {
      const existing = latestByNpi.get(r.npi);
      if (!existing || r.period > existing.period) latestByNpi.set(r.npi, r);
    }
    const withDelta = Array.from(latestByNpi.values()).filter((r) => r.pct_change !== null);
    const sorted = [...withDelta].sort((a, b) => (b.pct_change ?? 0) - (a.pct_change ?? 0));
    return { improving: sorted.slice(0, 5), declining: sorted.slice(-5).reverse() };
  }, [utilTrendByRadiologist.data]);

  const PRACTICE_COLUMNS: DataTableColumn<CapturePracticeRollup>[] = [
    { key: "practice", label: "Practice" },
    {
      key: "pct_captured_all",
      label: "Utilization Rate",
      render: (r) => fmtPct(filters.captureEnabledOnly ? r.pct_captured_enabled : r.pct_captured_all),
    },
    { key: "rads_live_on_capture", label: "Rads Live on Capture" },
    { key: "rads_capture_enabled", label: "Rads Capture Enabled" },
    { key: "enablement_date", label: "Enablement Date", render: (r) => fmtDate(r.enablement_date) },
    {
      key: "pct_change_since_enablement",
      label: "Δ Since Enablement",
      render: (r) => <TrendDelta value={r.pct_change_since_enablement} />,
    },
  ];

  const RAD_COLUMNS: DataTableColumn<CaptureRadiologistItem>[] = [
    { key: "radiologist_name", label: "Radiologist" },
    { key: "practice", label: "Practice" },
    { key: "capture_enabled", label: "Capture Enabled", render: (r) => (r.capture_enabled ? "Yes" : "No") },
    { key: "pct_captured", label: "Utilization Rate", render: (r) => fmtPct(r.pct_captured) },
  ];

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Capture</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Mosaic Capture = US + Dexa combined. Utilization rate = captured ÷ capturable exams. Efficiency rate reuses the
          existing "Capture Only" TBWU/min mode from the Efficiency page.
        </div>
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <ToggleGroup
          options={[
            { value: "week" as Granularity, label: "Week over Week" },
            { value: "month" as Granularity, label: "Month over Month" },
          ]}
          value={granularity}
          onChange={setGranularity}
        />
      </div>

      <FilterBar practices={practices} showCaptureEnabled showLocal={false} showMonth={false} />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <StatTile
          label="Overall Capture Utilization Rate"
          value={
            overview.data
              ? fmtPct(filters.captureEnabledOnly ? overview.data.pct_captured_enabled : overview.data.pct_captured_all)
              : "…"
          }
          accent="var(--domain-capture)"
        />
        <StatTile
          label="Overall Capture Efficiency Rate"
          value={overview.data?.capture_mosaic_tbwu_per_min != null ? `${overview.data.capture_mosaic_tbwu_per_min.toFixed(3)} TBWU/min` : "…"}
          accent="var(--domain-capture)"
          sublabel={
            overview.data?.capture_pct_change_vs_baseline != null
              ? `${(overview.data.capture_pct_change_vs_baseline * 100).toFixed(1)}% vs baseline`
              : undefined
          }
        />
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Utilization Trend {filters.practice ? `— ${filters.practice}` : ""}
        </div>
        {filters.practice ? (
          <CaptureTrendChart
            data={selectedPracticeUtilTrend}
            granularity={granularity}
            percent
            lines={[
              { key: "pct_captured_all", name: "All Rads", color: "var(--series-6-green)" },
              { key: "pct_captured_enabled", name: "Enabled Rads", color: "var(--domain-capture)" },
            ]}
          />
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
            Select a practice above to see its utilization trend.
          </div>
        )}
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Efficiency Trend {filters.practice ? `— ${filters.practice}` : ""}
        </div>
        {filters.practice ? (
          <CaptureTrendChart
            data={selectedPracticeEffTrend}
            granularity={granularity}
            lines={[
              { key: "capture_tbwu_per_min", name: "Mosaic TBWU/min", color: "var(--series-6-green)" },
              { key: "capture_baseline_tbwu_per_min", name: "Baseline TBWU/min", color: "var(--domain-capture)", dashed: true },
            ]}
          />
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
            Select a practice above to see its efficiency trend.
          </div>
        )}
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Improvement / Decline Highlights ({granularity === "week" ? "Week over Week" : "Month over Month"})
        </div>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 300px" }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Top Improving Practices</div>
            {topPracticeMoves.improving.map((r) => (
              <div key={r.practice} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 }}>
                <span>{r.practice}</span>
                <TrendDelta value={filters.captureEnabledOnly ? r.pct_change_enabled : r.pct_change_all} />
              </div>
            ))}
          </div>
          <div style={{ flex: "1 1 300px" }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Top Declining Practices</div>
            {topPracticeMoves.declining.map((r) => (
              <div key={r.practice} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 }}>
                <span>{r.practice}</span>
                <TrendDelta value={filters.captureEnabledOnly ? r.pct_change_enabled : r.pct_change_all} />
              </div>
            ))}
          </div>
          <div style={{ flex: "1 1 300px" }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Top Improving Radiologists</div>
            {topRadiologistMoves.improving.map((r) => (
              <div key={r.npi} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 }}>
                <span>{r.radiologist_name ?? r.npi}</span>
                <TrendDelta value={r.pct_change} />
              </div>
            ))}
          </div>
          <div style={{ flex: "1 1 300px" }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Top Declining Radiologists</div>
            {topRadiologistMoves.declining.map((r) => (
              <div key={r.npi} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 }}>
                <span>{r.radiologist_name ?? r.npi}</span>
                <TrendDelta value={r.pct_change} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Practice
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byPractice.data && (
            <DataTable columns={PRACTICE_COLUMNS} rows={filteredByPractice} rowKey={(r) => r.practice ?? "unknown"} />
          )}
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byRadiologist.data && (
            <DataTable columns={RAD_COLUMNS} rows={filteredByRadiologist} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>
    </div>
  );
}
