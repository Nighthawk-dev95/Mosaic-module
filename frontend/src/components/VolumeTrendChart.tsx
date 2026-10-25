import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { VolumeTrendPoint } from "../api/types";

type Mode = "pct" | "count";

interface Props {
  data: VolumeTrendPoint[];
}

// Reuses the same validated 2-series pair RpceTrendChart uses (fixed categorical slots 4/5,
// not the per-domain tab colors - this chart isn't "the Volume domain's identity", just two
// related adoption lines on one page).
const MOSAIC_COLOR = "var(--series-4-yellow)";
const DRAFTING_COLOR = "var(--series-5-magenta)";

function fmtDate(period: string): string {
  const d = new Date(period);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function TrendTooltip({ active, payload, label, mode }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "8px 12px",
        fontSize: 12,
      }}
    >
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{fmtDate(label)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 2, background: p.color, display: "inline-block" }} />
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
            {mode === "pct" ? `${(p.value * 100).toFixed(1)}%` : p.value.toLocaleString()}
          </span>
          <span style={{ color: "var(--text-secondary)" }}>{p.name}</span>
        </div>
      ))}
    </div>
  );
}

export function VolumeTrendChart({ data }: Props) {
  const [mode, setMode] = useState<Mode>("count");

  const mosaicKey = mode === "pct" ? "pct_mosaic" : "mosaic_exams";
  const draftingKey = mode === "pct" ? "pct_drafting" : "drafting_exams";

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {(["count", "pct"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              fontSize: 12,
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: mode === m ? "var(--surface-raised)" : "transparent",
              color: mode === m ? "var(--text-primary)" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            {m === "pct" ? "% of Exams" : "Exam Counts"}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="period"
            tickFormatter={fmtDate}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--gridline)" }}
            tickLine={false}
            minTickGap={40}
          />
          <YAxis
            tickFormatter={(v) => (mode === "pct" ? `${Math.round(v * 100)}%` : v.toLocaleString())}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<TrendTooltip mode={mode} />} />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
            formatter={(value) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
          />
          <Line
            type="monotone"
            dataKey={mosaicKey}
            name="Mosaic Exams"
            stroke={MOSAIC_COLOR}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey={draftingKey}
            name="Drafting Exams"
            stroke={DRAFTING_COLOR}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
