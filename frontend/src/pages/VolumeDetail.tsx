import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { TABLE_SECTION_STYLE, TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { VolumeTrendChart } from "../components/VolumeTrendChart";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice } from "../context/FilterContext";
import type { VolumeGroupRollup } from "../api/types";

function fmtCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

type GroupBy = "practice" | "team" | "local_region";

const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "practice", label: "By Practice" },
  { value: "team", label: "By Team" },
  { value: "local_region", label: "By Local Region" },
];

const GROUP_COLUMNS: DataTableColumn<VolumeGroupRollup>[] = [
  { key: "group", label: "Group" },
  { key: "total_exams", label: "Total Exams", render: (r) => fmtCount(r.total_exams) },
  { key: "mosaic_exams", label: "Mosaic Exams", render: (r) => fmtCount(r.mosaic_exams) },
  { key: "pct_mosaic", label: "% Mosaic", render: (r) => fmtPct(r.pct_mosaic) },
  { key: "drafting_exams", label: "Drafting Exams", render: (r) => fmtCount(r.drafting_exams) },
  { key: "pct_drafting", label: "% Drafting", render: (r) => fmtPct(r.pct_drafting) },
  { key: "pct_rpce_reporting", label: "% RPCE Reporting", render: (r) => fmtPct(r.pct_rpce_reporting) },
  { key: "pct_rpce_drafting", label: "% RPCE Drafting", render: (r) => fmtPct(r.pct_rpce_drafting) },
];

function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        flex: "1 1 180px",
        minWidth: 160,
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "16px 20px",
      }}
    >
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-primary)" }}>{value}</div>
    </div>
  );
}

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
    <div style={{ display: "flex", gap: 4, background: "var(--surface-1)", borderRadius: 8, padding: 4 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            fontSize: 13,
            padding: "6px 14px",
            borderRadius: 6,
            border: "none",
            background: value === opt.value ? "var(--surface-raised)" : "transparent",
            color: value === opt.value ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
            fontWeight: value === opt.value ? 600 : 400,
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function VolumeDetail() {
  const [groupBy, setGroupBy] = useState<GroupBy>("practice");
  const filters = useFilters();

  const summary = useFetch(() => mosaicApi.getVolumeSummary(), []);
  const trend = useFetch(() => mosaicApi.getVolumeTrend(), []);
  const filterOptions = useFetch(() => mosaicApi.getVolumeFilters(), []);
  const byPractice = useFetch(() => mosaicApi.getVolumeByPractice(), []);
  const byTeam = useFetch(() => mosaicApi.getVolumeByTeam(), []);
  const byLocalRegion = useFetch(() => mosaicApi.getVolumeByLocalRegion(), []);

  const activeRows = useMemo(() => {
    const source =
      groupBy === "practice" ? byPractice.data : groupBy === "team" ? byTeam.data : byLocalRegion.data;
    if (!source) return [];
    // The top FilterBar's practice dropdown is populated from Managing Practice values, so it
    // only lines up with the "By Practice" grouping's own `group` field - Team and Local Region
    // are different grains with their own value sets, filtering by a Practice selection there
    // would silently drop every row instead of narrowing them.
    if (groupBy !== "practice") return source;
    return source.filter((r) => matchesPractice(filters, r.group));
  }, [groupBy, byPractice.data, byTeam.data, byLocalRegion.data, filters]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Volume</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Mosaic adoption volume -- exam counts, Mosaic reporting/drafting share, and RPCE coverage, reconciled
          exactly against the governed mosaic_volume_metric_view dashboard (see tools/mosaic_validation/
          VALIDATION_REPORT_VOLUME.md for the reconciliation this was built to match).
        </div>
      </div>

      {(summary.error || trend.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({summary.error ?? trend.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <KpiTile label="Total Exams" value={fmtCount(summary.data?.total_exams)} />
        <KpiTile label="Mosaic Exams" value={fmtCount(summary.data?.mosaic_exams)} />
        <KpiTile label="% Mosaic" value={fmtPct(summary.data?.pct_mosaic)} />
        <KpiTile label="Drafting Exams" value={fmtCount(summary.data?.drafting_exams)} />
        <KpiTile label="% Drafting" value={fmtPct(summary.data?.pct_drafting)} />
        <KpiTile label="% RPCE Reporting" value={fmtPct(summary.data?.pct_rpce_reporting)} />
        <KpiTile label="% RPCE Drafting" value={fmtPct(summary.data?.pct_rpce_drafting)} />
      </div>

      <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Volume Trend, Monthly
        </div>
        {/* The null-period bucket (exams with no final_datetime - confirmed identical on the
            Lakeview dashboard's own Final Month dimension) is excluded at the query layer in
            volume_service.get_volume_trend(), not here - every row this endpoint returns has a
            real period, no client-side filtering needed. */}
        {trend.data && <VolumeTrendChart data={trend.data} />}
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label}
          </div>
          <ToggleGroup options={GROUP_BY_OPTIONS} value={groupBy} onChange={setGroupBy} />
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          <DataTable columns={GROUP_COLUMNS} rows={activeRows} rowKey={(r) => r.group ?? "unknown"} />
        </div>
      </div>
    </div>
  );
}
