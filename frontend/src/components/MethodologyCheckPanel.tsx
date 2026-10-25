import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { CARD_STYLE } from "../styles/glassCard";

// Honest, live-recomputed checks on whether the Impact section's before/after comparison can
// actually be trusted - see backend/app/data/mvp_methodology_checks.py's own docstring for the
// three specific things these numbers check and why. This panel's job is to tell a viewer what
// the data can and can't support, not to make the Impact bucket counts look more authoritative
// than a rigorous read of this exact data supports (confirmed live 2026-10-22 - see
// declarative-dancing-willow.md's "methodology-check panel" plan for the full investigation).

function fmtPct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(digits)}%`;
}

function fmtSignedPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

const FIELD_LABELS: Record<string, string> = {
  drafting_captured_efficiency_change_pct: "Baseline D&C Eff. Δ",
  full_mosaic_change_l30d_pct: "Post-Engagement Eff. Δ (L30D)",
};

export function MethodologyCheckPanel({ scope }: { scope: "overview" | "mammo" }) {
  const check = useFetch(() => mosaicApi.getMvpMethodologyCheck(scope), [scope]);

  if (!check.data) return null;

  const { outlier_summary, outreach_week_reliability, baseline_severity_by_stage } = check.data;
  const stageOrder = ["Outreached", "Scheduled", "Solutioning", "Monitoring", "Closed"];

  return (
    <div style={CARD_STYLE}>
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
        Methodology Check: Can You Trust This Comparison?
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 12, fontStyle: "italic" }}>
        What a rigorous read of this exact data can and can't currently support - not a hidden caveat, the actual limitation.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13, color: "var(--text-secondary)" }}>
        <div>
          <strong style={{ color: "var(--text-primary)" }}>{outlier_summary.total_radiologists_affected}</strong> of{" "}
          {outlier_summary.total_radiologists} radiologists had an implausible (greater than 100% magnitude) efficiency-change
          value
          {Object.entries(outlier_summary.per_field)
            .filter(([, n]) => n > 0)
            .map(([field, n]) => ` (${FIELD_LABELS[field] ?? field}: ${n})`)
            .join("")}
          {" "}and are excluded from the Impact buckets above as insufficient data, not counted as improved or not.
        </div>

        <div>
          {outreach_week_reliability.contamination_rate === null ? (
            <>No radiologists currently have a future-dated target outreach week to check.</>
          ) : (
            <>
              The program's own target-outreach-week field can't be used to measure "time since engagement" -{" "}
              <strong style={{ color: "var(--text-primary)" }}>{fmtPct(outreach_week_reliability.contamination_rate)}</strong> (
              {outreach_week_reliability.already_past_outreached_count} of {outreach_week_reliability.future_dated_count}) of
              radiologists whose target week is still in the future are already active past "Outreached" - the field reflects
              planning, not actual treatment timing.
            </>
          )}
        </div>

        <div>
          <div style={{ marginBottom: 6 }}>
            Median baseline severity by funnel stage - checks whether radiologists further along started out systematically
            more or less severe than those earlier in the funnel (a selection-bias check, not just a time trend):
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {stageOrder
              .filter((s) => baseline_severity_by_stage[s])
              .map((stage) => (
                <div key={stage} style={{ fontSize: 12 }}>
                  <div style={{ color: "var(--text-muted)" }}>{stage} (n={baseline_severity_by_stage[stage].n})</div>
                  <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                    {fmtSignedPct(baseline_severity_by_stage[stage].median_baseline_pct)}
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
