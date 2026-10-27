"""Backup sync: Smartsheet "Managing Practice sites enabled per drafting model" sheet ->
edw_dev.enterprise_analytics.smartsheet_drafting_model_practice_sites.

This is the Track 2 (backup) path described in README.md - a direct Smartsheet REST API
pull, used because the native Lakeflow Connect Smartsheet connector (Track 1,
pipeline_create.json) is Beta and blocked on two admin-only one-time setup steps. Shaped
after tools/mosaic_version_pipeline/sync_exam_lookup.py: pull external data, stage a CSV in
a Databricks Volume, MERGE INTO the target table via the CLI's aitools query command - no
Spark cluster, no Databricks Job needed, same as that script.

Unlike sync_exam_lookup.py's additive MERGE, this one also runs WHEN NOT MATCHED BY SOURCE
THEN DELETE, so the table stays a faithful mirror of "currently enabled sites" - a sheet row
deleted in Smartsheet disappears here too. That matches Smartsheet's own full-refresh-only
semantics (no incremental sync exists in Smartsheet or in the native connector) and is still
done via MERGE, never DROP/CREATE OR REPLACE, so it stays consistent with this repo's
additive-only rule for pre-existing enterprise_analytics objects - this table is new and
solely owned by this script, nothing hand-authored ever writes to it.

Column handling: this script does NOT hardcode the sheet's column names. On every run it
reads whatever columns the sheet currently has from the Smartsheet API, snake_cases their
titles, and (on first run) generates a CREATE TABLE with one auto-generated COMMENT per
column recording the original Smartsheet title and declared type - a placeholder, not real
business documentation, since nobody has reviewed and written per-column semantics yet (see
README.md Status). If the sheet gains or loses a column, rerun with --apply; this script
only ever ADDs columns to the existing table (via ALTER TABLE ... ADD COLUMNS), it never
drops one a prior run already created, so historical data for a removed column is kept.

Setup required before first run - see README.md:
  1. SHEET_ID below (16-digit numeric Smartsheet sheet ID, not the share-link URL token).
  2. SMARTSHEET_API_TOKEN as a per-user Windows environment variable (setx), same pattern
     tools/edw_health/post_to_teams.py uses for TEAMS_WEBHOOK_URL.

Usage:
    python sync_drafting_model_practice_sites.py              # dry run: shows what would sync
    python sync_drafting_model_practice_sites.py --apply       # pulls, stages, and MERGEs
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SHEET_ID = "2580220413431684"

SMARTSHEET_API_BASE = "https://api.smartsheet.com/2.0"

# PATs lack the 'files' scope needed for volume uploads (same issue hit and documented in
# sync_exam_lookup.py) - use the full user OAuth login instead.
EDW_PROFILE = "mosaic-oauth"
TARGET_CATALOG = "edw_dev"
TARGET_SCHEMA = "enterprise_analytics"
TARGET_TABLE = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.smartsheet_drafting_model_practice_sites"
VOLUME_DIR = f"/Volumes/{TARGET_CATALOG}/{TARGET_SCHEMA}/smartsheet_staging"
STAGED_FILENAME = "smartsheet_drafting_model_practice_sites.csv"

ROW_ID_COL = "_smartsheet_row_id"
SYNCED_AT_COL = "_synced_at"

# Smartsheet cell type -> Delta type for the auto-generated DDL. Falls back to STRING for
# anything unmapped (TEXT_NUMBER's own sub-type varies per cell, so it's kept as STRING
# too rather than guessing INT vs DECIMAL - safer for a reference/config list than a wrong
# cast silently nulling a cell).
_SMARTSHEET_TYPE_TO_DELTA = {
    "DATE": "DATE",
    "DATETIME": "TIMESTAMP",
    "CHECKBOX": "BOOLEAN",
}


def _snake_case(title: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", title).strip("_").lower()
    return s or "unnamed_column"


def _run_cli(args: list[str]) -> str:
    result = subprocess.run(["databricks", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"databricks {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def _query_json(sql: str) -> list[dict]:
    out = _run_cli([
        "experimental", "aitools", "tools", "query",
        "--profile", EDW_PROFILE, "--output", "json", sql,
    ]).strip()
    if not out or "executed successfully" in out.lower():
        return []
    return json.loads(out)


def _get_api_token() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "SMARTSHEET_API_TOKEN")
            if value:
                return value
    except (ImportError, FileNotFoundError, OSError):
        pass
    import os
    token = os.environ.get("SMARTSHEET_API_TOKEN")
    if not token:
        raise RuntimeError(
            "SMARTSHEET_API_TOKEN is not set. Generate a personal API token in Smartsheet "
            "(Account -> Apps & Integrations -> API Access) and run: setx SMARTSHEET_API_TOKEN \"<token>\" "
            "- then open a fresh shell."
        )
    return token


def fetch_sheet() -> dict:
    if SHEET_ID.startswith("TODO"):
        raise RuntimeError("Fill in SHEET_ID at the top of this script first - see README.md.")
    token = _get_api_token()
    req = urllib.request.Request(
        f"{SMARTSHEET_API_BASE}/sheets/{SHEET_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def flatten_rows(sheet: dict) -> tuple[list[dict], list[dict]]:
    """Returns (column_defs, flattened_rows). column_defs: [{title, snake, sql_type}]."""
    columns = sheet.get("columns", [])
    col_by_id = {c["id"]: c for c in columns}
    column_defs = [
        {
            "title": c["title"],
            "snake": _snake_case(c["title"]),
            "sql_type": _SMARTSHEET_TYPE_TO_DELTA.get(c.get("type", ""), "STRING"),
        }
        for c in columns
    ]

    flattened = []
    for row in sheet.get("rows", []):
        values_by_col_id = {cell["columnId"]: cell for cell in row.get("cells", [])}
        out = {ROW_ID_COL: row["id"]}
        for col in columns:
            cell = values_by_col_id.get(col["id"], {})
            raw = cell.get("displayValue", cell.get("value"))
            out[_snake_case(col["title"])] = "" if raw is None else str(raw)
        flattened.append(out)
    return column_defs, flattened


def write_csv(column_defs: list[dict], rows: list[dict], out_path: Path) -> None:
    fieldnames = [ROW_ID_COL] + [c["snake"] for c in column_defs]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_volume_and_table(column_defs: list[dict], sheet_title: str) -> None:
    _query_json(f"CREATE VOLUME IF NOT EXISTS {TARGET_CATALOG}.{TARGET_SCHEMA}.smartsheet_staging "
                f"COMMENT 'Staging area for Smartsheet REST API pulls, e.g. sync_drafting_model_practice_sites.py.'")

    def _sql_quote(s: str) -> str:
        return s.replace("'", "''")

    col_lines = [f"  {ROW_ID_COL} BIGINT COMMENT 'Smartsheet internal row ID. Stable merge key across runs; NOT the visible row number, which can shift if rows are reordered.'"]
    for c in column_defs:
        title_escaped = _sql_quote(c["title"])
        col_lines.append(
            f"  {c['snake']} {c['sql_type']} COMMENT "
            f"'Raw Smartsheet column \"{title_escaped}\". "
            f"Auto-generated placeholder - no reviewed business-meaning documentation yet, see README.md Status.'"
        )
    col_lines.append(f"  {SYNCED_AT_COL} TIMESTAMP COMMENT 'When this row was last refreshed from the Smartsheet API by this script.'")

    sheet_title_escaped = _sql_quote(sheet_title)
    ddl = (
        f"CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (\n" + ",\n".join(col_lines) + "\n)\n"
        f"COMMENT 'Live mirror of the Smartsheet \"{sheet_title_escaped}\" sheet "
        f"(Managing Practice sites enabled per drafting model), synced via sync_drafting_model_practice_sites.py "
        f"(backup path for the Beta Lakeflow Connect Smartsheet connector - see README.md). Full-refresh mirror: "
        f"a row deleted in Smartsheet is deleted here too on the next sync. Additive-only schema evolution: new "
        f"Smartsheet columns are ADDed, never dropped, even if removed upstream.'"
    )
    _query_json(ddl)

    existing_cols = {c["col_name"] for c in _query_json(f"DESCRIBE TABLE {TARGET_TABLE}") if "col_name" in c}
    new_cols = [c for c in column_defs if c["snake"] not in existing_cols]
    if new_cols:
        add_lines = ", ".join(f"{c['snake']} {c['sql_type']}" for c in new_cols)
        _query_json(f"ALTER TABLE {TARGET_TABLE} ADD COLUMNS ({add_lines})")


def stage_and_merge(column_defs: list[dict], combined_path: Path) -> dict:
    volume_path = f"dbfs:{VOLUME_DIR}/{STAGED_FILENAME}"
    _run_cli(["fs", "cp", str(combined_path), volume_path, "--profile", EDW_PROFILE, "--overwrite"])

    snake_cols = [c["snake"] for c in column_defs]
    select_cols = ", ".join([ROW_ID_COL] + snake_cols)
    update_set = ",\n      ".join(f"target.{c} = source.{c}" for c in snake_cols) + f",\n      target.{SYNCED_AT_COL} = current_timestamp()"
    insert_cols = ", ".join([ROW_ID_COL] + snake_cols + [SYNCED_AT_COL])
    insert_vals = ", ".join([f"source.{ROW_ID_COL}"] + [f"source.{c}" for c in snake_cols] + ["current_timestamp()"])

    merge_sql = f"""
    MERGE INTO {TARGET_TABLE} AS target
    USING (
      SELECT {select_cols}
      FROM read_files('{VOLUME_DIR}/{STAGED_FILENAME}', format => 'csv', header => true)
    ) AS source
    ON target.{ROW_ID_COL} = source.{ROW_ID_COL}
    WHEN MATCHED THEN UPDATE SET
      {update_set}
    WHEN NOT MATCHED THEN INSERT ({insert_cols})
      VALUES ({insert_vals})
    WHEN NOT MATCHED BY SOURCE THEN DELETE
    """.strip()

    result = _query_json(merge_sql)
    return result[0] if result else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Run the full pull + merge (default: dry run)")
    args = parser.parse_args()

    sheet = fetch_sheet()
    column_defs, rows = flatten_rows(sheet)
    print(f"Sheet '{sheet.get('name')}': {len(column_defs)} columns, {len(rows)} rows.")
    for c in column_defs:
        print(f"  - {c['title']!r} -> {c['snake']} ({c['sql_type']})")

    if not args.apply:
        print("Dry run (pass --apply to execute).")
        return

    ensure_volume_and_table(column_defs, sheet.get("name", "unknown sheet"))

    with tempfile.TemporaryDirectory() as tmp:
        combined_path = Path(tmp) / STAGED_FILENAME
        write_csv(column_defs, rows, combined_path)
        print(f"Staging {len(rows)} rows and merging into {TARGET_TABLE}...")
        merge_result = stage_and_merge(column_defs, combined_path)
        print(f"Merge result: {merge_result}")


if __name__ == "__main__":
    sys.exit(main())
