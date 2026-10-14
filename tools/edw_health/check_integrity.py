"""EDW Mosaic Health - Agent 1: historical integrity monitor.

Catches a repeat of the exact bug this session spent days on: accessions already
tagged Mosaic_flag=1 (Msc_Rpt_Ind) silently getting reclassified later - e.g. the
2026-06-13 change where EDW's HL7-based classification pipeline resolved ~1.8M
previously-unclassified exams, and some of those turned out to be Powerscribe/Fluency
rows that were already (wrongly) flagged Mosaic. See memory: mosaic_flag_edw_investigation.

Mechanism: track two numbers per historical Calendar_Date - total Mosaic-flagged count,
and the "mismatch" count (flagged Mosaic but resolves to a non-Mosaic system per
Rpt_Sys_Nm_ID/generic_code_dim) - across the whole population since 2025-04-01. Compare
today's freshly-computed value for each date against what was recorded last run. A date
older than GRACE_PERIOD_DAYS should be fully settled by now; any change to its numbers
is the signal this monitor exists to catch. Recent dates (within the grace period) are
expected to shift slightly as late-arriving/backfilled data trickles in, so those are
tracked but not flagged.

Does not touch or fix anything - detect and report only, matching this app's other
watchers (tools/source_watch). A human decides what to do with a flagged date.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from _edw_connect import get_connection, run_query

MANIFEST_PATH = Path(__file__).parent / "integrity_manifest.json"
REPORTS_DIR = Path(__file__).parent / "reports"
GRACE_PERIOD_DAYS = 5
POPULATION_START = "2025-04-01"

# Materiality floor. Confirmed live on 2026-09-20: even dates 2+ months old still shift by
# 1-5 records run to run - routine late-arriving/backfilled data, observed as far back as
# 2026-04-03 (a delta of -1 on a base of ~52,316). The known real incident this monitor
# exists to catch (2026-06-13) moved counts by thousands per day, ~1.8M cumulatively - many
# orders of magnitude above this floor. A date is only flagged if it clears BOTH the
# absolute and relative bar, so a huge date isn't flagged by a tiny % move and a tiny date
# isn't flagged by a small absolute move that's actually a big relative swing for it.
MIN_ABSOLUTE_DELTA = 100
MIN_RELATIVE_DELTA_PCT = 1.0

QUERY = f"""
SELECT
  CAST(d.Calendar_Date AS STRING) AS calendar_date,
  COUNT(*) AS total_ct,
  SUM(CASE WHEN a.Msc_Rpt_Ind = 1 THEN 1 ELSE 0 END) AS total_mosaic_ct,
  SUM(CASE WHEN a.Msc_Rpt_Ind = 1 AND gc.Generic_Cd <> 'ORU_MSC' THEN 1 ELSE 0 END) AS mismatch_ct
FROM edw_prod.edw_gold.accum_exam_fact_vw a
JOIN edw_prod.bipa_analytics.date_dim d ON a.Final_Dt_ID = d.date_key
LEFT JOIN edw_prod.edw_gold.generic_code_dim gc ON gc.Generic_Cd_ID = a.Rpt_Sys_Nm_ID
WHERE d.Calendar_Date >= '{POPULATION_START}'
  AND a.SS_Nm IN ('rpceMidwest','rpceSouthwest')
  AND a.Exclusion_Reason_ID < 0
GROUP BY d.Calendar_Date
"""


def main() -> None:
    conn = get_connection()
    try:
        rows = run_query(conn, QUERY)
    finally:
        conn.close()

    fresh = {r["calendar_date"]: r for r in rows}
    previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}

    today = date.today()
    grace_cutoff = today - timedelta(days=GRACE_PERIOD_DAYS)

    flagged: list[dict] = []
    for cal_date, current in fresh.items():
        prior = previous.get(cal_date)
        if prior is None:
            continue  # first time seeing this date - nothing to compare against yet
        d = datetime.strptime(cal_date, "%Y-%m-%d").date()
        if d >= grace_cutoff:
            continue  # still within the normal late-arrival window, not suspicious yet
        def _material(now: int, was: int) -> bool:
            delta = abs(now - was)
            if delta < MIN_ABSOLUTE_DELTA:
                return False
            if was == 0:
                return True
            return (delta / was * 100) >= MIN_RELATIVE_DELTA_PCT

        if _material(current["total_mosaic_ct"], prior["total_mosaic_ct"]) or _material(current["mismatch_ct"], prior["mismatch_ct"]):
            flagged.append({
                "calendar_date": cal_date,
                "total_mosaic_ct_was": prior["total_mosaic_ct"],
                "total_mosaic_ct_now": current["total_mosaic_ct"],
                "mismatch_ct_was": prior["mismatch_ct"],
                "mismatch_ct_now": current["mismatch_ct"],
            })

    MANIFEST_PATH.write_text(json.dumps(fresh, indent=2), encoding="utf-8")

    report = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "dates_checked": len(fresh),
        "grace_period_days": GRACE_PERIOD_DAYS,
        "flagged_dates": sorted(flagged, key=lambda x: x["calendar_date"], reverse=True),
    }
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"integrity_{today.isoformat()}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
