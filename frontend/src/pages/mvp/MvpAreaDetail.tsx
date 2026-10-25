import { useMemo, useState } from "react";
import { mosaicApi } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { Badge } from "../../components/Badge";
import { AIHoverCard } from "../../components/AIHoverCard";
import { Drawer } from "../../components/Drawer";
import { EfficiencyTrendChart } from "../../components/EfficiencyTrendChart";
import { useFilters, matchesRadiologistSearch } from "../../context/FilterContext";
import { CARD_STYLE } from "../../styles/glassCard";
import { LOCAL_REGIONS, getLocalRegion } from "../../utils/localRegion";
import { getEffLossPrograms, getImpactStatus, getOutreachEscalationRows, getRadsDecliningSupportRows } from "../../utils/mvpDashboardStats";
import type { MvpRadiologistItem } from "../../api/types";

const IMPACT_COLORS: Record<string, string> = {
  "At/Above Baseline": "var(--status-good)",
  "Improving Towards Baseline": "var(--domain-deployment)",
  "Not Improving": "var(--status-critical)",
};

interface ImpactRow {
  npi: number;
  radiologist_name: string | null;
  practice: string | null;
  status: string;
  bl_pct: number | null;
  post_pct: number | null;
}

function fmtPctRaw(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function fmtNum(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

export function MvpAreaDetail() {
  const [team, setTeam] = useState<string>(LOCAL_REGIONS[1]); // default "Apex"
  const [detailTarget, setDetailTarget] = useState<MvpRadiologistItem | null>(null);
  const radiologists = useFetch(() => mosaicApi.getMvpRadiologists(), []);
  const areaTrend = useFetch(() => mosaicApi.getMvpAreaDetail(), []);
  const filters = useFilters();

  const teamRows = useMemo(() => {
    const inTeam = (radiologists.data ?? []).filter((r) => getLocalRegion(r.practice) === team);
    return inTeam.filter((r) => matchesRadiologistSearch(filters, r.radiologist_name, r.npi));
  }, [radiologists.data, team, filters]);

  function openDetail(npi: number) {
    const full = teamRows.find((r) => r.npi === npi);
    if (full) setDetailTarget(full);
  }

  const impactRows: ImpactRow[] = useMemo(() => {
    const rows: ImpactRow[] = [];
    for (const r of teamRows) {
      const status = getImpactStatus(r);
      if (!status) continue;
      rows.push({
        npi: r.npi,
        radiologist_name: r.radiologist_name,
        practice: r.practice,
        status,
        bl_pct: r.drafting_captured_efficiency_change_pct,
        // efficiency_change_last_30d_pct is confirmed 100% NULL for this population -
        // full_mosaic_change_l30d_pct is the rolling figure that's actually populated.
        post_pct: r.full_mosaic_change_l30d_pct,
      });
    }
    return rows;
  }, [teamRows]);

  const outreachEscalations = useMemo(() => getOutreachEscalationRows(teamRows), [teamRows]);
  const decliningSupport = useMemo(() => getRadsDecliningSupportRows(teamRows), [teamRows]);

  const impactColumns: DataTableColumn<ImpactRow>[] = [
    { key: "practice", label: "Practice" },
    { key: "radiologist_name", label: "Radiologist" },
    {
      key: "status",
      label: "Impact Status",
      render: (r) => (
        <AIHoverCard feature="mvp_impact" entityLabel={r.radiologist_name ?? `NPI ${r.npi}`} metricLabel="Impact status" value={r.status}>
          <Badge label={r.status} color={IMPACT_COLORS[r.status] ?? "var(--text-secondary)"} />
        </AIHoverCard>
      ),
    },
    {
      key: "bl_pct",
      label: "BL D&C Eff Change",
      render: (r) => (
        <AIHoverCard feature="mvp_efficiency_change" entityLabel={r.radiologist_name ?? `NPI ${r.npi}`} metricLabel="Baseline D&C efficiency change" value={fmtPctRaw(r.bl_pct)}>
          {fmtPctRaw(r.bl_pct)}
        </AIHoverCard>
      ),
    },
    {
      key: "post_pct",
      label: "Post Engagement D&C Eff Change",
      render: (r) => (
        <AIHoverCard
          feature="mvp_efficiency_change"
          entityLabel={r.radiologist_name ?? `NPI ${r.npi}`}
          metricLabel="Post-engagement D&C efficiency change"
          value={fmtPctRaw(r.post_pct)}
        >
          {fmtPctRaw(r.post_pct)}
        </AIHoverCard>
      ),
    },
  ];

  const escalationColumns: DataTableColumn<MvpRadiologistItem>[] = [
    { key: "practice", label: "Practice" },
    { key: "radiologist_name", label: "Radiologist" },
    { key: "eff_loss_programs", label: "Eff. Loss Programs", render: (r) => getEffLossPrograms(r) },
    { key: "drafting_captured_efficiency_change_pct", label: "% Eff Loss D&C L30Days", render: (r) => fmtPctRaw(r.drafting_captured_efficiency_change_pct) },
    {
      key: "optimization_last_updated",
      label: "Latest Update (approx.)",
      render: (r) => (r.optimization_last_updated ? new Date(r.optimization_last_updated).toLocaleDateString() : "—"),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 16 }}>Area Detail: {team} MVP Dashboard</h2>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Drafting/Capture, scoped to the {team} Local team.</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
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
              minWidth: 200,
            }}
          />
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            style={{
              background: "var(--surface-raised)",
              border: "var(--glass-border)",
              borderRadius: "var(--radius)",
              color: "var(--text-primary)",
              padding: "6px 10px",
              fontSize: 13,
            }}
          >
            {LOCAL_REGIONS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(radiologists.error || areaTrend.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({radiologists.error ?? areaTrend.error})
        </div>
      )}

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Efficiency Change, Time Series
        </div>
        {areaTrend.data?.[team] && <EfficiencyTrendChart trend={areaTrend.data[team]} mode="change" showDraftingOnly />}
      </div>

      <div style={CARD_STYLE}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Impact Status ({impactRows.length})
        </div>
        {impactRows.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No post-engagement radiologists in this area yet.</div>
        ) : (
          <DataTable columns={impactColumns} rows={impactRows} rowKey={(r) => r.npi} onRowClick={(r) => openDetail(r.npi)} />
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Outreach Escalations ({outreachEscalations.length})
          </div>
          {outreachEscalations.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>None in this area.</div>
          ) : (
            <DataTable columns={escalationColumns} rows={outreachEscalations} rowKey={(r) => r.npi} onRowClick={(r) => openDetail(r.npi)} />
          )}
        </div>
        <div style={CARD_STYLE}>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
            Rads Declining Support ({decliningSupport.length})
          </div>
          {decliningSupport.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>None in this area.</div>
          ) : (
            <DataTable columns={escalationColumns} rows={decliningSupport} rowKey={(r) => r.npi} onRowClick={(r) => openDetail(r.npi)} />
          )}
        </div>
      </div>

      <Drawer
        open={detailTarget !== null}
        onClose={() => setDetailTarget(null)}
        title={detailTarget ? detailTarget.radiologist_name ?? `NPI ${detailTarget.npi}` : undefined}
      >
        {detailTarget && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{detailTarget.practice ?? "—"}</div>
            {detailTarget.mvp_cohort && <Badge label={detailTarget.mvp_cohort} color="var(--text-secondary)" />}
            {detailTarget.exclusion_reason && <Badge label={detailTarget.exclusion_reason} color="var(--text-muted)" />}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 13 }}>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Baseline Capacity (TBWU/9h)</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtNum(detailTarget.baseline_capacity_tbwu_9h)}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Full Mosaic Eff. Δ</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtPctRaw(detailTarget.full_mosaic_efficiency_change_pct)}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>XR Drafting Δ</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtPctRaw(detailTarget.xr_drafting_efficiency_change_pct)}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>CT Head Δ</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtPctRaw(detailTarget.ct_head_efficiency_change_pct)}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>US Capture Δ</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtPctRaw(detailTarget.us_capture_efficiency_change_pct)}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Eff. Δ (Last 30d)</div>
                <div style={{ color: "var(--text-primary)" }}>{fmtPctRaw(detailTarget.full_mosaic_change_l30d_pct)}</div>
              </div>
            </div>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Support Status</div>
              <div style={{ color: "var(--text-primary)", fontSize: 13 }}>{detailTarget.optimization_support_status ?? "—"}</div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
