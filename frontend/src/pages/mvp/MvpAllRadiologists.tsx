import { Fragment, useMemo, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { Badge } from "../../components/Badge";
import { StatTile } from "../../components/StatTile";
import { AIHoverCard } from "../../components/AIHoverCard";
import { Drawer } from "../../components/Drawer";
import { CARD_STYLE } from "../../styles/glassCard";
import { FilterBar } from "../../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../../context/FilterContext";
import { journeyPosition, journeyLabel, computeJourneyCounts } from "../../utils/mvpDashboardStats";
import type { JourneyStage } from "../../utils/mvpDashboardStats";
import type { MvpRadiologistItem } from "../../api/types";

function fmtPctRaw(value: number | null | undefined): string {
  // MVP's own efficiency-change figures already arrive as percentage units (e.g. -5.32 meaning
  // -5.32%), unlike the rest of the app's fraction-based fmtPct() - do not re-multiply by 100.
  return value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function fmtNum(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

const COHORT_COLORS: Record<string, string> = {
  "Cohort 1": "var(--status-critical)",
  "Cohort 2": "var(--status-warning)",
  "Cohort 3": "var(--domain-deployment)",
  "Cohort 4": "var(--text-secondary)",
};

function cohortColor(cohort: string): string {
  for (const [prefix, color] of Object.entries(COHORT_COLORS)) {
    if (cohort.startsWith(prefix)) return color;
  }
  return "var(--text-secondary)";
}

type PriorityTier = "Priority 1" | "Priority 2" | "Priority 3" | null;

const PRIORITY_COLORS: Record<string, string> = {
  "Priority 1": "var(--status-critical)",
  "Priority 2": "var(--status-warning)",
  "Priority 3": "var(--domain-deployment)",
};

// The real Mosaic Mentors / peer-coach "Matching Status" progression (see
// app/data/mvp_mentor_matching.py), not a severity scale - color reads left-to-right as "how far
// along", not "good vs. bad".
const MENTOR_MATCH_COLORS: Record<string, string> = {
  "Sourcing Mentor": "var(--status-warning)",
  "Mentor Proposal Sent": "var(--status-warning)",
  "Mentorship Introduction Sent": "var(--domain-deployment)",
  "Mentorship Scheduled": "var(--domain-deployment)",
  "Post-Mentorship Monitoring": "var(--status-good)",
  Closed: "var(--text-muted)",
};

// Same reading as MENTOR_MATCH_COLORS above: progression, not severity. Step 1 is not a problem
// and step 5 is not a reward - the ramp just says how far along the engagement is.
const JOURNEY_COLORS: Record<JourneyStage, string> = {
  Identify: "var(--text-muted)",
  Engage: "var(--status-warning)",
  Address: "var(--domain-deployment)",
  Monitor: "var(--domain-capture)",
  Resolve: "var(--status-good)",
};

// Derived approximation of the MVP deck's own qualitative Priority 1/2/3 definitions (see
// mvp_context.PRIORITY_TIER_DEFINITIONS) - the deck never codified an exact formula, so this
// picks defensible stand-ins: productivity = percentile rank of baseline capacity across the
// active cohort (top third = "high"), and the modality thresholds reuse the exact ~20%/~37%
// figures already cited in PROGRAM_NARRATIVE. Mirrored exactly in
// ai_context_service._priority_tier_counts() on the backend (used only to ground the precomputed
// program narrative) - there's no shared code between the two runtimes, so keep both in sync by
// hand if either threshold ever changes.
function computePriorities(rows: MvpRadiologistItem[]): Map<number, PriorityTier> {
  const active = rows.filter((r) => !r.exclusion_reason && r.baseline_capacity_tbwu_9h != null);
  const ranked = [...active].sort((a, b) => (b.baseline_capacity_tbwu_9h ?? 0) - (a.baseline_capacity_tbwu_9h ?? 0));
  const highCutoff = Math.ceil(ranked.length / 3);
  const highNpis = new Set(ranked.slice(0, highCutoff).map((r) => r.npi));

  const result = new Map<number, PriorityTier>();
  for (const r of rows) {
    if (r.exclusion_reason || r.baseline_capacity_tbwu_9h == null) {
      result.set(r.npi, null);
      continue;
    }
    const isHigh = highNpis.has(r.npi);
    const dc = r.drafting_captured_efficiency_change_pct;
    const lowOrNegativeDC = dc != null && dc < 5;
    const veryNegativeModality =
      (r.xr_drafting_efficiency_change_pct != null && r.xr_drafting_efficiency_change_pct < -20) ||
      (r.ct_head_efficiency_change_pct != null && r.ct_head_efficiency_change_pct < -20) ||
      (r.us_capture_efficiency_change_pct != null && r.us_capture_efficiency_change_pct < -37);

    let tier: PriorityTier = null;
    if (isHigh && lowOrNegativeDC) tier = "Priority 1";
    else if (!isHigh && lowOrNegativeDC) tier = "Priority 2";
    else if (veryNegativeModality) tier = "Priority 3";
    result.set(r.npi, tier);
  }
  return result;
}

function NotesDrawerContent({ radiologist }: { radiologist: MvpRadiologistItem }) {
  const summary = useFetch(
    () =>
      radiologist.optimization_support_notes
        ? mosaicApi.getAiContext({
            feature: "mvp_notes_summary",
            entity_label: radiologist.radiologist_name ?? `NPI ${radiologist.npi}`,
            metric_label: "Case note summary",
            value: radiologist.optimization_support_notes,
          })
        : Promise.resolve({ explanation: "" }),
    [radiologist.npi]
  );

  const sectionLabelStyle = {
    color: "var(--text-muted)",
    fontSize: 11,
    textTransform: "uppercase" as const,
    letterSpacing: 0.5,
    marginBottom: 6,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {radiologist.optimization_support_notes && (
        <>
          <div>
            <div style={sectionLabelStyle}>✨ AI-generated summary</div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
              {summary.loading ? "Thinking…" : summary.data?.explanation ?? "No summary available."}
            </div>
          </div>
          <div>
            <div style={sectionLabelStyle}>Raw case-note history</div>
            <div style={{ fontSize: 13, whiteSpace: "pre-wrap", color: "var(--text-primary)", lineHeight: 1.5 }}>
              {radiologist.optimization_support_notes}
            </div>
          </div>
        </>
      )}
      {radiologist.mentor_match && (
        <div>
          <div style={sectionLabelStyle}>Mosaic Mentors / peer-coach matching</div>
          <div style={{ marginBottom: 6 }}>
            <Badge
              label={radiologist.mentor_match.matching_status}
              color={MENTOR_MATCH_COLORS[radiologist.mentor_match.matching_status] ?? "var(--text-secondary)"}
            />
          </div>
          {radiologist.mentor_match.mentors_identified && (
            <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6 }}>
              <strong style={{ color: "var(--text-primary)" }}>Candidate mentor(s):</strong>{" "}
              <span style={{ whiteSpace: "pre-wrap" }}>{radiologist.mentor_match.mentors_identified}</span>
            </div>
          )}
          {radiologist.mentor_match.matching_notes && (
            <div style={{ fontSize: 13, whiteSpace: "pre-wrap", color: "var(--text-primary)", lineHeight: 1.5 }}>
              {radiologist.mentor_match.matching_notes}
            </div>
          )}
        </div>
      )}
      {radiologist.utilization_plan_notes && (
        <div>
          <div style={sectionLabelStyle}>Utilization plan notes</div>
          <div style={{ fontSize: 13, whiteSpace: "pre-wrap", color: "var(--text-primary)", lineHeight: 1.5 }}>
            {radiologist.utilization_plan_notes}
          </div>
        </div>
      )}
    </div>
  );
}

export function MvpAllRadiologists() {
  const filters = useFilters();
  const [showExcluded, setShowExcluded] = useState(false);
  const [showLearnMore, setShowLearnMore] = useState(false);
  const [notesTarget, setNotesTarget] = useState<MvpRadiologistItem | null>(null);
  const [tierFilter, setTierFilter] = useState<PriorityTier>(null);
  const [cohortFilter, setCohortFilter] = useState<string | null>(null); // null = all, "" = excluded only
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);
  const context = useFetch(() => mosaicApi.getMvpContext(), []);

  const priorities = useMemo(() => computePriorities(radiologists.data ?? []), [radiologists.data]);

  const priorityCounts = useMemo(() => {
    const counts: Record<string, number> = { "Priority 1": 0, "Priority 2": 0, "Priority 3": 0 };
    for (const tier of priorities.values()) {
      if (tier) counts[tier] += 1;
    }
    return counts;
  }, [priorities]);

  const practices = useMemo(() => {
    if (!radiologists.data) return [];
    return Array.from(new Set(radiologists.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [radiologists.data]);

  const filteredRows = useMemo(() => {
    if (!radiologists.data) return [];
    return radiologists.data.filter((r) => {
      if (!showExcluded && r.exclusion_reason) return false;
      if (!matchesPractice(filters, r.practice)) return false;
      if (!matchesRadiologistSearch(filters, r.radiologist_name, r.npi)) return false;
      if (tierFilter && priorities.get(r.npi) !== tierFilter) return false;
      if (cohortFilter === "") {
        if (!r.exclusion_reason) return false;
      } else if (cohortFilter) {
        if (r.exclusion_reason || r.mvp_cohort !== cohortFilter) return false;
      }
      return true;
    });
  }, [radiologists.data, filters, showExcluded, tierFilter, cohortFilter, priorities]);

  const cohortCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    let excluded = 0;
    for (const r of radiologists.data ?? []) {
      if (r.exclusion_reason) {
        excluded += 1;
      } else if (r.mvp_cohort) {
        counts[r.mvp_cohort] = (counts[r.mvp_cohort] ?? 0) + 1;
      }
    }
    return { counts, excluded };
  }, [radiologists.data]);

  // Counted across the whole roster, not the filtered view, so the "N rads are also here"
  // context on a hover means the same thing no matter which filters happen to be on.
  const journeyCounts = useMemo(() => computeJourneyCounts(radiologists.data ?? []), [radiologists.data]);

  const columns: DataTableColumn<MvpRadiologistItem>[] = [
    { key: "radiologist_name", label: "Radiologist" },
    { key: "practice", label: "Practice" },
    {
      key: "priority",
      label: "Priority",
      render: (r) => {
        const tier = priorities.get(r.npi);
        if (!tier) return "—";
        return (
          <AIHoverCard
            feature="mvp_priority"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Derived MVP priority tier"
            value={tier}
            extra={{
              baseline_capacity_tbwu_9h: fmtNum(r.baseline_capacity_tbwu_9h),
              drafting_captured_efficiency_change_pct: fmtPctRaw(r.drafting_captured_efficiency_change_pct),
            }}
          >
            <Badge label={tier} color={PRIORITY_COLORS[tier]} />
          </AIHoverCard>
        );
      },
    },
    {
      key: "mvp_cohort",
      label: "Cohort / Exclusion",
      render: (r) =>
        r.exclusion_reason ? (
          <AIHoverCard
            feature="mvp_exclusion"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Exclusion reason"
            value={r.exclusion_reason}
            // The glossary is the program's own wording for this reason code. Passing it as
            // `extra` means the model explains the documented meaning rather than guessing one
            // from a ten-character label; when the code isn't in the glossary we send nothing
            // rather than a placeholder, so the hover degrades to the label alone.
            extra={
              context.data?.exclusion_reason_glossary?.[r.exclusion_reason]
                ? { definition: context.data.exclusion_reason_glossary[r.exclusion_reason] }
                : undefined
            }
          >
            <Badge label={r.exclusion_reason} color="var(--text-muted)" />
          </AIHoverCard>
        ) : r.mvp_cohort ? (
          <AIHoverCard
            feature="mvp_cohort"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="MVP cohort"
            value={r.mvp_cohort}
            extra={{ baseline_capacity: String(r.baseline_capacity_tbwu_9h ?? "unknown") }}
          >
            <Badge label={r.mvp_cohort} color={cohortColor(r.mvp_cohort)} />
          </AIHoverCard>
        ) : (
          "—"
        ),
    },
    {
      key: "baseline_capacity_tbwu_9h",
      label: "Baseline Capacity (TBWU/9h)",
      render: (r) =>
        r.baseline_capacity_tbwu_9h == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_capacity"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Baseline capacity (TBWU/9h shift)"
            value={fmtNum(r.baseline_capacity_tbwu_9h)}
          >
            {fmtNum(r.baseline_capacity_tbwu_9h)}
          </AIHoverCard>
        ),
    },
    {
      key: "full_mosaic_efficiency_change_pct",
      label: "Full Mosaic Eff. Δ",
      render: (r) =>
        r.full_mosaic_efficiency_change_pct == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_efficiency_change"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Full Mosaic efficiency change vs. May-Jul 2026 baseline"
            value={fmtPctRaw(r.full_mosaic_efficiency_change_pct)}
            extra={{ last_30d: fmtPctRaw(r.full_mosaic_change_l30d_pct) }}
          >
            {fmtPctRaw(r.full_mosaic_efficiency_change_pct)}
          </AIHoverCard>
        ),
    },
    {
      key: "xr_drafting_efficiency_change_pct",
      label: "XR Drafting Δ",
      render: (r) =>
        r.xr_drafting_efficiency_change_pct == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_efficiency_change"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="XR Drafting efficiency change vs. May-Jul 2026 baseline"
            value={fmtPctRaw(r.xr_drafting_efficiency_change_pct)}
          >
            {fmtPctRaw(r.xr_drafting_efficiency_change_pct)}
          </AIHoverCard>
        ),
    },
    {
      key: "ct_head_efficiency_change_pct",
      label: "CT Head Δ",
      render: (r) =>
        r.ct_head_efficiency_change_pct == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_efficiency_change"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="CT Head efficiency change vs. May-Jul 2026 baseline"
            value={fmtPctRaw(r.ct_head_efficiency_change_pct)}
          >
            {fmtPctRaw(r.ct_head_efficiency_change_pct)}
          </AIHoverCard>
        ),
    },
    {
      key: "us_capture_efficiency_change_pct",
      label: "US Capture Δ",
      render: (r) =>
        r.us_capture_efficiency_change_pct == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_efficiency_change"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="US Capture efficiency change vs. May-Jul 2026 baseline"
            value={fmtPctRaw(r.us_capture_efficiency_change_pct)}
          >
            {fmtPctRaw(r.us_capture_efficiency_change_pct)}
          </AIHoverCard>
        ),
    },
    {
      // efficiency_change_last_30d_pct is confirmed live (2026-10-21) to be 100% NULL across
      // the entire MVP population - full_mosaic_change_l30d_pct is the rolling figure that's
      // actually populated and serves the same "current rolling efficiency" role.
      key: "full_mosaic_change_l30d_pct",
      label: "Eff. Δ (Last 30d)",
      render: (r) =>
        r.full_mosaic_change_l30d_pct == null ? (
          "—"
        ) : (
          <AIHoverCard
            feature="mvp_efficiency_change"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Full Mosaic efficiency change, last 30 days (rolling)"
            value={fmtPctRaw(r.full_mosaic_change_l30d_pct)}
            extra={{ full_mosaic_vs_fixed_baseline: fmtPctRaw(r.full_mosaic_efficiency_change_pct) }}
          >
            {fmtPctRaw(r.full_mosaic_change_l30d_pct)}
          </AIHoverCard>
        ),
    },
    { key: "mvp_target_outreach_week", label: "Target Outreach Week", render: (r) => r.mvp_target_outreach_week ?? "—" },
    { key: "mosaic_mentor", label: "Mentor", render: (r) => r.mosaic_mentor ?? "—" },
    {
      key: "journey",
      label: "MVP Journey",
      render: (r) => {
        const pos = journeyPosition(r);
        const label = journeyLabel(pos);
        return (
          <AIHoverCard
            feature="mvp_journey"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Position in the 5-step MVP engagement process"
            value={label}
            // The raw status is the evidence for the step, and the cohort size is the only
            // thing that makes a step number mean anything on its own.
            extra={{
              support_status: pos.detail,
              rads_at_this_step: pos.stage ? String(journeyCounts[pos.stage]) : "n/a",
            }}
          >
            <Badge label={label} color={pos.stage ? JOURNEY_COLORS[pos.stage] : "var(--text-muted)"} />
          </AIHoverCard>
        );
      },
    },
    { key: "optimization_support_status", label: "Support Status", render: (r) => r.optimization_support_status ?? "—" },
    {
      key: "mentor_match",
      label: "Mentor Match",
      render: (r) =>
        r.mentor_match ? (
          <AIHoverCard
            feature="mvp_mentor_match"
            entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
            metricLabel="Peer-coach matching status"
            value={r.mentor_match.matching_status}
            extra={r.mentor_match.mentors_identified ? { candidate_mentors: r.mentor_match.mentors_identified } : undefined}
          >
            <Badge label={r.mentor_match.matching_status} color={MENTOR_MATCH_COLORS[r.mentor_match.matching_status] ?? "var(--text-secondary)"} />
          </AIHoverCard>
        ) : (
          "—"
        ),
    },
    {
      key: "notes",
      label: "Notes",
      render: (r) =>
        r.optimization_support_notes || r.mentor_match ? (
          <button
            onClick={() => setNotesTarget(r)}
            title="View case-note history, mentor-match status, and AI summary"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: 13,
              padding: "2px 4px",
              transition: "color var(--dur-card) var(--ease-standard)",
            }}
          >
            📝 View
          </button>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {(radiologists.error || context.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({radiologists.error ?? context.error})
        </div>
      )}

      {context.data && (
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            ✨ AI-generated summary — refreshes every 30 min
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{context.data.ai_generated_narrative}</div>
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {(["Priority 1", "Priority 2", "Priority 3"] as const).map((tier) => (
          <AIHoverCard
            key={tier}
            feature="mvp_priority"
            entityLabel="Enterprise-wide"
            metricLabel={`${tier} - radiologist count`}
            value={String(priorityCounts[tier])}
            extra={
              context.data?.priority_tier_definitions?.[tier]
                ? { deck_definition: context.data.priority_tier_definitions[tier] }
                : undefined
            }
            underline={false}
            style={{ flex: "1 1 200px", minWidth: 180 }}
          >
            <StatTile
              label={tier}
              value={String(priorityCounts[tier])}
              accent={PRIORITY_COLORS[tier]}
              active={tierFilter === tier}
              onClick={() => setTierFilter((cur) => (cur === tier ? null : tier))}
              title="Click to filter the table to this priority tier"
            />
          </AIHoverCard>
        ))}
        {tierFilter && (
          <button
            onClick={() => setTierFilter(null)}
            style={{
              alignSelf: "center",
              fontSize: 12,
              padding: "6px 14px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Clear tier filter
          </button>
        )}
      </div>

      {/* computePriorities() above is an approximation - the deck defined these three tiers in
          words and never codified a formula. Printing the deck's own wording next to the counts
          is what lets a reader see the gap instead of taking the tile at face value. */}
      {context.data?.priority_tier_definitions && (
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
            How the program defines each priority
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {Object.entries(context.data.priority_tier_definitions).map(([tier, definition]) => (
              <div key={tier} style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
                <span style={{ color: PRIORITY_COLORS[tier] ?? "var(--text-secondary)", fontSize: 12, fontWeight: 600, minWidth: 72 }}>
                  {tier}
                </span>
                <span style={{ color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.5 }}>{definition}</span>
              </div>
            ))}
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 10, fontStyle: "italic" }}>
            The tiles above apply a derived stand-in for these definitions, scored on the current roster rather than the
            deck's fixed May–Jul 2026 window — so the counts move and the definitions don't.
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <AIHoverCard
          feature="mvp_cohort"
          entityLabel="Enterprise-wide"
          metricLabel="Actively tracked MVP radiologists"
          value={String((radiologists.data?.length ?? 0) - cohortCounts.excluded)}
          extra={{ excluded: String(cohortCounts.excluded) }}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="Actively tracked" value={String((radiologists.data?.length ?? 0) - cohortCounts.excluded)} />
        </AIHoverCard>
        {Object.entries(cohortCounts.counts)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([cohort, count]) => (
            <AIHoverCard
              key={cohort}
              feature="mvp_cohort"
              entityLabel="Enterprise-wide"
              metricLabel={`${cohort} - radiologist count`}
              value={String(count)}
              underline={false}
              style={{ flex: "1 1 200px", minWidth: 180 }}
            >
              <StatTile
                label={cohort}
                value={String(count)}
                accent={cohortColor(cohort)}
                active={cohortFilter === cohort}
                onClick={() => setCohortFilter((cur) => (cur === cohort ? null : cohort))}
                title="Click to filter the table to this cohort"
              />
            </AIHoverCard>
          ))}
        <AIHoverCard
          feature="mvp_exclusion"
          entityLabel="Enterprise-wide"
          metricLabel="Excluded radiologist count"
          value={String(cohortCounts.excluded)}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="Excluded"
            value={String(cohortCounts.excluded)}
            accent="var(--text-muted)"
            active={cohortFilter === ""}
            onClick={() => {
              if (cohortFilter === "") {
                setCohortFilter(null);
              } else {
                setCohortFilter("");
                setShowExcluded(true);
              }
            }}
            title="Click to filter the table to excluded radiologists"
          />
        </AIHoverCard>
        {cohortFilter !== null && (
          <button
            onClick={() => setCohortFilter(null)}
            style={{
              alignSelf: "center",
              fontSize: 12,
              padding: "6px 14px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Clear cohort filter
          </button>
        )}
      </div>

      {context.data && (
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Engagement Capacity Plan
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12, fontStyle: "italic" }}>
            A staffing/timeline planning snapshot from the team's own {context.data.engagement_capacity_plan.source_date} calculator —
            not a live forecast. Its original target date ({context.data.engagement_capacity_plan.finish_by_date}) has passed (only{" "}
            {context.data.engagement_capacity_plan.engaged_by_finish_by_date} of{" "}
            {context.data.engagement_capacity_plan.realistic_target} would have been reached by then at current staffing), but its
            "if nobody is added" projected finish date below is still near-term. Shown for planning context, not reconciled against
            the live EDW counts above.
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 }}>
            <StatTile
              label="Radiologists on the list"
              value={String(context.data.engagement_capacity_plan.radiologists_on_list)}
            />
            <StatTile
              label="Team's own 'real target'"
              value={String(context.data.engagement_capacity_plan.realistic_target)}
            />
            <StatTile
              label="Weekly throughput (current team)"
              value={`${fmtNum(context.data.engagement_capacity_plan.throughput_per_week_current_team)}/wk`}
            />
            <StatTile
              label="People needed to hit target"
              value={`${context.data.engagement_capacity_plan.people_needed_at_full_col_hours} (+${context.data.engagement_capacity_plan.people_to_add} vs. today)`}
            />
            <StatTile
              label="Projected finish (if unaided)"
              value={context.data.engagement_capacity_plan.projected_finish_date_if_unaided}
            />
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{context.data.engagement_capacity_plan.summary}</div>
        </div>
      )}

      {context.data && (
        <div style={CARD_STYLE}>
          <button
            onClick={() => setShowLearnMore((v) => !v)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary)",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              padding: 0,
            }}
          >
            {showLearnMore ? "▾" : "▸"} Learn more about MVP
          </button>
          {showLearnMore && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 10 }}>{context.data.program_narrative}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>{context.data.program_history}</div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", fontStyle: "italic" }}>{context.data.current_status_notes}</div>

              {/* Every reason code observed live in rad_onboarding, in the program's own words.
                  These codes are the whole explanation for why the denominator is 392 and not
                  1,500, and until now they appeared only as a ten-character badge. */}
              {context.data.exclusion_reason_glossary && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
                    Why a radiologist is excluded ({Object.keys(context.data.exclusion_reason_glossary).length} reason codes)
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "minmax(170px, 220px) 1fr", gap: "6px 14px", alignItems: "baseline" }}>
                    {Object.entries(context.data.exclusion_reason_glossary).map(([reason, definition]) => (
                      <Fragment key={reason}>
                        <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600 }}>{reason}</span>
                        <span style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>{definition}</span>
                      </Fragment>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <FilterBar practices={practices} showMonth={false} showLocal={false} />

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-secondary)", cursor: "pointer" }}>
          <input type="checkbox" checked={showExcluded} onChange={(e) => setShowExcluded(e.target.checked)} />
          Show excluded radiologists
        </label>
      </div>

      <div style={CARD_STYLE}>
        {radiologists.data && (
          filteredRows.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No radiologists match the current filters.</div>
          ) : (
            <DataTable columns={columns} rows={filteredRows} rowKey={(r) => r.npi} />
          )
        )}
      </div>

      <Drawer
        open={notesTarget !== null}
        onClose={() => setNotesTarget(null)}
        title={notesTarget ? `Case notes — ${notesTarget.radiologist_name ?? `NPI ${notesTarget.npi}`}` : undefined}
      >
        {notesTarget && <NotesDrawerContent radiologist={notesTarget} />}
      </Drawer>
    </div>
  );
}
