import type { CSSProperties } from "react";
import { useFilters } from "../context/FilterContext";
import { LOCAL_REGIONS } from "../utils/localRegion";

// Pill-shaped dropdown chrome: fully-rounded corners + a small chevron drawn via
// background-image (appearance:none removes the native arrow so the custom one shows).
const SELECT_STYLE: CSSProperties = {
  fontSize: 13,
  padding: "6px 28px 6px 14px",
  borderRadius: 999,
  border: "1px solid var(--border)",
  background:
    'var(--surface-raised) url(\'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 1l4 4 4-4" stroke="%23898781" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>\') no-repeat right 10px center',
  color: "var(--text-primary)",
  appearance: "none",
  WebkitAppearance: "none",
  cursor: "pointer",
};

// Same pill shape for text/month inputs, without the chevron (no appearance override needed).
const INPUT_STYLE: CSSProperties = {
  fontSize: 13,
  padding: "6px 14px",
  borderRadius: 999,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
};

interface Props {
  practices: string[];
  showCaptureEnabled?: boolean;
  showLocal?: boolean;
  showMonth?: boolean;
  /**
   * What the first dropdown is actually filtering, in the product's own words.
   *
   * Two different columns answer to the word "practice", and the difference is not cosmetic:
   *
   *   Practice = managing_local_practice_name_curr = the *site* the exam was read at
   *   Team     = provider_local_practice_name_curr = the radiologist's *home* practice
   *
   * A radiologist has one Team and reads at as many as seventy Practices, so the two filters
   * return different populations. Most pages here filter the site, and default accordingly -
   * `volume_service.py` builds that list from the managing column. Pages whose rows carry
   * `home_practice` (the roster, the rad summary stats) are filtering the Team and must say so,
   * or the control is quietly answering a different question than its label claims.
   */
  entityLabel?: "Practice" | "Team";
}

// Interactive filter bar shared across pages - state lives in FilterContext, so a change
// here immediately re-filters every table/chart on the current page that reads useFilters().
// showLocal/showMonth default to true; pages whose data has no team/date field to match
// against pass false so the control isn't shown as a false affordance.
export function FilterBar({
  practices,
  showCaptureEnabled = false,
  showLocal = true,
  showMonth = true,
  entityLabel = "Practice",
}: Props) {
  const { practice, local, radiologistSearch, captureEnabledOnly, month, setPractice, setLocal, setRadiologistSearch, setCaptureEnabledOnly, setMonth, reset } =
    useFilters();

  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
      <select
        value={practice}
        onChange={(e) => setPractice(e.target.value)}
        style={SELECT_STYLE}
        title={
          entityLabel === "Team"
            ? "Team = the radiologist's home practice (provider_local_practice_name_curr)."
            : "Practice = the site where the exam was read (managing_local_practice_name_curr)."
        }
      >
        <option value="">All {entityLabel === "Team" ? "Teams" : "Practices"}</option>
        {practices.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      {showLocal && (
        <select value={local} onChange={(e) => setLocal(e.target.value as typeof local)} style={SELECT_STYLE}>
          <option value="">All Regions (Local)</option>
          {LOCAL_REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      )}

      <input
        value={radiologistSearch}
        onChange={(e) => setRadiologistSearch(e.target.value)}
        placeholder="Search radiologist (name or NPI)"
        style={{ ...INPUT_STYLE, minWidth: 220 }}
      />

      {showMonth && (
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          style={INPUT_STYLE}
          title="Filters trend/date-based charts where a monthly breakdown is available"
        />
      )}

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
            padding: "6px 14px",
            borderRadius: 999,
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
