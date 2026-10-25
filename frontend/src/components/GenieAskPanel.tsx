import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { mosaicApi } from "../api/client";
import type { GenieMessageResponse } from "../api/types";
import { useFilters } from "../context/FilterContext";
import type { Filters } from "../context/FilterContext";
import { TABS } from "../utils/tabs";

// Floating, app-wide "Ask Mosaic" launcher - natural-language Q&A against the existing
// "Mosaic performance metrics" Genie Space (already covers Deployment/Volume/Efficiency/
// Read-Times/Capacity). Mounted once in MosaicShell so it's available on every tab, not a
// per-page component. Genie responses take real time (30-120s+) so this polls rather than
// blocking - a first, deliberately small version of this app's first conversational surface.

interface Turn {
  question: string;
  conversationId: string;
  messageId: string;
  state: GenieMessageResponse | null;
  scope: string[]; // the page filters that travelled with this question, for the transcript
}

const POLL_MS = 2000;
const MAX_POLLS = 150; // 5 minutes at POLL_MS - well past Genie's own documented worst case (120s+)
const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

/**
 * The page's active filters, as short human-readable chips.
 *
 * Order is deliberate: entity first, then time, then the narrowing flags - it reads the way
 * someone would say it out loud, which is also how it gets prepended to the question.
 */
function scopeChips(filters: Filters): string[] {
  const chips: string[] = [];
  if (filters.practice) chips.push(filters.practice);
  if (filters.local) chips.push(`${filters.local} Local`);
  if (filters.month) chips.push(filters.month);
  if (filters.captureEnabledOnly) chips.push("Capture-enabled only");
  if (filters.radiologistSearch) chips.push(`name matches "${filters.radiologistSearch}"`);
  return chips;
}

const SCOPE_CLEARED =
  "Context: the dashboard filters have just been cleared - answer enterprise-wide from here on.";

/**
 * Turn the current page + filters into a preamble Genie can actually use.
 *
 * Genie is a text interface with no view of our React state, so until now a question like
 * "which practices are lowest?" asked from a page filtered to one Local Region came back
 * answered enterprise-wide, with nothing on screen saying the filter had been ignored. The
 * cheapest honest fix is to say the scope in words. Returns "" when nothing is filtered -
 * an unfiltered page should not pay for a preamble.
 */
function scopeSentence(chips: string[], pathname: string): string {
  if (chips.length === 0) return "";
  const tab = TABS.find((t) => (t.end ? pathname === t.to : pathname.startsWith(t.to)));
  return (
    `Context: the person asking is on the ${tab?.label ?? "Mosaic"} tab of an internal Mosaic ` +
    `dashboard, currently filtered to ${chips.join("; ")}. Scope your answer to that filter ` +
    `unless the question clearly asks for something wider.`
  );
}

export function GenieAskPanel() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const filters = useFilters(); // FilterContextValue extends Filters, so it reads as one
  const { pathname } = useLocation();
  const chips = scopeChips(filters);
  // Genie keeps conversation history, so the preamble is only worth sending when the scope
  // has actually changed - otherwise every follow-up turn re-states the same filters and
  // crowds out the question itself.
  const lastScopeRef = useRef("");

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  function pollMessage(convId: string, msgId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const state = await mosaicApi.getGenieMessage(convId, msgId);
        setTurns((prev) => prev.map((t) => (t.messageId === msgId ? { ...t, state } : t)));
        if (TERMINAL.has(state.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setSubmitting(false);
        }
      } catch {
        // transient poll failure - next tick retries, no need to surface this mid-flight
      }
      if (attempts >= MAX_POLLS && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setSubmitting(false);
        setTurns((prev) =>
          prev.map((t) =>
            t.messageId === msgId && (!t.state || !TERMINAL.has(t.state.status))
              ? { ...t, state: { status: "FAILED", text: null, sql: null, error: "Timed out waiting for a response.", suggested_questions: [], result: null } }
              : t
          )
        );
      }
    }, POLL_MS);
  }

  async function submit() {
    const question = input.trim();
    if (!question || submitting) return;
    setSubmitting(true);
    setInput("");
    const scope = scopeSentence(chips, pathname);
    // Both directions matter. A newly-applied filter has to be announced; so does a cleared
    // one, or Genie keeps answering inside a scope the user has already walked away from.
    const payload = scope === lastScopeRef.current ? question : `${scope || SCOPE_CLEARED}\n\n${question}`;
    lastScopeRef.current = scope;
    try {
      const res = await mosaicApi.askGenie({ question: payload, conversation_id: conversationId });
      setConversationId(res.conversation_id);
      // The transcript shows what the user typed, not the padded payload - the scope is
      // surfaced separately beneath it so it is disclosed without being noise.
      setTurns((prev) => [...prev, { question, conversationId: res.conversation_id, messageId: res.message_id, state: null, scope: chips }]);
      pollMessage(res.conversation_id, res.message_id);
    } catch {
      setSubmitting(false);
    }
  }

  function newConversation() {
    if (pollRef.current) clearInterval(pollRef.current);
    setConversationId(null);
    setTurns([]);
    setSubmitting(false);
    lastScopeRef.current = ""; // fresh conversation carries no history, so re-send the scope
  }

  return (
    <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 300 }}>
      {open && (
        <div
          style={{
            width: 380,
            maxHeight: 520,
            display: "flex",
            flexDirection: "column",
            marginBottom: 12,
            background: "var(--glass-fill-drawer)",
            backdropFilter: "blur(var(--glass-blur-md))",
            WebkitBackdropFilter: "blur(var(--glass-blur-md))",
            border: "var(--glass-border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--glass-shadow-modal), var(--glass-highlight)",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 14px", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: 13 }}>✨ Ask Mosaic</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {turns.length > 0 && (
                <button onClick={newConversation} style={{ background: "transparent", border: "none", color: "var(--text-muted)", fontSize: 11, cursor: "pointer" }}>
                  New question
                </button>
              )}
              <button onClick={() => setOpen(false)} style={{ background: "transparent", border: "none", color: "var(--text-secondary)", fontSize: 16, cursor: "pointer", lineHeight: 1 }}>
                ✕
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 14 }}>
            {turns.length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
                Ask anything about Mosaic adoption, efficiency, capacity, or read times - e.g.
                "What was total TBWU last week?" or "Which practices have the lowest RPCE drafting?"
              </div>
            )}
            {turns.map((t) => (
              <GenieTurn key={t.messageId} turn={t} onPickSuggestion={setInput} />
            ))}
          </div>

          {chips.length > 0 && (
            <div
              style={{
                padding: "10px 12px 0",
                borderTop: "1px solid var(--border)",
                fontSize: 11,
                color: "var(--text-muted)",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span>Scoped to</span>
              {chips.map((c) => (
                <span
                  key={c}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 999,
                    padding: "1px 8px",
                    color: "var(--text-secondary)",
                  }}
                >
                  {c}
                </span>
              ))}
              <span>- your page filters travel with the question.</span>
            </div>
          )}

          <div
            style={{
              display: "flex",
              gap: 8,
              padding: 12,
              // The scope chips sit directly above and already carry the divider when present.
              borderTop: chips.length > 0 ? "none" : "1px solid var(--border)",
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="Ask a question..."
              disabled={submitting}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "var(--radius)",
                border: "1px solid var(--border)",
                background: "var(--surface-raised)",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            />
            <button
              onClick={submit}
              disabled={submitting || !input.trim()}
              style={{
                padding: "8px 14px",
                borderRadius: "var(--radius)",
                border: "none",
                background: "var(--color-primary)",
                color: "#0a0a0a",
                fontSize: 13,
                fontWeight: 600,
                cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              Ask
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          padding: "10px 18px",
          borderRadius: 999,
          border: "none",
          background: "var(--color-primary)",
          color: "#0a0a0a",
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: "var(--glass-shadow-elevated)",
        }}
      >
        {open ? "Close" : "✨ Ask Mosaic"}
      </button>
    </div>
  );
}

function GenieTurn({ turn, onPickSuggestion }: { turn: Turn; onPickSuggestion: (q: string) => void }) {
  const [showSql, setShowSql] = useState(false);
  const status = turn.state?.status;
  const thinking = !status || !TERMINAL.has(status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ alignSelf: "flex-end", background: "var(--color-primary)", color: "#0a0a0a", borderRadius: "var(--radius)", padding: "6px 12px", fontSize: 13, maxWidth: "85%" }}>
        {turn.question}
      </div>

      {/* Scrolling back up a conversation, the filters may have changed since. Each turn keeps
          the scope it was actually asked under so an old answer can't be misread as current. */}
      {turn.scope.length > 0 && (
        <div style={{ alignSelf: "flex-end", fontSize: 10, color: "var(--text-muted)", maxWidth: "85%", textAlign: "right" }}>
          asked within {turn.scope.join(" · ")}
        </div>
      )}

      {thinking && <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Thinking… ({status ?? "SUBMITTED"})</div>}

      {turn.state?.error && <div style={{ color: "var(--status-critical)", fontSize: 12 }}>{turn.state.error}</div>}

      {turn.state?.text && (
        <div style={{ background: "var(--surface-raised)", borderRadius: "var(--radius)", padding: "8px 12px", fontSize: 13 }}>
          {turn.state.text}
        </div>
      )}

      {turn.state?.result && turn.state.result.rows.length > 0 && (
        <div style={{ overflowX: "auto", fontSize: 11 }}>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                {turn.state.result.columns.map((c) => (
                  <th key={c} style={{ textAlign: "left", padding: "4px 8px", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {turn.state.result.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j} style={{ padding: "4px 8px", borderBottom: "1px solid var(--gridline)" }}>
                      {cell ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {turn.state?.sql && (
        <div>
          <button onClick={() => setShowSql((s) => !s)} style={{ background: "transparent", border: "none", color: "var(--text-muted)", fontSize: 11, cursor: "pointer", padding: 0 }}>
            {showSql ? "Hide SQL" : "Show SQL"}
          </button>
          {showSql && (
            <pre style={{ fontSize: 10, color: "var(--text-secondary)", whiteSpace: "pre-wrap", background: "var(--surface-raised)", padding: 8, borderRadius: "var(--radius)", marginTop: 4 }}>
              {turn.state.sql}
            </pre>
          )}
        </div>
      )}

      {turn.state?.suggested_questions && turn.state.suggested_questions.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {turn.state.suggested_questions.map((q) => (
            <button
              key={q}
              onClick={() => onPickSuggestion(q)}
              style={{
                fontSize: 11,
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
                borderRadius: 999,
                padding: "3px 10px",
                background: "transparent",
                cursor: "pointer",
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
