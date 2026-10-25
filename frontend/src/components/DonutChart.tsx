import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export interface DonutSlice {
  key: string;
  label: string;
  value: number;
  color: string;
}

interface Props {
  data: DonutSlice[];
  height?: number;
  // Click-to-drill-down (e.g. MVP Overview's "Solutioning Escalations by Owner" -> which
  // radiologists are escalated to a given owner).
  onSliceClick?: (key: string) => void;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
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
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ width: 8, height: 8, borderRadius: 2, background: p.payload.color, display: "inline-block" }} />
        <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{p.value}</span>
        <span style={{ color: "var(--text-secondary)" }}>{p.name}</span>
      </div>
    </div>
  );
}

// Generic donut (Solutioning Escalations by Owner, Mentor Matching Status) - recharts PieChart
// with innerRadius, the one chart primitive this app didn't have yet.
export function DonutChart({ data, height = 220, onSliceClick }: Props) {
  const nonZero = data.filter((d) => d.value > 0);
  if (nonZero.length === 0) {
    return <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", padding: 40 }}>No data.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={nonZero}
          dataKey="value"
          nameKey="label"
          innerRadius="55%"
          outerRadius="80%"
          isAnimationActive={false}
          cursor={onSliceClick ? "pointer" : undefined}
          onClick={onSliceClick ? (slice: any) => onSliceClick(slice?.key ?? slice?.payload?.key) : undefined}
        >
          {nonZero.map((d) => (
            <Cell key={d.key} fill={d.color} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
          formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
