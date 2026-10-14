"""EDW Mosaic Health - Agent 2: daily volume trend monitor.

Checks yesterday's total Mosaic-flagged exam count (the most recently fully-completed
day - deliberately not "today," which is always partial and would look artificially low;
same lesson learned from the undrafted-analysis partial-week issue this session) against
weekday-matched baselines: the same weekday last week, and the same weekday's average
over the trailing 4 weeks. A swing beyond +/-THRESHOLD_PCT on either marks the day
anomalous.

"vs day before" and a blended (all-weekdays) trailing average are reported for context
only and never trigger anomalous status - confirmed live on 2026-09-20 that both produce
a false positive every Fri->Sat/Sun transition purely from normal weekly seasonality
(volume is naturally lower on weekends), which is exactly the kind of noisy false alarm
this monitor should not raise. Comparing only against the same weekday avoids that.

Company-wide check first, by design (not every practice/radiologist/site individually
every day - too noisy). Only when the company-wide number is anomalous does this drill
into which practices/radiologists/sites are the largest contributors to the swing,
against whichever baseline had the single largest swing.

Uses presentation_mosaicdailyvolume_vw (this app's actual data source) rather than the
raw EDW fact tables, since this is meant to track what the app itself would show.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from _edw_connect import get_connection, run_query

REPORTS_DIR = Path(__file__).parent / "reports"
THRESHOLD_PCT = 20.0
TREND_WINDOW_DAYS = 28

DAILY_QUERY = """
SELECT CAST(Calendar_Date AS STRING) AS calendar_date,
  SUM(CASE WHEN Mosaic_flag = 1 THEN 1 ELSE 0 END) AS mosaic_ct
FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
WHERE Calendar_Date >= DATE_SUB(CURRENT_DATE(), 40)
GROUP BY Calendar_Date
"""


def _drilldown_query(dim_col: str, dim_alias: str, day1: str, day2: str) -> str:
    return f"""
    SELECT {dim_col} AS {dim_alias},
      SUM(CASE WHEN Calendar_Date = '{day1}' AND Mosaic_flag = 1 THEN 1 ELSE 0 END) AS day1_ct,
      SUM(CASE WHEN Calendar_Date = '{day2}' AND Mosaic_flag = 1 THEN 1 ELSE 0 END) AS day2_ct
    FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
    WHERE Calendar_Date IN ('{day1}', '{day2}')
    GROUP BY {dim_col}
    ORDER BY ABS(
      SUM(CASE WHEN Calendar_Date = '{day1}' AND Mosaic_flag = 1 THEN 1 ELSE 0 END)
      - SUM(CASE WHEN Calendar_Date = '{day2}' AND Mosaic_flag = 1 THEN 1 ELSE 0 END)
    ) DESC
    LIMIT 10
    """


def pct_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return round((current - baseline) / baseline * 100, 1)


def main() -> None:
    conn = get_connection()
    try:
        daily_rows = run_query(conn, DAILY_QUERY)
        by_date = {r["calendar_date"]: r["mosaic_ct"] for r in daily_rows}

        yesterday = date.today() - timedelta(days=1)
        day_before = yesterday - timedelta(days=1)
        last_week = yesterday - timedelta(days=7)
        same_weekday_weeks_back = [yesterday - timedelta(days=7 * n) for n in range(1, 5)]  # last 4 occurrences

        yesterday_ct = by_date.get(yesterday.isoformat(), 0)
        day_before_ct = by_date.get(day_before.isoformat(), 0)
        last_week_ct = by_date.get(last_week.isoformat(), 0)
        same_weekday_values = [by_date.get(d.isoformat(), 0) for d in same_weekday_weeks_back]
        same_weekday_avg = round(sum(same_weekday_values) / len(same_weekday_values), 1) if same_weekday_values else 0

        # Context only - never trigger anomalous status on these (see file header: both
        # produce a false positive every weekday/weekend transition).
        context = {
            "vs_day_before": {"baseline_date": day_before.isoformat(), "baseline_ct": day_before_ct,
                               "pct_change": pct_change(yesterday_ct, day_before_ct)},
        }

        # Trigger comparisons - both weekday-matched against yesterday.
        comparisons = {
            "vs_last_week_same_weekday": {"baseline_date": last_week.isoformat(), "baseline_ct": last_week_ct,
                                            "pct_change": pct_change(yesterday_ct, last_week_ct)},
            "vs_trailing_4week_same_weekday_avg": {"baseline_ct": same_weekday_avg,
                                        "pct_change": pct_change(yesterday_ct, same_weekday_avg)},
        }

        anomalous_keys = [
            k for k, v in comparisons.items()
            if v["pct_change"] is not None and abs(v["pct_change"]) >= THRESHOLD_PCT
        ]

        report: dict = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "yesterday": yesterday.isoformat(),
            "yesterday_mosaic_ct": yesterday_ct,
            "threshold_pct": THRESHOLD_PCT,
            "comparisons": comparisons,
            "context_only": context,
            "anomalous": bool(anomalous_keys),
            "anomalous_comparisons": anomalous_keys,
        }

        if anomalous_keys:
            worst_key = max(anomalous_keys, key=lambda k: abs(comparisons[k]["pct_change"]))
            baseline_date = comparisons[worst_key].get("baseline_date")
            if baseline_date is None:
                # trailing-average comparisons have no single baseline date to drill against -
                # fall back to the same-weekday-last-week date, which always exists.
                baseline_date = last_week.isoformat()
            drilldown = {}
            for dim_col, dim_alias, key in [
                ("local_practice_short_name", "practice", "by_practice"),
                ("Radiologist", "radiologist", "by_radiologist"),
                ("Location_Name", "site", "by_site"),
            ]:
                rows = run_query(conn, _drilldown_query(dim_col, dim_alias, yesterday.isoformat(), baseline_date))
                drilldown[key] = [
                    {dim_alias: r[dim_alias], "yesterday_ct": r["day1_ct"], "baseline_ct": r["day2_ct"],
                     "delta": r["day1_ct"] - r["day2_ct"]}
                    for r in rows
                ]
            report["drilldown_against"] = baseline_date
            report["drilldown"] = drilldown
    finally:
        conn.close()

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"volume_{yesterday.isoformat()}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
