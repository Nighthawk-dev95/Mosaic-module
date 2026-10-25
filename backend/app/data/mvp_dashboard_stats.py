"""Pure classification/aggregation functions over the MVP rad_onboarding rows, shared by the AI
narrative generators (ai_context_service.py) that ground the Overview/Mammo dashboard
narratives in real computed numbers. Mirrors (and must be kept in sync by hand with - no shared
code between the two runtimes) the equivalent computations in frontend/src/pages/mvp/*.tsx,
which is what the UI itself actually renders; this module exists only so the precomputed AI
narrative can cite real, matching figures rather than guessing.

Status-stage mapping confirmed live (2026-10-20) against
edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding's mosaic_optimization_support_status
vocabulary: 1 Identified / 2 Confirmed (pre-funnel, not yet outreached) / 3-4 Outreached(+
Escalated) / 5 Scheduled / 6-7 Solutioning(+Escalated - Mentorship/IT/Program Specific) /
8 Monitoring Impact / 9 Closed (+Completed/Declined/Resigning/... variants). The PDF's own funnel
total (n=368 for the 10/16 snapshot) is exactly the sum of Outreached+Scheduled+Solutioning+
Monitoring+Closed - stages 1/2 are excluded from the funnel, tracked separately as "not yet
engaged" in the weekly trend instead.
"""

_ESCALATION_OWNER_MAP = {
    "Mentorship": "Mentorship",
    "IT": "IT",
    "Program Specific": "Development",
}


def _stage_bucket(status: str | None) -> str | None:
    if not status:
        return None
    if status in ("1 Identified", "2 Confirmed"):
        return None  # not yet in the funnel
    if status.startswith("3 Outreached") or status.startswith("4 Outreached"):
        return "Outreached"
    if status.startswith("5 Scheduled"):
        return "Scheduled"
    if status.startswith("6 Solutioning") or status.startswith("7 Solutioning"):
        return "Solutioning"
    if status.startswith("8 Monitoring"):
        return "Monitoring"
    if status.startswith("9 Closed"):
        return "Closed"
    return None


def _is_declined_outcome(status: str) -> bool:
    return any(
        kw in status
        for kw in ("Declined Support", "Resigning", "Mentor Declined", "Not Progressing")
    )


def compute_status_funnel(rows: list[dict]) -> dict[str, dict[str, int]]:
    """{stage: {on_track, escalated, declined}} for the 5 funnel stages."""
    funnel = {s: {"on_track": 0, "escalated": 0, "declined": 0} for s in
              ("Outreached", "Scheduled", "Solutioning", "Monitoring", "Closed")}
    for r in rows:
        status = r.get("optimization_support_status")
        stage = _stage_bucket(status)
        if stage is None:
            continue
        if stage == "Closed":
            funnel[stage]["declined" if _is_declined_outcome(status) else "on_track"] += 1
        elif "Escalated" in status:
            funnel[stage]["escalated"] += 1
        else:
            funnel[stage]["on_track"] += 1
    return funnel


def compute_escalations_by_owner(rows: list[dict]) -> dict[str, int]:
    counts = {"Development": 0, "IT": 0, "Mentorship": 0}
    for r in rows:
        status = r.get("optimization_support_status") or ""
        if not status.startswith("7 Solutioning (Escalated - "):
            continue
        suffix = status.removeprefix("7 Solutioning (Escalated - ").rstrip(")")
        owner = _ESCALATION_OWNER_MAP.get(suffix)
        if owner:
            counts[owner] += 1
    return counts


def _to_float(value) -> float | None:
    """The raw rad_onboarding dicts this module reads straight from cache_store (bypassing
    Pydantic's usual lax-mode string->float coercion) mix numeric and string representations of
    the same column across rows - same confirmed-live issue as
    ai_context_service._to_float - so every numeric read here needs explicit, failure-safe
    conversion rather than assuming a Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def scope_rows(rows: list[dict], scope: str) -> list[dict]:
    """Shared cohort-string filter for the two dashboard scopes this app computes stats for -
    extracted from what was previously duplicated inline in
    ai_context_service.generate_mvp_overview_narrative/generate_mvp_mammo_narrative, now also
    used by mvp_weekly_report_service so there's one definition, not two (or three)."""
    if scope == "mammo":
        return [r for r in rows if r.get("mvp_cohort") and "(Mammo)" in r["mvp_cohort"]]
    if scope == "overview":
        return [
            r for r in rows
            if r.get("mvp_cohort") and "(Mammo)" not in r["mvp_cohort"] and "(Ops or Self Referred)" not in r["mvp_cohort"]
        ]
    raise ValueError(f"unknown scope: {scope!r}")


def diff_counts(current: dict, previous: dict | None) -> dict:
    """Recursively diffs two same-shaped count dicts - handles both flat int-valued dicts
    (impact, escalations) and funnel's one-level-nested {stage: {on_track, escalated, declined}}
    shape. Returns the same shape with every leaf None when there's no prior snapshot to compare
    against (first-ever snapshot for a scope) - callers must render that as "no comparison yet",
    never as a fabricated zero delta."""
    result: dict = {}
    for key, value in current.items():
        prev_value = previous.get(key) if previous else None
        if isinstance(value, dict):
            result[key] = diff_counts(value, prev_value)
        else:
            result[key] = (value - prev_value) if prev_value is not None else None
    return result


# Confirmed live (2026-10-22) against tbl_mvp_rad_onboarding: drafting_captured_efficiency_
# change_pct ranges from -79% to +916%, full_mosaic_change_l30d_pct from -100% to +1724%, across
# only 7-11 of 643 rows - almost certainly tiny-denominator blowups (e.g. a radiologist with
# near-zero baseline reading minutes), not real efficiency gains. Left unfiltered, a single
# +1724% artifact gets classified "At/Above Baseline" alongside radiologists who genuinely
# recovered. 100% is not a scientific cutoff, just the point past which a "percent change" in
# this domain stops being a plausible real result - values beyond it are treated as
# insufficient_data, same as a missing value, never silently averaged or bucketed as real.
_IMPLAUSIBLE_PCT_MAGNITUDE = 100.0


def _is_implausible(value: float | None) -> bool:
    return value is not None and abs(value) > _IMPLAUSIBLE_PCT_MAGNITUDE


def compute_impact_breakdown(rows: list[dict]) -> dict[str, int]:
    """At/above baseline vs improving vs not-improving vs insufficient data, for radiologists
    who've progressed at least to Solutioning (i.e. genuinely "post-engagement")."""
    counts = {"post_engagement_rads": 0, "at_above_baseline": 0, "improving": 0, "not_improving": 0, "insufficient_data": 0}
    for r in rows:
        stage = _stage_bucket(r.get("optimization_support_status"))
        if stage not in ("Solutioning", "Monitoring", "Closed"):
            continue
        counts["post_engagement_rads"] += 1
        bl = _to_float(r.get("drafting_captured_efficiency_change_pct"))
        # efficiency_change_last_30d_pct is confirmed live (2026-10-21) to be 100% NULL across
        # the entire post-engagement population (0 of 510 rows) - full_mosaic_change_l30d_pct
        # is the rolling figure that's actually populated (427/510) and serves the same "how is
        # this radiologist doing right now" role.
        post = _to_float(r.get("full_mosaic_change_l30d_pct"))
        if bl is None or post is None or _is_implausible(bl) or _is_implausible(post):
            counts["insufficient_data"] += 1
        elif post >= 0:
            counts["at_above_baseline"] += 1
        elif post > bl:
            counts["improving"] += 1
        else:
            counts["not_improving"] += 1
    return counts
