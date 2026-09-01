import type { CSSProperties, ReactNode } from "react";
import { useMemo } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import { getLocalRegion } from "../utils/localRegion";
import type { CapacityPracticeRollup, CapacityRadiologistItem } from "../api/types";

function fmtNum(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

function fmtShiftNames(value: string | null | undefined): ReactNode {
  if (!value) return "—";
  const names = value.split(", ");
  if (names.length <= 3) return value;
  return (
    <span title={value}>
      {names.slice(0, 3).join(", ")} +{names.length - 3} more
    </span>
  );
}

const SHARED_COLUMNS = <T extends CapacityPracticeRollup | CapacityRadiologistItem>(): DataTableColumn<T>[] => [
  { key: "total_shifts", label: "Shifts" },
  { key: "total_hours", label: "Hours", render: (r) => fmtNum(r.total_hours) },
  { key: "capacity_rvu", label: "On-Shift Capacity (RVU)", render: (r) => fmtNum(r.capacity_rvu) },
  { key: "capacity_rvu_per_hour", label: "On-Shift Capacity (RVU/hr)", render: (r) => fmtNum(r.capacity_rvu_per_hour, 2) },
  { key: "utilization_rvu_pct", label: "On-Shift Utilization", render: (r) => fmtPct(r.utilization_rvu_pct) },
  { key: "efficiency_rpwu_per_min", label: "On-Shift Efficiency (RPWU/min)", render: (r) => fmtNum(r.efficiency_rpwu_per_min, 3) },
  { key: "pct_mosaic", label: "% Mosaic", render: (r) => fmtPct(r.pct_mosaic) },
  { key: "pct_drafting", label: "% Mosaic Drafting", render: (r) => fmtPct(r.pct_drafting) },
  { key: "avg_rvu_per_case", label: "Avg RVU / Case", render: (r) => fmtNum(r.avg_rvu_per_case, 2) },
  { key: "on_shift_cases", label: "Cases" },
  { key: "ct_cases", label: "CT" },
  { key: "xr_cases", label: "XR" },
  { key: "us_cases", label: "US" },
  { key: "mr_cases", label: "MR" },
  { key: "ir_cases", label: "IR" },
];

const PRACTICE_COLUMNS: DataTableColumn<CapacityPracticeRollup>[] = [
  { key: "practice", label: "Practice" },
  ...SHARED_COLUMNS<CapacityPracticeRollup>(),
];

const RAD_COLUMNS: DataTableColumn<CapacityRadiologistItem>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "practice", label: "Practice" },
  { key: "shift_names", label: "Shift Names", render: (r) => fmtShiftNames(r.shift_names) },
  ...SHARED_COLUMNS<CapacityRadiologistItem>(),
];

const TABLE_SECTION_STYLE: CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
};

const TABLE_SCROLL_STYLE: CSSProperties = {
  maxHeight: 480,
  overflow: "auto",
};

export function CapacityDetail() {
  const byPractice = useFetch(() => mosaicApi.getCapacityByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCapacityByRadiologist(), []);
  const anyError = byPractice.error || byRadiologist.error;

  const filters = useFilters();
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
          (!filters.local || getLocalRegion(r.team) === filters.local) &&
          matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
      ),
    [byRadiologist.data, filters]
  );

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Capacity</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          On-shift capacity, efficiency, utilization, Mosaic/drafting mix, and case-mix, rolled up by practice and by radiologist.
        </div>
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      <FilterBar practices={practices} />

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
