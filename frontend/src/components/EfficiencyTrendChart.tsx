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
import type { EfficiencyTrendPoint, EfficiencyTrendRpAvgPoint } from "../api/types";

type Mode = "absolute" | "change";

interface Props {
  trend: EfficiencyTrendPoint[];
  rpAvg?: EfficiencyTrendRpAvgPoint[];
  mode: Mode;
}

const REPORTING_COLOR = "var(--series-6-green)";
const DRAFTING_COLOR = "var(--series-4-yellow)";
const FULL_MOSAIC_COLOR = "var(--series-5-magenta)";

function fmtMonth(period: string): string {
  const d = new Date(period);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function CombinedTooltip({ active, payload, label, mode }: any) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload as (EfficiencyTrendPoint & Partial<EfficiencyTrendRpAvgPoint>) | undefined;
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "8px 12px",
        fontSize: 12,
        maxWidth: 260,
      }}
    >
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{fmtMonth(label)}</div>
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
            {mode === "change" ? `${(p.value * 100).toFixed(1)}%` : p.value?.toFixed(3)}
          </span>
          <span style={{ color: "var(--text-secondary)" }}>{p.name}</span>
        </div>
      ))}
      {point && (
        <div style={{ color: "var(--text-muted)", marginTop: 6, borderTop: "1px solid var(--border)", paddingTop: 6 }}>
          Reporting: {point.reporting_rad_count ?? 0} rads, {point.reporting_exam_count ?? 0} exams
          <br />
          Drafting: {point.drafting_rad_count ?? 0} rads, {point.drafting_exam_count ?? 0} exams
        </div>
      )}
    </div>
  );
}

export function EfficiencyTrendChart({ trend, rpAvg, mode }: Props) {
  const rpAvgByPeriod = new Map((rpAvg ?? []).map((r) => [r.period, r]));
  const data = trend.map((t) => {
    const rp = rpAvgByPeriod.get(t.period);
    return {
      ...t,
      rp_avg_drafting_tbwu_per_min: rp?.drafting_tbwu_per_min ?? null,
      rp_avg_full_mosaic_tbwu_per_min: rp?.full_mosaic_tbwu_per_min ?? null,
    };
  });

  const reportingKey = mode === "absolute" ? "reporting_tbwu_per_min" : "reporting_pct_change";
  const draftingKey = mode === "absolute" ? "drafting_tbwu_per_min" : "drafting_pct_change";
  const fullMosaicKey = mode === "absolute" ? "full_mosaic_tbwu_per_min" : "full_mosaic_pct_change";

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
        <XAxis
          dataKey="period"
          tickFormatter={fmtMonth}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => (mode === "change" ? `${Math.round(v * 100)}%` : v.toFixed(2))}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip content={<CombinedTooltip mode={mode} />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>} />
        <Line type="monotone" dataKey={reportingKey} name="Reporting (Non-Drafted)" stroke={REPORTING_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
        <Line type="monotone" dataKey={draftingKey} name="Drafting Only" stroke={DRAFTING_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
        <Line type="monotone" dataKey={fullMosaicKey} name="Full Mosaic" stroke={FULL_MOSAIC_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
        {mode === "absolute" && rpAvg && (
          <>
            <Line
              type="monotone"
              dataKey="rp_avg_drafting_tbwu_per_min"
              name="RP Avg, Drafting Only"
              stroke={DRAFTING_COLOR}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="rp_avg_full_mosaic_tbwu_per_min"
              name="RP Avg, Full Mosaic"
              stroke={FULL_MOSAIC_COLOR}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          </>
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
