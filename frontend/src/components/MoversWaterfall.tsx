import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { AIHoverCard } from "./AIHoverCard";
import type { EfficiencyMode, MoversDecomposition } from "../api/types";

// Mix versus rate, for the one question a headline efficiency gap cannot answer on its own:
// is this group slower, or is it simply reading harder work?
//
// Two colours carry that distinction everywhere on this tile and nowhere else on the page:
// MIX is the work the group was *given*, RATE is how it *worked*. Only the second is
// actionable, and the whole point of the tile is that a reader can see which one they are
// looking at without reading a legend twice.
const MIX_COLOR = "var(--domain-capacity)";
const RATE_COLOR = "var(--domain-efficiency)";

// Never `--accent`: it is defined in src/index.css, which main.tsx does not import, so it
// resolves to transparent and a bar painted with it renders as nothing at all. Bar tracks use
// `--border` - `--surface-raised` is nearly invisible against `--surface-1` in dark mode.
const TRACK = "var(--border)";

type Comparison = "peers" | "baseline";

interface Scope {
  /** A column `efficiency_store._GROUP_COLS` accepts. */
  groupCol: string;
  groupValue: string;
  /** What the reader calls it. */
  label: string;
}

export interface MoversWaterfallProps {
  mode: EfficiencyMode;
  practice: string;
  subspecialty: string;
  modality: string;
  procedure: string;
  examCategory: string;
}

/** Pick the one filter the decomposition runs on.
 *
 * The endpoint takes a single group, not a conjunction, so a page carrying five filters has to
 * choose. Practice leads because it is the scope a practice conversation actually happens at -
 * and because it is the only one of the five that comes from the shared FilterBar, so it is the
 * filter a reader arriving from another page already has set. The chosen scope is printed on
 * the tile, so there is never a question about which filter produced the numbers.
 */
function resolveScope(p: MoversWaterfallProps): Scope | null {
  if (p.practice) return { groupCol: "practice", groupValue: p.practice, label: "Practice" };
  if (p.subspecialty) return { groupCol: "subspecialty", groupValue: p.subspecialty, label: "Subspecialty" };
  if (p.modality) return { groupCol: "modality_code", groupValue: p.modality, label: "Modality" };
  if (p.procedure) return { groupCol: "parent_procedure_name", groupValue: p.procedure, label: "Procedure" };
  if (p.examCategory) return { groupCol: "exam_category", groupValue: p.examCategory, label: "Exam category" };
  return null;
}

/** The store raises on `decompose_by == group_col` and the route turns that into a 400, not an
 * `available: false` refusal - deliberately, because an unknown column is a bug on our side
 * rather than a data condition. So the collision is made structurally unreachable here instead
 * of being handled after the fact. */
function bucketColumnFor(groupCol: string): string {
  return groupCol === "exam_category" ? "subspecialty" : "exam_category";
}

const BUCKET_LABELS: Record<string, string> = {
  exam_category: "Exam category",
  subspecialty: "Subspecialty",
  modality_code: "Modality",
  parent_procedure_name: "Procedure",
};

function fmtRate(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function fmtSigned(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const s = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  if (v > 0) return `+${s}`;
  if (v < 0) return `-${s}`;
  return s;
}

function fmtShare(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;
}

/** A bar that grows left or right from a centre line.
 *
 * Mix and rate get one of these each rather than being stacked into a single bar: when they
 * point in opposite directions - a group given easier work that it nonetheless reads slowly -
 * a stacked bar shows only the small net and hides both of the large effects that produced it.
 */
function DivergingBar({ value, max, color, title }: { value: number; max: number; color: string; title: string }) {
  const half = max > 0 ? Math.min(50, (Math.abs(value) / max) * 50) : 0;
  return (
    <div
      title={title}
      style={{ position: "relative", height: 7, background: TRACK, borderRadius: 999, overflow: "hidden" }}
    >
      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--text-muted)", opacity: 0.55 }} />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: value >= 0 ? "50%" : `${50 - half}%`,
          width: `${half}%`,
          background: color,
          borderRadius: 999,
        }}
      />
    </div>
  );
}

const cellStyle: CSSProperties = {
  padding: "7px 8px",
  fontSize: 13,
  borderBottom: "1px solid var(--border)",
  whiteSpace: "nowrap",
};

const headStyle: CSSProperties = {
  padding: "0 8px 6px",
  fontSize: 11,
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: 0.5,
  textAlign: "right",
  fontWeight: 500,
};

export function MoversWaterfall(props: MoversWaterfallProps) {
  const { mode } = props;
  const [comparison, setComparison] = useState<Comparison>("peers");
  const scope = resolveScope(props);
  const groupCol = scope?.groupCol ?? "";
  const groupValue = scope?.groupValue ?? "";
  const decomposeBy = bucketColumnFor(groupCol);

  // useFetch has no skip, so the no-scope case resolves to null rather than firing a request
  // the backend would refuse anyway ("no comparison group - this group is the entire
  // population"). A prompt is a better surface for that than a round-trip to a refusal.
  const x = useFetch<MoversDecomposition | null>(
    () =>
      scope
        ? mosaicApi.getEfficiencyMovers({
            group_col: groupCol,
            group_value: groupValue,
            decompose_by: decomposeBy,
            mode,
            comparison,
          })
        : Promise.resolve(null),
    [groupCol, groupValue, decomposeBy, mode, comparison],
  );

  const d = x.data;
  const buckets = useMemo(() => (d?.available ? d.buckets : []), [d]);
  const maxAbs = useMemo(
    () => buckets.reduce((m, b) => Math.max(m, Math.abs(b.mix), Math.abs(b.rate)), 0),
    [buckets],
  );
  const headlineMax = Math.max(Math.abs(d?.mix_effect ?? 0), Math.abs(d?.rate_effect ?? 0));
  const hasImputed = buckets.some((b) => b.imputed_peer_rate);
  const bucketLabel = BUCKET_LABELS[d?.bucket_label ?? decomposeBy] ?? "Bucket";
  const comparisonLabel = comparison === "peers" ? "peers" : "legacy baseline";
  const mixIsZero = Boolean(d?.mix_is_structurally_zero);

  return (
    <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Movers &amp; Drivers — case mix vs. reading rate
          </div>
          {/* Stated on the face of the tile, not in a tooltip. `efficiency_matrix` has no period
              column, so "what moved since last month" is genuinely unavailable here and is not
              faked - a reader who assumes this is a trend will misread every row. */}
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4 }}>
            A cross-sectional split of the current gap, not a week-over-week movement.
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {(["peers", "baseline"] as Comparison[]).map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setComparison(c)}
              style={{
                background: comparison === c ? "var(--color-primary)" : "transparent",
                color: comparison === c ? "#fff" : "var(--text-muted)",
                border: `1px solid ${comparison === c ? "var(--color-primary)" : "var(--border)"}`,
                borderRadius: 999,
                padding: "4px 12px",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              {c === "peers" ? "vs. peers" : "vs. legacy"}
            </button>
          ))}
        </div>
      </div>

      {!scope && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 14 }}>
          Choose a practice, subspecialty, modality, procedure or exam category above. A
          decomposition needs a group to compare — with no filter set, the group is the entire
          population and there is nothing to compare it against.
        </div>
      )}

      {scope && x.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13, marginTop: 14 }}>{x.error}</div>
      )}

      {scope && x.loading && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 14 }}>Decomposing the gap…</div>
      )}

      {/* `available: false` renders its reason, never a waterfall of zeros - a zeroed waterfall
          reads as "no difference found", which is a different and wrong claim. */}
      {scope && !x.loading && !x.error && d && !d.available && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 14 }}>
          {d.reason ?? "This gap cannot be decomposed for the current scope."}
        </div>
      )}

      {scope && !x.loading && !x.error && d && d.available && (
        <>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 14 }}>
            {scope.label}: <span style={{ color: "var(--text-primary)" }}>{scope.groupValue}</span> · split by{" "}
            {bucketLabel.toLowerCase()}
          </div>

          <AIHoverCard
            feature="efficiency_movers"
            entityLabel={`${scope.label} ${scope.groupValue}`}
            metricLabel={`Efficiency gap vs. ${comparisonLabel}`}
            value={`${fmtSigned(d.gap)} TBWU/min`}
            underline={false}
            style={{ display: "block", marginTop: 10 }}
            extra={{
              "This group": `${fmtRate(d.target_rate)} TBWU/min`,
              [comparison === "peers" ? "Peers" : "Legacy baseline"]: `${fmtRate(d.comparison_rate)} TBWU/min`,
              "Case-mix effect": fmtSigned(d.mix_effect),
              "Within-bucket rate effect": fmtSigned(d.rate_effect),
              "Split by": bucketLabel,
              Solution: mode,
            }}
          >
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Gap vs. {comparisonLabel}
                </div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 600,
                    color: (d.gap ?? 0) >= 0 ? "var(--status-good)" : "var(--status-critical)",
                  }}
                >
                  {fmtSigned(d.gap)}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  TBWU/min · {fmtRate(d.target_rate)} vs {fmtRate(d.comparison_rate)}
                </div>
              </div>

              <div style={{ flex: "1 1 320px", minWidth: 260, display: "flex", flexDirection: "column", gap: 10 }}>
                {/* vs. baseline both rates cover the same exams, so the weights cancel and the
                    mix term is zero by construction. Say that, rather than drawing a bar that
                    is permanently empty and inviting it to be read as a finding. */}
                {mixIsZero ? (
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    No case-mix component exists against the legacy baseline: both rates cover the
                    same exams, so the blend is identical on each side and every point of the gap
                    is rate.
                  </div>
                ) : (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                      <span style={{ color: MIX_COLOR }}>Case mix — the work it was given</span>
                      <span style={{ color: "var(--text-primary)" }}>{fmtSigned(d.mix_effect)}</span>
                    </div>
                    <DivergingBar
                      value={d.mix_effect ?? 0}
                      max={headlineMax}
                      color={MIX_COLOR}
                      title={`Case-mix effect ${fmtSigned(d.mix_effect)} TBWU/min`}
                    />
                  </div>
                )}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                    <span style={{ color: RATE_COLOR }}>Reading rate — how it worked</span>
                    <span style={{ color: "var(--text-primary)" }}>{fmtSigned(d.rate_effect)}</span>
                  </div>
                  <DivergingBar
                    value={d.rate_effect ?? 0}
                    max={headlineMax}
                    color={RATE_COLOR}
                    title={`Within-bucket rate effect ${fmtSigned(d.rate_effect)} TBWU/min`}
                  />
                </div>
              </div>
            </div>
          </AIHoverCard>

          <div style={{ overflowX: "auto", marginTop: 16 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
              <thead>
                <tr>
                  <th style={{ ...headStyle, textAlign: "left" }}>{bucketLabel}</th>
                  <th style={{ ...headStyle, textAlign: "left", width: 190 }}>Contribution</th>
                  <th style={headStyle}>Share</th>
                  <th style={headStyle}>{comparison === "peers" ? "Peer share" : ""}</th>
                  <th style={headStyle}>Rate</th>
                  <th style={headStyle}>{comparison === "peers" ? "Peer rate" : "Legacy rate"}</th>
                  <th style={{ ...headStyle, color: MIX_COLOR }}>{mixIsZero ? "" : "Mix"}</th>
                  <th style={{ ...headStyle, color: RATE_COLOR }}>Rate effect</th>
                  <th style={headStyle}>Total</th>
                </tr>
              </thead>
              <tbody>
                {buckets.map((b) => (
                  <tr key={b.bucket}>
                    <td
                      style={{
                        ...cellStyle,
                        whiteSpace: "normal",
                        color: b.is_tail ? "var(--text-muted)" : "var(--text-primary)",
                        fontStyle: b.is_tail ? "italic" : "normal",
                      }}
                    >
                      {b.bucket}
                      {b.imputed_peer_rate && <span style={{ color: "var(--text-muted)" }}> †</span>}
                    </td>
                    <td style={{ ...cellStyle, width: 190 }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        {!mixIsZero && (
                          <DivergingBar
                            value={b.mix}
                            max={maxAbs}
                            color={MIX_COLOR}
                            title={`Mix ${fmtSigned(b.mix)} TBWU/min`}
                          />
                        )}
                        <DivergingBar
                          value={b.rate}
                          max={maxAbs}
                          color={RATE_COLOR}
                          title={`Rate ${fmtSigned(b.rate)} TBWU/min`}
                        />
                      </div>
                    </td>
                    <td style={{ ...cellStyle, textAlign: "right" }}>{fmtShare(b.target_share)}</td>
                    <td style={{ ...cellStyle, textAlign: "right", color: "var(--text-muted)" }}>
                      {comparison === "peers" ? fmtShare(b.peer_share) : ""}
                    </td>
                    {/* A folded row's rates are null on purpose: an "All other" row spanning
                        dozens of unrelated procedures has no meaningful blended rate, and an
                        imputed row's null peer rate means the peers never read it at all. Both
                        print as an em dash rather than as a zero. */}
                    <td style={{ ...cellStyle, textAlign: "right" }}>{fmtRate(b.target_rate)}</td>
                    <td style={{ ...cellStyle, textAlign: "right", color: "var(--text-muted)" }}>
                      {fmtRate(b.peer_rate)}
                    </td>
                    <td style={{ ...cellStyle, textAlign: "right" }}>{mixIsZero ? "" : fmtSigned(b.mix)}</td>
                    <td style={{ ...cellStyle, textAlign: "right" }}>{fmtSigned(b.rate)}</td>
                    <td
                      style={{
                        ...cellStyle,
                        textAlign: "right",
                        fontWeight: 600,
                        color: b.total >= 0 ? "var(--status-good)" : "var(--status-critical)",
                      }}
                    >
                      {fmtSigned(b.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasImputed && (
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 10 }}>
              † The comparison group recorded no reading time in this bucket, so its rate is
              unknown — not zero. The mix effect there is valued at the comparison group's overall
              rate, which cancels out of the headline and only decides how that bucket's own
              contribution is split.
            </div>
          )}

          {/* Verbatim from the API. It is built from the same registry entry that defines the
              rates in the table, so any rewording here is a chance for the prose and the numbers
              to disagree. */}
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 10, lineHeight: 1.5 }}>
            {d.methodology}
          </div>
        </>
      )}
    </div>
  );
}
