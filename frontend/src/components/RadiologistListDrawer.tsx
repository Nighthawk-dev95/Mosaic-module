import { DataTable } from "./DataTable";
import type { DataTableColumn } from "./DataTable";
import { Badge } from "./Badge";
import { Drawer } from "./Drawer";
import type { MvpRadiologistItem } from "../api/types";

interface Props {
  open: boolean;
  onClose: () => void;
  title?: string;
  rows: MvpRadiologistItem[];
  // Short context line under the title - e.g. "Current roster, not frozen to this snapshot's
  // date" for Weekly Report's latest-week drill-down, where the caveat matters.
  caption?: string;
}

function fmtPctRaw(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

const COLUMNS: DataTableColumn<MvpRadiologistItem>[] = [
  { key: "radiologist_name", label: "Radiologist", render: (r) => r.radiologist_name ?? `NPI ${r.npi}` },
  { key: "practice", label: "Practice", render: (r) => r.practice ?? "—" },
  {
    key: "mvp_cohort",
    label: "Cohort / Exclusion",
    render: (r) =>
      r.exclusion_reason ? (
        <Badge label={r.exclusion_reason} color="var(--text-muted)" />
      ) : r.mvp_cohort ? (
        <Badge label={r.mvp_cohort} color="var(--text-secondary)" />
      ) : (
        "—"
      ),
  },
  { key: "optimization_support_status", label: "Support Status", render: (r) => r.optimization_support_status ?? "—" },
  // Why a radiologist landed in a given impact bucket is literally the comparison of these two
  // figures (post >= baseline -> At/Above Baseline, post > baseline but still negative ->
  // Improving, etc. - see mvp_dashboard_stats.py's compute_impact_breakdown) - showing both
  // numbers directly in the drill-down list, not just the bucket name, answers "why" on sight.
  {
    key: "drafting_captured_efficiency_change_pct",
    label: "Baseline D&C Eff. Δ",
    render: (r) => fmtPctRaw(r.drafting_captured_efficiency_change_pct),
  },
  {
    key: "full_mosaic_change_l30d_pct",
    label: "Post-Engagement Eff. Δ (L30D)",
    render: (r) => fmtPctRaw(r.full_mosaic_change_l30d_pct),
  },
];

// Shared drill-down target for every MVP funnel-segment/impact-bucket/escalation-owner click
// (Overview, Mammo, Weekly Report's latest week) - a compact radiologist list in a Drawer,
// rather than hand-building the same small table at each of those call sites.
export function RadiologistListDrawer({ open, onClose, title, rows, caption }: Props) {
  return (
    <Drawer open={open} onClose={onClose} title={title}>
      {caption && <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12, fontStyle: "italic" }}>{caption}</div>}
      {rows.length === 0 ? (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No radiologists match.</div>
      ) : (
        <DataTable columns={COLUMNS} rows={rows} rowKey={(r) => r.npi} />
      )}
    </Drawer>
  );
}
