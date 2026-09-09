import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface CaptureTrendLine {
  key: string;
  name: string;
  color: string;
  dashed?: boolean;
}

interface CaptureTrendChartProps {
  data: Record<string, unknown>[];
  granularity: "week" | "month";
  lines: CaptureTrendLine[];
  percent?: boolean;
}

function fmtPeriod(period: string, granularity: "week" | "month"): string {
  const d = new Date(period);
  return granularity === "week"
    ? d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function CaptureTrendTooltip({ active, payload, label, granularity, percent }: any) {
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
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{fmtPeriod(label, granularity)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span
            style={{
              width: 10,
              height: 2,
              background: p.color,
              display: "inline-block",
              opacity: p.strokeDasharray ? 0.6 : 1,
            }}
          />
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
            {p.value === null || p.value === undefined ? "—" : percent ? `${(p.value * 100).toFixed(1)}%` : p.value.toFixed(3)}
          </span>
          <span style={{ color: "var(--text-secondary)" }}>{p.name}</span>
        </div>
      ))}
    </div>
  );
}

export function CaptureTrendChart({ data, granularity, lines, percent = false }: CaptureTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
        <XAxis
          dataKey="period"
          tickFormatter={(v) => fmtPeriod(v, granularity)}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => (percent ? `${Math.round(v * 100)}%` : v.toFixed(2))}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip content={<CaptureTrendTooltip granularity={granularity} percent={percent} />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
          formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>}
        />
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.name}
            stroke={line.color}
            strokeWidth={line.dashed ? 1.5 : 2}
            strokeDasharray={line.dashed ? "4 3" : undefined}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
