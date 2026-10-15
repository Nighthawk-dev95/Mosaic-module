import { mosaicApi } from "../api/client";
import type { ReconciliationFinding } from "../api/types";
import { useFetch } from "../hooks/useFetch";
import { Badge } from "../components/Badge";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { StatTile } from "../components/StatTile";
import { TABLE_SCROLL_STYLE, TABLE_SECTION_STYLE } from "../styles/tableLayout";

// Read-only "where the counts disagree" feed - the pattern (not the data source) of PCC's
// native Mosaic Intelligence Reconciliation tab, confirmed via its own compiled bundle: PCC
// reconciles its computed numbers against a different team's published figures. We have no
// equivalent external feed, so this surfaces 3 concrete, already-diagnosed divergences from
// this app's own prior investigations instead - see reconciliation_service.py for each
// check's full rationale. No accept/reject workflow here (unlike Baseline Review Queue) -
// there's nothing on our side for a user to resolve by clicking; this is pure surfacing.

const CHECK_LABEL: Record<string, string> = {
  mosaic_flag_mismatch: "Mosaic Flag Mismatch",
  seal_team_mislabeling: "SEAL Mislabeling",
  seal_baseline_drift: "SEAL Baseline Drift",
};

const CHECK_COLOR: Record<string, string> = {
  mosaic_flag_mismatch: "var(--status-warning)",
  seal_team_mislabeling: "var(--status-critical)",
  seal_baseline_drift: "var(--color-primary)",
};

function summarize(findings: ReconciliationFinding[]) {
  const counts: Record<string, number> = {
    mosaic_flag_mismatch: 0,
    seal_team_mislabeling: 0,
    seal_baseline_drift: 0,
  };
  for (const f of findings) counts[f.check] = (counts[f.check] ?? 0) + 1;
  return counts;
}

const COLUMNS: DataTableColumn<ReconciliationFinding>[] = [
  {
    key: "check",
    label: "Check",
    render: (f) => <Badge label={CHECK_LABEL[f.check] ?? f.check} color={CHECK_COLOR[f.check] ?? "var(--text-secondary)"} dot />,
  },
  { key: "scope", label: "Scope" },
  { key: "entity", label: "Entity" },
  { key: "expected", label: "Expected" },
  { key: "actual", label: "Actual" },
  { key: "magnitude", label: "Magnitude", render: (f) => f.magnitude.toLocaleString() },
];

export function Reconciliation() {
  const findingsFetch = useFetch(() => mosaicApi.getReconciliationFindings(), []);
  const findings = findingsFetch.data ?? [];
  const counts = summarize(findings);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        Where the counts disagree - divergences between this app's own numbers and a second,
        independently-computed source for the same facts. Biggest divergence first, across all
        checks combined.
      </div>

      {findingsFetch.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({findingsFetch.error})
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {Object.entries(CHECK_LABEL).map(([check, label]) => (
          <StatTile
            key={check}
            label={label}
            value={String(counts[check] ?? 0)}
            accent={(counts[check] ?? 0) > 0 ? CHECK_COLOR[check] : "var(--status-good)"}
          />
        ))}
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ fontWeight: "var(--font-weight-semibold)", marginBottom: 12 }}>
          All findings ({findings.length})
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {findingsFetch.loading ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading...</div>
          ) : findings.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
              No divergences found - either everything reconciles cleanly, or the SEAL checks
              are still waiting on their data migration (see tools/edw_fixes/011_...).
            </div>
          ) : (
            <DataTable columns={COLUMNS} rows={findings} rowKey={(f) => `${f.check}-${f.entity}`} />
          )}
        </div>
      </div>
    </div>
  );
}
