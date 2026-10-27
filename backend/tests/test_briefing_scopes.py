"""Pins the weekly-briefing scope registry - plan item E-5.

Run from the `backend/` directory, with or without pytest:

    python tests/test_briefing_scopes.py
    python -m pytest tests/test_briefing_scopes.py

Before E-5 the two MVP cohorts were hardcoded in four places that had to agree and had no way to
notice when they did not: `_SCOPE_LABELS` in the service, a `^(overview|mammo)$` regex on each of
three routes, a `CHECK (scope IN ('overview','mammo'))` in the Postgres DDL, and three MVP-shaped
sentences inside the narrative prompt. The first three fail loudly; the fourth does not, and is
the one this file spends the most effort on. A non-MVP program handed to the old prompt had its
numbers introduced to the model as "radiologist counts by onboarding stage" and "escalations by
owning team", and the model wrote fluent, confident prose about a funnel that did not exist.

So the assertions here are, in order of how badly each would fail unnoticed:

  1. The narrative prompt carries each scope's *own* descriptions and no MVP vocabulary.
  2. Every scope's sections produce diffable shapes - a list or a string in a section surfaces
     as a `TypeError` inside `diff_counts` on a Friday, not at the point of the mistake.
  3. The MVP response keys the existing frontend reads are unchanged.
  4. The route pattern and the registry cannot disagree.

Offline: Postgres and the serving endpoint are both monkeypatched. What is under test is the
scope plumbing, not the LLM and not the database.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data import mvp_context, mvp_dashboard_stats  # noqa: E402
from app.db import cache_store, postgres_client  # noqa: E402
from app.services import ai_context_service, mvp_weekly_report_service as briefing  # noqa: E402

# Two MVP onboarding rows, enough for the funnel/impact/escalation computations to be non-empty.
_MVP_ROWS = [
    {
        "mvp_cohort": "2026 Q1 (Drafting)",
        "optimization_support_status": "7 Solutioning (Escalated - Hardware)",
        "drafting_captured_efficiency_change_pct": -10.0,
        "full_mosaic_change_l30d_pct": -2.0,
    },
    {
        "mvp_cohort": "2026 Q1 (Mammo)",
        "optimization_support_status": "9 Monitoring",
        "drafting_captured_efficiency_change_pct": -5.0,
        "full_mosaic_change_l30d_pct": 3.0,
    },
]

# Leakage rows at `undrafted_analysis`'s cached grain, one team.
#
# Nine distinct dated weeks, because the window is the last eight weeks *present in the data* -
# not the last eight weeks of the calendar (`rank()`, and the comment above its `all_weeks`).
# A fixture with fewer than nine weeks cannot tell a correct window from no window at all: every
# row it holds is inside the window either way, and a `_drafting_leakage` that ignored the
# boundary entirely would pass. The ninth-oldest week carries a deliberately huge number so the
# failure, if it comes back, is unmistakable rather than a rounding-sized discrepancy.
_UNDRAFTED_ROWS = [
    # Week 1 of 9: falls out of the eight-week window. Must not be counted.
    {"week_start": "2026-08-25", "team": "Boca Radiology", "category": "Drafted", "tbwu": 9999.0, "exam_count": 1},
    # Weeks 2-7: inside the window, and proof that it is a window and not just "the last two weeks".
    *[
        {"week_start": wk, "team": "Boca Radiology",
         "category": "Draftable - Not Drafted (Workflow)", "tbwu": 1.0, "exam_count": 1}
        for wk in ("2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06")
    ],
    # Weeks 8-9: the recent detail the assertions below are written against.
    {"week_start": "2026-10-13", "team": "Boca Radiology", "category": "Drafted", "tbwu": 100.0, "exam_count": 10},
    {"week_start": "2026-10-13", "team": "Boca Radiology", "category": "Draftable - Rad Not Enrolled", "tbwu": 40.0, "exam_count": 4},
    {"week_start": "2026-10-13", "team": "Boca Radiology", "category": "Procedure Not Covered", "tbwu": 25.0, "exam_count": 2},
    {"week_start": "2026-10-20", "team": "Boca Radiology", "category": "Drafted", "tbwu": 60.0, "exam_count": 6},
    {"week_start": "2026-10-20", "team": "Boca Radiology", "category": "Practice Not Enabled for Model", "tbwu": 15.0, "exam_count": 1},
    # Undated: dropped rather than bucketed, same rule `rank()` applies. "None" sorts after every
    # ISO date, so a naive window would admit this as the most recent week.
    {"week_start": None, "team": "Boca Radiology", "category": "Drafted", "tbwu": 7777.0, "exam_count": 1},
]


class _Patch:
    """Make `generate_snapshot` fully offline and record what the narrative prompt was given.

    Patches four seams: the two cache reads, both Postgres calls, and the narrative generator.
    The narrative is replaced rather than letting it fail into its own fallback - the whole point
    is to inspect the arguments it *would* have prompted with.
    """

    def __init__(self, previous: dict | None = None):
        self.previous, self.captured = previous, {}

    def __enter__(self):
        self._orig = (
            cache_store.load,
            postgres_client.get_weekly_snapshots,
            postgres_client.save_weekly_snapshot,
            ai_context_service.generate_weekly_report_narrative,
            briefing.ai_context_service.generate_weekly_report_narrative,
        )

        def _load(name):
            if name == "mvp_rad_onboarding_raw":
                return (_MVP_ROWS, "2026-10-26")
            if name == "undrafted_analysis":
                return (_UNDRAFTED_ROWS, "2026-10-26")
            return (None, None)

        def _narrative(scope_label, grounding, sections, has_previous):
            self.captured = {
                "scope_label": scope_label,
                "grounding": grounding,
                "sections": list(sections),
                "has_previous": has_previous,
            }
            return {"key_insights": "ki", "focus_next_week": "fnw"}

        def _save(*args, **kwargs):
            self.captured["saved"] = args
            return True

        cache_store.load = _load
        postgres_client.get_weekly_snapshots = lambda scope, limit=12: ([self.previous] if self.previous else [])
        postgres_client.save_weekly_snapshot = _save
        ai_context_service.generate_weekly_report_narrative = _narrative
        briefing.ai_context_service.generate_weekly_report_narrative = _narrative
        return self

    def __exit__(self, *exc):
        (
            cache_store.load,
            postgres_client.get_weekly_snapshots,
            postgres_client.save_weekly_snapshot,
            ai_context_service.generate_weekly_report_narrative,
            briefing.ai_context_service.generate_weekly_report_narrative,
        ) = self._orig
        return False


def test_every_scope_generates_without_touching_mvp_specific_assumptions():
    """The headline claim: a scope that is not an MVP cohort produces a snapshot."""
    for key in briefing.scope_keys():
        with _Patch() as p:
            result = briefing.generate_snapshot(key)
        assert result["scope"] == key
        assert len(result["sections"]) == 3, f"{key} produced {len(result['sections'])} sections"
        assert p.captured, f"{key} never reached the narrative generator"


def test_the_prompt_describes_each_scope_in_its_own_words():
    """The regression that would not have announced itself.

    The old prompt hardcoded "radiologist counts by stage", "radiologists who've reached
    Solutioning or later" and "escalations by owning team" around whatever three dicts it was
    handed. Pointed at enterprise Drafting, it introduced TBWU leakage totals as an MVP
    onboarding funnel and the model wrote fluent prose about stages nobody is in. Nothing would
    have failed; the text simply would have been wrong, weekly, in a leadership report.
    """
    with _Patch() as p:
        briefing.generate_snapshot("drafting")

    labels = [label for label, _, _, _ in p.captured["sections"]]
    descriptions = " ".join(d for _, d, _, _ in p.captured["sections"]).lower()

    assert labels == ["Draftable volume by outcome", "Addressable unlock", "Escalations by owner"]
    assert "tbwu" in descriptions and "leakage" in descriptions, (
        "the Drafting scope's numbers reached the model without being described as TBWU leakage"
    )
    for mvp_word in ("solutioning", "onboarding stage", "radiologist counts by"):
        assert mvp_word not in descriptions, (
            f"MVP vocabulary ({mvp_word!r}) described an enterprise Drafting block - this is the "
            f"exact failure E-5 exists to prevent, and it produces confident wrong prose rather "
            f"than an error"
        )
    assert p.captured["scope_label"] == "Enterprise AI Drafting"
    assert "Mosaic Value Project" not in p.captured["grounding"], (
        "the Drafting scope was grounded in the MVP program narrative"
    )


def test_each_section_carries_its_own_deltas_next_to_its_own_numbers():
    """The model must not have to re-pair deltas with blocks by name.

    The old prompt listed all three sections, then all three delta dicts in a trailing sentence
    keyed `funnel`/`impact`/`escalations`. That works while the names mean something; for a scope
    whose blocks are not a funnel it asks the model to match four unlabelled dicts by position.
    """
    previous = {
        "week_ending": "2026-10-16",
        "funnel": {"Drafted": 100, "Draftable - Rad Not Enrolled": 50, "Draftable - Not Drafted (Workflow)": 0,
                   "Practice Not Enabled for Model": 10, "Procedure Not Covered": 20, "Not Read on Mosaic": 0},
        "impact": {},
        "escalations": {},
    }
    with _Patch(previous=previous) as p:
        briefing.generate_snapshot("drafting")

    first_label, _, first_values, first_deltas = p.captured["sections"][0]
    assert first_label == "Draftable volume by outcome"
    assert first_deltas.keys() == first_values.keys(), (
        "a section's deltas did not cover its own values - the model would be shown a change "
        "dict that does not line up with the numbers above it"
    )
    assert first_deltas["Drafted"] == first_values["Drafted"] - 100
    assert p.captured["has_previous"] is True


def test_a_first_ever_snapshot_reports_no_comparison_rather_than_a_zero():
    """None, not 0. A fabricated zero delta reads as "nothing changed this week"."""
    with _Patch(previous=None) as p:
        briefing.generate_snapshot("drafting")
    _, _, _, deltas = p.captured["sections"][0]
    assert set(deltas.values()) == {None}, f"first-ever snapshot invented deltas: {deltas}"
    assert p.captured["has_previous"] is False


def test_the_drafting_leakage_respects_the_rankings_own_window():
    """One window, not two - and the out-of-window rows are large enough to prove it.

    `_drafting_leakage` sums raw rows; the window comes off the ranking. If it computed its own
    "last 8 weeks" the two would drift the moment the cache lagged a refresh, and the briefing
    would describe a funnel from different weeks than the unlock figure beside it.
    """
    with _Patch() as p:
        result = briefing.generate_snapshot("drafting")

    leakage = result["funnel"]
    assert leakage["Drafted"] == 160, (
        f"expected 100 + 60 from the two most recent weeks, got {leakage['Drafted']} - the 9,999 "
        f"TBWU row from the ninth-oldest week, or the 7,777 undated row, entered the window"
    )
    assert leakage["Draftable - Not Drafted (Workflow)"] == 6, (
        "the six middle weeks of the window were not summed - the leakage is reading a shorter "
        "window than the ranking beside it"
    )
    assert leakage["Draftable - Rad Not Enrolled"] == 40
    assert leakage["Not Read on Mosaic"] == 0, "a category with no rows must report 0, not vanish"
    assert len(leakage) == 6, "the six-category taxonomy lost or gained a category"
    assert p.captured  # the narrative still ran


def test_the_window_is_the_same_set_of_weeks_the_ranking_ranked():
    """`rank()` tests set membership in the last N weeks; `_drafting_leakage` tests a date range
    between the window's reported endpoints. Those two are only equivalent because the set is a
    contiguous suffix of the sorted weeks - a week inside the range is either in the set or has
    no rows at all. Asserted rather than assumed, because a future change to how `rank()` picks
    its window (say, dropping weeks under a volume floor) would break the equivalence silently,
    and the briefing would then sum weeks the unlock figure beside it had excluded.
    """
    from app.services import cache_service

    with _Patch():
        ranking = cache_service.get_next_best_actions(weeks=8).model_dump()
        dated = sorted({str(r["week_start"]) for r in _UNDRAFTED_ROWS
                        if r.get("week_start") and str(r["week_start"]) != "None"})
        in_range = [w for w in dated if str(ranking["window_start"]) <= w <= str(ranking["window_end"])]

    assert len(dated) == 9, "the fixture stopped having more weeks than the window holds"
    assert in_range == dated[-8:], (
        f"the range the leakage sums ({in_range}) is not the set of weeks the ranking ranked "
        f"({dated[-8:]})"
    )


def test_escalations_name_an_owner_other_than_the_reader():
    """Same slot, same job, across scopes: the block that is work for somebody else."""
    with _Patch():
        result = briefing.generate_snapshot("drafting")
    owners = result["escalations"]
    assert owners["Model roadmap (procedure not covered)"] == 25
    assert owners["Deployment (practice not enabled)"] == 15
    assert all(v >= 0 for v in owners.values())


def test_the_offline_fallback_names_this_scopes_blocks_and_not_mvps():
    """The fallback is read exactly when something else has already failed.

    It used to be the MVP dashboard's string - "see the status funnel and impact breakdown
    above" - which on the enterprise Drafting briefing points at two blocks that are not on the
    page. It renders only when the serving endpoint is unreachable, so nothing routine would
    have caught it. The real local run that surfaced it had no model-serving scope on its token.
    """
    drafting = [(label, "d", {}, {}) for label in
                ("Draftable volume by outcome", "Addressable unlock", "Escalations by owner")]
    text = ai_context_service._weekly_report_fallback(drafting)
    assert "Draftable volume by outcome" in text and "Escalations by owner" in text
    assert "status funnel" not in text and "impact breakdown" not in text, (
        f"the Drafting fallback still sends the reader to MVP blocks: {text!r}"
    )

    mvp = [(label, "d", {}, {}) for label in
           ("Status funnel", "Impact breakdown", "Escalations by owning team")]
    assert "Status funnel" in ai_context_service._weekly_report_fallback(mvp)

    # Degenerate shapes: a fallback that raises defeats its own purpose, and the `except` arm
    # that calls it is the one place a raise cannot be absorbed.
    assert ai_context_service._weekly_report_fallback([])
    assert "Only block" in ai_context_service._weekly_report_fallback([("Only block", "d", {}, {})])


def test_a_narrative_failure_still_returns_both_halves():
    """Fail-closed, not fail-empty: a briefing with a blank insights field reads as "nothing
    happened this week", which is a different claim from "the model was unreachable"."""
    with _Patch():
        sections = [(s.label, s.description, {}, {}) for s in briefing.get_scope("drafting").sections]
    result = ai_context_service.generate_weekly_report_narrative(
        "Enterprise AI Drafting", "grounding", sections=sections, has_previous=False,
    )
    assert result["key_insights"].strip() and result["focus_next_week"].strip()
    assert set(result) == {"key_insights", "focus_next_week"}


def test_the_mvp_response_keys_the_frontend_already_reads_are_unchanged():
    """E-5 must be invisible to the two MVP pages. They read these keys by name today."""
    with _Patch():
        result = briefing.generate_snapshot("overview")
    for key in ("scope", "week_ending", "funnel", "impact", "escalations", "deltas",
                "key_insights", "focus_next_week", "has_previous", "generated_at"):
        assert key in result, f"the MVP weekly-report response lost {key!r}"
    assert set(result["deltas"]) == {"funnel", "impact", "escalations"}
    assert "Outreached" in result["funnel"], "the MVP funnel stopped being the MVP funnel"


def test_the_mvp_scopes_still_filter_to_their_own_cohort():
    """Both MVP scopes read the same raw rows; the cohort string is the only thing separating
    them, and a generalization that dropped the filter would show identical numbers for both."""
    with _Patch():
        overview = briefing.generate_snapshot("overview")
        mammo = briefing.generate_snapshot("mammo")
    assert overview["funnel"] != mammo["funnel"], (
        "the two MVP cohorts produced the same funnel - the scope filter stopped being applied"
    )


def test_the_three_sections_are_stored_in_slot_order():
    """`save_weekly_snapshot` is positional. A section list that reached it reordered would write
    the unlock numbers into the funnel column, and nothing would complain until a week later when
    the diff compared unrelated dicts."""
    with _Patch() as p:
        result = briefing.generate_snapshot("drafting")
    scope, _week, funnel, impact, escalations = p.captured["saved"][:5]
    assert scope == "drafting"
    assert funnel == result["funnel"] and impact == result["impact"] and escalations == result["escalations"]


def test_a_section_that_cannot_be_diffed_is_rejected_where_the_mistake_is():
    """A list or a string in a section raises inside `diff_counts` otherwise - a week later, in a
    user-triggered request, with a message naming neither the scope nor the section."""
    bad = briefing.Section(label="Bad", description="d", compute=lambda: {"a": ["not", "a", "number"]})
    try:
        briefing._check_section_shape("drafting", bad, bad.compute())
    except TypeError as exc:
        assert "drafting/Bad" in str(exc) and "a is list" in str(exc), f"unhelpful message: {exc}"
    else:
        raise AssertionError("a section holding a list was accepted")

    nested_ok = briefing.Section(label="OK", description="d", compute=lambda: {"s": {"on_track": 1}})
    briefing._check_section_shape("overview", nested_ok, nested_ok.compute())  # must not raise


def test_a_bool_is_not_a_number_here():
    """`isinstance(True, int)` is True in Python, so a flag slips through a naive numeric check
    and then subtracts into 1 or 0 in the week-over-week diff, rendering as a real change."""
    flag = briefing.Section(label="Flag", description="d", compute=lambda: {"enabled": True})
    try:
        briefing._check_section_shape("drafting", flag, flag.compute())
    except TypeError as exc:
        assert "bool" in str(exc)
    else:
        raise AssertionError("a boolean was accepted as a section value and would diff as 1/0")


def test_every_declared_scope_passes_its_own_shape_check():
    """Run the real compute functions through the real validator - the import-time
    `_validate_scopes` can only check the declaration, not what the callables return."""
    with _Patch():
        for key in briefing.scope_keys():
            scope = briefing.get_scope(key)
            for section in scope.sections:
                briefing._check_section_shape(key, section, section.compute())


def test_an_unknown_scope_names_the_known_ones():
    try:
        briefing.get_scope("capacity")
    except ValueError as exc:
        assert "drafting" in str(exc) and "overview" in str(exc), (
            f"the error for an unknown scope did not list the valid ones: {exc}"
        )
    else:
        raise AssertionError("an unknown scope was accepted")


def test_the_route_pattern_is_built_from_the_registry():
    """The three briefing routes used to repeat `^(overview|mammo)$`. A scope added to the
    registry and not to all three would 422 on two endpoints with no error saying why."""
    import re

    from app.routes.mosaic import _BRIEFING_SCOPES

    pattern = re.compile(_BRIEFING_SCOPES)
    for key in briefing.scope_keys():
        assert pattern.fullmatch(key), f"scope {key!r} exists but the routes would reject it"
    assert not pattern.fullmatch("capacity"), "the route pattern accepts a scope that does not exist"


def test_the_typescript_scope_union_matches_the_registry():
    """The fifth copy of the scope list, and the only one on the other side of a language border.

    Python cannot import a TypeScript union, so this reads the declaration as text - the same
    technique `test_registry_parity.py` uses for the frontend's copies of the coverage threshold
    and the read-time formula. Without it, a scope added to `_SCOPES` is reachable by curl and
    invisible to the app, and one removed 422s in a browser with no failing test anywhere.
    """
    import re
    from pathlib import Path

    types_ts = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "types.ts").read_text(
        encoding="utf-8"
    )

    m = re.search(r"export type BriefingScope\s*=\s*([^;]+);", types_ts)
    assert m, "types.ts no longer declares `export type BriefingScope`"
    declared = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert declared == set(briefing.scope_keys()), (
        f"TypeScript BriefingScope is {sorted(declared)}; the registry declares "
        f"{sorted(briefing.scope_keys())}"
    )

    # The MVP subset is typed separately because those two scopes are the only ones whose
    # persisted `funnel` is nested one level. Widening it to BriefingScope would tell the MVP
    # page that `funnel[stage].on_track` is a number on a Drafting snapshot where it is
    # undefined - and the page renders NaN rather than failing.
    m = re.search(r"export type MvpBriefingScope\s*=\s*([^;]+);", types_ts)
    assert m, "types.ts no longer declares `export type MvpBriefingScope`"
    mvp_declared = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert mvp_declared < declared, (
        f"MvpBriefingScope {sorted(mvp_declared)} is not a strict subset of BriefingScope "
        f"{sorted(declared)} - if they are equal, the separate type buys nothing and the nested "
        f"`funnel` type is now a claim about scopes that do not have it"
    )
    for key in mvp_declared:
        scope = briefing.get_scope(key)
        assert scope.grounding is mvp_context.PROGRAM_NARRATIVE, (
            f"{key!r} is typed as an MVP scope in TypeScript but is no longer grounded in the "
            f"MVP program narrative"
        )


def test_the_storage_ddl_no_longer_pins_the_scope_list():
    """The fourth copy of the list, and the one that failed last and worst - as an opaque
    IntegrityError inside a user's button click rather than a 422 naming the valid scopes."""
    import inspect

    source = inspect.getsource(postgres_client)
    # Comment lines are stripped first. The comment above the migration *explains* the removed
    # constraint and necessarily quotes it, so a plain substring search over the whole module
    # reports a failure that is the explanation, not the thing explained.
    executable = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "CHECK (scope IN" not in executable, (
        "the Postgres DDL still constrains the scope column to a hardcoded list - a new scope "
        "would pass the route and the service and fail on INSERT"
    )
    assert "DROP CONSTRAINT IF EXISTS mvp_weekly_snapshots_scope_check" in source, (
        "CREATE TABLE IF NOT EXISTS does nothing to the table that already exists in prod, so "
        "removing the CHECK from the DDL alone does not remove it from the live table"
    )


def test_exactly_three_sections_because_the_table_has_three_columns():
    """Guards the constraint rather than the taste. A fourth section needs a schema migration,
    and the failure without this check is silent truncation at the `*computed` splat."""
    for key in briefing.scope_keys():
        assert len(briefing.get_scope(key).sections) == len(briefing._SLOTS)
    assert briefing._SLOTS == ("funnel", "impact", "escalations"), (
        "the storage slots were renamed - mosaic.mvp_weekly_snapshots holds live MVP history in "
        "columns of these names, so this is a migration, not a rename"
    )


def test_diff_counts_still_handles_both_section_shapes():
    """The MVP funnel is one level nested; every Drafting section is flat. `diff_counts` serves
    both, and this is the only place that fact is asserted rather than assumed."""
    nested = mvp_dashboard_stats.diff_counts({"a": {"x": 5}}, {"a": {"x": 2}})
    flat = mvp_dashboard_stats.diff_counts({"a": 5}, {"a": 2})
    assert nested == {"a": {"x": 3}} and flat == {"a": 3}


class _StoredRows:
    """Stands in for Postgres on the *read* path, and records the window it was asked for.

    `_Patch` cannot serve these tests: its stub is `lambda scope, limit=12: [self.previous]`,
    which both ignores `limit` and caps the result at one row - so it can neither prove that the
    read path asks for one row beyond its window nor produce the predecessor that proves why.
    """

    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.limits: list[int] = []
        self._original = postgres_client.get_weekly_snapshots

    def __enter__(self):
        def _get(scope: str, limit: int = 12) -> list[dict]:
            self.limits.append(limit)
            return self.rows[:limit]

        postgres_client.get_weekly_snapshots = _get
        return self

    def __exit__(self, *exc):
        postgres_client.get_weekly_snapshots = self._original
        return False


def _stored_row(week_ending: str, n: float) -> dict:
    """What Postgres actually holds: three slot columns and no labels anywhere."""
    return {
        "week_ending": week_ending,
        "scope": "drafting",
        "funnel": {"drafted_tbwu": n},
        "impact": {"expected_unlock_tbwu": n},
        "escalations": {"Deployment (practice not enabled)": n},
        "key_insights": "",
        "focus_next_week": "",
    }


def test_the_section_labels_come_from_the_scope_and_not_from_storage():
    """The renderer's whole contract: the slot is the identity, the label is a caption.

    `mosaic.mvp_weekly_snapshots` stores three JSON columns and nothing else - no scope label, no
    section labels, no descriptions. Those are attached at read time from `_SCOPES`, which is what
    makes editing a scope's wording retroactively rename every past week rather than leaving a
    year of history captioned in the old vocabulary. Storing them would have been the obvious
    implementation and would have produced exactly that split.
    """
    import dataclasses

    spec = briefing.get_scope("drafting")
    with _StoredRows([_stored_row("2026-10-19", 100.0)]):
        out = briefing.read_snapshots("drafting", 1)

    assert len(out) == 1
    assert out[0]["scope_label"] == spec.label
    assert [s["slot"] for s in out[0]["sections"]] == list(briefing._SLOTS)
    assert [s["label"] for s in out[0]["sections"]] == [s.label for s in spec.sections]
    assert [s["description"] for s in out[0]["sections"]] == [s.description for s in spec.sections]

    # The same stored row, read against a renamed scope. Nothing about the row changed.
    renamed = dataclasses.replace(
        spec,
        label="Renamed Scope",
        sections=(dataclasses.replace(spec.sections[0], label="Renamed Section"), *spec.sections[1:]),
    )
    briefing._SCOPES["drafting"] = renamed
    try:
        with _StoredRows([_stored_row("2026-10-19", 100.0)]):
            after = briefing.read_snapshots("drafting", 1)
    finally:
        briefing._SCOPES["drafting"] = spec

    assert after[0]["scope_label"] == "Renamed Scope", (
        "the scope label survived a change to `_SCOPES`, which means it is being read from the "
        "stored row - past weeks would stay captioned in the old vocabulary forever"
    )
    assert after[0]["sections"][0]["label"] == "Renamed Section"
    assert after[0]["sections"][0]["values"] == out[0]["sections"][0]["values"], (
        "renaming a caption changed the numbers under it"
    )


def test_a_one_row_window_still_knows_it_has_a_predecessor():
    """The `limit + 1` read, and the reason it is not an off-by-one.

    Reading exactly `limit` rows and diffing adjacent pairs leaves the oldest row returned with no
    predecessor, so `limit=1` - which is what every page asking for "this week" passes - would
    always report `has_previous: False` and null deltas. That is true of the window and false of
    the data, and it is indistinguishable from a genuinely first-ever snapshot, so the panel would
    print "nothing to compare against yet" on a scope with a year of history.
    """
    rows = [_stored_row("2026-10-19", 100.0), _stored_row("2026-10-12", 40.0)]

    with _StoredRows(rows) as stored:
        out = briefing.read_snapshots("drafting", 1)

    assert stored.limits == [2], (
        f"the read path asked Postgres for {stored.limits} rows to fill a 1-row window - it must "
        f"ask for one beyond it so the oldest row returned still has something to diff against"
    )
    assert len(out) == 1, "the extra row is for diffing only and must not be returned"
    assert out[0]["week_ending"] == "2026-10-19"
    assert out[0]["has_previous"] is True
    assert out[0]["deltas"]["funnel"]["drafted_tbwu"] == 60.0
    assert out[0]["sections"][0]["deltas"]["drafted_tbwu"] == 60.0

    # And the genuine first week, which must still read as one.
    with _StoredRows(rows[-1:]):
        first = briefing.read_snapshots("drafting", 1)
    assert first[0]["has_previous"] is False
    assert first[0]["deltas"]["funnel"]["drafted_tbwu"] is None, (
        "a missing comparison rendered as 0 claims a flat week on evidence that does not exist"
    )


def test_the_briefing_renderer_names_no_scope_specific_vocabulary():
    """`BriefingPanel.tsx` must stay scope-blind, so a fourth scope is a backend declaration.

    The same hand-sync risk as `test_the_typescript_scope_union_matches_the_registry`, in the
    other direction: that one catches a scope the frontend does not know about, this one catches
    frontend code that knows too much. The moment one category name, stage or owner sentence is
    hardcoded here, adding a scope stops being a one-file change and nothing says so.
    """
    from pathlib import Path

    from app.services import next_best_action_service as nba

    panel = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "BriefingPanel.tsx"
    ).read_text(encoding="utf-8")

    # Everything the backend is allowed to call a thing, plus the MVP vocabulary that leaked into
    # the narrative prompt once already (see this module's docstring).
    forbidden = {
        nba.DRAFTED,
        nba.NOT_ENROLLED,
        nba.NOT_DRAFTED_WORKFLOW,
        nba.PRACTICE_NOT_ENABLED,
        nba.PROCEDURE_NOT_COVERED,
        nba.NOT_ON_MOSAIC,
        "expected_unlock_tbwu",
        "benchmark_draft_rate_pct",
        "teams_ranked",
        "Solutioning",
        "mentor",
        "cohort",
    }
    for key in briefing.scope_keys():
        scope = briefing.get_scope(key)
        forbidden.add(scope.label)
        forbidden.update(section.label for section in scope.sections)

    # `humanize()` deliberately passes prose keys through untouched, and its comment quotes two
    # category names to explain why. A comment is not a render, so strip them before searching -
    # otherwise the only way to document the rule is to break the test that enforces it.
    code = "\n".join(
        line for line in panel.splitlines() if not line.lstrip().startswith(("*", "//", "/*"))
    )
    leaked = sorted(term for term in forbidden if term in code)
    assert not leaked, (
        f"BriefingPanel.tsx names scope-specific vocabulary {leaked} - it renders whatever the "
        f"server declares and must not know what any scope contains"
    )

    # The positive half: it is scope-blind because it reads the payload, not because it is empty.
    for expected in ("section.label", "section.description", "section.values", "section.deltas"):
        assert expected in panel, f"the renderer no longer reads `{expected}` off the payload"


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {t.__name__}\n        {exc}")
        except Exception as exc:  # noqa: BLE001 - a crash is a failure, not a reason to stop
            # Without this, the first KeyError or TypeError aborts the run mid-suite and every
            # test after it reports neither pass nor fail - it simply vanishes, while the
            # summary line still reads as though the whole suite had been considered.
            failed += 1
            print(f"  ERROR {t.__name__}\n        {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
