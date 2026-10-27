import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { TABLE_SECTION_STYLE, TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { VolumeTrendChart } from "../components/VolumeTrendChart";
import { FilterBar } from "../components/FilterBar";
import { SolutionAxis, SOLUTION_FALLBACK } from "../components/SolutionAxis";
import { AIHoverCard } from "../components/AIHoverCard";
import { useFilters, matchesPractice } from "../context/FilterContext";
import type { EfficiencyMode, VolumeGroupRollup, VolumeSummary } from "../api/types";

function fmtCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

type GroupBy = "practice" | "team" | "local_region";

const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "practice", label: "By Practice" },
  { value: "team", label: "By Team" },
  { value: "local_region", label: "By Local Region" },
];

/**
 * The solution axis on Volume, where "solution" means something different than it does on
 * Efficiency.
 *
 * On Efficiency a solution is a *filter mode*: the same measure recomputed over a different
 * subset of exams (`efficiency_store._MODE_EXPRS`). Here it is a *different column pair* -
 * `mosaic_exams` / `pct_mosaic` and `drafting_exams` / `pct_drafting` are separate measures the
 * ETL emits side by side, not one measure under two filters. Conflating the two would be an easy
 * mistake to make while "rolling the toggle out to every page", and it would produce numbers
 * that are wrong rather than merely confusing.
 *
 * Two solutions are absent, for two different reasons:
 *
 *   - **Capture** has no volume column at all. There is no capture equivalent of `mosaic_exams`
 *     upstream, so there is nothing to select.
 *   - **Full Mosaic** is a *mode*, not a solution - Reporting + Drafting, excluding Capture. It
 *     has meaning where modes exist (Efficiency); on a page whose axis is columns, selecting it
 *     would have to mean "both column pairs at once", which is just the unfiltered table.
 *
 * The column keys below are the registry's own metric keys, not display strings, and
 * `test_registry_parity.py::test_the_volume_solution_axis_matches_the_registrys_tags` asserts
 * each one exists in the registry carrying the solution it is filed under here. So this map is a
 * layout decision (which columns to emphasise) resting on a governed one (which solution each
 * column belongs to), rather than a second opinion about either.
 */
const VOLUME_SOLUTION_COLUMNS = {
  reporting: { count: "mosaic_exams", pct: "pct_mosaic", rpce: "pct_rpce_reporting" },
  drafting: { count: "drafting_exams", pct: "pct_drafting", rpce: "pct_rpce_drafting" },
} as const satisfies Partial<
  Record<EfficiencyMode, { count: keyof VolumeGroupRollup; pct: keyof VolumeGroupRollup; rpce: keyof VolumeGroupRollup }>
>;

const VOLUME_SOLUTIONS = Object.keys(VOLUME_SOLUTION_COLUMNS) as readonly (keyof typeof VOLUME_SOLUTION_COLUMNS)[];

const VOLUME_UNAVAILABLE_NOTE =
  "Not measurable on Volume. Capture has no exam-count column upstream, and Full Mosaic is a " +
  "filter mode rather than a column - both are available on Efficiency.";

const GROUP_COLUMNS: DataTableColumn<VolumeGroupRollup>[] = [
  { key: "group", label: "Group" },
  { key: "total_exams", label: "Total Exams", render: (r) => fmtCount(r.total_exams) },
  { key: "mosaic_exams", label: "Mosaic Exams", render: (r) => fmtCount(r.mosaic_exams) },
  { key: "pct_mosaic", label: "% Mosaic", render: (r) => fmtPct(r.pct_mosaic) },
  { key: "drafting_exams", label: "Drafting Exams", render: (r) => fmtCount(r.drafting_exams) },
  { key: "pct_drafting", label: "% Drafting", render: (r) => fmtPct(r.pct_drafting) },
  { key: "pct_rpce_reporting", label: "% RPCE Reporting", render: (r) => fmtPct(r.pct_rpce_reporting) },
  { key: "pct_rpce_drafting", label: "% RPCE Drafting", render: (r) => fmtPct(r.pct_rpce_drafting) },
];

/**
 * The table narrowed to one solution: Group, Total Exams, then that solution's three columns.
 *
 * Narrowing rather than highlighting is the deliberate choice. The eight-column table showed
 * Reporting and Drafting side by side with no indication that `pct_mosaic` and `pct_drafting`
 * have different denominators-worth of meaning, and a reader scanning across read them as a
 * series. Picking a solution first makes the comparison an explicit act.
 *
 * `total_exams` stays in every view because it is the one column tagged with all three solutions
 * in the registry - it is the common denominator, not a Reporting measure.
 */
function columnsForSolution(solution: keyof typeof VOLUME_SOLUTION_COLUMNS): DataTableColumn<VolumeGroupRollup>[] {
  const picked = VOLUME_SOLUTION_COLUMNS[solution];
  const keep = new Set<string>(["group", "total_exams", picked.count, picked.pct, picked.rpce]);
  return GROUP_COLUMNS.filter((c) => keep.has(c.key as string));
}

/**
 * The scope these four tiles describe.
 *
 * `/volume/summary` runs with no WHERE clause and no GROUP BY - it is the whole exam inventory,
 * and the FilterBar below it governs the table, not these. Saying so in the hover card matters
 * more here than on a scoped surface: a reader who has just picked a practice downstairs will
 * otherwise assume the headline number moved with it.
 */
const SUMMARY_SCOPE = "Enterprise - every exam in the inventory, unfiltered";

/** Label and formatted value for one summary column.
 *
 * Reuses the table's own key convention (`pct_` prefix means percentage) rather than keeping a
 * second list of which columns format which way - two lists is how a new column ends up
 * rendering 0.43 instead of 43%. */
function kpiFor(key: keyof VolumeSummary, data: VolumeSummary | null | undefined) {
  const v = data?.[key] as number | null | undefined;
  return {
    label: (GROUP_COLUMNS.find((c) => c.key === key)?.label ?? key) as string,
    value: key.startsWith("pct_") ? fmtPct(v) : fmtCount(v),
  };
}

function KpiTile({
  label,
  value,
  feature,
}: {
  label: string;
  value: string;
  /** Governed feature key the hover card explains this tile under. */
  feature: string;
}) {
  return (
    <AIHoverCard
      feature={feature}
      entityLabel={SUMMARY_SCOPE}
      metricLabel={label}
      value={value}
      underline={false}
      // The hover wrapper becomes the flex item, so the sizing moves out here with it -
      // leaving `flex` on the inner div would size a block that no longer has a flex parent.
      style={{ flex: "1 1 180px", minWidth: 160 }}
    >
      <div
        style={{
          height: "100%",
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "16px 20px",
        }}
      >
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 8 }}>{label}</div>
        <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-primary)" }}>{value}</div>
      </div>
    </AIHoverCard>
  );
}

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
    <div style={{ display: "flex", gap: 4, background: "var(--surface-1)", borderRadius: 8, padding: 4 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            fontSize: 13,
            padding: "6px 14px",
            borderRadius: 6,
            border: "none",
            background: value === opt.value ? "var(--surface-raised)" : "transparent",
            color: value === opt.value ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
            fontWeight: value === opt.value ? 600 : 400,
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function VolumeDetail() {
  const [groupBy, setGroupBy] = useState<GroupBy>("practice");
  // Reporting first: it is the larger population and the one `% Mosaic` refers to, so it is the
  // view that matches the page's existing headline number.
  const [solution, setSolution] = useState<keyof typeof VOLUME_SOLUTION_COLUMNS>("reporting");
  const filters = useFilters();

  const summary = useFetch(() => mosaicApi.getVolumeSummary(), []);
  const trend = useFetch(() => mosaicApi.getVolumeTrend(), []);
  const filterOptions = useFetch(() => mosaicApi.getVolumeFilters(), []);
  const byPractice = useFetch(() => mosaicApi.getVolumeByPractice(), []);
  const byTeam = useFetch(() => mosaicApi.getVolumeByTeam(), []);
  const byLocalRegion = useFetch(() => mosaicApi.getVolumeByLocalRegion(), []);

  const activeRows = useMemo(() => {
    const source =
      groupBy === "practice" ? byPractice.data : groupBy === "team" ? byTeam.data : byLocalRegion.data;
    if (!source) return [];
    // The top FilterBar's practice dropdown is populated from Managing Practice values, so it
    // only lines up with the "By Practice" grouping's own `group` field - Team and Local Region
    // are different grains with their own value sets, filtering by a Practice selection there
    // would silently drop every row instead of narrowing them.
    if (groupBy !== "practice") return source;
    return source.filter((r) => matchesPractice(filters, r.group));
  }, [groupBy, byPractice.data, byTeam.data, byLocalRegion.data, filters]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Volume</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Mosaic adoption volume -- exam counts, Mosaic reporting/drafting share, and RPCE coverage, reconciled
          exactly against the governed mosaic_volume_metric_view dashboard (see tools/mosaic_validation/
          VALIDATION_REPORT_VOLUME.md for the reconciliation this was built to match).
        </div>
      </div>

      {(summary.error || trend.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({summary.error ?? trend.error})
        </div>
      )}

      {/* The solution axis sits above the KPIs, not beside the table, because it governs both.
          Mosaic is a product with three solutions; which one you are looking at is a more
          fundamental question than how the rows are grouped, and the layout should say so. */}
      <SolutionAxis
        value={solution}
        onChange={(v) => setSolution(v as keyof typeof VOLUME_SOLUTION_COLUMNS)}
        fallback={SOLUTION_FALLBACK}
        available={VOLUME_SOLUTIONS}
        unavailableNote={VOLUME_UNAVAILABLE_NOTE}
      />

      {/* Four tiles, three groundings, written out rather than mapped.
          A `.map` over the three solution columns said they were the same kind of thing. They
          are not: the count answers "what is in this number", the share answers "how far along
          is the rollout", and the RPCE share answers "why is this denominator different from
          the one beside it". Each goes to the feature that can answer its own question, and
          `adoption_rollout` - which already explains exactly this metric pair on five other
          surfaces - is reused rather than restated under a new key. */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {/* Total Exams is solution-independent - the denominator all three share - so it holds
            its position while the three beside it change. It shares the counts' grounding
            because the two are only meaningful together. */}
        <KpiTile feature="volume_counts" {...kpiFor("total_exams", summary.data)} />
        <KpiTile feature="volume_counts" {...kpiFor(VOLUME_SOLUTION_COLUMNS[solution].count, summary.data)} />
        <KpiTile feature="adoption_rollout" {...kpiFor(VOLUME_SOLUTION_COLUMNS[solution].pct, summary.data)} />
        <KpiTile feature="volume_rpce" {...kpiFor(VOLUME_SOLUTION_COLUMNS[solution].rpce, summary.data)} />
      </div>

      <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Volume Trend, Monthly
        </div>
        {/* The null-period bucket (exams with no final_datetime - confirmed identical on the
            Lakeview dashboard's own Final Month dimension) is excluded at the query layer in
            volume_service.get_volume_trend(), not here - every row this endpoint returns has a
            real period, no client-side filtering needed. */}
        {trend.data && <VolumeTrendChart data={trend.data} />}
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label}
          </div>
          <ToggleGroup options={GROUP_BY_OPTIONS} value={groupBy} onChange={setGroupBy} />
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          <DataTable columns={columnsForSolution(solution)} rows={activeRows} rowKey={(r) => r.group ?? "unknown"} />
        </div>
      </div>
    </div>
  );
}
