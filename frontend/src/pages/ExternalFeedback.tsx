import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { StatTile } from "../components/StatTile";
import { Badge } from "../components/Badge";
import { DataTable } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";
import type { ExternalFeedbackItem, FeedbackSentiment } from "../api/types";

// Positive/neutral/negative mapped onto the app's 3 usable status colors - same reasoning as
// a promoter/passive/detractor NPS breakdown (the Rad Sentiment page this is a live counterpart
// to), just generalized to free-text feedback rather than a fixed 0-10 survey score.
const SENTIMENT_COLOR: Record<FeedbackSentiment, string> = {
  positive: "var(--status-good)",
  neutral: "var(--status-warning)",
  negative: "var(--status-critical)",
};

function SentimentBadge({ sentiment }: { sentiment: FeedbackSentiment }) {
  return <Badge label={sentiment} color={SENTIMENT_COLOR[sentiment]} dot />;
}

function CategoryTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>{label}</div>
      <div style={{ color: "var(--text-secondary)" }}>{payload[0].value} items</div>
    </div>
  );
}

const FEEDBACK_COLUMNS: DataTableColumn<ExternalFeedbackItem>[] = [
  { key: "submitted_at", label: "Submitted", render: (r) => new Date(r.submitted_at).toLocaleString() },
  { key: "practice", label: "Practice", render: (r) => r.practice ?? "—" },
  { key: "radiologist_name", label: "Radiologist", render: (r) => r.radiologist_name ?? "—" },
  { key: "sentiment", label: "Sentiment", render: (r) => <SentimentBadge sentiment={r.sentiment} /> },
  { key: "category", label: "Category", render: (r) => r.category ?? "—" },
  { key: "comment", label: "Comment", render: (r) => r.comment ?? "—" },
];

export function ExternalFeedback() {
  const feedback = useFetch(() => mosaicApi.getExternalFeedback(), []);

  const bySentiment = useMemo(() => {
    const counts: Record<FeedbackSentiment, number> = { positive: 0, neutral: 0, negative: 0 };
    for (const item of feedback.data ?? []) counts[item.sentiment] = (counts[item.sentiment] ?? 0) + 1;
    return counts;
  }, [feedback.data]);

  const byCategory = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of feedback.data ?? []) {
      const key = item.category ?? "Uncategorized";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count);
  }, [feedback.data]);

  const sorted = useMemo(
    () => [...(feedback.data ?? [])].sort((a, b) => b.submitted_at.localeCompare(a.submitted_at)),
    [feedback.data]
  );

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>External Feedback</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13, maxWidth: 680 }}>
          Live feedback pushed in through the ingestion endpoint - a speculative mirror of
          practice-command-dev's apparent push-based architecture (see /api/mosaic/ingest). This
          is a <em>live</em> counterpart to the static Rad Sentiment survey on the Today tab, not
          a replacement for it.
        </div>
      </div>

      {feedback.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({feedback.error})
        </div>
      )}

      {feedback.data && feedback.data.length === 0 && (
        <div style={{ ...CARD_STYLE, color: "var(--text-muted)", fontSize: 13 }}>
          No feedback has been ingested yet - this fills in once something pushes data through
          POST /api/mosaic/ingest/external_feedback_demo.
        </div>
      )}

      {feedback.data && feedback.data.length > 0 && (
        <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <StatTile label="Positive" value={String(bySentiment.positive)} accent={SENTIMENT_COLOR.positive} />
            <StatTile label="Neutral" value={String(bySentiment.neutral)} accent={SENTIMENT_COLOR.neutral} />
            <StatTile label="Negative" value={String(bySentiment.negative)} accent={SENTIMENT_COLOR.negative} />
          </div>

          <div style={CARD_STYLE}>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              By Category
            </div>
            <ResponsiveContainer width="100%" height={Math.max(160, byCategory.length * 32)}>
              <BarChart data={byCategory} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
                <CartesianGrid stroke="var(--gridline)" strokeDasharray="0" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--gridline)" }} tickLine={false} />
                <YAxis type="category" dataKey="category" width={140} tick={{ fill: "var(--text-secondary)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CategoryTooltip />} cursor={{ fill: "var(--surface-raised)" }} />
                <Bar dataKey="count" fill="var(--color-primary)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={CARD_STYLE}>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Recent Feedback
            </div>
            <DataTable columns={FEEDBACK_COLUMNS} rows={sorted} rowKey={(r) => `${r.submitted_at}-${r.practice}-${r.radiologist_name}`} />
          </div>
        </>
      )}
    </div>
  );
}
