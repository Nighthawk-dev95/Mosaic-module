"""A dedicated SQLite table (not the generic JSON cache_store) for the Efficiency matrix -
one row per (radiologist, practice, subspecialty, modality, parent procedure), ~780K rows at
full grain. Real columns + indexes so filtered aggregate queries (population efficiency for
whatever slice the user has selected) run as actual indexed SQL instead of parsing a huge
JSON array in Python on every request.
"""

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent.parent / "mosaic_cache.sqlite3"

_COLUMNS = [
    "npi", "radiologist_name", "practice", "subspecialty", "modality_code", "parent_procedure_name",
    "exam_category",
    "reporting_tbwu", "reporting_time", "reporting_baseline_contrib",
    "drafting_tbwu", "drafting_time", "drafting_baseline_contrib",
    "capture_tbwu", "capture_time", "capture_baseline_contrib",
]

# (mosaic tbwu column, mosaic time column, baseline contribution column) per mode.
# "full_mosaic" combines reporting + drafting, matching the source ETL's Is_Mosaic_Row
# (= Is_Reporting_Row OR Is_Drafting_Row).
_MODE_EXPRS = {
    "reporting": ("reporting_tbwu", "reporting_time", "reporting_baseline_contrib"),
    "drafting": ("drafting_tbwu", "drafting_time", "drafting_baseline_contrib"),
    "capture": ("capture_tbwu", "capture_time", "capture_baseline_contrib"),
    "full_mosaic": (
        "(reporting_tbwu + drafting_tbwu)",
        "(reporting_time + drafting_time)",
        "(reporting_baseline_contrib + drafting_baseline_contrib)",
    ),
}


def _connect() -> sqlite3.Connection:
    # See app/db/cache_store.py for why WAL + busy_timeout matter here - this module and
    # cache_store.py write to the same underlying file from independent connections, and
    # this one's writes (784K-row inserts) are long enough to otherwise starve readers.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def replace_all(rows: list[dict[str, Any]]) -> None:
    conn = _connect()
    try:
        conn.execute("DROP TABLE IF EXISTS efficiency_matrix")
        conn.execute(
            f"""
            CREATE TABLE efficiency_matrix (
                npi INTEGER, radiologist_name TEXT, practice TEXT, subspecialty TEXT,
                modality_code TEXT, parent_procedure_name TEXT, exam_category TEXT,
                reporting_tbwu REAL, reporting_time REAL, reporting_baseline_contrib REAL,
                drafting_tbwu REAL, drafting_time REAL, drafting_baseline_contrib REAL,
                capture_tbwu REAL, capture_time REAL, capture_baseline_contrib REAL
            )
            """
        )
        placeholders = ", ".join(f":{c}" for c in _COLUMNS)
        conn.executemany(f"INSERT INTO efficiency_matrix VALUES ({placeholders})", rows)
        for col in ("practice", "subspecialty", "modality_code", "parent_procedure_name", "exam_category", "npi"):
            conn.execute(f"CREATE INDEX idx_eff_{col} ON efficiency_matrix({col})")
        conn.commit()
    finally:
        conn.close()


def _rate(tbwu: float | None, time_sec: float | None) -> float | None:
    if not time_sec:
        return None
    return (tbwu or 0) / (time_sec / 60.0)


def _baseline_rate(baseline_contrib: float | None, time_sec: float | None) -> float | None:
    # baseline_contrib is already a per-minute value pre-multiplied by TotalTime (seconds) as
    # a weight, so dividing by SUM(TotalTime) directly (no /60) gives the correct time-weighted
    # average TBWU/min - see mosaic_service.get_efficiency_detail for the verified derivation.
    if not time_sec:
        return None
    return (baseline_contrib or 0) / time_sec


def aggregate(
    mode: str = "full_mosaic",
    practice: str | None = None,
    subspecialty: str | None = None,
    modality_code: str | None = None,
    parent_procedure_name: str | None = None,
    exam_category: str | None = None,
) -> dict[str, float | None]:
    tbwu_expr, time_expr, baseline_expr = _MODE_EXPRS.get(mode, _MODE_EXPRS["full_mosaic"])

    where_clauses = []
    params: list[str] = []
    if practice:
        where_clauses.append("practice = ?")
        params.append(practice)
    if subspecialty:
        where_clauses.append("subspecialty = ?")
        params.append(subspecialty)
    if modality_code:
        where_clauses.append("modality_code = ?")
        params.append(modality_code)
    if parent_procedure_name:
        where_clauses.append("parent_procedure_name = ?")
        params.append(parent_procedure_name)
    if exam_category:
        where_clauses.append("exam_category = ?")
        params.append(exam_category)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    conn = _connect()
    try:
        row = conn.execute(
            f"""
            SELECT SUM({tbwu_expr}) AS tbwu, SUM({time_expr}) AS time_sec, SUM({baseline_expr}) AS baseline_contrib
            FROM efficiency_matrix
            {where_sql}
            """,
            params,
        ).fetchone()
    finally:
        conn.close()

    tbwu, time_sec, baseline_contrib = row if row else (None, None, None)
    return {
        "mosaic_tbwu_per_min": _rate(tbwu, time_sec),
        "baseline_tbwu_per_min": _baseline_rate(baseline_contrib, time_sec),
    }


def rollup_by(group_col: str, mode: str = "full_mosaic") -> list[dict[str, Any]]:
    """GROUP BY npi (+radiologist_name/practice/subspecialty) or practice, for the table view."""
    tbwu_expr, time_expr, baseline_expr = _MODE_EXPRS.get(mode, _MODE_EXPRS["full_mosaic"])
    conn = _connect()
    try:
        if group_col == "npi":
            rows = conn.execute(
                f"""
                SELECT npi, MAX(radiologist_name) AS radiologist_name, MAX(practice) AS practice,
                       MAX(subspecialty) AS subspecialty,
                       SUM({tbwu_expr}) AS tbwu, SUM({time_expr}) AS time_sec, SUM({baseline_expr}) AS baseline_contrib
                FROM efficiency_matrix
                GROUP BY npi
                """
            ).fetchall()
            cols = ["npi", "radiologist_name", "practice", "subspecialty", "tbwu", "time_sec", "baseline_contrib"]
        else:
            rows = conn.execute(
                f"""
                SELECT practice,
                       SUM({tbwu_expr}) AS tbwu, SUM({time_expr}) AS time_sec, SUM({baseline_expr}) AS baseline_contrib
                FROM efficiency_matrix
                WHERE practice IS NOT NULL
                GROUP BY practice
                ORDER BY practice
                """
            ).fetchall()
            cols = ["practice", "tbwu", "time_sec", "baseline_contrib"]
    finally:
        conn.close()

    results = []
    for row in rows:
        d = dict(zip(cols, row))
        d["mosaic_tbwu_per_min"] = _rate(d["tbwu"], d["time_sec"])
        d["baseline_tbwu_per_min"] = _baseline_rate(d["baseline_contrib"], d["time_sec"])
        results.append(d)
    return results


def distinct_values(column: str) -> list[str]:
    if column not in ("practice", "subspecialty", "modality_code", "parent_procedure_name", "exam_category"):
        raise ValueError(f"unsupported column: {column}")
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM efficiency_matrix WHERE {column} IS NOT NULL ORDER BY {column}"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]
