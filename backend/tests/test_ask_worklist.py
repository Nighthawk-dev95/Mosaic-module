"""Pins the action-intent seam on Ask Mosaic - plan item E-4's second half.

Run from the `backend/` directory, with or without pytest:

    python tests/test_ask_worklist.py
    python -m pytest tests/test_ask_worklist.py

`ask_service.ask()` resolves a question to a governed *scope*: what to measure, over which
dimensions, for which solution. "Where should we focus next week" is not that question. It asks
which row to work, which is a ranking over a computed worklist, and pushed through the resolver
unchanged it fails in the worst available way - silently. No alias matches "focus" or "next", so
the scope comes back empty and the UI reports it cannot answer, while the governed ranking that
answers it exactly sits one module away, already computed and already on screen elsewhere.

So this file asserts three things, in order of how badly each would fail unnoticed:

  1. An action question attaches the worklist.
  2. An ordinary metric question does not - the key is *absent*, not null, so a surface can tell
     "not that kind of question" from "that kind, and there is nothing to work".
  3. Attaching it never costs the scope. Both intents can live in one sentence, and answering
     the action half by dropping the measurement half is the same mistake in reverse.

Offline: `cache_service.get_next_best_actions` is monkeypatched. The ranking's own arithmetic is
pinned in `test_next_best_action.py`; what is under test here is the routing, not the maths.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.mosaic import NextBestAction, NextBestActionList  # noqa: E402
from app.services import ask_service  # noqa: E402
from app.services import cache_service  # noqa: E402

_BASIS = "FIXTURE BASIS - carried verbatim or not at all"


def _action(team: str, unlock: float = 1000.0) -> NextBestAction:
    return NextBestAction(
        team=team,
        action="Enroll radiologists",
        primary_blocker="Draftable - Rad Not Enrolled",
        rationale="fixture",
        expected_unlock_tbwu=unlock,
        draft_rate=0.40,
        gap_to_benchmark_pct=12.0,
        blocker_share_of_gap=0.8,
        addressable_tbwu=5000.0,
        drafted_tbwu=2000.0,
        not_enrolled_tbwu=2500.0,
        workflow_gap_tbwu=500.0,
        deployment_blocked_tbwu=0.0,
        procedure_not_covered_tbwu=0.0,
        not_on_mosaic_tbwu=0.0,
        gap_exams=900,
    )


def _fake_list(teams: tuple[str, ...]) -> NextBestActionList:
    return NextBestActionList(
        actions=[_action(t, 1000.0 - i) for i, t in enumerate(teams)],
        benchmark_draft_rate=0.52,
        benchmark_pctile=0.75,
        benchmark_team_count=40,
        excluded_low_volume_teams=7,
        undated_rows_skipped=0,
        min_addressable_tbwu=500.0,
        window_start="2026-08-25",
        window_end="2026-10-20",
        weeks=8,
        total_expected_unlock_tbwu=3000.0,
        basis=_BASIS,
    )


class _Patch:
    """Swap `cache_service.get_next_best_actions` for the duration of one test.

    `ask_service` imports the module lazily *inside* `_worklist_for`, so patching the attribute
    on the module object is what the live call path actually reads - patching a name imported at
    the top of this file would not be.
    """

    def __init__(self, teams: tuple[str, ...] = ("Boca Radiology", "Apex Imaging"), raises: bool = False):
        self.teams, self.raises = teams, raises

    def __enter__(self):
        self._original = cache_service.get_next_best_actions

        def _stub(**kwargs):
            if self.raises:
                raise RuntimeError("cold cache")
            return _fake_list(self.teams)

        cache_service.get_next_best_actions = _stub
        return self

    def __exit__(self, *exc):
        cache_service.get_next_best_actions = self._original
        return False


def test_an_action_question_attaches_the_governed_worklist():
    with _Patch():
        result = ask_service.ask("where should we focus next week")
    assert "worklist" in result, (
        "an action question resolved to a scope and nothing else - the user asked which row to "
        "work and got an empty measurement scope, which reads as 'I cannot answer that'"
    )
    assert result["worklist"]["actions"], "the worklist attached with no rows in it"


def test_a_metric_question_does_not_attach_one():
    with _Patch():
        result = ask_service.ask("what is our drafting efficiency by local region")
    assert "worklist" not in result, (
        "a measurement question carried a ranked worklist. Every answer would then arrive with "
        "a list of teams to action, which trains the reader to ignore it on the one question "
        "where it is the answer."
    )


def test_the_key_is_absent_rather_than_null_when_there_is_no_action_intent():
    """Absent and empty must stay distinguishable - they are different answers.

    `{"actions": []}` means "you asked where to act, and no team is behind the benchmark" - a
    real, reportable result. A missing key means "you did not ask that". Collapsing both to
    `null` would make the first indistinguishable from the second, and the good news would
    render as silence.

    This is the *service's* contract. The response model declares the field, so what the HTTP
    boundary sends for "not that kind of question" is an explicit null - still distinguishable
    from an empty payload, and pinned separately in
    `test_the_three_states_survive_serialization_as_null_empty_and_ranked`.
    """
    with _Patch():
        no_intent = ask_service.ask("what is our drafting efficiency")
    with _Patch(teams=()):
        intent_no_rows = ask_service.ask("where should we focus")

    assert "worklist" not in no_intent
    assert "worklist" in intent_no_rows and intent_no_rows["worklist"]["actions"] == []


def test_the_basis_is_carried_verbatim():
    """The one string that must not be re-worded on its way through.

    `basis` is built around `next_best_action_service.METHODOLOGY` and carries this run's live
    benchmark, team count and window. The panel prints it; this answer repeats it. A summary
    written here would be a second description of a ranking that can move between the two
    renderings, and the discrepancy would surface in a meeting rather than in a test.
    """
    with _Patch():
        result = ask_service.ask("what is the biggest opportunity")
    assert result["worklist"]["basis"] == _BASIS


def test_attaching_the_worklist_does_not_cost_the_scope():
    """Both intents can live in one sentence; serving one by dropping the other is the bug.

    "where should we focus on drafting efficiency" has a real metric scope *and* a real action
    answer. An early version that returned the worklist instead of the scope would have looked
    correct on this exact question - the reader gets a useful answer - while having quietly
    stopped resolving the metric they named.
    """
    with _Patch():
        result = ask_service.ask("where should we focus on drafting efficiency")
    assert "worklist" in result
    assert result["scope"]["metrics"], (
        "the action path swallowed the scope - the question named a metric and the response "
        "resolved none"
    )


def test_a_cold_cache_degrades_to_the_scope_rather_than_failing_the_answer():
    """The ordinary case on a fresh process, not an error worth losing the whole response to."""
    with _Patch(raises=True):
        result = ask_service.ask("where should we focus next week")
    assert "worklist" not in result
    assert "scope" in result and "genie_prompt" in result


def test_the_entity_narrowing_only_fires_on_a_team():
    """Team and Practice are different columns, and this is where confusing them goes quiet.

    The worklist's `team` is `provider_local_practice_name_curr` - the radiologist's home
    practice. A name the user meant as a Practice (the site the exam was read at) filtered
    against that column returns an empty list, which renders as "nothing to do here" rather than
    "wrong column". So narrowing happens only when the vocabulary placed the name as a Team; a
    Practice gets the full ranking with `scoped_to` empty, and the surface can say which.
    """
    with _Patch():
        scoped = ask_service._worklist_for("Boca Radiology", {"kind": "team"})
        unscoped = ask_service._worklist_for("Boca Radiology", {"kind": "practice"})
        unplaced = ask_service._worklist_for("Boca Radiology", {})

    assert scoped["scoped_to"] == "Boca Radiology" and len(scoped["actions"]) == 1
    assert unscoped["scoped_to"] == "" and len(unscoped["actions"]) == 2, (
        "a Practice name narrowed the Team column - an empty worklist would have been shown as "
        "an absence of work"
    )
    assert unplaced["scoped_to"] == "" and len(unplaced["actions"]) == 2


def test_a_team_with_no_row_in_the_ranking_falls_back_to_the_full_list():
    """Not in the top N is not the same as nothing to do, and must not render as it.

    A team can be absent from the ranking for three different reasons: it is at or above the
    benchmark, it is below the minimum addressable volume, or it simply did not make the limit.
    Returning an empty list for all three tells the reader "no action for you" when two of those
    are "we did not rank you". So the full list comes back with `scoped_to` empty.
    """
    with _Patch():
        result = ask_service._worklist_for("Nowhere Imaging", {"kind": "team"})
    assert result["scoped_to"] == ""
    assert len(result["actions"]) == 2


def test_the_three_states_survive_serialization_as_null_empty_and_ranked():
    """The distinction has to hold at the HTTP boundary, not only inside Python.

    `ask()` omits the key; `AskResponse` declares the field, so FastAPI emits it as `null`. That
    is fine - null, `{"actions": []}` and a populated list are still three distinguishable
    answers - but it means a frontend testing `"worklist" in response` would see the key on
    *every* answer and render an empty worklist block on measurement questions. This pins what
    actually goes over the wire, which is what the TS client branches on.

    Checked against the response model rather than through TestClient: this venv has no httpx,
    deliberately - `requirements.txt` ships into the deployed Databricks App.
    """
    from app.routes.mosaic import AskResponse

    with _Patch():
        ranked = ask_service.ask("where should we focus next week")
    with _Patch(teams=()):
        empty = ask_service.ask("where should we focus next week")
    with _Patch():
        none = ask_service.ask("what is our drafting efficiency")

    wire = [AskResponse(**r).model_dump()["worklist"] for r in (ranked, empty, none)]

    assert wire[0] and wire[0]["actions"], "a ranked answer serialized without its rows"
    assert wire[1] is not None and wire[1]["actions"] == [], (
        "'no team is behind the benchmark' serialized as null, which is indistinguishable from "
        "'you did not ask that' - the good news would render as silence"
    )
    assert wire[2] is None, (
        "a measurement question serialized a worklist object; every answer would then carry an "
        "empty action block"
    )


def test_the_intent_pattern_does_not_fire_on_ordinary_measurement_language():
    """The regex is the whole gate, so its false positives are worth pinning individually.

    Each of these contains a word the pattern is built around - focus, priority, top, best -
    inside a sentence that is plainly a measurement question. A pattern loose enough to match
    them would attach a worklist to most of the product's traffic.
    """
    for question in (
        "what is our top line volume this month",
        "show me the best performing practices by efficiency",
        "how many radiologists are in the priority tier",
        "what is the focus factor on shift utilization",
    ):
        assert not ask_service._ACTION_INTENT.search(question), (
            f"{question!r} reads as a measurement question but matched the action-intent pattern"
        )


def test_the_intent_pattern_fires_on_the_questions_it_exists_for():
    for question in (
        "where should we focus next week",
        "what should we do about drafting",
        "which teams should we prioritize",
        "what is the biggest opportunity right now",
        "show me the next best action",
        "where do I get the most impact",
    ):
        assert ask_service._ACTION_INTENT.search(question), (
            f"{question!r} is the question this feature exists to answer and did not match"
        )


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
            # Catching only AssertionError means the first `KeyError` or `TypeError` aborts the
            # run mid-suite, and every test after it reports neither pass nor fail - it simply
            # vanishes. That happened here: a fixture missing one required field took eight
            # unrelated tests down with it and left "2/10 passed" as the only evidence.
            failed += 1
            print(f"  ERROR {t.__name__}\n        {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
