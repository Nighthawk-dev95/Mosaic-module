import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { mosaicApi } from "../api/client";
import type { CubeCell, RegistryMetric } from "../api/types";
import { useFetch } from "../hooks/useFetch";
import { useScope, type Scope } from "../hooks/useScope";
import { Drawer } from "../components/Drawer";
import styles from "./Explorer.module.css";

/**
 * Explorer - the cube, as a grid.
 *
 * Five pages used to answer five fixed questions: Volume by practice, Efficiency by practice,
 * Capacity, Non-Drafted leakage, Shift Utilization. None of them composed, so "Mosaic adoption
 * and RPCE drafting, by team, for the last six months" meant opening two tabs and reading across
 * them. This asks the cube one scope at a time instead: pick metrics, pick an axis, get a grid.
 *
 * Three rules the surface is built around, all of them the registry's rather than this file's:
 *
 * 1. **A refused scope is an answer.** The cube rejects an illegal metric x dimension by name and
 *    says what would work. That message is rendered as a prompt to refine, not as a failure.
 * 2. **Withheld is not missing.** A null under a `gated_by` metric is a coverage policy doing its
 *    job. The cell says so rather than showing a bare dash that reads as an outage.
 * 3. **The grid shows only what the cube can actually answer.** `/cube/status` names the measures
 *    that have been folded in; everything else in the registry is listed as not yet available,
 *    with the reason, instead of rendering as an empty row.
 */

const MAX_COLS = 24;

/** Dimension keys the cube groups by, in the order they are offered. */
const AXES = ["practice", "team", "local_region", "month"] as const;

/**
 * Percent-valued metrics are named `pct_*` by registry convention, which is what separates a 0.83
 * that means 83% from a 0.83 that means 0.83 TBWU per minute. `is_rate` alone cannot tell them
 * apart - both are rates.
 */
function formatValue(key: string, isRate: boolean, value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (key.startsWith("pct_")) return `${(value * 100).toFixed(1)}%`;
  if (isRate) return value.toFixed(2);
  return Math.round(value).toLocaleString();
}

/**
 * Sequential single-hue ramp from the page's own surface up to its primary accent, scaled within
 * a row rather than globally: exam counts and adoption rates share this grid, and a ramp spanning
 * both would render every rate as the same shade. Shading compares cells across one metric.
 */
function heatFill(value: number | null, min: number, max: number): string | undefined {
  if (value === null || value === undefined) return undefined;
  const t = max > min ? (value - min) / (max - min) : 1;
  const pct = (Math.max(0, Math.min(1, t)) * 85).toFixed(0);
  return `color-mix(in srgb, var(--color-primary) ${pct}%, var(--surface-raised))`;
}

/**
 * The four pages Explore has taken off the tab bar but cannot yet answer for itself.
 *
 * Their metrics are computed in their own services and are not stored as numerators in the
 * cube, so folding them in is a later wave. Until then they stay one click away rather than
 * being redirected into a grid that would have to say "not available" for every one of them.
 */
const DEEPER_VIEWS = [
  { to: "/volume-detail", label: "Volume detail" },
  { to: "/efficiency", label: "Efficiency" },
  { to: "/capacity", label: "Capacity" },
  { to: "/non-drafted", label: "Non-drafted leakage" },
  { to: "/shift-utilization", label: "Shift utilization" },
];

interface Selection {
  cell: CubeCell;
  metric: RegistryMetric | undefined;
  column: string;
}

export function Explorer() {
  const status = useFetch(() => mosaicApi.getCubeStatus(), []);
  const registry = useFetch(() => mosaicApi.getRegistry(), []);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [showAllCols, setShowAllCols] = useState(false);

  const available = status.data?.measure_keys ?? [];

  // The fallback has to be stable across renders - useScope holds it in a dependency list.
  const fallback = useMemo<Scope>(() => {
    const wave1 = status.data?.wave_1_metrics ?? [];
    const defaults = wave1.filter((k) => available.includes(k)).slice(0, 4);
    return {
      metrics: defaults.length ? defaults : available.slice(0, 4),
      axis: "practice",
      entityId: null,
      periodFrom: null,
      periodTo: null,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.data]);

  const [scope, patchScope] = useScope(fallback);

  const metricsKey = scope.metrics.join(",");
  const cube = useFetch(
    () =>
      scope.metrics.length
        ? mosaicApi.postCube({ metrics: scope.metrics, group_by: [scope.axis], limit: 5000 })
        : Promise.resolve(null),
    [metricsKey, scope.axis],
  );

  const metricOf = (key: string) => registry.data?.metrics.find((m) => m.key === key);
  const dimensionOf = (key: string) => registry.data?.dimensions.find((d) => d.key === key);

  /** An axis is offered only where every selected metric declares it. Disabled, and said why. */
  const axisBlockedBy = (axis: string): string | null => {
    const offender = scope.metrics
      .map(metricOf)
      .find((m) => m && m.allowed_dims.length > 0 && !m.allowed_dims.some((d) => d.key === axis));
    return offender ? offender.label : null;
  };

  // Pivot the flat rows into metric x column.
  const { columns, byMetric } = useMemo(() => {
    const rows = cube.data?.rows ?? [];
    const colLabels = new Map<string, string>();
    const grid = new Map<string, Map<string, CubeCell>>();
    for (const r of rows) {
      const key = scope.axis === "month" ? r.period_start ?? "" : r.entity_id ?? "";
      if (!key) continue;
      colLabels.set(key, scope.axis === "month" ? key.slice(0, 7) : r.entity_label ?? key);
      if (!grid.has(r.measure)) grid.set(r.measure, new Map());
      grid.get(r.measure)!.set(key, r);
    }
    let keys = [...colLabels.keys()];
    if (scope.axis === "month") {
      keys.sort();
    } else {
      // Rank by the first selected metric so the grid opens on the biggest contributors rather
      // than on whatever alphabetically comes first.
      const lead = grid.get(scope.metrics[0]);
      keys.sort((a, b) => (lead?.get(b)?.value ?? -Infinity) - (lead?.get(a)?.value ?? -Infinity));
    }
    return {
      columns: keys.map((k) => ({ key: k, label: colLabels.get(k) ?? k })),
      byMetric: grid,
    };
  }, [cube.data, scope.axis, scope.metrics]);

  const visibleColumns = showAllCols ? columns : columns.slice(0, MAX_COLS);
  const activeDim = dimensionOf(scope.axis);

  const toggleMetric = (key: string) => {
    const next = scope.metrics.includes(key)
      ? scope.metrics.filter((k) => k !== key)
      : [...scope.metrics, key];
    if (next.length) patchScope({ metrics: next });
  };

  const freshness = status.data
    ? status.data.rows > 0
      ? `${status.data.rows.toLocaleString()} stored facts across ${status.data.measures} measures, ` +
        `${(status.data.first_period ?? "").slice(0, 7)} to ${(status.data.last_period ?? "").slice(0, 7)}. ` +
        `Registry ${status.data.registry_version}.`
      : "The cube is empty. It fills on the next refresh cycle."
    : "";

  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", padding: "16px 24px 24px", gap: 16, textAlign: "left", overflow: "auto" }}>
      <div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Explore</div>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 2, maxWidth: 620 }}>
          Pick the numbers and the breakdown. Every cell carries its own definition, its numerator
          and denominator, and the coverage behind it.
        </div>
      </div>

      {/* Scope bar. Inline styles - the CSS module is scoped to the grid. */}
      <div
        style={{
          display: "flex", flexWrap: "wrap", gap: 20, alignItems: "flex-start",
          padding: "12px 14px", background: "var(--surface-1)",
          border: "1px solid var(--border)", borderRadius: "var(--radius)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 260 }}>
          <label style={{ fontSize: 12, color: "var(--text-secondary)" }}>Metrics</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {(registry.data?.metrics ?? []).map((m) => {
              const inCube = available.includes(m.key);
              const on = scope.metrics.includes(m.key);
              if (!inCube && !on) return null;
              return (
                <button
                  key={m.key}
                  onClick={() => toggleMetric(m.key)}
                  style={{
                    border: on ? "1px solid var(--color-primary)" : "1px solid var(--border)",
                    background: on ? "var(--color-primary)" : "transparent",
                    color: on ? "#0a0a0a" : "var(--text-secondary)",
                    borderRadius: "var(--radius-pill)", padding: "3px 10px",
                    fontSize: 12, cursor: "pointer",
                  }}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
          {registry.data && available.length > 0 && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", maxWidth: 420 }}>
              {registry.data.metrics.length - available.length} further registry metrics are not in
              the cube yet — Efficiency and MVP are computed in their own services and cannot be
              composed from stored numerators.
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label htmlFor="explorer-axis" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            Break down by
          </label>
          <select
            id="explorer-axis"
            value={scope.axis}
            onChange={(e) => patchScope({ axis: e.target.value })}
            style={{
              background: "var(--surface-raised)", color: "var(--text-primary)",
              border: "1px solid var(--border)", borderRadius: "var(--radius)",
              padding: "6px 10px", fontSize: 13,
            }}
          >
            {AXES.map((a) => {
              const blocked = axisBlockedBy(a);
              const dim = dimensionOf(a);
              return (
                <option key={a} value={a} disabled={!!blocked}>
                  {dim?.label ?? a}
                  {blocked ? ` — not available for ${blocked}` : ""}
                </option>
              );
            })}
          </select>
          {activeDim && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", maxWidth: 360 }}>
              {activeDim.note}
            </div>
          )}
        </div>
      </div>

      {freshness && (
        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{freshness}</div>
      )}

      {cube.error && (
        <div
          style={{
            padding: "10px 14px", borderRadius: "var(--radius)",
            border: "1px solid var(--status-warning)", color: "var(--text-primary)", fontSize: 13,
            maxWidth: 720,
          }}
        >
          {cube.error}
        </div>
      )}

      {cube.loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}

      {!cube.loading && !cube.error && columns.length === 0 && (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Nothing stored for this scope yet. Pick another breakdown, or choose a metric the cube
          already covers.
        </div>
      )}

      {columns.length > 0 && (
        <>
          <div className={styles.grid}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.corner} />
                  {visibleColumns.map((c) => (
                    <th key={c.key} className={styles.colHead}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scope.metrics.map((key) => {
                  const metric = metricOf(key);
                  const row = byMetric.get(key);
                  const values = visibleColumns
                    .map((c) => row?.get(c.key)?.value)
                    .filter((v): v is number => typeof v === "number");
                  // Anchored at zero rather than at the smallest cell: across 24 practices the
                  // exam counts span 2.6M to 4.5M, and a min-max ramp paints all of them near
                  // full moss, which reads as "everything is high" instead of as the 1.7x
                  // spread it is. Zero is the real floor for both counts and rates here.
                  const min = Math.min(0, ...values);
                  const max = values.length ? Math.max(...values) : 0;
                  return (
                    <tr key={key}>
                      <th
                        className={styles.rowHead}
                        style={{ ["--domain" as string]: `var(--domain-${metric?.domain ?? "deployment"})` }}
                      >
                        <span className={styles.metricLabel}>{metric?.label ?? key}</span>
                        <span className={styles.metricMeta}>{metric?.domain}</span>
                      </th>
                      {visibleColumns.map((c) => {
                        const cell = row?.get(c.key);
                        const value = cell?.value ?? null;
                        // Withheld by a coverage gate, versus simply not present in the cube.
                        const withheld = !!cell && value === null && !!metric?.gated_by;
                        const className = [
                          styles.cell,
                          withheld ? styles.suppressed : "",
                          cell ? "" : styles.empty,
                        ].filter(Boolean).join(" ");
                        return (
                          <td key={c.key} className={styles.cellWrap}>
                            <button
                              type="button"
                              className={className}
                              disabled={!cell}
                              onClick={() => cell && setSelected({ cell, metric, column: c.label })}
                              style={{ ["--cell-fill" as string]: heatFill(value, min, max) ?? "var(--surface-raised)" }}
                            >
                              {withheld ? "withheld" : formatValue(key, !!metric?.is_rate, value)}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", gap: 12, alignItems: "center", fontSize: 11, color: "var(--text-muted)" }}>
            <span>Shading compares cells within a row.</span>
            {columns.length > MAX_COLS && (
              <button
                onClick={() => setShowAllCols((s) => !s)}
                style={{
                  background: "transparent", border: "1px solid var(--border)",
                  borderRadius: "var(--radius-pill)", color: "var(--text-secondary)",
                  padding: "2px 10px", fontSize: 11, cursor: "pointer",
                }}
              >
                {showAllCols ? `Show the top ${MAX_COLS}` : `Show all ${columns.length}`}
              </button>
            )}
          </div>
        </>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12, fontSize: 12, color: "var(--text-muted)" }}>
        <span>Not in the cube yet:</span>
        {DEEPER_VIEWS.map((v) => (
          <Link
            key={v.to}
            to={v.to}
            style={{
              color: "var(--text-secondary)", textDecoration: "none",
              border: "1px solid var(--border)", borderRadius: "var(--radius-pill)",
              padding: "2px 10px",
            }}
          >
            {v.label}
          </Link>
        ))}
      </div>

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.metric?.label ?? selected.cell.measure} — ${selected.column}` : ""}
      >
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13, textAlign: "left" }}>
            <div style={{ fontSize: 28, fontWeight: 600 }}>
              {formatValue(selected.cell.measure, selected.cell.is_rate, selected.cell.value)}
            </div>
            <div style={{ color: "var(--text-secondary)" }}>{selected.metric?.definition}</div>

            <div style={{ display: "flex", gap: 24 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Numerator</div>
                <div>{selected.cell.num?.toLocaleString() ?? "—"}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Denominator</div>
                <div>{selected.cell.den?.toLocaleString() ?? "—"}</div>
              </div>
            </div>

            {selected.cell.coverage_pct !== undefined && (
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Coverage</div>
                <div>{(selected.cell.coverage_pct * 100).toFixed(1)}%</div>
              </div>
            )}

            {selected.cell.value === null && selected.metric?.gated_by && (
              <div style={{ color: "var(--text-secondary)" }}>
                {registry.data?.coverage.find((c) => c.key === selected.metric?.gated_by)?.sentence ??
                  "Withheld: coverage for this slice is below the documented floor."}
              </div>
            )}

            {!!selected.metric?.caveats.length && (
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>Caveats</div>
                <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text-secondary)" }}>
                  {selected.metric.caveats.map((c) => <li key={c}>{c}</li>)}
                </ul>
              </div>
            )}

            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {selected.metric?.source} · {selected.metric?.owner} · v{selected.metric?.version}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
