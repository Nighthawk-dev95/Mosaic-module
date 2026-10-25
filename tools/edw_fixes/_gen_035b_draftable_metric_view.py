"""Generates 035b_mosaic_draftable_metric_view_{DRAFT,FLOW}.sql.

Run from repo root: python tools/edw_fixes/_gen_035b_draftable_metric_view.py
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _to_flow_style import flatten_strings  # noqa: E402

CATS = [
    (0, "Drafted", "Drafted"),
    (1, "RAD not enabled - Rad declined", "Rad Declined"),
    (2, "RAD not enabled - Ops declined", "Ops Declined"),
    (3, "RAD not enabled - Incomplete process", "Incomplete Process"),
    (4, "PRACTICE not enabled for model", "Practice Not Enabled"),
    (5, "DRAFT not available - Exam opened in <5 min", "Opened Under 5 Min"),
    (6, "DRAFT not available - Exam opened in >5 min", "Opened Over 5 Min"),
    (7, "Exam never opened, not drafted", "Never Opened"),
]


def q(s):
    return "'" + s.replace("'", "''") + "'"


def share(num, den="Draftable Exam Count"):
    return f"MEASURE(`{num}`) / NULLIF(MEASURE(`{den}`), 0)"


DIMS = [
    ("Calendar Date", "source.calendar_date",
     "Exam calendar date (legacy calendar_date). Bind the dashboard Period filter here."),
    ("Week Start", "source.week_start_monday",
     "Monday that starts the Mon-Sun week. The legacy/PBI column holding this is (mis)named week_end; "
     "PBI's own [Week Start] calc column (= week_end - 6) is a further 6 days earlier."),
    ("Month", "DATE_TRUNC('MONTH', source.calendar_date)", "Calendar month of the exam date."),
    ("PBI Month (by week)", "DATE_TRUNC('MONTH', source.week_start_monday)",
     "Month bucket PBI uses (Draftable[Month Start] = month of week_end). Only for reproducing PBI month "
     "visuals: a week spanning a month boundary lands wholly in the month of its Monday."),
    ("Category", "source.category",
     "Why a draftable exam was or was not drafted. First match wins: Drafted > RAD not enabled - Rad "
     "declined > Ops declined > Incomplete process > PRACTICE not enabled for model > Exam never opened > "
     "DRAFT not available - opened <5 min > opened >5 min. Sort with Category Sort Order."),
    ("Category Sort Order", "source.category_sort_order", "0 = Drafted ... 7 = Exam never opened."),
    ("Category Group",
     "CASE WHEN source.category = 'Drafted' THEN 'Drafted' "
     "WHEN source.category LIKE 'RAD not enabled%' THEN 'Radiologist not enabled' "
     "WHEN source.category = 'PRACTICE not enabled for model' THEN 'Practice not enabled' "
     "ELSE 'Enabled, draft not used' END",
     "Owner-level roll-up of Category: Radiologist not enabled (consent / ops / enablement), Practice not "
     "enabled (model roll-out), Enabled, draft not used (workflow / product)."),
    ("Is Drafted", "source.category = 'Drafted'", "TRUE if the exam was drafted."),
    ("Team", "source.Team", "Radiologist's roster team (Provider Practice sub-team). PBI Draftable[Team]."),
    ("Team Rolled Up", "source.team_rolled_up",
     "Provider Practice rolled up via tbl_team_rollups (PBI 'Team Rolled up' = Provider Practice)."),
    ("Local Region", "source.local_region",
     "6 fixed regions, exact copy of PBI Draftable[Localdraf] keyed on Team. Differs from the volume "
     "view's Local Region for a few Teams - see 035a comment."),
    ("Local Practice", "source.local_practice",
     "Exam's local practice short name (legacy local_practice = local_practice_short_name)."),
    ("Site", "source.site", "Exam location."),
    ("Radiologist Name", "source.Radiologist", "Reading radiologist."),
    ("NPI", "CAST(source.npi AS STRING)", "Reading radiologist NPI."),
    ("Exam Category", "source.exam_category", "Exam category from exam_category_lookup_xwalk (ParentRpt)."),
    ("Drafting Model", "source.drafting_model",
     "Declared AI drafting model / capturable category for the RPID (XR/MSK, CT Chest, CT Abd/Pel, "
     "CT Spine, CT Head, US Capturable, DEXA Capturable)."),
]

MEAS = [
    ("Draftable Exam Count", "SUM(source.exam_count)",
     "All Mosaic exams on drafting-eligible RPIDs (all 8 categories, Drafted included). = PBI "
     "Draftable[Exam Count]. Denominator of every Pct measure."),
    ("Draftable TBWU", "SUM(source.tbwu)", "TBWU of draftable exams. = PBI [Category Value] with Metric Selector = TBWU."),
    ("Radiologist Count", "COUNT(DISTINCT source.Radiologist)",
     "Distinct radiologists by name. = PBI Draftable[Rad Count] (DISTINCTCOUNT Radiologist)."),
    ("Undrafted Exam Count", "SUM(source.exam_count) FILTER (WHERE source.category <> 'Drafted')",
     "Draftable exams that were not drafted (categories 1-7)."),
    ("Undrafted TBWU", "SUM(source.tbwu) FILTER (WHERE source.category <> 'Drafted')",
     "TBWU of draftable exams not drafted."),
    ("Radiologists With Undrafted Exams",
     "COUNT(DISTINCT source.Radiologist) FILTER (WHERE source.category <> 'Drafted')",
     "Distinct radiologists with at least one undrafted draftable exam."),
]
for sort, cat, short in CATS:
    MEAS.append((f"{short} Exam Count", f"SUM(source.exam_count) FILTER (WHERE source.category = {q(cat)})",
                 f"Exams in category {sort} '{cat}'."))
MEAS += [
    ("Pct Drafted", share("Drafted Exam Count"),
     "Drafted / draftable. = PBI [Category % of Draftable] for Drafted."),
    ("Pct Undrafted", share("Undrafted Exam Count"), "Undrafted / draftable (= 1 - Pct Drafted)."),
]
for sort, cat, short in CATS[1:]:
    MEAS.append((f"Pct {short}", share(f"{short} Exam Count"),
                 f"Share of draftable exams in '{cat}'. = PBI [Category % of Draftable] for that category "
                 "(denominator = all 8 categories incl. Drafted)."))
MEAS += [
    ("Rad Not Enabled Exam Count",
     "SUM(source.exam_count) FILTER (WHERE source.category LIKE 'RAD not enabled%')",
     "Rad declined + Ops declined + Incomplete process (rad drafted <10% of the model's exams that week)."),
    ("Draft Not Used Exam Count",
     "SUM(source.exam_count) FILTER (WHERE source.category LIKE 'DRAFT not available%' "
     "OR source.category = 'Exam never opened, not drafted')",
     "Rad and practice enabled but no draft used: opened <5 min, opened >5 min, or never opened. The "
     "workflow / product bucket."),
    ("Pct Rad Not Enabled", share("Rad Not Enabled Exam Count"),
     "Share of draftable exams lost to radiologist enablement (consent / ops / incomplete)."),
    ("Pct Draft Not Used", share("Draft Not Used Exam Count"),
     "Share of draftable exams where rad and practice were enabled but no draft was used."),
    ("Pct Undrafted TBWU", share("Undrafted TBWU", "Draftable TBWU"),
     "TBWU-weighted undrafted share (= 1 - PBI [Category % of Draftable] for Drafted with Metric Selector = TBWU)."),
    ("Data Through Date", "MAX(source.calendar_date)",
     "Last calendar date in the snapshot (legacy view keeps completed Mon-Sun weeks only)."),
]

HEADER = """-- 035b: Mosaic Draftable / Undrafted metric view. DRAFT STATUS: edw_test only - do not promote
-- to edw_prod without approval. Generated by _gen_035b_draftable_metric_view.py - edit that, not this.
--
-- WHY: the Executive Dashboard's "Draftable, Undrafted" page (and Genie) need the PBI Volume
-- report's Draftable analysis as a governed metric view.
-- SOURCE: edw_test.enterprise_analytics.mosaic_draftable_snapshot_mv (035a), a 1:1 daily snapshot
-- of edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw - the table PBI imports - so the
-- category logic is PBI's by construction.
-- PBI parity: Draftable Exam Count = Draftable[Exam Count]; each Pct <category> =
-- [Category % of Draftable] for that category; Radiologist Count = [Rad Count].
-- Not carried over (broken in PBI as of 2026-10-24): [Total Draftable] (references missing table
-- draftabletotals_vw) and [Category % of Week] (filters on stale category names -> blank).
--
-- ADDITIVE ONLY: plain CREATE VIEW (no OR REPLACE).

CREATE VIEW edw_test.enterprise_analytics.mosaic_draftable_metric_view
COMMENT 'MOSAIC DRAFTABLE / UNDRAFTED SEMANTIC LAYER (draft, edw_test only). Every Mosaic exam on a drafting-eligible RPID, classified into the PBI 8-category waterfall explaining why it was or was not drafted. Source = daily snapshot of the PBI Draftable table (examsnotdraftedbutdraftable_vw).'
WITH METRICS
LANGUAGE YAML
AS
$$
"""


def main():
    doc = {
        "version": 1.1,
        "source": "edw_test.enterprise_analytics.mosaic_draftable_snapshot_mv",
        "comment": "Why draftable Mosaic exams were or were not drafted (PBI Volume report Draftable page). See CREATE VIEW comment.",
        "dimensions": [{"name": n, "expr": e, "comment": c} for n, e, c in DIMS],
        "measures": [{"name": n, "expr": e, "comment": c} for n, e, c in MEAS],
    }
    block = yaml.dump(doc, sort_keys=False, width=100000, allow_unicode=True)
    flow = yaml.dump(flatten_strings(doc), default_flow_style=True, sort_keys=False, width=100000, allow_unicode=True)
    assert yaml.safe_load(flow) == flatten_strings(doc)
    for suffix, body in (("DRAFT", block), ("FLOW", flow)):
        path = os.path.join(HERE, f"035b_mosaic_draftable_metric_view_{suffix}.sql")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(HEADER + body + "$$\n")
        print(path, len(DIMS), "dims", len(MEAS), "measures")


if __name__ == "__main__":
    main()
