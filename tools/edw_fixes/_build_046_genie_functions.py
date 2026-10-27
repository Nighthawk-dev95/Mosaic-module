"""Generate 046_mosaic_eff_genie_functions.sql: UC SQL table functions over the exec dashboard's PBI-visual-logic
efficiency SQL (tools/lakeview_exec_dashboard/*.sql), so the curated Genie space answers practice / radiologist /
site / parent-exam efficiency and "vs average" questions with exactly the numbers the dashboard and PowerBI show.

The dashboard SQL files stay the single source: placeholders {START} / {END} / {MIN_EXAMS} / {FINAL} become the
function parameters and output level. Additive only -- new functions in edw_test.enterprise_analytics.

    python tools/edw_fixes/_build_046_genie_functions.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tools" / "lakeview_exec_dashboard"
OUT = Path(__file__).resolve().parent / "046_mosaic_eff_genie_functions.sql"
S = "edw_test.enterprise_analytics"

MODES = "Mode is one of: Full Mosaic, Reporting Only, Drafting Only, Capture Only, Drafting + Capture; filter on it."
PERIOD = ("start_date / end_date are inclusive exam dates as 'YYYY-MM-DD' strings (e.g. '2026-09-01', '2026-09-30' "
          "for September 2026); use complete months.")
PCT = "Pct Change Vs Baseline is a fraction (0.12 = +12%)."

FUNCS = [
    ("mosaic_eff_by_provider_practice", "provider_practice_efficiency.sql", "practice_rows", False,
     "Mosaic efficiency by Provider Practice (Team Rolled Up = the radiologist's home practice), exactly as the "
     "PowerBI Mosaic Efficiency 'By Provider Practice' table and the exec dashboard show it. One row per Mode x "
     "practice plus the table's 'Total' row. Use for practice breakdowns and rankings only; for overall / "
     "company-wide efficiency change use MEASURE(`Full Mosaic Pct Change Vs Baseline`) in "
     "mosaic_efficiency_metric_view instead. " + MODES + " " + PERIOD + " " + PCT),
    ("mosaic_eff_by_radiologist", "provider_practice_efficiency.sql", "radiologist_rows", False,
     "Mosaic efficiency by radiologist within Provider Practice (PowerBI 'By Provider Practice' radiologist level). "
     "Use for top / bottom radiologists or one radiologist's efficiency change. " + MODES + " " + PERIOD + " " + PCT),
    ("mosaic_eff_by_parent_exam", "provider_practice_efficiency.sql", "parent_exam_rows", False,
     "Mosaic efficiency by Provider Practice x radiologist x parent exam (PowerBI 'By Provider Practice' exam level). "
     + MODES + " " + PERIOD + " " + PCT),
    ("mosaic_eff_by_managing_practice", "managing_practice_efficiency.sql", "practice_rows", False,
     "Mosaic efficiency by Managing Practice (the exam site's practice, PowerBI 'Practice'), exactly as the PowerBI "
     "'By Managing Practice' table shows it, plus a 'Total' row. " + MODES + " " + PERIOD + " " + PCT),
    ("mosaic_eff_by_managing_site", "managing_practice_efficiency.sql", "site_rows", False,
     "Mosaic efficiency by Managing Practice x imaging site (PowerBI 'By Managing Practice' site level). "
     + MODES + " " + PERIOD + " " + PCT),
    ("mosaic_eff_vs_avg_benchmarks", "mosaic_eff_vs_avg.sql", "card_rows", True,
     "PowerBI 'Mosaic Efficiency vs Average' benchmark cards per Mode: qualifying radiologists, Pop Avg Efficiency, "
     "RP Avg Efficiency Overall and the shown-population benchmark. " + MODES + " " + PERIOD +
     " min_exams = PowerBI 'Min exams' slicer, default 100."),
    ("mosaic_eff_vs_avg_by_practice", "mosaic_eff_vs_avg.sql", "team_rows", True,
     "PowerBI 'Mosaic Efficiency vs Average' by Provider Practice: Mosaic Efficiency and Vs RP Avg "
     "(ratio, 1.05 = 5% above the radiologist-population average), plus a 'Total' row. " + MODES + " " + PERIOD +
     " min_exams default 100."),
    ("mosaic_eff_vs_avg_by_radiologist", "mosaic_eff_vs_avg.sql", "radiologist_rows", True,
     "PowerBI 'Mosaic Efficiency vs Average' by radiologist: Mosaic Efficiency, Vs RP Avg and Vs RP Avg "
     "Overall (ratios to the average). Use for 'which radiologists are above / below average'. " + MODES + " "
     + PERIOD + " min_exams default 100."),
]


def body(file, final, min_exams):
    lines = [l for l in (SRC / file).read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("--")]
    sql = "\n".join(lines).strip() + "\n"
    # SQL UDFs reject parameters inside aggregates (AGGREGATE_FUNCTION_MIXED_OUTER_LOCAL_REFERENCES). The date
    # window becomes a row-level flag `in_w` projected over the MV (a one-row parameter CTE cross-joined to the
    # MV ran 50x slower); min_exams enters via a one-row CTE `prm` joined only to the small radiologist-level CTEs.
    # Genie certified-answer functions reject DATE arguments, so the window arrives as 'YYYY-MM-DD' strings.
    sql = sql.replace("{START} AS `Window Start`, {END} AS `Window End`",
                      "DATE(start_date) AS `Window Start`, DATE(end_date) AS `Window End`")
    mv = f"FROM {S}." + {"provider_practice_efficiency.sql": "mosaic_eff_provider_leaf_modes_mv",
                          "managing_practice_efficiency.sql": "mosaic_eff_managing_site_modes_mv",
                          "mosaic_eff_vs_avg.sql": "mosaic_eff_vs_avg_daily_mv"}[file]
    sql = rep(sql, mv + "\n", "FROM (SELECT *, exam_date BETWEEN DATE(start_date) AND DATE(end_date) AS in_w " + mv + ")\n")
    sql = sql.replace("exam_date BETWEEN {START} AND {END}", "in_w")
    if min_exams:
        sql = rep(sql, "COALESCE(SUM(q), 0) >= {MIN_EXAMS} AS qualifies FROM leaf GROUP BY ALL",
                  "COALESCE(SUM(q), 0) >= MAX(p_min) AS qualifies FROM leaf CROSS JOIN prm GROUP BY mode, team, rad")
        sql = rep(sql, "FROM card_rad GROUP BY ALL", "FROM card_rad CROSS JOIN prm GROUP BY mode")
        sql = rep(sql, "FROM shown_rad GROUP BY ALL", "FROM shown_rad CROSS JOIN prm GROUP BY mode")
        sql = sql.replace("{MIN_EXAMS}", "p_min")
        sql = rep(sql, "WITH ", "WITH prm AS (SELECT min_exams AS p_min),\n", count=None)
    sql = sql.replace("{FINAL}", final)
    assert "{" not in sql, (file, final)
    return sql


def rep(sql, old, new, count=1):
    """Replace, asserting the anchor occurs exactly once (count=None: replace only the first occurrence)."""
    if count is None:
        assert sql.startswith(old), old
        return sql.replace(old, new, 1)
    assert sql.count(old) == count, (old, sql.count(old))
    return sql.replace(old, new)


def main():
    out = ["-- 046: UC SQL table functions for the curated exec Genie space (GENERATED by _build_046_genie_functions.py;",
           "-- edit the dashboard SQL in tools/lakeview_exec_dashboard/ and regenerate). edw_test only; these functions",
           "-- are owned by this generator (created 2026-10-26), so OR REPLACE re-syncs them. Nothing pre-existing is touched.",
           ""]
    for name, file, final, min_exams, comment in FUNCS:
        params = ["start_date STRING COMMENT 'First exam date of the window, YYYY-MM-DD (inclusive)'",
                  "end_date STRING COMMENT 'Last exam date of the window, YYYY-MM-DD (inclusive)'"]
        if min_exams:
            params.append("min_exams INT DEFAULT 100 COMMENT 'PowerBI Min exams slicer; default 100'")
        out += [f"CREATE OR REPLACE FUNCTION {S}.{name}(", "  " + ",\n  ".join(params), ")",
                "RETURNS TABLE", "COMMENT '" + comment.replace("'", "''") + "'",
                "RETURN", body(file, final, min_exams) + ";", ""]
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({len(FUNCS)} functions)")


if __name__ == "__main__":
    main()
