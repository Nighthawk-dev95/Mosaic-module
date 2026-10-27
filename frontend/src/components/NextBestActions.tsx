import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { Badge } from "./Badge";
import { AIHoverCard } from "./AIHoverCard";
import type { NextBestAction } from "../api/types";

/**
 * The Drafting worklist: leakage ranked by the TBWU an operator could realistically unlock.
 *
 * The chart above this tells you *where* draftable volume leaks. It cannot tell you which leak
 * is worth someone's Tuesday, because the six categories are not equally actionable - a pile
 * sitting behind a model that does not cover the procedure is not work this list's owner can
 * do. So two of the six are excluded from the ranking and reported on the row instead.
 *
 * Three rendering decisions follow from that, and each one is load-bearing:
 *
 * **Expected unlock and gap-to-benchmark sit side by side, always.** The ordering is by
 * expected unlock, so a team four points behind the benchmark on an enormous book outranks one
 * sixty points behind on a small one. That is correct and reads as a bug until both numbers are
 * visible at once.
 *
 * **The benchmark is drawn on the rate bar, not just stated.** A rate is only a verdict
 * relative to something; drawing the peer frontier as a tick on each bar makes the headroom the
 * thing you see rather than a number you have to subtract.
 *
 * **The basis prose is rendered verbatim from the API.** It is built from the same values the
 * rows are, so it cannot drift from them - which paraphrasing it here would immediately allow.
 */

// Bars and chips use `--color-primary` / `--domain-*`, never `--accent`. `--accent` is defined
// in src/index.css, which main.tsx does not import - so it resolves to transparent and a bar
// painted with it renders as nothing at all. Checked live: the unlock bar came back
// `background-color: rgba(0, 0, 0, 0)`. `--domain-efficiency` for the workflow blocker matches
// `--undrafted-opened-over-5min`, the same leak in the chart directly above this list.
const BLOCKER_COLOR: Record<string, string> = {
  "Draftable - Rad Not Enrolled": "var(--status-warning)",
  "Draftable - Not Drafted (Workflow)": "var(--domain-efficiency)",
};

function fmt(n: number, digits = 0): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/**
 * This team's draft rate against the peer frontier, as one bar with a tick on it.
 *
 * The filled portion is what the team converts today; the tick is the benchmark; the gap
 * between them is the headroom the unlock number is computed from. Drawing all three in one
 * object is the point - three separate numbers in three columns is the same information and a
 * much worse answer to "how far behind is this team".
 */
function RateBar({ rate, benchmark }: { rate: number; benchmark: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          position: "relative",
          flex: 1,
          minWidth: 90,
          height: 8,
          borderRadius: 999,
          // --border, not --surface-raised: the card sits on --surface-1, against which
          // --surface-raised is nearly invisible in dark mode. The track has to read as an
          // empty bar or the fill has nothing to be a fraction of.
          background: "var(--border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: `${Math.min(100, Math.max(0, rate * 100))}%`,
            background: "var(--color-primary)",
            borderRadius: 999,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: -2,
            bottom: -2,
            left: `${Math.min(100, Math.max(0, benchmark * 100))}%`,
            width: 2,
            background: "var(--text-primary)",
          }}
          title={`Peer benchmark ${(benchmark * 100).toFixed(0)}%`}
        />
      </div>
      <span style={{ fontSize: 12, color: "var(--text-secondary)", width: 36, textAlign: "right" }}>
        {(rate * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function ActionRow({ row, benchmark, maxUnlock }: { row: NextBestAction; benchmark: number; maxUnlock: number }) {
  const [open, setOpen] = useState(false);
  const color = BLOCKER_COLOR[row.primary_blocker] ?? "var(--text-secondary)";
  // Volume this list's owner cannot convert. Shown only when it is big enough to change the
  // conversation - otherwise it is noise on every row.
  const blocked = row.deployment_blocked_tbwu + row.procedure_not_covered_tbwu;
  const blockedIsMaterial = blocked > row.expected_unlock_tbwu * 0.25;

  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <div
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(140px, 1.4fr) minmax(170px, 1.6fr) minmax(120px, 1fr) 110px 24px",
          gap: 16,
          alignItems: "center",
          padding: "12px 4px",
          cursor: "pointer",
        }}
      >
        <div>
          <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: 13 }}>{row.team}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{fmt(row.gap_exams)} exams in the gap</div>
        </div>

        <div>
          <Badge label={row.action} color={color} dot />
          {blockedIsMaterial && (
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 4 }}>
              + {fmt(blocked)} TBWU blocked elsewhere — escalate, don't work
            </div>
          )}
        </div>

        <div>
          <RateBar rate={row.draft_rate} benchmark={benchmark} />
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 4 }}>
            {row.gap_to_benchmark_pct.toFixed(1)}pp behind peers
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: 15 }}>
            {fmt(row.expected_unlock_tbwu)}
          </div>
          <div
            style={{
              height: 3,
              marginTop: 4,
              borderRadius: 999,
              background: "var(--color-primary)",
              width: `${maxUnlock ? Math.max(4, (row.expected_unlock_tbwu / maxUnlock) * 100) : 0}%`,
              marginLeft: "auto",
            }}
          />
        </div>

        <div style={{ color: "var(--text-muted)", fontSize: 11, textAlign: "center" }}>{open ? "▾" : "▸"}</div>
      </div>

      {open && (
        <div
          style={{
            padding: "0 4px 14px 4px",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 12,
          }}
        >
          <div style={{ gridColumn: "1 / -1", color: "var(--text-secondary)", fontSize: 12 }}>{row.rationale}</div>
          {[
            ["Drafted", row.drafted_tbwu],
            ["Rad not enrolled", row.not_enrolled_tbwu],
            ["Enrolled, not drafted", row.workflow_gap_tbwu],
            ["Practice not enabled", row.deployment_blocked_tbwu],
            ["Procedure not covered", row.procedure_not_covered_tbwu],
            ["Not read on Mosaic", row.not_on_mosaic_tbwu],
          ].map(([label, value]) => (
            <div key={label as string}>
              <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{label}</div>
              <div style={{ fontSize: 13 }}>{fmt(value as number)} TBWU</div>
            </div>
          ))}
          {/* The taxonomy grounding sits here, on the six categories themselves, rather than on
              the header where it used to be. A reader expanding a row is asking what the
              categories mean; a reader hovering the headline is asking why the ranking is
              ordered as it is. Same page, two different questions, two different groundings. */}
          <div style={{ gridColumn: "1 / -1", color: "var(--text-muted)", fontSize: 11 }}>
            <AIHoverCard
              feature="non_drafted_reason"
              entityLabel={row.team}
              metricLabel={`Primary blocker: ${row.primary_blocker}`}
              value={`${(row.blocker_share_of_gap * 100).toFixed(0)}% of the draftable gap`}
              extra={{
                Drafted: fmt(row.drafted_tbwu),
                "Rad not enrolled": fmt(row.not_enrolled_tbwu),
                "Enrolled, not drafted": fmt(row.workflow_gap_tbwu),
                "Practice not enabled": fmt(row.deployment_blocked_tbwu),
                "Procedure not covered": fmt(row.procedure_not_covered_tbwu),
                "Not read on Mosaic": fmt(row.not_on_mosaic_tbwu),
              }}
            >
              {(row.blocker_share_of_gap * 100).toFixed(0)}% of this team's draftable gap sits behind{" "}
              {row.primary_blocker}
            </AIHoverCard>
            . The first three figures above are the rate's denominator; the next two are excluded from it
            and owned by deployment and the model roadmap respectively.
          </div>
        </div>
      )}
    </div>
  );
}

/** CSV, built here rather than server-side: the operator exports exactly the rows they're looking at. */
function toCsv(rows: NextBestAction[]): string {
  const headers = [
    "Team",
    "Action",
    "Primary blocker",
    "Expected unlock TBWU",
    "Draft rate",
    "Gap to benchmark (pp)",
    "Addressable TBWU",
    "Rad not enrolled TBWU",
    "Enrolled not drafted TBWU",
    "Gap exams",
    "Practice not enabled TBWU",
    "Procedure not covered TBWU",
  ];
  const lines = rows.map((r) =>
    [
      r.team,
      r.action,
      r.primary_blocker,
      r.expected_unlock_tbwu.toFixed(1),
      (r.draft_rate * 100).toFixed(1),
      r.gap_to_benchmark_pct.toFixed(1),
      r.addressable_tbwu.toFixed(1),
      r.not_enrolled_tbwu.toFixed(1),
      r.workflow_gap_tbwu.toFixed(1),
      String(r.gap_exams),
      r.deployment_blocked_tbwu.toFixed(1),
      r.procedure_not_covered_tbwu.toFixed(1),
      // A team name containing a comma or a quote would otherwise shift every column after it.
    ].map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
  );
  return [headers.join(","), ...lines].join("\n");
}

export function NextBestActions() {
  // p75 is "what three-quarters of your peers already beat" - ambitious enough to be worth
  // chasing, modest enough that someone has actually done it. Exposed because the right answer
  // is a judgement, and one buried in a constant is a judgement nobody can argue with.
  const [pctile, setPctile] = useState(0.75);
  const worklist = useFetch(() => mosaicApi.getNextBestActions({ benchmark_pctile: pctile }), [pctile]);
  const rows = worklist.data?.actions ?? [];
  const maxUnlock = useMemo(() => rows.reduce((m, r) => Math.max(m, r.expected_unlock_tbwu), 0), [rows]);

  const download = () => {
    const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mosaic-drafting-worklist-${worklist.data?.window_end ?? "export"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, flexWrap: "wrap", marginBottom: 4 }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div
            style={{
              color: "var(--text-muted)",
              fontSize: 13,
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            {/* `next_best_action`, not `non_drafted_reason`. The six leakage categories are the
                right grounding for the *breakdown* inside each expanded row, and they are used
                there. The figure here is the ranking total, and what someone challenges about it
                in a room is the peer frontier behind it - "why is this team first", not "what
                does Draftable - Not Drafted mean". The backend grounding for this key is composed
                from `next_best_action_service.METHODOLOGY`, the same constant the `basis` line at
                the foot of this panel is built around, so the tooltip and the printed basis
                cannot describe different rankings. */}
            <AIHoverCard
              feature="next_best_action"
              entityLabel="Enterprise-wide"
              metricLabel="Total expected unlock (TBWU)"
              value={fmt(worklist.data?.total_expected_unlock_tbwu ?? 0)}
              extra={Object.fromEntries(rows.slice(0, 8).map((r) => [r.team, fmt(r.expected_unlock_tbwu)]))}
            >
              Next best action — where to spend the week
            </AIHoverCard>
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 6 }}>
            Ranked by expected TBWU unlock against what comparable teams already achieve.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label style={{ color: "var(--text-muted)", fontSize: 11 }}>Benchmark</label>
          <select
            value={pctile}
            onChange={(e) => setPctile(Number(e.target.value))}
            style={{
              fontSize: 12,
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface-raised)",
              color: "var(--text-primary)",
            }}
          >
            <option value={0.5}>Median peer</option>
            <option value={0.75}>Top quartile</option>
            <option value={0.9}>Top decile</option>
          </select>
          <button
            onClick={download}
            disabled={!rows.length}
            style={{
              fontSize: 12,
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface-raised)",
              color: rows.length ? "var(--text-primary)" : "var(--text-muted)",
              cursor: rows.length ? "pointer" : "default",
            }}
          >
            Export worklist
          </button>
        </div>
      </div>

      {worklist.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13, marginTop: 12 }}>
          Couldn't load the worklist ({worklist.error})
        </div>
      )}
      {worklist.loading && (
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 12 }}>Ranking teams…</div>
      )}

      {!worklist.loading && !worklist.error && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(140px, 1.4fr) minmax(170px, 1.6fr) minmax(120px, 1fr) 110px 24px",
              gap: 16,
              padding: "10px 4px",
              marginTop: 10,
              borderBottom: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            <div>Team</div>
            <div>Action</div>
            <div>Draft rate vs peers</div>
            <div style={{ textAlign: "right" }}>Unlock (TBWU)</div>
            <div />
          </div>

          {rows.length === 0 && (
            <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "16px 4px" }}>
              No team is behind the {(pctile * 100).toFixed(0)}% peer benchmark with convertible volume. Raise the
              benchmark to see who is behind a more ambitious frontier.
            </div>
          )}

          {rows.map((r) => (
            <ActionRow
              key={r.team}
              row={r}
              benchmark={worklist.data?.benchmark_draft_rate ?? 0}
              maxUnlock={maxUnlock}
            />
          ))}

          {worklist.data && (
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 12, lineHeight: 1.6 }}>
              {/* Verbatim from the API - it is built from the same numbers as the rows, so any
                  rewording here is a chance for the prose and the ranking to disagree. */}
              {worklist.data.basis}
              {worklist.data.excluded_low_volume_teams > 0 && (
                <>
                  {" "}
                  {worklist.data.excluded_low_volume_teams} team
                  {worklist.data.excluded_low_volume_teams === 1 ? " was" : "s were"} held out of both the ranking
                  and the benchmark for having under {fmt(worklist.data.min_addressable_tbwu)} addressable TBWU.
                </>
              )}
              {worklist.data.undated_rows_skipped > 0 && (
                <>
                  {" "}
                  {fmt(worklist.data.undated_rows_skipped)} leakage rows carry no week and were excluded from the
                  window rather than counted in its most recent week.
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
