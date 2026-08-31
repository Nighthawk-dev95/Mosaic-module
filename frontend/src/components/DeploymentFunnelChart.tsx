import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DeploymentFunnelStage } from "../api/types";

interface Props {
  stages: DeploymentFunnelStage[];
}

const BAR_COLOR = "var(--domain-deployment)";

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const stage = payload[0]?.payload as DeploymentFunnelStage | undefined;
  if (!stage) return null;
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
      <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>{stage.stage}</div>
      <div style={{ color: "var(--text-secondary)" }}>{stage.count.toLocaleString()} rads</div>
    </div>
  );
}

export function DeploymentFunnelChart({ stages }: Props) {
  const sorted = [...stages].sort((a, b) => a.rank - b.rank);
  const height = Math.max(180, sorted.length * 36);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
        <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="stage"
          width={160}
          tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--surface-raised)" }} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {sorted.map((s) => (
            <Cell key={s.stage} fill={BAR_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
