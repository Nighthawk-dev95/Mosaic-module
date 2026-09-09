import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import type { RadiologistScorecard, ScorecardMetrics } from "../api/types";

const SELECT_STYLE = {
  fontSize: 13,
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
} as const;

const CARD_STYLE = { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 } as const;

const TOP_N_OPTIONS = [
  { value: "5", label: "Last 5 shifts" },
  { value: "10", label: "Last 10 shifts" },
  { value: "15", label: "Last 15 shifts" },
  { value: "20", label: "Last 20 shifts" },
  { value: "25", label: "Last 25 shifts" },
  { value: "30", label: "Last 30 shifts" },
  { value: "all", label: "All shifts" },
];

const MODALITY_FIELDS: { key: keyof ScorecardMetrics; label: string }[] = [
  { key: "ct_cases", label: "CT" },
  { key: "xr_cases", label: "XR" },
  { key: "us_cases", label: "US" },
  { key: "mr_cases", label: "MR" },
  { key: "nm_cases", label: "NM" },
  { key: "pt_cases", label: "PT" },
  { key: "mg_cases", label: "MG" },
  { key: "ir_cases", label: "IR" },
  { key: "other_modality_cases", label: "Other" },
];

const PRIORITY_FIELDS: { key: keyof ScorecardMetrics; label: string }[] = [
  { key: "routine_cases", label: "Routine" },
  { key: "stat_cases", label: "STAT" },
  { key: "stroke_cases", label: "Stroke" },
  { key: "trauma_cases", label: "Trauma" },
  { key: "otherp_cases", label: "Other" },
];

const NUMERIC_METRIC_KEYS: (keyof ScorecardMetrics)[] = [
  "shifts_worked",
  "case_count",
  "addl_capacity_per_shift",
  "efficiency",
  "shift_utilization",
  "avg_units_per_shift",
  "ct_cases",
  "xr_cases",
  "us_cases",
  "mr_cases",
  "nm_cases",
  "pt_cases",
  "mg_cases",
  "ir_cases",
  "other_modality_cases",
  "routine_cases",
  "stat_cases",
  "stroke_cases",
  "trauma_cases",
  "otherp_cases",
];

// Every count-based field sums cleanly across radiologists; the four rate fields need a
// shifts-worked-weighted average instead of a straight SUM, since averaging two radiologists'
// already-averaged per-shift rates equally (ignoring how many shifts each contributed) would
// skew the practice number toward whichever radiologist happens to have fewer shifts.
const RATE_FIELDS = new Set<keyof ScorecardMetrics>(["addl_capacity_per_shift", "efficiency", "shift_utilization", "avg_units_per_shift"]);

function computePracticeRollup(rows: RadiologistScorecard[], topN: string): ScorecardMetrics | null {
  const entries = rows.map((r) => r.metrics.find((m) => m.top_n === topN)).filter((m): m is ScorecardMetrics => !!m);
  if (!entries.length) return null;

  const result = { top_n: topN } as ScorecardMetrics;
  for (const key of NUMERIC_METRIC_KEYS) {
    if (RATE_FIELDS.has(key)) {
      let weightedSum = 0;
      let weightTotal = 0;
      for (const m of entries) {
        const value = m[key];
        if (typeof value === "number" && m.shifts_worked) {
          weightedSum += value * m.shifts_worked;
          weightTotal += m.shifts_worked;
        }
      }
      (result[key] as number | null) = weightTotal ? weightedSum / weightTotal : null;
    } else {
      (result[key] as number) = entries.reduce((acc, m) => acc + ((m[key] as number) || 0), 0);
    }
  }
  return result;
}

function fmtRpwu(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toFixed(2);
}

function fmtPctValue(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function fmtCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

function MixCard({ title, fields, metrics }: { title: string; fields: { key: keyof ScorecardMetrics; label: string }[]; metrics: ScorecardMetrics }) {
  const rows = fields
    .map((f) => ({ label: f.label, count: (metrics[f.key] as number) || 0 }))
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count);

  return (
    <div style={{ ...CARD_STYLE, flex: "1 1 240px" }}>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>{title}</div>
      {rows.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No cases in this window.</div>}
      {rows.map((r) => (
        <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 13 }}>
          <span style={{ color: "var(--text-secondary)" }}>{r.label}</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{r.count.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export function ScorecardDetail() {
  const scorecards = useFetch(() => mosaicApi.getRadiologistScorecard(), []);
  const [practice, setPractice] = useState("");
  const [npi, setNpi] = useState<number | null>(null);
  const [topN, setTopN] = useState("10");

  const practices = useMemo(() => {
    if (!scorecards.data) return [];
    return Array.from(new Set(scorecards.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [scorecards.data]);

  const radiologistsInPractice = useMemo(() => {
    if (!scorecards.data) return [];
    return scorecards.data
      .filter((r) => !practice || r.practice === practice)
      .sort((a, b) => (a.radiologist_name ?? "").localeCompare(b.radiologist_name ?? ""));
  }, [scorecards.data, practice]);

  const selectedRadiologist = useMemo(() => radiologistsInPractice.find((r) => r.npi === npi) ?? null, [radiologistsInPractice, npi]);

  const practiceRollup = useMemo(
    () => (practice ? computePracticeRollup(radiologistsInPractice, topN) : null),
    [radiologistsInPractice, practice, topN]
  );

  const metrics = selectedRadiologist ? selectedRadiologist.metrics.find((m) => m.top_n === topN) ?? null : practiceRollup;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Radiologist Scorecard</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Additional shift capacity, efficiency, and utilization Mosaic has generated over each radiologist's re-baselined
          proxy, for radiologists live on Mosaic. Metrics are RPWU, per shift, averaged over the N most recent shifts
          since Mosaic go-live. Selecting a practice shows its overall rollup; picking a radiologist narrows further.
        </div>
      </div>

      {scorecards.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({scorecards.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={practice}
          onChange={(e) => {
            setPractice(e.target.value);
            setNpi(null);
          }}
          style={SELECT_STYLE}
        >
          <option value="">Select a practice…</option>
          {practices.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <select value={npi ?? ""} onChange={(e) => setNpi(e.target.value ? Number(e.target.value) : null)} style={{ ...SELECT_STYLE, minWidth: 240 }}>
          <option value="">All radiologists (practice rollup)</option>
          {radiologistsInPractice.map((r) => (
            <option key={r.npi} value={r.npi}>
              {r.radiologist_name ?? r.npi}
            </option>
          ))}
        </select>

        <select value={topN} onChange={(e) => setTopN(e.target.value)} style={SELECT_STYLE}>
          {TOP_N_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {!practice && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
          Select a practice above to see its scorecard.
        </div>
      )}

      {practice && metrics && (
        <>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            {selectedRadiologist ? (
              <>
                Mosaic go-live: {fmtDate(selectedRadiologist.mosaic_go_live_date)} · Team: {selectedRadiologist.team ?? "—"}
              </>
            ) : (
              <>
                {practice} · {radiologistsInPractice.length} radiologist{radiologistsInPractice.length === 1 ? "" : "s"}
              </>
            )}
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <StatTile label="Addl Capacity/Shift (RPWU)" value={fmtRpwu(metrics.addl_capacity_per_shift)} />
            <StatTile label="Efficiency (TBWU per shift)" value={fmtRpwu(metrics.efficiency)} />
            <StatTile label="Shift Utilization" value={fmtPctValue(metrics.shift_utilization)} />
            <StatTile label="Avg Units/Shift (RPWU)" value={fmtRpwu(metrics.avg_units_per_shift)} />
            <StatTile label="Case Count" value={fmtCount(metrics.case_count)} />
            <StatTile label="Shifts Worked" value={fmtCount(metrics.shifts_worked)} />
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <MixCard title="Modality Mix" fields={MODALITY_FIELDS} metrics={metrics} />
            <MixCard title="Priority Mix" fields={PRIORITY_FIELDS} metrics={metrics} />
          </div>
        </>
      )}
    </div>
  );
}
