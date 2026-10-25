"""Honest, live-recomputed checks on whether the MVP Impact classification (mvp_dashboard_stats.
compute_impact_breakdown) can actually be trusted as a before/after comparison - not a causal-
inference engine, just the specific things a rigorous read of this exact data surfaced as real
limitations (confirmed live 2026-10-22):

1. A handful of implausible (>100%-magnitude) efficiency-change values exist in the same fields
   the Impact classification reads - compute_impact_breakdown now excludes them as
   insufficient_data (see its own _IMPLAUSIBLE_PCT_MAGNITUDE), this module just reports how many.
2. mvp_target_outreach_week looked like it could support a staggered-rollout time-since-treatment
   analysis, but a live check killed that: radiologists whose target week is still in the future
   are, almost always, already active past "Outreached" - the field is a stale planning date that
   doesn't get updated once a case moves, not a reliable "has this person been treated yet"
   signal. This function quantifies that contamination rate live, rather than asserting it once
   and letting it go stale.
3. Funnel stages aren't necessarily comparable on starting severity - a later-stage population
   that started out much worse (or better) than an earlier-stage one would make any naive
   stage-to-stage comparison a selection-bias artifact, not a program effect. Reported as a
   median (not mean, to resist the same outlier problem as #1) per stage.

Feeds the MVP Overview/Mammo "Methodology Check" panel - the point of that panel is to tell a
viewer what this data can and can't support, not to make the existing Impact numbers look more
authoritative.
"""

from app.data.mvp_dashboard_stats import _is_implausible, _stage_bucket, _to_float

_EFFICIENCY_CHANGE_FIELDS = ("drafting_captured_efficiency_change_pct", "full_mosaic_change_l30d_pct")


def compute_outlier_summary(rows: list[dict]) -> dict:
    """Per-field count of rows hitting the implausible-magnitude guard, plus the total distinct
    radiologists affected (a row can hit the guard on one field, both, or neither)."""
    per_field = {f: 0 for f in _EFFICIENCY_CHANGE_FIELDS}
    affected_npis: set = set()
    for r in rows:
        hit_any = False
        for field in _EFFICIENCY_CHANGE_FIELDS:
            value = _to_float(r.get(field))
            if _is_implausible(value):
                per_field[field] += 1
                hit_any = True
        if hit_any:
            affected_npis.add(r.get("npi"))
    return {
        "per_field": per_field,
        "total_radiologists_affected": len(affected_npis),
        "total_radiologists": len(rows),
    }


def compute_outreach_week_reliability(rows: list[dict]) -> dict:
    """Takes rows already annotated with a `_outreach_week_is_future` boolean (see
    compute_methodology_check, which does the date parsing once and calls this) rather than
    parsing dates itself - keeps the date-parsing logic in one place. Of the radiologists whose
    target outreach week is still in the future, how many are already past "Outreached" - if
    this is high, the field is a stale planning date, not a reliable treatment-timing signal.
    contamination_rate is None (not zero) when there are no future-dated rows to check at all."""
    future_dated = [r for r in rows if r.get("_outreach_week_is_future")]
    if not future_dated:
        return {"future_dated_count": 0, "already_past_outreached_count": 0, "contamination_rate": None}
    already_active = sum(
        1 for r in future_dated if _stage_bucket(r.get("optimization_support_status")) not in (None, "Outreached")
    )
    return {
        "future_dated_count": len(future_dated),
        "already_past_outreached_count": already_active,
        "contamination_rate": already_active / len(future_dated),
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def compute_baseline_severity_by_stage(rows: list[dict]) -> dict:
    """Median (not mean) baseline drafting_captured_efficiency_change_pct per funnel stage,
    excluding implausible values - lets a viewer see whether radiologists further along the
    funnel started out systematically more or less severe than those earlier in it, a real
    selection-bias check on any stage-to-stage comparison (including the funnel chart itself)."""
    by_stage: dict[str, list[float]] = {}
    for r in rows:
        stage = _stage_bucket(r.get("optimization_support_status"))
        if stage is None:
            continue
        bl = _to_float(r.get("drafting_captured_efficiency_change_pct"))
        if bl is None or _is_implausible(bl):
            continue
        by_stage.setdefault(stage, []).append(bl)
    return {
        stage: {"median_baseline_pct": _median(values), "n": len(values)}
        for stage, values in by_stage.items()
    }


def _parse_outreach_date(value: str | None):
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return None


def compute_methodology_check(rows: list[dict]) -> dict:
    """Combines all three checks, using the system clock for "today" (mvp_target_outreach_week
    is a 'M/d/yyyy'-formatted string, same format this parses)."""
    from datetime import datetime

    today = datetime.now()
    annotated = [
        {**r, "_outreach_week_is_future": bool((target := _parse_outreach_date(r.get("mvp_target_outreach_week"))) and target > today)}
        for r in rows
    ]

    return {
        "outlier_summary": compute_outlier_summary(rows),
        "outreach_week_reliability": compute_outreach_week_reliability(annotated),
        "baseline_severity_by_stage": compute_baseline_severity_by_stage(rows),
    }
