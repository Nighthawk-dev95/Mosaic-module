import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LocalRegion } from "../utils/localRegion";

export interface Filters {
  practice: string;
  local: LocalRegion | "";
  radiologistSearch: string;
  captureEnabledOnly: boolean;
  month: string; // "YYYY-MM", empty = all time
}

interface FilterContextValue extends Filters {
  setPractice: (v: string) => void;
  setLocal: (v: LocalRegion | "") => void;
  setRadiologistSearch: (v: string) => void;
  setCaptureEnabledOnly: (v: boolean) => void;
  setMonth: (v: string) => void;
  reset: () => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [practice, setPractice] = useState("");
  const [local, setLocal] = useState<LocalRegion | "">("");
  const [radiologistSearch, setRadiologistSearch] = useState("");
  const [captureEnabledOnly, setCaptureEnabledOnly] = useState(false);
  const [month, setMonth] = useState("");

  const value = useMemo<FilterContextValue>(
    () => ({
      practice,
      local,
      radiologistSearch,
      captureEnabledOnly,
      month,
      setPractice,
      setLocal,
      setRadiologistSearch,
      setCaptureEnabledOnly,
      setMonth,
      reset: () => {
        setPractice("");
        setLocal("");
        setRadiologistSearch("");
        setCaptureEnabledOnly(false);
        setMonth("");
      },
    }),
    [practice, local, radiologistSearch, captureEnabledOnly, month]
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used within a FilterProvider");
  return ctx;
}

// Shared match helpers - a filter that doesn't apply to a given row shape (e.g. no `team`
// field present) simply doesn't exclude it, rather than silently fabricating a match.
export function matchesPractice(filters: Filters, practice: string | null | undefined): boolean {
  return !filters.practice || practice === filters.practice;
}

export function matchesRadiologistSearch(
  filters: Filters,
  name: string | null | undefined,
  npi?: number | null
): boolean {
  if (!filters.radiologistSearch) return true;
  const q = filters.radiologistSearch.toLowerCase();
  return Boolean(name?.toLowerCase().includes(q)) || String(npi ?? "").includes(q);
}
