import { useEffect, useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { Badge } from "../components/Badge";
import { AIHoverCard } from "../components/AIHoverCard";
import { ReviewActivityTicker } from "../components/ReviewActivityTicker";
import { RingGauge } from "../components/RingGauge";
import { CARD_STYLE } from "../styles/glassCard";
import type { BaselineProxyCandidate, BaselineProxyDetail, BaselineReviewDecision } from "../api/types";

// Matches the 8-component scoring weights in mosaic_service._CAPACITY_PROXY_CTE_SQL - used to
// size each component's bar proportionally to what it could actually score, not just its raw value.
const SCORE_DIMENSIONS: { key: keyof BaselineProxyCandidate; label: string; max: number }[] = [
  { key: "score_subspecialty", label: "Subspecialty", max: 10 },
  { key: "score_interventional", label: "Interventional", max: 20 },
  { key: "score_modality", label: "Modality Mix", max: 5 },
  { key: "score_tbwu", label: "TBWU/Exam", max: 5 },
  { key: "score_shift_duration", label: "Shift Duration", max: 10 },
  { key: "score_location", label: "Location", max: 10 },
  { key: "score_weekday_weekend", label: "Weekday/Weekend", max: 5 },
  { key: "score_time_of_day", label: "Time of Day", max: 5 },
];

function decisionKey(npi: number, targetShift: string): string {
  return `${npi}|${targetShift}`;
}

// Score < 40 is the backend's actual "No Good Proxy" cutoff (mosaic_service._CAPACITY_PROXY_CTE_SQL) -
// reusing that exact threshold here means the gauge's color always agrees with the real
// Manual Review classification, not an invented third tier.
function totalScoreColor(score: number | null): string {
  if (score === null) return "var(--text-muted)";
  return score < 40 ? "var(--status-critical)" : "var(--status-good)";
}

function CandidateCard({
  candidate,
  entityLabel,
  onChoose,
  disabled,
}: {
  candidate: BaselineProxyCandidate;
  entityLabel: string;
  onChoose: () => void;
  disabled: boolean;
}) {
  const [replayTrigger, setReplayTrigger] = useState(0);

  return (
    <div
      className="mosaic-card-hover"
      onMouseEnter={() => setReplayTrigger((t) => t + 1)}
      style={{
        ...CARD_STYLE,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        alignItems: "center",
        border: candidate.rank === 1 ? "1px solid var(--status-good)" : CARD_STYLE.border,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
        <Badge
          label={`Rank ${candidate.rank}`}
          color={candidate.rank === 1 ? "var(--status-good)" : "var(--text-secondary)"}
        />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{candidate.proxy_shift}</span>
      </div>

      <AIHoverCard
        feature="baseline_review_match"
        entityLabel={entityLabel}
        metricLabel={`Match score for borrowing "${candidate.proxy_shift}"`}
        value={String(candidate.total_match_score ?? "—")}
        extra={{ rank: String(candidate.rank) }}
        underline={false}
      >
        <RingGauge
          value={candidate.total_match_score}
          max={70}
          size={96}
          strokeWidth={9}
          color={totalScoreColor(candidate.total_match_score)}
          replayTrigger={replayTrigger}
        />
      </AIHoverCard>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
        {SCORE_DIMENSIONS.map((d, i) => (
          <RingGauge
            key={d.key}
            value={candidate[d.key] as number | null}
            max={d.max}
            size={52}
            strokeWidth={5}
            color="var(--color-primary)"
            delayMs={150 + i * 80}
            label={d.label}
            replayTrigger={replayTrigger}
          />
        ))}
      </div>

      <button
        onClick={onChoose}
        disabled={disabled}
        style={{
          marginTop: 4,
          width: "100%",
          padding: "6px 10px",
          borderRadius: 6,
          border: "1px solid var(--border)",
          background: candidate.rank === 1 ? "var(--status-good)" : "var(--surface-raised)",
          color: candidate.rank === 1 ? "#0a0a0a" : "var(--text-primary)",
          fontSize: 12,
          fontWeight: 600,
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        {candidate.rank === 1 ? "Accept (algorithm's pick)" : "Use this instead"}
      </button>
    </div>
  );
}

export function BaselineReviewQueue() {
  const proxyDetail = useFetch(() => mosaicApi.getBaselineProxyDetail(), []);
  const decisionsFetch = useFetch(() => mosaicApi.getBaselineReviewDecisions(), []);
  const [localDecisions, setLocalDecisions] = useState<BaselineReviewDecision[]>([]);
  const [showReviewed, setShowReviewed] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (decisionsFetch.data) setLocalDecisions(decisionsFetch.data);
  }, [decisionsFetch.data]);

  const reviewedKeys = useMemo(
    () => new Set(localDecisions.map((d) => decisionKey(d.npi, d.target_shift))),
    [localDecisions]
  );

  const manualReviewItems = useMemo(
    () => (proxyDetail.data ?? []).filter((r) => r.baseline_type === "Manual Review"),
    [proxyDetail.data]
  );

  const activeQueue = useMemo(
    () => (showReviewed ? manualReviewItems : manualReviewItems.filter((r) => !reviewedKeys.has(decisionKey(r.npi, r.target_shift)))),
    [manualReviewItems, reviewedKeys, showReviewed]
  );

  useEffect(() => {
    if (currentIndex >= activeQueue.length && activeQueue.length > 0) {
      setCurrentIndex(activeQueue.length - 1);
    } else if (activeQueue.length === 0 && currentIndex !== 0) {
      setCurrentIndex(0);
    }
  }, [activeQueue.length, currentIndex]);

  const currentItem: BaselineProxyDetail | undefined = activeQueue[currentIndex];

  const candidatesFetch = useFetch(
    () =>
      currentItem
        ? mosaicApi.getBaselineProxyCandidates(currentItem.npi, currentItem.target_shift)
        : Promise.resolve([] as BaselineProxyCandidate[]),
    [currentItem?.npi, currentItem?.target_shift]
  );

  async function submitDecision(status: "accepted" | "overridden" | "rejected_no_match", candidate?: BaselineProxyCandidate) {
    if (!currentItem || submitting) return;
    setSubmitting(true);
    try {
      const result = await mosaicApi.postBaselineReviewDecision({
        npi: currentItem.npi,
        target_shift: currentItem.target_shift,
        status,
        chosen_proxy_shift: candidate?.proxy_shift ?? null,
        chosen_rank: candidate?.rank ?? null,
        note: note || null,
      });
      if (result.saved) {
        setLocalDecisions((prev) => [
          ...prev.filter((d) => decisionKey(d.npi, d.target_shift) !== decisionKey(currentItem.npi, currentItem.target_shift)),
          {
            npi: currentItem.npi,
            target_shift: currentItem.target_shift,
            status,
            chosen_proxy_shift: candidate?.proxy_shift ?? null,
            chosen_rank: candidate?.rank ?? null,
            note: note || null,
            reviewed_at: new Date().toISOString(),
          },
        ]);
        setNote("");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const reviewedCount = manualReviewItems.filter((r) => reviewedKeys.has(decisionKey(r.npi, r.target_shift))).length;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20 }}>Baseline Review Queue</h1>
          <div style={{ color: "var(--text-muted)", fontSize: 13, maxWidth: 640 }}>
            Shift-types the proxy-matching algorithm flagged as a weak match (score below 40, or well
            below peer-median TBWU). Each candidate below is a different shift-type this same
            radiologist worked during their own baseline window - pick which one should stand in, or
            mark it as having no good match. Decisions are saved durably on the dev-bhargav Postgres
            branch.
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Reviewed: {reviewedCount} / {manualReviewItems.length}
          </div>
          <label style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
            <input type="checkbox" checked={showReviewed} onChange={(e) => setShowReviewed(e.target.checked)} />
            Show already-reviewed items
          </label>
        </div>
      </div>

      <ReviewActivityTicker />

      {(proxyDetail.error || decisionsFetch.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({proxyDetail.error ?? decisionsFetch.error})
        </div>
      )}

      {proxyDetail.data && activeQueue.length === 0 && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>
          {manualReviewItems.length === 0
            ? "No Manual Review items right now - every proxy match is above the confidence threshold."
            : "All Manual Review items have been reviewed. Toggle \"Show already-reviewed items\" to look back."}
        </div>
      )}

      {currentItem && (
        <>
          <div style={{ ...CARD_STYLE, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{currentItem.radiologist_name ?? `NPI ${currentItem.npi}`}</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                {currentItem.practice} - needs a baseline for <strong>{currentItem.target_shift}</strong>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
                disabled={currentIndex === 0}
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-raised)" }}
              >
                ◀ Prev
              </button>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {currentIndex + 1} / {activeQueue.length}
              </span>
              <button
                onClick={() => setCurrentIndex((i) => Math.min(activeQueue.length - 1, i + 1))}
                disabled={currentIndex >= activeQueue.length - 1}
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-raised)" }}
              >
                Next ▶
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
            {candidatesFetch.data?.map((c) => (
              <CandidateCard
                key={c.rank}
                candidate={c}
                entityLabel={currentItem.radiologist_name ?? `NPI ${currentItem.npi}`}
                disabled={submitting}
                onChoose={() => submitDecision(c.rank === 1 ? "accepted" : "overridden", c)}
              />
            ))}
          </div>

          <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 8 }}>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note for this decision..."
              style={{
                padding: "8px 10px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--surface-raised)",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            />
            <button
              onClick={() => submitDecision("rejected_no_match")}
              disabled={submitting}
              style={{
                alignSelf: "flex-start",
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid var(--status-critical)",
                background: "transparent",
                color: "var(--status-critical)",
                fontSize: 12,
                cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              No good match
            </button>
          </div>
        </>
      )}
    </div>
  );
}
