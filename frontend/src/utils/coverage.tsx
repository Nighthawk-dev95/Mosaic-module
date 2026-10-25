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
): ReactNode {
  if (coverage == null) return "—";
  const sufficient = coverage >= MIN_READ_TIME_COVERAGE;
  const label = `${(coverage * 100).toFixed(1)}%`;
  return (
    <AIHoverCard
      feature="capacity_coverage"
      entityLabel={entityLabel}
      metricLabel="% of exams with a usable dictation timestamp"
      value={label}
      extra={{
        threshold: `${(MIN_READ_TIME_COVERAGE * 100).toFixed(0)}%`,
        status: sufficient ? "sufficient" : "insufficient",
        ...(rpceCoverage == null ? {} : { pct_shifts_rpce_source: `${(rpceCoverage * 100).toFixed(1)}%` }),
        note: sufficient
          ? "Read-time coverage is high enough for Utilization and Efficiency to be meaningful for this slice."
          : `Below the ${(MIN_READ_TIME_COVERAGE * 100).toFixed(0)}% floor, so On-Shift Utilization is suppressed (shown as "—") rather than displayed. Its numerator counts only exams with a dictation timestamp while its denominator counts the whole scheduled shift, so a low-coverage value understates the truth by roughly the coverage fraction. Efficiency is still shown because its numerator is restricted to the same exams as its denominator.`,
      }}
    >
      <Badge label={label} color={sufficient ? "var(--status-good)" : "var(--status-critical)"} dot />
    </AIHoverCard>
  );
}
