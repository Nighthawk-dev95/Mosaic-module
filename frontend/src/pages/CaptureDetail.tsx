import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { StatTile } from "../components/StatTile";
import { AIHoverCard } from "../components/AIHoverCard";
import { TrendDelta } from "../components/TrendDelta";
import { Badge } from "../components/Badge";
import { CaptureTrendChart } from "../components/CaptureTrendChart";
import { SolutionPin } from "../components/SolutionAxis";
import { TABLE_SECTION_STYLE, TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { CARD_STYLE } from "../styles/glassCard";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import type { CapturePracticeRollup, CaptureRadiologistItem } from "../api/types";

type Granularity = "week" | "month";

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            fontSize: 12,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: value === opt.value ? "var(--surface-raised)" : "transparent",
            color: value === opt.value ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function fmtDate(value: string | null): string {
  if (!value) return "—";
  // A bare YYYY-MM-DD is parsed by Date() as UTC midnight, so west of Greenwich it renders as
  // the day before - a Monday week-start showed up as the preceding Sunday. These are calendar
  // dates with no time component, so build them in local time instead.
  const ymd = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (ymd) {
    return new Date(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3])).toLocaleDateString();
  }
  return new Date(value).toLocaleDateString();
}

// Minimum capturable exams a mover needs in BOTH the current and the prior bucket to appear.
// Without a floor, 22 of 70 practice deltas and 54% of radiologist deltas were computed on
// denominators small enough that a single exam swings the rate by double digits - the lists
// filled up with volumes of 1, 4, 5 and 6. The two numbers differ because a practice reads
// roughly an order of magnitude more than one of its radiologists.
const PRACTICE_MIN_CAPTURABLE = 50;
const RAD_MIN_CAPTURABLE = 10;

const MOVER_LIST_SIZE = 5;

interface TrendPeriodPoint {
  period: string;
  is_partial_period: boolean;
}

interface MoverRow<T> {
  row: T;
  /** Absolute change in the capture rate, as a fraction. 0.0376 = +3.76 points. */
  delta: number;
  /** The rate itself at the comparison period, for context next to the delta. */
  rate: number | null;
  volume: number;
}

interface MoverResult<T> {
  improving: MoverRow<T>[];
  declining: MoverRow<T>[];
  /** The single complete period every row in both lists is measured at. */
  period: string | null;
  /** The in-progress bucket that was held out, if there is one. */
  excludedPartialPeriod: string | null;
  /** How many entities had a usable delta at `period` after the volume floor. */
  qualified: number;
  /** How many had a delta at `period` before the floor - the difference is what we dropped. */
  considered: number;
}

/**
 * Rank entities by how far their capture rate moved between two adjacent calendar buckets.
 *
 * Four rules, each of which is a defect this card used to ship:
 *  1. One period for the whole card - the latest *complete* one. Taking each entity's own max
 *     period mixed an 18-month-old delta in beside this week's under a "Week over Week" label,
 *     and including the in-progress bucket compared one day of volume against seven.
 *  2. Rank on points, never on relative change. `pct_change` divides by the base, so a move
 *     from 0.04% to 0.86% scores +2294% and outranks a genuine +37-point move, and -100% is a
 *     hard floor that dozens of entities tie at. Subtraction has neither property.
 *  3. Both denominators must clear the floor - a big current week against a 3-exam prior week
 *     is just as noisy as the reverse.
 *  4. Split by sign, not by slicing from both ends. `slice(0,5)` and `slice(-5)` overlap when
 *     fewer than ten entities qualify, which put the same practice in both lists.
 */
function pickMovers<T extends TrendPeriodPoint>(
  rows: T[],
  opts: {
    minVolume: number;
    delta: (r: T) => number | null;
    rate: (r: T) => number | null;
    volume: (r: T) => number;
    prevVolume: (r: T) => number;
  }
): MoverResult<T> {
  const empty: MoverResult<T> = {
    improving: [],
    declining: [],
    period: null,
    excludedPartialPeriod: null,
    qualified: 0,
    considered: 0,
  };
  if (rows.length === 0) return empty;

  let latestComplete: string | null = null;
  let latestPartial: string | null = null;
  for (const r of rows) {
    if (r.is_partial_period) {
      if (!latestPartial || r.period > latestPartial) latestPartial = r.period;
    } else if (!latestComplete || r.period > latestComplete) {
      latestComplete = r.period;
    }
  }
  if (!latestComplete) return { ...empty, excludedPartialPeriod: latestPartial };

  const atPeriod = rows.filter((r) => r.period === latestComplete && opts.delta(r) !== null);
  const qualified: MoverRow<T>[] = [];
  for (const r of atPeriod) {
    if (opts.volume(r) < opts.minVolume) continue;
    if (opts.prevVolume(r) < opts.minVolume) continue;
    qualified.push({ row: r, delta: opts.delta(r) as number, rate: opts.rate(r), volume: opts.volume(r) });
  }
  qualified.sort((a, b) => b.delta - a.delta);

  return {
    improving: qualified.filter((m) => m.delta > 0).slice(0, MOVER_LIST_SIZE),
    declining: qualified
      .filter((m) => m.delta < 0)
      .slice(-MOVER_LIST_SIZE)
      .reverse(),
    period: latestComplete,
    excludedPartialPeriod: latestPartial,
    qualified: qualified.length,
    considered: atPeriod.length,
  };
}

function MoverList<T>({
  title,
  movers,
  label,
}: {
  title: string;
  movers: MoverRow<T>[];
  label: (row: T) => string;
}) {
  return (
    <div style={{ flex: "1 1 300px" }}>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>{title}</div>
      {movers.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--text-muted)", padding: "4px 0" }}>
          None above the volume floor.
        </div>
      )}
      {movers.map((m, i) => (
        <div
          key={i}
          style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "4px 0", fontSize: 13 }}
        >
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {label(m.row)}
          </span>
          <span style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <span style={{ color: "var(--text-muted)" }}>{fmtPct(m.rate)}</span>
            <TrendDelta value={m.delta} unit="pp" />
          </span>
        </div>
      ))}
    </div>
  );
}

export function CaptureDetail() {
  const [granularity, setGranularity] = useState<Granularity>("week");
  const filters = useFilters();

  const overview = useFetch(() => mosaicApi.getCaptureOverview(), []);
  const byPractice = useFetch(() => mosaicApi.getCaptureByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCaptureByRadiologist(), []);
  const utilTrendByPractice = useFetch(() => mosaicApi.getCaptureTrendUtilizationByPractice(granularity), [granularity]);
  const utilTrendByRadiologist = useFetch(
    () => mosaicApi.getCaptureTrendUtilizationByRadiologist(granularity),
    [granularity]
  );
  const effTrendByPractice = useFetch(() => mosaicApi.getCaptureTrendEfficiencyByPractice(granularity), [granularity]);

  const anyError = overview.error || byPractice.error || byRadiologist.error || utilTrendByPractice.error || effTrendByPractice.error;

  const practices = useMemo(() => {
    if (!byPractice.data) return [];
    return Array.from(new Set(byPractice.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [byPractice.data]);

  const filteredByPractice = useMemo(
    () => (byPractice.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [byPractice.data, filters]
  );
  const filteredByRadiologist = useMemo(
    () =>
      (byRadiologist.data ?? []).filter(
        (r) =>
          matchesPractice(filters, r.practice) &&
          matchesRadiologistSearch(filters, r.radiologist_name, r.npi) &&
          (!filters.captureEnabledOnly || r.capture_enabled === true)
      ),
    [byRadiologist.data, filters]
  );

  const selectedPracticeUtilTrend = useMemo(
    () => (filters.practice ? (utilTrendByPractice.data ?? []).filter((r) => r.practice === filters.practice) : []),
    [utilTrendByPractice.data, filters.practice]
  );
  const selectedPracticeEffTrend = useMemo(
    () => (filters.practice ? (effTrendByPractice.data ?? []).filter((r) => r.practice === filters.practice) : []),
    [effTrendByPractice.data, filters.practice]
  );

  const topPracticeMoves = useMemo(() => {
    const rows = utilTrendByPractice.data ?? [];
    return pickMovers(rows.filter((r) => !!r.practice), {
      minVolume: PRACTICE_MIN_CAPTURABLE,
      delta: (r) => (filters.captureEnabledOnly ? r.pp_change_enabled : r.pp_change_all),
      rate: (r) => (filters.captureEnabledOnly ? r.pct_captured_enabled : r.pct_captured_all),
      volume: (r) => (filters.captureEnabledOnly ? r.capturable_exams_enabled : r.capturable_exams_all),
      prevVolume: (r) =>
        filters.captureEnabledOnly ? r.prev_capturable_exams_enabled : r.prev_capturable_exams_all,
    });
  }, [utilTrendByPractice.data, filters.captureEnabledOnly]);

  const topRadiologistMoves = useMemo(() => {
    const rows = utilTrendByRadiologist.data ?? [];
    return pickMovers(rows, {
      minVolume: RAD_MIN_CAPTURABLE,
      delta: (r) => r.pp_change,
      rate: (r) => r.pct_captured,
      volume: (r) => r.capturable_exams,
      prevVolume: (r) => r.prev_capturable_exams,
    });
  }, [utilTrendByRadiologist.data]);

  // The card's own footnote. Everything it states is a rule the ranking actually applied, so a
  // reader can tell at a glance why their practice is absent - partial period, volume floor, or
  // no prior bucket at all - instead of assuming the number is simply wrong.
  const moverCaption = useMemo(() => {
    const unit = granularity === "week" ? "week" : "month";
    const period = topPracticeMoves.period ?? topRadiologistMoves.period;
    if (!period) {
      return `No complete ${unit} available to compare yet.`;
    }
    const parts = [
      `Change in capture rate, in percentage points, for the ${unit} of ${fmtDate(period)} against the ${unit} before it.`,
    ];
    const partial = topPracticeMoves.excludedPartialPeriod ?? topRadiologistMoves.excludedPartialPeriod;
    if (partial && partial > period) {
      parts.push(`The ${unit} of ${fmtDate(partial)} is still in progress and is excluded.`);
    }
    parts.push(
      `Requires at least ${PRACTICE_MIN_CAPTURABLE} capturable exams in both ${unit}s for a practice ` +
        `(${topPracticeMoves.qualified} of ${topPracticeMoves.considered} qualify) and ${RAD_MIN_CAPTURABLE} for a radiologist ` +
        `(${topRadiologistMoves.qualified} of ${topRadiologistMoves.considered}).`
    );
    return parts.join(" ");
  }, [granularity, topPracticeMoves, topRadiologistMoves]);

  const PRACTICE_COLUMNS: DataTableColumn<CapturePracticeRollup>[] = [
    {
      key: "practice",
      label: "Practice",
      render: (r) => (
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {r.practice}
          {r.opted_out && <Badge label="Opted Out" color="var(--status-critical)" />}
        </span>
      ),
    },
    {
      key: "pct_captured_all",
      label: "Utilization Rate",
      render: (r) => fmtPct(filters.captureEnabledOnly ? r.pct_captured_enabled : r.pct_captured_all),
    },
    { key: "rads_live_on_capture", label: "Rads Live on Capture" },
    { key: "rads_capture_enabled", label: "Rads Capture Enabled" },
    { key: "enablement_date", label: "Enablement Date", render: (r) => fmtDate(r.enablement_date) },
    {
      key: "pct_change_since_enablement",
      label: "Δ Since Enablement",
      render: (r) => <TrendDelta value={r.pct_change_since_enablement} />,
    },
  ];

  const RAD_COLUMNS: DataTableColumn<CaptureRadiologistItem>[] = [
    { key: "radiologist_name", label: "Radiologist" },
    { key: "practice", label: "Practice" },
    { key: "capture_enabled", label: "Capture Enabled", render: (r) => (r.capture_enabled ? "Yes" : "No") },
    { key: "pct_captured", label: "Utilization Rate", render: (r) => fmtPct(r.pct_captured) },
  ];

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Capture</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Mosaic Capture = US + Dexa combined. Utilization rate = captured ÷ capturable exams. Efficiency rate reuses the
          existing "Capture Only" TBWU/min mode from the Efficiency page.
        </div>
        <SolutionPin
          solution="capture"
          elsewhere="Efficiency carries all four solutions on one axis, and Mosaic Pulse shows the three side by side"
          style={{ marginTop: 8 }}
        />
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <ToggleGroup
          options={[
            { value: "week" as Granularity, label: "Week over Week" },
            { value: "month" as Granularity, label: "Month over Month" },
          ]}
          value={granularity}
          onChange={setGranularity}
        />
      </div>

      <FilterBar practices={practices} showCaptureEnabled showLocal={false} showMonth={false} />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel="Enterprise-wide"
          metricLabel="Overall Capture utilization rate"
          value={
            overview.data
              ? fmtPct(filters.captureEnabledOnly ? overview.data.pct_captured_enabled : overview.data.pct_captured_all)
              : "…"
          }
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="Overall Capture Utilization Rate"
            value={
              overview.data
                ? fmtPct(filters.captureEnabledOnly ? overview.data.pct_captured_enabled : overview.data.pct_captured_all)
                : "…"
            }
            accent="var(--domain-capture)"
          />
        </AIHoverCard>
        <AIHoverCard
          feature="efficiency_metric"
          entityLabel="Enterprise-wide"
          metricLabel="Overall Capture efficiency rate"
          value={overview.data?.capture_mosaic_tbwu_per_min != null ? `${overview.data.capture_mosaic_tbwu_per_min.toFixed(3)} TBWU/min` : "…"}
          extra={
            overview.data?.capture_pct_change_vs_baseline != null
              ? { pct_change_vs_baseline: `${(overview.data.capture_pct_change_vs_baseline * 100).toFixed(1)}%` }
              : undefined
          }
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="Overall Capture Efficiency Rate"
            value={overview.data?.capture_mosaic_tbwu_per_min != null ? `${overview.data.capture_mosaic_tbwu_per_min.toFixed(3)} TBWU/min` : "…"}
            accent="var(--domain-capture)"
            sublabel={
              overview.data?.capture_pct_change_vs_baseline != null
                ? `${(overview.data.capture_pct_change_vs_baseline * 100).toFixed(1)}% vs baseline`
                : undefined
            }
          />
        </AIHoverCard>
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Utilization Trend {filters.practice ? `— ${filters.practice}` : ""}
        </div>
        {filters.practice ? (
          <CaptureTrendChart
            data={selectedPracticeUtilTrend}
            granularity={granularity}
            percent
            lines={[
              { key: "pct_captured_all", name: "All Rads", color: "var(--series-6-green)" },
              { key: "pct_captured_enabled", name: "Enabled Rads", color: "var(--domain-capture)" },
            ]}
          />
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
            Select a practice above to see its utilization trend.
          </div>
        )}
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Efficiency Trend {filters.practice ? `— ${filters.practice}` : ""}
        </div>
        {filters.practice ? (
          <CaptureTrendChart
            data={selectedPracticeEffTrend}
            granularity={granularity}
            lines={[
              { key: "capture_tbwu_per_min", name: "Mosaic TBWU/min", color: "var(--series-6-green)" },
              { key: "capture_baseline_tbwu_per_min", name: "Baseline TBWU/min", color: "var(--domain-capture)", dashed: true },
            ]}
          />
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
            Select a practice above to see its efficiency trend.
          </div>
        )}
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Improvement / Decline Highlights ({granularity === "week" ? "Week over Week" : "Month over Month"})
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12, lineHeight: 1.5 }}>
          {moverCaption}
        </div>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          <MoverList
            title="Top Improving Practices"
            movers={topPracticeMoves.improving}
            label={(r) => r.practice ?? "Unknown"}
          />
          <MoverList
            title="Top Declining Practices"
            movers={topPracticeMoves.declining}
            label={(r) => r.practice ?? "Unknown"}
          />
          <MoverList
            title="Top Improving Radiologists"
            movers={topRadiologistMoves.improving}
            label={(r) => r.radiologist_name ?? String(r.npi)}
          />
          <MoverList
            title="Top Declining Radiologists"
            movers={topRadiologistMoves.declining}
            label={(r) => r.radiologist_name ?? String(r.npi)}
          />
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Practice
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byPractice.data && (
            <DataTable columns={PRACTICE_COLUMNS} rows={filteredByPractice} rowKey={(r) => r.practice ?? "unknown"} />
          )}
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byRadiologist.data && (
            <DataTable columns={RAD_COLUMNS} rows={filteredByRadiologist} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>
    </div>
  );
}
