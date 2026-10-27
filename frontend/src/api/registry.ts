import { useEffect, useState } from "react";
import { mosaicApi } from "./client";
import type { RegistryFeature, RegistryMetric, RegistryMode, RegistrySnapshot } from "./types";

// One fetch of the governed registry per browser session, shared by every component that needs
// a definition, a threshold, or the solution axis.
//
// A single module-level promise rather than per-component state: ~40 AIHoverCards can be mounted
// on one page and they must not each issue a request. The backend route is frozen dataclasses
// with no EDW or cache access, so it resolves in milliseconds and is safe to fire on mount.
//
// This lived inside AIHoverCard.tsx until the solution axis needed it too. Copying the singleton
// would have meant two caches, two in-flight requests, and - the real cost - two places that
// could fall out of step about what the registry says. The whole point of the registry is that a
// definition is declared once; its client cannot be the exception.
let registryPromise: Promise<RegistrySnapshot | null> | null = null;
let registrySnapshot: RegistrySnapshot | null = null;
const subscribers = new Set<() => void>();

export function ensureRegistry(): Promise<RegistrySnapshot | null> {
  if (!registryPromise) {
    registryPromise = mosaicApi
      .getRegistry()
      .then((snap) => {
        registrySnapshot = snap;
        subscribers.forEach((fn) => fn());
        return snap;
      })
      // Fail soft and stay silent: a missing registry degrades each consumer back to exactly what
      // it did before the registry existed. It must never block a render or throw into one.
      .catch(() => null);
  }
  return registryPromise;
}

/** The snapshot, re-rendering the caller once it lands. `null` until then, and on failure. */
export function useRegistry(): RegistrySnapshot | null {
  const [, bump] = useState(0);
  useEffect(() => {
    if (registrySnapshot) return;
    const fn = () => bump((n) => n + 1);
    subscribers.add(fn);
    void ensureRegistry();
    return () => {
      subscribers.delete(fn);
    };
  }, []);
  return registrySnapshot;
}

/** Resolve one `feature` key against the snapshot. */
export function useRegistryFeature(feature: string): RegistryFeature | null {
  const snap = useRegistry();
  return snap?.features.find((f) => f.feature === feature) ?? null;
}

/**
 * The solution axis of the cube: Reporting, AI Drafting, Capture, Full Mosaic.
 *
 * Empty until the snapshot lands, so callers must keep their own default selection rather than
 * reading `modes[0]`.
 */
export function useSolutionModes(): RegistryMode[] {
  return useRegistry()?.modes ?? [];
}

/**
 * One metric's governed definition by key.
 *
 * Keys are globally unique and deployed column names are not: Volume and Capacity both ship a
 * column called `pct_mosaic` over denominators differing by roughly a quarter of all exams. Look
 * up by `key` here, never by the column name off a payload.
 */
export function useRegistryMetric(key: string): RegistryMetric | null {
  const snap = useRegistry();
  return snap?.metrics.find((m) => m.key === key) ?? null;
}
