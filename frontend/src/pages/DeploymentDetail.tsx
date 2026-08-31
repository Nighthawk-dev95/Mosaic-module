import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { DeploymentFunnelChart } from "../components/DeploymentFunnelChart";
import { BlockerStackedChart } from "../components/BlockerStackedChart";
import type { DeploymentPracticeRollup, DeploymentRadiologistItem } from "../api/types";

const PRACTICE_COLUMNS: DataTableColumn<DeploymentPracticeRollup>[] = [
  { key: "practice", label: "Practice" },
  { key: "total_rads", label: "Total Rads" },
  { key: "xr_ct_head_enabled_rads", label: "XR / CT Head Enabled" },
  { key: "ct_abdpel_enabled_rads", label: "CT Abd/Pel Enabled" },
  { key: "ct_chest_cases_last_14d", label: "CT Chest Enabled", render: () => "Pending data" },
  { key: "ct_head_cases_last_14d", label: "CT Head Cases (14d)" },
  { key: "xr_cases_last_14d", label: "XR Cases (14d)" },
  { key: "ct_abdpel_cases_last_14d", label: "CT Abd/Pel Cases (14d)" },
];

const RAD_COLUMNS: DataTableColumn<DeploymentRadiologistItem>[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "home_practice", label: "Practice" },
  { key: "working_subspecialty", label: "Subspecialty" },
  { key: "xr_ct_head_status", label: "XR / CT Head Status" },
  { key: "ct_abdpel_status", label: "CT Abd/Pel Status" },
  { key: "ct_chest_status", label: "CT Chest Status", render: () => "Pending data" },
  { key: "ct_head_drafts_last_14d", label: "CT Head (14d)" },
  { key: "xr_drafts_last_14d", label: "XR (14d)" },
  { key: "ct_abdpel_drafts_last_14d", label: "CT Abd/Pel (14d)" },
];

export function DeploymentDetail() {
  const byPractice = useFetch(() => mosaicApi.getDeploymentByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getDeploymentByRadiologist(), []);
  const funnelReporting = useFetch(() => mosaicApi.getDeploymentFunnelReporting(), []);
  const funnelDrafting = useFetch(() => mosaicApi.getDeploymentFunnelDrafting(), []);
  const blockersDrafting = useFetch(() => mosaicApi.getDeploymentBlockersDrafting(), []);
  const anyError =
    byPractice.error || byRadiologist.error || funnelReporting.error || funnelDrafting.error || blockersDrafting.error;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>Deployment</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          CT Head / XR drafting enablement, CT Abd/Pel drafting enablement, and cases read in the last 14 days.
          CT Chest is pending upstream data (rad_onboarding fields not yet added). "Do Not Launch" rads are
          excluded from every visual on this page.
        </div>
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. Is it running at http://127.0.0.1:8000? ({anyError})
        </div>
      )}

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 420px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Reporting Deployment Waterfall
          </div>
          {funnelReporting.data && <DeploymentFunnelChart stages={funnelReporting.data.stages} />}
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 420px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Drafting Deployment Waterfall (XR / CT Head)
          </div>
          {funnelDrafting.data && <DeploymentFunnelChart stages={funnelDrafting.data.stages} />}
        </div>
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Drafting: Rads Blocked by Practice
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
          Eligible-but-not-yet-live rads only, stacked by blocker reason.
        </div>
        {blockersDrafting.data && <BlockerStackedChart data={blockersDrafting.data} />}
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, overflowX: "auto" }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Practice
        </div>
        {byPractice.data && (
          <DataTable columns={PRACTICE_COLUMNS} rows={byPractice.data} rowKey={(r) => r.practice ?? "unknown"} />
        )}
      </div>

      <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, overflowX: "auto" }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        {byRadiologist.data && (
          <DataTable columns={RAD_COLUMNS} rows={byRadiologist.data} rowKey={(r) => r.npi} />
        )}
      </div>
    </div>
  );
}
