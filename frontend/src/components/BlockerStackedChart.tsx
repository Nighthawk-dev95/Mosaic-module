import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BlockerByPractice } from "../api/types";

interface Props {
  data: BlockerByPractice[];
  topN?: number;
}

// Fixed order - never cycled. A practice that has zero rads in a given bucket just
// contributes 0 to that segment; the legend and color assignment stay stable regardless.
const BLOCKER_ORDER: { key: string; color: string }[] = [
  { key: "No Reporting Cases Read", color: "var(--blocker-no-cases-read)" },
  { key: "No AD Group", color: "var(--blocker-no-ad-group)" },
  { key: "No XR & CT Head Training", color: "var(--blocker-no-xr-and-cthead-training)" },
  { key: "No XR Training", color: "var(--blocker-no-xr-training)" },
  { key: "No CT Head Training", color: "var(--blocker-no-cthead-training)" },
  { key: "Other", color: "var(--blocker-other)" },
];

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
            {p.dataKey}: {p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function BlockerStackedChart({ data, topN = 15 }: Props) {
  const byPractice = new Map<string, Record<string, number>>();
  for (const row of data) {
    const practice = row.practice ?? "Unknown";
    if (!byPractice.has(practice)) byPractice.set(practice, {});
    byPractice.get(practice)![row.blocker] = (byPractice.get(practice)![row.blocker] ?? 0) + row.count;
  }

  const ranked = Array.from(byPractice.entries())
    .map(([practice, counts]) => ({
      practice,
      ...counts,
      total: Object.values(counts).reduce((a, b) => a + b, 0),
    }))
    .sort((a, b) => b.total - a.total);

  const shown = ranked.slice(0, topN);
  const droppedCount = ranked.length - shown.length;

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(280, shown.length * 28)}>
        <BarChart data={shown} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--gridline)" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="practice"
            width={140}
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--surface-raised)" }} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>} />
          {BLOCKER_ORDER.map((b) => (
            <Bar key={b.key} dataKey={b.key} stackId="blockers" fill={b.color} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      {droppedCount > 0 && (
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 8 }}>
          Showing top {topN} practices by blocked-rad count; {droppedCount} more practice{droppedCount === 1 ? "" : "s"} not shown.
        </div>
      )}
    </div>
  );
}
