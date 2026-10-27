"""Builds the Mosaic cube and reads it back - the only module that knows both the registry and
the EDW.

Two halves, deliberately kept in one file because they are two directions of the same contract:

**Write side** (`fetch_rows` / `store_rows`, called from refresh_service): ONE EDW query with five
GROUPING SETS produces every entity level in a single pass, and `_fan_out` turns each grid row
into one `mosaic_fact` row per measure. The alternative - five queries, one per level - would be
five cold-connection waits against `databricks_client`'s single process-lifetime connection, and
would let the levels disagree: an enterprise total summed at 09:00 and a practice breakdown summed
at 09:40 can legitimately differ, which is the stale-snapshot failure class this project has
already been bitten by.

**Read side** (`query`): takes a scope the registry has already validated, rolls up via
`fact_store.rollup`, and only then divides. The division lives here and nowhere else, because of
two things stored numerators cannot carry:

  - SUM(num)/SUM(den) re-aggregates correctly; AVG(rate) does not. This is `_scorecard_window_sql`'s
    "Fix 3" relocated into the storage schema, where it cannot be forgotten.
  - `MetricSpec.offset` is *additive* and must be applied exactly ONCE per grain, after dividing.
    Folded into a stored numerator it would be multiplied by the number of rows summed.

Wave 1 covers the seven composable Utilization (Volume) metrics. Capacity (27 metrics) is Wave 2
and Deployment is Wave 3; the 19 `composable=False` specs - all three Efficiency metrics, all
fourteen MVP metrics, plus `expected_unlock_tbwu` and `peer_benchmark_draft_rate` - are computed in
their own services and will never be cube-composed. `_WAVE1_METRICS` is filtered through
`spec.composable` anyway rather than hand-listed, so adding a non-composable metric to a wave
raises at import rather than emitting SQL for an expression the registry refuses to build.
"""

from __future__ import annotations

from datetime import date

from app.config import settings
from app.db import cache_store, fact_store
from app.db.databricks_client import run_query
from app.semantics import registry as reg
from app.services.volume_service import _LOCAL_REGION_CASE_SQL

# How far back the cube is built. 24 months × (1 enterprise + 6 regions + ~200 practices +
# ~200 teams + ~5,000 radiologists) ≈ 130K grid rows ≈ 900K facts across 7 measures - the same
# order as efficiency_store's proven 784K, so this fits the existing SQLite budget.
LOOKBACK_MONTHS = 24

GRAIN = "month"

# Written into entity_id when the grouping column itself is NULL - exams whose managing or
# provider practice is unattributed in the source. The fact table's primary key includes
# entity_id, so a NULL there would collapse every unattributed group into one row (or be rejected
# outright); naming the bucket keeps it visible instead of silently merged into a real practice.
UNATTRIBUTED = "(unattributed)"

# Wave 1: Utilization/Volume. Order is the order measures appear in the SELECT, and therefore the
# order they are stored - kept stable so a diff of two cube builds is readable.
_WAVE1_KEYS = (
    "total_exams",
    "mosaic_exams",
    "pct_mosaic",
    "drafting_exams",
    "pct_drafting",
    "pct_rpce_reporting",
    "pct_rpce_drafting",
)


def _wave1_specs() -> list:
    specs = [reg.get_metric(k) for k in _WAVE1_KEYS]
    bad = [s.key for s in specs if not s.composable]
    if bad:
        # Import-time-ish guard (this runs on first use). A non-composable spec has no SQL to
        # emit - registry.MetricSpec.value_sql() raises for exactly this reason - so catching it
        # here names the metric, rather than failing later inside a 900K-row fan-out.
        raise ValueError(f"cube wave 1 contains non-composable metrics: {', '.join(bad)}")
    return specs


def _solution_for(spec) -> str:
    """The cube's solution axis value for a metric.

    A metric that belongs to exactly one solution is filed under it; one that spans all three
    (only `total_exams` today - it is the denominator the other six are measured against) is
    filed under 'all'. This is mechanical on purpose: the axis is read off the registry rather
    than assigned by hand, so a metric cannot be filed under a solution its own definition
    doesn't claim.
    """
    return spec.solutions[0] if len(spec.solutions) == 1 else "all"


# ---------------------------------------------------------------------------------------------
# Write side
# ---------------------------------------------------------------------------------------------

def _measures_sql(specs: list, indent: str = "      ") -> str:
    """One `expr AS key__num` (and `__den` for rates) per metric, taken from the registry.

    `total_exams.numerator` and `pct_mosaic.denominator` are both `COUNT(*)`, and the two RPCE
    rates share a denominator - so this emits the same expression more than once. That duplication
    is deliberate: collapsing it would mean this module deciding which metrics may share a
    denominator, which is precisely the judgment the registry exists to hold. Spark's optimizer
    computes each distinct aggregate once regardless.

    `numerator_scale` (` * 1.0` on the two RPCE rates) is intentionally NOT applied here. It exists
    to force float division in a context that divides in SQL; this query stores numerator and
    denominator separately and divides in Python, where the scale is a no-op.
    """
    parts: list[str] = []
    for spec in specs:
        parts.append(f"{spec.numerator} AS {spec.key}__num")
        if spec.is_rate:
            parts.append(f"{spec.denominator} AS {spec.key}__den")
    return (",\n" + indent).join(parts)


def _grid_sql() -> str:
    specs = _wave1_specs()
    return f"""
    WITH base AS (
      SELECT
        DATE_TRUNC('MONTH', final_datetime)   AS month_start,
        managing_local_practice_name_curr     AS practice,
        provider_local_practice_name_curr     AS team,
        {_LOCAL_REGION_CASE_SQL}              AS local_region,
        CAST(reading_provider_npi AS STRING)  AS npi,
        reading_provider_name_full            AS rad_name,
        mosaic_read_flag,
        mosaic_draft_flag,
        Source_System_Code
      FROM {settings.qualified}.tbl_exam_inventory
      WHERE final_datetime IS NOT NULL
        AND final_datetime >= DATE_TRUNC('MONTH', ADD_MONTHS(CURRENT_DATE(), -{LOOKBACK_MONTHS - 1}))
    )
    SELECT
      month_start,
      practice,
      team,
      local_region,
      npi,
      MAX(rad_name)          AS rad_name,
      GROUPING(practice)     AS g_practice,
      GROUPING(team)         AS g_team,
      GROUPING(local_region) AS g_local_region,
      GROUPING(npi)          AS g_npi,
      {_measures_sql(specs)}
    FROM base
    GROUP BY GROUPING SETS (
      (month_start),
      (month_start, local_region),
      (month_start, practice),
      (month_start, team),
      (month_start, npi, team)
    )
    """


def _entity_of(row: dict) -> tuple[str, str, str, str | None, str | None]:
    """(entity_type, entity_id, entity_label, parent_practice, parent_team) for one grid row.

    Which grouping set produced a row is read from GROUPING(), never from "is this column NULL" -
    a genuinely-NULL practice and a practice aggregated away both show NULL, and conflating them
    would file every unattributed exam under the enterprise total.

    The radiologist branch is checked first and is the one that matters: a rad has exactly one
    home practice (Team, `provider_local_practice_name_curr`) but reads at up to ~70 managing
    Practices, so `parent_practice` is left NULL at that grain *on purpose*. Writing any single
    value there is the `MAX(practice) AS team` conflation that Phase 1 removed from
    get_radiologist_scorecard, and this schema is shaped so it cannot be re-introduced.
    """
    if not row["g_npi"]:
        npi = row["npi"] or UNATTRIBUTED
        return "radiologist", npi, (row["rad_name"] or npi), None, row["team"]
    if not row["g_practice"]:
        practice = row["practice"] or UNATTRIBUTED
        return "practice", practice, practice, practice, None
    if not row["g_team"]:
        team = row["team"] or UNATTRIBUTED
        return "team", team, team, None, team
    if not row["g_local_region"]:
        region = row["local_region"] or UNATTRIBUTED
        return "local_region", region, region, None, None
    return "enterprise", "enterprise", "Enterprise", None, None


def _period_of(row: dict) -> str:
    month = row.get("month_start")
    if month is None:
        return ""
    if isinstance(month, date):
        return month.isoformat()[:10]
    return str(month)[:10]


def _fan_out(grid: list[dict], specs: list) -> list[dict]:
    """One grid row -> one fact row per measure."""
    facts: list[dict] = []
    for row in grid:
        entity_type, entity_id, entity_label, parent_practice, parent_team = _entity_of(row)
        period = _period_of(row)
        for spec in specs:
            num = row.get(f"{spec.key}__num")
            den = row.get(f"{spec.key}__den") if spec.is_rate else None
            facts.append(
                {
                    "period_start": period,
                    "grain": GRAIN,
                    "solution": _solution_for(spec),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "entity_label": entity_label,
                    "parent_practice": parent_practice,
                    "parent_team": parent_team,
                    # Deployment (Wave 3) owns this column; until it lands there is no governed
                    # go-live stage to write, and an invented one would read as real.
                    "lifecycle_stage": None,
                    "measure": spec.key,
                    "num": None if num is None else float(num),
                    "den": None if den is None else float(den),
                    # Counts carry their value directly; rates deliberately store NULL here so
                    # there is no pre-divided number for a caller to SUM or AVG by mistake.
                    "value": None if spec.is_rate or num is None else float(num),
                    # No Wave 1 metric declares `gated_by`, so there is no coverage gate to
                    # record. Capacity (Wave 2) is where these columns start carrying values.
                    "coverage_num": None,
                    "coverage_den": None,
                }
            )
    return facts


def fetch_rows() -> list[dict]:
    """Build every Wave 1 fact row. One EDW round trip."""
    specs = _wave1_specs()
    grid = run_query(_grid_sql())
    return _fan_out(grid, specs)


def store_rows(rows: list[dict]) -> None:
    """refresh_service store override for the cube dataset.

    Mirrors `_store_efficiency_matrix`: the bulk goes to its own table, and a small summary goes to
    cache_store under the dataset key so `refresh_status` keeps reporting a refreshed_at for it.
    """
    fact_store.replace_all(rows)
    cache_store.save("mosaic_cube", {"row_count": len(rows), **fact_store.coverage_summary()})


# ---------------------------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------------------------

# A registry dimension -> how the cube answers it. The three entity dimensions select an
# entity_type and group by that type's own rows; `month` is the time axis and composes with any
# of them.
_ENTITY_DIMS = {"practice": "practice", "team": "team", "local_region": "local_region"}


def _months_between(period_from: str | None, period_to: str | None) -> list[str] | None:
    """The explicit list of month starts in a range, or None for "no period filter".

    An IN list rather than a BETWEEN because `fact_store._where` takes values, not ranges, and
    keeping it that way means every filter the cube can express is a bound parameter. With a
    24-month cube the list is at most 24 entries and hits the primary key's leading column.
    """
    if not period_from and not period_to:
        return None
    start = period_from or "1900-01-01"
    end = period_to or "2999-12-01"
    y, m = int(start[:4]), int(start[5:7])
    end_y, end_m = int(end[:4]), int(end[5:7])
    months: list[str] = []
    while (y, m) <= (end_y, end_m) and len(months) <= 240:
        months.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return months


def query(
    metrics: list[str],
    group_by: list[str] | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    limit: int | None = None,
) -> dict:
    """Answer a validated scope from the cube.

    `metrics` and `group_by` must already have passed `registry.validate_scope` - the route does
    that, so an illegal metric×dimension is refused by name with its supported alternatives before
    any SQL is built, rather than returning an empty grid the caller has to interpret.

    `entity_type` may also be 'radiologist', which the cube stores but `registry.DIMENSIONS` does
    not yet expose as a group-by dimension. That asymmetry is intentional: the rows are built now
    so Entity 360 has them, and a `radiologist` dimension is only added to the registry once there
    is a governed definition for rolling a rate up across a rad's many managing practices.
    """
    group_by = list(group_by or [])
    specs = [reg.get_metric(k) for k in metrics]
    unsupported = [s.key for s in specs if not s.composable]
    if unsupported:
        raise reg.UnsupportedDimensionError(
            f"not available from the cube: {', '.join(unsupported)} "
            "(computed in their own services, not composed from stored numerators)"
        )

    entity_dims = [d for d in group_by if d in _ENTITY_DIMS]
    if len(entity_dims) > 1:
        raise reg.UnsupportedDimensionError(
            f"cannot group by more than one entity dimension at once: {', '.join(entity_dims)}. "
            "The cube stores one entity per row; pick one and filter on the other."
        )

    # An explicit entity_type wins; otherwise the group-by picks it; otherwise enterprise.
    resolved_type = entity_type or (entity_dims[0] if entity_dims else "enterprise")

    filters: dict = {"grain": GRAIN, "entity_type": resolved_type}
    if entity_id:
        filters["entity_id"] = entity_id
    months = _months_between(period_from, period_to)
    if months is not None:
        filters["period_start"] = months

    cols: list[str] = []
    if "month" in group_by:
        cols.append("period_start")
    if entity_dims or entity_type:
        cols += ["entity_id", "entity_label"]

    rows = fact_store.rollup(
        measures=[s.key for s in specs],
        group_by=cols,
        filters=filters,
        limit=limit,
    )

    out = [_divide(r, reg.get_metric(r["measure"])) for r in rows]
    return {
        "scope": {
            "metrics": [s.key for s in specs],
            "group_by": group_by,
            "entity_type": resolved_type,
            "entity_id": entity_id,
            "period_from": period_from,
            "period_to": period_to,
        },
        "rows": out,
        "definitions": {s.key: reg.describe(s.key) for s in specs},
        "grain": GRAIN,
    }


def _divide(row: dict, spec) -> dict:
    """num/den -> value, with the registry's additive offset applied once, here and only here.

    `try_divide` semantics: a zero or missing denominator yields None rather than raising or
    silently reading as 0. A rate of "no data" and a rate of "zero percent" are different answers
    and the second one is the dangerous one to fabricate - the RASF slice that produced 158.7
    TBWU/min did so by dividing by an almost-empty denominator.
    """
    num = row.get("num")
    den = row.get("den")
    if spec.is_rate:
        value = None if not den or num is None else (num / den) + spec.offset
    else:
        value = None if num is None else num + spec.offset

    out = {
        "measure": spec.key,
        "label": spec.label,
        "solution": _solution_for(spec),
        "is_rate": spec.is_rate,
        "num": num,
        "den": den,
        "value": value,
        "fact_rows": row.get("fact_rows"),
    }
    for key in ("period_start", "entity_id", "entity_label"):
        if key in row:
            out[key] = row[key]
    cov_num, cov_den = row.get("coverage_num"), row.get("coverage_den")
    if cov_den:
        out["coverage_pct"] = (cov_num or 0.0) / cov_den
    return out


def status() -> dict:
    """What the cube currently holds, plus which metrics each wave is expected to cover."""
    summary = fact_store.coverage_summary()
    summary["wave_1_metrics"] = list(_WAVE1_KEYS)
    summary["lookback_months"] = LOOKBACK_MONTHS
    summary["registry_version"] = reg.REGISTRY_VERSION
    return summary
