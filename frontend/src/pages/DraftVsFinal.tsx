import { useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import { AIHoverCard } from "../components/AIHoverCard";
import { Badge } from "../components/Badge";
import { DataTable, fmtPct } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";
import { SolutionPin } from "../components/SolutionAxis";
import type { DraftInsightCategoryStat, DraftInsightModalityStat, DraftInsightPracticeStat, DraftInsightSampleItem } from "../api/types";

const ASSESSMENT_COLORS: Record<string, string> = {
  "Highly Useful": "var(--status-good)",
  "Moderately Useful": "var(--series-4-yellow)",
  "Slightly Useful": "var(--status-warning)",
  "Not Useful": "var(--status-critical)",
};

const ASSESSMENT_ORDER = ["Highly Useful", "Moderately Useful", "Slightly Useful", "Not Useful"];

// Ranked horizontal bars for magnitude comparison - same pattern/reasoning as
// MosaicIntelligence.tsx's ThemeBarCard (rank+label already carry identity, one hue per
// bar is enough), reimplemented locally here since that component isn't shared/exported.
function CategoryBarCard({ title, categories, colorFor }: {
  title: string;
  categories: DraftInsightCategoryStat[];
  colorFor?: (category: string) => string;
}) {
  const maxCount = categories.length ? categories[0].count : 0;
  return (
    <div style={{ ...CARD_STYLE, flex: "1 1 280px" }}>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>{title}</div>
      {categories.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No data yet</div>}
      {categories.map((c) => (
        <div key={c.category} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
          <span style={{ color: "var(--text-secondary)", fontSize: 12, width: 160, flexShrink: 0 }}>{c.category}</span>
          <div style={{ flex: 1, background: "var(--gridline)", height: 16, position: "relative" }}>
            <div
              style={{
                width: `${maxCount ? (c.count / maxCount) * 100 : 0}%`,
                height: "100%",
                background: colorFor ? colorFor(c.category) : "var(--series-5-magenta)",
                borderRadius: "0 4px 4px 0",
              }}
            />
          </div>
          <span style={{ color: "var(--text-primary)", fontSize: 12, fontWeight: 600, width: 42, textAlign: "right", flexShrink: 0 }}>
            {c.pct.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function fmt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

function fmtRetention(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function truncate(value: string | null, max = 140): string {
  if (!value) return "—";
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

const MODALITY_COLUMNS: DataTableColumn<DraftInsightModalityStat>[] = [
  { key: "modality", label: "Modality", render: (r) => r.modality ?? "Unknown" },
  { key: "n", label: "Exams Assessed", render: (r) => fmt(r.n) },
  { key: "avg_retention_pct", label: "Avg Retention %", render: (r) => fmtRetention(r.avg_retention_pct) },
];

const PRACTICE_COLUMNS: DataTableColumn<DraftInsightPracticeStat>[] = [
  { key: "practice", label: "Practice", render: (r) => r.practice ?? "Unknown" },
  { key: "n", label: "Exams Assessed", render: (r) => fmt(r.n) },
  { key: "avg_retention_pct", label: "Avg Retention %", render: (r) => fmtRetention(r.avg_retention_pct) },
];

const SAMPLE_COLUMNS: DataTableColumn<DraftInsightSampleItem>[] = [
  { key: "accession_number", label: "Accession" },
  {
    key: "overall_assessment",
    label: "Assessment",
    render: (r) => <Badge label={r.overall_assessment ?? "Unknown"} color={ASSESSMENT_COLORS[r.overall_assessment ?? ""] ?? "var(--text-secondary)"} />,
  },
  { key: "retention_pct", label: "Retention %", render: (r) => (r.retention_pct === null ? "—" : `${r.retention_pct}%`) },
  { key: "added_by_radiologist", label: "Added by Radiologist", render: (r) => truncate(r.added_by_radiologist) },
  { key: "removed_from_draft", label: "Removed / Changed", render: (r) => truncate(r.removed_from_draft) },
];

export function DraftVsFinal() {
  const [assessmentFilter, setAssessmentFilter] = useState("");

  const overview = useFetch(() => mosaicApi.getDraftInsightOverview(), []);
  const byModality = useFetch(() => mosaicApi.getDraftInsightByModality(), []);
  const byPractice = useFetch(() => mosaicApi.getDraftInsightByPractice(), []);
  const categories = useFetch(() => mosaicApi.getDraftInsightCategories(), []);
  const samples = useFetch(
    () => mosaicApi.getDraftInsightSamples({ overall_assessment: assessmentFilter || undefined, limit: 100 }),
    [assessmentFilter]
  );

  const anyError = overview.error || byModality.error || byPractice.error || categories.error || samples.error;

  const distribution = overview.data?.overall_assessment_distribution ?? {};
  const totalAssessed = overview.data?.n ?? 0;
  const highlyUsefulPct = totalAssessed ? ((distribution["Highly Useful"] ?? 0) / totalAssessed) * 100 : null;
  const notUsefulPct = totalAssessed ? ((distribution["Not Useful"] ?? 0) / totalAssessed) * 100 : null;

  const assessmentBars: DraftInsightCategoryStat[] = ASSESSMENT_ORDER.filter((label) => distribution[label] !== undefined).map((label) => ({
    category: label,
    count: distribution[label],
    pct: totalAssessed ? (distribution[label] / totalAssessed) * 100 : 0,
  }));

  const categoryTitles: Record<string, string> = {
    added_by_radiologist: "What Radiologists Added",
    removed_from_draft: "What Got Removed / Changed",
    formatting: "Formatting Changes",
    clinical_interpretation: "Clinical Interpretation Changes",
    additional_findings: "Additional Findings Added",
  };

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Draft vs Final</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          AI-assessed comparison of Mosaic AI draft findings against the radiologist's final signed report - a bounded recent sample, not the
          full drafted population (see tools/draft_insights).
        </div>
        <SolutionPin
          solution="drafting"
          elsewhere="there is no draft-to-final comparison for Reporting or Capture, since neither produces an AI draft to compare against"
          style={{ marginTop: 8 }}
        />
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      {overview.data && totalAssessed === 0 && (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          No assessed exams yet - tools/draft_insights/001_build_draft_insights_sample.sql hasn't been run, or a refresh hasn't picked it up
          yet.
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <StatTile label="Exams Assessed" value={overview.data ? fmt(overview.data.n) : "…"} accent="var(--domain-efficiency)" />
        <AIHoverCard
          feature="efficiency_metric"
          entityLabel="Sampled exams"
          metricLabel="Average draft retention"
          value={overview.data ? fmtRetention(overview.data.avg_retention_pct) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile
            label="Avg Draft Retention"
            value={overview.data ? fmtRetention(overview.data.avg_retention_pct) : "…"}
            accent="var(--domain-efficiency)"
          />
        </AIHoverCard>
        <AIHoverCard
          feature="efficiency_metric"
          entityLabel="Sampled exams"
          metricLabel="% of drafts rated Highly Useful"
          value={overview.data ? fmtPct((highlyUsefulPct ?? 0) / 100) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="% Highly Useful" value={overview.data ? fmtPct((highlyUsefulPct ?? 0) / 100) : "…"} accent="var(--status-good)" />
        </AIHoverCard>
        <AIHoverCard
          feature="efficiency_metric"
          entityLabel="Sampled exams"
          metricLabel="% of drafts rated Not Useful"
          value={overview.data ? fmtPct((notUsefulPct ?? 0) / 100) : "…"}
          underline={false}
          style={{ flex: "1 1 200px", minWidth: 180 }}
        >
          <StatTile label="% Not Useful" value={overview.data ? fmtPct((notUsefulPct ?? 0) / 100) : "…"} accent="var(--status-critical)" />
        </AIHoverCard>
      </div>

      <CategoryBarCard title="Overall Assessment Distribution" categories={assessmentBars} colorFor={(c) => ASSESSMENT_COLORS[c]} />

      {categories.data && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {categories.data.map((group) => (
            <CategoryBarCard key={group.dimension} title={categoryTitles[group.dimension] ?? group.dimension} categories={group.categories} />
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ ...CARD_STYLE, flex: "1 1 400px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            By Modality
          </div>
          {byModality.data && <DataTable columns={MODALITY_COLUMNS} rows={byModality.data} rowKey={(r) => r.modality ?? "unknown"} />}
        </div>
        <div style={{ ...CARD_STYLE, flex: "1 1 400px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            By Practice
          </div>
          {byPractice.data && <DataTable columns={PRACTICE_COLUMNS} rows={byPractice.data} rowKey={(r) => r.practice ?? "unknown"} />}
        </div>
      </div>

      <div style={CARD_STYLE}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>Sample Assessments</div>
          <select
            value={assessmentFilter}
            onChange={(e) => setAssessmentFilter(e.target.value)}
            style={{
              fontSize: 13,
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface-raised)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">All Assessments</option>
            {ASSESSMENT_ORDER.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div style={{ maxHeight: 480, overflowY: "auto", overflowX: "auto" }}>
          {samples.data && <DataTable columns={SAMPLE_COLUMNS} rows={samples.data} rowKey={(r) => r.accession_number} />}
        </div>
      </div>
    </div>
  );
}
