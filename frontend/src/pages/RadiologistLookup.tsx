import { useEffect, useState } from "react";
import { mosaicApi } from "../api/client";
import type { RadiologistLookupDetail, RadiologistLookupMatch } from "../api/types";
import { StatTile } from "../components/StatTile";
import { AIHoverCard } from "../components/AIHoverCard";
import { NotesPanel } from "../components/NotesPanel";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { CARD_STYLE } from "../styles/glassCard";

// Deliberately mirrors PCC's own privacy-gated radiologist drilldown (confirmed from its own
// compiled bundle/changelog): search-only, 3-character minimum, no roster-browsing endpoint,
// and - critically - no route param for the selected NPI, so this page can never be deep-
// linked or bookmarked by name. Every real open of a detail view is logged server-side
// (see routes/mosaic.py's GET /radiologist-lookup/{npi}).

const EFF_COLUMNS: DataTableColumn<RadiologistLookupDetail["efficiency_by_category"][number]>[] = [
  { key: "exam_category", label: "Category" },
  {
    key: "full_mosaic_tbwu_per_min",
    label: "TBWU/min",
    render: (r) => (r.full_mosaic_tbwu_per_min != null ? r.full_mosaic_tbwu_per_min.toFixed(3) : "—"),
  },
];

export function RadiologistLookup() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<RadiologistLookupMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RadiologistLookupMatch | null>(null);
  const [detail, setDetail] = useState<RadiologistLookupDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(id);
  }, [query]);

  useEffect(() => {
    if (debouncedQuery.trim().length < 3) {
      setResults([]);
      setSearchError(null);
      return;
    }
    let cancelled = false;
    setSearching(true);
    setSearchError(null);
    mosaicApi
      .searchRadiologistLookup(debouncedQuery)
      .then((r) => {
        if (!cancelled) setResults(r);
      })
      .catch((err: Error) => {
        if (!cancelled) setSearchError(err.message);
      })
      .finally(() => {
        if (!cancelled) setSearching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  function selectMatch(match: RadiologistLookupMatch) {
    setSelected(match);
    setDetail(null);
    setDetailLoading(true);
    mosaicApi
      .getRadiologistLookup(match.npi, debouncedQuery)
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, padding: "16px 24px", minHeight: 0, overflow: "auto" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-13)" }}>
        Search for a radiologist by name (3+ characters) to view their individual efficiency,
        capacity, and scorecard detail. This page intentionally has no browsable roster and
        cannot be linked to by name - every view is logged.
      </div>

      <div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search radiologist name..."
          style={{
            width: "100%",
            maxWidth: 420,
            padding: "8px 12px",
            borderRadius: "var(--radius)",
            border: "var(--glass-border)",
            background: "var(--surface-raised)",
            color: "var(--text-primary)",
            fontSize: 14,
          }}
        />
        {query.trim().length > 0 && query.trim().length < 3 && (
          <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4 }}>
            Type at least 3 characters to search.
          </div>
        )}
        {searchError && <div style={{ color: "var(--status-critical)", fontSize: 12, marginTop: 4 }}>{searchError}</div>}
      </div>

      {searching && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Searching...</div>}

      {!selected && results.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {results.map((r) => (
            <div
              key={r.npi}
              className="mosaic-card-hover"
              onClick={() => selectMatch(r)}
              style={{ ...CARD_STYLE, padding: 12, cursor: "pointer" }}
            >
              <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{r.radiologist_name ?? `NPI ${r.npi}`}</div>
              <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{r.home_practice ?? "—"}</div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0, fontSize: 18 }}>{selected.radiologist_name ?? `NPI ${selected.npi}`}</h2>
            <button
              onClick={() => {
                setSelected(null);
                setDetail(null);
              }}
              style={{
                background: "transparent",
                border: "var(--glass-border)",
                borderRadius: "var(--radius)",
                color: "var(--text-secondary)",
                padding: "4px 10px",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              ← Back to search
            </button>
          </div>

          {detailLoading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading detail...</div>}

          {detail && (
            <>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <AIHoverCard
                  feature="adoption_rollout"
                  entityLabel={selected.radiologist_name ?? `NPI ${selected.npi}`}
                  metricLabel="Home practice"
                  value={String((detail.roster as Record<string, unknown> | null)?.home_practice ?? "—")}
                  underline={false}
                  style={{ flex: "1 1 200px", minWidth: 180 }}
                >
                  <StatTile
                    label="Practice"
                    value={String((detail.roster as Record<string, unknown> | null)?.home_practice ?? "—")}
                  />
                </AIHoverCard>
                <AIHoverCard
                  feature="capacity_figure"
                  entityLabel={selected.radiologist_name ?? `NPI ${selected.npi}`}
                  metricLabel="Capacity (TBWU)"
                  value={
                    (detail.capacity as Record<string, unknown> | null)?.capacity_rpwu != null
                      ? Number((detail.capacity as Record<string, number>).capacity_rpwu).toFixed(1)
                      : "—"
                  }
                  underline={false}
                  style={{ flex: "1 1 200px", minWidth: 180 }}
                >
                  <StatTile
                    label="Capacity (TBWU)"
                    value={
                      (detail.capacity as Record<string, unknown> | null)?.capacity_rpwu != null
                        ? Number((detail.capacity as Record<string, number>).capacity_rpwu).toFixed(1)
                        : "—"
                    }
                  />
                </AIHoverCard>
                <AIHoverCard
                  feature="efficiency_metric"
                  entityLabel={selected.radiologist_name ?? `NPI ${selected.npi}`}
                  metricLabel="Utilization"
                  value={
                    (detail.capacity as Record<string, unknown> | null)?.utilization_rpwu_pct != null
                      ? `${(Number((detail.capacity as Record<string, number>).utilization_rpwu_pct) * 100).toFixed(0)}%`
                      : "—"
                  }
                  underline={false}
                  style={{ flex: "1 1 200px", minWidth: 180 }}
                >
                  <StatTile
                    label="Utilization"
                    value={
                      (detail.capacity as Record<string, unknown> | null)?.utilization_rpwu_pct != null
                        ? `${(Number((detail.capacity as Record<string, number>).utilization_rpwu_pct) * 100).toFixed(0)}%`
                        : "—"
                    }
                  />
                </AIHoverCard>
              </div>

              <div style={CARD_STYLE}>
                <div style={{ fontWeight: "var(--font-weight-semibold)", marginBottom: 10 }}>Efficiency by category</div>
                {detail.efficiency_by_category.length === 0 ? (
                  <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No efficiency data for this radiologist.</div>
                ) : (
                  <DataTable columns={EFF_COLUMNS} rows={detail.efficiency_by_category} rowKey={(r) => r.exam_category ?? "unknown"} />
                )}
              </div>

              <div style={CARD_STYLE}>
                <div style={{ fontWeight: "var(--font-weight-semibold)", marginBottom: 10 }}>Notes</div>
                <NotesPanel entityType="radiologist" entityKey={String(selected.npi)} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
