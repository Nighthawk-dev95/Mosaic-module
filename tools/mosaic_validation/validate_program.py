"""Independent check of edw_test.enterprise_analytics.mosaic_program_metric_view (033) against the
app's own MVP logic (backend/app/data/mvp_dashboard_stats.py - the code behind the app's MVP page
and the Weekly Update PDF). validate_program.sql only proves the view equals plain SQL written by
the same author; this proves the view's SQL port of the funnel/impact/escalation rules agrees with
the separately-written Python, for each app scope (all / overview / mammo).

Usage:  python tools/mosaic_validation/validate_program.py --profile <databricks-profile>
Exit code 0 = every count matches.
"""

import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
MV = "edw_test.enterprise_analytics.mosaic_program_metric_view"
SRC = "edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding"

_spec = importlib.util.spec_from_file_location("mvp_stats", REPO / "backend/app/data/mvp_dashboard_stats.py")
stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stats)

STAGE_LABELS = {"Outreached": "1 Outreached", "Scheduled": "2 Scheduled", "Solutioning": "3 Solutioning",
                "Monitoring": "4 Monitoring", "Closed": "5 Closed"}
OUTCOME_LABELS = {"on_track": "On Track", "escalated": "Escalated", "declined": "Declined"}
IMPACT_LABELS = {"at_above_baseline": "At Or Above Baseline", "improving": "Improving",
                 "not_improving": "Not Improving", "insufficient_data": "Insufficient Data"}
# Program Track values that make up each app scope (scope_rows in mvp_dashboard_stats.py).
SCOPES = {"all": None, "overview": ("Core",), "mammo": ("Mammo",)}


def query(sql: str, profile: str) -> list[dict]:
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile],
        capture_output=True, text=True, check=True, shell=(sys.platform == "win32"),
    ).stdout
    return json.loads(out[out.index("["):])


def python_side(rows: list[dict], scope: str) -> dict:
    if scope != "all":
        rows = stats.scope_rows(rows, scope)
    result = {}
    for stage, outcomes in stats.compute_status_funnel(rows).items():
        for outcome, n in outcomes.items():
            result[("funnel", STAGE_LABELS[stage], OUTCOME_LABELS[outcome])] = n
    impact = stats.compute_impact_breakdown(rows)
    result[("impact", "post_engagement_rads", "")] = impact.pop("post_engagement_rads")
    for k, n in impact.items():
        result[("impact", IMPACT_LABELS[k], "")] = n
    for owner, n in stats.compute_escalations_by_owner(rows).items():
        result[("escalation_owner", owner, "")] = n
    return result


def view_side(profile: str, scope: str) -> dict:
    tracks = SCOPES[scope]
    where = "" if tracks is None else "WHERE `Program Track` IN (" + ",".join(f"'{t}'" for t in tracks) + ")"
    result = {}
    for r in query(f"SELECT `Funnel Stage` s, `Funnel Outcome` o, MEASURE(`Radiologists`) n FROM {MV} {where} "
                   f"GROUP BY ALL HAVING s IS NOT NULL", profile):
        result[("funnel", r["s"], r["o"])] = int(float(r["n"]))
    for r in query(f"SELECT MEASURE(`Post Engagement Radiologists`) n FROM {MV} {where}", profile):
        result[("impact", "post_engagement_rads", "")] = int(float(r["n"]))
    for r in query(f"SELECT `Impact Status` s, MEASURE(`Radiologists`) n FROM {MV} {where} "
                   f"GROUP BY ALL HAVING s IS NOT NULL", profile):
        result[("impact", r["s"], "")] = int(float(r["n"]))
    for r in query(f"SELECT `Escalation Owner` s, MEASURE(`Radiologists`) n FROM {MV} {where} "
                   f"GROUP BY ALL HAVING s IS NOT NULL", profile):
        result[("escalation_owner", r["s"], "")] = int(float(r["n"]))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    profile = ap.parse_args().profile

    rows = query(f"SELECT npi, mvp_cohort, optimization_support_status, drafting_captured_efficiency_change_pct, "
                 f"full_mosaic_change_l30d_pct FROM {SRC}", profile)
    print(f"source rows: {len(rows)}")

    failures = 0
    for scope in SCOPES:
        py, mv = python_side(rows, scope), view_side(profile, scope)
        print(f"\n== scope: {scope} ==")
        for key in sorted(set(py) | set(mv)):
            p, m = py.get(key, 0), mv.get(key, 0)
            flag = "" if p == m else "   <-- MISMATCH"
            failures += p != m
            print(f"  {' / '.join(x for x in key if x):55} app={p:5}  view={m:5}{flag}")
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
