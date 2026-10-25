"""Python port of frontend/src/utils/localRegion.ts - kept in exact sync by hand (there's no
shared code between the two runtimes). That file is itself translated from the real Power BI
DAX calculated column '0. Cur'[Local], which buckets each Team into one of 6 named regions via
a fixed SWITCH(TRUE(), Team IN {...}, "X", ...) list. Used server-side only for the MVP Area
Detail dashboard's practice -> Local-team grouping (see mosaic_service.get_mammo_screening_trend
sibling, cache_service.get_efficiency_trend_by_local_team) - every other page in this app does
this grouping client-side via localRegion.ts directly.

MVP Area Detail groups by tbl_mvp_rad_onboarding.practice (a Dataverse CRM field, independent of
tbl_exam_inventory), not by this app's own Team/Practice columns - confirmed live (2026-10-23)
this is a genuinely different pipeline, so the Team-vs-Practice column-conflation bug fixed in
mosaic_service.py's Capacity/Efficiency CTEs doesn't apply here directly. A related but distinct
problem does: confirmed live that 220 of the ~2600 MVP radiologists' practice strings didn't
case-sensitively match any of the 5 named-region sets below, silently landing them in the
"Matrix" catch-all instead of their real region. 205 of those 220 were confirmed, real fixes
(added below): "Helios"/"Boca"/"RP Iowa" are case/prefix variants of already-listed practices;
"RP Phoenix" had no existing entry at all, confirmed via tbl_exam_inventory's own Team breakdown
to be dominated by already-Maverick teams. The remaining 15 (Bethesda: 13, RP Atlantic Coast: 1,
RP West Georgia: 1) are NOT fixed here - Bethesda's own Team signal is genuinely mixed (no clear
majority), and the other two don't appear in tbl_exam_inventory at all (likely new/administrative
Dataverse-only entries) - flagged for a human decision rather than guessed.
"""

_SPECIAL_OPERATIONS = {
    "ESR", "LFI", "Jefferson", "GLI", "RAI", "RP Cascade", "RP Crossroads", "JR", "DRSRP",
    "RP East Florida", "RP North Florida", "RP Palm Beach", "RP Florida West", "PRA",
    "ESRMH Garnet", "ESRMH Hackensack", "ESRMH Legacy", "ESR Long Island", "ESR Metro Hudson",
    "SEAL Team", "SEAL Legacy", "vRad", "Spec Ops Reserve",
}

_APEX = {
    "ADI", "ADR", "CRC Central", "CRC NW", "CRC SW", "Midstate", "NEOH", "Rad Alliance",
    "RP Kentucky", "RP Bluegrass", "RAC", "RACSW", "RPKY", "RPBG", "RA", "ADR Legacy", "CRC",
    "Rad Alliance Legacy", "Rad Alliance NorthCrest", "RP Bluegrass Legacy",
}

_GENESIS = {
    "Coastal", "Greensboro", "MBB", "Northside", "Greensboro Canopy", "RAF", "RP Florida",
    "RP Sandhills", "RP South Carolina", "SOAR", "BOCA", "Boca", "GR", "NRA", "RASF", "MBB Legacy",
    "MBB Phoebe Putney", "Northside Radiology", "RAF East Coast", "RAF Panhandle",
    "RAF Sarasota", "RAF Tampa", "RAF Tele", "RASF Miami", "RASF Naples", "RP Florida Legacy",
    "RP Florida West",
}

_MAVERICK = {
    "Advanced Radiology", "Alaska", "CIR", "Desert", "GIMA", "RP SoCal", "IAM", "IAMSE", "MIA",
    "Mountain", "NIR", "RAA", "MXC", "Red Rock", "RIMA", "RP Sol", "RP Sun City", "RP Chicago",
    "RP Forest City", "Saline Valley", "RP Valley Radiologists", "SVDI", "Western Colorado",
    "WIR", "RP IOWA", "RP Iowa", "GSIA", "SVL", "MR", "DR", "NWIR", "ARSC", "DR Legacy", "DR DRS",
    "IAMSE Hurley", "IAM Marquette", "IAM Midlands", "Lakefront Imaging", "Mountain Legacy",
    "Mountain Yampa", "RP NWIR", "RP SMIL", "RP SoCal Lakewood", "RP SoCal Legacy",
    "RP SoCal Palmdale", "RP Valley", "SVDI Legacy", "SVDI San Ramon", "SMI", "RIMA California",
    # RP Phoenix - no explicit PBI/DAX source entry found (confirmed absent from the original
    # 5-set vocabulary), but confirmed live (2026-10-23) against tbl_exam_inventory: of the
    # named-Team radiologists reading RP Phoenix exams, the plurality are RP Valley/RP Sol/
    # RP Sun City/RP SMIL - all already-Maverick teams - a real, data-confirmed placement, not
    # a guess.
    "RP Phoenix",
}

_TRAILBLAZER = {
    "Access Alexandria", "ARA", "BR Academic", "BR Community", "CIRPA", "Community", "RP Eagle",
    "EBI", "GIA", "Lake Charles", "RP Borderlands", "RP Brazosport", "RP Corpus Christi",
    "RP Dallas", "RP El Paso", "RP Gulf Coast", "RP Houston", "RP Laredo", "RP Victoria", "BR",
    "Slidell", "ACC", "RPNM", "EAG", "RPEP", "RPGC", "RPH", "Other", "EXTHMC",
    "RP Singleton Academic", "RP Singleton Community", "RP Singleton", "Rose",
    "RP North Houston", "Synergy", "Access Lake Charles", "Community Laredo",
    "Community Legacy", "Community Victoria", "Elite", "RP Borderlands Legacy",
    "RP Borderlands Lovelace", "RP Helios", "Helios",
}

LOCAL_REGIONS = ["Special Operations", "Apex", "Genesis", "Maverick", "Trailblazer", "Matrix"]


def get_local_region(team: str | None) -> str:
    if not team:
        return "Matrix"
    if team in _SPECIAL_OPERATIONS:
        return "Special Operations"
    if team in _APEX:
        return "Apex"
    if team in _GENESIS:
        return "Genesis"
    if team in _MAVERICK:
        return "Maverick"
    if team in _TRAILBLAZER:
        return "Trailblazer"
    return "Matrix"
