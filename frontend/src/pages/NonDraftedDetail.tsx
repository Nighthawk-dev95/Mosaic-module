import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice } from "../context/FilterContext";
import { getLocalRegion } from "../utils/localRegion";
import { UndraftedStackedChart } from "../components/UndraftedStackedChart";
import type { UndraftedDisplayMode, UndraftedMetric } from "../components/UndraftedStackedChart";

function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        fontSize: 13,
        padding: "6px 10px",
        borderRadius: 6,
        border: "1px solid var(--border)",
        background: "var(--surface-raised)",
        color: "var(--text-primary)",
      }}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            fontSize: 12,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: value === opt.value ? "var(--surface-raised)" : "transparent",
            color: value === opt.value ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function NonDraftedDetail() {
  const [metric, setMetric] = useState<UndraftedMetric>("exams");
  const [displayMode, setDisplayMode] = useState<UndraftedDisplayMode>("percent");
  const [examCategory, setExamCategory] = useState("");
  const [site, setSite] = useState("");
  const filters = useFilters();

  // exam_category/site are high-cardinality dimensions the backend collapses away from the
  // default response (unfiltered, they'd be ~845K rows / 120MB+) - narrowing by either
  // means a real refetch, unlike practice/month/local which filter client-side below.
  const undrafted = useFetch(
    () => mosaicApi.getUndraftedAnalysis({ exam_category: examCategory || undefined, site: site || undefined }),
    [examCategory, site]
  );
  const filterOptions = useFetch(() => mosaicApi.getUndraftedAnalysisFilters(), []);

  const practices = useMemo(() => {
    if (!undrafted.data) return [];
    return Array.from(new Set(undrafted.data.map((r) => r.local_practice).filter(Boolean) as string[])).sort();
  }, [undrafted.data]);

  const filteredRows = useMemo(
    () =>
      (undrafted.data ?? []).filter(
        (r) =>
          matchesPractice(filters, r.local_practice) &&
          (!filters.month || r.week_start.startsWith(filters.month)) &&
          (!filters.local || getLocalRegion(r.team) === filters.local)
      ),
    [undrafted.data, filters]
  );

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Non-Drafted Analysis</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Draftable exams that weren't drafted, broken down by reason, per week. Reasons follow the reconciled
          Clinical Transformation categorization: "Rad declined" is true declines only; radiologists who signed
          the IRB but aren't yet added to a model's AD group fall under "Incomplete process" instead.
        </div>
      </div>

      {undrafted.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({undrafted.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <ToggleGroup
          options={[
            { value: "percent" as UndraftedDisplayMode, label: "% of Draftable" },
            { value: "absolute" as UndraftedDisplayMode, label: "Absolute" },
          ]}
          value={displayMode}
          onChange={setDisplayMode}
        />
        <ToggleGroup
          options={[
            { value: "exams" as UndraftedMetric, label: "No. of Exams" },
            { value: "tbwu" as UndraftedMetric, label: "TBWU" },
          ]}
          value={metric}
          onChange={setMetric}
        />
      </div>

      <FilterBar practices={practices} />

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <FilterSelect
          value={examCategory}
          onChange={setExamCategory}
          options={filterOptions.data?.exam_categories ?? []}
          placeholder="All Exam Categories"
        />
        <FilterSelect value={site} onChange={setSite} options={filterOptions.data?.sites ?? []} placeholder="All Sites" />
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Percent of Draftable Cases Not Drafted, by Reason
        </div>
        {undrafted.data && <UndraftedStackedChart data={filteredRows} metric={metric} displayMode={displayMode} />}
      </div>
    </div>
  );
}
