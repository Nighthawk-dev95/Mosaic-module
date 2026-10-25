import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface ComboTrendPoint {
  period: string;
  volume: number;
  efficiencyChangePct: number | null;
}

interface Props {
  data: ComboTrendPoint[];
  volumeLabel?: string;
  efficiencyLabel?: string;
  height?: number;
}

function fmtMonth(period: string): string {
  const d = new Date(period);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function ComboTooltip({ active, payload, label }: any) {
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
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{fmtMonth(label)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ width: 10, height: 2, background: p.color, display: "inline-block" }} />
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
            {p.dataKey === "efficiencyChangePct"
              ? p.value === null || p.value === undefined
                ? "—"
                : `${(p.value * 100).toFixed(1)}%`
              : p.value}
          </span>
          <span style={{ color: "var(--text-secondary)" }}>{p.name}</span>
        </div>
      ))}
    </div>
  );
}

// Dual-axis Bar+Line combo - the one genuinely new chart primitive the Mammo Screening
// dashboard needs (volume as bars on the left axis, efficiency change % as a line on the
// right axis). No existing component did dual-axis before this.
export function ComboTrendChart({ data, volumeLabel = "Volume", efficiencyLabel = "Efficiency Change", height = 260 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
        <XAxis
          dataKey="period"
          tickFormatter={fmtMonth}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          yAxisId="volume"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <YAxis
          yAxisId="pct"
          orientation="right"
          tickFormatter={(v) => `${Math.round(v * 100)}%`}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip content={<ComboTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>} />
        <Bar yAxisId="volume" dataKey="volume" name={volumeLabel} fill="var(--domain-capture)" isAnimationActive={false} />
        <Line
          yAxisId="pct"
          type="monotone"
          dataKey="efficiencyChangePct"
          name={efficiencyLabel}
          stroke="var(--series-5-magenta)"
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
