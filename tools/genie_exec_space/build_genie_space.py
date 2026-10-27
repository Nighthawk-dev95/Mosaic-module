"""Build the curated "Mosaic Executive" Genie space (Sandbox tier) for the exec dashboard.

Data assets are ONLY the governed metric views the exec dashboard reads, so every Genie answer
uses the same measure logic as the dashboard (and therefore PowerBI). No raw tables. Practice / radiologist /
site / vs-average efficiency comes from the UC table functions in tools/edw_fixes/046 (dashboard SQL verbatim).

    python build_genie_space.py --check  --profile mosaic-app     # run every example SQL, no changes
    python build_genie_space.py --create --profile mosaic-oauth   # create the space (Sandbox folder)
    python build_genie_space.py --update --profile mosaic-oauth   # push changes to the id in space_id.txt

Governance (Genie Space Best Practices & Certification Guide, Oct 2026): lifecycle stage Development --
[DEV] title prefix, author-only (CAN MANAGE). Peer reviewers get CAN EDIT and the prefix becomes [TEST];
only after Genie Governance approval does EDW apply the Certified tag and the audience get CAN RUN.
Checklist status: CERTIFICATION_CHECKLIST.md.
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
TITLE = "[DEV] Mosaic Executive"  # [DEV] -> [TEST] at peer review -> no prefix once certified
DESCRIPTION = ("Curated Q&A for the Mosaic Executive Dashboard: adoption, efficiency vs legacy VR, "
               "capacity & utilization, drafting coverage (why draftable exams are not drafted) and the "
               "MVP program. Same governed metric views as the dashboard and PowerBI.")

S = "edw_test.enterprise_analytics"
VOLUME, EFF, RP_AVG = f"{S}.mosaic_volume_metric_view", f"{S}.mosaic_efficiency_metric_view", \
    f"{S}.mosaic_efficiency_vs_rp_avg_metric_view"
CAP, PROGRAM, DRAFTABLE = f"{S}.mosaic_capacity_pbi_metric_view", f"{S}.mosaic_program_metric_view", \
    f"{S}.mosaic_draftable_metric_view"
TABLES = [VOLUME, EFF, RP_AVG, CAP, PROGRAM, DRAFTABLE]

# UC table functions (tools/edw_fixes/046) = the dashboard's PowerBI-visual-logic efficiency tables.
FN_PP, FN_RAD, FN_EXAM = f"{S}.mosaic_eff_by_provider_practice", f"{S}.mosaic_eff_by_radiologist", \
    f"{S}.mosaic_eff_by_parent_exam"
FN_MP, FN_SITE = f"{S}.mosaic_eff_by_managing_practice", f"{S}.mosaic_eff_by_managing_site"
FN_AVG_CARDS, FN_AVG_PP, FN_AVG_RAD = f"{S}.mosaic_eff_vs_avg_benchmarks", f"{S}.mosaic_eff_vs_avg_by_practice", \
    f"{S}.mosaic_eff_vs_avg_by_radiologist"
FUNCTIONS = [FN_PP, FN_RAD, FN_EXAM, FN_MP, FN_SITE, FN_AVG_CARDS, FN_AVG_PP, FN_AVG_RAD]

LAST_MONTH = "add_months(date_trunc('MONTH', current_date()), -1)"
THIS_MONTH = "date_trunc('MONTH', current_date())"
# Last complete month as DATE arguments for the efficiency functions.
# Genie certified-answer functions take the window as 'YYYY-MM-DD' strings (DATE arguments are rejected).
LM_WINDOW = ("date_format(add_months(current_date(), -1), 'yyyy-MM-01'), "
             "date_format(last_day(add_months(current_date(), -1)), 'yyyy-MM-dd')")
SEP_WINDOW = "'2026-09-01', '2026-09-30'"

INSTRUCTIONS = f"""\
This space answers executive questions about Mosaic, Radiology Partners' AI radiology platform, for the
CEO, President and leadership. It mirrors the Mosaic Executive Dashboard and the PowerBI reports.
Solutions: Reporting, AI Drafting, Capture. Metrics: adoption, efficiency vs legacy VR, read-time savings,
capacity, utilization, drafting coverage, MVP program.

TABLE -> DOMAIN
- Adoption / volume / % of RPCE exams: mosaic_volume_metric_view (date: `Final Date`, month: `Final Month`)
- Efficiency vs baseline (legacy VR), read-time savings: mosaic_efficiency_metric_view (month: `Exam Month`)
- Efficiency vs RP average (peer benchmark): mosaic_efficiency_vs_rp_avg_metric_view (month: `Exam Month`)
- Capacity & utilization: mosaic_capacity_pbi_metric_view (date: `Shift Date`, month: `Month`)
- Drafting coverage -- why draftable exams were not drafted: mosaic_draftable_metric_view
  (date: `Calendar Date`, week: `Week Start`, month: `Month`)
- MVP program (Dynamics CRM onboarding/optimization): mosaic_program_metric_view

RULES -- these keep answers identical to the dashboard and PowerBI
1. All six assets are metric views. Always aggregate with MEASURE(`Measure Name`) and GROUP BY ALL. Never
   re-derive a percentage from counts, never SUM a percentage, never apply your own adjustments.
2. Never join the metric views to each other. Answer multi-domain questions with one query per view.
3. If no period is given, use the LAST COMPLETE MONTH, e.g. `Final Date` >= {LAST_MONTH} AND
   `Final Date` < {THIS_MONTH}. Say which month you used. The current month is partial.
4. Capacity and utilization: the view already applies the PowerBI Practice Summary defaults (TBWU 26 per
   shift, shifts with baselines, report shift-length filter); do not filter `Baseline Type`. To match
   PowerBI, keep only practice-months that have a TBWU 26 baseline: when grouping by `Local Practice` add
   HAVING MEASURE(`Has TBWU26 Baseline`) = 1; for totals or other groupings first select the qualifying
   (`Local Practice`, `Month`) pairs in a CTE and filter on them (see the capacity examples). This applies
   to EVERY capacity measure, company totals included (`Pct Mosaic`, `Pct Mosaic Drafting`, `New Utilization`,
   `Pct Addl Capacity`, ...); skipping it changes the answer by ~1 point.
5. Efficiency: outlier exams are already excluded inside the view; do not filter for them.
6. "% of RPCE exams" measures (Pct RPCE Reporting / Drafting / Capture) already include the PowerBI
   +0.02 adjustment. Report them as returned.
7. Do not use `Allocated TBWU`.
8. Every `Pct ...` measure and every `... Pct Change Vs Baseline` / `... Utilization Pct` measure is a
   ratio between 0 and 1 (efficiency changes can be negative). Always present them to the user as
   percentages with one decimal (0.742 -> 74.2%). Show counts with thousands separators.
9. Filter Local Region with equality (`Local Region` = 'Apex'), not LIKE; the 6 values are exact.
10. 'Matrix' is BOTH a Local Region and a Provider Practice (different populations). If the user says
   "region", use `Local Region`; otherwise treat "Matrix" / "Matrix's" as the Provider Practice. Always
   state which one you used and that the other exists.

TERMINOLOGY
- Provider Practice = `Team Rolled Up` (PowerBI "Team Rolled up"). Team = the finer `Team` column.
- Managing Practice = `Managing Practice` in the volume view, `Practice` in the efficiency view and
  `Local Practice` in the capacity view (PowerBI "Practice"). The draftable view has NO managing practice; use `Team Rolled Up` or
  `Local Region` there. `Local Practice` in the draftable view is a short site-group code, not Managing
  Practice.
- Local Region = one of 6 buckets: Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix.
- TBWU and RPWU are the same workload unit. RVU is a different (billing) unit.
- Baseline / legacy VR = the radiologist's own pre-Mosaic efficiency on legacy voice recognition.
- Efficiency % change = Mosaic efficiency vs that baseline (positive = more productive). Implied read
  time savings = the same comparison as time per exam (negative = less time per exam).
- Modes (efficiency measures prefix): Reporting, Drafting (restricted to CR/CT exams), Capture,
  Drafting Capture, Both, Full Mosaic (overall). Use Full Mosaic for "overall Mosaic efficiency".
- Capacity is per shift in TBWU 26. `Average Baseline` = pre-Mosaic workload per shift, `New Capacity` =
  workload per shift with Mosaic, `Addl Capacity Per Shift` = the difference, "added capacity" / "% add'l
  capacity" = `Pct Addl Capacity`. `New Utilization` = reading time / shift time (0-1). `Pct Mosaic` /
  `Pct Mosaic Drafting` = share of on-shift cases read / drafted in Mosaic. `New Efficiency` is a raw
  per-shift efficiency ratio (show 3 decimals, not a %). `Selected Shift Count` = shifts in scope.
- "Efficiency vs RP average" is 1.0 company-wide by construction; only quote it for a slice
  (region, practice, radiologist).
- Radiologist names are "Last, First M" (e.g. 'Taha, Manuel R'). When the user gives a partial name,
  match with ILIKE '%taha%' and say which radiologist(s) matched.

EFFICIENCY BY PRACTICE / RADIOLOGIST / SITE -- use the efficiency FUNCTIONS
The PowerBI efficiency tables (and the dashboard's By Provider Practice, By Managing Practice and
Mosaic Efficiency vs Average tables) apply visual-level filters that the metric view cannot express.
For any efficiency question broken down by Provider Practice, Radiologist, Parent Exam, Managing
Practice or Site, or for "vs average" rankings, call these table functions instead of the metric views:
- {FN_PP}(start_date, end_date): one row per Mode x `Provider Practice` (+ 'Total')
- {FN_RAD}(start_date, end_date): per Mode x `Provider Practice` x `Radiologist`
- {FN_EXAM}(start_date, end_date): per Mode x Provider Practice x Radiologist x `Parent Exam`
- {FN_MP}(start_date, end_date): per Mode x `Managing Practice` (+ 'Total')
- {FN_SITE}(start_date, end_date): per Mode x `Managing Practice` x `Site`
- {FN_AVG_CARDS}(start_date, end_date[, min_exams]): the vs-Average benchmark cards per Mode
  (`Pop Avg Efficiency` = radiologist-population average Mosaic efficiency)
- {FN_AVG_PP}(start_date, end_date[, min_exams]): `Vs RP Avg` by Provider Practice (+ 'Total')
- {FN_AVG_RAD}(start_date, end_date[, min_exams]): `Vs RP Avg` by radiologist
How to call: SELECT ... FROM {FN_PP}('2026-09-01', '2026-09-30') WHERE `Mode` = 'Full Mosaic'.
- start_date / end_date are 'YYYY-MM-DD' strings, not DATE literals.
- Always filter `Mode`: 'Full Mosaic' (default, "overall"), 'Reporting Only', 'Drafting Only',
  'Capture Only', 'Drafting + Capture'.
- Pass whole months: last complete month = ({LM_WINDOW}).
- To compare all Mosaic solutions / modes company-wide in one answer, read the 'Total' rows of {FN_PP}
  (one fast call returns every Mode). Do not put more than 2 efficiency metric-view measures in one query:
  each measure rescans the exam-level source and the query becomes very slow.
- Rows are already aggregated: never SUM or AVG `Pct Change Vs Baseline`, `Mosaic Efficiency` or `Vs RP Avg`
  across rows; filter to the row you need.
- 'Total' is a ROW of {FN_PP}, {FN_MP} and {FN_AVG_PP} and always has the most exams. For any top / most /
  largest / smallest / rank / "which practice" question you MUST add `<> 'Total'` (else the answer is 'Total').
- `Pct Change Vs Baseline` is a fraction (0.127 -> 12.7%). The functions have no read-time-savings column;
  derive it per row as `Baseline Efficiency` / `Mosaic Efficiency` - 1 (negative = less read time per exam).
  `Vs RP Avg` is a ratio to the average (0.92 -> 8% below average, 1.10 -> 10% above). `Mosaic Efficiency`
  and `Baseline Efficiency` are raw ratios (3 decimals).
- min_exams = PowerBI "Min exams" slicer, default 100; omit it unless the user gives another threshold.
- When ranking radiologists by efficiency change with {FN_RAD}, add `Mosaic Exams` >= 100 unless the user
  gives a threshold (tiny volumes give extreme ratios) and say you did so. The vs-average functions already
  apply min_exams.
- Find a radiologist with `Radiologist` ILIKE '%lastname%'.
- A practice named on its own ("PRA's efficiency", "RP Florida", "for CRC") is a PROVIDER practice: use
  {FN_PP} / `Provider Practice`. Use {FN_MP} / {FN_SITE} only when the user says "managing practice",
  "site", "location" or "where the exams were read". Many names exist as both; say which one you used.
- Never SELECT * from a function: always filter `Mode` and the row(s) the user asked about.
Use the METRIC VIEWS (not the functions) for company-wide or Local Region efficiency, mode KPIs and
month-by-month trends. "Overall" / "company-wide" / "total" efficiency change for a period is ONE number:
MEASURE(`Full Mosaic Pct Change Vs Baseline`) from mosaic_efficiency_metric_view, not a function.
The functions have no region or month column; call once per window if needed.

SYNONYMS
- adoption, usage, penetration, "% read in Mosaic" -> `Pct RPCE Reporting` (volume view)
- draft usage, drafting adoption -> `Pct RPCE Drafting`; capture usage -> `Pct RPCE Capture`
- coverage, "% drafted" of draftable exams -> `Pct Drafted` (draftable view)
- efficiency gain / lift / improvement / productivity change -> `... Pct Change Vs Baseline`
- read time savings, time saved per exam -> `... Implied Read Time Savings Pct`
- added capacity, extra capacity, capacity lift -> `Pct Addl Capacity`; capacity per shift -> `New Capacity`
- utilization, busy-ness, reading time share of shift -> `New Utilization`
- peer benchmark, vs average, vs RP average -> efficiency vs RP average
- rads, docs, physicians, providers -> radiologists; group, practice, team -> Provider Practice unless the user
  says managing / site practice.

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

def cap_total(month_expr, measures):
    """PBI-parity capacity total: only practices with a TBWU 26 baseline that month (PBI visual filter)."""
    return f"""WITH ok AS (
  SELECT `Local Practice` FROM {CAP}
  WHERE `Month` = {month_expr}
  GROUP BY ALL HAVING MEASURE(`Has TBWU26 Baseline`) = 1)
SELECT {measures}
FROM {CAP}
WHERE `Month` = {month_expr} AND `Local Practice` IN (SELECT `Local Practice` FROM ok)"""


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
     f"""SELECT `Mode`, `Radiologists`, `Mosaic Exams`, `Pct Change Vs Baseline`,
       `Baseline Efficiency` / `Mosaic Efficiency` - 1 AS read_time_change_per_exam
FROM {FN_PP}({LM_WINDOW})
WHERE `Provider Practice` = 'Total'
ORDER BY `Pct Change Vs Baseline` DESC"""),
    ("Efficiency vs baseline by local region last month",
     f"""SELECT `Local Region`, MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS eff_change,
       MEASURE(`Full Mosaic Mosaic Exams`) AS mosaic_exams
FROM {EFF}
WHERE `Exam Month` = {LAST_MONTH}
GROUP BY ALL ORDER BY eff_change DESC"""),
    ("Which provider practices are least efficient compared with the RP average?",
     f"""SELECT `Provider Practice`, `Radiologists`, `Mosaic Efficiency`, `Vs RP Avg`
FROM {FN_AVG_PP}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` <> 'Total'
ORDER BY `Vs RP Avg` ASC LIMIT 10"""),
    ("How did PRA do last month?",
     f"""SELECT `Mode`, `Radiologists`, `Mosaic Exams`, `Baseline Efficiency`, `Mosaic Efficiency`,
       `Pct Change Vs Baseline`
FROM {FN_PP}({LM_WINDOW})
WHERE `Provider Practice` = 'PRA'"""),
    ("Efficiency change by provider practice last month",
     f"""SELECT `Provider Practice`, `Radiologists`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_PP}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic'
ORDER BY sort_key, `Mosaic Exams` DESC"""),
    ("Which provider practices had the smallest efficiency gain last month?",
     f"""SELECT `Provider Practice`, `Radiologists`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_PP}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` <> 'Total'
ORDER BY `Pct Change Vs Baseline` ASC LIMIT 10"""),
    ("Top 10 radiologists by efficiency gain last month",
     f"""SELECT `Provider Practice`, `Radiologist`, `Mosaic Exams`, `Baseline Efficiency`, `Mosaic Efficiency`,
       `Pct Change Vs Baseline`
FROM {FN_RAD}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Mosaic Exams` >= 100
ORDER BY `Pct Change Vs Baseline` DESC LIMIT 10"""),
    ("How did radiologist Taha do on each Mosaic solution last month?",
     f"""SELECT `Mode`, `Provider Practice`, `Radiologist`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_RAD}({LM_WINDOW})
WHERE `Radiologist` ILIKE '%taha%'"""),
    ("Which exams drove Taha's Drafting efficiency change last month?",
     f"""SELECT `Radiologist`, `Parent Exam`, `Mosaic Exams`, `Baseline Efficiency`, `Mosaic Efficiency`,
       `Pct Change Vs Baseline`
FROM {FN_EXAM}({LM_WINDOW})
WHERE `Mode` = 'Drafting Only' AND `Radiologist` ILIKE '%taha%'
ORDER BY `Mosaic Exams` DESC LIMIT 20"""),
    ("Efficiency change by managing practice last month",
     f"""SELECT `Managing Practice`, `Sites`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_MP}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic'
ORDER BY sort_key, `Mosaic Exams` DESC"""),
    ("What was overall Mosaic efficiency change vs baseline last month?",
     f"""SELECT MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS full_mosaic_pct_change
FROM {EFF}
WHERE `Exam Month` = {LAST_MONTH}"""),
    ("Which managing practice read the most Mosaic exams last month?",
     f"""SELECT `Managing Practice`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_MP}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Managing Practice` <> 'Total'
ORDER BY `Mosaic Exams` DESC LIMIT 1"""),
    ("Efficiency change by site for managing practice ESR last month",
     f"""SELECT `Site`, `Mosaic Exams`, `Pct Change Vs Baseline`
FROM {FN_SITE}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Managing Practice` = 'ESR'
ORDER BY `Mosaic Exams` DESC"""),
    ("What is the radiologist-population average Mosaic efficiency for each solution?",
     f"""SELECT `Mode`, `Radiologists`, `Pop Avg Efficiency`, `RP Avg Efficiency Overall`
FROM {FN_AVG_CARDS}({LM_WINDOW})
ORDER BY sort_key"""),
    ("Which radiologists are furthest below the RP average efficiency?",
     f"""SELECT `Provider Practice`, `Radiologist`, `Subspecialty`, `Mosaic Exams Period`, `Mosaic Efficiency`, `Vs RP Avg`
FROM {FN_AVG_RAD}({LM_WINDOW})
WHERE `Mode` = 'Full Mosaic'
ORDER BY `Vs RP Avg` ASC LIMIT 20"""),
    ("How did % of RPCE exams read in Mosaic change month over month?",
     f"""SELECT `Final Month`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting,
       MEASURE(`Pct RPCE Drafting`) AS pct_rpce_drafting
FROM {VOLUME}
WHERE `Final Month` IN (add_months({LAST_MONTH}, -1), {LAST_MONTH})
GROUP BY ALL ORDER BY `Final Month`"""),
    ("How does last month's Mosaic efficiency gain compare with the same month last year?",
     f"""SELECT `Exam Month`, MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS full_mosaic_pct_change,
       MEASURE(`Full Mosaic Mosaic Exams`) AS mosaic_exams
FROM {EFF}
WHERE `Exam Month` IN (add_months({LAST_MONTH}, -12), {LAST_MONTH})
GROUP BY ALL ORDER BY `Exam Month`"""),
    ("Break down Mosaic adoption in the Apex region by managing practice last month",
     f"""SELECT `Managing Practice`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting,
       MEASURE(`RPCE Exam Count`) AS rpce_exams
FROM {VOLUME}
WHERE `Local Region` = 'Apex' AND `Final Date` >= {LAST_MONTH} AND `Final Date` < {THIS_MONTH}
GROUP BY ALL ORDER BY rpce_exams DESC"""),
    ("What capacity did Mosaic add last month and what was utilization?",
     cap_total(LAST_MONTH, """MEASURE(`Selected Shift Count`) AS shifts,
       MEASURE(`Average Baseline`) AS avg_baseline_tbwu,
       MEASURE(`New Capacity`) AS new_capacity_tbwu,
       MEASURE(`Addl Capacity Per Shift`) AS addl_capacity_per_shift,
       MEASURE(`Pct Addl Capacity`) AS pct_addl_capacity,
       MEASURE(`New Utilization`) AS utilization""")),
    ("What share of on-shift cases were read and drafted in Mosaic last month?",
     cap_total(LAST_MONTH, """MEASURE(`Pct Mosaic`) AS pct_mosaic, MEASURE(`Pct Mosaic Drafting`) AS pct_mosaic_drafting""")),
    ("Capacity by practice last month",
     f"""SELECT `Local Region`, `Local Practice`, MEASURE(`Selected Shift Count`) AS shifts,
       MEASURE(`Average Baseline`) AS avg_baseline_tbwu, MEASURE(`New Capacity`) AS new_capacity_tbwu,
       MEASURE(`Pct Addl Capacity`) AS pct_addl_capacity, MEASURE(`New Utilization`) AS utilization
FROM {CAP}
WHERE `Month` = {LAST_MONTH}
GROUP BY ALL HAVING MEASURE(`Has TBWU26 Baseline`) = 1
ORDER BY shifts DESC"""),
    ("Monthly trend of added capacity and utilization",
     f"""WITH ok AS (
  SELECT `Local Practice`, `Month` FROM {CAP}
  WHERE `Month` >= add_months({THIS_MONTH}, -12) AND `Month` < {THIS_MONTH}
  GROUP BY ALL HAVING MEASURE(`Has TBWU26 Baseline`) = 1)
SELECT `Month`, MEASURE(`Pct Addl Capacity`) AS pct_addl_capacity, MEASURE(`New Utilization`) AS utilization,
       MEASURE(`Selected Shift Count`) AS shifts
FROM {CAP}
WHERE (`Local Practice`, `Month`) IN (SELECT `Local Practice`, `Month` FROM ok)
GROUP BY ALL ORDER BY `Month`"""),
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

SEP_2026 = "DATE'2026-09-01'"
SEP_RANGE = "`Final Date` >= DATE'2026-09-01' AND `Final Date` < DATE'2026-10-01'"
SEP_DRAFT = "`Calendar Date` >= DATE'2026-09-01' AND `Calendar Date` < DATE'2026-10-01'"

# Benchmarks (question, ground-truth sql) for Genie evaluation runs. Anchored on the PBI parity month
# (tools/mosaic_validation/parity) so expected answers tie back to PowerBI. --check executes them too.
BENCHMARKS = [
    ("How many clinical exams and RPCE exams were there in September 2026?",
     f"""SELECT MEASURE(`Exam Count`) AS clinical_exams, MEASURE(`RPCE Exam Count`) AS rpce_exams
FROM {VOLUME} WHERE {SEP_RANGE}"""),
    ("What percent of RPCE exams were read, drafted and captured in Mosaic in September 2026?",
     f"""SELECT MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting, MEASURE(`Pct RPCE Drafting`) AS pct_rpce_drafting,
       MEASURE(`Pct RPCE Capture`) AS pct_rpce_capture
FROM {VOLUME} WHERE {SEP_RANGE}"""),
    ("Show % of RPCE exams read in Mosaic by local region for September 2026",
     f"""SELECT `Local Region`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting
FROM {VOLUME} WHERE {SEP_RANGE} GROUP BY ALL ORDER BY `Local Region`"""),
    ("How many radiologists used Mosaic in September 2026?",
     f"""SELECT MEASURE(`Mosaic Radiologist Count`) AS mosaic_radiologists FROM {VOLUME} WHERE {SEP_RANGE}"""),
    ("What was overall Mosaic efficiency change vs baseline in September 2026?",
     f"""SELECT MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS full_mosaic_pct_change
FROM {EFF} WHERE `Exam Month` = {SEP_2026}"""),
    ("What were the implied read time savings with Mosaic in September 2026?",
     f"""SELECT MEASURE(`Full Mosaic Implied Read Time Savings Pct`) AS implied_read_time_savings
FROM {EFF} WHERE `Exam Month` = {SEP_2026}"""),
    ("Drafting efficiency change vs baseline by local region in September 2026",
     f"""SELECT `Local Region`, MEASURE(`Drafting Pct Change Vs Baseline`) AS drafting_pct_change
FROM {EFF} WHERE `Exam Month` = {SEP_2026} GROUP BY ALL ORDER BY `Local Region`"""),
    ("Efficiency vs RP average by local region in September 2026",
     f"""SELECT `Local Region`, MEASURE(`Full Mosaic Efficiency Vs RP Avg`) AS eff_vs_rp_avg
FROM {RP_AVG} WHERE `Exam Month` = {SEP_2026} GROUP BY ALL ORDER BY `Local Region`"""),
    ("How many shifts were in scope for capacity in September 2026, and what were the average baseline and new capacity per shift?",
     cap_total(SEP_2026, """MEASURE(`Selected Shift Count`) AS shifts, MEASURE(`Average Baseline`) AS avg_baseline_tbwu,
       MEASURE(`New Capacity`) AS new_capacity_tbwu""")),
    ("What was the % additional capacity and utilization in September 2026?",
     cap_total(SEP_2026, """MEASURE(`Pct Addl Capacity`) AS pct_addl_capacity, MEASURE(`New Utilization`) AS utilization""")),
    ("What % of on-shift cases were read and drafted in Mosaic in September 2026?",
     cap_total(SEP_2026, """MEASURE(`Pct Mosaic`) AS pct_mosaic, MEASURE(`Pct Mosaic Drafting`) AS pct_mosaic_drafting""")),
    ("Additional capacity per shift by practice in September 2026",
     f"""SELECT `Local Practice`, MEASURE(`Addl Capacity Per Shift`) AS addl_capacity_per_shift
FROM {CAP} WHERE `Month` = {SEP_2026}
GROUP BY ALL HAVING MEASURE(`Has TBWU26 Baseline`) = 1 ORDER BY `Local Practice`"""),
    ("What share of draftable exams were drafted in September 2026?",
     f"""SELECT MEASURE(`Pct Drafted`) AS pct_drafted FROM {DRAFTABLE} WHERE {SEP_DRAFT}"""),
    ("What were the top reasons draftable exams were not drafted in September 2026?",
     f"""SELECT `Category`, MEASURE(`Draftable Exam Count`) AS exams FROM {DRAFTABLE}
WHERE {SEP_DRAFT} AND `Is Drafted` = false
GROUP BY ALL ORDER BY exams DESC"""),
    ("How many radiologists are at each MVP funnel stage?",
     f"""SELECT `Funnel Stage`, MEASURE(`Radiologists`) AS radiologists FROM {PROGRAM}
WHERE `Funnel Stage` IS NOT NULL GROUP BY ALL ORDER BY `Funnel Stage`"""),
    # --- efficiency functions (= dashboard / PowerBI efficiency tables) ---
    ("What was PRA's Full Mosaic efficiency change vs baseline in September 2026?",
     f"""SELECT `Pct Change Vs Baseline` FROM {FN_PP}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` = 'PRA'"""),
    ("Show the Matrix provider practice's efficiency change vs baseline for each Mosaic mode in September 2026",
     f"""SELECT `Mode`, `Pct Change Vs Baseline` FROM {FN_PP}({SEP_WINDOW})
WHERE `Provider Practice` = 'Matrix'"""),
    ("Which 5 provider practices with at least 40,000 Mosaic exams had the highest Full Mosaic efficiency change in September 2026?",
     f"""SELECT `Provider Practice`, `Pct Change Vs Baseline` FROM {FN_PP}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` <> 'Total' AND `Mosaic Exams` >= 40000
ORDER BY `Pct Change Vs Baseline` DESC LIMIT 5"""),
    ("How many radiologists and Mosaic exams were in the Full Mosaic provider practice efficiency table in September 2026?",
     f"""SELECT `Radiologists`, `Mosaic Exams` FROM {FN_PP}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` = 'Total'"""),
    ("What was RP Florida's Drafting Only efficiency change in September 2026?",
     f"""SELECT `Pct Change Vs Baseline` FROM {FN_PP}({SEP_WINDOW})
WHERE `Mode` = 'Drafting Only' AND `Provider Practice` = 'RP Florida'"""),
    ("Which managing practice had the most Mosaic exams in September 2026, and what was its Full Mosaic efficiency change?",
     f"""SELECT `Managing Practice`, `Mosaic Exams`, `Pct Change Vs Baseline` FROM {FN_MP}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Managing Practice` <> 'Total'
ORDER BY `Mosaic Exams` DESC LIMIT 1"""),
    ("Full Mosaic efficiency change by site for managing practice RAF in September 2026",
     f"""SELECT `Site`, `Pct Change Vs Baseline` FROM {FN_SITE}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Managing Practice` = 'RAF' ORDER BY `Site`"""),
    ("What was Taha, Manuel R's Full Mosaic efficiency change vs baseline in September 2026?",
     f"""SELECT `Radiologist`, `Pct Change Vs Baseline` FROM {FN_RAD}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Radiologist` = 'Taha, Manuel R'"""),
    ("Top 5 radiologists by Full Mosaic efficiency change in September 2026 among those with at least 500 Mosaic exams",
     f"""SELECT `Radiologist`, `Pct Change Vs Baseline` FROM {FN_RAD}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Mosaic Exams` >= 500
ORDER BY `Pct Change Vs Baseline` DESC LIMIT 5"""),
    ("For the Mosaic Efficiency vs Average benchmark in September 2026, how many radiologists qualified and what was the population average efficiency for each mode?",
     f"""SELECT `Mode`, `Radiologists`, `Pop Avg Efficiency` FROM {FN_AVG_CARDS}({SEP_WINDOW})"""),
    ("Which 5 provider practices were furthest below the RP average Full Mosaic efficiency in September 2026?",
     f"""SELECT `Provider Practice`, `Vs RP Avg` FROM {FN_AVG_PP}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` <> 'Total'
ORDER BY `Vs RP Avg` ASC LIMIT 5"""),
    ("Which CRC radiologists were below the RP average Full Mosaic efficiency in September 2026?",
     f"""SELECT `Radiologist`, `Vs RP Avg` FROM {FN_AVG_RAD}({SEP_WINDOW})
WHERE `Mode` = 'Full Mosaic' AND `Provider Practice` = 'CRC' AND `Vs RP Avg` < 1
ORDER BY `Vs RP Avg`"""),
    # --- trends / comparisons / drill-down (metric views) ---
    ("How did the % of RPCE exams read in Mosaic change from August to September 2026?",
     f"""SELECT `Final Month`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting FROM {VOLUME}
WHERE `Final Date` >= DATE'2026-08-01' AND `Final Date` < DATE'2026-10-01'
GROUP BY ALL ORDER BY `Final Month`"""),
    ("Monthly Full Mosaic efficiency change vs baseline for July through September 2026",
     f"""SELECT `Exam Month`, MEASURE(`Full Mosaic Pct Change Vs Baseline`) AS full_mosaic_pct_change FROM {EFF}
WHERE `Exam Month` BETWEEN DATE'2026-07-01' AND DATE'2026-09-01'
GROUP BY ALL ORDER BY `Exam Month`"""),
    ("% of RPCE exams read in Mosaic by managing practice in the Apex region for September 2026",
     f"""SELECT `Managing Practice`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting FROM {VOLUME}
WHERE `Local Region` = 'Apex' AND {SEP_RANGE}
GROUP BY ALL ORDER BY `Managing Practice`"""),
    # --- edge cases (certification guide: misspellings, synonyms, no period, date ranges, regions) ---
    ("whats mosiac adoption for sept 2026",
     f"""SELECT MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting FROM {VOLUME} WHERE {SEP_RANGE}"""),
    ("How many radiologists used Mosaic?",  # no period -> last complete month (rule 3)
     f"""SELECT MEASURE(`Mosaic Radiologist Count`) AS mosaic_radiologists FROM {VOLUME}
WHERE `Final Date` >= {LAST_MONTH} AND `Final Date` < {THIS_MONTH}"""),
    ("How much capacity lift did Mosaic give us in September 2026?",
     cap_total(SEP_2026, "MEASURE(`Pct Addl Capacity`) AS pct_addl_capacity")),
    ("Mosaic adoption by month for Q3 2026",
     f"""SELECT `Final Month`, MEASURE(`Pct RPCE Reporting`) AS pct_rpce_reporting FROM {VOLUME}
WHERE `Final Date` >= DATE'2026-07-01' AND `Final Date` < DATE'2026-10-01'
GROUP BY ALL ORDER BY `Final Month`"""),
    ("What % of RPCE exams were drafted in Mosaic in the Maverick region in Sept 2026?",
     f"""SELECT MEASURE(`Pct RPCE Drafting`) AS pct_rpce_drafting FROM {VOLUME}
WHERE `Local Region` = 'Maverick' AND {SEP_RANGE}"""),
]

# column_configs: descriptions / synonyms; entity matching only on low-cardinality business dimensions
# (radiologist names are thousands of values -> format assistance only).
_PP = dict(d="Provider Practice (PowerBI 'Team Rolled up'): the radiologist's home practice.",
           s=["provider practice", "home practice", "rolled up team", "group"], em=True)
_TEAM = dict(d="Radiologist's team, finer than Team Rolled Up (Provider Practice).", s=["sub team"], em=True)
_REGION = dict(d="Local Region: one of Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix.",
               s=["region", "local"], em=True)
_MP = dict(d="Managing Practice (PowerBI 'Practice'): the practice that owns the exam's imaging site.",
           s=["managing practice", "site practice"], em=True)
_RAD = dict(d="Radiologist name, 'Last, First M'. Match partial names with ILIKE.",
            s=["radiologist", "rad", "doctor", "physician", "provider"], fa=True)
_DIMS = {"Team Rolled Up": _PP, "Team": _TEAM, "Local Region": _REGION, "Radiologist Name": _RAD,
         "Modality": dict(em=True), "Exam Category": dict(em=True)}
COLUMN_CONFIGS = {
    VOLUME: {**_DIMS, "Managing Practice": _MP,
             "Practice (PBI)": dict(d="PowerBI 'Practice' slicer value (location practice of the exam site).", em=True),
             "Drafting Model Category": dict(em=True), "Care Setting": dict(em=True),
             "Allocated TBWU": dict(x=True), "Exam Id": dict(x=True)},
    EFF: {**_DIMS, "Practice": _MP, "Subspecialty": dict(em=True)},
    RP_AVG: {**_DIMS, "Practice": _MP, "Subspecialty": dict(em=True)},
    CAP: {**_DIMS, "Radiologist": _RAD, "Local Practice": {**_MP, "s": ["managing practice", "practice"]}},
    DRAFTABLE: {**_DIMS,
                "Category": dict(d="Why a draftable exam was or was not drafted (first match in Category Sort Order).",
                                 s=["reason not drafted", "undrafted reason", "drafting category"], em=True),
                "Category Group": dict(em=True), "Drafting Model": dict(em=True),
                "Local Practice": dict(d="Short site-group code; NOT Managing Practice.")},
    PROGRAM: {"Radiologist Name": _RAD, "Funnel Stage": dict(em=True), "Program Track": dict(em=True),
              "MVP Cohort": dict(s=["cohort"], em=True), "Optimization Support Status": dict(em=True),
              "Dynamics Practice": dict(d="Free-text practice from Dynamics CRM, not the governed practice list.")},
}


def _column_configs(table):
    out = []
    for col, c in sorted(COLUMN_CONFIGS.get(table, {}).items()):
        cfg = {"column_name": col}
        if c.get("d"):
            cfg["description"] = [c["d"]]
        if c.get("s"):
            cfg["synonyms"] = c["s"]
        if c.get("em"):
            cfg["enable_entity_matching"] = True
        if c.get("em") or c.get("fa"):
            cfg["enable_format_assistance"] = True
        if c.get("x"):
            cfg["exclude"] = True
        out.append(cfg)
    return out

# SQL Expressions (certification guide: preferred over plain-text instructions). Measures stay governed in
# the metric views, so only reusable filters / expressions live here. Columns must be qualified with the
# view's last name segment. probe = a measure --check runs with the snippet to prove it executes.
def _v(t):
    return t.rsplit(".", 1)[1]

_LM_EQ = f"= {LAST_MONTH}"
SQL_FILTERS = [
    # (display_name, sql, synonyms, view, probe measure)
    ("Last complete month (adoption / volume)",
     f"{_v(VOLUME)}.`Final Date` >= {LAST_MONTH} AND {_v(VOLUME)}.`Final Date` < {THIS_MONTH}",
     ["last month adoption", "previous month volume", "last full month RPCE"], VOLUME, "Pct RPCE Reporting"),
    ("Year to date, complete months (adoption / volume)",
     f"{_v(VOLUME)}.`Final Date` >= date_trunc('YEAR', {LAST_MONTH}) AND {_v(VOLUME)}.`Final Date` < {THIS_MONTH}",
     ["YTD adoption", "year to date volume", "this year so far"], VOLUME, "Pct RPCE Reporting"),
    ("Last complete month (efficiency vs baseline)", f"{_v(EFF)}.`Exam Month` {_LM_EQ}",
     ["last month efficiency", "previous month read time savings"], EFF, "Full Mosaic Pct Change Vs Baseline"),
    ("Last complete month (efficiency vs RP average)", f"{_v(RP_AVG)}.`Exam Month` {_LM_EQ}",
     ["last month vs RP average", "previous month peer benchmark"], RP_AVG, "Full Mosaic Efficiency Vs RP Avg"),
    ("Last complete month (capacity / utilization)", f"{_v(CAP)}.`Month` {_LM_EQ}",
     ["last month capacity", "previous month utilization"], CAP, "Selected Shift Count"),
    ("Last complete month (drafting coverage)", f"{_v(DRAFTABLE)}.`Month` {_LM_EQ}",
     ["last month drafting coverage", "previous month draftable exams"], DRAFTABLE, "Draftable Exam Count"),
    ("Draftable but not drafted", f"{_v(DRAFTABLE)}.`Is Drafted` = false",
     ["not drafted", "undrafted", "missed drafts", "drafting misses"], DRAFTABLE, "Draftable Exam Count"),
    ("In an MVP cohort", f"{_v(PROGRAM)}.`Program Track` <> 'Not In A Cohort'",
     ["in the MVP program", "enrolled in MVP", "MVP cohort"], PROGRAM, "Radiologists"),
]
SQL_EXPRESSIONS = [
    # (alias, display_name, sql, view, probe measure)
    ("final_quarter", "Quarter (adoption / volume)", f"date_trunc('QUARTER', {_v(VOLUME)}.`Final Date`)",
     VOLUME, "Pct RPCE Reporting"),
    ("exam_quarter", "Quarter (efficiency)", f"date_trunc('QUARTER', {_v(EFF)}.`Exam Month`)",
     EFF, "Full Mosaic Pct Change Vs Baseline"),
]


def _snippet_checks():
    """(label, sql) pairs proving each snippet runs against its view."""
    out = [(f"filter: {d}", f"SELECT MEASURE(`{m}`) AS v FROM {t} WHERE {sql}") for d, sql, _, t, m in SQL_FILTERS]
    out += [(f"expression: {d}", f"SELECT {sql} AS {a}, MEASURE(`{m}`) AS v FROM {t} GROUP BY ALL ORDER BY 1 DESC LIMIT 4")
            for a, d, sql, t, m in SQL_EXPRESSIONS]
    return out


SAMPLE_QUESTIONS = [
    "What was Mosaic adoption last month?",
    "How much more efficient are radiologists on Mosaic than on legacy VR, by solution?",
    "What capacity did Mosaic add last month and what was utilization?",
    "Why weren't draftable exams drafted last month?",
    "Which provider practices have the most undrafted exams?",
    "Where does the MVP program stand?",
    "How did PRA do last month?",
    "Which radiologists are furthest below the RP average efficiency?",
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
    benchmarks = sorted(({"id": _id("bm", q), "question": [q],
                          "answer": [{"format": "SQL", "content": _lines(sql)}]} for q, sql in BENCHMARKS),
                        key=lambda e: e["id"])
    samples = sorted(({"id": _id("sq", q), "question": [q]} for q in SAMPLE_QUESTIONS), key=lambda e: e["id"])
    return {
        "version": 2,
        "config": {"sample_questions": samples},
        "data_sources": {"tables": [{"identifier": t, **({"column_configs": _column_configs(t)}
                                                          if t in COLUMN_CONFIGS else {})} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": _id("ti", "main"), "content": _lines(INSTRUCTIONS)}],
            "example_question_sqls": examples,
            "sql_functions": sorted(({"id": _id("fn", f), "identifier": f} for f in FUNCTIONS),
                                    key=lambda e: e["id"]),
            "sql_snippets": {
                "filters": sorted(({"id": _id("sf", d), "display_name": d, "sql": [sql], "synonyms": syn}
                                   for d, sql, syn, _, _ in SQL_FILTERS), key=lambda e: e["id"]),
                "expressions": sorted(({"id": _id("se", a), "alias": a, "display_name": d, "sql": [sql]}
                                       for a, d, sql, _, _ in SQL_EXPRESSIONS), key=lambda e: e["id"]),
            },
        },
        "benchmarks": {"questions": benchmarks},
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
    for q, sql in EXAMPLES + BENCHMARKS + _snippet_checks():
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
