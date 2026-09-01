import { useMemo } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import { getLocalRegion } from "../utils/localRegion";
import type { RadiologistRosterItem } from "../api/types";

const COLUMNS: DataTableColumn<RadiologistRosterItem>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "home_practice", label: "Practice" },
  { key: "working_subspecialty", label: "Subspecialty" },
  { key: "deployment_status", label: "Deployment Status" },
  { key: "current_team", label: "Team" },
  { key: "reporting_cases_read", label: "Exams Read" },
  { key: "total_drafting_cases", label: "Drafting Cases" },
  { key: "total_mosaic_exams", label: "Total Mosaic Exams" },
  { key: "capture_enabled", label: "Capture Enabled", render: (r) => (r.capture_enabled ? "Yes" : "No") },
];

export function RadiologistRoster() {
  const roster = useFetch(() => mosaicApi.getRoster({ limit: 500 }), []);
  const filters = useFilters();

  const practices = useMemo(() => {
    if (!roster.data) return [];
    return Array.from(new Set(roster.data.map((r) => r.home_practice).filter(Boolean) as string[])).sort();
  }, [roster.data]);

  const filteredRows = useMemo(() => {
    if (!roster.data) return [];
    return roster.data.filter(
      (r) =>
        matchesPractice(filters, r.home_practice) &&
        (!filters.local || getLocalRegion(r.current_team) === filters.local) &&
        matchesRadiologistSearch(filters, r.radiologist_name, r.npi) &&
        (!filters.captureEnabledOnly || r.capture_enabled === true)
    );
  }, [roster.data, filters]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16, flex: 1, overflowY: "auto" }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Radiologist Roster</h1>
      <FilterBar practices={practices} showCaptureEnabled />
      {roster.error && <div style={{ color: "var(--status-critical)" }}>{roster.error}</div>}
      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div style={{ maxHeight: 640, overflow: "auto" }}>
          {roster.data && <DataTable columns={COLUMNS} rows={filteredRows} rowKey={(r) => r.npi} />}
        </div>
      </div>
    </div>
  );
}
