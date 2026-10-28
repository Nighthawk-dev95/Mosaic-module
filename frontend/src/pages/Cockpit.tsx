import { useMemo, useState } from "react";
import { useFetch } from "../hooks/useFetch";
import { mosaicApi } from "../api/client";
import type { NextBestAction } from "../api/types";
import { CARD_STYLE } from "../styles/glassCard";
import { AIHoverCard } from "../components/AIHoverCard";
import { BaselineReviewQueue } from "./BaselineReviewQueue";
import { MvpOverview } from "./mvp/MvpOverview";
import { MvpMentorship } from "./mvp/MvpMentorship";
import { MvpMammo } from "./mvp/MvpMammo";
import { MvpAreaDetail } from "./mvp/MvpAreaDetail";
import { MvpAllRadiologists } from "./mvp/MvpAllRadiologists";
import { MvpWeeklyReport } from "./mvp/MvpWeeklyReport";

/**
 * Cockpit - the operator surface.
 *
 * Command answers "how is the product doing"; Cockpit answers "what do I do about it". It
 * absorbs the MVP tab (and its six sub-tabs) and the Baseline Review Queue, and adds the
 * worklist those two were always missing: the leakage ranked by how much capacity working
 * it would actually unlock.
 *
 * The three modes are the three shapes operator work comes in - a queue to call through, a
 * cohort to coach, a decision to rule on - so the mode strip is the operator's day, not a
 * list of datasets.
 */

type Mode = "worklist" | "mvp" | "decisions";
type MvpSection = "overview" | "mentorship" | "mammo" | "area" | "all" | "weekly-report";

const MVP_SECTIONS: { key: MvpSection; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "mentorship", label: "Mentorship" },
  { key: "mammo", label: "Mammo Screening" },
  { key: "area", label: "Area Detail" },
  { key: "all", label: "All Radiologists" },
  { key: "weekly-report", label: "Weekly Report" },
];

/**
 * The six-category leakage taxonomy, in the order a team actually moves through it, and split
 * where the operator's authority ends.
 *
 * The first three are convertible by whoever works this list. The last three are not - they go
 * to a model owner, a procedure-coverage owner, or a deployment owner - and `NextBestAction`
 * deliberately carries them anyway so they can be escalated rather than silently disappearing
 * into "gap". Rendering them at reduced opacity behind a divider is how the bar says which is
 * which without a legend sentence.
 */
const SEGMENTS: { key: keyof NextBestAction; label: string; color: string; yours: boolean }[] = [
  { key: "drafted_tbwu", label: "Drafted", color: "var(--domain-utilization)", yours: true },
  { key: "not_enrolled_tbwu", label: "Rad not enrolled", color: "var(--domain-deployment)", yours: true },
  { key: "workflow_gap_tbwu", label: "Draftable, not drafted", color: "var(--domain-efficiency)", yours: true },
  { key: "deployment_blocked_tbwu", label: "Practice not enabled", color: "var(--domain-capacity)", yours: false },
  { key: "procedure_not_covered_tbwu", label: "Procedure not covered", color: "var(--domain-feedback)", yours: false },
  { key: "not_on_mosaic_tbwu", label: "Not read on Mosaic", color: "var(--text-muted)", yours: false },
];

const WEEK_CHOICES = [4, 8, 13, 26];
const PCTILE_CHOICES = [0.5, 0.75, 0.9];
const FLOOR_CHOICES = [100, 500, 1000];

function fmtTbwu(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toFixed(0);
}

function fmtPct(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined) return "—";
  return `${(fraction * 100).toFixed(1)}%`;
}

// `gap_to_benchmark_pct` arrives already scaled (next_best_action_service.py:225 returns
// `headroom * 100`), unlike `draft_rate` and `blocker_share_of_gap`, which are fractions. Running
// it through fmtPct scaled it a second time and rendered RP Bluegrass - 12.0% against a 77.4%
// benchmark - as "behind by 6536.8%". It is also a difference of two rates, so even correctly
// scaled it is percentage *points*, not a percentage; `pp` is the unit the sibling
// NextBestActions.tsx:136 already uses for the same field.
function fmtPp(points: number | null | undefined): string {
  if (points === null || points === undefined) return "—";
  return `${points.toFixed(1)}pp`;
}

function LeakageBar({ action }: { action: NextBestAction }) {
  const values = SEGMENTS.map((s) => ({ ...s, value: Number(action[s.key] ?? 0) || 0 }));
  const total = values.reduce((sum, v) => sum + v.value, 0);
  if (total <= 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", background: "var(--surface-1)" }}>
        {values
          .filter((v) => v.value > 0)
          .map((v) => (
            <div
              key={String(v.key)}
              title={`${v.label}: ${fmtTbwu(v.value)} TBWU (${fmtPct(v.value / total)})${v.yours ? "" : " - escalate, not yours to convert"}`}
              style={{
                width: `${(v.value / total) * 100}%`,
                background: v.color,
                opacity: v.yours ? 1 : 0.32,
                borderRight: v.yours ? "none" : "1px solid var(--page-plane)",
              }}
            />
          ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 11, color: "var(--text-muted)" }}>
        {values
          .filter((v) => v.value > 0)
          .map((v) => (
            <span key={String(v.key)} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  background: v.color,
                  opacity: v.yours ? 1 : 0.32,
                  flexShrink: 0,
                }}
              />
              {v.label} {fmtTbwu(v.value)}
            </span>
          ))}
      </div>
    </div>
  );
}

function ActionCard({ action, rank }: { action: NextBestAction; rank: number }) {
  return (
    <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "baseline", minWidth: 0 }}>
          <span style={{ fontSize: 13, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>{rank}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{action.team}</div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>{action.action}</div>
          </div>
        </div>
        <AIHoverCard
          feature="next_best_action"
          entityLabel={action.team}
          metricLabel="Expected unlock"
          value={`${fmtTbwu(action.expected_unlock_tbwu)} TBWU`}
          extra={{
            "Primary blocker": action.primary_blocker,
            "Draft rate": fmtPct(action.draft_rate),
            "Gap to benchmark": fmtPp(action.gap_to_benchmark_pct),
          }}
          underline={false}
        >
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontSize: 22, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
              {fmtTbwu(action.expected_unlock_tbwu)}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>TBWU to unlock</div>
          </div>
        </AIHoverCard>
      </div>

      <LeakageBar action={action} />

      <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{action.rationale}</div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 20px", fontSize: 12, color: "var(--text-muted)" }}>
        <span>
          Blocker <strong style={{ color: "var(--text-primary)", fontWeight: 600 }}>{action.primary_blocker}</strong>{" "}
          holds {fmtPct(action.blocker_share_of_gap)} of the gap
        </span>
        <span>Draft rate {fmtPct(action.draft_rate)}</span>
        <span>{fmtPp(action.gap_to_benchmark_pct)} behind the benchmark</span>
        <span>{action.gap_exams.toLocaleString()} exams</span>
      </div>
    </div>
  );
}

function Worklist({
  weeks,
  pctile,
  floor,
  onWeeks,
  onPctile,
  onFloor,
}: {
  weeks: number;
  pctile: number;
  floor: number;
  onWeeks: (n: number) => void;
  onPctile: (n: number) => void;
  onFloor: (n: number) => void;
}) {
  // Every parameter here is a lever on the benchmark, not on the data, so each one is a visible
  // control. The backend's own defaults apply only when nothing is passed - which is why these
  // three are seeded to those same defaults rather than to arbitrary values.
  const list = useFetch(
    () => mosaicApi.getNextBestActions({ weeks, benchmark_pctile: pctile, min_addressable_tbwu: floor }),
    [weeks, pctile, floor]
  );

  const selectStyle: React.CSSProperties = {
    background: "var(--surface-raised)",
    color: "var(--text-primary)",
    border: "var(--glass-border)",
    borderRadius: "var(--radius-sm, 6px)",
    padding: "6px 10px",
    fontSize: 13,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ ...CARD_STYLE, display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px 24px" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)" }}>
          Look back
          <select value={weeks} onChange={(e) => onWeeks(Number(e.target.value))} style={selectStyle}>
            {WEEK_CHOICES.map((w) => (
              <option key={w} value={w}>
                {w} weeks
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)" }}>
          Benchmark
          <select value={pctile} onChange={(e) => onPctile(Number(e.target.value))} style={selectStyle}>
            {PCTILE_CHOICES.map((p) => (
              <option key={p} value={p}>
                p{Math.round(p * 100)} of teams
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)" }}>
          Smallest book that sets it
          <select value={floor} onChange={(e) => onFloor(Number(e.target.value))} style={selectStyle}>
            {FLOOR_CHOICES.map((f) => (
              <option key={f} value={f}>
                {f.toLocaleString()} TBWU
              </option>
            ))}
          </select>
        </label>
      </div>

      {list.loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Ranking the leakage…</div>}
      {list.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({list.error})
        </div>
      )}

      {list.data && (
        <>
          <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
              <div style={{ fontSize: 26, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                {fmtTbwu(list.data.total_expected_unlock_tbwu)}
              </div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                TBWU across {list.data.actions.length} teams, if every team on this list reached the benchmark
              </div>
            </div>
            {/* Prose the backend builds from the same numbers it ranked on. Rendered verbatim - a
                paraphrase here would be a second, unversioned definition of the benchmark. */}
            <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>{list.data.basis}</div>
          </div>

          {list.data.actions.length === 0 ? (
            <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>
              No team is behind the p{Math.round(pctile * 100)} benchmark by enough to rank at this floor. Lower the
              floor or raise the benchmark to see the next tier.
            </div>
          ) : (
            list.data.actions.map((a, i) => <ActionCard key={a.team} action={a} rank={i + 1} />)
          )}
        </>
      )}
    </div>
  );
}

export function Cockpit() {
  const [mode, setMode] = useState<Mode>("worklist");
  const [mvpSection, setMvpSection] = useState<MvpSection>("overview");
  const [weeks, setWeeks] = useState(8);
  const [pctile, setPctile] = useState(0.75);
  const [floor, setFloor] = useState(500);

  // Counts for the mode strip. Both come from endpoints the modes themselves re-fetch, which is
  // one extra cached round-trip on load - paid deliberately, because an operator who has to open
  // a tab to find out whether there is work in it will stop opening it.
  const actions = useFetch(
    () => mosaicApi.getNextBestActions({ weeks, benchmark_pctile: pctile, min_addressable_tbwu: floor }),
    [weeks, pctile, floor]
  );
  const proxyDetail = useFetch(() => mosaicApi.getBaselineProxyDetail(), []);
  const decisions = useFetch(() => mosaicApi.getBaselineReviewDecisions(), []);

  const pendingDecisions = useMemo(() => {
    if (!proxyDetail.data || !decisions.data) return null;
    const ruled = new Set(decisions.data.map((d) => `${d.npi}|${d.target_shift}`));
    return proxyDetail.data.filter((r) => r.baseline_type === "Manual Review" && !ruled.has(`${r.npi}|${r.target_shift}`))
      .length;
  }, [proxyDetail.data, decisions.data]);

  const MODES: { key: Mode; label: string; hint: string; count: number | null }[] = [
    {
      key: "worklist",
      label: "Worklist",
      hint: "Teams ranked by the capacity working them would unlock",
      count: actions.data?.actions.length ?? null,
    },
    { key: "mvp", label: "Mosaic Value Project", hint: "Cohorts, mentorship, and the Friday report", count: null },
    {
      key: "decisions",
      label: "Baseline decisions",
      hint: "Proxy baselines waiting on a human ruling",
      count: pendingDecisions,
    },
  ];

  const active = MODES.find((m) => m.key === mode);

  return (
    <div
      style={{
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        flex: 1,
        minHeight: 0,
        overflowY: "auto",
      }}
    >
      <div>
        <div style={{ fontSize: 20, fontWeight: 600 }}>Cockpit</div>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 2 }}>
          {active?.hint ?? "The operator surface: who to call, who to coach, what to rule on."}
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {MODES.map((m) => {
          const isActive = m.key === mode;
          return (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              style={{
                ...CARD_STYLE,
                padding: "12px 18px",
                cursor: "pointer",
                textAlign: "left",
                display: "flex",
                alignItems: "center",
                gap: 12,
                border: isActive ? "1px solid var(--color-primary)" : "var(--glass-border)",
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                fontSize: 14,
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {m.label}
              {m.count !== null && (
                <span
                  style={{
                    fontSize: 12,
                    fontVariantNumeric: "tabular-nums",
                    padding: "2px 8px",
                    borderRadius: 10,
                    background: isActive ? "var(--color-primary)" : "var(--surface-raised)",
                    color: isActive ? "var(--page-plane)" : "var(--text-muted)",
                  }}
                >
                  {m.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {mode === "worklist" && (
        <Worklist
          weeks={weeks}
          pctile={pctile}
          floor={floor}
          onWeeks={setWeeks}
          onPctile={setPctile}
          onFloor={setFloor}
        />
      )}

      {mode === "mvp" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", gap: 2, flexWrap: "wrap", borderBottom: "1px solid var(--border)" }}>
            {MVP_SECTIONS.map((s) => (
              <button
                key={s.key}
                onClick={() => setMvpSection(s.key)}
                style={{
                  background: "none",
                  border: "none",
                  borderBottom:
                    mvpSection === s.key ? "2px solid var(--rp-moss, var(--domain-deployment))" : "2px solid transparent",
                  color: mvpSection === s.key ? "var(--text-primary)" : "var(--text-secondary)",
                  fontWeight: mvpSection === s.key ? 600 : 400,
                  padding: "8px 14px",
                  fontSize: 13,
                  cursor: "pointer",
                  marginBottom: -1,
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
          {mvpSection === "overview" && <MvpOverview />}
          {mvpSection === "mentorship" && <MvpMentorship />}
          {mvpSection === "mammo" && <MvpMammo />}
          {mvpSection === "area" && <MvpAreaDetail />}
          {mvpSection === "all" && <MvpAllRadiologists />}
          {mvpSection === "weekly-report" && <MvpWeeklyReport />}
        </div>
      )}

      {/* BaselineReviewQueue brings its own page padding. Cancelling it with a negative margin
          keeps the queue flush with the mode strip instead of indenting one surface inside
          another, without forking the component for a second caller. */}
      {mode === "decisions" && (
        <div style={{ margin: "-24px -24px 0" }}>
          <BaselineReviewQueue />
        </div>
      )}
    </div>
  );
}
