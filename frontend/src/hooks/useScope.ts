import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * A cube scope, held in the URL rather than in component state.
 *
 * Every drill-down in this app used to dead-end in a Drawer with no address, so the only way to
 * show someone a finding was a screenshot. A scope that lives in the query string is a link: it
 * survives a reload, goes in a Teams message, and the back button steps through the questions
 * that were asked rather than leaving the page.
 *
 * This is a hook, not a context, and it has to stay one: `FilterProvider` is mounted above the
 * router's outlet in App.tsx, and `useSearchParams` throws outside a Router. Call this from a
 * routed component.
 */

export interface Scope {
  /** Registry metric keys, in display order. */
  metrics: string[];
  /** The single dimension forming the grid's columns: practice | team | local_region | month. */
  axis: string;
  /** Set when the grid is pinned to one entity rather than spread across the axis. */
  entityId: string | null;
  /** ISO dates; the day is ignored, months are the grain. */
  periodFrom: string | null;
  periodTo: string | null;
}

export type ScopePatch = Partial<Scope>;

const PARAM = {
  metrics: "m",
  axis: "by",
  entityId: "id",
  periodFrom: "from",
  periodTo: "to",
} as const;

/**
 * Read the scope from the URL, falling back to `fallback` for anything absent.
 *
 * Only values that differ from the fallback are written back, so a default scope has a clean
 * address and a shared link carries exactly the choices someone made - not a snapshot of every
 * default in force the day they copied it.
 */
export function useScope(fallback: Scope): [Scope, (patch: ScopePatch) => void] {
  const [params, setParams] = useSearchParams();

  const scope = useMemo<Scope>(() => {
    const raw = params.get(PARAM.metrics);
    const metrics = raw ? raw.split(",").filter(Boolean) : fallback.metrics;
    return {
      metrics: metrics.length ? metrics : fallback.metrics,
      axis: params.get(PARAM.axis) || fallback.axis,
      entityId: params.get(PARAM.entityId) || fallback.entityId,
      periodFrom: params.get(PARAM.periodFrom) || fallback.periodFrom,
      periodTo: params.get(PARAM.periodTo) || fallback.periodTo,
    };
    // `params` is a new object every render but its string form is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString(), fallback]);

  const patch = useCallback(
    (next: ScopePatch) => {
      const merged = { ...scope, ...next };
      const out = new URLSearchParams();
      const set = (key: string, value: string | null, fallbackValue: string | null) => {
        if (value && value !== fallbackValue) out.set(key, value);
      };
      set(PARAM.metrics, merged.metrics.join(","), fallback.metrics.join(","));
      set(PARAM.axis, merged.axis, fallback.axis);
      set(PARAM.entityId, merged.entityId, fallback.entityId);
      set(PARAM.periodFrom, merged.periodFrom, fallback.periodFrom);
      set(PARAM.periodTo, merged.periodTo, fallback.periodTo);
      // replace: false - each scope change is a step the back button should undo.
      setParams(out);
    },
    [scope, fallback, setParams],
  );

  return [scope, patch];
}
