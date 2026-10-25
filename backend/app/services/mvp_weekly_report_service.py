"""Generates and persists the MVP Weekly Report snapshot - the feature that actually answers
"can this replace the manual Friday slide-building work": a button-triggered (not scheduled,
per the user's explicit choice) computation of this week's Overview/Mammo stats, diffed against
whatever snapshot was last generated for that scope, with a real two-part AI narrative grounded
in those deltas. Everything computed here is persisted via app/db/postgres_client.py's
mosaic.mvp_weekly_snapshots table, so history accumulates from the first click forward.
"""

from datetime import date, datetime, timedelta, timezone

from app.data import mvp_context, mvp_dashboard_stats
from app.db import cache_store, postgres_client
from app.services import ai_context_service

_SCOPE_LABELS = {"overview": "Drafting/Capture", "mammo": "Mammo Screening"}


def _friday_of(d: date) -> date:
    """Most recent Friday on/before d - matches the real program's own Friday cadence (the
    10/16/2026 weekly update was itself sent on a Friday)."""
    # Monday=0 ... Friday=4 ... Sunday=6
    days_since_friday = (d.weekday() - 4) % 7
    return d - timedelta(days=days_since_friday)


def generate_snapshot(scope: str) -> dict:
    if scope not in _SCOPE_LABELS:
        raise ValueError(f"unknown scope: {scope!r}")

    rows = cache_store.load("mvp_rad_onboarding_raw")[0] or []
    scoped = mvp_dashboard_stats.scope_rows(rows, scope)

    funnel = mvp_dashboard_stats.compute_status_funnel(scoped)
    impact = mvp_dashboard_stats.compute_impact_breakdown(scoped)
    escalations = mvp_dashboard_stats.compute_escalations_by_owner(scoped)

    week_ending = _friday_of(date.today())
    existing = postgres_client.get_weekly_snapshots(scope, limit=5)
    previous = next((s for s in existing if s["week_ending"] != week_ending.isoformat()), None)
    has_previous = previous is not None

    deltas = {
        "funnel": mvp_dashboard_stats.diff_counts(funnel, previous["funnel"] if previous else None),
        "impact": mvp_dashboard_stats.diff_counts(impact, previous["impact"] if previous else None),
        "escalations": mvp_dashboard_stats.diff_counts(escalations, previous["escalations"] if previous else None),
    }

    narrative = ai_context_service.generate_weekly_report_narrative(
        _SCOPE_LABELS[scope], mvp_context.PROGRAM_NARRATIVE, funnel, impact, escalations, deltas, has_previous
    )

    generated_at = datetime.now(timezone.utc)
    postgres_client.save_weekly_snapshot(
        scope, week_ending, funnel, impact, escalations,
        narrative["key_insights"], narrative["focus_next_week"], generated_at,
    )

    return {
        "scope": scope,
        "week_ending": week_ending.isoformat(),
        "funnel": funnel,
        "impact": impact,
        "escalations": escalations,
        "deltas": deltas,
        "key_insights": narrative["key_insights"],
        "focus_next_week": narrative["focus_next_week"],
        "has_previous": has_previous,
        "generated_at": generated_at.isoformat(),
    }
