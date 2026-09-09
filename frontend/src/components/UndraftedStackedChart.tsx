import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, LabelList } from "recharts";
import type { UndraftedCategoryPoint } from "../api/types";

export type UndraftedMetric = "exams" | "tbwu";
export type UndraftedDisplayMode = "percent" | "absolute";

interface Props {
  data: UndraftedCategoryPoint[];
  metric: UndraftedMetric;
  displayMode: UndraftedDisplayMode;
}

const DRAFTED_CATEGORY = "Drafted";

// Fixed order and color, keyed to category_sort_order 1-7 from the view - never cycled,
// never reassigned based on which categories happen to have data for a given week.
const CATEGORY_ORDER: { key: string; color: string }[] = [
  { key: "RAD not enabled - Rad declined", color: "var(--undrafted-rad-declined)" },
  { key: "RAD not enabled - Ops declined", color: "var(--undrafted-ops-declined)" },
  { key: "RAD not enabled - Incomplete process", color: "var(--undrafted-incomplete-process)" },
  { key: "PRACTICE not enabled for model", color: "var(--undrafted-practice-not-enabled)" },
  { key: "DRAFT not available - Exam opened in <5 min", color: "var(--undrafted-opened-under-5min)" },
  { key: "DRAFT not available - Exam opened in >5 min", color: "var(--undrafted-opened-over-5min)" },
  { key: "Exam never opened, not drafted", color: "var(--undrafted-never-opened)" },
];

function formatWeekTick(weekStart: string): string {
  const d = new Date(`${weekStart}T00:00:00`);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// "90000" -> "90k", "1200000" -> "1.2M" - keeps absolute-mode axis ticks/labels short enough
// to fit the many-weeks-wide chart without crowding into neighboring bars.
function formatCompactNumber(value: number): string {
  const abs = Math.abs(value);
  const trim = (s: string) => (s.endsWith(".0") ? s.slice(0, -2) : s);
  if (abs >= 1_000_000) return `${trim((value / 1_000_000).toFixed(1))}M`;
  if (abs >= 1_000) return `${trim((value / 1_000).toFixed(1))}k`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtValue(value: number, displayMode: UndraftedDisplayMode, _metric: UndraftedMetric): string {
  if (displayMode === "percent") return `${(value * 100).toFixed(1)}%`;
  return formatCompactNumber(value);
}

function CustomTooltip({ active, payload, label, displayMode, metric }: any) {
  if (!active || !payload?.length) return null;
  const nonZero = payload.filter((p: any) => p.dataKey !== "totalLabel" && p.value);
  if (!nonZero.length) return null;
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "8px 12px",
        fontSize: 12,
        maxWidth: 320,
      }}
    >
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 4 }}>Week of {label}</div>
      {nonZero.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color, display: "inline-block", flexShrink: 0 }} />
          <span style={{ color: "var(--text-secondary)" }}>
            {p.dataKey}: {fmtValue(p.value, displayMode, metric)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function UndraftedStackedChart({ data, metric, displayMode }: Props) {
  const byWeek = new Map<string, Record<string, number>>();
  for (const row of data) {
    if (!byWeek.has(row.week_start)) byWeek.set(row.week_start, {});
    const bucket = byWeek.get(row.week_start)!;
    const value = metric === "tbwu" ? row.tbwu : row.exam_count;
    bucket[row.category] = (bucket[row.category] ?? 0) + value;
  }

  const rows = Array.from(byWeek.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([weekStart, bucket]) => {
      const weekTotal = Object.values(bucket).reduce((a, b) => a + b, 0);
      const drafted = bucket[DRAFTED_CATEGORY] ?? 0;
      const undraftedTotal = weekTotal - drafted;
      const row: Record<string, number | string> = {
        week_start: weekStart,
        weekTick: formatWeekTick(weekStart),
      };
      for (const cat of CATEGORY_ORDER) {
        const raw = bucket[cat.key] ?? 0;
        row[cat.key] = displayMode === "percent" ? (weekTotal ? raw / weekTotal : 0) : raw;
      }
      row.totalLabel = displayMode === "percent" ? (weekTotal ? undraftedTotal / weekTotal : 0) : undraftedTotal;
      return row;
    });

  const lastCategoryKey = CATEGORY_ORDER[CATEGORY_ORDER.length - 1].key;

  return (
    <div>
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={rows} margin={{ top: 24, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="weekTick"
            interval="preserveStartEnd"
            minTickGap={24}
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={{ stroke: "var(--gridline)" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => (displayMode === "percent" ? `${Math.round(v * 100)}%` : formatCompactNumber(v))}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip displayMode={displayMode} metric={metric} />} cursor={{ fill: "var(--surface-raised)" }} />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
            formatter={(v) => <span style={{ color: "var(--text-secondary)" }}>{v}</span>}
          />
          {CATEGORY_ORDER.map((cat) => (
            <Bar key={cat.key} dataKey={cat.key} stackId="undrafted" fill={cat.color} isAnimationActive={false}>
              {cat.key === lastCategoryKey && (
                <LabelList
                  dataKey="totalLabel"
                  position="top"
                  formatter={(v: number) => fmtValue(v, displayMode, metric)}
                  style={{ fill: "var(--text-primary)", fontSize: 12, fontWeight: 700 }}
                />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 4 }}>
        Weeks run Monday-Sunday; the label under each bar is the Monday it starts on. Only fully-elapsed weeks are
        shown. Total at the top of each bar is {displayMode === "percent" ? "% Undrafted" : "total undrafted"} for
        that week - the "Drafted" category itself is excluded from the stack but included in this total's
        denominator.
      </div>
    </div>
  );
}
