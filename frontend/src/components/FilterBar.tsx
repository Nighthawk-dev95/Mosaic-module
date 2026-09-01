import type { CSSProperties } from "react";
import { useFilters } from "../context/FilterContext";
import { LOCAL_REGIONS } from "../utils/localRegion";

const SELECT_STYLE: CSSProperties = {
  fontSize: 13,
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
};

interface Props {
  practices: string[];
  showCaptureEnabled?: boolean;
}

// Interactive filter bar shared across pages - state lives in FilterContext, so a change
// here immediately re-filters every table/chart on the current page that reads useFilters().
export function FilterBar({ practices, showCaptureEnabled = false }: Props) {
  const { practice, local, radiologistSearch, captureEnabledOnly, month, setPractice, setLocal, setRadiologistSearch, setCaptureEnabledOnly, setMonth, reset } =
    useFilters();

  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
      <select value={practice} onChange={(e) => setPractice(e.target.value)} style={SELECT_STYLE}>
        <option value="">All Practices</option>
        {practices.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <select value={local} onChange={(e) => setLocal(e.target.value as typeof local)} style={SELECT_STYLE}>
        <option value="">All Regions (Local)</option>
        {LOCAL_REGIONS.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>

      <input
        value={radiologistSearch}
        onChange={(e) => setRadiologistSearch(e.target.value)}
        placeholder="Search radiologist (name or NPI)"
        style={{ ...SELECT_STYLE, minWidth: 220 }}
      />

      <input
        type="month"
        value={month}
        onChange={(e) => setMonth(e.target.value)}
        style={SELECT_STYLE}
        title="Filters trend/date-based charts where a monthly breakdown is available"
      />

      {showCaptureEnabled && (
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-secondary)" }}>
          <input type="checkbox" checked={captureEnabledOnly} onChange={(e) => setCaptureEnabledOnly(e.target.checked)} />
          Capture Enabled only
        </label>
      )}

      {(practice || local || radiologistSearch || captureEnabledOnly || month) && (
        <button
          onClick={reset}
          style={{
            fontSize: 12,
            padding: "6px 10px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-muted)",
            cursor: "pointer",
          }}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
