import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, LabelList } from "recharts";
import type { UndraftedCategoryPoint } from "../api/types";

export type UndraftedMetric = "exams" | "tbwu";
export type UndraftedDisplayMode = "percent" | "absolute";

interface Props {
  data: UndraftedCategoryPoint[];
  metric: UndraftedMetric;
  displayMode: UndraftedDisplayMode;
}

export const DRAFTED_CATEGORY = "Drafted";

/**
 * Exams the radiologist never read on Mosaic at all. 104.9M of the 123M rows in the cache -
 * 85% of everything - and not a drafting outcome: no draft was possible because Mosaic was
 * not the reporting system for that exam. It is excluded from both the stack and the
 * denominator. Leaving it in the denominator (which is what this chart used to do, per the
 * backend's own docstring) pins every week near 93% undrafted and the bar stops moving when
 * drafting improves, because the ratio is really measuring Mosaic *reporting* adoption.
 */
export const NOT_ON_MOSAIC_CATEGORY = "Not Read on Mosaic";

/**
 * Fixed order and color, keyed to category_sort_order 1-4 exactly as
 * `mosaic_service.get_undrafted_analysis` emits them - never cycled, never reassigned from
 * whichever categories happen to have data in a given week.
 *
 * These strings are a contract with the SQL CASE expression in mosaic_service.py. They
 * previously named a retired seven-category taxonomy, so every `bucket[cat.key]` lookup
 * missed, every segment was zero, and the chart rendered an empty axis over live data -
 * which looks like "no leakage" rather than like a bug. If the CASE expression changes,
 * these change in the same commit.
 *
 * Ordered by owner: the first two are convertible by whoever works the Drafting worklist
 * below this chart, the last two are not and belong to deployment and model coverage.
 */
export const CATEGORY_ORDER: { key: string; color: string }[] = [
  { key: "Draftable - Rad Not Enrolled", color: "var(--undrafted-rad-not-enrolled)" },
  { key: "Draftable - Not Drafted (Workflow)", color: "var(--undrafted-workflow)" },
  { key: "Practice Not Enabled for Model", color: "var(--undrafted-practice-not-enabled)" },
  { key: "Procedure Not Covered", color: "var(--undrafted-procedure-not-covered)" },
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

  const allRows = Array.from(byWeek.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([weekStart, bucket]) => {
      // The denominator is every exam read on Mosaic that week: the four plotted reasons
      // plus Drafted, which is the success and so is in the denominator but never its own
      // segment. `Not Read on Mosaic` is excluded - see NOT_ON_MOSAIC_CATEGORY.
      const drafted = bucket[DRAFTED_CATEGORY] ?? 0;
      const undraftedTotal = CATEGORY_ORDER.reduce((sum, cat) => sum + (bucket[cat.key] ?? 0), 0);
      const mosaicRead = drafted + undraftedTotal;
      const row: Record<string, number | string> = {
        week_start: weekStart,
        weekTick: formatWeekTick(weekStart),
        mosaicRead,
      };
      for (const cat of CATEGORY_ORDER) {
        const raw = bucket[cat.key] ?? 0;
        row[cat.key] = displayMode === "percent" ? (mosaicRead ? raw / mosaicRead : 0) : raw;
      }
      row.totalLabel = displayMode === "percent" ? (mosaicRead ? undraftedTotal / mosaicRead : 0) : undraftedTotal;
      return row;
    });

  // Weeks where nothing was read on Mosaic at all are not drafting outcomes - they are weeks
  // before the slice went live. Plotted, they draw a zero-height bar carrying a "0.0%" label,
  // which reads as a *perfect* week rather than an absent one, and they stretch the x-axis
  // across a dead zone (the enterprise series starts in Jan 2024 but the first real Mosaic
  // volume is in Mar 2024).
  const rows = allRows.filter((r) => (r.mosaicRead as number) > 0);

  // One label per bar is legible at ~16 weeks and an unreadable white smear at 147. Thin to a
  // fixed budget and always keep the most recent week, which is the one being discussed.
  const LABEL_BUDGET = 16;
  const labelStride = Math.max(1, Math.ceil(rows.length / LABEL_BUDGET));
  for (let i = 0; i < rows.length; i++) {
    const keep = i % labelStride === 0 || i === rows.length - 1;
    rows[i].totalLabelText = keep ? fmtValue(rows[i].totalLabel as number, displayMode, metric) : "";
  }

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
            // Pinned in percent mode. Left to auto-scale, a week with no plotted volume
            // lets recharts pick whatever domain it likes - which is how an all-zero stack
            // came to be drawn under a 400% axis.
            domain={displayMode === "percent" ? [0, 1] : [0, "auto"]}
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
                  // Pre-formatted and pre-thinned above - suppressed bars carry "".
                  dataKey="totalLabelText"
                  position="top"
                  style={{ fill: "var(--text-primary)", fontSize: 12, fontWeight: 700 }}
                />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 4 }}>
        Weeks run Monday-Sunday; the label under each bar is the Monday it starts on. Only fully-elapsed weeks with at
        least one exam read on Mosaic are shown. The label above a bar is{" "}
        {displayMode === "percent" ? "% not drafted" : "total not drafted"} for that week — shown on every bar when the
        range is short, and thinned to roughly {LABEL_BUDGET} evenly-spaced weeks (always including the most recent)
        when it isn't. Hover any bar for its exact split. Denominator is every exam{" "}
        <strong>read on Mosaic</strong> that week: the four reasons above plus
        "Drafted", which is in the denominator but is not drawn as its own segment. Exams never read on Mosaic are
        excluded entirely - no draft was possible, so they measure reporting adoption rather than drafting. The first
        two reasons are the ones the worklist below can convert; the last two belong to deployment and model coverage,
        so the worklist reports them but does not rank on them.
      </div>
    </div>
  );
}
