import { useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { mosaicApi } from "../api/client";
import { useRegistry, useRegistryFeature } from "../api/registry";

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

// The governed registry (GET /api/mosaic/registry) supplies the definition half of this card.
//
// Two different things share it. The *definition* is static, governed, and known before the user
// hovers - it should appear instantly. The *explanation* is generated, takes a second or two, and
// may fail. Previously the card only had the second, so a hover was a blank "Thinking…" that
// sometimes resolved into nothing. Now the definition renders immediately and the AI commentary
// fills in underneath it, so the card is never empty and never a lie: what it says the metric
// *is* comes from the same module that composes the SQL producing the number.
//
// The fetch itself lives in api/registry.ts - one cache shared with the solution axis and
// everything else that reads a governed value.

// Distinct from the registry's own `ai_fallback_text`, deliberately - this is the narrower case
// where the registry itself could not be fetched, i.e. the backend is unreachable, so there is
// no governed string to show. The ordinary "AI call failed" wording lives in Python
// (registry.AI_FALLBACK_TEXT) and is served on the snapshot; it is not re-typed here.
const UNREACHABLE_TEXT = "Context is unavailable - the server could not be reached.";

const headerStyle: CSSProperties = {
  fontSize: 10,
  color: "var(--text-muted)",
  marginBottom: 4,
  textTransform: "uppercase",
  letterSpacing: 0.5,
};

// The "A, B and C" list formatter that used to live here moved server-side into
// `registry._list_of`, alongside the `CoverageSpec.sentence` property that consumes it. Keeping
// a copy here would have meant two renderings of the same rule - the exact duplication the
// registry exists to remove.

export function AIHoverCard({ feature, entityLabel, metricLabel, value, extra, children, style, underline = true }: AIHoverCardProps) {
  const [open, setOpen] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const registryFeature = useRegistryFeature(feature);
  const registry = useRegistry();

  // Is there anything above the AI text? Three things can put something there, and both the
  // width and the separator below need the same answer - they were two copies of a two-arm
  // version of this expression, which is how the third state would have been added to one and
  // forgotten in the other.
  const hasGovernedBlock = Boolean(
    registryFeature?.metrics.length ||
      registryFeature?.coverage ||
      registryFeature?.unregistered_reason,
  );

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
        .catch(() => setExplanation(registry?.ai_fallback_text ?? UNREACHABLE_TEXT))
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
            // Wider only when the registry actually resolved something to show above the AI
            // text; an unmapped feature keeps the original single-section width.
            width: hasGovernedBlock ? 320 : 260,
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
          {registryFeature?.metrics.map((m) => (
            <div key={m.key} style={{ marginBottom: 8 }}>
              <div style={headerStyle}>{m.label}</div>
              <div>{m.definition}</div>
              {m.caveats.map((c) => (
                <div key={c} style={{ color: "var(--text-muted)", marginTop: 3 }}>
                  {c}
                </div>
              ))}
            </div>
          ))}

          {/* Structured fields only, never the registry's full `caveat` prose - that runs ~200
              words, which belongs in the AI prompt (where it already is, via the backend's
              grounding) and not in a tooltip. The threshold, what it suppresses, and what
              survives it are the three things a reader needs at a glance. */}
          {registryFeature?.coverage && (
            <div style={{ marginBottom: 8 }}>
              <div style={headerStyle}>{registryFeature.coverage.label}</div>
              {/* Rendered, not composed. This block used to build the sentence from the parts
                  and in doing so hardcoded "Below {x}" - correct for the one spec that existed,
                  and exactly backwards for MVP's plausibility ceiling, which suppresses values
                  ABOVE its threshold. The sentence now comes from `CoverageSpec.sentence`,
                  composed next to the fields it describes, so a third gate shape breaks the
                  server-side property loudly instead of mis-describing itself quietly here. */}
              <div>{registryFeature.coverage.sentence}</div>
            </div>
          )}

          {/* The third state, and the only one that says something about itself rather than
              about a number. These four features have no num/den to govern - a leakage taxonomy,
              a survey of 810 radiologists, a review-queue workflow state, and a free-text note
              summary - so the honest thing to show is why, not a blank space the reader has to
              interpret. Without it an undefined feature and a misspelled `feature` prop render
              identically, and the misspelling is the one nobody would ever notice. */}
          {registryFeature?.unregistered_reason && (
            <div style={{ marginBottom: 8 }}>
              <div style={headerStyle}>Not a governed metric</div>
              <div style={{ color: "var(--text-muted)" }}>
                {registryFeature.unregistered_reason}
              </div>
            </div>
          )}

          <div
            style={{
              ...headerStyle,
              // Only a separator when there is something above it to separate from.
              ...(hasGovernedBlock
                ? { borderTop: "var(--glass-border)", paddingTop: 6 }
                : {}),
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
