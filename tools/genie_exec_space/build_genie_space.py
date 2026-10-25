"""Build the curated "Mosaic Executive" Genie space (Sandbox tier) for the exec dashboard.

Data assets are ONLY the governed metric views the exec dashboard reads, so every Genie answer
uses the same measure logic as the dashboard (and therefore PowerBI). No raw tables.

    python build_genie_space.py --check  --profile mosaic-app     # run every example SQL, no changes
    python build_genie_space.py --create --profile mosaic-oauth   # create the space (Sandbox folder)
    python build_genie_space.py --update --profile mosaic-oauth   # push changes to the id in space_id.txt

Governance (company 3-tier model): this is Tier 1 Sandbox -- personal Genie-Sandbox folder,
creator-only. Promotion to Candidate/Bronze is a separate, deliberate step.
"""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPACE_ID_FILE = os.path.join(HERE, "space_id.txt")
WAREHOUSE_ID = "fe0ad987563c672a"  # same warehouse as the exec dashboard
PARENT_PATH = "/Users/bhargav.narasimhan@radpartners.com/Genie-Sandbox"
TITLE = "Mosaic Executive (Sandbox)"
DESCRIPTION = ("Curated Q&A for the Mosaic Executive Dashboard: adoption, efficiency vs legacy VR, "
               "capacity & utilization, drafting coverage (why draftable exams are not drafted) and the "
               "MVP program. Same governed metric views as the dashboard and PowerBI.")

S = "edw_test.enterprise_analytics"
VOLUME, EFF, RP_AVG = f"{S}.mosaic_volume_metric_view", f"{S}.mosaic_efficiency_metric_view", \
    f"{S}.mosaic_efficiency_vs_rp_avg_metric_view"
CAP, PROGRAM, DRAFTABLE = f"{S}.mosaic_capacity_metric_view", f"{S}.mosaic_program_metric_view", \
    f"{S}.mosaic_draftable_metric_view"
TABLES = [VOLUME, EFF, RP_AVG, CAP, PROGRAM, DRAFTABLE]

LAST_MONTH = "add_months(date_trunc('MONTH', current_date()), -1)"
THIS_MONTH = "date_trunc('MONTH', current_date())"

INSTRUCTIONS = f"""\
This space answers executive questions about Mosaic, Radiology Partners' AI radiology platform, for the
CEO, President and leadership. It mirrors the Mosaic Executive Dashboard and the PowerBI reports.
Solutions: Reporting, AI Drafting, Capture. Metrics: adoption, efficiency vs legacy VR, read-time savings,
capacity, utilization, drafting coverage, MVP program.

TABLE -> DOMAIN
- Adoption / volume / % of RPCE exams: mosaic_volume_metric_view (date: `Final Date`, month: `Final Month`)
- Efficiency vs baseline (legacy VR), read-time savings: mosaic_efficiency_metric_view (month: `Exam Month`)
- Efficiency vs RP average (peer benchmark): mosaic_efficiency_vs_rp_avg_metric_view (month: `Exam Month`)
- Capacity & utilization: mosaic_capacity_metric_view (date: `Shift Date`, month: `Shift Month`)
- Drafting coverage -- why draftable exams were not drafted: mosaic_draftable_metric_view
  (date: `Calendar Date`, week: `Week Start`, month: `Month`)
- MVP program (Dynamics CRM onboarding/optimization): mosaic_program_metric_view

RULES -- these keep answers identical to the dashboard and PowerBI
1. All six assets are metric views. Always aggregate with MEASURE(`Measure Name`) and GROUP BY ALL. Never
   re-derive a percentage from counts, never SUM a percentage, never apply your own adjustments.
2. Never join the metric views to each other. Answer multi-domain questions with one query per view.
3. If no period is given, use the LAST COMPLETE MONTH, e.g. `Final Date` >= {LAST_MONTH} AND
   `Final Date` < {THIS_MONTH}. Say which month you used. The current month is partial.
4. Capacity and utilization: by default filter `Baseline Type` IN ('Exact','Proxy','Manual Review')
   (shifts with a matched baseline -- the PowerBI default). Only drop the filter if the user asks for all
   shifts, and then warn that capacity vs baseline is not meaningful without a baseline.
5. Efficiency: outlier exams are already excluded inside the view; do not filter for them.
6. "% of RPCE exams" measures (Pct RPCE Reporting / Drafting / Capture) already include the PowerBI
   +0.02 adjustment. Report them as returned.
7. Do not use `Allocated TBWU`.
8. Every `Pct ...` measure and every `... Pct Change Vs Baseline` / `... Utilization Pct` measure is a
   ratio between 0 and 1 (efficiency changes can be negative). Always present them to the user as
   percentages with one decimal (0.742 -> 74.2%). Show counts with thousands separators.
9. Filter Local Region with equality (`Local Region` = 'Apex'), not LIKE; the 6 values are exact.

TERMINOLOGY
- Provider Practice = `Team Rolled Up` (PowerBI "Team Rolled up"). Team = the finer `Team` column.
- Managing Practice = `Managing Practice` in the volume view and `Practice` in the efficiency and capacity
  views (PowerBI "Practice"). The draftable view has NO managing practice; use `Team Rolled Up` or
  `Local Region` there. `Local Practice` in the draftable view is a short site-group code, not Managing
  Practice.
- Local Region = one of 6 buckets: Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix.
- TBWU and RPWU are the same workload unit. RVU is a different (billing) unit.
- Baseline / legacy VR = the radiologist's own pre-Mosaic efficiency on legacy voice recognition.
- Efficiency % change = Mosaic efficiency vs that baseline (positive = more productive). Implied read
  time savings = the same comparison as time per exam (negative = less time per exam).
- Modes (efficiency measures prefix): Reporting, Drafting (restricted to CR/CT exams), Capture,
  Drafting Capture, Both, Full Mosaic (overall). Use Full Mosaic for "overall Mosaic efficiency".
- "Added capacity" = `On Shift Capacity Vs Baseline RPWU Per Hour`. Utilization = `On Shift Utilization Pct`
  (reading time / shift time). Trust checks: `Pct Exams With Valid Read Time`, `Pct Shifts With Baseline`.
- "Efficiency vs RP average" is 1.0 company-wide by construction; only quote it for a slice
  (region, practice, radiologist).

DRAFTABLE / UNDRAFTED (mosaic_draftable_metric_view)
- Draftable = Mosaic exams on drafting-eligible procedure codes. Each exam gets exactly one `Category`,
  first match wins, in `Category Sort Order`:
  0 Drafted; 1 RAD not enabled - Rad declined; 2 RAD not enabled - Ops declined;
  3 RAD not enabled - Incomplete process; 4 PRACTICE not enabled for model;
  5 DRAFT not available - Exam opened in <5 min; 6 DRAFT not available - Exam opened in >5 min;
  7 Exam never opened, not drafted.
- `Category Group`: Drafted | Radiologist not enabled (1-3) | Practice not enabled (4) |
  Enabled, draft not used (5-7).
- Every Pct measure here (Pct Drafted, Pct Rad Declined, Pct Rad Not Enabled, Pct Draft Not Used, ...)
  is a share of ALL draftable exams, Drafted included -- the PowerBI "Category % of Draftable".
  For "why weren't exams drafted", rank the undrafted categories by MEASURE(`Draftable Exam Count`)
  with `Is Drafted` = false, or use the Pct measures.
- Interpretation: opened >5 min = draft had time to arrive but was not used (adoption/workflow);
  opened <5 min = draft likely not ready yet (latency); incomplete process = enablement paperwork/
  onboarding not finished (biggest single lever).
- Data is a daily snapshot (7am CT) and covers completed weeks only; `Data Through Date` gives the
  last date. `Local Region` here uses PowerBI's drafting-page mapping, which places a few teams
  (RP Florida West, RAA, Lakefront Imaging) differently from the other views.

MVP PROGRAM (mosaic_program_metric_view)
- Snapshot of Dynamics CRM onboarding/optimization records; `Latest Dynamics Activity` is the as-of date.
- `Funnel Stage`: 1 Outreached, 2 Scheduled, 3 Solutioning, 4 Monitoring, 5 Closed.
  `Program Track`: Core, Mammo, Ops or Self Referred, Not In A Cohort.
- Efficiency-change figures (Median Full Mosaic L30D Change Pct) are entered by hand in Dynamics; say so.
- `Dynamics Practice` is free text from CRM, not the governed practice list.
"""

# (question, sql). Every SQL is executed by --check before the space is created/updated.
EXAMPLES = [
    ("What was Mosaic adoption last month?",
     f"""SELECT MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting,
       MEASURE(`Pct RPCE Drafting`) AS pct_rpce_drafting,
       MEASURE(`Pct RPCE Capture`) AS pct_rpce_capture,
       MEASURE(`Mosaic Exam Count`) AS mosaic_exams,
       MEASURE(`Mosaic Radiologist Count`) AS mosaic_radiologists
FROM {VOLUME}
WHERE `Final Date` >= {LAST_MONTH} AND `Final Date` < {THIS_MONTH}"""),
    ("Show the monthly trend of % RPCE exams read in Mosaic",
     f"""SELECT `Final Month`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting,
       MEASURE(`Pct RPCE Drafting`) AS pct_rpce_drafting
FROM {VOLUME}
WHERE `Final Month` >= add_months({THIS_MONTH}, -12) AND `Final Month` < {THIS_MONTH}
GROUP BY ALL ORDER BY `Final Month`"""),
    ("How much more efficient are radiologists on Mosaic than on legacy VR, by solution?",
     f"""SELECT MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS full_mosaic,
       MEASURE(`Reporting Pct Change Vs Baseline`) AS reporting,
       MEASURE(`Drafting Pct Change Vs Baseline`) AS drafting_cr_ct,
       MEASURE(`Capture Pct Change Vs Baseline`) AS capture,
       MEASURE(`Full Mosaic Implied Read Time Savings Pct`) AS read_time_change_per_exam
FROM {EFF}
WHERE `Exam Month` = {LAST_MONTH}"""),
    ("Efficiency vs baseline by local region last month",
     f"""SELECT `Local Region`, MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS eff_change,
       MEASURE(`Full Mosaic Mosaic Exams`) AS mosaic_exams
FROM {EFF}
WHERE `Exam Month` = {LAST_MONTH}
GROUP BY ALL ORDER BY eff_change DESC"""),
    ("Which provider practices are least efficient compared with the RP average?",
     f"""SELECT `Team Rolled Up` AS provider_practice,
       MEASURE(`Full Mosaic Efficiency Vs RP Avg`) AS eff_vs_rp_avg,
       MEASURE(`Full Mosaic Own Exams`) AS exams
FROM {RP_AVG}
WHERE `Exam Month` = {LAST_MONTH}
GROUP BY ALL HAVING exams >= 1000 ORDER BY eff_vs_rp_avg ASC LIMIT 10"""),
    ("What capacity did Mosaic add last month and what was utilization?",
     f"""SELECT MEASURE(`On Shift Capacity Vs Baseline RPWU Per Hour`) AS added_rpwu_per_hour,
       MEASURE(`On Shift Utilization Pct`) AS utilization,
       MEASURE(`Pct Exams With Valid Read Time`) AS pct_valid_read_time
FROM {CAP}
WHERE `Shift Date` >= {LAST_MONTH} AND `Shift Date` < {THIS_MONTH}
  AND `Baseline Type` IN ('Exact', 'Proxy', 'Manual Review')"""),
    ("Why weren't draftable exams drafted last month?",
     f"""SELECT `Category Sort Order`, `Category Group`, `Category`,
       MEASURE(`Draftable Exam Count`) AS exams,
       MEASURE(`Radiologist Count`) AS radiologists
FROM {DRAFTABLE}
WHERE `Calendar Date` >= {LAST_MONTH} AND `Calendar Date` < {THIS_MONTH}
GROUP BY ALL ORDER BY `Category Sort Order`"""),
    ("What share of draftable exams were drafted last month, and what share were lost to radiologist enablement vs drafts not used?",
     f"""SELECT MEASURE(`Draftable Exam Count`) AS draftable_exams,
       MEASURE(`Pct Drafted`) AS pct_drafted,
       MEASURE(`Pct Rad Not Enabled`) AS pct_rad_not_enabled,
       MEASURE(`Pct Practice Not Enabled`) AS pct_practice_not_enabled,
       MEASURE(`Pct Draft Not Used`) AS pct_draft_not_used
FROM {DRAFTABLE}
WHERE `Calendar Date` >= {LAST_MONTH} AND `Calendar Date` < {THIS_MONTH}"""),
    ("Which provider practices have the most undrafted exams?",
     f"""SELECT `Team Rolled Up` AS provider_practice,
       MEASURE(`Undrafted Exam Count`) AS undrafted_exams,
       MEASURE(`Pct Drafted`) AS pct_drafted,
       MEASURE(`Pct Rad Not Enabled`) AS pct_rad_not_enabled,
       MEASURE(`Pct Draft Not Used`) AS pct_draft_not_used
FROM {DRAFTABLE}
WHERE `Calendar Date` >= {LAST_MONTH} AND `Calendar Date` < {THIS_MONTH}
GROUP BY ALL ORDER BY undrafted_exams DESC LIMIT 10"""),
    ("Which radiologists most often open draftable exams after 5 minutes without using the draft?",
     f"""SELECT `Radiologist Name`, `NPI`, `Team Rolled Up`,
       MEASURE(`Opened Over 5 Min Exam Count`) AS opened_over_5_min,
       MEASURE(`Draftable Exam Count`) AS draftable_exams
FROM {DRAFTABLE}
WHERE `Calendar Date` >= {LAST_MONTH} AND `Calendar Date` < {THIS_MONTH}
GROUP BY ALL ORDER BY opened_over_5_min DESC LIMIT 20"""),
    ("Weekly trend of % drafted by drafting model",
     f"""SELECT `Week Start`, `Drafting Model`, MEASURE(`Pct Drafted`) AS pct_drafted
FROM {DRAFTABLE}
WHERE `Week Start` >= date_sub(current_date(), 91)
GROUP BY ALL ORDER BY `Week Start`, `Drafting Model`"""),
    ("Where does the MVP program stand?",
     f"""SELECT `Funnel Stage`, `Program Track`, MEASURE(`Radiologists`) AS radiologists
FROM {PROGRAM}
WHERE `Funnel Stage` IS NOT NULL
GROUP BY ALL ORDER BY `Funnel Stage`, `Program Track`"""),
]

SAMPLE_QUESTIONS = [
    "What was Mosaic adoption last month?",
    "How much more efficient are radiologists on Mosaic than on legacy VR, by solution?",
    "What capacity did Mosaic add last month and what was utilization?",
    "Why weren't draftable exams drafted last month?",
    "Which provider practices have the most undrafted exams?",
    "Where does the MVP program stand?",
]


def _id(*parts):
    """Stable 32-hex id so re-running --update does not churn ids."""
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _lines(text):
    rows = text.split("\n")
    return [r + "\n" for r in rows[:-1]] + [rows[-1]]


def serialized_space():
    examples = sorted(({"id": _id("ex", q), "question": [q], "sql": _lines(sql)} for q, sql in EXAMPLES),
                      key=lambda e: e["id"])
    samples = sorted(({"id": _id("sq", q), "question": [q]} for q in SAMPLE_QUESTIONS), key=lambda e: e["id"])
    return {
        "version": 2,
        "config": {"sample_questions": samples},
        "data_sources": {"tables": [{"identifier": t} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": _id("ti", "main"), "content": _lines(INSTRUCTIONS)}],
            "example_question_sqls": examples,
        },
    }


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(cmd[:4])}...\n{r.stdout}\n{r.stderr}")
    return r.stdout


def _body_file(body):
    """Request body goes via a file: the serialized space is too long/quote-heavy for a Windows command line."""
    path = os.path.join(tempfile.gettempdir(), "mosaic_exec_genie_body.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)
    return path


def check(profile):
    bad = 0
    for q, sql in EXAMPLES:
        out = run(["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile])
        rows = json.loads(out[out.find("["):]) if "[" in out else []
        ok = bool(rows) and any(v is not None for v in rows[0].values())
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {len(rows):>4} rows  {q}")
        if rows:
            print("        first row:", {k: v for k, v in list(rows[0].items())[:6]})
    if bad:
        sys.exit(f"{bad} example(s) returned no data")
    print("PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--create", action="store_true")
    g.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check(a.profile)
    payload = json.dumps(serialized_space())
    if a.create:
        if os.path.exists(SPACE_ID_FILE):
            sys.exit(f"space already exists ({open(SPACE_ID_FILE).read().strip()}); use --update")
        run(["databricks", "workspace", "mkdirs", PARENT_PATH, "--profile", a.profile])
        body = {"warehouse_id": WAREHOUSE_ID, "serialized_space": payload, "title": TITLE,
                "description": DESCRIPTION, "parent_path": PARENT_PATH}
        out = json.loads(run(["databricks", "genie", "create-space", "--json", "@" + _body_file(body),
                              "--profile", a.profile, "-o", "json"]))
        open(SPACE_ID_FILE, "w").write(out["space_id"])
        print("created", out["space_id"])
    else:
        sid = open(SPACE_ID_FILE).read().strip()
        body = {"serialized_space": payload, "title": TITLE, "description": DESCRIPTION,
                "warehouse_id": WAREHOUSE_ID}
        run(["databricks", "genie", "update-space", sid, "--json", "@" + _body_file(body), "--profile", a.profile])
        print("updated", sid)


if __name__ == "__main__":
    main()
