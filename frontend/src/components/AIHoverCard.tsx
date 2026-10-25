import { useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { mosaicApi } from "../api/client";

interface AIHoverCardProps {
  feature: string;
  entityLabel: string;
  metricLabel: string;
  value: string;
  extra?: Record<string, string>;
  children: ReactNode;
  /** Extra style merged onto the wrapper span - e.g. `{ flex: "1 1 200px" }` when wrapping a
   * whole flex-item component (StatTile) rather than an inline text/badge value. */
  style?: CSSProperties;
  /** Set false when wrapping a block-level card (StatTile) instead of inline text/a badge -
   * a dotted underline reads fine under a word, not under a whole card. Default true. */
  underline?: boolean;
}

// Live, LLM-generated explanation on hover - the one new reusable primitive this feature adds
// (see app/services/ai_context_service.py). A 400ms delay before firing skips pure mouse-pass-
// throughs; a module-level cache means repeat hovers of the same cell in this session are
// instant without re-calling the backend (which has its own, separate process-lifetime cache).
const cache = new Map<string, string>();

function cacheKey(feature: string, entityLabel: string, metricLabel: string, value: string, extra?: Record<string, string>): string {
  return JSON.stringify([feature, entityLabel, metricLabel, value, extra ?? {}]);
}

export function AIHoverCard({ feature, entityLabel, metricLabel, value, extra, children, style, underline = true }: AIHoverCardProps) {
  const [open, setOpen] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleEnter() {
    timerRef.current = setTimeout(() => {
      setOpen(true);
      const key = cacheKey(feature, entityLabel, metricLabel, value, extra);
      const cached = cache.get(key);
      if (cached) {
        setExplanation(cached);
        return;
      }
      setLoading(true);
      mosaicApi
        .getAiContext({ feature, entity_label: entityLabel, metric_label: metricLabel, value, extra })
        .then((res) => {
          cache.set(key, res.explanation);
          setExplanation(res.explanation);
        })
        .catch(() => setExplanation("No additional context is available for this value right now."))
        .finally(() => setLoading(false));
    }, 400);
  }

  function handleLeave() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    setOpen(false);
  }

  return (
    <span
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      style={{
        position: "relative",
        display: "inline-block",
        cursor: "help",
        ...(underline ? { borderBottom: "1px dotted var(--text-muted)" } : {}),
        ...style,
      }}
    >
      {children}
      {open && (
        <div
          style={{
            position: "absolute",
            zIndex: 200,
            top: "100%",
            left: 0,
            marginTop: 6,
            width: 260,
            background: "var(--glass-fill-card)",
            backdropFilter: "blur(var(--glass-blur-md))",
            WebkitBackdropFilter: "blur(var(--glass-blur-md))",
            border: "var(--glass-border)",
            borderRadius: "var(--radius)",
            boxShadow: "var(--glass-shadow-elevated)",
            padding: 10,
            fontSize: 12,
            color: "var(--text-secondary)",
            lineHeight: 1.4,
            cursor: "default",
            // Read-only tooltip, nothing inside it to click - without this, the popover (anchored
            // directly below whatever it's wrapping, e.g. a section header) sits on top of
            // content below it (e.g. the Impact stat tiles right under "Impact on MVP Rads...")
            // and silently swallows clicks meant for that content instead of passing them through.
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "var(--text-muted)",
              marginBottom: 4,
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            ✨ AI context
          </div>
          {loading && !explanation ? "Thinking…" : explanation}
        </div>
      )}
    </span>
  );
}
