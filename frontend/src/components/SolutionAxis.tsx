import { useState } from "react";
import type { CSSProperties } from "react";
import { useSolutionModes } from "../api/registry";
import type { EfficiencyMode } from "../api/types";

/**
 * The solution axis of the Mosaic cube: Reporting, AI Drafting, Capture, Full Mosaic.
 *
 * Mosaic is a product with three solutions measured on four metrics across every radiologist and
 * practice - a cube, not a metric list. This control is the axis that makes that structural
 * rather than rhetorical: "how is Drafting doing" becomes a first-class question instead of a
 * filter someone remembers to apply.
 *
 * Why it reads the registry instead of a local array
 * --------------------------------------------------
 * Every page that offered this toggle hand-typed its own four labels. That is survivable while
 * the labels are only labels - and it stops being survivable the moment one of them carries a
 * definition. `full_mosaic` is Reporting + Drafting and deliberately *excludes* Capture,
 * mirroring the upstream ETL's `Is_Mosaic_Row`. A reader who assumes "Full Mosaic" means all
 * three will mis-read every number under it, and no amount of label-writing fixes that: the
 * governed sentence has to travel with the control. It does now, on hover.
 *
 * The keys are also the backend's: `EFFICIENCY_MODES` in app/semantics/registry.py holds the
 * same four, pointing at `efficiency_store._MODE_EXPRS` by reference rather than by copy, with a
 * parity test asserting the identity. So the word means one thing from the SQL expression
 * through to this button.
 *
 * Degradation: `modes` is empty until the snapshot lands and stays empty if the fetch fails, so
 * the caller's `fallback` renders instead. A page must never lose its solution toggle because a
 * definition endpoint was slow.
 *
 * Why unavailable solutions are disabled rather than hidden
 * ---------------------------------------------------------
 * Not every surface can answer for all four. Efficiency can: the solution is a filter mode, and
 * `_MODE_EXPRS` has an expression for each. Volume and Capacity cannot: there the solution is a
 * *different column*, and no Capture volume column exists - the ETL has no capture equivalent of
 * `mosaic_exams`. Hiding the button would make the cube look complete and quietly change what
 * "all solutions" means from page to page; a reader comparing two surfaces would have no way to
 * tell a solution that is at zero from one that is not measured. A disabled button that says why
 * is the honest shape, and it is the same shape the registry already uses for a refused scope.
 */
export function SolutionAxis({
  value,
  onChange,
  fallback,
  available,
  unavailableNote,
  style,
}: {
  value: EfficiencyMode;
  onChange: (v: EfficiencyMode) => void;
  /** Labels to show before the registry lands. Keys must match the registry's. */
  fallback: { value: EfficiencyMode; label: string }[];
  /**
   * Which solutions this surface can actually resolve. Omit on a surface that serves all four
   * (Efficiency). Anything outside the list renders disabled with `unavailableNote`.
   */
  available?: readonly EfficiencyMode[];
  /** Why the others are absent here. Required in practice whenever `available` is passed. */
  unavailableNote?: string;
  style?: CSSProperties;
}) {
  const modes = useSolutionModes();
  const [hovered, setHovered] = useState<string | null>(null);

  const options = modes.length
    ? modes.map((m) => ({ value: m.key as EfficiencyMode, label: m.label, description: m.description }))
    : fallback.map((f) => ({ ...f, description: "" }));

  const isAvailable = (v: EfficiencyMode) => !available || available.includes(v);

  const active = options.find((o) => o.value === hovered);
  // An unavailable button explains its absence rather than its meaning - the definition is not
  // the thing the reader is confused about.
  const activeNote =
    active && !isAvailable(active.value) ? unavailableNote ?? "" : active?.description ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, ...style }}>
      <div style={{ display: "flex", gap: 4 }}>
        {options.map((opt) => {
          const enabled = isAvailable(opt.value);
          return (
            <button
              key={opt.value}
              disabled={!enabled}
              onClick={() => enabled && onChange(opt.value)}
              onMouseEnter={() => setHovered(opt.value)}
              onMouseLeave={() => setHovered((h) => (h === opt.value ? null : h))}
              // The governed description is also the title attribute: the inline strip below is
              // the discoverable path, this is the one that survives a screenshot being pasted
              // into a deck. A disabled button carries the reason instead - `title` still fires
              // on a disabled button in every browser we target, and the strip below covers the
              // case where it does not.
              title={(enabled ? opt.description : unavailableNote) || undefined}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: value === opt.value && enabled ? "var(--surface-raised)" : "transparent",
                color: !enabled
                  ? "var(--text-muted)"
                  : value === opt.value
                    ? "var(--text-primary)"
                    : "var(--text-secondary)",
                // Struck through, not just greyed: grey alone reads as "unselected" on a toggle
                // whose unselected state is already grey.
                textDecoration: enabled ? "none" : "line-through",
                cursor: enabled ? "pointer" : "not-allowed",
                opacity: enabled ? 1 : 0.65,
              }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {/* Reserve the line whether or not it is filled, so hovering the axis does not reflow the
          page beneath it. */}
      <div
        style={{
          fontSize: 11,
          lineHeight: "15px",
          minHeight: 15,
          color: "var(--text-muted)",
          maxWidth: 680,
        }}
      >
        {activeNote}
      </div>
    </div>
  );
}

/**
 * The labels to show before the registry lands, and the only place they are written down.
 *
 * Not a second definition of the axis - a definition would include what each solution *means*,
 * and that is exactly what these do not carry. They exist so a page renders a usable toggle
 * during the first few milliseconds of a session, and are replaced wholesale the moment the
 * governed modes arrive.
 */
export const SOLUTION_FALLBACK: { value: EfficiencyMode; label: string }[] = [
  { value: "full_mosaic", label: "Full Mosaic" },
  { value: "reporting", label: "Reporting Only" },
  { value: "drafting", label: "Drafting Only" },
  { value: "capture", label: "Capture Only" },
];

/**
 * Which solutions a surface is *not* showing, given the one it is pinned to.
 *
 * `full_mosaic` is the only entry that is not a sibling of the other three: it already contains
 * Reporting and Drafting, so the single thing it leaves out is Capture. Spelling that out here
 * rather than computing "the other three" is the point - a derived list would claim a
 * `full_mosaic` surface omits Reporting and Drafting, which is the exact misreading the axis
 * docstring exists to prevent.
 */
const SOLUTIONS_ABSENT: Record<EfficiencyMode, EfficiencyMode[]> = {
  full_mosaic: ["capture"],
  reporting: ["drafting", "capture"],
  drafting: ["reporting", "capture"],
  capture: ["reporting", "drafting"],
};

/**
 * The same axis, declared rather than chosen: for a surface that sits at one fixed point on it.
 *
 * `SolutionAxis` is for pages that can move along the solution axis. Most cannot. Capture, the
 * non-drafted leakage taxonomy and Draft-vs-Final are each built around one solution - the page
 * *is* the solution's surface, and a four-button toggle with three buttons struck through would
 * be a control that changes nothing. But the reader still has to be told where they are standing,
 * and today they are not: nothing on those pages names the solution at all, so the cube's third
 * dimension is invisible on every surface that does not happen to carry a toggle. A number that
 * silently covers one solution reads exactly like a number that covers the product.
 *
 * Why the page passes the key and the registry supplies the words
 * ---------------------------------------------------------------
 * The obvious shortcut - derive the solution from the page's registry feature - is wrong, and
 * wrong in a way that would render confidently. `efficiency_metric` declares
 * `solutions=("reporting", "drafting", "capture")` because the *metric* can be measured on all
 * three; `DraftVsFinal` pins it to drafting. Deriving would print "all three solutions" on a
 * drafting-only page. And the leakage taxonomy is one of the deliberately unregistered features,
 * so its metrics array is empty and a derived pin would print nothing at all. A metric's
 * `solutions` tuple answers "what can this be measured on", never "what is this page showing".
 * So the page states the fact it alone knows, and the registry supplies the governed sentence -
 * the same division of labour `SolutionAxis` already uses.
 *
 * Degradation matches the axis: `SOLUTION_FALLBACK` carries the label until the snapshot lands,
 * and a missing registry costs the description, never the pin.
 */
export function SolutionPin({
  solution,
  elsewhere,
  style,
}: {
  solution: EfficiencyMode;
  /**
   * Where the absent solutions *are* measured. Without it the pin says what this surface omits
   * but leaves the reader with nowhere to go, which is half an answer.
   */
  elsewhere?: string;
  style?: CSSProperties;
}) {
  const modes = useSolutionModes();
  const labelOf = (key: EfficiencyMode) =>
    modes.find((m) => m.key === key)?.label ??
    SOLUTION_FALLBACK.find((f) => f.value === key)?.label ??
    key;
  const description = modes.find((m) => m.key === solution)?.description ?? "";
  const absent = SOLUTIONS_ABSENT[solution] ?? [];

  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap", ...style }}>
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: 0.4,
          textTransform: "uppercase",
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          borderRadius: 3,
          padding: "2px 7px",
          whiteSpace: "nowrap",
        }}
        title={description || undefined}
      >
        Solution · {labelOf(solution)}
      </span>
      <span style={{ fontSize: 11, lineHeight: "16px", color: "var(--text-muted)", maxWidth: 680 }}>
        {description && `${description} `}
        {absent.length > 0 && (
          <>
            {absent.map(labelOf).join(" and ")} {absent.length > 1 ? "are" : "is"} not measured on
            this surface{elsewhere ? ` - ${elsewhere}` : ""}.
          </>
        )}
      </span>
    </div>
  );
}
