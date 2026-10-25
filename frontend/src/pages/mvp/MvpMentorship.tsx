import { useMemo, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { Badge } from "../../components/Badge";
import { AIHoverCard } from "../../components/AIHoverCard";
import { DonutChart } from "../../components/DonutChart";
import { Drawer } from "../../components/Drawer";
import { useFilters, matchesRadiologistSearch } from "../../context/FilterContext";
import { CARD_STYLE } from "../../styles/glassCard";
import type { MvpRadiologistItem } from "../../api/types";

const MENTOR_MATCH_COLORS: Record<string, string> = {
  "Sourcing Mentor": "var(--status-warning)",
  "Mentor Proposal Sent": "var(--status-warning)",
  "Mentorship Introduction Sent": "var(--domain-deployment)",
  "Mentorship Scheduled": "var(--domain-deployment)",
  "Post-Mentorship Monitoring": "var(--status-good)",
  Closed: "var(--text-muted)",
};

export function MvpMentorship() {
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);
  const [notesTarget, setNotesTarget] = useState<MvpRadiologistItem | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const filters = useFilters();

  const matched = useMemo(() => (radiologists.data ?? []).filter((r) => r.mentor_match), [radiologists.data]);

  const visibleRows = useMemo(
    () =>
      matched.filter(
        (r) =>
          (!statusFilter || r.mentor_match!.matching_status === statusFilter) &&
          matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
      ),
    [matched, statusFilter, filters]
  );

  const donutData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of matched) {
      const status = r.mentor_match!.matching_status;
      counts[status] = (counts[status] ?? 0) + 1;
    }
    return Object.entries(counts).map(([status, value]) => ({
      key: status,
      label: status,
      value,
      color: MENTOR_MATCH_COLORS[status] ?? "var(--text-secondary)",
    }));
  }, [matched]);

  const columns: DataTableColumn<MvpRadiologistItem>[] = [
    { key: "radiologist_name", label: "Radiologist" },
    { key: "practice", label: "Practice" },
    {
      key: "matching_status",
      label: "Status",
      render: (r) => (
        <AIHoverCard feature="mvp_mentor_match" entityLabel={r.radiologist_name ?? `NPI ${r.npi}`} metricLabel="Peer-coach matching status" value={r.mentor_match!.matching_status}>
          <Badge label={r.mentor_match!.matching_status} color={MENTOR_MATCH_COLORS[r.mentor_match!.matching_status] ?? "var(--text-secondary)"} />
        </AIHoverCard>
      ),
    },
    { key: "mentors_identified", label: "Candidate Mentor(s)", render: (r) => r.mentor_match!.mentors_identified ?? "—" },
    {
      key: "notes",
      label: "Notes",
      render: (r) => (
        <button
          onClick={() => setNotesTarget(r)}
          style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 13, padding: "2px 4px" }}
        >
          📝 View
        </button>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16 }}>Mosaic Mentorship Program Status</h2>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Real peer-coach matching pipeline, from the team's own Peer Coach List workbook - a point-in-time snapshot, not a live feed.
        </div>
      </div>

      {radiologists.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({radiologists.error})</div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Mentor Matching Status (click a slice to filter the table)
          </div>
          <DonutChart data={donutData} onSliceClick={(status) => setStatusFilter((cur) => (cur === status ? null : status))} />
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 8, fontStyle: "italic" }}>
            A "Mentorship Offered" pre-stage (rads offered mentorship, not yet responded) isn't currently tracked separately
            from this data source - known gap, not fabricated.
          </div>
        </div>
        <div style={CARD_STYLE}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
            <input
              value={filters.radiologistSearch}
              onChange={(e) => filters.setRadiologistSearch(e.target.value)}
              placeholder="Search radiologist (name or NPI)"
              style={{
                fontSize: 13,
                padding: "6px 14px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: "var(--surface-raised)",
                color: "var(--text-primary)",
                minWidth: 220,
              }}
            />
            {statusFilter && (
              <button
                onClick={() => setStatusFilter(null)}
                style={{
                  fontSize: 12,
                  padding: "6px 14px",
                  borderRadius: 999,
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                }}
              >
                Clear status filter ({statusFilter})
              </button>
            )}
          </div>
          {visibleRows.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No radiologists match the current filters.</div>
          ) : (
            <DataTable columns={columns} rows={visibleRows} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>

      <Drawer
        open={notesTarget !== null}
        onClose={() => setNotesTarget(null)}
        title={notesTarget ? `Mentor matching — ${notesTarget.radiologist_name ?? `NPI ${notesTarget.npi}`}` : undefined}
      >
        {notesTarget?.mentor_match && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Badge
              label={notesTarget.mentor_match.matching_status}
              color={MENTOR_MATCH_COLORS[notesTarget.mentor_match.matching_status] ?? "var(--text-secondary)"}
            />
            {notesTarget.mentor_match.mentors_identified && (
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                <strong style={{ color: "var(--text-primary)" }}>Candidate mentor(s):</strong>{" "}
                <span style={{ whiteSpace: "pre-wrap" }}>{notesTarget.mentor_match.mentors_identified}</span>
              </div>
            )}
            {notesTarget.mentor_match.matching_notes && (
              <div style={{ fontSize: 13, whiteSpace: "pre-wrap", color: "var(--text-primary)", lineHeight: 1.5 }}>
                {notesTarget.mentor_match.matching_notes}
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
