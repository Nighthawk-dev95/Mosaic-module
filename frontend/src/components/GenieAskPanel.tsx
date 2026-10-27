import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useLocation } from "react-router-dom";
import { mosaicApi } from "../api/client";
import { useRegistry } from "../api/registry";
import type { AskResponse, AskWorklist, GenieMessageResponse } from "../api/types";
import { useFilters } from "../context/FilterContext";
import type { Filters } from "../context/FilterContext";
import { TABS } from "../utils/tabs";

// Floating, app-wide "Ask Mosaic" launcher - natural-language Q&A against the existing
// "Mosaic performance metrics" Genie Space (already covers Deployment/Volume/Efficiency/
// Read-Times/Capacity). Mounted once in MosaicShell so it's available on every tab, not a
// per-page component. Genie responses take real time (30-120s+) so this polls rather than
// blocking - a first, deliberately small version of this app's first conversational surface.
//
// Every question now goes through `POST /api/mosaic/ask` first. That call does not answer
// anything; it decides what the question *means* in registry terms, and either hands back a
// grounded prompt carrying the governed definitions or refuses a term by name. Genie is only
// asked the grounded version.
//
// The reason is a specific failure, not a principle. Two deployed columns are both called
// `pct_mosaic` and their denominators differ by roughly a quarter of all exams; "utilization"
// means adoption % on one surface and share-of-shift on another. Genie is a capable open-ended
// query engine over that same warehouse, which makes it equally capable of picking the wrong
// one and saying so fluently. Resolving first turns an open question into a constrained one,
// and turns the cases that cannot be constrained into a visible question back to the user.

interface Turn {
  /** Stable across the turn's life. `messageId` is not: a refusal turn never gets one. */
  id: string;
  question: string;
  conversationId: string;
  /** "" for a turn that was refused before Genie was called. Also the poll's match key. */
  messageId: string;
  state: GenieMessageResponse | null;
  scope: string[]; // the page filters that travelled with this question, for the transcript
  /** What the question was taken to mean. `null` only when /ask itself was unreachable. */
  resolved: AskResponse | null;
}

let turnSeq = 0;

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

/**
 * The page's filters as the resolver's seed fields, not as prose.
 *
 * Deliberately narrower than `scopeChips`. The resolver only seeds `entity`, `period` and
 * `solution`, and a term named in the question overrides any of them - so "and how about Boca"
 * asked on a Bethesda page asks about Boca. The flags `scopeChips` carries that have no field
 * here (Capture-enabled only, a name search) still reach Genie through the prose preamble; they
 * narrow a result set rather than name a scope, so there is nothing for the registry to resolve.
 */
function pageScope(filters: Filters): Record<string, string> {
  const scope: Record<string, string> = {};
  const entity = filters.practice || (filters.local ? `${filters.local} Local` : "");
  if (entity) scope.entity = entity;
  if (filters.month) scope.period = filters.month;
  return scope;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Rewrite the question with a refused term swapped for one the registry accepts.
 *
 * The alternatives are the one part of a refusal a user can act on, so they are buttons rather
 * than prose. Substituting in place keeps the rest of the sentence - including the entity and
 * period the resolver already understood - instead of making the user retype a question that
 * was mostly right. When the refused term is not literally in the sentence (the resolver works
 * in keys, so "local_region" can stand for the words "local region" or neither), append in
 * parentheses rather than silently changing nothing.
 *
 * The alternative goes in **verbatim, underscores and all**, even though the button shows a
 * prettified label. That is not cosmetic sloppiness - `pct_mosaic` with the underscore is a
 * globally unique registry key, and "pct mosaic" without it is precisely the colloquial phrase
 * the resolver refuses as ambiguous. Prettifying the substitution would make this button feed
 * the resolver the exact string it just rejected.
 */
function refineQuestion(question: string, term: string, alternative: string): string {
  const spoken = term.replace(/_/g, " ");
  const pattern = new RegExp(`\\b${escapeRegExp(spoken)}\\b`, "i");
  return pattern.test(question)
    ? question.replace(pattern, alternative)
    : `${question} (${alternative})`;
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

  /**
   * `reask` is the entity chip's Team/Practice switch: the same question, re-resolved with the
   * other column forced. A new turn rather than an edit in place, so the transcript keeps both
   * readings side by side - which is the actual point. Seeing "Boca as Practice" and "Boca as
   * Team" give different numbers is how the distinction stops being a footnote.
   */
  async function submit(reask?: string, entityKind?: string) {
    const question = (reask ?? input).trim();
    if (!question || submitting) return;
    setSubmitting(true);
    if (reask === undefined) setInput("");
    const id = `turn-${(turnSeq += 1)}`;

    // Step one: what does this question mean? Never a hard failure - if /ask is unreachable the
    // panel degrades to exactly what it did before the resolver existed (an ungrounded question
    // with the prose preamble), rather than losing the ability to ask anything at all.
    let resolved: AskResponse | null = null;
    try {
      resolved = await mosaicApi.ask({
        question,
        // `entity_kind` rides on page_scope because that is what it is - scope the surface is
        // carrying rather than something the question said. The resolver never infers it.
        page_scope: { ...pageScope(filters), ...(entityKind ? { entity_kind: entityKind } : {}) },
      });
    } catch {
      resolved = null;
    }

    // Step two, only if the question survived. An unanswerable scope resolved no metric at all,
    // so there is nothing to ground on and nothing worth asking - sending it anyway is precisely
    // the ungoverned question this path exists to stop. Partial refusals do go through: a
    // question naming one good metric and one impossible breakdown is mostly answerable, and
    // the refusal rides along beside the answer.
    if (resolved && !resolved.scope.is_answerable) {
      setTurns((prev) => [
        ...prev,
        { id, question, conversationId: conversationId ?? "", messageId: "", state: null, scope: chips, resolved },
      ]);
      setSubmitting(false);
      return;
    }

    const scope = scopeSentence(chips, pathname);
    // The grounded prompt already restates the question with the governed definitions attached,
    // so it replaces the raw question rather than wrapping it. The prose preamble stays on top:
    // it carries the page flags that are not registry vocabulary (Capture-enabled only, a name
    // search) and the tab the person is standing on.
    const body = resolved?.genie_prompt || question;
    // Both directions matter. A newly-applied filter has to be announced; so does a cleared
    // one, or Genie keeps answering inside a scope the user has already walked away from.
    const payload = scope === lastScopeRef.current ? body : `${scope || SCOPE_CLEARED}\n\n${body}`;
    lastScopeRef.current = scope;
    try {
      const res = await mosaicApi.askGenie({ question: payload, conversation_id: conversationId });
      setConversationId(res.conversation_id);
      // The transcript shows what the user typed, not the padded payload - the scope is
      // surfaced separately beneath it so it is disclosed without being noise.
      setTurns((prev) => [
        ...prev,
        { id, question, conversationId: res.conversation_id, messageId: res.message_id, state: null, scope: chips, resolved },
      ]);
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
              <GenieTurn
                key={t.id}
                turn={t}
                onPickSuggestion={setInput}
                onSwitchEntity={(q, kind) => submit(q, kind)}
              />
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
              // Wrapped, not passed by reference: `submit`'s first parameter is now a question
              // to re-ask, and a click event is a string to TypeScript's eye only by accident.
              onClick={() => submit()}
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

const chipStyle: CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 999,
  padding: "1px 8px",
  fontSize: 10,
  color: "var(--text-secondary)",
  whiteSpace: "nowrap",
};

/**
 * What the question was taken to mean, above the answer rather than buried under it.
 *
 * A number is only as good as its definition, and this is the one place in the product where
 * the user picked the definition by typing a sentence. Showing the resolved metric, solution
 * and breakdown is what makes that reviewable: if the chips say something other than what was
 * meant, the answer below them can be dismissed without reading it.
 *
 * `resolved_by` is deliberately visible. "keywords (model unavailable)" is a materially weaker
 * resolution than "model", and a degraded answer that looks identical to a good one is how a
 * degradation goes unnoticed for a quarter.
 */
/**
 * The named entity, and - the part that matters - *which column* answered it.
 *
 * Team is `provider_local_practice_name_curr`, the radiologist's home practice. Practice is
 * `managing_local_practice_name_curr`, the site they read the exam at. A radiologist has one
 * Team and reads at as many as seventy Practices, so "how is Boca doing" is two questions with
 * two different numbers, and a bare "Boca" chip discloses neither.
 *
 * Nearly every name is both - 86 Practice names and 96 Team names that overlap almost entirely -
 * so this cannot be a clarifier the user has to clear before seeing an answer; one that fires
 * every time is one people learn to click past. Instead the default is taken (Practice, matching
 * what the filter bar's own "Practice" dropdown means), shown on the answer, and one click from
 * the other reading. The switch re-asks the same question with `entity_kind` forced, so the
 * number updates rather than the label.
 */
function EntityChip({
  resolved,
  onSwitchEntity,
}: {
  resolved: AskResponse;
  onSwitchEntity: (kind: string) => void;
}) {
  const registry = useRegistry();
  const { entity_match: match, scope } = resolved;
  const labelOf = (kind: string) => registry?.dimensions.find((d) => d.key === kind)?.label ?? kind;
  const noteOf = (kind: string) => registry?.dimensions.find((d) => d.key === kind)?.note ?? "";
  // An entity the vocabulary could not place keeps the old bare chip. Dressing it in a column
  // name we had to guess would be worse than saying nothing.
  if (!match || !match.kind || match.kind === "unknown") {
    return <span style={chipStyle}>{scope.entity}</span>;
  }
  const other = match.candidates.find((c) => c.kind !== match.kind);
  return (
    <span style={{ ...chipStyle, display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span title={noteOf(match.kind)}>
        {match.value} · {labelOf(match.kind)}
        {/* Only when it *is* an assumption. Once the user has switched, the chip is reporting a
            choice they made, and still calling it a default would be noise. */}
        {match.assumed && <span style={{ color: "var(--text-muted)" }}> (assumed)</span>}
      </span>
      {other && (
        <button
          onClick={() => onSwitchEntity(other.kind)}
          title={noteOf(other.kind)}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--text-muted)",
            fontSize: 10,
            cursor: "pointer",
            padding: 0,
            textDecoration: "underline",
          }}
        >
          use {labelOf(other.kind)}
        </button>
      )}
    </span>
  );
}

function ScopeStrip({
  resolved,
  onSwitchEntity,
}: {
  resolved: AskResponse;
  onSwitchEntity: (kind: string) => void;
}) {
  const { scope } = resolved;
  const [showPrompt, setShowPrompt] = useState(false);
  if (!scope.is_answerable) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
        {scope.metrics.map((m) => (
          // The governed definition travels with the chip. The whole point of resolving is that
          // "utilization" stopped being a word and became one of two specific ratios; the title
          // is where a reader finds out which one they got.
          <span key={m.key} style={{ ...chipStyle, color: "var(--text-primary)" }} title={m.definition}>
            {m.label}
          </span>
        ))}
        {scope.solution.key !== "full_mosaic" && (
          <span style={chipStyle} title={scope.solution.description}>
            {scope.solution.label}
          </span>
        )}
        {scope.group_by.map((d) => (
          <span key={d.key} style={chipStyle} title={d.note}>
            by {d.label}
          </span>
        ))}
        {scope.entity && <EntityChip resolved={resolved} onSwitchEntity={onSwitchEntity} />}
        {scope.period && <span style={chipStyle}>{scope.period}</span>}
      </div>

      {/* Notes are not refusals. Nothing was dropped - the answer simply carries a condition a
          reader would otherwise have to know already, like which of Team and Practice a
          breakdown means. Rendered as plain text so they never read as an error. */}
      {scope.notes.map((n) => (
        <div key={n} style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4 }}>
          {n}
        </div>
      ))}

      <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 10, color: "var(--text-muted)" }}>
        <span>resolved by {resolved.resolved_by} · registry {scope.registry_version}</span>
        {resolved.genie_prompt && (
          <button
            onClick={() => setShowPrompt((s) => !s)}
            style={{ background: "transparent", border: "none", color: "var(--text-muted)", fontSize: 10, cursor: "pointer", padding: 0, textDecoration: "underline" }}
          >
            {showPrompt ? "Hide grounding" : "Show grounding"}
          </button>
        )}
      </div>
      {showPrompt && (
        <pre style={{ fontSize: 10, color: "var(--text-secondary)", whiteSpace: "pre-wrap", background: "var(--surface-raised)", padding: 8, borderRadius: "var(--radius)", margin: 0 }}>
          {resolved.genie_prompt}
        </pre>
      )}
    </div>
  );
}

/**
 * The refusals, as a prompt to refine rather than a failure.
 *
 * Each one names a term the registry does not define at the grain asked for, says why, and
 * offers the terms that would work. The alternatives are buttons: clicking one rewrites the
 * question in place and drops it back in the input, so a refused question costs a click rather
 * than a retype.
 *
 * An empty `alternatives` is a real answer, not a broken suggester - a metric that exists
 * enterprise-wide only has no legal breakdown to offer, and `reason` says so.
 */
function RefusalBlock({ turn, onPickSuggestion }: { turn: Turn; onPickSuggestion: (q: string) => void }) {
  const refusals = turn.resolved?.scope.refusals ?? [];
  if (refusals.length === 0) return null;
  const answerable = turn.resolved?.scope.is_answerable ?? false;
  return (
    <div
      style={{
        border: "1px solid var(--status-warning, var(--border))",
        borderRadius: "var(--radius)",
        padding: "8px 10px",
        fontSize: 12,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
        {answerable ? "Answered without part of this" : "Needs one more thing"}
      </div>
      {refusals.map((r) => (
        <div key={r.term} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ color: "var(--text-secondary)", lineHeight: 1.4 }}>{r.reason}</div>
          {r.alternatives.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {r.alternatives.map((alt) => (
                <button
                  key={alt}
                  onClick={() => onPickSuggestion(refineQuestion(turn.question, r.term, alt))}
                  style={{ ...chipStyle, background: "transparent", cursor: "pointer" }}
                >
                  {alt.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * The action half of an answer - the governed ranking, when the question asked where to act.
 *
 * "Where should we focus next week" is not a measurement question, and the scope resolver has
 * no shape for it: a scope names what to measure, this asks which row to work. The backend
 * attaches the Next Best Action ranking *alongside* the resolved scope for exactly these
 * questions (`ask_service._ACTION_INTENT`), and this is where it surfaces.
 *
 * Rendered above "Thinking…" because it is already computed - it comes back with the resolution,
 * in the 30-120s before Genie says anything. For an action question this block is usually the
 * whole answer, and Genie's prose arrives underneath it as commentary.
 *
 * Three things here are deliberate and worth not undoing:
 *   - `basis` is printed verbatim. It carries this run's live benchmark, team count and window,
 *     and it is the same string the Next Best Action panel prints. A paraphrase here is how the
 *     chat answer and the on-screen panel start describing different rankings.
 *   - An empty `actions` renders as a sentence, not as nothing. "No team is behind the
 *     benchmark" is good news and a real answer; rendering it as absence makes it read as a
 *     failure to answer.
 *   - When `scoped_to` is empty the heading says so. The ranking is grouped on Team (the
 *     radiologist's home practice); a question naming a Practice (the site the exam was read
 *     at) gets the full list rather than a filter against the wrong column, and the reader has
 *     to be able to tell which list they are looking at.
 */
function WorklistBlock({ worklist }: { worklist: AskWorklist }) {
  const [showBasis, setShowBasis] = useState(false);
  const { actions, scoped_to: scopedTo } = worklist;

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "8px 10px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
        Where to act {scopedTo ? `· ${scopedTo}` : "· across all teams"}
      </div>

      {actions.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          No team is behind the peer benchmark draft rate of{" "}
          {(worklist.benchmark_draft_rate * 100).toFixed(0)}% in this window. That is the answer,
          not an empty result - there is no ranked unlock to work right now.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {actions.map((a, i) => (
            <div key={a.team} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12 }}>
              <span style={{ color: "var(--text-muted)", minWidth: 14 }}>{i + 1}.</span>
              <div style={{ flex: 1, lineHeight: 1.45 }}>
                <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{a.team}</span>
                <span style={{ color: "var(--text-secondary)" }}> — {a.action}</span>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {/* The gap sits next to the unlock on purpose. A team 4 points off the
                      benchmark on a large book outranking one 60 points off on a small one is
                      correct, and looks like a sorting bug until both numbers are visible. */}
                  {Math.round(a.expected_unlock_tbwu).toLocaleString()} TBWU expected unlock ·{" "}
                  {a.gap_to_benchmark_pct.toFixed(0)} pts off benchmark ·{" "}
                  {(a.blocker_share_of_gap * 100).toFixed(0)}% behind {a.primary_blocker}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
        <button
          onClick={() => setShowBasis((s) => !s)}
          style={{ background: "transparent", border: "none", color: "var(--text-muted)", fontSize: 10, cursor: "pointer", padding: 0, textDecoration: "underline" }}
        >
          {showBasis ? "Hide how this is ranked" : "How this is ranked"}
        </button>
      </div>
      {showBasis && (
        <div style={{ fontSize: 10, color: "var(--text-secondary)", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
          {worklist.basis}
        </div>
      )}
    </div>
  );
}

function GenieTurn({
  turn,
  onPickSuggestion,
  onSwitchEntity,
}: {
  turn: Turn;
  onPickSuggestion: (q: string) => void;
  /** Re-ask *this* turn's question against the other column. Scoped per turn, not per panel:
   *  a conversation can name more than one entity, and the switch belongs to the answer it is
   *  rendered on. */
  onSwitchEntity: (question: string, kind: string) => void;
}) {
  const [showSql, setShowSql] = useState(false);
  const status = turn.state?.status;
  // A refused turn has no message to wait for. Without the `messageId` guard it would sit on
  // "Thinking…" forever, which reads as a hang rather than as the deliberate stop it is.
  const thinking = Boolean(turn.messageId) && (!status || !TERMINAL.has(status));

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

      {/* Above the answer and above "Thinking…", on purpose: the resolution is instant and the
          answer is not, so this is what fills the 30-120s a reader would otherwise spend
          wondering whether the question was understood. */}
      {turn.resolved && (
        <ScopeStrip
          resolved={turn.resolved}
          onSwitchEntity={(kind) => onSwitchEntity(turn.question, kind)}
        />
      )}
      <RefusalBlock turn={turn} onPickSuggestion={onPickSuggestion} />

      {/* Presence, not length. The backend omits the key entirely for a measurement question and
          sends it with an empty `actions` for an action question with nothing to work - those
          are different answers, and `?.actions?.length` would collapse the second into the
          first, rendering "no team is behind the benchmark" as silence. */}
      {turn.resolved?.worklist && <WorklistBlock worklist={turn.resolved.worklist} />}

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
