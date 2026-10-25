import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface StackedBarSeries {
  key: string;
  label: string;
  color: string;
}

interface Props {
  // Intentionally loose (any[], not Record<string, number | string>[]) - callers pass concrete
  // interfaces (e.g. WeeklyEngagementPoint) that don't carry an index signature, and this is a
  // generic chart wrapper, not a type-safe data contract.
  data: any[];
  categoryKey: string;
  series: StackedBarSeries[];
  height?: number;
  yTickFormatter?: (v: number) => string;
  // Click-to-drill-down (MVP Overview/Mammo's status funnel -> which radiologists make up a
  // given stage+segment). Receives the clicked bar's category value (e.g. "Solutioning") and
  // which series/segment was clicked (e.g. "escalated").
  onSegmentClick?: (category: string, seriesKey: string) => void;
}

// Generic vertical stacked-column chart - reused by the MVP Overview status funnel and the
// weekly-engaged trend (both PDF charts are vertical columns with stacked segments, unlike
// BlockerStackedChart's horizontal-bar-by-practice layout, which stays separate since its own
// axis orientation genuinely differs).
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const nonZero = payload.filter((p: any) => p.value);
  if (!nonZero.length) return null;
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
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {nonZero.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color, display: "inline-block" }} />
          <span style={{ color: "var(--text-secondary)" }}>
            {p.name}: {p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function StackedBarChart({ data, categoryKey, series, height = 280, yTickFormatter, onSegmentClick }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 20, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
        <XAxis
          dataKey={categoryKey}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={yTickFormatter}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--surface-raised)" }} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>} />
        {series.map((s) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            stackId="stack"
            fill={s.color}
            isAnimationActive={false}
            cursor={onSegmentClick ? "pointer" : undefined}
            onClick={
              onSegmentClick
                ? (point: any) => onSegmentClick(point?.[categoryKey] ?? point?.payload?.[categoryKey], s.key)
                : undefined
            }
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
