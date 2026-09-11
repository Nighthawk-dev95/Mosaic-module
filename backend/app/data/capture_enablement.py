"""Real per-practice US Capture enablement dates - not derivable from EDW (no per-rad or
per-practice enablement-date field exists there), sourced from two manually-maintained
trackers: "Capture Deployment Tracker.xlsx" (Capture Deployment Tracker sheet, "Capture Soft
Launch Date" column - the first champion-rad go-live) and "US Capture Phase 3 Deployment
Status.xlsx" (Phase 3 sheet, dated "Full Enablement <date>" strings in the Notes column - the
all-rad go-live milestone), both under Carlton Prickett - US. Snapshot as of 2026-09-11.
Practices absent from this table have no known real date - the app falls back to its existing
"first captured exam" proxy for those. Refresh by re-running the same extraction against
updated copies of both workbooks and replacing the rows below.

Full-enablement dates are parsed from free-text notes ("Full Enablement 6/15" -> 2026-06-15);
two practices (CRC, RP Borderlands) show the opposite of monotonic adoption - fully enabled,
then explicitly opted back out weeks later - a lifecycle state ("opted_out") the rest of this
app doesn't otherwise model.

# (practice, soft_launch_date, full_enablement_date, opted_out)
"""

from datetime import date

CAPTURE_ENABLEMENT_ROWS: list[tuple[str, date | None, date | None, bool]] = [
    ("ADI", None, date(2026, 5, 19), False),
    ("ADR", date(2026, 3, 2), date(2026, 6, 3), False),
    ("ARA", date(2026, 5, 4), None, False),
    ("Access Alexandria", date(2026, 3, 6), date(2026, 5, 22), False),
    ("Access Lake Charles", date(2026, 3, 6), date(2026, 5, 19), False),
    ("Baylor", date(2026, 3, 19), None, False),
    ("CIR", date(2026, 4, 2), date(2026, 6, 15), False),
    ("CIRPA", date(2026, 1, 26), None, False),
    ("CRC", date(2026, 1, 26), date(2026, 5, 21), True),
    ("Coastal", date(2026, 3, 16), date(2026, 6, 4), False),
    ("Community", date(2026, 2, 24), None, False),
    ("ESR Long Island", date(2026, 3, 19), date(2026, 6, 2), False),
    ("ESR Metro Hudson", date(2026, 3, 11), date(2026, 6, 2), False),
    ("GLI", date(2026, 3, 9), date(2026, 6, 4), False),
    ("Greensboro", date(2026, 3, 10), date(2026, 6, 2), False),
    ("IAM", date(2026, 2, 19), None, False),
    ("IAMSE Hurley", date(2026, 2, 19), None, False),
    ("Jefferson", None, date(2026, 5, 22), False),
    ("Lakefront Imaging", date(2026, 3, 11), None, False),
    ("MBB", date(2026, 3, 12), None, False),
    ("Matrix", date(2026, 3, 10), date(2026, 5, 20), False),
    ("Mountain", None, date(2026, 5, 22), False),
    ("NEOH", None, date(2026, 5, 21), False),
    ("PRA", None, date(2026, 6, 1), False),
    ("RAC", date(2026, 1, 26), None, False),
    ("RACSW", date(2026, 1, 26), None, False),
    ("RAF", date(2026, 3, 10), date(2026, 5, 26), False),
    ("RAI", date(2026, 3, 23), date(2026, 6, 4), False),
    ("RIMA", date(2026, 3, 12), date(2026, 6, 11), False),
    ("RP Bluegrass", date(2026, 3, 17), None, False),
    ("RP Borderlands", date(2026, 2, 23), date(2026, 5, 21), True),
    ("RP Cascade", None, date(2026, 6, 4), False),
    ("RP Chicago", date(2026, 3, 11), date(2026, 5, 29), False),
    ("RP Corpus Christi", None, date(2026, 6, 1), False),
    ("RP Crossroads", date(2026, 3, 9), None, False),
    ("RP Dallas", None, date(2026, 5, 22), False),
    ("RP Eagle", date(2026, 1, 26), date(2026, 6, 2), False),
    ("RP El Paso", None, date(2026, 6, 4), False),
    ("RP Florida", date(2026, 3, 17), date(2026, 5, 20), False),
    ("RP Gulf Coast", date(2026, 3, 20), date(2026, 6, 1), False),
    ("RP Houston", date(2026, 2, 23), date(2026, 6, 1), False),
    ("RP Kentucky", date(2026, 2, 27), None, False),
    ("RP NWIR", date(2026, 3, 23), date(2026, 6, 15), False),
    ("RP North Florida", None, date(2026, 5, 21), False),
    ("RP SoCal", date(2026, 4, 6), date(2026, 6, 1), False),
    ("RP Sol", date(2026, 4, 3), date(2026, 5, 27), False),
    ("RP South Carolina", date(2026, 3, 23), date(2026, 6, 11), False),
    ("RP West Florida", None, date(2026, 5, 25), False),
    ("Rad Alliance", None, date(2026, 5, 19), False),
    ("Red Rock", date(2026, 3, 12), None, False),
    ("SEAL Team", date(2026, 3, 6), None, False),
    ("SOAR", date(2026, 3, 18), None, False),
    ("SVDI", date(2026, 3, 12), date(2026, 6, 1), False),
    ("Western Colorado", None, date(2026, 5, 22), False),
]

_BY_PRACTICE = {row[0]: row for row in CAPTURE_ENABLEMENT_ROWS}


def capture_enablement_for(practice: str | None) -> tuple[date | None, bool]:
    """Returns (best real enablement date, opted_out). Prefers the full-enablement (all-rad)
    date over the soft-launch (champion-rad-only) date; returns (None, False) when no tracker
    entry exists for this practice, meaning the caller should fall back to its own proxy."""
    if not practice or practice not in _BY_PRACTICE:
        return None, False
    _practice, soft_launch, full_enablement, opted_out = _BY_PRACTICE[practice]
    return (full_enablement or soft_launch), opted_out
