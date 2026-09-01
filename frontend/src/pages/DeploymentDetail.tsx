import type { CSSProperties } from "react";
import { useMemo } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DataTable } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { DeploymentFunnelChart } from "../components/DeploymentFunnelChart";
import { BlockerStackedChart } from "../components/BlockerStackedChart";
import { FilterBar } from "../components/FilterBar";
import { useFilters, matchesPractice, matchesRadiologistSearch } from "../context/FilterContext";
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

const TABLE_SECTION_STYLE: CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
};

const TABLE_SCROLL_STYLE: CSSProperties = {
  maxHeight: 480,
  overflow: "auto",
};

export function DeploymentDetail() {
  const byPractice = useFetch(() => mosaicApi.getDeploymentByPractice(), []);
  const byRadiologist = useFetch(() => mosaicApi.getDeploymentByRadiologist(), []);
  const funnelReporting = useFetch(() => mosaicApi.getDeploymentFunnelReporting(), []);
  const funnelDrafting = useFetch(() => mosaicApi.getDeploymentFunnelDrafting(), []);
  const funnelCtAbdpel = useFetch(() => mosaicApi.getDeploymentFunnelCtAbdpel(), []);
  const blockersDrafting = useFetch(() => mosaicApi.getDeploymentBlockersDrafting(), []);
  const blockersCtAbdpel = useFetch(() => mosaicApi.getDeploymentBlockersCtAbdpel(), []);
  const anyError =
    byPractice.error ||
    byRadiologist.error ||
    funnelReporting.error ||
    funnelDrafting.error ||
    funnelCtAbdpel.error ||
    blockersDrafting.error ||
    blockersCtAbdpel.error;

  const filters = useFilters();
  const practices = useMemo(() => {
    if (!byPractice.data) return [];
    return Array.from(new Set(byPractice.data.map((r) => r.practice).filter(Boolean) as string[])).sort();
  }, [byPractice.data]);

  const filteredByPractice = useMemo(
    () => (byPractice.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [byPractice.data, filters]
  );
  const filteredByRadiologist = useMemo(
    () =>
      (byRadiologist.data ?? []).filter(
        (r) => matchesPractice(filters, r.home_practice) && matchesRadiologistSearch(filters, r.radiologist_name, r.npi)
      ),
    [byRadiologist.data, filters]
  );
  const filteredBlockersDrafting = useMemo(
    () => (blockersDrafting.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [blockersDrafting.data, filters]
  );
  const filteredBlockersCtAbdpel = useMemo(
    () => (blockersCtAbdpel.data ?? []).filter((r) => matchesPractice(filters, r.practice)),
    [blockersCtAbdpel.data, filters]
  );

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

      <FilterBar practices={practices} />
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: -12 }}>
        Practice/Radiologist filters narrow the tables and blocker charts below. The waterfalls are company-wide
        totals and aren't broken down by practice.
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 380px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Reporting Deployment Waterfall
          </div>
          {funnelReporting.data && <DeploymentFunnelChart stages={funnelReporting.data.stages} />}
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 380px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Drafting Deployment Waterfall (XR / CT Head)
          </div>
          {funnelDrafting.data && <DeploymentFunnelChart stages={funnelDrafting.data.stages} />}
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 380px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            CT Abd/Pel Deployment Waterfall
          </div>
          {funnelCtAbdpel.data && <DeploymentFunnelChart stages={funnelCtAbdpel.data.stages} />}
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 480px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Drafting: Rads Blocked by Practice
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
            Eligible-but-not-yet-live rads only, stacked by blocker reason.
          </div>
          {blockersDrafting.data && <BlockerStackedChart data={filteredBlockersDrafting} />}
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, flex: "1 1 480px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            CT Abd/Pel: Rads Blocked by Practice
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 12 }}>
            Eligible-but-not-yet-enabled rads only, stacked by blocker reason.
          </div>
          {blockersCtAbdpel.data && <BlockerStackedChart data={filteredBlockersCtAbdpel} />}
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Practice
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byPractice.data && (
            <DataTable columns={PRACTICE_COLUMNS} rows={filteredByPractice} rowKey={(r) => r.practice ?? "unknown"} />
          )}
        </div>
      </div>

      <div style={TABLE_SECTION_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
          By Radiologist
        </div>
        <div style={TABLE_SCROLL_STYLE}>
          {byRadiologist.data && (
            <DataTable columns={RAD_COLUMNS} rows={filteredByRadiologist} rowKey={(r) => r.npi} />
          )}
        </div>
      </div>
    </div>
  );
}
