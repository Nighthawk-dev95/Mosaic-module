import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { CARD_STYLE } from "../styles/glassCard";
import { FilterBar } from "../components/FilterBar";
import { Badge } from "../components/Badge";
import { NotesButton } from "../components/NotesButton";
import { AIHoverCard } from "../components/AIHoverCard";
import { Drawer } from "../components/Drawer";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import { getLocalRegion } from "../utils/localRegion";
import { MIN_READ_TIME_COVERAGE, readTimeCoverageBadge } from "../utils/coverage";
import type {
  BaselineProxyDetail,
  CapacityBaselineScorecard,
  CapacityPracticeRollup,
  CapacityRadiologistItem,
} from "../api/types";

function fmtNum(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

/** SHARED_COLUMNS serves both the practice and the radiologist table; each names its rows differently. */
function rowLabel(r: CapacityPracticeRollup | CapacityRadiologistItem): string {
  if ("radiologist_name" in r && r.radiologist_name) return r.radiologist_name;
  return r.practice ?? "this row";
}

function fmtShiftNames(value: string | null | undefined): ReactNode {
  if (!value) return "—";
  const names = value.split(", ");
  if (names.length <= 3) return value;
  return (
    <span title={value}>
      {names.slice(0, 3).join(", ")} +{names.length - 3} more
    </span>
  );
}

const SHARED_COLUMNS = <T extends CapacityPracticeRollup | CapacityRadiologistItem>(): DataTableColumn<T>[] => [
  { key: "total_shifts", label: "Shifts" },
  { key: "total_hours", label: "Hours", render: (r) => fmtNum(r.total_hours) },
  { key: "capacity_rvu", label: "On-Shift Capacity (RVU)", render: (r) => fmtNum(r.capacity_rvu) },
  { key: "capacity_rvu_per_hour", label: "On-Shift Capacity (RVU/hr)", render: (r) => fmtNum(r.capacity_rvu_per_hour, 2) },
  {
    key: "utilization_rvu_pct",
    label: "On-Shift Utilization",
    // A "-" here is a deliberate suppression by the backend, not missing data - see
    // _MIN_READ_TIME_COVERAGE in mosaic_service.py. Say so on hover rather than letting
    // the user read it as "we don't have this yet".
    render: (r) =>
      r.utilization_rvu_pct != null ? (
        fmtPct(r.utilization_rvu_pct)
      ) : (
        <AIHoverCard
          feature="capacity_coverage"
          entityLabel={rowLabel(r)}
          metricLabel="On-Shift Utilization (suppressed)"
          value="—"
          extra={{
            read_time_coverage: fmtPct(r.pct_exams_with_valid_read_time),
            threshold: `${(MIN_READ_TIME_COVERAGE * 100).toFixed(0)}%`,
            note:
              "Not missing - withheld. Read-time coverage for this slice is below the floor, and utilization's numerator counts only exams with a dictation timestamp while its denominator counts the whole scheduled shift. A value here would be understated by roughly the coverage fraction, so it is suppressed rather than shown with a caveat.",
          }}
        >
          —
        </AIHoverCard>
      ),
  },
  { key: "efficiency_rpwu_per_min", label: "On-Shift Efficiency (RPWU/min)", render: (r) => fmtNum(r.efficiency_rpwu_per_min, 3) },
  {
    key: "pct_exams_with_valid_read_time",
    label: "Read-Time Coverage",
    render: (r) => readTimeCoverageBadge(r.pct_exams_with_valid_read_time, rowLabel(r), r.pct_shifts_rpce_source),
  },
  {
    key: "pct_shifts_rpce_source",
    label: "% Cases from RPCE",
    // Computed and cached since the capacity CTE was written; never rendered until now.
    // Distinct from read-time coverage - a slice can be fully RPCE-sourced and still have
    // no usable dictation timestamps - so the two travel as separate columns, not one score.
    render: (r) => fmtPct(r.pct_shifts_rpce_source),
  },
  { key: "pct_mosaic", label: "% Mosaic", render: (r) => fmtPct(r.pct_mosaic) },
  { key: "pct_drafting", label: "% Mosaic Drafting", render: (r) => fmtPct(r.pct_drafting) },
  { key: "avg_rvu_per_case", label: "Avg RVU / Case", render: (r) => fmtNum(r.avg_rvu_per_case, 2) },
  { key: "on_shift_cases", label: "Cases" },
  { key: "ct_cases", label: "CT" },
  { key: "xr_cases", label: "XR" },
  { key: "us_cases", label: "US" },
  { key: "mr_cases", label: "MR" },
  { key: "ir_cases", label: "IR" },
];

function practiceColumns(onSelectPractice: (practice: string) => void): DataTableColumn<CapacityPracticeRollup>[] {
  return [
    {
      key: "practice",
      label: "Practice",
      render: (r) =>
        r.practice ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span
              onClick={() => onSelectPractice(r.practice!)}
              style={{ cursor: "pointer", textDecoration: "underline", textDecorationStyle: "dotted" }}
              title="Click to drill into this practice"
            >
              {r.practice}
            </span>
            <NotesButton entityType="practice" entityKey={r.practice} />
          </span>
        ) : (
          "—"
        ),
    },
    ...SHARED_COLUMNS<CapacityPracticeRollup>(),
  ];
}

const RAD_COLUMNS: DataTableColumn<CapacityRadiologistItem>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "practice", label: "Practice" },
  { key: "shift_names", label: "Shift Names", render: (r) => fmtShiftNames(r.shift_names) },
  ...SHARED_COLUMNS<CapacityRadiologistItem>(),
];

// Coverage badge: green when most shifts got a real (Exact) baseline, yellow when Proxy-
// heavy, red when the practice has too little baseline coverage to trust its numbers -
// mirrors the _MIN_RELIABLE_BASELINE_TBWU_PER_HOUR floor in cache_service.py, which is why
// additional_capacity_pct comes back null for the "red" case instead of a distorted number.
function coverageBadge(r: CapacityBaselineScorecard): ReactNode {
  const exact = r.pct_exact ?? 0;
  const noBaseline = r.pct_no_baseline ?? 0;
  const label = noBaseline >= 70 ? `${noBaseline.toFixed(0)}% no baseline` : exact >= 50 ? `${exact.toFixed(0)}% exact` : `${(r.pct_proxy ?? 0).toFixed(0)}% proxy`;
  const color = noBaseline >= 70 ? "var(--status-critical)" : exact >= 50 ? "var(--status-good)" : "var(--status-warning)";
  return (
    <AIHoverCard
      feature="capacity_coverage"
      entityLabel={r.practice ?? "this practice"}
      metricLabel="Baseline coverage"
      value={label}
      extra={{ pct_exact: String(exact), pct_proxy: String(r.pct_proxy ?? 0), pct_no_baseline: String(noBaseline) }}
    >
      <Badge label={label} color={color} />
    </AIHoverCard>
  );
}

const BASELINE_SCORECARD_COLUMNS: DataTableColumn<CapacityBaselineScorecard>[] = [
  { key: "practice", label: "Practice" },
  { key: "total_shifts", label: "Shifts" },
  {
    key: "baseline_capacity_tbwu_per_hour",
    label: "Baseline Capacity (TBWU/hr)",
    render: (r) =>
      r.baseline_capacity_tbwu_per_hour == null ? (
        "—"
      ) : (
        <AIHoverCard
          feature="capacity_figure"
          entityLabel={r.practice ?? "this practice"}
          metricLabel="Baseline capacity (TBWU/hr)"
          value={fmtNum(r.baseline_capacity_tbwu_per_hour, 2)}
        >
          {fmtNum(r.baseline_capacity_tbwu_per_hour, 2)}
        </AIHoverCard>
      ),
  },
  {
    key: "avg_capacity_tbwu_per_hour",
    label: "Mosaic Capacity (TBWU/hr)",
    render: (r) =>
      r.avg_capacity_tbwu_per_hour == null ? (
        "—"
      ) : (
        <AIHoverCard
          feature="capacity_figure"
          entityLabel={r.practice ?? "this practice"}
          metricLabel="Current Mosaic capacity (TBWU/hr)"
          value={fmtNum(r.avg_capacity_tbwu_per_hour, 2)}
          extra={{ baseline_capacity: fmtNum(r.baseline_capacity_tbwu_per_hour, 2) }}
        >
          {fmtNum(r.avg_capacity_tbwu_per_hour, 2)}
        </AIHoverCard>
      ),
  },
  {
    key: "additional_capacity_pct",
    label: "Additional Capacity %",
    render: (r) =>
      r.additional_capacity_pct === null ? (
        "—"
      ) : (
        <AIHoverCard
          feature="capacity_additional_pct"
          entityLabel={r.practice ?? "this practice"}
          metricLabel="Additional capacity vs. baseline"
          value={fmtPct(r.additional_capacity_pct / 100)}
        >
          {fmtPct(r.additional_capacity_pct / 100)}
        </AIHoverCard>
      ),
  },
  { key: "pct_exact", label: "Baseline Coverage", render: (r) => coverageBadge(r) },
];

const PROXY_DETAIL_COLUMNS: DataTableColumn<BaselineProxyDetail>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "target_shift", label: "Shift Without Its Own Baseline" },
  { key: "proxy_shift", label: "Matched Proxy Shift" },
  { key: "total_match_score", label: "Match Score", render: (r) => fmtNum(r.total_match_score, 2) },
  { key: "score_subspecialty", label: "Subspecialty", render: (r) => fmtNum(r.score_subspecialty, 2) },
  { key: "score_modality", label: "Modality", render: (r) => fmtNum(r.score_modality, 2) },
  { key: "score_tbwu", label: "TBWU", render: (r) => fmtNum(r.score_tbwu, 2) },
  { key: "score_shift_duration", label: "Duration", render: (r) => fmtNum(r.score_shift_duration, 2) },
  { key: "score_location", label: "Location", render: (r) => fmtNum(r.score_location, 2) },
  { key: "score_weekday_weekend", label: "Weekday/Weekend", render: (r) => fmtNum(r.score_weekday_weekend, 2) },
];

export function CapacityDetail() {
  const byPractice = useFetch(() => mosaicApi.getCapacityByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCapacityByRadiologist(), []);
  const baselineScorecard = useFetch(() => mosaicApi.getCapacityBaselineScorecard(), []);
  const filters = useFilters();
  const proxyDetail = useFetch(() => mosaicApi.getBaselineProxyDetail(filters.practice || undefined), [filters.practice]);
  const anyError = byPractice.error || byRadiologist.error || baselineScorecard.error || proxyDetail.error;

  // Drill-down: clicking a practice name in "By Practice" opens this instead of requiring a
  // separate scroll-and-filter through "By Radiologist"/"How Proxies Are Derived" below.
  const [drilldownPractice, setDrilldownPractice] = useState<string | null>(null);
  const drilldownRadiologists = useMemo(
    () => (byRadiologist.data ?? []).filter((r) => r.practice === drilldownPractice),
    [byRadiologist.data, drilldownPractice]
  );
  const drilldownProxy = useFetch(
    () => (drilldownPractice ? mosaicApi.getBaselineProxyDetail(drilldownPractice) : Promise.resolve([])),
    [drilldownPractice]
  );
  const practiceColumnsMemo = useMemo(() => practiceColumns(setDrilldownPractice), []);

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
          (!filters.local || getLocalRegion(r.team) === filters.local) &&
          matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
      ),
    [byRadiologist.data, filters]
  );
  const filteredBaselineScorecard = useMemo(
    () => (baselineScorecard.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [baselineScorecard.data, filters]
  );

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Capacity</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          On-shift capacity, efficiency, utilization, Mosaic/drafting mix, and case-mix, rolled up by practice and by radiologist.
        </div>
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      <FilterBar practices={practices} showMonth={false} />

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Capacity Scorecard - Baseline vs. Mosaic
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
          Capacity = TBWU/hour scheduled. Baseline Capacity comes from each rad's own pre-Mosaic history per shift type
          (edw_dev.bipa_analytics.stg_mosaic_baseline_master); Additional Capacity % is only shown when a practice has
          decent baseline coverage - low-coverage practices show "—" instead of a distorted number.
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {baselineScorecard.data && (
            <DataTable
              columns={BASELINE_SCORECARD_COLUMNS}
              rows={filteredBaselineScorecard}
              rowKey={(r) => r.practice ?? "unknown"}
            />
          )}
        </div>
      </div>

      <div style={CARD_STYLE}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>
            By Practice
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Click a practice name to drill in</div>
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byPractice.data && (
            <DataTable columns={practiceColumnsMemo} rows={filteredByPractice} rowKey={(r) => r.practice ?? "unknown"} />
          )}
        </div>
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byRadiologist.data && (
            <DataTable columns={RAD_COLUMNS} rows={filteredByRadiologist} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
          How Proxies Are Derived{filters.practice ? ` - ${filters.practice}` : ""}
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
          Shifts with no baseline history of their own borrow one from the closest-matching shift elsewhere, scored across
          subspecialty, modality, TBWU, duration, location, and weekday/weekend. Use the practice filter above to narrow this
          down.
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {proxyDetail.data &&
            (proxyDetail.data.length === 0 ? (
              <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No proxy matches for this filter.</div>
            ) : (
              <DataTable
                columns={PROXY_DETAIL_COLUMNS}
                rows={proxyDetail.data}
                rowKey={(r) => `${r.npi}-${r.target_shift}`}
              />
            ))}
        </div>
      </div>

      <Drawer
        open={drilldownPractice !== null}
        onClose={() => setDrilldownPractice(null)}
        title={drilldownPractice ?? undefined}
      >
        {drilldownPractice && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Radiologists
              </div>
              {drilldownRadiologists.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No radiologists found for this practice.</div>
              ) : (
                <DataTable columns={RAD_COLUMNS} rows={drilldownRadiologists} rowKey={(r) => r.npi} />
              )}
            </div>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
                How Proxies Are Derived
              </div>
              {drilldownProxy.data && drilldownProxy.data.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No proxy matches for this practice.</div>
              ) : (
                drilldownProxy.data && (
                  <DataTable
                    columns={PROXY_DETAIL_COLUMNS}
                    rows={drilldownProxy.data}
                    rowKey={(r) => `${r.npi}-${r.target_shift}`}
                  />
                )
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
