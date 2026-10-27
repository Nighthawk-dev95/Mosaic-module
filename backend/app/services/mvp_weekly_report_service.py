"""Weekly briefing snapshots - plan item E-5.

Started life as the MVP Weekly Report: the feature that answers "can this replace the manual
Friday slide-building work" for the two MVP cohorts. It is button-triggered (not scheduled, per
the user's explicit choice), diffs this week's numbers against whatever snapshot was last
generated for the same scope, and writes a real two-part AI narrative grounded in those deltas.
History accumulates in `mosaic.mvp_weekly_snapshots` from the first click forward.

**What E-5 changed.** The two MVP cohorts were hardcoded in four places that had to agree and
had no way of noticing when they did not: a `_SCOPE_LABELS` dict here, a `^(overview|mammo)$`
regex on each of three routes, a `CHECK (scope IN ('overview','mammo'))` in the Postgres DDL,
and three MVP-shaped paragraph templates inside the narrative prompt. A scope is now declared
once, as a `BriefingScope` in `_SCOPES` below, and those four places read it.

**Three sections, no more, no less - and that is a storage constraint, not a design taste.**
`mosaic.mvp_weekly_snapshots` has exactly three JSON columns (`funnel`, `impact`,
`escalations`) and they already hold live MVP history. Renaming them to something scope-neutral
would mean migrating rows that are the only record of what the program looked like in past
weeks, for no behaviour change. So the columns stay, and a scope declares three sections that
are *positionally* bound to them. The names are MVP vocabulary preserved as storage slots;
`Section.label` is what anyone actually reads. The same reasoning is why this module and that
table keep their `mvp_` names: three routes, a table and a quarter of accumulated snapshots
point at them, and a rename buys nothing.

Adding a fourth section means a schema migration. Say so out loud rather than discovering it.

**A section must be a flat or one-level-nested dict of numbers.** `diff_counts` recurses one
level and subtracts leaves; a section carrying a list or a string would come back with a
`TypeError` at diff time, a week after it was added, inside a user-triggered request. The
contract is checked at import by `_validate_scopes()` as far as it can be (shape of the
declaration) and at generate time by `_check_section_shape` (shape of the computed values).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from app.data import mvp_context, mvp_dashboard_stats
from app.db import cache_store, postgres_client
from app.services import ai_context_service

# The three JSON columns on mosaic.mvp_weekly_snapshots, in the order `save_weekly_snapshot`
# takes them. A scope's sections are zipped against this, so the order here is load-bearing.
_SLOTS = ("funnel", "impact", "escalations")


@dataclass(frozen=True)
class Section:
    """One of the three persisted blocks of a briefing.

    `label` and `description` are what the narrative model is told this dict means - they are
    the whole reason a non-MVP scope can produce readable prose from the same prompt. A
    description that just restates the label ("the funnel is the funnel") produces generic
    narrative, which is the failure mode this feature exists to avoid.

    `compute` takes no arguments and returns the section's numbers. It closes over whatever its
    scope needs (a cohort filter, a ranking window) so that `generate_snapshot` stays scope-blind.
    """

    label: str
    description: str
    compute: Callable[[], dict]


@dataclass(frozen=True)
class BriefingScope:
    key: str
    label: str
    grounding: str
    sections: tuple[Section, Section, Section]


def _mvp_sections(scope_key: str) -> tuple[Section, Section, Section]:
    """The two MVP cohorts' sections - unchanged numbers, now declared rather than inlined.

    Each `compute` re-reads `mvp_rad_onboarding_raw` rather than closing over a row list captured
    at import: the cache is refreshed on a cycle this module does not control, and a snapshot
    generated from rows read at process start would be stale in a way nothing would show.
    """

    def _scoped() -> list[dict]:
        return mvp_dashboard_stats.scope_rows(cache_store.load("mvp_rad_onboarding_raw")[0] or [], scope_key)

    return (
        Section(
            label="Status funnel",
            description=(
                "radiologist counts by onboarding stage, each split on-track / escalated / declined"
            ),
            compute=lambda: mvp_dashboard_stats.compute_status_funnel(_scoped()),
        ),
        Section(
            label="Impact breakdown",
            description=(
                "among radiologists who have reached Solutioning or later, how many are at or "
                "above their pre-Mosaic baseline, improving toward it, not improving, or lack "
                "enough data to say"
            ),
            compute=lambda: mvp_dashboard_stats.compute_impact_breakdown(_scoped()),
        ),
        Section(
            label="Escalations by owning team",
            description="open Solutioning escalations, counted by the team that owns the fix",
            compute=lambda: mvp_dashboard_stats.compute_escalations_by_owner(_scoped()),
        ),
    )


# --------------------------------------------------------------------------------------------
# The enterprise Drafting scope - the first non-MVP briefing, and the reason E-5 was worth doing
# --------------------------------------------------------------------------------------------

_DRAFTING_GROUNDING = (
    "Mosaic AI Drafting is one of three Mosaic solutions (alongside Reporting and Capture). A "
    "radiologist reads an exam with a model-generated draft already in the report; the measure "
    "of the program is how much of the draftable volume is actually drafted. Volume that could "
    "have been drafted and was not is tracked in six categories, of which only two are workable "
    "by an operator - radiologists who were never enrolled, and enrolled radiologists who did "
    "not use the draft. The other leaks escalate elsewhere: practice enablement is a Deployment "
    "decision, uncovered procedures are a model-roadmap one, and volume not read on Mosaic at "
    "all is a Reporting adoption question. Units are TBWU (time-based work units), the "
    "enterprise's volume currency."
)

# The window and the ranking both come from one `rank()` call, deliberately. An independently
# computed "last 8 weeks" here would drift from the ranking's the moment the cache lagged a
# refresh - and the two would then describe different weeks in the same paragraph, which is
# exactly the class of error a weekly briefing is least able to survive.
_DRAFTING_CACHE: dict[str, object] = {}


def _drafting_ranking() -> dict:
    """One ranking per `generate_snapshot` call, shared by all three Drafting sections."""
    if "ranking" not in _DRAFTING_CACHE:
        from app.services import cache_service

        _DRAFTING_CACHE["ranking"] = cache_service.get_next_best_actions(weeks=8).model_dump()
    return _DRAFTING_CACHE["ranking"]  # type: ignore[return-value]


def _drafting_leakage() -> dict:
    """Enterprise TBWU by leakage category, over the ranking's own window.

    Summed from the raw `undrafted_analysis` rows rather than from the ranked worklist: the
    worklist deliberately excludes teams at or above the benchmark and teams below the minimum
    addressable volume, so adding its per-team columns up would report an enterprise funnel that
    is missing every team doing well. That number would fall every time a team improved.
    """
    from app.services import next_best_action_service

    ranking = _drafting_ranking()
    start, end = ranking.get("window_start"), ranking.get("window_end")
    rows = cache_store.load("undrafted_analysis")[0] or []

    categories = (
        next_best_action_service.DRAFTED,
        next_best_action_service.NOT_ENROLLED,
        next_best_action_service.NOT_DRAFTED_WORKFLOW,
        next_best_action_service.PRACTICE_NOT_ENABLED,
        next_best_action_service.PROCEDURE_NOT_COVERED,
        next_best_action_service.NOT_ON_MOSAIC,
    )
    totals = {c: 0.0 for c in categories}
    for row in rows:
        week = str(row.get("week_start"))
        # Same admission rule as `rank()`: undated rows are dropped, not bucketed. "None" sorts
        # after every ISO date, so admitting them would quietly add undated volume to the window.
        if not start or not end or week == "None" or week < str(start) or week > str(end):
            continue
        category = row.get("category") or ""
        if category in totals:
            totals[category] += float(row.get("tbwu") or 0.0)
    return {c: round(v) for c, v in totals.items()}


def _drafting_unlock() -> dict:
    """What the ranked worklist says is available, and how much of the field it covers.

    `teams_ranked` sits next to `expected_unlock_tbwu` on purpose: the unlock is a sum over
    ranked teams only, so a week where it falls because teams reached the benchmark reads
    identically to one where it falls because the cache lost rows - unless the team count is
    visible beside it.
    """
    ranking = _drafting_ranking()
    return {
        "expected_unlock_tbwu": round(float(ranking.get("total_expected_unlock_tbwu") or 0.0)),
        "teams_ranked": len(ranking.get("actions") or []),
        "teams_in_benchmark": int(ranking.get("benchmark_team_count") or 0),
        "benchmark_draft_rate_pct": round(float(ranking.get("benchmark_draft_rate") or 0.0) * 100),
        "teams_below_volume_threshold": int(ranking.get("excluded_low_volume_teams") or 0),
    }


def _drafting_escalations() -> dict:
    """The leaks nobody on the operator worklist can close, by the owner they escalate to.

    Deliberately the same slot the MVP scopes use for escalations, and for the same reason: it
    is the block of the briefing that names work for someone other than the reader.
    """
    from app.services import next_best_action_service

    leakage = _drafting_leakage()
    return {
        "Deployment (practice not enabled)": leakage[next_best_action_service.PRACTICE_NOT_ENABLED],
        "Model roadmap (procedure not covered)": leakage[next_best_action_service.PROCEDURE_NOT_COVERED],
        "Reporting adoption (not read on Mosaic)": leakage[next_best_action_service.NOT_ON_MOSAIC],
    }


_SCOPES: dict[str, BriefingScope] = {
    "overview": BriefingScope(
        key="overview",
        label="Drafting/Capture",
        grounding=mvp_context.PROGRAM_NARRATIVE,
        sections=_mvp_sections("overview"),
    ),
    "mammo": BriefingScope(
        key="mammo",
        label="Mammo Screening",
        grounding=mvp_context.PROGRAM_NARRATIVE,
        sections=_mvp_sections("mammo"),
    ),
    "drafting": BriefingScope(
        key="drafting",
        label="Enterprise AI Drafting",
        grounding=_DRAFTING_GROUNDING,
        sections=(
            Section(
                label="Draftable volume by outcome",
                description=(
                    "TBWU of draftable volume in each of the six leakage categories across the "
                    "whole enterprise, over the last eight weeks present in the data"
                ),
                compute=_drafting_leakage,
            ),
            Section(
                label="Addressable unlock",
                description=(
                    "TBWU the ranked operator worklist expects to unlock if every team behind "
                    "the peer benchmark reached it, with the size of the peer field it is "
                    "measured against"
                ),
                compute=_drafting_unlock,
            ),
            Section(
                label="Escalations by owner",
                description=(
                    "TBWU behind the three leaks an operator cannot close, by the team that can"
                ),
                compute=_drafting_escalations,
            ),
        ),
    ),
}


def _validate_scopes() -> None:
    """Fail at import, not on a Friday afternoon inside someone's button click."""
    for key, scope in _SCOPES.items():
        assert scope.key == key, f"scope {key!r} declares key {scope.key!r}"
        assert len(scope.sections) == len(_SLOTS), (
            f"scope {key!r} declares {len(scope.sections)} sections; the storage table has "
            f"{len(_SLOTS)} JSON columns and a fourth needs a schema migration"
        )
        assert scope.grounding.strip(), f"scope {key!r} has no grounding text to narrate from"
        for section in scope.sections:
            assert section.label.strip() and section.description.strip(), (
                f"scope {key!r} has a section with no label or description - the narrative "
                f"prompt has nothing to call it, and the prose goes generic"
            )


_validate_scopes()


def scope_keys() -> tuple[str, ...]:
    """The scopes that exist, for the routes to validate against.

    `app/routes/mosaic.py` builds its query-parameter pattern from this rather than repeating
    the list, so a scope added here is reachable immediately and one removed stops being
    accepted - the two cannot disagree.
    """
    return tuple(_SCOPES)


def get_scope(key: str) -> BriefingScope:
    scope = _SCOPES.get(key)
    if scope is None:
        raise ValueError(f"unknown scope: {key!r} (known: {', '.join(_SCOPES)})")
    return scope


def _friday_of(d: date) -> date:
    """Most recent Friday on/before d - matches the real program's own Friday cadence (the
    10/16/2026 weekly update was itself sent on a Friday)."""
    # Monday=0 ... Friday=4 ... Sunday=6
    days_since_friday = (d.weekday() - 4) % 7
    return d - timedelta(days=days_since_friday)


def _check_section_shape(scope_key: str, section: Section, values: dict) -> None:
    """A section must diff. Catch a bad shape here, where the message can say whose fault it is.

    `diff_counts` recurses one level and subtracts leaves. A section returning a list, a string
    or a three-deep dict raises somewhere inside it instead, with a message naming neither the
    scope nor the section - a week after whoever added it stopped looking.
    """
    if not isinstance(values, dict):
        raise TypeError(f"{scope_key}/{section.label}: section computed {type(values).__name__}, not a dict")
    for key, value in values.items():
        if isinstance(value, dict):
            for inner_key, inner in value.items():
                if not isinstance(inner, (int, float)) or isinstance(inner, bool):
                    raise TypeError(
                        f"{scope_key}/{section.label}: {key}.{inner_key} is "
                        f"{type(inner).__name__}; sections nest at most one level and hold numbers"
                    )
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(
                f"{scope_key}/{section.label}: {key} is {type(value).__name__}; sections hold "
                f"numbers (or one level of dicts of numbers), so week-over-week deltas exist"
            )


def _sections_view(scope_spec: BriefingScope, computed: list[dict], deltas: dict) -> list[dict]:
    """The scope-neutral view of the three blocks: what they are called, not what they mean.

    Shared by the generate path and the read path deliberately. These two used to be the same
    four lines written twice, which is how a renderer ends up showing one set of section labels
    after a regenerate and a different set after a page reload.
    """
    return [
        {"slot": slot, "label": section.label, "description": section.description,
         "values": values, "deltas": deltas[slot]}
        for slot, section, values in zip(_SLOTS, scope_spec.sections, computed)
    ]


def read_snapshots(scope: str, limit: int) -> list[dict]:
    """Persisted snapshots, newest week first, with the scope-neutral `sections` view attached.

    Purely additive: the three slot keys stay on the row exactly as Postgres holds them, so the
    MVP pages that read `funnel`/`impact`/`escalations` by name are unaffected. What this adds is
    the half a generic renderer needs and the storage table does not hold - the scope's label and
    its per-section labels and descriptions, which live in `_SCOPES`, not in the database.

    Reads one row beyond the window so the oldest row returned still has a predecessor to diff
    against. Without it a `limit=1` read always reports `has_previous=False` and null deltas -
    true of the window, false of the data, and indistinguishable from a first-ever snapshot.
    """
    scope_spec = get_scope(scope)
    rows = postgres_client.get_weekly_snapshots(scope, limit + 1)
    out: list[dict] = []
    for index, row in enumerate(rows[:limit]):
        previous = rows[index + 1] if index + 1 < len(rows) else None
        computed = [row[slot] for slot in _SLOTS]
        deltas = {
            slot: mvp_dashboard_stats.diff_counts(values, previous[slot] if previous else None)
            for slot, values in zip(_SLOTS, computed)
        }
        out.append({
            **row,
            "scope_label": scope_spec.label,
            "sections": _sections_view(scope_spec, computed, deltas),
            "deltas": deltas,
            "has_previous": previous is not None,
        })
    return out


def generate_snapshot(scope: str) -> dict:
    scope_spec = get_scope(scope)

    # Per-call memo for anything a scope's sections share (the Drafting ranking, which all three
    # of its sections read). Cleared up front rather than at the end so an exception mid-generate
    # cannot leave a stale ranking behind for the next click.
    _DRAFTING_CACHE.clear()

    computed: list[dict] = []
    for section in scope_spec.sections:
        values = section.compute()
        _check_section_shape(scope, section, values)
        computed.append(values)

    week_ending = _friday_of(date.today())
    existing = postgres_client.get_weekly_snapshots(scope, limit=5)
    previous = next((s for s in existing if s["week_ending"] != week_ending.isoformat()), None)
    has_previous = previous is not None

    # Deltas are keyed by storage slot, not by label: this is the dict that goes back to a
    # frontend which has always read `deltas.funnel`, and the MVP pages still do.
    deltas = {
        slot: mvp_dashboard_stats.diff_counts(values, previous[slot] if previous else None)
        for slot, values in zip(_SLOTS, computed)
    }

    narrative = ai_context_service.generate_weekly_report_narrative(
        scope_spec.label,
        scope_spec.grounding,
        sections=[
            (section.label, section.description, values, deltas[slot])
            for section, values, slot in zip(scope_spec.sections, computed, _SLOTS)
        ],
        has_previous=has_previous,
    )

    generated_at = datetime.now(timezone.utc)
    postgres_client.save_weekly_snapshot(
        scope, week_ending, *computed,
        narrative["key_insights"], narrative["focus_next_week"], generated_at,
    )

    return {
        "scope": scope,
        "scope_label": scope_spec.label,
        "week_ending": week_ending.isoformat(),
        # The three slot keys are kept verbatim because the MVP pages read them by name and have
        # done since before scopes were a thing. `sections` is the scope-neutral view of the
        # same three blocks, carrying the labels a generic renderer needs; new surfaces read it.
        **dict(zip(_SLOTS, computed)),
        "sections": _sections_view(scope_spec, computed, deltas),
        "deltas": deltas,
        "key_insights": narrative["key_insights"],
        "focus_next_week": narrative["focus_next_week"],
        "has_previous": has_previous,
        "generated_at": generated_at.isoformat(),
    }
