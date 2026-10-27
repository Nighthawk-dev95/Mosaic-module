"""The Mosaic cube: one pre-aggregated fact table that every governed metric rolls up from.

Modelled line-for-line on app/db/efficiency_store.py, for the same reason that module exists -
a real SQLite table with real columns and real indexes, so a filtered rollup runs as indexed SQL
instead of parsing a multi-hundred-megabyte JSON blob out of cache_store on every request.

Three rules are structural here, not conventions:

1. **Rates are stored as num/den, never pre-divided.** Every rollup is SUM(num)/SUM(den). This is
   `_scorecard_window_sql`'s "Fix 3" made impossible to get wrong: there is no per-row rate column
   for a caller to accidentally AVG(). `value` is populated only for counts (rows whose `den` is
   NULL); for a rate it stays NULL, so there is nothing pre-divided to sum by mistake.

2. **The division is left to the caller**, exactly as efficiency_store.decomposition_rows does.
   `rollup()` returns summed numerators and denominators. app/services/cube_service.py divides and
   applies the registry's `MetricSpec.offset` - an additive offset only re-aggregates correctly
   when applied once per grain *after* dividing, so it cannot live in a stored numerator.

3. **parent_practice and parent_team are separate columns.** The schema cannot represent the
   `MAX(practice) AS team` conflation that the Phase-1 fix removed from get_radiologist_scorecard.
   Team = the radiologist's home practice (provider_local_practice_name_curr), single-valued per
   rad. Practice = the site the exam was read at (managing_local_practice_name_curr), of which one
   rad can have dozens. At radiologist grain parent_practice is therefore NULL *on purpose* - it
   is not single-valued at that grain and writing any single value there would be a lie.

This module deliberately imports nothing from app.semantics: it is pure SQLite plus whitelists, so
it stays importable (and testable) under a bare Python with no dependencies installed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "mosaic_cache.sqlite3"

TABLE = "mosaic_fact"

# The physical column order, used by both CREATE TABLE and the named-parameter INSERT below.
_COLUMNS = [
    "period_start",     # ISO date of the period's first day; '' for the all-time row
    "grain",            # 'all' | 'month' | 'week'
    "solution",         # 'reporting' | 'drafting' | 'capture' | 'all'
    "entity_type",      # 'enterprise' | 'local_region' | 'practice' | 'team' | 'radiologist'
    "entity_id",
    "entity_label",
    "parent_practice",  # managing_local_practice_name_curr; NULL where not single-valued
    "parent_team",      # provider_local_practice_name_curr;  NULL where not single-valued
    "lifecycle_stage",  # go-live / MVP funnel stage; NULL until Wave 3 (Deployment) lands
    "measure",          # a registry metric key
    "num",
    "den",              # NULL => this measure is a count, not a rate
    "value",            # == num for counts; NULL for rates (see rule 1 above)
    "coverage_num",
    "coverage_den",
]

# Columns a caller may name in a GROUP BY or a WHERE. Same whitelist-or-raise discipline as
# efficiency_store._GROUP_COLS, for the same reason: these end up interpolated into SQL because
# SQLite cannot parameterise an identifier. Everything a caller can reach is listed here; the
# measure *values* are always bound as parameters, never interpolated.
_DIM_COLS = (
    "period_start",
    "grain",
    "solution",
    "entity_type",
    "entity_id",
    "entity_label",
    "parent_practice",
    "parent_team",
    "lifecycle_stage",
    "measure",
)


def _connect() -> sqlite3.Connection:
    # See app/db/cache_store.py for why WAL + busy_timeout matter here - this module,
    # cache_store.py and efficiency_store.py all write to the same underlying file from
    # independent connections, and a full cube rebuild is long enough to starve readers.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _check(col: str) -> str:
    if col not in _DIM_COLS:
        raise ValueError(f"unsupported cube column: {col} (known: {', '.join(_DIM_COLS)})")
    return col


# ---------------------------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------------------------


def replace_all(rows: list[dict]) -> None:
    """Rebuild the whole cube from `rows`. Called from refresh_service via a store override.

    Whole-table replace rather than an upsert because a partial write is the stale-snapshot
    failure class this project has already been bitten by: a cube half on yesterday's numbers
    and half on today's is internally consistent and wrong, which is the hardest kind to catch.
    """
    conn = _connect()
    try:
        conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {TABLE} (
                period_start    TEXT NOT NULL,
                grain           TEXT NOT NULL,
                solution        TEXT NOT NULL,
                entity_type     TEXT NOT NULL,
                entity_id       TEXT NOT NULL,
                entity_label    TEXT,
                parent_practice TEXT,
                parent_team     TEXT,
                lifecycle_stage TEXT,
                measure         TEXT NOT NULL,
                num             REAL,
                den             REAL,
                value           REAL,
                coverage_num    REAL,
                coverage_den    REAL,
                PRIMARY KEY (period_start, grain, solution, entity_type, entity_id, measure)
            )
            """
        )
        placeholders = ", ".join(f":{c}" for c in _COLUMNS)
        conn.executemany(
            f"INSERT INTO {TABLE} ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            [{c: row.get(c) for c in _COLUMNS} for row in rows],
        )
        # The PK already covers (period_start, grain, solution, entity_type, entity_id, measure)
        # left-to-right, which serves a period-scan. These cover the two shapes that start from
        # the other end: "this measure everywhere" and "this entity across time".
        conn.execute(f"CREATE INDEX idx_fact_measure ON {TABLE}(measure, entity_type, period_start)")
        conn.execute(f"CREATE INDEX idx_fact_entity ON {TABLE}(entity_type, entity_id, measure)")
        conn.execute(f"CREATE INDEX idx_fact_practice ON {TABLE}(parent_practice)")
        conn.execute(f"CREATE INDEX idx_fact_team ON {TABLE}(parent_team)")
        conn.commit()
    finally:
        conn.close()


def row_count() -> int:
    conn = _connect()
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {TABLE}")
        return int(cur.fetchone()[0])
    except sqlite3.OperationalError:
        return 0  # table not built yet - the cube refresh has not run in this process's lifetime
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------------------------


def _where(filters: dict | None) -> tuple[str, list]:
    """Build a parameterised WHERE from a {column: value-or-list} mapping.

    `None` as a value means IS NULL, and a list containing None mixes IN (...) with IS NULL -
    because `parent_practice <> 'X'` and `parent_practice = NULL` are both NULL (not true, not
    false) in SQLite, so a naive equality filter silently drops every unattributed row. Same
    footgun efficiency_store.decomposition_rows documents for its peer comparison.
    """
    if not filters:
        return "", []
    clauses: list[str] = []
    params: list = []
    for col, val in filters.items():
        _check(col)
        if val is None:
            clauses.append(f"{col} IS NULL")
        elif isinstance(val, (list, tuple, set)):
            vals = list(val)
            concrete = [v for v in vals if v is not None]
            parts = []
            if concrete:
                parts.append(f"{col} IN ({', '.join('?' for _ in concrete)})")
                params.extend(concrete)
            if len(concrete) != len(vals):
                parts.append(f"{col} IS NULL")
            if not parts:
                # An explicitly empty list means "nothing matches" - say so, rather than
                # emitting no clause at all and silently widening the query to everything.
                parts.append("1 = 0")
            clauses.append("(" + " OR ".join(parts) + ")")
        else:
            clauses.append(f"{col} = ?")
            params.append(val)
    return " WHERE " + " AND ".join(clauses), params


def rollup(
    measures: list[str],
    group_by: list[str] | None = None,
    filters: dict | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """SUM(num) / SUM(den) for each measure, grouped by whitelisted columns.

    Returns summed numerators and denominators - *not* a divided rate. The caller divides, and
    applies the registry's additive offset once, after the division. See rule 2 in the module
    docstring; the same discipline as efficiency_store.decomposition_rows.

    `measure` is always in the GROUP BY, so one call can roll up several metrics at once and the
    caller gets one row per (group, measure).
    """
    if not measures:
        raise ValueError("rollup() needs at least one measure")
    cols = [_check(c) for c in (group_by or [])]
    if "measure" not in cols:
        cols = cols + ["measure"]

    where_sql, params = _where({**(filters or {}), "measure": list(measures)})
    select_cols = ", ".join(cols)
    order_sql = ""
    if order_by:
        # Only a column we are already grouping by, or one of the three computed aggregates.
        allowed = set(cols) | {"num", "den", "coverage_num", "coverage_den"}
        key, _, direction = order_by.partition(" ")
        if key not in allowed or direction.upper() not in ("", "ASC", "DESC"):
            raise ValueError(f"unsupported order_by: {order_by} (allowed: {', '.join(sorted(allowed))})")
        order_sql = f" ORDER BY {key} {direction.upper() or 'ASC'}"
    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ?"
        params = params + [int(limit)]

    sql = (
        f"SELECT {select_cols}, "
        "SUM(num) AS num, SUM(den) AS den, "
        "SUM(coverage_num) AS coverage_num, SUM(coverage_den) AS coverage_den, "
        "COUNT(*) AS fact_rows "
        f"FROM {TABLE}{where_sql} GROUP BY {select_cols}{order_sql}{limit_sql}"
    )
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []  # cube not built yet; the route reports this as an empty, not an error
        raise
    finally:
        conn.close()


def distinct_values(column: str, filters: dict | None = None) -> list[str]:
    """Distinct non-null values of a whitelisted dimension, for populating filter controls."""
    col = _check(column)
    where_sql, params = _where(filters)
    joiner = " AND " if where_sql else " WHERE "
    sql = f"SELECT DISTINCT {col} FROM {TABLE}{where_sql}{joiner}{col} IS NOT NULL ORDER BY {col}"
    conn = _connect()
    try:
        return [r[0] for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    finally:
        conn.close()


def coverage_summary() -> dict:
    """What the cube currently holds, for /api/mosaic/cube/status and the refresh page.

    Deliberately cheap: counts and min/max over indexed columns only, so it can be called on
    every page load without competing with a refresh cycle for the write lock.
    """
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"""
            SELECT COUNT(*)                     AS rows,
                   COUNT(DISTINCT measure)      AS measures,
                   COUNT(DISTINCT entity_type)  AS entity_types,
                   MIN(NULLIF(period_start, '')) AS first_period,
                   MAX(period_start)            AS last_period
            FROM {TABLE}
            """
        ).fetchone()
        measures = [r[0] for r in conn.execute(f"SELECT DISTINCT measure FROM {TABLE} ORDER BY measure")]
        entity_types = [
            r[0] for r in conn.execute(f"SELECT DISTINCT entity_type FROM {TABLE} ORDER BY entity_type")
        ]
        return {**dict(row), "measure_keys": measures, "entity_type_keys": entity_types}
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return {
                "rows": 0,
                "measures": 0,
                "entity_types": 0,
                "first_period": None,
                "last_period": None,
                "measure_keys": [],
                "entity_type_keys": [],
            }
        raise
    finally:
        conn.close()
