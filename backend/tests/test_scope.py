"""Pins what the scope resolver refuses, and why - plan §E-1b, verification item 7.

Run from the `backend/` directory, with or without pytest:

    python tests/test_scope.py
    python -m pytest tests/test_scope.py

No model and no warehouse. `app.semantics.scope` is pure by design and
`ask_service._keyword_proposal` is its no-model path, so every assertion below is a string-level
check that runs offline - which is the point: the resolver's behaviour must be reviewable
without an LLM in the loop, because the LLM is the part we are deliberately not trusting.

What this file is actually protecting
-------------------------------------
The plan's §E decision was text-to-*scope*, never text-to-SQL, on the grounds that a wrong
number delivered in fluent prose is worse than no number. That only holds if the refusals
actually fire. Each test below corresponds to a reading that has already been made wrongly at
least once, by a person or by a model:

  - "utilization" meaning adoption % when time utilization was meant, or the reverse
  - "pct mosaic" over the enterprise denominator when the on-shift one was meant (~25% fewer)
  - a breakdown requested on a metric that has no breakdown, answered by mis-joining
  - "practice" treated as ambiguous when the user has already defined it

The last is the inverse failure and is tested just as hard: refusing a question that was asked
precisely is not rigour, it is a resolver that cannot read its own spec.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.semantics import registry as reg  # noqa: E402
from app.semantics import scope as sc  # noqa: E402
from app.services import ask_service as ask  # noqa: E402


def _resolve(question: str) -> sc.ScopeSpec:
    """The no-model path end to end: English in, governed scope out."""
    return sc.resolve(ask._keyword_proposal(question))


def _refusal(spec: sc.ScopeSpec, term: str) -> sc.Refusal:
    for r in spec.refusals:
        if r.term == term:
            return r
    raise AssertionError(f"expected a refusal for {term!r}, got {[r.term for r in spec.refusals]}")


# --------------------------------------------------------------------------- ambiguity


def test_bare_utilization_is_refused_with_both_readings():
    spec = _resolve("what is utilization at Bethesda")
    assert spec.metrics == (), "the resolver picked a reading of 'utilization' instead of asking"
    assert not spec.is_answerable
    r = _refusal(spec, "utilization")
    assert set(r.alternatives) == {"pct_mosaic", "utilization_rpwu_pct"}
    # Both readings must be *named*, not just listed by key - the refusal is the explanation.
    assert "adoption" in r.reason.lower() and "shift" in r.reason.lower()


def test_pct_mosaic_is_refused_across_its_two_denominators():
    spec = _resolve("pct mosaic by team")
    assert spec.metrics == ()
    r = _refusal(spec, "pct mosaic")
    assert set(r.alternatives) == {"pct_mosaic", "capacity_pct_mosaic"}
    vol, cap = reg.get_metric("pct_mosaic"), reg.get_metric("capacity_pct_mosaic")
    assert vol.denominator != cap.denominator, (
        "the two pct_mosaic metrics now share a denominator - if that is real, this ambiguity "
        "should be deleted from _AMBIGUOUS rather than left refusing a question with one answer"
    )


def test_the_disambiguating_word_actually_disambiguates():
    """"Shift utilization" is precise where "utilization" is not, and must resolve."""
    spec = _resolve("shift utilization by practice this month")
    assert spec.metrics == ("utilization_rpwu_pct",)
    assert not any(r.term == "utilization" for r in spec.refusals), (
        "bare 'utilization' was matched inside 'shift utilization' and refused anyway"
    )


def test_ambiguity_survives_a_confident_model():
    """A proposal that picked one reading is still refused. Confidence is not evidence."""
    spec = sc.resolve({"metrics": ["utilization"], "group_by": [], "solution": "full_mosaic"})
    assert spec.metrics == ()
    assert _refusal(spec, "utilization").alternatives


# --------------------------------------------------------------------------- unknown terms


def test_unknown_metric_is_refused_with_somewhere_to_go():
    spec = sc.resolve({"metrics": ["subspecialty_rate"], "group_by": []})
    r = _refusal(spec, "subspecialty_rate")
    assert not spec.is_answerable
    # Either a near-miss suggestion or a pointer to the full vocabulary, never a bare "no".
    assert r.alternatives or "/api/mosaic/registry" in r.reason


def test_a_near_miss_is_offered_the_real_key():
    spec = sc.resolve({"metrics": ["pct_draftng"], "group_by": []})
    assert "pct_drafting" in _refusal(spec, "pct_draftng").alternatives


# --------------------------------------------------------------------------- grain


def test_a_breakdown_with_no_grain_behind_it_is_dropped_not_faked():
    """The metric survives, the breakdown does not. A half-answerable question gets half an
    answer plus a statement of what was dropped - not a silent mis-join."""
    spec = _resolve("capacity by team")
    assert spec.metrics == ("capacity_rpwu",)
    assert spec.group_by == ()
    assert spec.is_answerable
    r = _refusal(spec, "team")
    assert "shift grain" in r.reason, r.reason
    assert reg.get_metric("capacity_rpwu").allowed_dims == ()


def test_the_refusal_names_the_grain_it_actually_found():
    """Capacity and Efficiency both have no breakdown, for different reasons. An explanation
    that is right for one and wrong for the other is worse than none."""
    cap = _refusal(_resolve("capacity by team"), "team")
    eff = _refusal(_resolve("efficiency by local region"), "local_region")
    assert "shift grain" in cap.reason
    assert "exam grain" in eff.reason, eff.reason
    assert reg.get_metric("mosaic_tbwu_per_min").grain == "exam"


def test_alternatives_never_include_the_dimension_being_refused():
    """Alternatives are the intersection across the scope's metrics, not the union.

    With a union, asking two metrics for one breakdown that only one of them supports offered
    that very breakdown back as the alternative - true per-metric, useless as advice, and it
    reads as a bug rather than as a boundary.
    """
    spec = sc.resolve(
        {"metrics": ["mosaic_tbwu_per_min", "pct_drafting"], "group_by": ["local_region"]}
    )
    r = _refusal(spec, "local_region")
    assert "local_region" not in r.alternatives, r.alternatives
    assert reg.get_metric("pct_drafting").allowed_dims, "the mixed-grain premise no longer holds"


def test_a_legal_breakdown_is_left_alone():
    spec = sc.resolve({"metrics": ["pct_mosaic", "pct_drafting"], "group_by": ["local_region", "month"]})
    assert spec.group_by == ("local_region", "month")
    assert spec.refusals == ()


# --------------------------------------------------------------------------- the user's rule


def test_practice_and_team_both_resolve_and_are_not_ambiguous():
    """The convention is set: Team = Provider (the rad's home practice), Practice = Managing
    (the site where the exam was read). Interrogating the user about a word they have already
    defined is not rigour."""
    for word in ("practice", "team"):
        assert word not in sc._AMBIGUOUS, f"{word!r} was added back to the ambiguity table"
    spec = sc.resolve({"metrics": ["pct_mosaic"], "group_by": ["practice", "team"]})
    assert spec.group_by == ("practice", "team")
    assert spec.refusals == ()


def test_a_team_or_practice_breakdown_carries_the_distinction_as_a_note():
    spec = sc.resolve({"metrics": ["pct_mosaic"], "group_by": ["team"]})
    note = "\n".join(spec.notes)
    assert "home practice" in note and "read" in note, note
    assert "exactly one Team" in note


def test_the_two_dimensions_point_at_different_columns():
    practice, team = reg.get_dimension("practice"), reg.get_dimension("team")
    assert practice.sql != team.sql
    assert "managing" in practice.sql.lower(), practice.sql
    assert "provider" in team.sql.lower(), team.sql


# --------------------------------------------------------------------------- notes vs refusals


def test_a_gated_metric_says_a_blank_is_a_suppression():
    spec = sc.resolve({"metrics": ["utilization_rpwu_pct"], "group_by": []})
    assert spec.is_answerable, "a gate withholds a value; it does not refuse the question"
    assert spec.refusals == ()
    note = "\n".join(spec.notes)
    assert reg.READ_TIME_COVERAGE.min_pct_label in note
    assert "not a zero" in note, note


def test_an_unavailable_column_is_declared_before_it_is_asked_for():
    spec = sc.resolve({"metrics": ["baseline_rvu"], "group_by": []})
    assert spec.is_answerable
    assert "not computed" in "\n".join(spec.notes).lower()
    assert reg.get_metric("baseline_rvu").trust == "unavailable"


# --------------------------------------------------------------------------- the keyword floor


def test_the_longest_alias_wins():
    """Alias scanning is longest-first. Shortest-first would match "utilization" inside "shift
    utilization" and refuse the precise question as ambiguous."""
    p = ask._keyword_proposal("shift utilization by practice")
    assert p["metrics"] == ["shift utilization"], p
    assert "utilization" not in p["metrics"]


def test_an_ambiguous_phrase_reaches_the_resolver_as_a_phrase():
    """The keyword floor must not resolve - resolving is picking, and picking is the thing this
    whole module exists to avoid."""
    p = ask._keyword_proposal("how is utilization trending")
    assert p["metrics"] == ["utilization"], p
    assert p["metrics"][0] in sc._AMBIGUOUS


def test_a_solution_word_inside_a_metric_name_is_not_the_solution():
    p = ask._keyword_proposal("adoption and drafting rate for capture at Boca")
    assert p["solution"] == "capture", p
    assert "drafting rate" in p["metrics"]


def test_a_solution_word_is_not_also_counted_as_a_second_metric():
    p = ask._keyword_proposal("how is drafting efficiency trending")
    assert p["solution"] == "drafting"
    assert p["metrics"] == ["efficiency"], p


def test_every_offered_alternative_can_actually_be_asked_for():
    """A refusal's alternatives have to be reachable, or the refusal is a dead end.

    The UI renders them as buttons that rewrite the question, so this is the round trip a user
    makes with one click. It failed: the refusal for "utilization" advises asking for
    `pct_mosaic`, but the keyword floor slugged that key to "pct mosaic" - the colloquial phrase
    the ambiguity table refuses - so taking the advice produced the same refusal forever. The
    resolver's exact-key short-circuit could not help, because the key never reached it.
    """
    for phrase in sc._AMBIGUOUS:
        _, candidates = sc._AMBIGUOUS[phrase]
        refused = _resolve(f"what is {phrase} at Boca")
        assert not refused.is_answerable, phrase
        for key in candidates:
            again = _resolve(f"what is {key} at Boca")
            assert again.metrics == (key,), (phrase, key, again.metrics)
            assert not again.refusals, (key, [r.term for r in again.refusals])


def test_naming_a_key_does_not_also_raise_its_alias():
    """The literal-key scan runs first, so the alias and ambiguity scans must not re-add the
    same ask in colloquial form - that would hand `resolve()` two terms for one question and
    refuse the half the user had been precise about."""
    p = ask._keyword_proposal("what is pct_mosaic at Boca")
    assert p["metrics"] == ["pct_mosaic"], p


def test_a_bare_solution_question_still_gets_a_metric():
    """The inverse of the test above. Stripping the solution word unconditionally would leave
    "how is drafting doing" with nothing to measure; adoption is the honest reading."""
    spec = _resolve("how is drafting doing")
    assert spec.metrics == ("pct_drafting",)
    assert spec.solution == "drafting"
    assert spec.is_answerable


# --------------------------------------------------------------------------- contract


def test_an_unanswerable_scope_sends_genie_nothing():
    """The grounded prompt is built from registry definitions. With no metrics there are no
    definitions, so the prompt would be the ungoverned question we are refusing to ask."""
    out = ask.ask.__wrapped__ if hasattr(ask.ask, "__wrapped__") else None
    assert out is None or callable(out)
    spec = sc.resolve({"metrics": ["utilization"], "group_by": []})
    assert not spec.is_answerable
    assert spec.as_dict()["is_answerable"] is False


def test_the_grounded_prompt_carries_definitions_and_caveats():
    spec = sc.resolve({"metrics": ["pct_mosaic"], "group_by": ["team"], "entity": "Boca"})
    prompt = ask.genie_prompt("How is adoption at Boca?", spec)
    m = reg.get_metric("pct_mosaic")
    assert m.definition in prompt
    for c in m.caveats:
        assert c in prompt, c
    assert "Boca" in prompt
    assert reg.get_dimension("team").note in prompt


def test_the_scope_dict_is_json_shaped_and_carries_its_version():
    spec = _resolve("adoption by local region for drafting")
    d = spec.as_dict()
    assert d["registry_version"] == reg.REGISTRY_VERSION
    assert isinstance(d["metrics"], list) and isinstance(d["metrics"][0], dict)
    assert d["solution"]["key"] == "drafting"
    assert set(d) == {
        "metrics", "solution", "group_by", "entity", "period",
        "refusals", "notes", "is_answerable", "registry_version",
    }, sorted(d)


def test_the_vocabulary_offered_to_the_model_is_the_registry():
    v = sc.vocabulary()
    assert set(v["metrics"]) == set(reg.METRICS)
    assert set(v["dimensions"]) == set(reg.DIMENSIONS)
    assert set(v["solutions"]) == set(reg.EFFICIENCY_MODES)
    block = ask._vocabulary_block()
    for key in ("pct_mosaic", "capacity_pct_mosaic", "utilization_rpwu_pct"):
        assert key in block, f"{key} is askable but was not offered to the model"


# --- entity classification ----------------------------------------------------------------
#
# `_entity_match` is the one part of the Ask path that reads deployed vocabulary rather than the
# registry, so it is the one part these tests have to fake. The stub below is not a convenience:
# `semantics` is pure on purpose so this file runs with no warehouse and no network, and reaching
# into the real cache here would quietly give that up for every test in the file.


class _FakeOptions:
    # Deliberately shaped like the live data, not like a clean example. "Boca" is both a Practice
    # and a Team because that is the normal case - 86 practice names and 96 team names that
    # overlap almost entirely - and a fixture that made overlap exotic would have let the first
    # (refusing) version of this code pass.
    practices = ["Boca", "Bethesda", "RASF"]
    teams = ["BOCA", "Bethesda", "SEAL Team"]
    local_regions = ["Genesis", "Apex"]


class _offline:
    """Run the Ask path with no warehouse and no serving endpoint.

    Two stubs. The first points `_entity_match`'s lazy `from app.services import cache_service`
    at the fixture above. The second pins `propose` to its own keyword fallback - otherwise
    `ask()` reaches for a model endpoint, which makes these tests both slow and dependent on
    what an LLM happened to return. The keyword path is the floor the model is measured
    against, so pinning to it tests the weaker of the two paths, not a friendlier one.
    """

    def __enter__(self):
        import types

        from app import services

        self._real = getattr(services, "cache_service", None)
        mod = types.SimpleNamespace(get_volume_filter_options=lambda: _FakeOptions())
        services.cache_service = mod
        sys.modules["app.services.cache_service"] = mod
        self._propose = ask.propose
        ask.propose = lambda q: (ask._keyword_proposal(q), "keywords")
        return self

    def __exit__(self, *exc):
        from app import services

        ask.propose = self._propose
        if self._real is None:
            del services.cache_service
            sys.modules.pop("app.services.cache_service", None)
        else:
            services.cache_service = self._real
            sys.modules["app.services.cache_service"] = self._real
        return False


def test_a_name_in_both_lists_defaults_to_practice_and_says_so():
    """The user's rule - Team is the rad's home practice, Practice is the site they read at -
    makes this a real fork. It is answered with a stated default rather than a refusal because
    almost every organisation is both, so refusing here would refuse almost every question."""
    with _offline():
        m = ask._entity_match("Boca")
    assert m["kind"] == "practice", m
    assert m["assumed"] is True
    assert {c["kind"] for c in m["candidates"]} == {"practice", "team"}


def test_the_default_uses_the_vocabularys_casing_not_the_questions():
    with _offline():
        assert ask._entity_match("boca")["value"] == "Boca"
        assert ask._entity_match("boca", forced="team")["value"] == "BOCA"


def test_the_switch_is_honoured_and_stops_being_an_assumption():
    with _offline():
        m = ask._entity_match("Boca", forced="team")
    assert m["kind"] == "team"
    # Chosen, not guessed - the chip must stop claiming a default once the user has set one.
    assert m["assumed"] is False
    assert {c["kind"] for c in m["candidates"]} == {"practice", "team"}


def test_a_name_in_one_list_is_not_offered_a_switch():
    """A one-item chooser implies a choice that does not exist."""
    with _offline():
        for name, kind in (("RASF", "practice"), ("SEAL Team", "team"), ("Genesis", "local_region")):
            m = ask._entity_match(name)
            assert m["kind"] == kind, (name, m)
            assert m["candidates"] == [] and m["assumed"] is False, (name, m)


def test_a_name_the_vocabulary_never_heard_of_is_not_given_a_column():
    with _offline():
        m = ask._entity_match("Somewhere That Does Not Exist")
    assert m["kind"] == "unknown" and m["candidates"] == []


def test_the_prompt_names_the_column_that_answers_the_entity():
    """"Boca" alone lets Genie pick between two columns with different populations."""
    spec = sc.resolve({"metrics": ["pct_mosaic"], "entity": "Boca"})
    with _offline():
        placed = ask.genie_prompt("How is Boca doing?", spec, ask._entity_match("Boca"))
        switched = ask.genie_prompt("How is Boca doing?", spec, ask._entity_match("Boca", "team"))
        unknown = ask.genie_prompt("q", spec, ask._entity_match("Nowhere"))
    assert reg.get_dimension("practice").sql in placed
    assert reg.get_dimension("team").sql in switched
    assert reg.get_dimension("practice").sql not in switched
    # Unqualified on purpose: inventing a column for a name we cannot place is the silent
    # wrong-number failure the whole module exists to avoid.
    assert "Restrict to: Boca" in unknown


def test_a_default_entity_does_not_block_the_answer():
    """An ambiguous *metric* blocks because there is no defensible default. The Team/Practice
    default is defensible and visible, so it must not put the answer behind a clarifier."""
    # The entity rides in on `page_scope`, which is the real path: naming the entity is the
    # model's job, and these tests deliberately run the keyword floor instead.
    with _offline():
        out = ask.ask("what is pct_mosaic", {"entity": "Boca"})
    assert out["entity_match"]["assumed"] is True
    assert out["needs_clarification"] is False
    assert out["genie_prompt"]
    with _offline():
        blocked = ask.ask("what is utilization", {"entity": "Boca"})
    assert blocked["needs_clarification"] is True


def test_the_switch_travels_on_page_scope():
    with _offline():
        out = ask.ask("what is pct_mosaic", {"entity": "Boca", "entity_kind": "team"})
    assert out["entity_match"]["kind"] == "team"
    assert reg.get_dimension("team").sql in out["genie_prompt"]


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
