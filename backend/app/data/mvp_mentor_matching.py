"""The real Mosaic Mentors / peer-coach matching pipeline, hand-extracted once from
"Carlton Prickett - Deployment/260820 MVP_Peer Coach List for Review.xlsx" (OneDrive-synced,
tracked in tools/source_watch/check_sources.py's CORE_FILES) - not derivable from EDW.
`rad_onboarding`'s own my_mosaic_mentor/mosaic_mentor_status columns are populated for almost
none of the MVP cohort (confirmed live: 17 of 2,609 rows) because the real, actively-worked
matching data lives only in this spreadsheet, not in Dynamics.

Unlike the weekly-cadence MVP deck, this file is actively edited day-to-day (confirmed: last
modified the same day as this extraction, 2026-10-20) - this is a point-in-time snapshot of its
"Matching Status" sheet (15 radiologists being actively matched, as of that date), not a live
feed. Refresh by re-running the same extraction against a later copy and replacing
MENTOR_MATCHING_STATUS wholesale - there's no incremental-update story here, just re-snapshot.

Deliberately NOT included (out of scope for this pass, see the 2026-10-20 scoping conversation):
the 1,385-row candidate peer-coach pool ("Peer Coaches Qualification Data"/"Peer Coaches For
Review-CL"), the 811-row raw interest-survey responses, and the richer per-case narrative fields
that live alongside matching_status in the source sheet (Perception of Challenges, Optimizations
Completed) - those overlap conceptually with optimization_support_notes already shown elsewhere
and were left out to keep this addition to exactly "matching status + qualification criteria."
"""

# The "Peer Coach Qualifications" sheet's own stated core requirements for a radiologist to
# qualify as a peer coach (status "Yes"/"Yes-Volunteered") - used as AI hover-context grounding
# (app/services/ai_context_service.py) so an explanation of a mentor-match status can also
# answer "what would it take for someone to BE a coach", not just "what status is this".
PEER_COACH_QUALIFICATION_THRESHOLDS = (
    "To qualify as a peer coach (status 'Yes' or 'Yes-Volunteered'), a radiologist must meet "
    "every core requirement: 70-110 TBWUs per 9-hour shift, Mosaic efficiency greater than 0.22, "
    "20%-75% overall efficiency improvement, at least 500 Mosaic exams in the selected period, "
    "and Employed or W2 employment type - plus qualify in at least one modality (US, CT, or XR, "
    "each requiring >=100 exams and 20%-75% efficiency improvement in that modality). "
    "'Volunteered' means they expressed interest via survey but don't meet every core "
    "requirement; 'Volunteered-Not Supported by Eff. Data' means they volunteered but have no "
    "qualifying modality."
)

# The "Matching Status" sheet's own status-progression definitions (from its companion "Sheet2"
# legend) - the real per-radiologist mentor-matching workflow, distinct from the generic
# mosaic_mentor_status field in rad_onboarding.
MENTOR_MATCH_STATUS_DEFINITIONS: dict[str, str] = {
    "New Request": "Just identified as a candidate for mentorship - not yet actively worked.",
    "Sourcing Mentor": "Actively identifying and evaluating candidate peer coaches for this radiologist.",
    "Mentor Proposal Sent": "A specific candidate mentor has been proposed to local practice leadership for approval.",
    "Mentor Approved": "Local practice leadership has approved the proposed mentor match.",
    "Mentorship Introduction Sent": "The mentor and mentee have been introduced to each other.",
    "Mentorship Scheduled": "A mentorship session has been scheduled.",
    "Post-Mentorship Monitoring": "The mentorship session(s) have occurred; efficiency is being tracked post-session.",
    "Closed": "The case is closed - either resolved, the radiologist declined, or no further action is planned.",
}

# One entry per radiologist on the "Matching Status" sheet as of 2026-10-20 (15 rows - the
# sheet's entire real-time worklist at snapshot time, not a sample). Keyed by npi for the O(1)
# lookup cache_service.get_mvp_radiologists() does when attaching this to MvpRadiologistItem.
# mentors_identified is the raw "Name (Practice)" list, newline-joined exactly as the sheet
# stores it - left unparsed since there's no need to query by individual coach name yet.
MENTOR_MATCHING_STATUS: list[dict] = [
    {
        "npi": 1518178235,
        "matching_status": "Closed",
        "mentors_identified": None,
        "matching_notes": "Rad moved into mosaic 2.0 so there isn't a general body rad able to mentor him in that platform yet",
    },
    {
        "npi": 1245215649,
        "matching_status": "Closed",
        "mentors_identified": None,
        "matching_notes": "9/2: Rad declined mentorship",
    },
    {
        "npi": 1083696561,
        "matching_status": "Closed",
        "mentors_identified": "Michael Borbely (MBB)\nJason Poff (GR)\nSriyesh Krishnan (GR)\nRaleigh Johnson (IAM)\nJeremy O'Brien (RAF)",
        "matching_notes": (
            "9/29: Rad not interested in mentorship, all efficiency metrics improved above baseline\n"
            "Borbely - per PD, not a match due to a difference in case mix\n"
            "Poff - not responsive, no further f/u due to concern over inappropriate match\n"
            "Krishnan - Declined to participate due to time constraints and concerns about case mix match\n"
            "Johnson - Quality review in progress, rad indicated interest in mentoring on Mosaic survey\n"
            "O'Brien - email sent to ops 9/16; 9/23 agreed to participate, meeting scheduled week of 9/28"
        ),
    },
    {
        "npi": 1841411568,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "James Stallworth (Rad Alliance)",
        "matching_notes": (
            "9/30: Second follow up sent\n9/23: Follow up email sent\n"
            "9/16: Email sent to PD/RVP/ACMO to inquire about rad match and availability"
        ),
    },
    {
        "npi": 1679557417,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "Radparvar, Arash (GR)\nTade Adewale, Funmilayo (Saline Valley)\nSchroeder, Reid (ARSC)",
        "matching_notes": (
            "10/7: Dr. Radparvar agreed to participate, briefing meet scheduled for 10/12\n"
            "9/30: Follow up email sent to Dr. Radparvar and local ops\n"
            "9/24: Email outreach sent directly to Dr. Radparvar\n"
            "9/23: Dr. Stroud (GR) approved Dr. Radparvar as a mentor"
        ),
    },
    {
        "npi": 1689602872,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "Griggs, Thomas (RP Eagle)\nSchroeder, Reid (ARSC)\nTade Adewale, Funmilayo (Saline Valley)",
        "matching_notes": "10/1: Proposal email sent to ops leadership at RPBG, Eagle, ARSC, and Saline Valley",
    },
    {
        "npi": 1326093345,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "Johnson, David (Rad Alliance)\nSud, Avinash (ADR)\nTerrell, John (MXC)",
        "matching_notes": "10/1: Proposal email sent to ops leadership at RA/ADI, MXC, and ADR",
    },
    {
        "npi": 1245325422,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "Benjamin, Joseph (CRC)\nWyatt, Gina (Rad Alliance)\nGarrison, Stephen (RP Florida)",
        "matching_notes": None,
    },
    {
        "npi": 1407834435,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": "Olga Kutsenko (Red Rock)",
        "matching_notes": "10/5: Per PD, Kutsenko not a match. Weidenfeld only reads diagnostic now. Sourcing new mentors",
    },
    {
        "npi": 1578588588,
        "matching_status": "Mentorship Introduction Sent",
        "mentors_identified": "Kellie Curtis (RIMA)\nSafwan Halabi (PRA)\nLori Barr (RAF)",
        "matching_notes": (
            "9/29: PRA AVP declined, wants Halabi to focus on helping PRA rads first before helping other practices\n"
            "9/24: Follow up email sent\n9/18: Email sent to PRA leadership to inquire about Dr. Halabi\n"
            "9/16: Per Ops/Carlton, Dr. Barr is not a coaching candidate\n"
            "Email sent to PD/RVP/ACMO on 9/16 to inquire about rad match and availability; rad suggested as mentor by DD/COL"
        ),
    },
    {
        "npi": 1750506481,
        "matching_status": "Post-Mentorship Monitoring",
        "mentors_identified": "O'Brien, Jeremy (RAF)",
        "matching_notes": "9/30: Intro email sent\n9/29: Briefing call conducted with Dr. O'Brien and mentee background email sent",
        "mentorship_meeting_date": "2026-10-06",
    },
    {
        "npi": 1447390554,
        "matching_status": "Post-Mentorship Monitoring",
        "mentors_identified": "Nelson Uzquiano (Community)\nStuart Head (Access Alexandria)",
        "matching_notes": (
            "9/18: Email sent to Community PD/VP to request mentorship from Dr. Uzquiano\n"
            "Awaiting confirmation from Dr. Elfrink that would he like to participate in peer coaching before approaching potential mentors"
        ),
        "mentorship_meeting_date": "2026-10-02",
    },
    {
        "npi": 1215138185,
        "matching_status": "Sourcing Mentor",
        "mentors_identified": "Matthew Darce (RP Houston)\nRobin Osborn (MBB)\nRobbie Shoots (RP Borderlands)\nJose Becerra (RPFL)\nWarren Cohen (RAF)",
        "matching_notes": (
            "9/28: Per PD, Dr. Shoots doesn't have capacity to participate\n"
            "9/24 - Proposal email sent to PDs for BG, Houston, Borderlands, and MBB\n"
            "Becerra - declined to participate\n"
            "Cohen - email sent to PD/RVP/ACMO on 9/16 to inquire about rad match and availability; 9/22 practice declined"
        ),
    },
    {
        "npi": 1447784616,
        "matching_status": "Sourcing Mentor",
        "mentors_identified": None,
        "matching_notes": None,
    },
    {
        "npi": 1164461315,
        "matching_status": "Mentor Proposal Sent",
        "mentors_identified": None,
        "matching_notes": None,
    },
]

MENTOR_MATCH_BY_NPI: dict[int, dict] = {row["npi"]: row for row in MENTOR_MATCHING_STATUS}
