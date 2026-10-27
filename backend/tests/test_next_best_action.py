"""Pins the Drafting worklist's arithmetic and, more importantly, what it refuses to rank on.

Run from the `backend/` directory, with or without pytest:

    python tests/test_next_best_action.py
    python -m pytest tests/test_next_best_action.py

No cache and no warehouse: `next_best_action_service.rank` takes plain dicts, so every
assertion here runs offline. That is deliberate - this function turns leakage into a list of
people's Tuesdays, and the ordering has to be arguable from a fixture rather than from
production.

The failure this file exists to prevent is a plausible ranking: one that puts a team at the top
because of volume nobody on this list can convert (a procedure the model does not cover, a
practice not yet enabled), or because a tiny book posted a freak rate. Both read as insight.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import next_best_action_service as nba  # noqa: E402


def _row(week: str, team: str, category: str, tbwu: float, exams: int = 10) -> dict:
    return {
        "week_start": week,
        "local_practice": team,
        "team": team,
        "site": "Site A",
        "exam_category": "CT",
        "category": category,
        "category_sort_order": 0,
        "exam_count": exams,
        "tbwu": tbwu,
    }


WEEK = "2026-10-05"


def _team(team: str, drafted: float, not_enrolled: float = 0.0, workflow: float = 0.0, **other: float) -> list[dict]:
    rows = [_row(WEEK, team, nba.DRAFTED, drafted)]
    if not_enrolled:
        rows.append(_row(WEEK, team, nba.NOT_ENROLLED, not_enrolled))
    if workflow:
        rows.append(_row(WEEK, team, nba.NOT_DRAFTED_WORKFLOW, workflow))
    for category, tbwu in other.items():
        rows.append(_row(WEEK, team, category, tbwu))
    return rows


def test_the_benchmark_is_a_rate_some_team_actually_achieved():
    # Four teams at 100%, 80%, 60% and 40%. Nearest-rank at p75 must return 80%, not an
    # interpolated 85% that nobody has ever posted.
    rows = (
        _team("A", 1000, workflow=0)
        + _team("B", 800, workflow=200)
        + _team("C", 600, workflow=400)
        + _team("D", 400, workflow=600)
    )
    out = nba.rank(rows, min_addressable_tbwu=100)
    assert abs(out["benchmark_draft_rate"] - 0.8) < 1e-9, out["benchmark_draft_rate"]
    assert out["benchmark_team_count"] == 4


def test_a_team_at_or_above_the_benchmark_is_not_on_the_worklist():
    rows = _team("A", 1000) + _team("B", 800, workflow=200) + _team("C", 600, workflow=400) + _team("D", 400, workflow=600)
    out = nba.rank(rows, min_addressable_tbwu=100)
    named = {a["team"] for a in out["actions"]}
    assert "A" not in named and "B" not in named, named
    assert named == {"C", "D"}


def test_volume_nobody_on_this_list_can_convert_does_not_rank_a_team():
    """The whole point. A team whose only leakage is model coverage has no action here."""
    rows = (
        _team("A", 1000)
        + _team("B", 800, workflow=200)
        + _team("C", 600, workflow=400)
        + _team("D", 400, workflow=600)
        # Blocked has a perfect draft rate and an enormous uncovered/unenabled pile. If either
        # counted toward the rate it would outrank every real item below.
        + _team("Blocked", 900, **{nba.PROCEDURE_NOT_COVERED: 50_000, nba.PRACTICE_NOT_ENABLED: 40_000})
    )
    out = nba.rank(rows, min_addressable_tbwu=100)
    assert "Blocked" not in {a["team"] for a in out["actions"]}


def test_blocked_volume_is_still_reported_on_the_rows_that_do_rank():
    rows = (
        _team("A", 1000)
        + _team("B", 800, workflow=200)
        + _team("C", 600, workflow=400, **{nba.PRACTICE_NOT_ENABLED: 7_000})
        + _team("D", 400, workflow=600)
    )
    out = nba.rank(rows, min_addressable_tbwu=100)
    row = next(a for a in out["actions"] if a["team"] == "C")
    # Escalatable, just to a different owner - so it must survive to the response even though it
    # is excluded from the rate.
    assert row["deployment_blocked_tbwu"] == 7_000


def test_a_small_book_cannot_set_the_frontier():
    tiny = _team("Tiny", 50)  # a flawless 100% on 50 TBWU
    rows = tiny + _team("A", 800, workflow=200) + _team("B", 600, workflow=400) + _team("C", 400, workflow=600)
    out = nba.rank(rows, min_addressable_tbwu=500)
    assert out["excluded_low_volume_teams"] == 1
    assert "Tiny" not in {a["team"] for a in out["actions"]}
    # p75 of the three remaining rates (0.8, 0.6, 0.4) is 0.8 - unchanged by Tiny's 1.0.
    assert abs(out["benchmark_draft_rate"] - 0.8) < 1e-9


def test_expected_unlock_is_headroom_times_addressable_volume():
    rows = _team("A", 1000) + _team("B", 800, workflow=200) + _team("C", 600, workflow=400) + _team("D", 400, workflow=600)
    out = nba.rank(rows, min_addressable_tbwu=100)
    d = next(a for a in out["actions"] if a["team"] == "D")
    # benchmark 0.8, D is at 0.4 on 1000 addressable TBWU -> 400.
    assert abs(d["expected_unlock_tbwu"] - 400.0) < 1e-9
    assert abs(d["gap_to_benchmark_pct"] - 40.0) < 1e-9


def test_a_big_book_slightly_behind_outranks_a_small_book_far_behind():
    """The ordering that looks wrong at a glance and is right: unlock, not percentage gap."""
    rows = (
        _team("Frontier", 1000)
        + _team("Big", 30_400, workflow=9_600)  # 76% on 40,000 - 4 points behind -> 1,600
        + _team("Small", 200, workflow=800)  # 20% on 1,000 - 60 points behind -> 600
        + _team("Mid", 800, workflow=200)
    )
    out = nba.rank(rows, min_addressable_tbwu=100)
    assert [a["team"] for a in out["actions"]][0] == "Big"
    big = next(a for a in out["actions"] if a["team"] == "Big")
    small = next(a for a in out["actions"] if a["team"] == "Small")
    assert big["gap_to_benchmark_pct"] < small["gap_to_benchmark_pct"]
    assert big["expected_unlock_tbwu"] > small["expected_unlock_tbwu"]


def test_the_named_blocker_is_the_larger_of_the_two_gaps():
    rows = (
        _team("A", 1000)
        + _team("B", 800, workflow=200)
        + _team("Enrol", 400, not_enrolled=500, workflow=100)
        + _team("Flow", 400, not_enrolled=100, workflow=500)
    )
    out = nba.rank(rows, min_addressable_tbwu=100)
    by_team = {a["team"]: a for a in out["actions"]}
    assert by_team["Enrol"]["primary_blocker"] == nba.NOT_ENROLLED
    assert "Enroll" in by_team["Enrol"]["action"]
    assert by_team["Flow"]["primary_blocker"] == nba.NOT_DRAFTED_WORKFLOW
    assert by_team["Flow"]["blocker_share_of_gap"] > 0.8


def test_the_window_is_the_last_weeks_present_in_the_data():
    old = [_row("2026-01-05", "A", nba.NOT_DRAFTED_WORKFLOW, 90_000)]
    recent = _team("A", 500, workflow=500) + _team("B", 1000)
    out = nba.rank(old + recent, weeks=1, min_addressable_tbwu=100)
    a = next(x for x in out["actions"] if x["team"] == "A")
    # January's 90,000 is outside the window, so it cannot inflate the unlock.
    assert a["workflow_gap_tbwu"] == 500
    assert out["window_start"] == WEEK and out["window_end"] == WEEK and out["weeks"] == 1


def test_an_undated_row_cannot_become_the_most_recent_week():
    """Regression: found in production, not in a fixture.

    The cache really does carry rows with a null `week_start`. `str(None)` is `"None"`, which
    sorts after every ISO date, so an undated row was being admitted as the newest "week" in
    the window - which both reported `window_end: None` to the caller and added undated volume
    to every team's gap. The rows are dropped and counted instead.
    """
    undated = dict(_row(WEEK, "A", nba.NOT_DRAFTED_WORKFLOW, 90_000))
    undated["week_start"] = None
    rows = [undated] + _team("A", 500, workflow=500) + _team("B", 1000)
    out = nba.rank(rows, weeks=1, min_addressable_tbwu=100)
    assert out["window_end"] == WEEK, out["window_end"]
    assert out["undated_rows_skipped"] == 1
    a = next(x for x in out["actions"] if x["team"] == "A")
    assert a["workflow_gap_tbwu"] == 500


def test_an_empty_cache_is_an_empty_list_and_says_why():
    out = nba.rank([])
    assert out["actions"] == []
    assert "refresh" in out["basis"].lower()


def test_the_basis_states_the_benchmark_it_actually_used():
    rows = _team("A", 1000) + _team("B", 800, workflow=200) + _team("C", 400, workflow=600)
    out = nba.rank(rows, min_addressable_tbwu=100, benchmark_pctile=0.5)
    assert "50%" in out["basis"]
    assert "3 teams" in out["basis"]
    assert "not a forecast" in out["basis"]


def test_the_response_validates_against_the_api_model():
    """The route returns this shape verbatim - a key renamed here must fail here, not in prod."""
    from app.models.mosaic import NextBestActionList

    rows = _team("A", 1000) + _team("B", 800, workflow=200) + _team("C", 400, workflow=600)
    model = NextBestActionList(**nba.rank(rows, min_addressable_tbwu=100))
    assert model.actions and model.actions[0].team == "C"


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
