import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { mosaicApi } from "../api/client";
import type {
  CubeCell,
  RadiologistLookupDetail,
  RadiologistLookupMatch,
  UtilizationPracticeRollup,
} from "../api/types";
import { CARD_STYLE } from "../styles/glassCard";
import { DataTable } from "../components/DataTable";
import type { DataTableColumn } from "../components/DataTable";
import { NotesPanel } from "../components/NotesPanel";
import { MoversWaterfall } from "../components/MoversWaterfall";

/**
 * Entity 360 - one practice or one radiologist, on one page.
 *
 * Every drill-down in this module used to dead-end in a Drawer: no URL, no back button, and
 * nothing to paste into a message. The entity is the unit people actually talk about, so it
 * gets a route.
 *
 * ⚠️ Privacy note, deliberately left visible for whoever reads this next.
 * `RadiologistLookup.tsx` mirrors PCC's own privacy-gated drilldown, and one of the controls
 * it mirrors is that the selected NPI is NOT a route param - so that page can never be deep-
 * linked. `/entity/radiologist/:npi` changes that. Two things are preserved verbatim:
 * search-first entry (the finder below is the same 3-character search, there is no name-
 * browsable radiologist index), and the server-side access log, which fires on
 * `GET /radiologist-lookup/{npi}` exactly as before and still receives the search term when
 * there is one. What changes is that a rad's page is now bookmarkable by NPI. That is a policy
 * call, not an implementation detail - it is flagged for a ruling rather than assumed.
 */

type EntityType = "practice" | "radiologist";

function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString();
}

function fmtPct(fraction: number | null | undefined, digits = 1): string {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  return `${(fraction * 100).toFixed(digits)}%`;
}

const PAGE_STYLE: React.CSSProperties = {
  padding: 24,
  display: "flex",
  flexDirection: "column",
  gap: 20,
  flex: 1,
  minHeight: 0,
  overflowY: "auto",
};

function Measure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ ...CARD_STYLE, flex: "1 1 170px", minWidth: 150 }}>
      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function EntityHeader({ kind, name, sub }: { kind: string; name: string; sub?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
      <div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: 0.5, fontWeight: 600 }}>{kind}</div>
        <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2 }}>{name}</div>
        {sub && <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{sub}</div>}
      </div>
      <Link to="/entity" style={{ fontSize: 13, color: "var(--text-secondary)" }}>
        ← Find another
      </Link>
    </div>
  );
}

/**
 * Renders whatever of a set of known keys is actually present in one of the lookup endpoint's
 * untyped bags. The bags are `Record<string, unknown>` on purpose - they are forwarded from
 * three different services - so this reads defensively rather than asserting a shape that
 * nothing guarantees.
 */
function BagFields({ bag, fields }: { bag: Record<string, unknown> | null | undefined; fields: [string, string][] }) {
  if (!bag) return null;
  const present = fields.filter(([key]) => bag[key] !== null && bag[key] !== undefined && bag[key] !== "");
  if (present.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 28px", fontSize: 12, color: "var(--text-muted)" }}>
      {present.map(([key, label]) => {
        const raw = bag[key];
        const text = typeof raw === "number" ? raw.toLocaleString() : String(raw);
        return (
          <span key={key}>
            {label} <strong style={{ color: "var(--text-primary)", fontWeight: 600 }}>{text}</strong>
          </span>
        );
      })}
    </div>
  );
}

const CUBE_MEASURES = ["total_exams", "mosaic_exams", "drafting_exams", "pct_mosaic", "pct_rpce_reporting", "pct_rpce_drafting"];

function useCubeSlice(entityType: EntityType, entityId: string) {
  const cube = useFetch(
    () => mosaicApi.postCube({ metrics: CUBE_MEASURES, entity_type: entityType, entity_id: entityId }),
    [entityType, entityId]
  );
  const cells = useMemo(() => {
    const map = new Map<string, CubeCell>();
    for (const row of cube.data?.rows ?? []) map.set(row.measure, row);
    return map;
  }, [cube.data]);
  return { cube, cells };
}

function PracticeEntity({ id }: { id: string }) {
  const { cube, cells } = useCubeSlice("practice", id);
  const utilization = useFetch(() => mosaicApi.getUtilizationByPractice(), []);
  const capture = useFetch(() => mosaicApi.getCaptureByPractice(id), [id]);
  const capacity = useFetch(() => mosaicApi.getCapacityByPractice(), []);

  const mine: UtilizationPracticeRollup | undefined = (utilization.data ?? []).find((r) => r.practice === id);
  const myCapture = (capture.data ?? [])[0];
  const myCapacity = (capacity.data ?? []).find((r) => r.practice === id);

  // Peer band: where this practice sits among all practices on adoption. A rank is a comparison
  // the reader can act on; a bare percentage is not.
  const peers = useMemo(() => {
    const rows = (utilization.data ?? []).filter((r) => r.pct_mosaic !== null && r.practice);
    const sorted = [...rows].sort((a, b) => (b.pct_mosaic ?? 0) - (a.pct_mosaic ?? 0));
    const idx = sorted.findIndex((r) => r.practice === id);
    if (idx < 0 || sorted.length === 0) return null;
    const median = sorted[Math.floor(sorted.length / 2)]?.pct_mosaic ?? null;
    return { rank: idx + 1, of: sorted.length, median };
  }, [utilization.data, id]);

  return (
    <div style={PAGE_STYLE}>
      <EntityHeader
        kind="PRACTICE (exam site)"
        name={id}
        sub={
          peers
            ? `Ranked ${peers.rank} of ${peers.of} practices on Mosaic adoption. Median practice is at ${fmtPct(
                peers.median
              )}.`
            : undefined
        }
      />

      {cube.error && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>Couldn't reach the backend API. ({cube.error})</div>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Measure label="Exams" value={fmtInt(cells.get("total_exams")?.value ?? cells.get("total_exams")?.num)} sub="All exams at this site" />
        <Measure
          label="On Mosaic"
          value={fmtPct(cells.get("pct_mosaic")?.value)}
          sub={`${fmtInt(cells.get("mosaic_exams")?.value ?? cells.get("mosaic_exams")?.num)} exams`}
        />
        <Measure
          label="AI Drafting"
          value={fmtPct(cells.get("pct_rpce_drafting")?.value)}
          sub={`${fmtInt(cells.get("drafting_exams")?.value ?? cells.get("drafting_exams")?.num)} exams`}
        />
        <Measure
          label="Capture"
          value={fmtPct(myCapture?.pct_captured_enabled)}
          sub={myCapture ? `${myCapture.rads_live_on_capture} live of ${myCapture.rads_capture_enabled} enabled` : undefined}
        />
        <Measure
          label="Radiologists live"
          value={fmtInt(mine?.rads_live)}
          sub={mine?.rads_drafting !== null && mine?.rads_drafting !== undefined ? `${mine.rads_drafting} on drafting` : undefined}
        />
        <Measure
          label="Shift utilization"
          value={fmtPct(myCapacity?.utilization_rpwu_pct !== null && myCapacity?.utilization_rpwu_pct !== undefined ? myCapacity.utilization_rpwu_pct / 100 : null)}
          sub={myCapacity ? `${fmtInt(myCapacity.total_shifts)} shifts` : undefined}
        />
      </div>

      {/* Why this practice sits where it does: case mix against rate, not a single number. */}
      <MoversWaterfall mode="full_mosaic" practice={id} subspecialty="" modality="" procedure="" examCategory="" />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 320px", minWidth: 280 }}>
          <NotesPanel entityType="practice" entityKey={id} />
        </div>
        <div style={{ ...CARD_STYLE, flex: "1 1 280px", minWidth: 260, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Go deeper on {id}</div>
          <Link to={`/explore?dim=practice`} style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            See it beside every other practice in Explore
          </Link>
          <Link to="/cockpit" style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            What to work here — the Cockpit worklist
          </Link>
          <Link to={`/non-drafted?practice=${encodeURIComponent(id)}`} style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Draftable exams that were not drafted
          </Link>
        </div>
      </div>
    </div>
  );
}

const EFFICIENCY_COLUMNS: DataTableColumn<RadiologistLookupDetail["efficiency_by_category"][number]>[] = [
  { key: "exam_category", label: "Exam category" },
  { key: "reporting_tbwu", label: "Reporting TBWU" },
  { key: "drafting_tbwu", label: "Drafting TBWU" },
  { key: "capture_tbwu", label: "Capture TBWU" },
  {
    key: "full_mosaic_tbwu_per_min",
    label: "TBWU / min",
    render: (row) => (row.full_mosaic_tbwu_per_min === null ? "—" : row.full_mosaic_tbwu_per_min.toFixed(3)),
  },
];

function RadiologistEntity({ npi, searchTerm }: { npi: number; searchTerm?: string }) {
  // `searchTerm` is forwarded so the server-side access log keeps recording what the opener
  // typed. A deep-linked open has no term and simply logs without one - the open itself is
  // still logged, which is the control that matters.
  const detail = useFetch(() => mosaicApi.getRadiologistLookup(npi, searchTerm), [npi, searchTerm]);
  const { cube, cells } = useCubeSlice("radiologist", String(npi));

  const roster = detail.data?.roster ?? null;
  const name = typeof roster?.radiologist_name === "string" ? roster.radiologist_name : `NPI ${npi}`;
  const homePractice = typeof roster?.home_practice === "string" ? roster.home_practice : null;

  return (
    <div style={PAGE_STYLE}>
      <EntityHeader
        kind="RADIOLOGIST"
        name={name}
        sub={homePractice ? `Home practice (Team): ${homePractice}` : undefined}
      />

      {(detail.error || cube.error) && (
        <div style={{ color: "var(--status-critical)", fontSize: 13 }}>
          Couldn't reach the backend API. ({detail.error ?? cube.error})
        </div>
      )}
      {detail.loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Measure label="Exams" value={fmtInt(cells.get("total_exams")?.value ?? cells.get("total_exams")?.num)} />
        <Measure label="On Mosaic" value={fmtPct(cells.get("pct_mosaic")?.value)} />
        <Measure label="AI Drafting" value={fmtPct(cells.get("pct_rpce_drafting")?.value)} />
        <Measure label="Reporting" value={fmtPct(cells.get("pct_rpce_reporting")?.value)} />
      </div>

      {/* Team and Practice are different columns and are shown as different rows on purpose:
          home practice is the rad's team, and the sites below are where the exams happened. */}
      <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Roster and deployment</div>
        <BagFields
          bag={roster}
          fields={[
            ["current_team", "Current team"],
            ["primary_site", "Primary site"],
            ["site_count", "Sites read at"],
            ["working_subspecialty", "Subspecialty"],
            ["deployment_status", "Deployment status"],
            ["deployment_launch_group", "Launch group"],
            ["capture_enabled", "Capture enabled"],
          ]}
        />
        <BagFields
          bag={detail.data?.capacity}
          fields={[
            ["total_shifts", "Shifts"],
            ["utilization_rpwu_pct", "Shift utilization %"],
            ["efficiency_rpwu_per_min", "RPWU / min"],
            ["avg_rvu_per_case", "Avg RVU / case"],
          ]}
        />
        <BagFields
          bag={detail.data?.scorecard}
          fields={[
            ["team", "Scorecard team"],
            ["practice", "Scorecard practice"],
            ["pct_mosaic", "Scorecard % Mosaic"],
            ["pct_drafting", "Scorecard % drafting"],
          ]}
        />
      </div>

      {detail.data && detail.data.efficiency_by_category.length > 0 && (
        <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Efficiency by exam category</div>
          <DataTable
            columns={EFFICIENCY_COLUMNS}
            rows={detail.data.efficiency_by_category}
            rowKey={(row) => row.exam_category ?? "—"}
          />
        </div>
      )}

      <NotesPanel entityType="radiologist" entityKey={String(npi)} />
    </div>
  );
}

/**
 * The front door. Radiologists are search-only with a three-character minimum, exactly as the
 * lookup page has always been; practices are browsable, because a practice is an organizational
 * unit rather than a person.
 */
export function EntityFinder() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [practiceFilter, setPracticeFilter] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const matches = useFetch<RadiologistLookupMatch[]>(
    () => (debounced.length >= 3 ? mosaicApi.searchRadiologistLookup(debounced) : Promise.resolve([])),
    [debounced]
  );
  const practices = useFetch(() => mosaicApi.getUtilizationByPractice(), []);

  const practiceRows = useMemo(() => {
    const rows = (practices.data ?? []).filter((r): r is UtilizationPracticeRollup & { practice: string } => Boolean(r.practice));
    const needle = practiceFilter.trim().toLowerCase();
    const filtered = needle ? rows.filter((r) => r.practice.toLowerCase().includes(needle)) : rows;
    return [...filtered].sort((a, b) => (b.total_exams ?? 0) - (a.total_exams ?? 0));
  }, [practices.data, practiceFilter]);

  const inputStyle: React.CSSProperties = {
    background: "var(--surface-raised)",
    color: "var(--text-primary)",
    border: "var(--glass-border)",
    borderRadius: "var(--radius-sm, 6px)",
    padding: "9px 12px",
    fontSize: 14,
    width: "100%",
    boxSizing: "border-box",
  };

  return (
    <div style={PAGE_STYLE}>
      <div>
        <div style={{ fontSize: 20, fontWeight: 600 }}>Entity 360</div>
        <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 2 }}>
          One practice or one radiologist, with everything the module knows about them on one page.
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ ...CARD_STYLE, flex: "1 1 360px", minWidth: 300, display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Find a radiologist</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
              Search by name or NPI. Three characters minimum, and every detail view opened is logged.
            </div>
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Name or NPI…"
            style={inputStyle}
            aria-label="Search radiologists by name or NPI"
          />
          {debounced.length > 0 && debounced.length < 3 && (
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Keep typing — three characters minimum.</div>
          )}
          {matches.loading && <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Searching…</div>}
          {debounced.length >= 3 && matches.data?.length === 0 && !matches.loading && (
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>No radiologist matches “{debounced}”.</div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, maxHeight: 280, overflowY: "auto" }}>
            {(matches.data ?? []).map((m) => (
              <Link
                key={m.npi}
                to={`/entity/radiologist/${m.npi}?q=${encodeURIComponent(debounced)}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "8px 10px",
                  borderRadius: 6,
                  fontSize: 13,
                  color: "var(--text-primary)",
                  textDecoration: "none",
                  background: "var(--surface-1)",
                }}
              >
                <span>{m.radiologist_name ?? `NPI ${m.npi}`}</span>
                <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{m.home_practice ?? "—"}</span>
              </Link>
            ))}
          </div>
          <Link to="/roster" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            Browse the full roster instead
          </Link>
        </div>

        <div style={{ ...CARD_STYLE, flex: "1 1 360px", minWidth: 300, display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Pick a practice</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
              The exam site, ordered by volume. {practiceRows.length} in view.
            </div>
          </div>
          <input
            value={practiceFilter}
            onChange={(e) => setPracticeFilter(e.target.value)}
            placeholder="Filter practices…"
            style={inputStyle}
            aria-label="Filter practices by name"
          />
          {practices.loading && <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading practices…</div>}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, maxHeight: 340, overflowY: "auto" }}>
            {practiceRows.map((r) => (
              <Link
                key={r.practice}
                to={`/entity/practice/${encodeURIComponent(r.practice)}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "8px 10px",
                  borderRadius: 6,
                  fontSize: 13,
                  color: "var(--text-primary)",
                  textDecoration: "none",
                  background: "var(--surface-1)",
                }}
              >
                <span>{r.practice}</span>
                <span style={{ color: "var(--text-muted)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                  {fmtInt(r.total_exams)} exams · {fmtPct(r.pct_mosaic, 0)} Mosaic
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Entity360() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const searchTerm = new URLSearchParams(window.location.search).get("q") ?? undefined;

  if (!type || !id) return <EntityFinder />;

  if (type === "practice") return <PracticeEntity id={decodeURIComponent(id)} />;

  if (type === "radiologist") {
    const npi = Number(id);
    if (!Number.isFinite(npi)) {
      return (
        <div style={PAGE_STYLE}>
          <div style={{ ...CARD_STYLE, fontSize: 13, color: "var(--text-muted)" }}>
            “{id}” is not an NPI. Radiologists are addressed by NPI, never by name.
          </div>
          <EntityFinder />
        </div>
      );
    }
    return <RadiologistEntity npi={npi} searchTerm={searchTerm} />;
  }

  return (
    <div style={PAGE_STYLE}>
      <div style={{ ...CARD_STYLE, fontSize: 13, color: "var(--text-muted)" }}>
        There is no entity type called “{type}”. This page knows about practices and radiologists.
      </div>
      <EntityFinder />
    </div>
  );
}
