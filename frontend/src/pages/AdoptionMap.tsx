import { useCallback, useMemo, useState } from "react";
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
import { useTheme } from "../context/ThemeContext";

// Practice -> Radiologist adoption hierarchy, built entirely from data the app already has
// (utilization-by-practice for the parent tier, roster filtered by practice for children,
// fetched lazily on expand rather than all ~2,830 radiologists up front). A scoped first
// version of the kind of interactive map Yaro built for PCC's client/site hierarchy - read-only
// explore, no drag-to-edit (that's PCC's own distinct "journalable" interaction, not this).

const PRACTICE_SPACING_X = 220;
const RAD_SPACING_X = 160;
const RAD_ROW_Y = 160;

function adoptionColor(pct: number | null): string {
  if (pct === null) return "var(--text-muted)";
  if (pct >= 50) return "var(--status-good)";
  if (pct >= 20) return "var(--status-warning)";
  return "var(--status-critical)";
}

function nodeStyle(borderColor: string): React.CSSProperties {
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

export function AdoptionMap() {
  const { theme } = useTheme();
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
      const color = adoptionColor(p.pct_mosaic);
      newNodes.push({
        id: `practice:${practice}`,
        position: { x: i * PRACTICE_SPACING_X, y: 0 },
        data: {
          label: (
            <div onClick={() => togglePractice(practice)} style={{ cursor: "pointer" }}>
              <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{practice}</div>
              <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-11)" }}>
                {p.pct_mosaic !== null ? `${p.pct_mosaic.toFixed(0)}% Mosaic` : "—"}
                {loadingPractice === practice ? " · loading…" : expanded.has(practice) ? " · ▾" : " · ▸"}
              </div>
            </div>
          ),
        },
        style: nodeStyle(color),
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });

      if (expanded.has(practice) && radByPractice[practice]) {
        const rads = radByPractice[practice];
        const startX = i * PRACTICE_SPACING_X - ((rads.length - 1) * RAD_SPACING_X) / 2;
        rads.forEach((r, j) => {
          const radId = `rad:${practice}:${j}`;
          const radColor = r.hasExams ? "var(--status-good)" : "var(--text-muted)";
          newNodes.push({
            id: radId,
            position: { x: startX + j * RAD_SPACING_X, y: RAD_ROW_Y },
            data: { label: <div style={{ fontSize: "var(--font-size-11)" }}>{r.name}</div> },
            style: { ...nodeStyle(radColor), minWidth: 120, padding: "6px 10px" },
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
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ padding: "16px 24px 0" }}>
        <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
          Practice → Radiologist adoption hierarchy. Click a practice to expand its radiologists - node color
          reflects Mosaic adoption (green/amber/red by % live, muted for not-yet-reporting radiologists).
        </div>
      </div>
      {practices.error && (
        <div style={{ color: "var(--status-critical)", fontSize: 13, padding: "0 24px" }}>
          Couldn't reach the backend API. ({practices.error})
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, background: "var(--page-plane)" }}>
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
    </div>
  );
}
