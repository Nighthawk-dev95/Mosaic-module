import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  Position,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { useCountUp } from "../hooks/useCountUp";
import { useTheme } from "../context/ThemeContext";
import { AIHoverCard } from "../components/AIHoverCard";
import { Drawer } from "../components/Drawer";
import { StatTile } from "../components/StatTile";
import { RingGauge } from "../components/RingGauge";
import { DataTable, fmtPct } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";
import type { EfficiencyMode, EfficiencyPracticeRollup, CapturePracticeRollup } from "../api/types";

// Replaces the rejected 3D "Mosaic Core" prototype - same ambitions (live/animated, AI hover
// context, click-to-drill-down) rebuilt on this app's own already-proven 2D motion primitives
// (RingGauge's sweep-in, ReviewActivityTicker's mount-triggered slide-in, plain AIHoverCard/
// Drawer) instead of inventing a new 3D interaction model from scratch.

type CapabilityKey = "reporting" | "drafting" | "capture";

interface CapabilityConfig {
  key: CapabilityKey;
  label: string;
  adoptionPct: number | null;
  radsLive: number;
  efficiencyChangePct: number | null;
}

const CAPABILITY_LABELS: Record<CapabilityKey, string> = {
  reporting: "Reporting",
  drafting: "Drafting",
  capture: "Capture",
};

// pct_rpce_reporting/pct_rpce_drafting/pct_captured_enabled/pct_change_vs_baseline are all
// fractions (0-1) at the API layer - confirmed by DataTable.tsx's own fmtPct (x100). Converting
// once here means every downstream computation (gauges, colors, the flow strip) works in plain
// percent numbers, matching the bug class that undermined the 3D prototype's own color/speed math.
function toPct(fraction: number | null): number | null {
  return fraction === null ? null : fraction * 100;
}

function statusColor(pct: number | null): string {
  if (pct === null) return "var(--text-muted)";
  if (pct > 0) return "var(--status-good)";
  if (pct > -5) return "var(--status-warning)";
  return "var(--status-critical)";
}

function fmtSignedPct(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

interface DetailRow {
  practice: string | null;
  primaryValue: string;
}

/**
 * The drill-down list under a capability ring. Two different endpoints feed it, and - this is
 * the part worth knowing - they are grouped by two *different* columns:
 *
 *   Capture              -> `provider_local_practice_name_curr` = the rad's home practice = Team
 *   Reporting / Drafting -> `managing_local_practice_name_curr` = the site read at  = Practice
 *
 * (`get_capture_by_practice` groups on the provider column; the Efficiency matrix carries the
 * "Fix 2" split and exposes the managing column as `Practice`.) One rad has one Team and reads
 * at as many as seventy Practices, so labelling both lists "Practice" put the wrong word on the
 * capture rows - and the same practice name legitimately appears in both lists with different
 * numbers. The heading follows the data instead of asserting one answer for both.
 */
function entityLabelFor(selected: CapabilityKey | null): "Practice" | "Team" {
  return selected === "capture" ? "Team" : "Practice";
}

function useCapabilityDetail(selected: CapabilityKey | null) {
  const [rows, setRows] = useState<DetailRow[] | null>(null);
  const [sortLabel, setSortLabel] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected) {
      setRows(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setRows(null);

    if (selected === "capture") {
      setSortLabel("% captured (enabled), sorted by captured-exam volume");
      mosaicApi
        .getCaptureByPractice()
        .then((practices: CapturePracticeRollup[]) => {
          if (cancelled) return;
          const top = [...practices]
            .filter((p) => p.practice)
            .sort((a, b) => (b.captured_exams_all ?? 0) - (a.captured_exams_all ?? 0))
            .slice(0, 8)
            .map((p) => ({ practice: p.practice, primaryValue: fmtPct(p.pct_captured_enabled) }));
          setRows(top);
        })
        .finally(() => !cancelled && setLoading(false));
    } else {
      const mode: EfficiencyMode = selected;
      setSortLabel("Change vs baseline, sorted by largest magnitude of change");
      mosaicApi
        .getEfficiencyDetail(mode)
        .then((detail) => {
          if (cancelled) return;
          const top = [...detail.by_practice]
            .filter((p: EfficiencyPracticeRollup) => p.practice)
            .sort((a, b) => Math.abs(b.pct_change_vs_baseline ?? 0) - Math.abs(a.pct_change_vs_baseline ?? 0))
            .slice(0, 8)
            .map((p) => ({ practice: p.practice, primaryValue: fmtPct(p.pct_change_vs_baseline) }));
          setRows(top);
        })
        .finally(() => !cancelled && setLoading(false));
    }

    return () => {
      cancelled = true;
    };
  }, [selected]);

  return { rows, sortLabel, loading };
}

function CapabilityDrawerBody({ config, rows, sortLabel, loading, entityLabel }: {
  config: CapabilityConfig;
  rows: DetailRow[] | null;
  sortLabel: string;
  loading: boolean;
  /** Which column grouped these rows - see `entityLabelFor`. Not cosmetic. */
  entityLabel: "Practice" | "Team";
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <AIHoverCard
          feature="adoption_rollout"
          entityLabel={config.label}
          metricLabel="Adoption"
          value={config.adoptionPct !== null ? `${config.adoptionPct.toFixed(1)}%` : "—"}
          underline={false}
          style={{ flex: "1 1 140px", minWidth: 140 }}
        >
          <StatTile label="Adoption" value={config.adoptionPct !== null ? `${config.adoptionPct.toFixed(1)}%` : "—"} />
        </AIHoverCard>
        <AIHoverCard
          feature="efficiency_metric"
          entityLabel={config.label}
          metricLabel="Efficiency change vs baseline"
          value={fmtSignedPct(config.efficiencyChangePct)}
          underline={false}
          style={{ flex: "1 1 140px", minWidth: 140 }}
        >
          <StatTile label="Efficiency change" value={fmtSignedPct(config.efficiencyChangePct)} />
        </AIHoverCard>
      </div>
      <div>
        <div style={{ fontWeight: "var(--font-weight-semibold)", marginBottom: 4 }}>
          By {entityLabel.toLowerCase()}
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 8 }}>
          {sortLabel}
          {entityLabel === "Team"
            ? " · grouped by the radiologist's home practice (Team)"
            : " · grouped by the site the exam was read at (Practice)"}
        </div>
        {loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}
        {!loading && rows && rows.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            No {entityLabel.toLowerCase()}-level data available.
          </div>
        )}
        {!loading && rows && rows.length > 0 && (
          <DataTable
            columns={[
              { key: "practice", label: entityLabel },
              { key: "primaryValue", label: "Value", render: (r) => r.primaryValue },
            ]}
            rows={rows}
            rowKey={(r) => r.practice ?? "unknown"}
          />
        )}
      </div>
    </div>
  );
}

function CapabilityGauge({ config, onSelect }: { config: CapabilityConfig; onSelect: (key: CapabilityKey) => void }) {
  const animatedAdoption = useCountUp(config.adoptionPct, 900);

  return (
    <AIHoverCard
      feature="adoption_rollout"
      entityLabel={config.label}
      metricLabel="Adoption"
      value={config.adoptionPct !== null ? `${config.adoptionPct.toFixed(1)}%` : "—"}
      extra={{ efficiency_change: fmtSignedPct(config.efficiencyChangePct), rads_live: String(config.radsLive) }}
      underline={false}
      style={{ flex: "1 1 220px", minWidth: 200 }}
    >
      <div
        className="mosaic-card-hover"
        onClick={() => onSelect(config.key)}
        style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, cursor: "pointer" }}
      >
        <div style={{ fontSize: 13, fontWeight: "var(--font-weight-semibold)", color: "var(--text-primary)" }}>{config.label}</div>
        <RingGauge
          value={animatedAdoption === null ? null : Math.round(animatedAdoption * 10) / 10}
          max={100}
          size={110}
          strokeWidth={10}
          color={statusColor(config.efficiencyChangePct)}
          format={(v) => `${v.toFixed(0)}%`}
        />
        <div style={{ fontSize: 12, color: statusColor(config.efficiencyChangePct) }}>
          {fmtSignedPct(config.efficiencyChangePct)} vs baseline
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{config.radsLive.toLocaleString()} radiologists live</div>
      </div>
    </AIHoverCard>
  );
}

function FlowPipe({ thickness, color }: { thickness: number; color: string }) {
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", minWidth: 40 }}>
      <style>{`@keyframes mosaic-pulse-flow { to { background-position-x: -28px; } }`}</style>
      <div
        style={{
          width: "100%",
          height: thickness,
          borderRadius: 999,
          background: `repeating-linear-gradient(90deg, ${color} 0 10px, transparent 10px 20px)`,
          backgroundSize: "28px 100%",
          animation: "mosaic-pulse-flow 1s linear infinite",
          opacity: 0.8,
        }}
      />
    </div>
  );
}

function FlowStrip({ capabilities, onSelect }: { capabilities: CapabilityConfig[]; onSelect: (key: CapabilityKey) => void }) {
  const maxRads = Math.max(1, ...capabilities.map((c) => c.radsLive));

  return (
    <div style={{ ...CARD_STYLE, display: "flex", alignItems: "center", gap: 4 }}>
      {capabilities.map((config, i) => (
        <div key={config.key} style={{ display: "flex", alignItems: "center", flex: i === capabilities.length - 1 ? "0 0 auto" : 1 }}>
          <AIHoverCard
            feature="adoption_rollout"
            entityLabel={config.label}
            metricLabel="Radiologists live"
            value={config.radsLive.toLocaleString()}
            underline={false}
          >
            <div
              className="mosaic-card-hover"
              onClick={() => onSelect(config.key)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
                cursor: "pointer",
                padding: "4px 10px",
                borderRadius: "var(--radius)",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: statusColor(config.efficiencyChangePct),
                  boxShadow: `0 0 8px ${statusColor(config.efficiencyChangePct)}`,
                }}
              />
              <div style={{ fontSize: 12, fontWeight: "var(--font-weight-semibold)" }}>{config.label}</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{config.radsLive.toLocaleString()} live</div>
            </div>
          </AIHoverCard>
          {i < capabilities.length - 1 && (
            <FlowPipe
              thickness={Math.max(3, Math.min(14, (Math.min(config.radsLive, capabilities[i + 1].radsLive) / maxRads) * 14))}
              color={statusColor(capabilities[i + 1].efficiencyChangePct)}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function PulseFacts({ capabilities, practicesFullyOnRpce, totalRadsLive }: {
  capabilities: CapabilityConfig[];
  practicesFullyOnRpce: number | null;
  totalRadsLive: number | null;
}) {
  const facts = useMemo(() => {
    const list: string[] = [];
    const best = capabilities
      .filter((c) => c.efficiencyChangePct !== null && c.efficiencyChangePct > 0)
      .sort((a, b) => (b.efficiencyChangePct ?? 0) - (a.efficiencyChangePct ?? 0))[0];
    list.push(
      best
        ? `${best.label} is up ${fmtSignedPct(best.efficiencyChangePct)} vs baseline - the strongest gain this period.`
        : "No capability is currently trending above its baseline this period."
    );
    if (totalRadsLive !== null) {
      list.push(`${totalRadsLive.toLocaleString()} radiologists are live on Mosaic right now.`);
    }
    if (practicesFullyOnRpce !== null) {
      list.push(`${practicesFullyOnRpce.toLocaleString()} practices are fully on RPCE.`);
    }
    return list;
  }, [capabilities, practicesFullyOnRpce, totalRadsLive]);

  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % facts.length), 5000);
    return () => clearInterval(id);
  }, [facts.length]);

  return (
    <div style={{ ...CARD_STYLE, padding: "10px 16px", minHeight: 20 }}>
      <style>{`
        @keyframes mosaic-pulse-fact-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
      <div
        key={index}
        style={{ fontSize: 13, color: "var(--text-secondary)", animation: "mosaic-pulse-fact-in var(--dur-card) var(--ease-snap)" }}
      >
        {facts[index % facts.length]}
      </div>
    </div>
  );
}

// Team -> Radiologist adoption hierarchy - folded in from the standalone Adoption Map tab
// (removed per user feedback it felt redundant with this page). Built entirely from data the
// app already has (utilization-by-practice for the parent tier, roster filtered by practice for
// children, fetched lazily on expand). Fixes a real bug found while merging this in:
// `pct_mosaic` is a 0-1 fraction (same convention as every other pct_* field in this codebase,
// confirmed via DataTable.tsx's own fmtPct) but the old standalone page rendered it with
// `.toFixed(0)` directly - so every practice showed "0%" or "1%" regardless of real adoption,
// and the color thresholds (>=50/>=20) could never be cleared by a fraction <=1. Converting to
// a plain percent number once (adoptionColor/labels below) is the actual fix.
const TREE_PRACTICE_SPACING_X = 220;
const TREE_RAD_SPACING_X = 160;
const TREE_RAD_ROW_Y = 160;

function treeAdoptionColor(pct: number | null): string {
  if (pct === null) return "var(--text-muted)";
  if (pct >= 50) return "var(--status-good)";
  if (pct >= 20) return "var(--status-warning)";
  return "var(--status-critical)";
}

function treeNodeStyle(borderColor: string): React.CSSProperties {
  return {
    background: "var(--glass-fill-card)",
    backdropFilter: "blur(var(--glass-blur-sm))",
    WebkitBackdropFilter: "blur(var(--glass-blur-sm))",
    border: `1.5px solid ${borderColor}`,
    borderRadius: "var(--radius)",
    color: "var(--text-primary)",
    padding: "8px 12px",
    fontSize: "var(--font-size-12)",
    minWidth: 150,
    transition: `border-color var(--dur-card) var(--ease-standard)`,
  };
}

function AdoptionTreeSection() {
  const { theme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const practices = useFetch(() => mosaicApi.getUtilizationByPractice(), []);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [radByPractice, setRadByPractice] = useState<Record<string, { name: string; hasExams: boolean }[]>>({});
  const [loadingPractice, setLoadingPractice] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const practiceList = useMemo(
    () => (practices.data ?? []).filter((p) => p.practice).sort((a, b) => (b.pct_mosaic ?? 0) - (a.pct_mosaic ?? 0)),
    [practices.data]
  );

  const togglePractice = useCallback(
    async (practice: string) => {
      const next = new Set(expanded);
      if (next.has(practice)) {
        next.delete(practice);
        setExpanded(next);
        return;
      }
      next.add(practice);
      setExpanded(next);
      if (!radByPractice[practice]) {
        setLoadingPractice(practice);
        try {
          const roster = await mosaicApi.getRoster({ practice, limit: 500 });
          setRadByPractice((prev) => ({
            ...prev,
            [practice]: roster.map((r) => ({
              name: r.radiologist_name ?? `NPI ${r.npi}`,
              hasExams: (r.total_mosaic_exams ?? 0) > 0,
            })),
          }));
        } finally {
          setLoadingPractice(null);
        }
      }
    },
    [expanded, radByPractice]
  );

  useMemo(() => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    practiceList.forEach((p, i) => {
      const practice = p.practice as string;
      const pct = p.pct_mosaic === null ? null : p.pct_mosaic * 100;
      const color = treeAdoptionColor(pct);
      newNodes.push({
        id: `practice:${practice}`,
        position: { x: i * TREE_PRACTICE_SPACING_X, y: 0 },
        data: {
          label: (
            <AIHoverCard
              feature="adoption_rollout"
              entityLabel={practice}
              metricLabel="% Mosaic adoption"
              value={pct !== null ? `${pct.toFixed(0)}%` : "—"}
              underline={false}
            >
              <div onClick={() => togglePractice(practice)} style={{ cursor: "pointer" }}>
                <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{practice}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-11)" }}>
                  {pct !== null ? `${pct.toFixed(0)}% Mosaic` : "—"}
                  {loadingPractice === practice ? " · loading…" : expanded.has(practice) ? " · ▾" : " · ▸"}
                </div>
              </div>
            </AIHoverCard>
          ),
        },
        style: treeNodeStyle(color),
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });

      if (expanded.has(practice) && radByPractice[practice]) {
        const rads = radByPractice[practice];
        const startX = i * TREE_PRACTICE_SPACING_X - ((rads.length - 1) * TREE_RAD_SPACING_X) / 2;
        rads.forEach((r, j) => {
          const radId = `rad:${practice}:${j}`;
          const radColor = r.hasExams ? "var(--status-good)" : "var(--text-muted)";
          newNodes.push({
            id: radId,
            position: { x: startX + j * TREE_RAD_SPACING_X, y: TREE_RAD_ROW_Y },
            data: { label: <div style={{ fontSize: "var(--font-size-11)" }}>{r.name}</div> },
            style: { ...treeNodeStyle(radColor), minWidth: 120, padding: "6px 10px" },
            sourcePosition: Position.Bottom,
            targetPosition: Position.Top,
          });
          newEdges.push({
            id: `edge:${practice}:${j}`,
            source: `practice:${practice}`,
            target: radId,
            style: { stroke: "var(--border)" },
          });
        });
      }
    });

    setNodes(newNodes);
    setEdges(newEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [practiceList, expanded, radByPractice, loadingPractice]);

  return (
    <div style={{ ...CARD_STYLE, padding: 0, overflow: "hidden" }}>
      <div
        className="mosaic-card-hover"
        onClick={() => setCollapsed((c) => !c)}
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", cursor: "pointer" }}
      >
        <div>
          <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: 13 }}>Adoption map</div>
          <div style={{ color: "var(--text-muted)", fontSize: 11 }}>
            {/* Team, not Practice: the parent tier is utilization-by-practice, which groups on
                provider_local_practice_name_curr, and the children come from
                `getRoster({ practice })`, which filters `home_practice` - the same column. Both
                tiers are the radiologist's home practice, so the hierarchy is right; only the
                word was wrong. */}
            Team → radiologist adoption hierarchy. Click a team to expand its radiologists.
          </div>
        </div>
        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{collapsed ? "▸ Expand" : "▾ Collapse"}</span>
      </div>
      {!collapsed && (
        <>
          {practices.error && (
            <div style={{ color: "var(--status-critical)", fontSize: 13, padding: "0 16px 12px" }}>
              Couldn't reach the backend API. ({practices.error})
            </div>
          )}
          <div style={{ height: 420, background: "var(--page-plane)" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
              colorMode={theme}
              proOptions={{ hideAttribution: true }}
              style={{ background: "transparent" }}
            >
              <Background color="var(--gridline)" gap={24} />
              <Controls />
            </ReactFlow>
          </div>
        </>
      )}
    </div>
  );
}

export function MosaicPulse() {
  const [refreshTick, setRefreshTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setRefreshTick((t) => t + 1), 60000);
    return () => clearInterval(id);
  }, []);

  const intelligence = useFetch(() => mosaicApi.getMosaicIntelligence(), [refreshTick]);
  const captureOverview = useFetch(() => mosaicApi.getCaptureOverview(), [refreshTick]);
  const effReporting = useFetch(() => mosaicApi.getEfficiencyPopulation({ mode: "reporting" }), [refreshTick]);
  const effDrafting = useFetch(() => mosaicApi.getEfficiencyPopulation({ mode: "drafting" }), [refreshTick]);
  const effCapture = useFetch(() => mosaicApi.getEfficiencyPopulation({ mode: "capture" }), [refreshTick]);
  const [selected, setSelected] = useState<CapabilityKey | null>(null);

  const capabilities: CapabilityConfig[] = useMemo(
    () => [
      {
        key: "reporting",
        label: CAPABILITY_LABELS.reporting,
        adoptionPct: toPct(intelligence.data?.pct_rpce_reporting ?? null),
        radsLive: intelligence.data?.rads_live_on_mosaic ?? 0,
        efficiencyChangePct: toPct(effReporting.data?.pct_change_vs_baseline ?? null),
      },
      {
        key: "drafting",
        label: CAPABILITY_LABELS.drafting,
        adoptionPct: toPct(intelligence.data?.pct_rpce_drafting ?? null),
        radsLive: intelligence.data?.rads_live_on_ai_drafting ?? 0,
        efficiencyChangePct: toPct(effDrafting.data?.pct_change_vs_baseline ?? null),
      },
      {
        key: "capture",
        label: CAPABILITY_LABELS.capture,
        adoptionPct: toPct(captureOverview.data?.pct_captured_enabled ?? null),
        radsLive: intelligence.data?.rads_live_on_capture ?? 0,
        efficiencyChangePct: toPct(effCapture.data?.pct_change_vs_baseline ?? null),
      },
    ],
    [intelligence.data, captureOverview.data, effReporting.data, effDrafting.data, effCapture.data]
  );

  const totalRadsLive = intelligence.data ? capabilities.reduce((sum, c) => sum + c.radsLive, 0) : null;
  const selectedConfig = capabilities.find((c) => c.key === selected) ?? null;
  const { rows, sortLabel, loading } = useCapabilityDetail(selected);

  const loadingAny = intelligence.loading || captureOverview.loading || effReporting.loading || effDrafting.loading || effCapture.loading;
  const anyError = intelligence.error || captureOverview.error || effReporting.error || effDrafting.error || effCapture.error;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        A live, animated overview of Mosaic as a platform - hover a capability for AI context,
        click one to drill into its breakdown - by Practice (the site read at) for Reporting and
        Drafting, by Team (the rad's home practice) for Capture. Ring color and the flow strip both reflect each
        capability's efficiency change vs baseline; ring sweep reflects live adoption %.
      </div>

      {anyError && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({anyError})</div>
      )}

      {loadingAny ? (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading live data…</div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {capabilities.map((config) => (
              <CapabilityGauge key={config.key} config={config} onSelect={setSelected} />
            ))}
          </div>

          <FlowStrip capabilities={capabilities} onSelect={setSelected} />

          <PulseFacts
            capabilities={capabilities}
            practicesFullyOnRpce={intelligence.data?.practices_fully_on_rpce ?? null}
            totalRadsLive={totalRadsLive}
          />

          <AdoptionTreeSection />
        </>
      )}

      <Drawer open={selected !== null} onClose={() => setSelected(null)} title={selectedConfig?.label}>
        {selectedConfig && (
          <CapabilityDrawerBody
            config={selectedConfig}
            rows={rows}
            sortLabel={sortLabel}
            loading={loading}
            entityLabel={entityLabelFor(selected)}
          />
        )}
      </Drawer>
    </div>
  );
}
