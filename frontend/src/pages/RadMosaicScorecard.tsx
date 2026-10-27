import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { useFilters } from "../context/FilterContext";
import { FilterBar } from "../components/FilterBar";
import { AIHoverCard } from "../components/AIHoverCard";
import { Drawer } from "../components/Drawer";
import { StatTile } from "../components/StatTile";
import { DataTable, fmtPct, type DataTableColumn } from "../components/DataTable";
import { readTimeCoverageBadge } from "../utils/coverage";
import { CARD_STYLE } from "../styles/glassCard";
import type { CapacityRadiologistItem, CapacityPracticeRollup } from "../api/types";

// Replaces the old Top-N-shift-window Scorecard tab. Built entirely on the existing
// /capacity/by-radiologist + /capacity/by-practice endpoints (zero new backend work) - adds one
// thing PCC's own productivity scorecards do that the old page didn't: every figure is shown
// next to its practice, so "am I ahead or behind my peers" is answered directly rather than
// left to the reader to infer from a bare number.
//
// "Practice rate", not "practice average". /capacity/by-practice runs the same
// _CAPACITY_MEASURES_SQL as the per-radiologist query, just GROUP BY localpractice, so its
// rate columns are try_divide(SUM(num), SUM(den)) over the practice's shifts - a recomputed
// rate, never a mean of per-radiologist rates. That is Fix 3, and the registry states it as a
// caveat on the metrics this page renders ("Never average across groups - recompute from
// numerator/denominator"). Calling the result an average on screen would contradict the
// methodology the same page's hover cards explain.

interface MetricDef {
  key: "efficiency_rpwu_per_min" | "capacity_rpwu" | "pct_mosaic" | "pct_drafting";
  label: string;
  format: (v: number | null) => string;
  feature: string;
  // "rate" = num/den, so the radiologist's figure and the practice's are the same kind of
  // number and the gap between them means something. "total" = an additive SUM, where the
  // practice figure is the practice's entire output and a difference is meaningless - see
  // capacity_rpwu below.
  kind: "rate" | "total";
  // Totals only. The field - present on both the radiologist row and the practice rollup -
  // to divide by so the two become comparable. Share-of-practice was the other option and it
  // is nearly useless here: a rad with 14 of RAF's 53,356 shifts renders "0.0% of practice",
  // which says more about how many radiologists RAF has than about this one. Per shift, the
  // same rad is 12.2 against the practice's 53.6 - a real answer to "ahead or behind".
  normalizeBy?: "total_shifts";
  // Stored 0-1 and rendered through fmtPct. A *difference* between two such values is in
  // percentage POINTS: fmtPct would print a 0.05 gap as "+5.0%", which reads as a relative
  // 5% lift when it is a 5 pp gap. Flagged metrics render "pp" instead.
  ratio?: boolean;
  // A gap smaller than this, in the metric's own units, is not a finding however large it is
  // *relatively*. AMBER_BAND alone cannot know that: against a practice % Mosaic of 0.004, a
  // radiologist at 0 is -100% relative and went out critical red - while the text beside it
  // read "-0.0 pp". 54 cells rendered that exact contradiction and another 44 were red on a
  // sub-0.5 pp gap, because 66-89 of the ~490 comparisons per ratio metric sit against a
  // practice rate under 1%. A relative band needs a reference with magnitude; this is the
  // floor for when there isn't one.
  noiseFloor?: number;
  // Normalised totals only: the smallest denominator that supports a verdict. The noise is
  // measurable in the live data - binning the 495 capacity comparisons by shift count, the
  // median |gap vs practice| runs 80.5% at 1-2 shifts, 82.0% at 3-4, 73.0% at 5-9, 62.4% at
  // 10-19 and 31.5% at 20+. Radiologists do not get twice as good at 20 shifts; that curve is
  // the sample thinning. 10 is where it stops being extreme (p90 drops from ~300% to ~100%),
  // and it leaves 34 of 495 rows uncoloured rather than 53 at a threshold of 20.
  minSample?: number;
}

const METRICS: MetricDef[] = [
  { key: "efficiency_rpwu_per_min", label: "Efficiency (RPWU/min)", format: (v) => (v === null ? "—" : v.toFixed(3)), feature: "efficiency_metric", kind: "rate" },
  // kind: "total", and the reason matters. capacity_rpwu is registered as SUM(shift_TBWU) -
  // the practice row is the practice's whole on-shift output (RAF: 2,858,482 RPWU) while a
  // radiologist's is their own (171 - 9,062). Subtracting the two rendered a seven-figure
  // negative on every row and painted every radiologist in every practice red. Normalising
  // both sides per shift is what makes the comparison legitimate.
  { key: "capacity_rpwu", label: "Capacity (RPWU)", format: (v) => (v === null ? "—" : v.toFixed(1)), feature: "capacity_figure", kind: "total", normalizeBy: "total_shifts", minSample: 10 },
  // 0.005 = half a percentage point, which is also the smallest gap fmtDelta can print
  // distinguishably ("-0.5 pp"); anything under it rounds to "-0.0 pp" or close to it.
  { key: "pct_mosaic", label: "% Mosaic", format: fmtPct, feature: "adoption_rollout", kind: "rate", ratio: true, noiseFloor: 0.005 },
  { key: "pct_drafting", label: "% Drafting", format: fmtPct, feature: "adoption_rollout", kind: "rate", ratio: true, noiseFloor: 0.005 },
];

// Within 5% below the practice rate is amber rather than red, so parity isn't a cliff edge.
// Note what this does NOT do: it is a purely *relative* band, so on its own it says nothing
// about whether the gap is large enough to matter (noiseFloor) or rests on enough data to
// mean anything (minSample). All three run before a cell is painted.
const AMBER_BAND = 0.05;

// The one place that decides whether a radiologist figure and a practice figure may be
// compared at all, and on what footing. Returns null when they may not be - the caller then
// renders no comparison rather than a number it cannot defend.
interface Comparison {
  value: number;
  reference: number;
  // Set when both sides were divided to make them comparable, e.g. "per shift". The caller
  // must print it: the headline value is still the raw total, so an unlabelled 12.2 beneath
  // a 171.2 reads as a bug.
  perUnit: string | null;
  // The radiologist-side denominator when there was one, so the caller can judge how much
  // weight the gap carries. Null for rates, whose denominators live inside the service.
  sample: number | null;
}

function comparison(row: CapacityRadiologistItem, practice: CapacityPracticeRollup, m: MetricDef): Comparison | null {
  const value = row[m.key];
  const reference = practice[m.key];
  if (value === null || reference === null) return null;

  if (m.kind === "rate") return { value, reference, perUnit: null, sample: null };

  // A total with no declared normaliser has no honest comparison - don't invent one.
  if (!m.normalizeBy) return null;
  const rowDen = row[m.normalizeBy];
  const practiceDen = practice[m.normalizeBy];
  if (!rowDen || !practiceDen) return null;
  return { value: value / rowDen, reference: reference / practiceDen, perUnit: "per shift", sample: rowDen };
}

// Enough data behind the radiologist side to paint a verdict on it?
function underSampled(c: Comparison, m: MetricDef): boolean {
  return m.minSample !== undefined && c.sample !== null && c.sample < m.minSample;
}

function deltaColor(c: Comparison | null, m: MetricDef): string {
  if (!c || c.reference === 0) return "var(--text-muted)";
  // Absolute floor before the relative band, because the relative band cannot see magnitude.
  // Muted rather than warning: a gap this small is not a weak finding, it is no finding, and
  // amber on ~100 rows at once would bury the ones that are.
  if (m.noiseFloor !== undefined && Math.abs(c.value - c.reference) < m.noiseFloor) {
    return "var(--text-muted)";
  }
  // And a gap of any size means nothing if too little sits behind it. Also muted rather than
  // warning, for the same reason: this is an absence of evidence, not evidence of a problem.
  if (underSampled(c, m)) return "var(--text-muted)";
  const relDiff = (c.value - c.reference) / Math.abs(c.reference);
  // Every metric in METRICS is higher-is-better (more work units per minute, more work units
  // per shift, more Mosaic, more drafting), so "above the practice is good" holds for all of
  // them. That is a property of this list, not a general rule: a read-time or idle-time
  // metric would invert it. Anything lower-is-better added to METRICS must carry its own
  // direction rather than inherit this.
  if (relDiff > 0) return "var(--status-good)";
  if (relDiff > -AMBER_BAND) return "var(--status-warning)";
  return "var(--status-critical)";
}

function fmtDelta(c: Comparison | null, m: MetricDef): string {
  if (!c) return "";
  // Normalised figures are in different units from the headline above them, so show both
  // sides outright. A lone "+2.4 per shift" would be read against the raw total.
  if (c.perUnit) {
    const pair = `${c.value.toFixed(1)} vs ${c.reference.toFixed(1)} ${c.perUnit} at practice`;
    // Still show both numbers - withholding the verdict is not a reason to withhold the data -
    // but name the sample, so a grey cell reads as "not enough to say" and not as "level with
    // the practice". Mirrors deltaColor, same as the noiseFloor wording below.
    if (underSampled(c, m)) {
      const unit = c.perUnit.replace(/^per\s+/, "");
      return `${pair} (${c.sample} ${unit}${c.sample === 1 ? "" : "s"} - too few to compare)`;
    }
    return pair;
  }
  const diff = c.value - c.reference;
  // Say so in words rather than printing "-0.0 pp", which reads as a rounding artefact and
  // leaves the reader guessing which way the sign went. Mirrors deltaColor's floor.
  if (m.noiseFloor !== undefined && Math.abs(diff) < m.noiseFloor) return "level with practice rate";
  const sign = diff >= 0 ? "+" : "";
  const body = m.ratio ? `${(diff * 100).toFixed(1)} pp` : m.format(diff);
  return `${sign}${body} vs practice rate`;
}

// What the Drawer tile shows under the value.
function fmtPracticeRef(c: Comparison | null, m: MetricDef): string | undefined {
  if (!c) return undefined;
  if (c.perUnit) return `${c.reference.toFixed(1)} ${c.perUnit} at practice`;
  return `practice rate ${m.format(c.reference)}`;
}

// The comparison as the model sees it. Keys name what the number IS - a generic
// "practice_avg" was what let a practice-wide SUM read as a per-radiologist mean.
function promptExtra(c: Comparison | null, m: MetricDef): Record<string, string> | undefined {
  if (!c) return undefined;
  if (c.perUnit) {
    const unit = c.perUnit.replace(/\s+/g, "_");
    return { [`radiologist_${unit}`]: c.value.toFixed(1), [`practice_${unit}`]: c.reference.toFixed(1) };
  }
  return { practice_rate: m.format(c.reference) };
}

interface Row extends CapacityRadiologistItem {
  // Not "practiceAvg" - /capacity/by-practice is a GROUP BY localpractice rollup, so rate
  // columns are recomputed rates and additive columns are practice totals. Neither is a mean
  // of per-radiologist values, and the name used to imply both were.
  practiceRollup: CapacityPracticeRollup | null;
}

function radLabel(r: CapacityRadiologistItem): string {
  return r.radiologist_name ?? `NPI ${r.npi}`;
}

export function RadMosaicScorecard() {
  const { practice, radiologistSearch } = useFilters();
  const filterOptions = useFetch(() => mosaicApi.getEfficiencyFilters(), []);
  const byRadiologist = useFetch(() => mosaicApi.getCapacityByRadiologist(), []);
  const byPractice = useFetch(() => mosaicApi.getCapacityByPractice(), []);
  const [selected, setSelected] = useState<number | null>(null);

  const practiceRollupByName = useMemo(() => {
    const map = new Map<string, CapacityPracticeRollup>();
    for (const p of byPractice.data ?? []) {
      if (p.practice) map.set(p.practice, p);
    }
    return map;
  }, [byPractice.data]);

  const rows: Row[] = useMemo(() => {
    let data = byRadiologist.data ?? [];
    if (practice) data = data.filter((r) => r.practice === practice);
    if (radiologistSearch) {
      const needle = radiologistSearch.toLowerCase();
      data = data.filter((r) => r.radiologist_name?.toLowerCase().includes(needle) || String(r.npi).includes(needle));
    }
    return data.map((r) => ({ ...r, practiceRollup: r.practice ? practiceRollupByName.get(r.practice) ?? null : null }));
  }, [byRadiologist.data, practice, radiologistSearch, practiceRollupByName]);

  const selectedRow = rows.find((r) => r.npi === selected) ?? null;

  const columns: DataTableColumn<Row>[] = [
    { key: "radiologist_name", label: "Radiologist", render: (r) => radLabel(r) },
    { key: "practice", label: "Practice" },
    // Coverage sits immediately before the metrics, not after, because it qualifies every
    // figure to its right. Efficiency is the headline here and it is NOT suppressed at low
    // coverage the way Utilization is - it stays population-matched, so it renders a number
    // whatever the coverage. That number can still be nonsense on a thin sample (RASF: 0.055%
    // coverage, 158.7 TBWU/min), so the badge is the only thing on this page saying so.
    {
      key: "pct_exams_with_valid_read_time",
      label: "Read-Time Coverage",
      render: (r) =>
        readTimeCoverageBadge(r.pct_exams_with_valid_read_time, radLabel(r), r.pct_shifts_rpce_source, "efficiency_metric"),
    },
    ...METRICS.map((m): DataTableColumn<Row> => ({
      key: m.key,
      label: m.label,
      render: (r) => {
        const c = r.practiceRollup ? comparison(r, r.practiceRollup, m) : null;
        return (
          <div>
            <span>{m.format(r[m.key])}</span>
            {c && <div style={{ fontSize: 10, color: deltaColor(c, m) }}>{fmtDelta(c, m)}</div>}
          </div>
        );
      },
    })),
  ];

  const loading = byRadiologist.loading || byPractice.loading;
  const error = byRadiologist.error || byPractice.error;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        Efficiency, % Mosaic, and % drafting per radiologist, each shown against the rate for the
        practice they read at, so you can see who's ahead of or behind their peers. Capacity is a
        total rather than a rate, so it is compared per shift - a radiologist's work units per
        shift against the practice's. Click a row for detail.
      </div>

      <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />

      {error && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({error})</div>}
      {loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}

      {!loading && rows.length > 0 && (
        <div style={{ ...CARD_STYLE, padding: 0, overflow: "auto" }}>
          <DataTable columns={columns} rows={rows} rowKey={(r) => r.npi} onRowClick={(r) => setSelected(r.npi)} />
        </div>
      )}

      {!loading && rows.length === 0 && !error && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>No radiologists match the current filters.</div>
      )}

      <Drawer open={selected !== null} onClose={() => setSelected(null)} title={selectedRow?.radiologist_name ?? undefined}>
        {selectedRow && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{selectedRow.practice}</div>

            {/* Above the tiles, not beside them - it qualifies all four at once. The practice
                comparison matters because coverage is an instrumentation property of the site,
                not of the radiologist: a rad reading at a site with no dictation timestamps
                looks identical to one who simply isn't producing. */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-muted)" }}>
              <span>Read-time coverage</span>
              {readTimeCoverageBadge(
                selectedRow.pct_exams_with_valid_read_time,
                radLabel(selectedRow),
                selectedRow.pct_shifts_rpce_source,
                "efficiency_metric",
              )}
              {selectedRow.practiceRollup?.pct_exams_with_valid_read_time != null && (
                <span>practice rate {fmtPct(selectedRow.practiceRollup.pct_exams_with_valid_read_time)}</span>
              )}
            </div>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {METRICS.map((m) => {
                const c = selectedRow.practiceRollup ? comparison(selectedRow, selectedRow.practiceRollup, m) : null;
                return (
                  <AIHoverCard
                    key={m.key}
                    feature={m.feature}
                    entityLabel={selectedRow.radiologist_name ?? `NPI ${selectedRow.npi}`}
                    metricLabel={m.label}
                    value={m.format(selectedRow[m.key])}
                    // Send the model the same comparison the tile renders, not the raw
                    // practice figure. These keys go straight into the prompt, so handing it
                    // a 2,858,482 practice total next to a radiologist's 171 invites exactly
                    // the wrong comparison in prose that the table used to make in numbers.
                    extra={promptExtra(c, m)}
                    underline={false}
                    style={{ flex: "1 1 160px", minWidth: 160 }}
                  >
                    <StatTile label={m.label} value={m.format(selectedRow[m.key])} sublabel={fmtPracticeRef(c, m)} />
                  </AIHoverCard>
                );
              })}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
