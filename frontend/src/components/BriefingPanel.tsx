import { useCallback, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import type { BriefingScope, BriefingSection, BriefingSnapshot } from "../api/types";

/**
 * The weekly executive briefing for *any* scope, rendered without knowing what the scope is.
 *
 * Every briefing is three blocks, and the server says what they are called: `sections` carries
 * `label`, `description`, `values` and `deltas` per block. Nothing in this file names a stage,
 * an owner, a leakage category or a cohort, so a fourth scope is a backend declaration and not
 * a frontend ticket. MvpWeeklyReport.tsx is the opposite choice and deliberately so - it knows
 * the MVP funnel has three statuses and draws them stacked, which this cannot and should not.
 *
 * Two rules this file exists to keep:
 *
 * **The label is a caption; the slot is the identity.** Labels are not stored - the read path
 * attaches them from the scope declaration at request time. So they are read off the section on
 * every render and never memoised against `slot`: editing a scope's wording must change what
 * every past week is called, because the wording was never part of the week's data.
 *
 * **A null delta is "no comparison", never zero.** `deltas` mirrors `values` with `null` where
 * there is nothing to subtract - a first-ever snapshot, or a key that did not exist last week.
 * Rendering that as `0` would claim a flat week on evidence that does not exist. It renders as
 * an em dash, and `has_previous: false` says so once at the top rather than thirty times.
 */

// Unit comes from the key's own suffix, not from a per-scope table - that would be exactly the
// scope knowledge this component is built to not have. `_pct` and `_tbwu` are the two
// conventions the backend's section computers already use; anything else is a count. Keys that
// are already prose ("Draftable - Rad Not Enrolled", "Deployment (practice not enabled)") are
// passed through untouched, which is why the humaniser tests for word characters rather than
// unconditionally splitting on underscores.
const UNIT_SUFFIXES: ReadonlyArray<readonly [string, string]> = [
  ["_pct", "%"],
  ["_tbwu", " TBWU"],
];

function splitUnit(key: string): [string, string] {
  for (const [suffix, unit] of UNIT_SUFFIXES) {
    if (key.endsWith(suffix)) return [key.slice(0, -suffix.length), unit];
  }
  return [key, ""];
}

function humanize(key: string): string {
  const [base] = splitUnit(key);
  // Already written for a reader - a category name or an owner sentence. Leave it alone;
  // title-casing it would turn "Draftable - Rad Not Enrolled" into something subtly different
  // from the same string on the chart directly above this panel.
  if (/\s/.test(base) || /[A-Z]/.test(base)) return base;
  const words = base.split("_").filter(Boolean);
  if (!words.length) return key;
  return words.map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");
}

function fmtNumber(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: Math.abs(n) < 10 && !Number.isInteger(n) ? 1 : 0 });
}

function fmtValue(key: string, n: number): string {
  const [, unit] = splitUnit(key);
  return `${fmtNumber(n)}${unit}`;
}

function fmtDelta(key: string, n: number | null | undefined): { text: string; color: string } {
  if (n === null || n === undefined) return { text: "—", color: "var(--text-muted)" };
  if (n === 0) return { text: "No change", color: "var(--text-muted)" };
  const [, unit] = splitUnit(key);
  return {
    text: `${n > 0 ? "+" : "−"}${fmtNumber(Math.abs(n))}${unit} vs last week`,
    // Deliberately not green/red. Up is good for unlock and bad for leakage, and this component
    // has no way to know which this key is - colouring the arrow would be a verdict it cannot
    // support. Direction is in the sign; the reader supplies the meaning.
    color: "var(--text-secondary)",
  };
}

const CARD: React.CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
};

function Metric({ label, value, delta }: { label: string; value: string; delta: { text: string; color: string } }) {
  return (
    <div style={{ minWidth: 150, flex: "1 1 150px" }}>
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 2 }}>{label}</div>
      <div style={{ color: "var(--text-primary)", fontSize: 20, fontWeight: 600 }}>{value}</div>
      <div style={{ color: delta.color, fontSize: 11, marginTop: 2 }}>{delta.text}</div>
    </div>
  );
}

/**
 * One block, split by the shape of each entry rather than by the shape of the section.
 *
 * Flat entries (`key: number`) become one row of metrics; nested ones
 * (`group: {key: number}` - the MVP funnel's shape) become a labelled sub-row each. The split
 * is per entry and not per section on purpose: the backend's `_check_section_shape` validates
 * each value independently, so a section holding both a nested funnel and a loose total beside
 * it is legal. Branching once on `values.some(isObject)` would type-cast the flat keys to `{}`
 * and drop them silently - a section that renders but is missing a number.
 */
function SectionBlock({ section }: { section: BriefingSection }) {
  const entries = Object.entries(section.values);
  const flat = entries.filter(([, v]) => typeof v !== "object" || v === null) as Array<[string, number]>;
  const groups = entries.filter(([, v]) => typeof v === "object" && v !== null) as Array<
    [string, Record<string, number>]
  >;

  return (
    <div style={CARD}>
      <div style={{ color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {section.label}
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4, marginBottom: 14, lineHeight: 1.4 }}>
        {section.description}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {flat.length > 0 && (
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            {flat.map(([key, n]) => (
              <Metric
                key={key}
                label={humanize(key)}
                value={fmtValue(key, n)}
                delta={fmtDelta(key, section.deltas[key] as number | null | undefined)}
              />
            ))}
          </div>
        )}
        {groups.map(([group, inner]) => {
          const innerDeltas = (section.deltas[group] ?? {}) as Record<string, number | null>;
          return (
            <div key={group}>
              <div style={{ color: "var(--text-secondary)", fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                {humanize(group)}
              </div>
              <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                {Object.entries(inner).map(([key, n]) => (
                  <Metric
                    key={key}
                    label={humanize(key)}
                    value={fmtValue(key, n)}
                    delta={fmtDelta(key, innerDeltas[key])}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function BriefingPanel({ scope }: { scope: BriefingScope }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const briefing = useFetch<BriefingSnapshot>(() => mosaicApi.getBriefing(scope), [scope, refreshKey]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setGenError(null);
    try {
      await mosaicApi.generateBriefing(scope);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setGenError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  }, [scope]);

  // A scope with no snapshot yet is the normal first state, not a failure: the route 404s by
  // design rather than inventing an empty week. Anything else is a real fetch error and says so
  // separately, because "nobody has generated this yet" and "the backend is down" need
  // different buttons.
  const notGeneratedYet = briefing.error !== null && briefing.error.includes(" 404 ");

  if (briefing.loading) {
    return <div style={{ ...CARD, color: "var(--text-muted)", fontSize: 13 }}>Loading briefing…</div>;
  }

  if (notGeneratedYet || !briefing.data) {
    return (
      <div style={{ ...CARD, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>
          {notGeneratedYet
            ? "No weekly briefing has been generated for this scope yet."
            : `Couldn't load the briefing. (${briefing.error})`}
        </div>
        {notGeneratedYet && (
          <div>
            <button onClick={generate} disabled={generating} style={BUTTON_STYLE}>
              {generating ? "Generating…" : "Generate this week's briefing"}
            </button>
          </div>
        )}
        {genError && <div style={{ color: "var(--status-critical)", fontSize: 12 }}>{genError}</div>}
      </div>
    );
  }

  const snap = briefing.data;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ color: "var(--text-primary)", fontSize: 15, fontWeight: 600 }}>
            {snap.scope_label} — week ending {snap.week_ending}
          </div>
          {!snap.has_previous && (
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 2 }}>
              First stored week for this scope — nothing to compare against yet.
            </div>
          )}
        </div>
        <button onClick={generate} disabled={generating} style={BUTTON_STYLE}>
          {generating ? "Regenerating…" : "Regenerate"}
        </button>
      </div>
      {genError && <div style={{ color: "var(--status-critical)", fontSize: 12 }}>{genError}</div>}

      {snap.sections.map((section) => (
        <SectionBlock key={section.slot} section={section} />
      ))}

      <div style={CARD}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
          Key insights this week
        </div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{snap.key_insights}</div>
      </div>
      <div style={CARD}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
          Focus next week
        </div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{snap.focus_next_week}</div>
      </div>
    </div>
  );
}

const BUTTON_STYLE: React.CSSProperties = {
  padding: "6px 12px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: 12,
  cursor: "pointer",
};
