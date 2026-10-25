"""Program narrative/glossary for the real Mosaic Value Project (MVP), hand-extracted once
from the Clinical Transformation team's own source decks - not derivable from EDW. The live
per-radiologist numbers (cohort, exclusion reason, efficiency-change figures) come from
`edw_prod.dataverse_m365-vra-dynamics-prod.rad_onboarding` (see `mosaic_service.get_mvp_rad_onboarding`);
this module is the static, slow-changing "what does this mean" layer that sits alongside it -
used both for UI copy (cohort/exclusion tooltips) and as grounding context for the AI
hover-explanation prompt (`app/services/ai_context_service.py`), so generated explanations use
RP's actual program language instead of guessing.

Source: "Carlton Prickett - Deployment/260724 Mosaic Value Project.pptx" (OneDrive-synced,
tracked in tools/source_watch/check_sources.py's CORE_FILES). Per that folder's own convention,
this one file is overwritten in place with each week's update rather than versioned, so as of
this extraction (2026-10-17) it contained BOTH the original July 2026 methodology slides (tier
definitions, program history, refined-approach process) AND the current 10/16/2026 weekly
status - both are captured below. Refresh by re-running the same extraction against a later
copy and replacing CURRENT_STATUS_NOTES (dated) + anything in the other constants that the
deck's own definitions have since changed.
"""

PROGRAM_NARRATIVE = (
    "The Mosaic Value Project (MVP) focuses on highly productive radiologists who are showing "
    "reduced efficiency on Mosaic Drafting and/or Capture - the AI-assisted exam-prep features. "
    "RP's own analysis found nearly 1/3 of radiologists may be losing efficiency on Drafting "
    "and/or Capture vs. legacy voice recognition (on average ~20% reduced efficiency on Drafted "
    "exams, ~37% on Captured exams). Root causes cited: on Drafting, time spent reviewing and "
    "editing AI-generated text exceeds what reading the case from scratch would take; on "
    "Capture, too much information gets pulled from tech worksheets, adding review time to "
    "verify accuracy. Left unaddressed, this risks degraded SLA adherence, radiologist "
    "retention, and overall product impact. MVP exists to find these radiologists, engage them "
    "directly, diagnose the specific barrier, and get them back to or above their own "
    "pre-Mosaic baseline."
)

PROGRAM_HISTORY = (
    "MVP grew out of a March-June 2026 'Revisit' training effort: RP partnered with every local "
    "practice to flag below-baseline radiologists and ran ~500 revisits. 70% of revisited rads "
    "had a utilization increase (avg +40%), 55% had an efficiency increase (avg +32%), and over "
    "300 radiologists moved from a negative to a positive efficiency change. MVP formalizes and "
    "continues that work as an ongoing program rather than a one-time push."
)

# The July 2026 methodology deck's own Priority definitions - a different, narrower dimension
# from rad_onboarding's `mvp_cohort` field (which looks like an outreach/wave grouping; the
# deck itself doesn't define "Cohort 1-4" by that exact name, so this module doesn't invent a
# definition for it - only what's actually documented is captured here). Priority was computed
# against a fixed May-Jul 2026 reporting window, on a population of 392 rads after exclusions
# (of an initial 1,500 on Drafting: 316 in Q3 go-live practices, 385 with <100 Drafted/Captured
# exams, 10 with missing/outlier data, 397 with no efficiency loss on any prepped exam type).
PRIORITY_TIER_DEFINITIONS: dict[str, str] = {
    "Priority 1": "High productivity (baseline capacity), low or negative overall "
    "Drafting/Capture efficiency change - the biggest combined capacity-at-risk.",
    "Priority 2": "Average productivity, low or negative overall Drafting/Capture efficiency "
    "change.",
    "Priority 3": "Average-to-high productivity with a very negative efficiency change on at "
    "least one specific exam-prep program (XR Drafting, CT Head Drafting, or US Capture), even "
    "when the overall Drafting/Capture number looks fine.",
}

# Plain-English meaning for every exclusion_reason value observed live in rad_onboarding
# (query_edw, 2026-10-17). Not all of these are explicitly named in the methodology deck (which
# only documents the original "Q3 go-live practice"/"<100 exams"/"no efficiency loss" buckets) -
# the rest are the CRM's own finer-grained reasons a candidate never entered or exited the
# active MVP worklist.
EXCLUSION_REASON_GLOSSARY: dict[str, str] = {
    "Reads <500 dx cases/mo": "Doesn't read enough diagnostic volume per month to produce a "
    "reliable efficiency signal.",
    "Not on RPCE": "Not yet live on the Radiology Partners Clinical Engine (RPCE) - Mosaic "
    "reporting/drafting isn't in use for this radiologist yet.",
    "LP Guidance - Unspecified": "Excluded on local-practice leadership's guidance; no specific "
    "reason given.",
    "LP Guidance - Other": "Excluded on local-practice leadership's guidance for a reason "
    "outside the standard categories.",
    "IC / Locum": "Independent contractor or locum - outside the standard MVP engagement model.",
    "Rad Refused": "The radiologist was offered engagement and declined.",
    "Specialty (Mammo)": "Mammography subspecialist - tracked under the separate Mammo "
    "Screening MVP dashboard, not the Drafting/Capture one.",
    "Specialty (IR)": "Interventional Radiology subspecialist - IR exam mix doesn't fit the "
    "Drafting/Capture efficiency model.",
    "Inconsistent Schedule": "Shift pattern too irregular to establish a reliable baseline.",
    "Heavy Mammo": "Case mix is mostly mammography even if not formally a Mammo subspecialist.",
    "Heavy IR": "Case mix is mostly interventional even if not formally an IR subspecialist.",
    "Mammo Only": "Reads mammography exclusively.",
    "Ops not currently including Neuro": "Local operations haven't included neuroradiology in "
    "this round of engagement.",
    "Practice Declined": "The practice itself opted the radiologist out of engagement.",
    "BCM Faculty": "Academic/faculty appointment - outside the standard community-practice "
    "engagement model.",
    "Highly productive": "Already performing well enough that engagement isn't a priority.",
    "Non-RP rad with Cox": "Not an RP-employed radiologist; reads under a Cox arrangement.",
    "Terming": "Radiologist is in the process of leaving RP.",
    "Practice dissolving": "The practice itself is winding down.",
    "Leaving practice": "Radiologist is transitioning out of their current practice.",
    "Transitioned to another practice": "Already moved to a different practice; re-baselining "
    "pending.",
    "Part-time IC": "Part-time independent contractor.",
    "Moving to PT IC status": "Transitioning to a part-time independent-contractor arrangement.",
    "Tech Stack constraint": "A technology/workstation limitation blocks engagement for now.",
}

# The 5-step engagement process (deck slides 20-21, "MVP - REFINED APPROACH"):
ENGAGEMENT_PROCESS_STEPS: list[str] = [
    "Identify - Deployment Directors align with each Local Practice Steering Committee on "
    "which radiologists to engage, the right contact method, and a target outreach week.",
    "Engage - 1st outreach sent on the target week; 2nd outreach 2 days later if no response; "
    "escalated to the Ops Practice Director/VP 1 day after that for engagement support.",
    "Address - Level 1: meet 1:1 with the radiologist to validate pain points and resolve "
    "on-the-spot. Level 2: engage other support teams for remaining barriers. Level 3: escalate "
    "'in-scope' barriers (skill/training gap, workflow, mic/peripheral, hardware/software) to "
    "Mosaic team; 'higher-order' barriers (product gaps, incentive misalignment, clinical/"
    "motivational) go to Product, local leadership, or Mosaic Mentors respectively.",
    "Monitor - Efficiency and utilization are tracked weekly until the radiologist returns to "
    "or exceeds their own pre-Mosaic baseline.",
    "Resolve - Case is closed once sustained improvement is confirmed.",
]

MENTORSHIP_PROGRAM_SUMMARY = (
    "Mosaic Mentors pairs a radiologist who's struggling with Mosaic with a peer coach matched "
    "on subspecialty, data metrics, and working style - used when the remaining barrier is a "
    "change-management one (trust, workflow habits) rather than a technical or training gap. "
    "Process: a Deployment Director identifies candidate peer coaches per practice from impact/"
    "feedback data; the Practice President finalizes official coaches; an Optimization "
    "Quarterback flags eligible radiologists and submits a mentor request; the Practice "
    "President matches referred radiologist to coach; the coach reports back with results, "
    "closing the loop."
)

# Dated snapshot from the most recent weekly update folded into the same source deck - refresh
# this when re-extracting from a newer copy (see module docstring).
CURRENT_STATUS_NOTES = (
    "As of 2026-10-16: 60% (217/368) of MVP radiologists signaling Drafting/Capture efficiency "
    "loss are now engaged (+9 vs. the prior week); 31 remain in outreach escalation needing ops "
    "support. Separately, 34% (43/127) of radiologists signaling Mammo-screening efficiency "
    "loss are engaged (+10 vs. prior week); 11 of those are past solutioning, with 6 back at or "
    "above their own baseline. 20 additional radiologists have been offered Mosaic Mentors "
    "support this week. CRC, NEOH, and RAC are tracked against their own Mosaic-efficiency-"
    "over-time trend rather than the legacy-VR baseline, since those practices' legacy baseline "
    "data isn't reliable."
)

# Hand-extracted from "Carlton Prickett - Deployment/260831 Mosaic_Rad_Engagement_Model (1).xlsx"
# - the Clinical Transformation team's own staffing/timeline calculator (also tracked in
# tools/source_watch/check_sources.py's CORE_FILES). Confirmed via openpyxl this session: a
# self-contained "how many people do we need to finish engaging everyone by date X" model, not a
# live feed - every number here is a single snapshot of whatever assumptions were typed into its
# "Inputs" tab as of this file's own last edit (2026-09-10 - supersedes an earlier, rosier
# "260827 MVP Rad Engagement Model.xlsx" snapshot this module previously used: that one assumed
# 1.25 hrs/radiologist and 66.1 rads/week throughput; this one is a materially more conservative
# re-estimate at 4.29 hrs/radiologist - including prep, scheduling, documentation, and chasing
# non-responders, not just session time - and 32.2 rads/week at current staffing). Its own
# original "Finish-by date" (2026-09-30) has already passed as of this extraction (2026-10-20),
# and at the current pace only 142 of 259 would have been reached by then - but its "if we add
# nobody at all" projected finish date (2026-10-26) is still genuinely near-term (6 days out as
# of this extraction), so that one IS still live-relevant, unlike the superseded file's stale
# projection. Deliberately NOT fed into the AI-generated weekly narrative (app/services/
# ai_context_service.py) to avoid an LLM conflating this staffing-ask snapshot with the weekly
# program-status update. Shown in the UI purely as dated planning context, clearly labeled as
# such - not reconciled against EDW's own headcount (409 actively tracked as of this same date)
# or the weekly deck's (368) - all three describe "MVP radiologists" from a different angle and
# don't share one census.
ENGAGEMENT_CAPACITY_PLAN: dict[str, object] = {
    "source_date": "2026-09-10",
    "radiologists_on_list": 400,
    "already_engaged_at_plan_time": 30,
    "left_to_go_at_plan_time": 370,
    "realistic_target": 259,  # "radiologists we have to engage" - 70% of the 370 left to go, per the COLs' own 65-75% estimate
    "hours_per_radiologist_all_in": 4.29,  # 1.5h in-session + 2.79h prep/scheduling/documentation/chasing non-responders
    "total_hours_of_work": 1110,
    "cols_today": 5,
    "people_needed_at_full_col_hours": 10,
    "people_to_add": 5,
    "trainers_to_borrow_at_16hrs_week": 8,
    "throughput_per_week_current_team": 32.2,
    "start_date": "2026-08-31",
    "finish_by_date": "2026-09-30",
    "engaged_by_finish_by_date": 142,  # at current-team pace - about 55% of the 259 target, not 100%
    "projected_finish_date_if_unaided": "2026-10-26",
    "summary": (
        "It takes about 4.3 hours of Clinical Optimization Lead (COL) time to engage one "
        "radiologist, all in - 1.5 hours in session and the rest in prep, scheduling, "
        "documentation, and outreach that doesn't convert. With 370 radiologists left to go and "
        "an estimated 70% actually needing and taking a 1:1, that's 259 radiologists and about "
        "1,110 hours of work. At current staffing (5 COLs, ~28 usable hours/week each), the team "
        "would reach only 142 of those 259 (about 55%) by their original September 30 target - "
        "reaching all 259 needs 10 people total (5 more than today), or 8 borrowed trainers at "
        "16 hours/week each. Left as currently staffed, the team projects finishing around "
        "October 26, 2026."
    ),
}

# Verbatim (lightly trimmed) transcription of slide 1's weekly narrative from the same source
# deck - the program team's own prose, not a derived summary - used as grounding for the
# AI-generated "state of the program" narrative (see app/services/ai_context_service.py). Dated
# the same as CURRENT_STATUS_NOTES; refresh both together from a newer deck copy.
LATEST_WEEKLY_NARRATIVE = (
    "MVP Weekly update, 10/16/2026: 60% (217/368) of MVP radiologists signaling Drafting/Capture "
    "efficiency loss are now engaged (+9 vs. last week), impact holding steady; 31 remain in "
    "outreach escalation needing ops support. CRC, NEOH, and RAC are tracked on Mosaic-"
    "efficiency-over-time rather than the legacy-VR baseline, since those practices' legacy "
    "baseline data is unreliable. 34% (43/127) of radiologists signaling Mammo-screening "
    "efficiency loss are engaged (+10 vs. last week); 11 are past solutioning, 6 back at or "
    "above baseline. 20 additional radiologists have been offered Mosaic Mentors this week, with "
    "leadership teams addressing how to incentivize time spent participating. What's next: "
    "Mosaic 2.0 for Diagnostic reading general-releases in November - some practices are holding "
    "off engaging radiologists until planned enhancements (especially customizable templates) "
    "land; some of this week's Mammo efficiency loss traces to radiologists switching between "
    "1.0 (general reading) and 2.0 (Mammo), partly from functionality gaps or guidance that 2.0 "
    "isn't ready for general use - next step is diagnosing per-radiologist friction in 2.0. DXA "
    "Capture's 2.0 template passed limited-scope testing; an impression-guidelines update is "
    "needed before a broader-use greenlight."
)
