import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { mosaicApi } from "../api/client";
import type { CubeCell, EfficiencyMode, RpceTrendPoint } from "../api/types";
import { CARD_STYLE } from "../styles/glassCard";
import { AIHoverCard } from "../components/AIHoverCard";
import { RpceTrendChart } from "../components/RpceTrendChart";

/**
 * Command - the value chain, not a tile wall.
 *
 * Mosaic is a product, so the question a Command surface has to answer is the product
 * question: we deployed it to people, they put work through it, the work went faster, and
 * something came back. Four stages, read left to right.
 *
 * The stages are the easy part. What this page exists for is the three gaps *between* them -
 * exams that never reached Mosaic, Mosaic exams read without drafting, and the conversion
 * from "faster" into "time back". Every tile wall this replaces could show the four numbers;
 * none of them could show where the product leaks between them.
 *
 * Nothing here is derived prose over invented arithmetic: the two leak counts are differences
 * between three stored cube measures at enterprise grain, and the efficiency and read-time
 * figures are the governed population measures compared against the pre-Mosaic baseline.
 */

type Solution = "all" | "reporting" | "drafting" | "capture";

const SOLUTIONS: { key: Solution; label: string; mode: EfficiencyMode; color: string }[] = [
  { key: "all", label: "All of Mosaic", mode: "full_mosaic", color: "var(--color-primary)" },
  { key: "reporting", label: "Reporting", mode: "reporting", color: "var(--domain-deployment)" },
  { key: "drafting", label: "AI Drafting", mode: "drafting", color: "var(--domain-efficiency)" },
  { key: "capture", label: "Capture", mode: "capture", color: "var(--domain-capture)" },
];

const WINDOWS = [
  { months: 3, label: "Last 3 months" },
  { months: 12, label: "Last 12 months" },
  { months: 24, label: "Full history" },
];

function monthsAgoIso(months: number): string {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - (months - 1));
  return d.toISOString().slice(0, 10);
}

function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return n.toLocaleString();
}

function fmtPct(fraction: number | null | undefined, digits = 1): string {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  return `${(fraction * 100).toFixed(digits)}%`;
}

function fmtSigned(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  const pct = fraction * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

interface Stage {
  ordinal: string;
  name: string;
  headline: string;
  caption: string;
  detail: string;
  color: string;
  /** Registry coverage for this stage's metric, where the cube carries one. */
  coverage?: number;
  aiMetric: string;
}

function StageCard({ stage }: { stage: Stage }) {
  return (
    <AIHoverCard
      feature="value_chain"
      entityLabel="Enterprise"
      metricLabel={stage.aiMetric}
      value={stage.headline}
      extra={{ Stage: stage.name, Basis: stage.detail }}
      underline={false}
      style={{ flex: "1 0 180px", minWidth: 170, display: "flex" }}
    >
      <div
        style={{
          ...CARD_STYLE,
          borderTop: `3px solid ${stage.color}`,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          // Not height:100%. The wrapper is a flex item whose height comes from the flex
          // line, which comes from its tallest child - so a percentage height here is
          // circular and resolves to zero. `flex: 1` inside an already-stretched wrapper
          // fills the card without asking the parent how tall it is.
          flex: 1,
          boxSizing: "border-box",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 11, color: stage.color, fontWeight: 700, letterSpacing: 0.4 }}>{stage.ordinal}</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{stage.name}</span>
        </div>
        <div style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" }}>
          {stage.headline}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{stage.caption}</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: "auto", lineHeight: 1.5 }}>
          {stage.detail}
          {stage.coverage !== undefined && (
            <>
              {" "}
              <span style={{ color: stage.coverage >= 0.5 ? "var(--status-ok, var(--domain-utilization))" : "var(--status-critical)" }}>
                Coverage {fmtPct(stage.coverage, 0)}.
              </span>
            </>
          )}
        </div>
      </div>
    </AIHoverCard>
  );
}

function Connector({ value, label, tone }: { value: string; label: string; tone: "leak" | "convert" }) {
  const color = tone === "leak" ? "var(--domain-feedback)" : "var(--domain-utilization)";
  return (
    <div
      style={{
        flex: "0 0 92px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        padding: "0 2px",
      }}
    >
      <div style={{ fontSize: 15, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      <div style={{ display: "flex", alignItems: "center", width: "100%", gap: 2 }}>
        <div style={{ flex: 1, height: 1, background: color, opacity: 0.5 }} />
        <div
          style={{
            width: 0,
            height: 0,
            borderTop: "4px solid transparent",
            borderBottom: "4px solid transparent",
            borderLeft: `6px solid ${color}`,
            opacity: 0.7,
          }}
        />
      </div>
      <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center", lineHeight: 1.3 }}>{label}</div>
    </div>
  );
}

export function Command() {
  const [solution, setSolution] = useState<Solution>("all");
  const [months, setMonths] = useState(12);
  const periodFrom = useMemo(() => monthsAgoIso(months), [months]);
  const active = SOLUTIONS.find((s) => s.key === solution)!;

  const intelligence = useFetch(() => mosaicApi.getMosaicIntelligence(), []);
  const capture = useFetch(() => mosaicApi.getCaptureOverview(), []);
  const trend = useFetch(() => mosaicApi.getRpceTrend(), []);
  const efficiency = useFetch(() => mosaicApi.getEfficiencyPopulation({ mode: active.mode }), [active.mode]);
  const actions = useFetch(() => mosaicApi.getNextBestActions(), []);
  // The scope-neutral view of the weekly report. A snapshot may simply not exist yet, and that
  // is not an error worth shouting about on the enterprise landing page - the narrative block
  // just doesn't render.
  const briefing = useFetch(() => mosaicApi.getBriefing("overview"), []);

  const cube = useFetch(
    () =>
      mosaicApi.postCube({
        metrics: ["total_exams", "mosaic_exams", "drafting_exams", "pct_mosaic", "pct_rpce_reporting", "pct_rpce_drafting"],
        entity_type: "enterprise",
        period_from: periodFrom,
      }),
    [periodFrom]
  );

  const cells = useMemo(() => {
    const map = new Map<string, CubeCell>();
    for (const row of cube.data?.rows ?? []) map.set(row.measure, row);
    return map;
  }, [cube.data]);

  const num = (key: string): number | null => {
    const cell = cells.get(key);
    if (!cell) return null;
    return cell.value ?? cell.num;
  };

  const totalExams = num("total_exams");
  const mosaicExams = num("mosaic_exams");
  const draftingExams = num("drafting_exams");

  const filteredTrend: RpceTrendPoint[] = trend.data ?? [];

  const stages: Stage[] = useMemo(() => {
    const intel = intelligence.data;
    const cap = capture.data;
    const eff = efficiency.data;

    const deploy = (() => {
      if (solution === "drafting")
        return {
          headline: fmtInt(intel?.rads_live_on_ai_drafting),
          caption: "radiologists live on AI Drafting",
          detail: `${fmtInt(intel?.rads_live_on_mosaic)} are live on Mosaic overall.`,
        };
      if (solution === "capture")
        return {
          headline: fmtInt(intel?.rads_live_on_capture),
          caption: "radiologists live on Capture",
          detail: `${fmtInt(intel?.rads_capture_enabled)} are enabled but not all are reading with it.`,
        };
      return {
        headline: fmtInt(intel?.rads_live_on_mosaic),
        caption: "radiologists live on Mosaic",
        detail: `${fmtInt(intel?.practices_fully_on_rpce)} practices fully on RPCE, ${fmtInt(
          intel?.practices_split_integration
        )} split, ${fmtInt(intel?.practices_not_on_rpce)} not yet.`,
      };
    })();

    const use = (() => {
      if (solution === "capture")
        return {
          headline: fmtPct(cap?.pct_captured_enabled),
          caption: "of capturable exams captured",
          detail: `${fmtInt(cap?.captured_exams_enabled)} of ${fmtInt(
            cap?.capturable_exams_enabled
          )} capturable exams, among enabled radiologists.`,
          coverage: undefined as number | undefined,
        };
      const key = solution === "reporting" ? "pct_rpce_reporting" : solution === "drafting" ? "pct_rpce_drafting" : "pct_mosaic";
      const cell = cells.get(key);
      return {
        headline: fmtPct(cell?.value),
        caption: cell?.label ?? "of exams run through Mosaic",
        detail: `${fmtInt(cell?.num)} of ${fmtInt(cell?.den)} exams in this window.`,
        coverage: cell?.coverage_pct,
      };
    })();

    return [
      {
        ordinal: "01",
        name: "Deploy",
        color: "var(--domain-deployment)",
        aiMetric: "Radiologists deployed",
        ...deploy,
      },
      { ordinal: "02", name: "Use", color: "var(--domain-utilization)", aiMetric: "Adoption rate", ...use },
      {
        ordinal: "03",
        name: "Perform",
        color: "var(--domain-efficiency)",
        aiMetric: "Efficiency vs pre-Mosaic baseline",
        headline: fmtSigned(eff?.pct_change_vs_baseline),
        caption: "efficiency vs the legacy system",
        detail: `${eff?.mosaic_tbwu_per_min?.toFixed(3) ?? "—"} TBWU/min on Mosaic against a ${
          eff?.baseline_tbwu_per_min?.toFixed(3) ?? "—"
        } baseline.`,
      },
      {
        ordinal: "04",
        name: "Return",
        color: "var(--domain-capacity)",
        aiMetric: "Read-time change vs baseline",
        headline: fmtSigned(eff?.read_time_change_pct),
        caption: "read time per exam",
        detail:
          eff?.read_time_change_pct !== null && eff?.read_time_change_pct !== undefined && eff.read_time_change_pct < 0
            ? "Negative is time handed back to the radiologist."
            : "Measured against the same pre-Mosaic baseline window.",
      },
    ];
  }, [intelligence.data, capture.data, efficiency.data, cells, solution]);

  // The two leaks, as differences between three stored measures rather than a modelled funnel.
  const leakToUse =
    totalExams !== null && mosaicExams !== null
      ? { count: totalExams - mosaicExams, share: totalExams > 0 ? (totalExams - mosaicExams) / totalExams : null }
      : null;
  const leakToPerform =
    solution === "capture"
      ? capture.data && capture.data.capturable_exams_enabled > 0
        ? {
            count: capture.data.capturable_exams_enabled - capture.data.captured_exams_enabled,
            share:
              (capture.data.capturable_exams_enabled - capture.data.captured_exams_enabled) /
              capture.data.capturable_exams_enabled,
          }
        : null
      : mosaicExams !== null && draftingExams !== null
        ? { count: mosaicExams - draftingExams, share: mosaicExams > 0 ? (mosaicExams - draftingExams) / mosaicExams : null }
        : null;

  const anyError = intelligence.error || cube.error || efficiency.error;

  const controlStyle: React.CSSProperties = {
    background: "var(--surface-raised)",
    color: "var(--text-primary)",
    border: "var(--glass-border)",
    borderRadius: "var(--radius-sm, 6px)",
    padding: "6px 10px",
    fontSize: 13,
  };

  return (
    <div
      style={{
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        flex: 1,
        minWidth: 0,
        minHeight: 0,
        overflowY: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>Command</div>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 2 }}>
            What Mosaic has been deployed to, what runs through it, and what comes back — against the system it replaced.
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)" }}>
          Window
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={controlStyle}>
            {WINDOWS.map((w) => (
              <option key={w.months} value={w.months}>
                {w.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* The solution axis of the cube, as a control. Switching it re-asks all four stages of
          the same question against one solution instead of the product as a whole. */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {SOLUTIONS.map((s) => {
          const isActive = s.key === solution;
          return (
            <button
              key={s.key}
              onClick={() => setSolution(s.key)}
              style={{
                padding: "7px 14px",
                borderRadius: 999,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                background: isActive ? s.color : "var(--surface-1)",
                color: isActive ? "var(--page-plane)" : "var(--text-secondary)",
                border: isActive ? `1px solid ${s.color}` : "var(--glass-border)",
              }}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({anyError})
        </div>
      )}

      {/*
        Never wraps. A wrapped value chain puts the last stage on its own line behind an
        arrow pointing at nothing, which reads as a broken layout rather than as a chain.
        Narrow viewports scroll the chain sideways instead - the left-to-right order is the
        argument the page is making, so it is the one thing that cannot be allowed to break.
      */}
      {/*
        flexShrink: 0 is load-bearing, not tidying. This is a flex item in the page's column,
        and the page column scrolls - so with the default shrink factor the browser resolves
        the overflow by squashing the chain to a sliver rather than by scrolling the page,
        and the stage cards render as four coloured lines.
      */}
      <div style={{ overflowX: "auto", maxWidth: "100%", paddingBottom: 6, flexShrink: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            flexWrap: "nowrap",
            gap: 4,
          }}
        >
        <StageCard stage={stages[0]} />
        <Connector
          value={leakToUse?.share !== null && leakToUse?.share !== undefined ? fmtPct(leakToUse.share, 0) : "—"}
          label={`${fmtInt(leakToUse?.count)} exams never reached Mosaic`}
          tone="leak"
        />
        <StageCard stage={stages[1]} />
        <Connector
          value={leakToPerform?.share !== null && leakToPerform?.share !== undefined ? fmtPct(leakToPerform.share, 0) : "—"}
          label={
            solution === "capture"
              ? `${fmtInt(leakToPerform?.count)} capturable exams not captured`
              : `${fmtInt(leakToPerform?.count)} Mosaic exams read without drafting`
          }
          tone="leak"
        />
        <StageCard stage={stages[2]} />
        <Connector value="→" label="faster reading, converted into time" tone="convert" />
          <StageCard stage={stages[3]} />
        </div>
      </div>

      {/* The chain ends in a number somebody has to work. This is the hand-off to Cockpit, and
          it is the only call to action on the page. */}
      {actions.data && actions.data.actions.length > 0 && (
        <div
          style={{
            ...CARD_STYLE,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            borderLeft: "3px solid var(--color-primary)",
          }}
        >
          <div style={{ fontSize: 14 }}>
            <strong style={{ fontWeight: 600 }}>
              {actions.data.total_expected_unlock_tbwu >= 1000
                ? `${(actions.data.total_expected_unlock_tbwu / 1000).toFixed(1)}k`
                : actions.data.total_expected_unlock_tbwu.toFixed(0)}{" "}
              TBWU
            </strong>{" "}
            of that leakage is addressable today, across {actions.data.actions.length} teams.
          </div>
          <Link
            to="/cockpit"
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--page-plane)",
              background: "var(--color-primary)",
              padding: "8px 16px",
              borderRadius: 6,
              textDecoration: "none",
            }}
          >
            Open the worklist
          </Link>
        </div>
      )}

      {briefing.data && (briefing.data.key_insights || briefing.data.focus_next_week) && (
        <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>This week</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Week ending {briefing.data.week_ending}</div>
          </div>
          {briefing.data.key_insights && (
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>{briefing.data.key_insights}</div>
          )}
          {briefing.data.focus_next_week && (
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              <span style={{ color: "var(--text-muted)" }}>Next week: </span>
              {briefing.data.focus_next_week}
            </div>
          )}
        </div>
      )}

      {filteredTrend.length > 0 && (
        <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Adoption over time</div>
          <RpceTrendChart data={filteredTrend} />
        </div>
      )}

      {/*
        The same "not absorbed yet" row Explore carries. Mosaic Intelligence and Mosaic Pulse
        leave the tab bar here but keep their routes: the per-radiologist summary table, the
        enablement-blocker breakdown, the full rad survey and the adoption tree are all answers
        this chain does not give, and retiring the URLs would delete them.
      */}
      <div style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span>Deeper views:</span>
        <Link to="/intelligence" style={{ color: "var(--text-secondary)" }}>
          Mosaic Intelligence
        </Link>
        <Link to="/pulse" style={{ color: "var(--text-secondary)" }}>
          Mosaic Pulse
        </Link>
        <Link to="/explore" style={{ color: "var(--text-secondary)" }}>
          Explore the cube
        </Link>
      </div>
    </div>
  );
}
