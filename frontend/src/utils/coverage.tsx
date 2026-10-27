import type { ReactNode } from "react";
import { Badge } from "../components/Badge";
import { AIHoverCard } from "../components/AIHoverCard";

/**
 * Mirror of `_MIN_READ_TIME_COVERAGE` in backend/app/services/mosaic_service.py.
 *
 * Hand-synced across the Python/TypeScript boundary, so it gets a comment on both sides
 * rather than being silently duplicated. The backend is authoritative: it is what actually
 * NULLs out a utilization value. This copy exists only so the badge can say *why* a value
 * came back as "—" instead of leaving the user to guess.
 */
export const MIN_READ_TIME_COVERAGE = 0.75;

/**
 * Read-time data coverage rendered as a two-state badge, not a letter grade.
 *
 * The failure mode here is binary rather than graduated. Measured live 2026-10-24: Boca
 * (5,783 shifts / 341,068 exams) and Bethesda (4,597 / 299,725) have zero exams with a usable
 * dictation timestamp, and because Spark's LEAST() skips NULLs they both reported a perfect
 * 100.0% utilization. RASF, at 0.055% coverage, reported 0.02%. A "C" grade would imply those
 * numbers are partly trustworthy; they are simply wrong. So: show the real percentage, plus
 * sufficient/insufficient against one documented threshold, and let the backend suppress the
 * dependent value entirely.
 */
export function readTimeCoverageBadge(
  coverage: number | null | undefined,
  entityLabel: string,
  rpceCoverage?: number | null,
  // Which surface is asking. Defaults to the capacity tables, the first consumer, so the
  // existing call sites keep their attribution; the scorecard passes its own so the AI
  // explanation is grounded in the metric the user is actually looking at there.
  feature = "capacity_coverage",
): ReactNode {
  if (coverage == null) return "—";
  const sufficient = coverage >= MIN_READ_TIME_COVERAGE;
  const label = `${(coverage * 100).toFixed(1)}%`;
  return (
    <AIHoverCard
      feature={feature}
      entityLabel={entityLabel}
      metricLabel="% of exams with a usable dictation timestamp"
      value={label}
      extra={{
        threshold: `${(MIN_READ_TIME_COVERAGE * 100).toFixed(0)}%`,
        status: sufficient ? "sufficient" : "insufficient",
        ...(rpceCoverage == null ? {} : { pct_shifts_rpce_source: `${(rpceCoverage * 100).toFixed(1)}%` }),
        // No methodology prose here. It used to carry a ~60-word paraphrase of the suppression
        // rule, which was the third copy of text that also lived in `ai_context_service` and in
        // `mosaic_service`'s threshold. It is now declared once, in
        // backend/app/semantics/registry.py (READ_TIME_COVERAGE.caveat), and reaches this card
        // two ways: the backend grounds the AI explanation on it, and AIHoverCard renders the
        // threshold's structured fields from GET /api/mosaic/registry. What stays here is only
        // what the registry cannot know - this slice's measured numbers.
      }}
    >
      <Badge label={label} color={sufficient ? "var(--status-good)" : "var(--status-critical)"} dot />
    </AIHoverCard>
  );
}
