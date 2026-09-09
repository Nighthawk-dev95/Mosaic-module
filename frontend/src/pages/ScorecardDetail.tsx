import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import type { RadiologistScorecard } from "../api/types";

const SELECT_STYLE = {
  fontSize: 13,
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
} as const;

const TOP_N_OPTIONS = [
  { value: "5", label: "Last 5 shifts" },
  { value: "10", label: "Last 10 shifts" },
  { value: "15", label: "Last 15 shifts" },
  { value: "20", label: "Last 20 shifts" },
  { value: "25", label: "Last 25 shifts" },
  { value: "30", label: "Last 30 shifts" },
  { value: "all", label: "All shifts" },
];

type TopNKey = "top5" | "top10" | "top15" | "top20" | "top25" | "top30" | "all";

function getField(row: RadiologistScorecard, metric: "addl_capacity" | "new_efficiency" | "new_utilization" | "shifts_used", topN: TopNKey): number | null {
  const key = `${metric}_${topN}` as keyof RadiologistScorecard;
  const value = row[key];
  return typeof value === "number" ? value : null;
}

function fmtRpwu(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

function fmtPctValue(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

export function ScorecardDetail() {
  const scorecards = useFetch(() => mosaicApi.getRadiologistScorecard(), []);
  const [practice, setPractice] = useState("");
  const [npi, setNpi] = useState<number | null>(null);
  const [topN, setTopN] = useState<TopNKey>("top10");

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

  const selected = useMemo(() => radiologistsInPractice.find((r) => r.npi === npi) ?? null, [radiologistsInPractice, npi]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Radiologist Scorecard</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Additional shift capacity, efficiency, and utilization Mosaic has generated over each radiologist's re-baselined
          proxy, for radiologists live on Mosaic. Metrics are RPWU, per shift, averaged over their N most recent shifts
          since Mosaic go-live.
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
          <option value="">All Practices</option>
          {practices.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <select value={npi ?? ""} onChange={(e) => setNpi(e.target.value ? Number(e.target.value) : null)} style={{ ...SELECT_STYLE, minWidth: 240 }}>
          <option value="">Select a radiologist…</option>
          {radiologistsInPractice.map((r) => (
            <option key={r.npi} value={r.npi}>
              {r.radiologist_name ?? r.npi}
            </option>
          ))}
        </select>

        <select value={topN} onChange={(e) => setTopN(e.target.value as TopNKey)} style={SELECT_STYLE}>
          {TOP_N_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value === "all" ? "all" : `top${opt.value}`}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {!selected && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
          Select a practice and radiologist above to see their scorecard.
        </div>
      )}

      {selected && (
        <>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Mosaic go-live: {fmtDate(selected.mosaic_go_live_date)} · Team: {selected.team ?? "—"} · Shifts used:{" "}
            {getField(selected, "shifts_used", topN)}
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <StatTile label="Addl Capacity/Shift (RPWU)" value={fmtRpwu(getField(selected, "addl_capacity", topN))} />
            <StatTile label="New Efficiency (RPWU/shift)" value={fmtRpwu(getField(selected, "new_efficiency", topN))} />
            <StatTile label="New Utilization" value={fmtPctValue(getField(selected, "new_utilization", topN))} />
          </div>
        </>
      )}
    </div>
  );
}
