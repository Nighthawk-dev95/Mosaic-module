import { useEffect, useRef, useState } from "react";
import { mosaicApi } from "../api/client";
import { CARD_STYLE } from "../styles/glassCard";
import type { ReviewActivityItem, ReviewDecisionStatus } from "../api/types";

const STATUS_COLOR: Record<ReviewDecisionStatus, string> = {
  accepted: "var(--status-good)",
  // "overridden" isn't a severity state (status colors are reserved for good/warning/critical
  // per the dataviz skill), so it gets the app's neutral accent instead of a status color.
  overridden: "var(--color-primary)",
  rejected_no_match: "var(--status-critical)",
};

const STATUS_LABEL: Record<ReviewDecisionStatus, string> = {
  accepted: "accepted",
  overridden: "overridden",
  rejected_no_match: "no match",
};

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function impactLabel(impact: number | null): string {
  if (impact === null) return "—";
  const sign = impact > 0 ? "+" : "";
  return `${sign}${impact.toFixed(2)} TBWU/hr`;
}

function decisionKey(item: ReviewActivityItem): string {
  return `${item.npi}|${item.target_shift}|${item.reviewed_at}`;
}

export function ReviewActivityTicker() {
  const [items, setItems] = useState<ReviewActivityItem[]>([]);
  const seenKeys = useRef<Set<string>>(new Set());
  const [freshKeys, setFreshKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await mosaicApi.getReviewActivity(20);
        if (cancelled) return;
        const newlySeen = new Set<string>();
        for (const item of data) {
          const key = decisionKey(item);
          if (!seenKeys.current.has(key)) newlySeen.add(key);
          seenKeys.current.add(key);
        }
        if (newlySeen.size > 0) setFreshKeys(newlySeen);
        setItems(data);
      } catch {
        // leave previous state on a transient poll failure
      }
    };
    poll();
    const id = setInterval(poll, 6000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div style={CARD_STYLE}>
      <style>{`
        @keyframes review-ticker-slide-in {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
        Live Review Activity
      </div>
      {items.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No review decisions yet.</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 280, overflowY: "auto" }}>
        {items.map((item) => {
          const key = decisionKey(item);
          const isFresh = freshKeys.has(key);
          return (
            <div
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                padding: "4px 0",
                animation: isFresh ? "review-ticker-slide-in var(--dur-card) var(--ease-snap)" : undefined,
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: STATUS_COLOR[item.status], flexShrink: 0 }} />
              <span style={{ color: "var(--text-secondary)", width: 72, flexShrink: 0 }}>{STATUS_LABEL[item.status]}</span>
              <span style={{ color: "var(--text-primary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.radiologist_name ?? `NPI ${item.npi}`}
              </span>
              <span style={{ color: "var(--text-secondary)", width: 110, textAlign: "right", flexShrink: 0 }}>
                {impactLabel(item.capacity_impact_tbwu_per_hour)}
              </span>
              <span style={{ color: "var(--text-muted)", width: 56, textAlign: "right", flexShrink: 0 }}>
                {relativeTime(item.reviewed_at)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
