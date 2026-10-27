import { useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { FilterBar } from "../components/FilterBar";
import { AIHoverCard } from "../components/AIHoverCard";
import { useFilters, matchesPractice } from "../context/FilterContext";
import { UndraftedStackedChart, CATEGORY_ORDER, DRAFTED_CATEGORY } from "../components/UndraftedStackedChart";
import { NextBestActions } from "../components/NextBestActions";
import { BriefingPanel } from "../components/BriefingPanel";
import { SolutionPin } from "../components/SolutionAxis";
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
          (!filters.local || r.local_region === filters.local)
      ),
    [undrafted.data, filters]
  );

  const byReason = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of filteredRows) counts.set(r.category, (counts.get(r.category) ?? 0) + (metric === "tbwu" ? r.tbwu : r.exam_count));
    return counts;
  }, [filteredRows, metric]);

  const byReasonExtra = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [category, value] of byReason.entries()) out[category] = value.toFixed(metric === "tbwu" ? 1 : 0);
    return out;
  }, [byReason, metric]);

  // Only the four plotted reasons. Summing every value in `byReason` - which is what this
  // used to do - counts "Drafted" and "Not Read on Mosaic" as not-drafted, so the headline
  // reported all 123M exams as leakage.
  const totalNotDrafted = CATEGORY_ORDER.reduce((sum, cat) => sum + (byReason.get(cat.key) ?? 0), 0);
  // Draft rate on the *worklist's* denominator, not the chart's. The chart divides by every
  // Mosaic-read exam so that no leakage is hidden; the worklist divides by what it can
  // actually convert - Drafted + the two addressable reasons - because a team cannot be
  // ranked on a procedure no model covers. Both are right for their own question and they
  // are different numbers, so this one is labelled with its denominator rather than being
  // shown as "the" draft rate.
  const drafted = byReason.get(DRAFTED_CATEGORY) ?? 0;
  const addressable =
    drafted +
    (byReason.get("Draftable - Rad Not Enrolled") ?? 0) +
    (byReason.get("Draftable - Not Drafted (Workflow)") ?? 0);
  const draftRate = addressable ? drafted / addressable : 0;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Non-Drafted Analysis</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Exams read on Mosaic that weren't drafted, broken down by reason, per week. The four reasons are
          mutually exclusive and come straight from <code>exam_not_draftable_reason</code>: a radiologist not yet
          enrolled in the model, an enrolled radiologist who didn't draft (workflow), a practice not enabled for
          the model, and a procedure no model covers. Only the first two are convertible by Clinical
          Transformation — the other two are deployment and model-coverage decisions.
        </div>
        <SolutionPin
          solution="drafting"
          elsewhere="Capture's equivalent gap is on the Capture page, and Efficiency carries all four solutions on one axis"
          style={{ marginTop: 8 }}
        />
      </div>

      {undrafted.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({undrafted.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <ToggleGroup
          options={[
            { value: "percent" as UndraftedDisplayMode, label: "% of Mosaic-Read" },
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
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 16,
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>
            <AIHoverCard
              feature="non_drafted_reason"
              entityLabel={filters.practice || "Enterprise-wide"}
              metricLabel={`Total not drafted (${metric === "tbwu" ? "TBWU" : "exams"})`}
              value={totalNotDrafted.toFixed(metric === "tbwu" ? 1 : 0)}
              extra={byReasonExtra}
            >
              {displayMode === "percent" ? "Percent of Mosaic-Read Exams Not Drafted, by Reason" : "Mosaic-Read Exams Not Drafted, by Reason"}
            </AIHoverCard>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
            Draft rate{" "}
            <strong style={{ color: "var(--text-primary)", fontSize: 15 }}>{(draftRate * 100).toFixed(1)}%</strong>{" "}
            of addressable
          </div>
        </div>
        {undrafted.data && <UndraftedStackedChart data={filteredRows} metric={metric} displayMode={displayMode} />}
      </div>

      {/* The chart above answers "where is it leaking"; this answers "which leak is worth the
          week". Deliberately *not* wired to the filter bar: it is a ranking across all teams,
          and filtering to one team would leave a list of one row whose only content is a
          benchmark computed from teams no longer shown. Its own benchmark control is the lever
          that belongs to it. */}
      <NextBestActions />

      {/* The same leakage in prose, for the weekly read rather than the daily one. It is the
          Drafting scope of the shared briefing - the generic renderer, not a drafting-specific
          component - so the three blocks it draws are whatever the backend declares the scope
          to be. Below the worklist deliberately: the worklist is what to do on Monday, the
          briefing is what to say about the week, and the second is only interesting once the
          first has been read. */}
      <BriefingPanel scope="drafting" />
    </div>
  );
}
