"""Next best action - rank Drafting leakage by the TBWU an operator could realistically unlock.

Plan item E-4. The Non-Drafted tab already shows *where* draftable volume is leaking, in six
categories. What it does not say is which of those leaks is worth someone's Tuesday. A bucket
holding 40,000 TBWU behind a model that does not cover the procedure is not an action; a bucket
holding 8,000 TBWU behind twelve rads who were never enrolled is.

Three decisions worth stating, because each one is a place this could have been wrong:

**It computes from the cached leakage rows, not from a new query.** `undrafted_analysis` is
already refreshed at (week, team, site, exam_category, category) grain and already carries
`tbwu`. Every number below is a regrouping of rows the app has on disk, so this endpoint costs
no EDW round trip - which it must not, since `databricks_client` holds one connection behind one
lock and a ranked worklist is exactly the sort of page someone refreshes.

**The conversion rate is observed from peers, not assumed.** The plan's sketch was
`Drafting Opportunity (Enrollment)` x "historical conversion rate per `rad_enrollment_state`".
`rad_enrollment_state` lives on `mosaic_drafting_metric_vw`, which this app does not cache, and
inventing a conversion constant would make the ranking a function of the constant rather than of
the data. So the achievable rate is read off the teams that have already achieved it: the
`benchmark_pctile`-th percentile of peer draft rates. The claim it supports is deliberately
modest and is stated on the response - *this is what comparable teams already do*, not *this is
what you will get*.

**Only the two operator-addressable leaks count toward the unlock.** `Practice Not Enabled for
Model` is a deployment decision and `Procedure Not Covered` is a model-roadmap one; neither is
convertible by the person working this list, and folding them in would rank teams by work nobody
on this list can do. Deployment-blocked TBWU still rides along on each row as its own field,
because it is the right thing to escalate - just to a different owner.

Pure Python over plain dicts, deliberately: no cache, no network, no Pydantic in the ranking
function, so the arithmetic can be tested offline against a fixture the way `app/semantics` is.
"""

from __future__ import annotations

import math

# The six categories `mosaic_service.get_undrafted_analysis` emits, named once here so a rename
# upstream fails loudly in one place instead of silently zeroing a bucket.
DRAFTED = "Drafted"
NOT_ENROLLED = "Draftable - Rad Not Enrolled"
NOT_DRAFTED_WORKFLOW = "Draftable - Not Drafted (Workflow)"
PRACTICE_NOT_ENABLED = "Practice Not Enabled for Model"
PROCEDURE_NOT_COVERED = "Procedure Not Covered"
NOT_ON_MOSAIC = "Not Read on Mosaic"

# What an operator can actually move. `Drafted` is in the denominator (it is the share already
# converted), the two gaps are the headroom. See the module docstring for why the other three
# categories are excluded from the rate.
_ADDRESSABLE = (DRAFTED, NOT_ENROLLED, NOT_DRAFTED_WORKFLOW)

_ACTIONS = {
    NOT_ENROLLED: (
        "Enroll radiologists in Drafting",
        "Draftable volume read by radiologists who are not enrolled in the drafting model. "
        "Owner: MVP onboarding / Dynamics.",
    ),
    NOT_DRAFTED_WORKFLOW: (
        "Workflow coaching for enrolled radiologists",
        "Draftable volume read by enrolled radiologists who did not use the draft. "
        "Owner: Clinical Transformation.",
    ),
}


# The part of the ranking's explanation that does not depend on this run's numbers.
#
# `rank()` builds a `basis` string carrying the live benchmark, team count and window; the AI
# grounding needs the same methodology but cannot have those numbers, because grounding is
# assembled per-hover with no ranking in hand. Writing it twice is how the tooltip ends up
# describing a frontier the list stopped using. So the stable half lives here, `basis`
# interpolates its numbers around it, and `ai_context_service` injects it verbatim.
#
# The last sentence is the one that matters in a room: this is a rate peers already achieve, so
# the right challenge to it is "those peers aren't comparable", not "your forecast is wrong".
# Framing it as a forecast would invite a defence the number cannot make.
METHODOLOGY = (
    "Expected unlock = (peer benchmark draft rate - this team's draft rate) x its addressable "
    "draftable TBWU. Addressable means the three operator-movable categories only: already "
    "Drafted (the converted share), Draftable - Rad Not Enrolled, and Draftable - Not Drafted "
    "(Workflow). Volume blocked by practice enablement or by procedures the model does not cover "
    "is excluded from the rate and reported separately, because neither is convertible by the "
    "person working this list - they escalate to Deployment and to the model roadmap instead. "
    "Teams below the minimum addressable volume are dropped from both the ranking and the "
    "benchmark, since a handful of exams can sit at 0% or 100% and drag the frontier somewhere "
    "no large team could follow. The benchmark is a percentile of peer draft rates actually "
    "observed in the window - a rate comparable teams already achieve, not a forecast or a target."
)


def _percentile(values: list[float], pctile: float) -> float:
    """Nearest-rank percentile - no interpolation.

    Interpolating would invent a draft rate no team has ever achieved and then rank everyone
    against it. Nearest-rank always returns a rate that is literally somebody's, which is the
    only claim this benchmark is entitled to make.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    # Nearest-rank: ceil(p * n), 1-indexed, clamped - so p=1.0 is the max and p=0 is the min.
    position = max(1, min(len(ordered), math.ceil(pctile * len(ordered))))
    return ordered[position - 1]


def rank(
    rows: list[dict],
    *,
    weeks: int = 8,
    min_addressable_tbwu: float = 500.0,
    benchmark_pctile: float = 0.75,
    limit: int = 25,
) -> dict:
    """Rank teams by expected TBWU unlock. `rows` is `undrafted_analysis` at its cached grain.

    Returns the worklist plus the basis it was computed on. The basis is not decoration: a
    ranking against a peer frontier is only readable if you can see how many peers, over what
    window, and at what rate - and a reader who disagrees with the frontier should be able to
    say so from the response alone.
    """
    if not rows:
        return _empty(weeks, benchmark_pctile, min_addressable_tbwu)

    # The window is the last `weeks` weeks *present in the data*, not the last `weeks` weeks of
    # the calendar. The cache can lag a refresh cycle, and silently ranking on a short final
    # week would understate every team by the same invisible amount.
    #
    # Rows with no week are dropped rather than bucketed: the cache really does carry some
    # (~2,700 of 2.97M, ~26K TBWU - finalized exams with no final_datetime), and because "None"
    # sorts after every ISO date they would otherwise have been admitted as the most recent
    # "week" in the window, quietly adding undated volume to every team's gap. They are counted
    # on the response instead of being silently swallowed.
    undated = sum(1 for r in rows if not r.get("week_start") or str(r.get("week_start")) == "None")
    all_weeks = sorted(
        {str(r["week_start"]) for r in rows if r.get("week_start") and str(r["week_start"]) != "None"}
    )
    window = set(all_weeks[-max(1, int(weeks)) :])

    # TBWU and exam counts kept in two maps rather than one with suffixed keys - the suffix
    # trick reads fine until someone adds a category whose name contains the separator.
    tbwu_by_team: dict[str, dict[str, float]] = {}
    exams_by_team: dict[str, dict[str, float]] = {}
    for row in rows:
        if str(row.get("week_start")) not in window:
            continue
        # No fallback to `local_practice`: since 2026-10-27 that column is the *managing* site,
        # not a duplicate of the provider practice, so falling back would file a site's leakage
        # under a field this worklist renders to operators as a team. A row with no `team` is
        # skipped instead.
        team = row.get("team")
        if not team:
            continue
        category = row.get("category") or ""
        bucket = tbwu_by_team.setdefault(team, {})
        bucket[category] = bucket.get(category, 0.0) + float(row.get("tbwu") or 0.0)
        counts = exams_by_team.setdefault(team, {})
        counts[category] = counts.get(category, 0.0) + float(row.get("exam_count") or 0.0)

    scored: list[dict] = []
    below_threshold = 0
    for team, bucket in tbwu_by_team.items():
        counts = exams_by_team.get(team, {})
        drafted = bucket.get(DRAFTED, 0.0)
        not_enrolled = bucket.get(NOT_ENROLLED, 0.0)
        workflow = bucket.get(NOT_DRAFTED_WORKFLOW, 0.0)
        addressable = drafted + not_enrolled + workflow
        if addressable < float(min_addressable_tbwu):
            # Excluded from the ranking *and* from the benchmark. A team with 30 TBWU of
            # draftable volume can sit at 0% or 100% on a handful of exams, and either way it
            # would drag the peer frontier somewhere no large team can follow.
            below_threshold += 1
            continue
        scored.append(
            {
                "team": team,
                "draft_rate": drafted / addressable if addressable else 0.0,
                "addressable_tbwu": addressable,
                "drafted_tbwu": drafted,
                "not_enrolled_tbwu": not_enrolled,
                "workflow_gap_tbwu": workflow,
                "deployment_blocked_tbwu": bucket.get(PRACTICE_NOT_ENABLED, 0.0),
                "procedure_not_covered_tbwu": bucket.get(PROCEDURE_NOT_COVERED, 0.0),
                "not_on_mosaic_tbwu": bucket.get(NOT_ON_MOSAIC, 0.0),
                "gap_exams": int(counts.get(NOT_ENROLLED, 0.0) + counts.get(NOT_DRAFTED_WORKFLOW, 0.0)),
            }
        )

    benchmark = _percentile([s["draft_rate"] for s in scored], benchmark_pctile)

    actions: list[dict] = []
    for s in scored:
        headroom = max(0.0, benchmark - s["draft_rate"])
        expected = headroom * s["addressable_tbwu"]
        if expected <= 0:
            # At or above the frontier. Not a failure and not a worklist item - the ranking is
            # of work to do, so a team with nothing to close simply is not on it.
            continue
        blocker = NOT_ENROLLED if s["not_enrolled_tbwu"] >= s["workflow_gap_tbwu"] else NOT_DRAFTED_WORKFLOW
        action, why = _ACTIONS[blocker]
        gap_total = s["not_enrolled_tbwu"] + s["workflow_gap_tbwu"]
        actions.append(
            {
                **s,
                "primary_blocker": blocker,
                "action": action,
                "rationale": why,
                "blocker_share_of_gap": (s[
                    "not_enrolled_tbwu" if blocker == NOT_ENROLLED else "workflow_gap_tbwu"
                ] / gap_total) if gap_total else 0.0,
                "expected_unlock_tbwu": expected,
                # The headroom in points, so a reader can see a team that is 2 points off the
                # frontier on huge volume outranking one that is 30 points off on a small book -
                # which is correct, and looks wrong until the two numbers sit side by side.
                "gap_to_benchmark_pct": headroom * 100.0,
            }
        )

    actions.sort(key=lambda a: a["expected_unlock_tbwu"], reverse=True)
    window_weeks = sorted(window)
    return {
        "actions": actions[: max(1, int(limit))],
        "benchmark_draft_rate": benchmark,
        "benchmark_pctile": benchmark_pctile,
        "benchmark_team_count": len(scored),
        "excluded_low_volume_teams": below_threshold,
        "undated_rows_skipped": undated,
        "min_addressable_tbwu": float(min_addressable_tbwu),
        "window_start": window_weeks[0] if window_weeks else "",
        "window_end": window_weeks[-1] if window_weeks else "",
        "weeks": len(window_weeks),
        "total_expected_unlock_tbwu": sum(a["expected_unlock_tbwu"] for a in actions),
        # Said on the response, not just in a docstring, because this number will be read out
        # loud in a meeting by someone who never opened this file.
        "basis": (
            f"{METHODOLOGY} This run: the {benchmark_pctile:.0%} percentile of {len(scored)} "
            f"teams carrying at least {float(min_addressable_tbwu):,.0f} addressable TBWU over "
            f"{len(window_weeks)} weeks, giving a benchmark draft rate of {benchmark:.1%}."
        ),
    }


def _empty(weeks: int, benchmark_pctile: float, min_addressable_tbwu: float) -> dict:
    return {
        "actions": [],
        "benchmark_draft_rate": 0.0,
        "benchmark_pctile": benchmark_pctile,
        "benchmark_team_count": 0,
        "excluded_low_volume_teams": 0,
        "undated_rows_skipped": 0,
        "min_addressable_tbwu": float(min_addressable_tbwu),
        "window_start": "",
        "window_end": "",
        "weeks": 0,
        "total_expected_unlock_tbwu": 0.0,
        "basis": "No cached drafting-leakage rows available - run a refresh.",
    }
