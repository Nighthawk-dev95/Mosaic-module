"""Automated incremental sync: AWS prod app logs -> edw_prod.enterprise_analytics.mosaic_version_exam_lookup.

Replaces the manual day-chunked export process used to build and refresh this table
(originally run by hand on 2026-10-19 through 2026-10-21: a bash loop querying the AWS
workspace one day at a time, combining CSVs, staging them in a volume, then loading).
This script does the same thing end to end, incrementally, so it can run unattended.

Pipeline:
  1. Find the last fully-loaded day: MAX(log_date) in the target table.
  2. Pull every day from (that day + 1) through yesterday (the most recent FULLY
     COMPLETED day - never today, which is always partial; this exact mistake was
     diagnosed and fixed by hand for Oct 19-21 before this script existed).
  3. For each day, query the AWS-hosted source table
     (p_use1_rp_aws_dbx_workspace01.support.prod_app_logs_silver_mosaicinfohub, profile
     aws-dbx-workspace01) for 'Report has been signed' events carrying a radpair_instance
     tag, dedup to one row per accession_number (latest event wins), and classify
     mosaic_version from instance ('rp-mg' -> Mosaic 2.0, else Mosaic 1.0).
  4. Combine the day-CSVs, stage them in the existing
     edw_prod.enterprise_analytics.mosaic_version_staging volume (profile mosaic-app).
  5. MERGE INTO the target table, keyed on accession_number, only updating a matched
     row when the new data is at least as recent (log_date >=) - makes reruns and
     any day's reprocessing safe. This is additive-only: no CREATE OR REPLACE, no
     INSERT OVERWRITE, no DROP, per this repo's hard rule for enterprise_analytics.

Usage:
    python sync_exam_lookup.py              # dry run: shows the day range, pulls nothing
    python sync_exam_lookup.py --apply       # runs the full pull + merge
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

AWS_PROFILE = "aws-dbx-workspace01"
# mosaic-app's PAT lacks the 'files' scope needed for fs cp/volume uploads (confirmed
# 2026-10-22) - using the full user OAuth login instead, which has it.
EDW_PROFILE = "mosaic-oauth"
SOURCE_TABLE = "p_use1_rp_aws_dbx_workspace01.support.prod_app_logs_silver_mosaicinfohub"
TARGET_TABLE = "edw_prod.enterprise_analytics.mosaic_version_exam_lookup"
VOLUME_DIR = "/Volumes/edw_prod/enterprise_analytics/mosaic_version_staging"
STAGED_FILENAME = "mosaic_version_exam_lookup_incremental.csv"

# A day pulled same-day (or the next morning, before all its log events have landed)
# undercounts - confirmed 2026-10-22: re-pulling 2026-10-21 found 91,177 rows for that
# day vs. 23,961 already loaded. Always re-pull the last N loaded days along with any
# new ones so a previously-partial day tops itself up automatically; the MERGE's
# `log_date >=` guard makes re-pulling an already-complete day a safe no-op.
REFRESH_LOOKBACK_DAYS = 2


def _run_cli(args: list[str]) -> str:
    result = subprocess.run(
        ["databricks", *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"databricks {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def _query_json(sql: str, profile: str) -> list[dict]:
    out = _run_cli(["experimental", "aitools", "tools", "query", "--profile", profile, "--output", "json", sql]).strip()
    if not out or "executed successfully" in out.lower():
        return []
    return json.loads(out)


def get_last_loaded_date() -> date:
    rows = _query_json(f"SELECT MAX(log_date) as max_log_date FROM {TARGET_TABLE}", EDW_PROFILE)
    raw = rows[0]["max_log_date"]
    return datetime.strptime(raw, "%Y-%m-%d").date()


def day_extraction_query(d: date) -> str:
    d_str = d.isoformat()
    return f"""
    WITH parsed AS (
      SELECT
        accession_number,
        date as log_date,
        regexp_extract(message, 'radpair_instance\\\\":\\\\"([^\\\\"]*)', 1) as instance,
        regexp_extract(message, '\\\\"NPI\\\\":\\\\"([^\\\\"]*)', 1) as npi,
        regexp_extract(message, 'modality\\\\":\\\\"([^\\\\"]*)', 1) as modality
      FROM {SOURCE_TABLE}
      WHERE date = DATE'{d_str}'
        AND message LIKE 'Report has been signed%' AND message LIKE '%radpair_instance%'
        AND regexp_extract(message, 'radpair_instance\\\\":\\\\"([^\\\\"]*)', 1) IN ('rp-mg','rp-prod')
    ),
    dedup AS (
      SELECT accession_number, max(log_date) as log_date, max_by(npi, log_date) as npi,
             max_by(modality, log_date) as modality, max_by(instance, log_date) as instance
      FROM parsed GROUP BY accession_number
    )
    SELECT
      accession_number,
      CASE WHEN instance = 'rp-mg' THEN 'Mosaic 2.0' ELSE 'Mosaic 1.0' END as mosaic_version,
      npi, modality,
      CASE WHEN modality = 'MG' THEN 'MG' ELSE 'Non-MG' END as modality_group,
      log_date
    FROM dedup
    """.strip()


def pull_day(d: date, out_dir: Path) -> Path:
    out_path = out_dir / f"part_{d.isoformat()}.csv"
    sql = day_extraction_query(d)
    csv_text = _run_cli(["experimental", "aitools", "tools", "query", "--profile", AWS_PROFILE, "--output", "csv", sql])
    out_path.write_text(csv_text, encoding="utf-8")
    return out_path


def combine_csvs(day_files: list[Path], combined_path: Path) -> int:
    row_count = 0
    with combined_path.open("w", encoding="utf-8", newline="") as out:
        for i, f in enumerate(day_files):
            lines = f.read_text(encoding="utf-8").splitlines()
            if not lines:
                continue
            if i == 0:
                out.write(lines[0] + "\n")
            out.writelines(line + "\n" for line in lines[1:])
            row_count += max(0, len(lines) - 1)
    return row_count


def stage_and_merge(combined_path: Path) -> dict:
    volume_path = f"dbfs:{VOLUME_DIR}/{STAGED_FILENAME}"
    _run_cli(["fs", "cp", str(combined_path), volume_path, "--profile", EDW_PROFILE, "--overwrite"])

    merge_sql = f"""
    MERGE INTO {TARGET_TABLE} AS target
    USING (
      SELECT accession_number, mosaic_version, npi, modality, modality_group, log_date
      FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY accession_number ORDER BY log_date DESC) as rn
        FROM read_files('{VOLUME_DIR}/{STAGED_FILENAME}', format => 'csv', header => true)
      ) WHERE rn = 1
    ) AS source
    ON target.accession_number = source.accession_number
    WHEN MATCHED AND source.log_date >= target.log_date THEN UPDATE SET
      target.mosaic_version = source.mosaic_version,
      target.npi = source.npi,
      target.modality = source.modality,
      target.modality_group = source.modality_group,
      target.log_date = source.log_date
    WHEN NOT MATCHED THEN INSERT (accession_number, mosaic_version, npi, modality, modality_group, log_date)
      VALUES (source.accession_number, source.mosaic_version, source.npi, source.modality, source.modality_group, source.log_date)
    """.strip()

    result = _query_json(merge_sql, EDW_PROFILE)
    return result[0] if result else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Run the full pull + merge (default: dry run)")
    args = parser.parse_args()

    last_loaded = get_last_loaded_date()
    yesterday = date.today() - timedelta(days=1)
    start = last_loaded - timedelta(days=REFRESH_LOOKBACK_DAYS - 1)

    if start > yesterday:
        print(f"Up to date: last loaded day is {last_loaded}, nothing new through {yesterday}.")
        return

    days = []
    d = start
    while d <= yesterday:
        days.append(d)
        d += timedelta(days=1)

    print(f"Last loaded day: {last_loaded}. Pulling {len(days)} day(s) "
          f"(including {REFRESH_LOOKBACK_DAYS} day(s) of refresh lookback): {days[0]} .. {days[-1]}.")

    if not args.apply:
        print("Dry run (pass --apply to execute).")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        day_files = []
        for d in days:
            out_path = pull_day(d, tmp_dir)
            rows = max(0, len(out_path.read_text(encoding="utf-8").splitlines()) - 1)
            print(f"  {d}: {rows} rows")
            day_files.append(out_path)

        combined_path = tmp_dir / STAGED_FILENAME
        total_rows = combine_csvs(day_files, combined_path)
        print(f"Combined {total_rows} rows across {len(days)} day(s). Staging and merging...")

        merge_result = stage_and_merge(combined_path)
        print(f"Merge result: {merge_result}")


if __name__ == "__main__":
    sys.exit(main())
