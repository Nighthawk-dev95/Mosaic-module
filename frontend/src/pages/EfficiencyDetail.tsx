import { useEffect, useMemo, useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { TABLE_SECTION_STYLE, TABLE_SCROLL_STYLE } from "../styles/tableLayout";
import { EfficiencyTrendChart } from "../components/EfficiencyTrendChart";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
import type {
  EfficiencyMode,
  EfficiencyPracticeRollup,
  EfficiencyRadiologistItem,
  PopulationEfficiency,
} from "../api/types";

function fmtRate(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toFixed(3);
}

const MODES: { value: EfficiencyMode; label: string }[] = [
  { value: "full_mosaic", label: "Full Mosaic" },
  { value: "reporting", label: "Reporting Only" },
  { value: "drafting", label: "Drafting Only" },
  { value: "capture", label: "Capture Only" },
];

type ViewFilter = "all" | "positive" | "negative";

const PRACTICE_COLUMNS: DataTableColumn<EfficiencyPracticeRollup>[] = [
  { key: "practice", label: "Practice" },
  { key: "mosaic_tbwu_per_min", label: "Mosaic TBWU / min", render: (r) => fmtRate(r.mosaic_tbwu_per_min) },
  { key: "baseline_tbwu_per_min", label: "Baseline TBWU / min", render: (r) => fmtRate(r.baseline_tbwu_per_min) },
  { key: "pct_change_vs_baseline", label: "Change vs Baseline", render: (r) => fmtPct(r.pct_change_vs_baseline) },
  { key: "read_time_change_pct", label: "Read Time Change", render: (r) => fmtPct(r.read_time_change_pct) },
];

const RAD_COLUMNS: DataTableColumn<EfficiencyRadiologistItem>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "practice", label: "Practice" },
  { key: "subspecialty", label: "Subspecialty" },
  { key: "mosaic_tbwu_per_min", label: "Mosaic TBWU / min", render: (r) => fmtRate(r.mosaic_tbwu_per_min) },
  { key: "baseline_tbwu_per_min", label: "Baseline TBWU / min", render: (r) => fmtRate(r.baseline_tbwu_per_min) },
  { key: "pct_change_vs_baseline", label: "Change vs Baseline", render: (r) => fmtPct(r.pct_change_vs_baseline) },
  { key: "read_time_change_pct", label: "Read Time Change", render: (r) => fmtPct(r.read_time_change_pct) },
];

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

function PopulationTile({ label, data }: { label: string; data: PopulationEfficiency | null }) {
  return (
    <div
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "16px 20px",
        flex: "1 1 260px",
        minWidth: 240,
      }}
    >
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", gap: 24 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-primary)" }}>
            {fmtRate(data?.mosaic_tbwu_per_min)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Mosaic TBWU/min</div>
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-secondary)" }}>
            {fmtRate(data?.baseline_tbwu_per_min)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Baseline TBWU/min</div>
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-primary)" }}>
            {fmtPct(data?.pct_change_vs_baseline)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Change vs Baseline</div>
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text-primary)" }}>
            {fmtPct(data?.read_time_change_pct)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Read Time Change</div>
        </div>
      </div>
    </div>
  );
}

function pctChange(current: number | null | undefined, baseline: number | null | undefined): number | null {
  if (current == null || baseline == null || baseline === 0) return null;
  return (current - baseline) / baseline;
}

function readTimeChange(current: number | null | undefined, baseline: number | null | undefined): number | null {
  if (current == null || baseline == null || current === 0) return null;
  return baseline / current - 1;
}

export function EfficiencyDetail() {
  const [mode, setMode] = useState<EfficiencyMode>("full_mosaic");
  const [viewFilter, setViewFilter] = useState<ViewFilter>("all");
  const filters = useFilters();
  const practice = filters.practice;
  const [subspecialty, setSubspecialty] = useState("");
  const [modality, setModality] = useState("");
  const [procedure, setProcedure] = useState("");
  const [examCategory, setExamCategory] = useState("");

  const detail = useFetch(() => mosaicApi.getEfficiencyDetail(mode), [mode]);
  const filterOptions = useFetch(() => mosaicApi.getEfficiencyFilters(), []);
  const trend = useFetch(
    () => mosaicApi.getEfficiencyTrend(examCategory || undefined, practice || undefined),
    [examCategory, practice]
  );
  const rpAvgTrend = useFetch(() => mosaicApi.getEfficiencyTrendRpAvg(), []);

  const [population, setPopulation] = useState<PopulationEfficiency | null>(null);
  useEffect(() => {
    let cancelled = false;
    mosaicApi
      .getEfficiencyPopulation({
        mode,
        practice: practice || undefined,
        subspecialty: subspecialty || undefined,
        modality_code: modality || undefined,
        parent_procedure_name: procedure || undefined,
        exam_category: examCategory || undefined,
      })
      .then((res) => {
        if (!cancelled) setPopulation(res);
      })
      .catch(() => {
        if (!cancelled) setPopulation(null);
      });
    return () => {
      cancelled = true;
    };
  }, [mode, practice, subspecialty, modality, procedure, examCategory]);

  const rpBenchmark: PopulationEfficiency | null = detail.data
    ? {
        mode: detail.data.mode,
        practice: null,
        subspecialty: null,
        modality_code: null,
        parent_procedure_name: null,
        exam_category: null,
        mosaic_tbwu_per_min: detail.data.rp_benchmark_mosaic_tbwu_per_min,
        baseline_tbwu_per_min: detail.data.rp_benchmark_baseline_tbwu_per_min,
        pct_change_vs_baseline: pctChange(
          detail.data.rp_benchmark_mosaic_tbwu_per_min,
          detail.data.rp_benchmark_baseline_tbwu_per_min
        ),
        read_time_change_pct: readTimeChange(
          detail.data.rp_benchmark_mosaic_tbwu_per_min,
          detail.data.rp_benchmark_baseline_tbwu_per_min
        ),
      }
    : null;

  const filteredRadRows = useMemo(() => {
    if (!detail.data) return [];
    return detail.data.by_radiologist.filter((r) => {
      if (!matchesPractice(filters, r.practice)) return false;
      if (!matchesRadiologistSearch(filters, r.radiologist_name, r.npi)) return false;
      if (subspecialty && r.subspecialty !== subspecialty) return false;
      if (viewFilter === "positive" && !(r.pct_change_vs_baseline != null && r.pct_change_vs_baseline > 0)) return false;
      if (viewFilter === "negative" && !(r.pct_change_vs_baseline != null && r.pct_change_vs_baseline < 0)) return false;
      return true;
    });
  }, [detail.data, filters, subspecialty, viewFilter]);

  const filteredPracticeRows = useMemo(() => {
    if (!detail.data) return [];
    return detail.data.by_practice.filter((r) => matchesPractice(filters, r.practice));
  }, [detail.data, filters]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Efficiency</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          TBWU per minute read time vs. each radiologist's own PowerScribe baseline, matched at the parent-procedure level.
        </div>
      </div>

      {detail.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({detail.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <ToggleGroup options={MODES} value={mode} onChange={setMode} />
        <ToggleGroup
          options={[
            { value: "all" as ViewFilter, label: "All" },
            { value: "positive" as ViewFilter, label: "Positive" },
            { value: "negative" as ViewFilter, label: "Negative" },
          ]}
          value={viewFilter}
          onChange={setViewFilter}
        />
      </div>

      <FilterBar practices={filterOptions.data?.practices ?? []} showLocal={false} showMonth={false} />

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <FilterSelect
          value={subspecialty}
          onChange={setSubspecialty}
          options={filterOptions.data?.subspecialties ?? []}
          placeholder="All Subspecialties"
        />
        <FilterSelect value={modality} onChange={setModality} options={filterOptions.data?.modalities ?? []} placeholder="All Modalities" />
        <FilterSelect
          value={procedure}
          onChange={setProcedure}
          options={filterOptions.data?.procedures ?? []}
          placeholder="All Procedures"
        />
        <FilterSelect
          value={examCategory}
          onChange={setExamCategory}
          options={filterOptions.data?.exam_categories ?? []}
          placeholder="All Exam Categories"
        />
      </div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: -12 }}>
        Practice/Subspecialty also narrow the tables below; Modality/Procedure only narrow the Population Efficiency comparison;
        Exam Category also narrows the trend charts below.
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <PopulationTile label="RP Benchmark (company-wide, ignores filters)" data={rpBenchmark} />
        <PopulationTile label="Population Efficiency (current filters)" data={population} />
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Mosaic Efficiency Over Time
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 8 }}>
          Dashed "RP Avg" reference lines are company-wide and ignore every filter, including Practice.
        </div>
        {trend.data && <EfficiencyTrendChart trend={trend.data} rpAvg={rpAvgTrend.data ?? undefined} mode="absolute" />}
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Efficiency Change Over Time
        </div>
        {trend.data && <EfficiencyTrendChart trend={trend.data} mode="change" />}
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Practice
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {detail.data && (
            <DataTable columns={PRACTICE_COLUMNS} rows={filteredPracticeRows} rowKey={(r) => r.practice ?? "unknown"} />
          )}
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {detail.data && <DataTable columns={RAD_COLUMNS} rows={filteredRadRows} rowKey={(r) => r.npi} />}
        </div>
      </div>
    </div>
  );
}
