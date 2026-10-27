"""Proves the registry still says what the deployed service modules say.

Run from the `backend/` directory, with or without pytest:

    python tests/test_registry_parity.py
    python -m pytest tests/test_registry_parity.py        # if pytest is installed

No Databricks connection is required and none is opened. `databricks_client` builds its shared
connection lazily (`_connection = None` at import), and `app.semantics` never queries anything -
so this is a pure string-level check that runs in CI, on a laptop, offline.

Why a test and not a comment
----------------------------
The plan's §Risks calls stale-snapshot "the house failure class": all three Mosaic metric views
once silently served a frozen `edw_test` copy six days and 963,040 rows behind prod, and the
hand-written bug checklist meant to catch that sort of thing was itself three-quarters stale. A
docstring promising "identical by construction" is exactly that kind of checklist. This file is
the executable version.

What is and is not guaranteed
-----------------------------
Guaranteed, and asserted below:

  (a) every numerator/denominator in the registry appears **verbatim** as a substring of the
      deployed `_VOLUME_MEASURES_SQL`; and
  (b) the registry's composed SELECT list is **whitespace-normalised equal** to that block.

Not guaranteed, deliberately: byte-for-byte equality of the whole composed block. The deployed
constant is an f-string whose `AS` keywords are column-aligned in the *source text*, but the two
RPCE lines interpolate `{_RPCE_PCT_ADJUSTMENT}` - 22 characters of placeholder collapsing to 4
characters of `0.02` - so in the *rendered* string those two lines' `AS` keywords sit ~18 columns
left of the others. No composer that pads to a fixed column can reproduce that, and claiming
otherwise in a docstring would be false. Whitespace-normalised equality is semantically exact for
SQL, which is the property that actually matters here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.mvp_dashboard_stats import (  # noqa: E402
    _ESCALATION_OWNER_MAP,
    _IMPLAUSIBLE_PCT_MAGNITUDE,
)
from app.db import fact_store  # noqa: E402
from app.semantics import registry as reg  # noqa: E402
from app.services import cache_service  # noqa: E402
from app.services import cube_service  # noqa: E402
from app.services import volume_service  # noqa: E402

_VOLUME_KEYS = [m.key for m in reg.VOLUME_METRICS]
# The five the monthly trend query inlines. It omits the RPCE pair: the dashboard's Volume Trend
# page does too, and an RPCE share over a single month is a thin enough denominator to mislead.
_TREND_KEYS = ["total_exams", "mosaic_exams", "pct_mosaic", "drafting_exams", "pct_drafting"]


def _norm(sql: str) -> str:
    """Collapse runs of whitespace. SQL is whitespace-insensitive outside string literals, and
    there are no string literals in these measure expressions."""
    return re.sub(r"\s+", " ", sql).strip()


def _strip_sql_comments(sql: str) -> str:
    """Drop `-- …` line comments.

    Needed only on the Capacity side. `_VOLUME_MEASURES_SQL` is bare expressions;
    `_CAPACITY_MEASURES_SQL` interleaves four explanatory comment lines with its 27 measures, and
    `_norm` would fold each one into the measure beneath it. The registry keeps that prose as
    `caveats`, where a reader can act on it; here we are comparing arithmetic.

    Safe for these two constants specifically: neither contains a string literal, so there is no
    `--` that could be inside quotes. Do not reuse this on arbitrary SQL.
    """
    return "\n".join(line.split("--")[0] for line in sql.splitlines())


def test_expressions_are_verbatim_substrings():
    """(a) Nobody retyped the SQL. A reworded-but-equivalent expression would pass the
    normalised comparison below while quietly becoming a second source of truth."""
    deployed = volume_service._VOLUME_MEASURES_SQL
    for spec in reg.VOLUME_METRICS:
        for part in (spec.numerator, spec.denominator):
            if part is None:
                continue
            assert part in deployed, (
                f"{spec.key}: expression is not a verbatim substring of "
                f"{spec.lifted_from}\n  registry: {part}"
            )


def test_composed_block_matches_deployed_measures():
    """(b) The registry composes the whole deployed measure list, in order, including the
    `* 1.0` scale and the `+ 0.02` offset on the RPCE pair."""
    composed = reg.select_sql(_VOLUME_KEYS)
    assert _norm(composed) == _norm(volume_service._VOLUME_MEASURES_SQL)


def test_composed_block_matches_monthly_trend():
    """`get_volume_trend` inlines its own five measures rather than reusing the shared constant,
    so it is a separate fold-in case and needs its own assertion - otherwise the registry could
    drift from the trend chart while still matching everything else.

    This also pins the `month` dimension: both its SELECT expression and its GROUP BY expression
    have to match what the trend query actually runs.
    """
    src = Path(volume_service.__file__).read_text(encoding="utf-8")
    body = src.split("def get_volume_trend()", 1)[1]
    select_block = body.split("SELECT", 1)[1].split("FROM", 1)[0]

    month = reg.DIMENSIONS["month"]
    expected = f"    {month.sql} AS period,\n" + reg.select_sql(_TREND_KEYS)

    assert _norm(select_block) == _norm(expected)
    assert f"GROUP BY {month.group_by_sql}" in body
    # The filter is a property of the dimension, not of this one call site. Leaving it out let a
    # null `period` reach VolumeTrendPoint's `period: str` and 500 the endpoint (live 2026-10-24).
    assert f"WHERE {month.required_filter}" in body
    assert reg.required_filters(["month"]) == [month.required_filter]


def test_team_and_practice_are_not_interchangeable():
    """The project's single most-repeated defect, asserted rather than remembered.

    Team is the radiologist's home practice (`provider_...`); Practice is the site where the exam
    was performed (`managing_...`). `get_radiologist_scorecard` still ends with
    `MAX(practice) AS team, MAX(practice) AS practice` - this test is what stops the registry
    inheriting that conflation as the services fold in.
    """
    team, practice = reg.DIMENSIONS["team"], reg.DIMENSIONS["practice"]
    assert team.sql == "provider_local_practice_name_curr"
    assert practice.sql == "managing_local_practice_name_curr"
    assert team.sql != practice.sql

    # And the deployed service groups by exactly these, under exactly these names.
    src = Path(volume_service.__file__).read_text(encoding="utf-8")
    assert f"GROUP BY {practice.sql}" in src
    assert f"GROUP BY {team.sql}" in src


def test_local_region_is_not_retyped():
    """The 6-region CASE is keyed on Team, and is shared by reference with the service module -
    not copied. A copy would let the two surfaces disagree on Local Region groupings silently,
    which is precisely what the constant's own header comment warns about."""
    assert reg.DIMENSIONS["local_region"].sql is volume_service._LOCAL_REGION_CASE_SQL
    assert "provider_local_practice_name_curr" in reg.DIMENSIONS["local_region"].sql


def test_rates_store_numerator_and_denominator():
    """Fix 3 made structural: a rate must be re-derivable at any grain. If a metric ever stores a
    pre-divided value, `SUM(num)/SUM(den)` rollups become `AVG(rate)` rollups and every
    multi-entity total in the product goes quietly wrong."""
    for spec in reg.VOLUME_METRICS:
        if spec.key.startswith("pct_"):
            assert spec.is_rate and spec.denominator, f"{spec.key} is a rate with no denominator"
            assert "NULLIF" not in spec.numerator, f"{spec.key} pre-divides in its numerator"


def test_rpce_offset_is_applied_after_the_division():
    """A constant additive offset only survives re-aggregation if it is applied once per grain,
    *after* dividing. Folded into the numerator it would be picked up N times by an N-group
    rollup. Declaring it as its own field is what makes that impossible."""
    for key in ("pct_rpce_reporting", "pct_rpce_drafting"):
        spec = reg.get_metric(key)
        assert spec.offset == 0.02
        sql = spec.value_sql()
        assert sql.endswith(") + 0.02"), sql
        assert str(spec.offset) not in spec.numerator


def test_unknown_metric_and_dimension_are_refused_with_alternatives():
    """Verification step 7: an undefined scope must be refused *with a listed alternative*, never
    answered. A plausible wrong number is worse than an error."""
    for call, bad in ((reg.get_metric, "efficiency_per_banana"), (reg.get_dimension, "zip_code")):
        try:
            call(bad)
        except (reg.UnknownMetricError, reg.UnsupportedDimensionError) as exc:
            assert "total_exams" in str(exc) or "practice" in str(exc), str(exc)
        else:
            raise AssertionError(f"{call.__name__}({bad!r}) should have raised")

    try:
        reg.validate_scope(["total_exams"], ["month", "zip_code"])
    except reg.UnsupportedDimensionError as exc:
        assert "practice" in str(exc)
    else:
        raise AssertionError("validate_scope should have rejected an unknown dimension")


def test_describe_carries_definition_and_caveats_for_every_metric():
    """`GET /api/mosaic/registry` serves this, so no definition is ever hardcoded in TSX. Every
    rate must carry at least one caveat - a bare ratio with no stated denominator semantics is
    how `% Mosaic` (exam-count adoption) and time-based Utilization got conflated in the first
    place."""
    for key in _VOLUME_KEYS:
        d = reg.describe(key)
        assert d["definition"].strip()
        assert d["allowed_dims"], key
        if d["is_rate"]:
            assert d["caveats"], f"{key} is a rate with no caveats"


def test_snapshot_has_the_shape_the_route_promises():
    """`GET /api/mosaic/registry` serves `snapshot()` with no `response_model`, deliberately -
    a Pydantic model here would be a fifth copy of the same schema, edited in lockstep with the
    registry. This is what stands in for it. It is a shape contract, not a content one: the
    frontend indexes `features` by `feature` and reads `metrics[].definition`, so those names are
    load-bearing even though nothing in Python would complain if they changed."""
    snap = reg.snapshot()
    for field in ("version", "ai_fallback_text", "metrics", "dimensions", "coverage", "features"):
        assert field in snap, f"snapshot is missing {field!r}"

    assert len(snap["metrics"]) == len(reg.METRICS)
    assert len(snap["dimensions"]) == len(reg.DIMENSIONS)

    # Team and Practice must be separately describable *without* first picking a metric - the
    # distinction is a property of the dimension, and burying it under a metric is how the UI
    # ended up with three surfaces titled "Practice" over provider-sourced columns.
    by_key = {d["key"]: d for d in snap["dimensions"]}
    assert "home practice" in by_key["team"]["note"].lower()
    assert "site where the exam was performed" in by_key["practice"]["note"]

    # Every served feature carries *something a reader can act on*: a definition, a coverage
    # threshold, or a stated reason it will never have either. The third arm was added when
    # `UNREGISTERED_FEATURES` moved into the registry and `snapshot()` started serving all three
    # states - before that, this loop was right to demand metrics-or-coverage, because an entry
    # with neither could only be a bug. It is now a deliberate, explained absence.
    for feat in snap["features"]:
        assert feat["metrics"] or feat["coverage"] or feat["unregistered_reason"], (
            f"feature {feat['feature']!r} resolves to nothing - do not serve an empty promise"
        )
        for m in feat["metrics"]:
            assert m["definition"].strip()


def test_composed_capacity_block_matches_deployed_measures():
    """Wave 2's half of (b), with one extra hazard Volume did not have.

    `_CAPACITY_MEASURES_SQL` carries four `--` comment lines explaining the gate, the
    coverage-matched numerator and the coverage spread. Whitespace normalisation alone cannot
    reconcile those - it would fold each comment into the line that follows it and produce a
    "difference" that is really just prose. So comments are stripped from the deployed side
    before comparing. The registry keeps that prose too, as `caveats`, which is where a reader
    can actually act on it; this assertion is about the *arithmetic* being the same.
    """
    from app.services import mosaic_service

    deployed = _strip_sql_comments(mosaic_service._CAPACITY_MEASURES_SQL)
    composed = reg.select_sql([m.key for m in reg.CAPACITY_METRICS], indent="  ")
    assert _norm(composed) == _norm(deployed), (
        "the registry's composed capacity block no longer matches "
        "mosaic_service._CAPACITY_MEASURES_SQL\n"
        f"composed: {_norm(composed)}\n"
        f"deployed: {_norm(deployed)}"
    )


def test_the_gate_is_built_not_retyped():
    """The suppression is the single most consequential expression in this product - two
    practices with zero read-time coverage once displayed a flawless 100% utilization. The
    registry must not carry a lookalike of it: `value_sql()` calls the same
    `_gated_utilization_sql` the deployed block calls, so a change to the gate reaches both at
    once. Asserted by composing one gated metric and comparing against a direct call."""
    from app.services import mosaic_service

    spec = reg.get_metric("utilization_rpwu_pct")
    assert spec.gated_by == reg.READ_TIME_COVERAGE.key
    assert spec.value_sql() == mosaic_service._gated_utilization_sql(
        "SUM(shift_read_minutes)",
        "SUM(no_hours)",
        "SUM(exams_with_valid_read_time)",
        "SUM(shift_cases)",
    )
    # And it really is a gate, not decoration: the threshold has to appear in the SQL.
    assert str(reg.READ_TIME_COVERAGE.min_ratio) in spec.value_sql()


def test_capacity_and_volume_adoption_do_not_collide():
    """The exact conflation this registry exists to prevent, asserted rather than commented.

    Both domains ship a column called `pct_mosaic`. Volume's divides by all exams; Capacity's
    divides by on-shift cases, a ~25%-smaller denominator. `METRICS` is a dict comprehension, so
    a shared *key* would have made one silently replace the other with no error anywhere - the
    reader would simply have seen the wrong number under the right name.
    """
    vol, cap = reg.get_metric("pct_mosaic"), reg.get_metric("capacity_pct_mosaic")
    assert vol.key != cap.key
    assert vol.output_name == cap.output_name == "pct_mosaic"
    assert vol.denominator != cap.denominator
    assert vol.domain != cap.domain
    assert vol.grain == "exam" and cap.grain == "shift"

    # And the guard that keeps it that way: re-registering under the colliding key must raise at
    # import, not resolve to the last one declared.
    colliding = reg.MetricSpec(
        key="pct_mosaic", label="dupe", domain="capacity", solutions=(),
        source="x", numerator="1", definition="d", lifted_from="test",
    )
    original = reg.CAPACITY_METRICS
    try:
        reg.CAPACITY_METRICS = original + (colliding,)
        raised = False
        try:
            reg._validate_registry()
        except ValueError as exc:
            raised = "duplicate metric key" in str(exc)
        assert raised, "a duplicate metric key passed validation"
    finally:
        reg.CAPACITY_METRICS = original
    reg._validate_registry()  # and the real registry is still valid afterwards


def test_solution_modes_reference_the_store_not_a_copy():
    """Reporting / AI Drafting / Capture are the product's solution axis, and their column
    triples are `efficiency_store._MODE_EXPRS` *by identity* - the same discipline as
    `_LOCAL_REGION_CASE_SQL`. Equality would pass against a retyped copy that later drifted;
    `is` cannot."""
    from app.db import efficiency_store

    assert set(reg.EFFICIENCY_MODES) == set(efficiency_store._MODE_EXPRS)
    for key, mode in reg.EFFICIENCY_MODES.items():
        assert mode.exprs is efficiency_store._MODE_EXPRS[key], (
            f"mode {key!r} holds a copy of its column triple, not the store's tuple"
        )
        assert mode.description.strip()

    # full_mosaic excludes Capture. That is the upstream ETL's definition of Is_Mosaic_Row, not
    # an oversight, and the description has to say so or someone will "fix" it.
    assert "Capture is deliberately NOT included" in reg.EFFICIENCY_MODES["full_mosaic"].description


def test_non_composable_metrics_refuse_to_emit_sql():
    """The Efficiency pair is computed in SQLite with a /60 on the Mosaic side and not on the
    baseline side (the baseline column is pre-weighted by duration in seconds). A composer that
    emitted "equivalent" SQL would be a second implementation of exactly the step that is easy to
    get wrong by a factor of 60. It refuses instead, and the asymmetry is recorded as a caveat."""
    for key in ("mosaic_tbwu_per_min", "baseline_tbwu_per_min"):
        spec = reg.get_metric(key)
        assert not spec.composable
        try:
            spec.value_sql()
            raise AssertionError(f"{key} composed SQL it has no right to compose")
        except ValueError as exc:
            assert "not composed here" in str(exc)
        assert any("factor of 60" in c for c in spec.caveats), key


def test_unavailable_columns_are_declared_not_silently_null():
    """Five capacity columns are hardcoded `CAST(NULL AS DOUBLE)` / `CAST(0 AS DOUBLE)` because
    their source is unreachable under this app's grants. Before the registry, a consumer could
    not tell those from a measured zero. `trust="unavailable"` is the difference between a gap
    and a lie."""
    unavailable = {m.key for m in reg.CAPACITY_METRICS if m.trust == "unavailable"}
    assert unavailable == {
        "baseline_rvu", "baseline_rpwu", "baseline_rvu_per_hour",
        "adjustment_rvu", "adjustment_tbwu",
    }
    for key in unavailable:
        spec = reg.get_metric(key)
        assert spec.numerator in ("CAST(NULL AS DOUBLE)", "CAST(0 AS DOUBLE)")
        assert "Not computed" in spec.definition or "Always 0" in spec.definition


def test_capacity_additional_pct_stays_coverage_only():
    """A deliberate omission, asserted so it is not "helpfully" filled in later.

    `capacity_additional_pct` renders (current - baseline) / baseline from
    `get_capacity_with_baseline`, a query this registry has not folded in. The nearest available
    metric, `capacity_rvu_per_hour`, is the *current* side only - mapping it would put a
    confidently wrong definition under a number, which is worse than putting none.
    """
    feat = reg.describe_feature("capacity_additional_pct")
    assert feat["metrics"] == []
    assert feat["coverage"] is not None
    for other in ("capacity_figure", "shift_utilization", "efficiency_metric", "capacity_coverage"):
        assert reg.describe_feature(other)["metrics"], f"{other} should resolve in Wave 2"


def test_coverage_threshold_is_imported_not_retyped():
    """The threshold that actually NULLs a value lives in `mosaic_service`; this is the one
    place it is published. A second literal `0.75` anywhere in the registry would mean the badge
    and the suppression could disagree - which is the four-copies problem in miniature."""
    from app.services import mosaic_service

    assert reg.READ_TIME_COVERAGE.min_ratio is mosaic_service._MIN_READ_TIME_COVERAGE
    assert reg.READ_TIME_COVERAGE.min_pct_label == "75%"


def test_ai_context_grounds_on_the_registry_without_losing_the_narrative():
    """The wiring, asserted end to end: `explain_data_point`'s grounding must contain the
    registry's definition text *and* keep the hand-written program narrative beside it.

    `_grounding_for` is additive on purpose. Four of the 21 features - the ones in
    `UNREGISTERED_FEATURES` - have no metric at all, so a registry-only prompt would say nothing
    about them; and the registry has no field for program narrative like "three independent
    tracks", so a narrative-only prompt loses every governed definition. The plan's phrasing
    ("retire the 13 methodology constants in favour of registry metadata") would have deleted
    one side of that.

    The caveat-duplication half of this lives in
    `test_the_coverage_caveat_reaches_the_prompt_exactly_once`, which checks every
    coverage-bearing feature rather than the three this test used to name.
    """
    from app.services import ai_context_service as ai

    assert ai._FALLBACK is reg.AI_FALLBACK_TEXT

    adoption = ai._grounding_for("adoption_rollout")
    assert reg.get_metric("pct_mosaic").definition in adoption
    assert "three independent tracks" in adoption

    # Unmapped features must degrade to exactly what they said before the registry existed.
    assert ai._grounding_for("sentiment") == ai._FEATURE_GROUNDING["sentiment"]


def test_typescript_carries_no_second_copy_of_the_methodology():
    """The Python/TypeScript seam, asserted - §Risks calls hand-sync across it a drift class, and
    `_priority_tier_counts` is already duplicated there.

    Two separate things are checked, because they are resolved two different ways:

      * The *prose* must be gone. `coverage.tsx` used to carry a ~60-word paraphrase of the
        suppression rule and `AIHoverCard.tsx` an independent copy of the fallback string. Both
        now arrive at runtime from `GET /api/mosaic/registry`, so a literal reappearing in TSX
        means someone re-typed instead of reading the snapshot.
      * The *threshold number* legitimately stays duplicated: the badge picks its colour on
        first paint, before any fetch can have resolved, so it cannot wait on the snapshot. A
        duplicated constant is fine; a silently diverging one is not, hence this assertion.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    coverage_tsx = (src / "utils" / "coverage.tsx").read_text(encoding="utf-8")
    hover_tsx = (src / "components" / "AIHoverCard.tsx").read_text(encoding="utf-8")

    m = re.search(r"MIN_READ_TIME_COVERAGE\s*=\s*([0-9.]+)", coverage_tsx)
    assert m, "coverage.tsx no longer declares MIN_READ_TIME_COVERAGE"
    assert float(m.group(1)) == reg.READ_TIME_COVERAGE.min_ratio, (
        f"TS threshold {m.group(1)} != Python {reg.READ_TIME_COVERAGE.min_ratio} - the badge and "
        f"the suppression would disagree"
    )

    # Fingerprints of the two deleted copies. Both are distinctive enough that a match means the
    # prose itself is back, not an incidental word.
    assert "158.7 TBWU/min" not in coverage_tsx, "the coverage methodology prose is back in TSX"
    assert reg.AI_FALLBACK_TEXT not in hover_tsx, (
        "AIHoverCard re-hardcoded the fallback string instead of reading ai_fallback_text"
    )


def test_the_unregistered_reason_survives_the_python_typescript_boundary():
    """The field is served, typed, and rendered - and all three have to stay true together.

    This one fails quietly in a way the others do not. `snapshot()` is served without a
    `response_model`, so an extra key on the wire that TypeScript does not declare is not an
    error anywhere: the backend keeps sending the reasons, the type says the field does not
    exist, and the card silently stops rendering them. Nothing throws, no test of the Python
    side notices, and the four features go back to being indistinguishable from a typo.

    So assert the whole chain - the key leaves Python, the interface declares it, the component
    reads it - rather than any one link.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    types_tsx = (src / "api" / "types.ts").read_text(encoding="utf-8")
    hover = (src / "components" / "AIHoverCard.tsx").read_text(encoding="utf-8")

    assert "unregistered_reason" in reg.describe_feature("sentiment"), (
        "describe_feature stopped emitting unregistered_reason - the client reads it by name"
    )
    block = re.search(r"interface RegistryFeature \{(.*?)\n\}", types_tsx, re.S)
    assert block, "types.ts no longer declares interface RegistryFeature"
    assert "unregistered_reason" in block.group(1), (
        "RegistryFeature lost unregistered_reason - the backend still sends it, so the card "
        "would render nothing for the four deliberately-undefined features and look identical "
        "to a misspelled `feature` prop"
    )
    assert "registryFeature?.unregistered_reason" in hover or (
        "registryFeature.unregistered_reason" in hover
    ), "AIHoverCard no longer renders the reason, so it is typed and served but invisible"


def test_read_time_savings_agrees_across_its_three_copies():
    """`read_time_change_pct` is written out three times, and all three must mean one thing.

    The formula lives in:

      1. `cache_service._read_time_change` - the only one that actually computes the shipped
         number, for every API model that carries the field.
      2. `EfficiencyDetail.tsx:readTimeChange` - a hand-written TypeScript copy, needed because
         the RP benchmark row is assembled client-side from two rates the detail payload carries
         separately. This is precisely the Python/TypeScript seam §Risks names as a drift class.
      3. The registry's `MetricSpec`, which is what the hover cards and the AI layer read.

    (3) is the one that can drift silently: it is prose and metadata, so nothing breaks when it
    stops describing (1). Since the spec is `composable=False` there is no `value_sql()` to
    diff - but the spec still *declares* num/den/offset, and a reader is entitled to trust that
    declaration. So reconstruct the arithmetic from the declared fields and check it against the
    live function on real-shaped inputs.
    """
    spec = reg.METRICS["read_time_change_pct"]

    # The offset carries the -1, and it must not have been folded into the numerator: an additive
    # constant inside a numerator is re-applied once per group and so is wrong at every rollup
    # above the grain it was written for. This is the registry's whole reason for having `offset`.
    assert spec.offset == -1.0, "the -1 moved out of `offset` - check it was not folded into num"
    assert spec.numerator == "baseline_tbwu_per_min"
    assert spec.denominator == "mosaic_tbwu_per_min"
    assert not spec.composable, "this metric divides two app-computed rates; it has no SQL form"

    # Reconstructed from the declared fields alone - deliberately not by calling the real one.
    def from_spec(mosaic: float, baseline: float) -> float:
        return (baseline / mosaic) + spec.offset

    # (mosaic rate, baseline rate) pairs spanning both directions and the no-change case.
    for mosaic, baseline in [(0.5, 0.44), (0.44, 0.5), (0.5, 0.5), (1.25, 1.0), (0.08, 0.09)]:
        live = cache_service._read_time_change(mosaic, baseline)
        assert live is not None
        assert abs(live - from_spec(mosaic, baseline)) < 1e-12, (
            f"registry declaration and cache_service disagree at "
            f"(mosaic={mosaic}, baseline={baseline}): {from_spec(mosaic, baseline)} vs {live}"
        )

    # The sign convention, asserted rather than described. A Mosaic rate FASTER than baseline
    # (more TBWU per minute) must produce a NEGATIVE value - less time for the same work. Getting
    # this backwards is the single most consequential misread available on the surface, because
    # the wrong reading is the flattering one.
    faster = cache_service._read_time_change(0.5, 0.44)
    assert faster is not None and faster < 0, "a faster Mosaic rate must read as a saving"
    slower = cache_service._read_time_change(0.44, 0.5)
    assert slower is not None and slower > 0, "a slower Mosaic rate must read as a cost"
    assert cache_service._read_time_change(0.5, 0.5) == 0.0

    # Undefined, not zero, when the Mosaic rate is absent or zero. Returning 0.0 here would paint
    # "no change" over a slice that has no measurement at all.
    assert cache_service._read_time_change(0.0, 0.44) is None
    assert cache_service._read_time_change(None, 0.44) is None
    assert cache_service._read_time_change(0.5, None) is None

    # Copy (2). Compared as normalised source text rather than executed - there is no JS runtime
    # here - but the guards and the expression are short enough that textual equality is a real
    # check and not a fingerprint.
    tsx = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "EfficiencyDetail.tsx"
    ).read_text(encoding="utf-8")
    m = re.search(r"function readTimeChange\([^)]*\)[^{]*\{(.*?)\n\}", tsx, re.S)
    assert m, "EfficiencyDetail.tsx no longer declares readTimeChange"
    body = _norm(m.group(1))
    assert "current === 0" in body, "the TS copy lost its zero-rate guard - it would return Infinity"
    assert "baseline / current - 1" in body, (
        f"the TS copy's formula changed and no longer matches cache_service._read_time_change: {body}"
    )

    # The wording layer. `fmtReadTimeSavings` renders direction in words because the raw sign
    # convention is inverted relative to "Change vs Baseline" on the same row; if the mapping of
    # negative->faster ever flips, every number on the tile silently reverses meaning.
    m = re.search(r"function fmtReadTimeSavings\([^)]*\)[^{]*\{(.*?)\n\}", tsx, re.S)
    assert m, "EfficiencyDetail.tsx no longer declares fmtReadTimeSavings"
    assert "value < 0 ? `${pct}% faster` : `${pct}% slower`" in _norm(m.group(1)), (
        "the faster/slower mapping changed - negative must still render as 'faster'"
    )


# ----------------------------------------------------------------------------------------------
# The feature-key seam, and MVP's Python/TypeScript seam
# ----------------------------------------------------------------------------------------------

# Feature keys that appear in TSX and deliberately resolve to no metric. The declaration lives
# in `registry.UNREGISTERED_FEATURES` - beside the two dicts it is the third state of - so that
# `_validate_registry` can enforce it and `snapshot()` can serve the reasons. This file reads it
# rather than owning it: the test guards completeness, the registry owns the exemption.
_UNREGISTERED_FEATURES = reg.UNREGISTERED_FEATURES


# Three syntaxes reach `AIHoverCard`'s `feature` prop, and a scan that knows only the first has
# a blind spot exactly where a typo is least visible:
#
#   feature="efficiency_metric"                       JSX attribute - the common case
#   { key: "pct_mosaic", ..., feature: "adoption_rollout" }
#                                                     object property, then `feature={m.feature}`
#   readTimeCoverageBadge(cov, label, rpce, "efficiency_metric")
#                                                     4th positional arg, then `feature={feature}`
#
# The last two pass through a variable, so the key never appears next to the word `feature` at
# the call site. `RadMosaicScorecard.tsx` uses both. Scanning only the attribute form would have
# left four live keys - and any future typo in that descriptor array - outside the guard.
#
# The first pattern allows spaces around `=` so it also catches the default-parameter form,
# `feature = "capacity_coverage"` in coverage.tsx - which is a fourth syntax, and the one that
# decides what every un-parameterised badge in CapacityDetail resolves to.
_FEATURE_KEY_PATTERNS = (
    r'feature\s*=\s*"([a-z0-9_]+)"',
    r'feature:\s*"([a-z0-9_]+)"',
    r'readTimeCoverageBadge\([^)]*?,\s*"([a-z0-9_]+)"\s*\)',
)


def _tsx_feature_keys() -> dict[str, set[str]]:
    """Every feature key literal in the frontend, mapped key -> the files that use it."""
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    found: dict[str, set[str]] = {}
    # `.ts` as well as `.tsx`: `coverage.tsx` is TSX today, but the descriptor-array pattern is
    # plain data and nothing stops the next one living in a `.ts` module.
    for path in [*src.rglob("*.tsx"), *src.rglob("*.ts")]:
        text = path.read_text(encoding="utf-8")
        for pattern in _FEATURE_KEY_PATTERNS:
            for key in re.findall(pattern, text, flags=re.DOTALL):
                found.setdefault(key, set()).add(path.name)
    return found


def test_the_feature_key_scan_sees_the_indirect_call_sites():
    """A guard on the guard.

    `test_every_hover_card_feature_key_resolves_in_the_registry` is only as good as its scan. If
    the scan silently stops matching a syntax, it keeps passing while covering less - the failure
    mode is a green test, not a red one. These four keys reach `AIHoverCard` through a variable
    rather than a literal attribute, so they are the ones a narrower regex would drop first.
    """
    found = _tsx_feature_keys()
    for key, where in (
        ("adoption_rollout", "RadMosaicScorecard.tsx"),  # object-property form
        ("capacity_figure", "RadMosaicScorecard.tsx"),  # object-property form
        ("efficiency_metric", "RadMosaicScorecard.tsx"),  # both forms, same file
        ("capacity_coverage", "coverage.tsx"),  # helper default
    ):
        assert key in found, f"the feature-key scan no longer finds {key!r}"
        assert where in found[key], f"{key!r} found, but not in {where} - scan coverage shrank"


def test_every_hover_card_feature_key_resolves_in_the_registry():
    """The seam that fails silently and looks identical to working.

    `AIHoverCard` resolves its `feature` prop against the snapshot with `.find(...) ?? null`, so
    an unregistered key does not error - it renders an ungrounded card. The model is then asked
    to explain a number with no definition, no caveats, and no coverage rule attached, and
    produces fluent commentary anyway. There is nothing on screen to distinguish that from a
    working card.

    This caught a real one: MVP's funnel card calls `feature="mvp_status_funnel"`, and the
    registry entry was first written as `mvp_funnel`. Both spellings are plausible; only one
    resolves.
    """
    registered = set(reg.FEATURE_METRICS) | set(reg.FEATURE_COVERAGE)
    unresolved = {
        key: sorted(files)
        for key, files in sorted(_tsx_feature_keys().items())
        if key not in registered and key not in _UNREGISTERED_FEATURES
    }
    assert not unresolved, (
        "feature keys used in TSX that resolve to nothing in the registry: "
        + "; ".join(f"{k} ({', '.join(v)})" for k, v in unresolved.items())
        + " - register them in FEATURE_METRICS/FEATURE_COVERAGE, or add them to "
        "registry.UNREGISTERED_FEATURES with the reason they stay undefined"
    )


def test_the_exemption_list_is_not_a_junk_drawer():
    """Every exemption is still used, and still says why.

    Two ways the list rots once it is no longer the test's own literal. A feature gets deleted
    from the UI and its exemption outlives it, so the next reader believes a card exists that
    does not. Or a reason gets trimmed to a placeholder - and since `describe_feature` now
    *serves* the reason, an empty one renders as a blank explanatory line on the card rather
    than failing anywhere.

    `_validate_registry` catches the empty reason at import; this catches the dead key, which it
    cannot, because the registry has no view of the TSX.
    """
    used = set(_tsx_feature_keys())
    dead = sorted(set(reg.UNREGISTERED_FEATURES) - used)
    assert not dead, (
        "exempted feature keys no longer used anywhere in TSX: "
        + ", ".join(dead)
        + " - drop them from registry.UNREGISTERED_FEATURES"
    )
    for key, reason in reg.UNREGISTERED_FEATURES.items():
        assert len(reason.strip()) > 40, (
            f"{key!r} is exempted with a reason too thin to render: {reason!r} - it is shown on "
            "the hover card, so it has to explain the absence to a reader who is not us"
        )


def test_the_deliberately_undefined_features_are_served_not_omitted():
    """An undefined feature and a misspelled one must not look the same on the wire.

    Before the exemption list moved into the registry, `snapshot()` built `features` from
    `FEATURE_METRICS | FEATURE_COVERAGE` only, so these four were absent from
    `GET /api/mosaic/registry` entirely. `useRegistryFeature` returned `null` for them - exactly
    what it returns for a typo - and the card rendered bare AI text either way. The reason the
    product has for each of them was written down and then shown to nobody.
    """
    snap = reg.snapshot()
    by_key = {f["feature"]: f for f in snap["features"]}
    for key, reason in reg.UNREGISTERED_FEATURES.items():
        assert key in by_key, f"{key!r} is exempted but missing from snapshot()['features']"
        entry = by_key[key]
        assert entry["unregistered_reason"] == reason
        # The honest shape: a reason, and nothing pretending to be a definition.
        assert entry["metrics"] == [], f"{key!r} is exempted yet carries metrics"
        assert entry["coverage"] is None, f"{key!r} is exempted yet carries a coverage spec"
        assert entry["grounding"] == "", f"{key!r} is exempted yet carries registry grounding"

    for key in set(reg.FEATURE_METRICS) | set(reg.FEATURE_COVERAGE):
        assert by_key[key]["unregistered_reason"] == "", (
            f"{key!r} is registered and would render an 'undefined' note next to its own "
            "definition"
        )


def test_the_volume_solution_axis_matches_the_registrys_tags():
    """The solution axis means two different things, and only one of them is a filter.

    On Efficiency, picking "AI Drafting" recomputes the same measure over a different subset of
    exams - `efficiency_store._MODE_EXPRS`, one expression per mode. On Volume it selects a
    different *column*: `drafting_exams` and `mosaic_exams` are separate measures the ETL emits
    side by side. The same control, two mechanisms. Rolling the toggle onto a third page without
    noticing which one applies is how a page ends up filtering a column that was never a filter.

    `VolumeDetail.VOLUME_SOLUTION_COLUMNS` files each column under a solution. That is a layout
    decision and belongs on the page - but *which solution a column belongs to* is a governed
    fact, and this asserts the page has not formed its own opinion about it.
    """
    page = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "pages"
        / "VolumeDetail.tsx"
    ).read_text(encoding="utf-8")

    block = re.search(r"VOLUME_SOLUTION_COLUMNS\s*=\s*\{(.*?)\n\}\s*as const", page, re.DOTALL)
    assert block, "VOLUME_SOLUTION_COLUMNS is no longer parseable - the axis map moved or changed shape"

    filed: dict[str, list[str]] = {}
    for solution, body in re.findall(r"(\w+):\s*\{([^}]*)\}", block.group(1)):
        filed[solution] = re.findall(r'"([a-z0-9_]+)"', body)
    assert filed, "no solutions parsed out of VOLUME_SOLUTION_COLUMNS"

    for solution, keys in filed.items():
        assert solution in reg.EFFICIENCY_MODES, (
            f"{solution!r} is not one of the registry's solution modes: "
            f"{sorted(reg.EFFICIENCY_MODES)}"
        )
        for key in keys:
            spec = reg.METRICS.get(key)
            assert spec is not None, f"VolumeDetail files {key!r} under {solution!r}, but the registry has no such metric"
            assert spec.domain == "utilization", (
                f"{key!r} is domain {spec.domain!r}, not utilization - the Volume axis would be "
                "selecting a column from another domain"
            )
            assert solution in spec.solutions, (
                f"VolumeDetail files {key!r} under the {solution!r} solution, but the registry "
                f"tags it {sorted(spec.solutions)} - one of the two is wrong, and the page is "
                "not the governed copy"
            )

    # Capture's absence is the claim most worth pinning: the page tells the user it is "not
    # measurable on Volume", and that has to stay true of the registry rather than just of the
    # page. `total_exams` carries all three tags because it is the shared denominator, so it is
    # excluded - a solution is only *measurable* if something other than the denominator
    # carries it.
    measurable = {
        s
        for m in reg.METRICS.values()
        if m.domain == "utilization" and len(m.solutions) < 3
        for s in m.solutions
    }
    assert "capture" not in measurable, (
        "a capture-tagged volume metric now exists - VolumeDetail still tells the user Capture "
        "has no exam-count column upstream, which is now a lie. Add it to "
        "VOLUME_SOLUTION_COLUMNS and update VOLUME_UNAVAILABLE_NOTE."
    )
    assert measurable == set(filed), (
        f"the Volume axis offers {sorted(filed)} but the registry measures {sorted(measurable)} "
        "- a solution is either missing from the toggle or offered without a column"
    )


def test_capacity_has_no_solution_scoped_metric():
    """Why CapacityDetail has no solution axis - asserted, so it can stop being true loudly.

    Volume and Efficiency both carry the toggle. The natural next move was to roll it onto
    Capacity, and the registry is the reason not to: every capacity metric is `grain="shift"`
    and tagged with all three solutions. A shift is not worked "on Drafting" - it is a scheduled
    block holding a mix of drafted and non-drafted exams, and its RVU, hours and utilization
    are properties of the block.

    A toggle there would be the worst available failure: selecting a solution would leave every
    headline number *identical* while telling the reader it had been scoped. No value changes,
    so nothing looks wrong.

    Splitting capacity by solution needs the measure re-derived at exam grain against scheduled
    time. If that ever lands, this test fails - which is the point. The failure message is the
    handoff note saying the axis is now buildable, rather than a page comment that has quietly
    become false.
    """
    capacity = {k: m for k, m in reg.METRICS.items() if m.domain == "capacity"}
    assert capacity, "no capacity metrics in the registry - this guard is now watching nothing"

    all_three = set(reg.EFFICIENCY_MODES) - {"full_mosaic"}
    scoped = {k: m.solutions for k, m in capacity.items() if set(m.solutions) != all_three}
    assert not scoped, (
        f"capacity metrics are now solution-scoped: {scoped}. CapacityDetail.tsx states on the "
        "page that capacity cannot be split by solution (CAPACITY_NO_SOLUTION_AXIS_NOTE) - that "
        "note is now wrong, and the SolutionAxis can be wired in as it was on VolumeDetail."
    )

    off_grain = {k: m.grain for k, m in capacity.items() if m.grain != "shift"}
    assert not off_grain, (
        f"capacity metrics no longer all sit at shift grain: {off_grain}. Shift grain is the "
        "whole reason a solution cannot scope them; re-check the page note before trusting it."
    )


def test_the_priority_tiering_rule_agrees_across_its_three_copies():
    """The last of the twelve hand-synced definitions, and the widest one.

    `computePriorities()` carries a comment that says outright: "there's no shared code between
    the two runtimes, so keep both in sync by hand if either threshold ever changes." That is an
    honest statement of a risk and no defence against it. Five numbers have to match across
    `ai_context_service._priority_tier_counts` (grounds the narrative), `MvpAllRadiologists.tsx`
    (renders the badge a radiologist may be shown), and the registry caveat that tells a CEO what
    the badge means.

    A drift here is quiet and asymmetric: the narrative would say "11 Priority 1 radiologists"
    while the table showed a different set, and both would look right in isolation.
    """
    ts_path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "pages"
        / "mvp"
        / "MvpAllRadiologists.tsx"
    )
    ts = ts_path.read_text(encoding="utf-8")
    py = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "ai_context_service.py"
    ).read_text(encoding="utf-8")
    caveats = " ".join(reg.METRICS["mvp_priority_tier_rads"].caveats)

    # 1. The D&C floor. Same number, three spellings: `dc < 5`, `dc < 5`, "below +5%".
    assert re.search(r"dc\s*!=\s*null\s*&&\s*dc\s*<\s*5\b", ts), "TS D&C threshold moved off +5"
    assert re.search(r"dc is not None and dc < 5\b", py), "Python D&C threshold moved off +5"
    assert "+5%" in caveats, "registry caveat no longer states the +5% D&C threshold"

    # 2. The three per-program floors, as (TS column, threshold) pairs.
    for column, threshold in (
        ("xr_drafting_efficiency_change_pct", -20),
        ("ct_head_efficiency_change_pct", -20),
        ("us_capture_efficiency_change_pct", -37),
    ):
        assert re.search(rf"{column}\s*<\s*{threshold}\b", ts), f"TS: {column} no longer < {threshold}"
        assert re.search(
            rf'"{column}",\s*{threshold}\b', py
        ), f"Python: {column} no longer < {threshold}"
    assert "-20%" in caveats and "-37%" in caveats, "registry caveat lost a program threshold"

    # 3. The top-third cutoff. `Math.ceil(n/3)` and `-(-n // 3)` are the same function written
    #    two ways - this is the pair most likely to drift into floor-vs-ceil disagreement, which
    #    would move exactly one radiologist between Priority 1 and 2 at most cohort sizes and so
    #    would never look obviously wrong.
    assert re.search(r"Math\.ceil\(\s*ranked\.length\s*/\s*3\s*\)", ts), "TS cutoff is no longer ceil(n/3)"
    assert re.search(r"-\(-len\(ranked\)\s*//\s*3\)", py), "Python cutoff is no longer ceil(n/3)"
    assert "top third" in caveats, "registry caveat no longer states the top-third rule"

    # 4. Behaviour, not just text: the precedence order. `veryNegativeModality` is only reachable
    #    in the `else` branch, so a radiologist who is BOTH high-productivity-with-flat-D&C and
    #    sharply down on a program must land in Priority 1, never Priority 3. Reordering those
    #    branches would keep every threshold above intact and still change who gets escalated.
    from app.services.ai_context_service import _priority_tier_counts

    both = {
        "npi": 1,
        "baseline_capacity_tbwu_9h": 100.0,
        "drafting_captured_efficiency_change_pct": 0.0,  # flat -> low_or_negative_dc
        "xr_drafting_efficiency_change_pct": -50.0,  # also very negative
    }
    counts = _priority_tier_counts([both])
    assert counts["Priority 1"] == 1 and counts["Priority 3"] == 0, (
        f"precedence changed: a radiologist matching both rules landed as {counts} - "
        "Priority 1 must win, or the escalation list silently reprioritises"
    )


def test_every_feature_key_is_grounded_on_the_backend():
    """The third list of feature keys, and the one with no guard until now.

    A key travels through three places: the TSX call site, `registry.FEATURE_METRICS` (what the
    card *shows*), and `ai_context_service._FEATURE_GROUNDING` (what the model is *told*). The
    registry half fails loudly-ish - a missing definition leaves a visibly thinner card. The
    grounding half does not: `_grounding_for` falls back, the model still answers, and the only
    symptom is commentary written without the methodology it should have been reasoning from.
    That is the most expensive failure in the set, because it reads as authoritative.

    All three agree exactly: 24 keys in TSX, 24 in `_FEATURE_GROUNDING`, and 24 across the
    registry's three dicts (19 in FEATURE_METRICS, 10 in FEATURE_COVERAGE overlapping all but
    `capacity_additional_pct`, 4 exempted). That is true by assertion, not by coincidence - which
    is the point of the test. The counts in this sentence are prose and nothing enforces them; the
    equalities below are what hold. If you are reading them because a key count surprised you,
    trust the assertions and re-count, then fix this paragraph.
    """
    from app.services.ai_context_service import _FEATURE_GROUNDING

    used = set(_tsx_feature_keys())
    grounded = set(_FEATURE_GROUNDING)

    assert not (used - grounded), (
        f"feature keys the UI calls with no backend grounding: {sorted(used - grounded)} - the "
        "model will answer anyway, with no methodology behind it"
    )
    assert not (grounded - used), (
        f"grounding entries no surface calls: {sorted(grounded - used)} - stale methodology "
        "prose outlives the tile it described"
    )
    registered = set(reg.FEATURE_METRICS) | set(reg.FEATURE_COVERAGE)
    assert not (registered - grounded), (
        f"registry features with no grounding: {sorted(registered - grounded)} - the card would "
        "show a governed definition above commentary that never saw it"
    )
    # The registry's three dicts partition the feature space, with no fourth, undeclared state.
    # An exempted feature is the one that most needs hand-written grounding - there is no
    # MetricSpec behind it - so it is exactly the one whose absence here would go unnoticed.
    assert grounded == registered | set(reg.UNREGISTERED_FEATURES), (
        "the grounding table and the registry's three dicts have drifted: only in grounding "
        f"{sorted(grounded - registered - set(reg.UNREGISTERED_FEATURES))}, only in the registry "
        f"{sorted((registered | set(reg.UNREGISTERED_FEATURES)) - grounded)}"
    )


# Read-time-gated features whose lineage does not actually enforce the gate, so the shared
# caveat's central promise - "below 75% Utilization is suppressed and shows '-'" - would be a
# lie in their prompt. An exemption list of one, named rather than special-cased inline, because
# the next entry here is a decision someone should have to write a reason for.
_UNGATED_LINEAGE = {"shift_utilization"}


def test_the_coverage_caveat_reaches_the_prompt_exactly_once():
    """Duplication, not absence, is the live risk at this seam.

    `_grounding_for` concatenates registry text and the hand-written methodology constant. The
    registry's `grounding_for` deliberately omits the ~200-word coverage caveat *because* the
    methodology constants already import and append it - a comment in each file says so. Nothing
    enforced it. Adding the caveat to `grounding_for` for symmetry would look like a tidy-up and
    would silently put the same 200 words into every capacity and efficiency prompt twice.

    Twice is worse than zero here: the model weights repeated text, and a prompt that states the
    suppression rule two different times is how you get commentary that hedges a number the rule
    did not actually suppress.

    One read-time-gated feature is exempt, and the exemption is the interesting half. See
    `_UNGATED_LINEAGE` below.
    """
    from app.services import ai_context_service as ai

    # A distinctive clause from the middle of the caveat - matching the whole string would pass
    # vacuously the moment anyone rewraps it.
    needle = "a scheduled shift has no"
    assert needle in reg.READ_TIME_COVERAGE.caveat, "the needle no longer appears in the caveat"

    checked = 0
    for feature in sorted(reg.FEATURE_COVERAGE):
        if reg.FEATURE_COVERAGE[feature] != reg.READ_TIME_COVERAGE.key:
            continue
        if feature in _UNGATED_LINEAGE:
            continue
        checked += 1
        text = ai._grounding_for(feature)
        # Exactly once, not at-most-once: zero is its own failure. A read-time-gated feature
        # whose prompt never states the gate produces confident commentary on a number the
        # product itself declines to show.
        assert text.count(needle) == 1, (
            f"the coverage caveat appears {text.count(needle)} times in the prompt for "
            f"{feature!r} - it must appear exactly once; registry.grounding_for omits it "
            "precisely because the methodology constants already append it"
        )
    assert checked >= 4, (
        f"only {checked} read-time-gated features were checked - the loop filter has drifted "
        "from FEATURE_COVERAGE and is now silently passing by examining almost nothing"
    )
    # And the registry half is the one that must stay silent about coverage.
    for feature in reg.FEATURE_COVERAGE:
        assert needle not in reg.grounding_for(feature), (
            f"registry.grounding_for({feature!r}) now carries the coverage caveat - that is the "
            "second copy, and ai_context_service already owns the first"
        )


def test_the_ungated_lineage_states_its_gap_in_its_own_words():
    """An exemption has to cost something, or it is just a way to switch a test off.

    `shift_utilization` is declared read-time-gated in `FEATURE_COVERAGE` and is not actually
    gated: `tbl_shift_utilization` carries no coverage column, so every value renders including
    ones built from almost no read time. That makes the shared caveat *inapplicable* rather than
    merely redundant - it promises suppression this lineage does not perform, and a model told
    the bad numbers were withheld will read the surviving low ones as certainly real. Confident,
    specific and wrong beats silence only in the wrong direction.

    So the exemption is from the shared text, not from the obligation. Assert both halves: the
    suppression promise must be absent, and a feature-specific statement of the same gap must be
    present. Without the second assertion `_UNGATED_LINEAGE` would be a one-word opt-out of the
    only check standing between a CEO-facing utilization number and commentary that never
    mentions its numerator may be missing.
    """
    from app.services import ai_context_service as ai

    for feature in sorted(_UNGATED_LINEAGE):
        assert reg.FEATURE_COVERAGE.get(feature) == reg.READ_TIME_COVERAGE.key, (
            f"{feature!r} is exempted from the read-time caveat but is no longer declared "
            "read-time-gated - delete it from _UNGATED_LINEAGE rather than leaving a dangling "
            "exemption that silently covers nothing"
        )
        text = ai._grounding_for(feature)
        assert "a scheduled shift has no" not in text, (
            f"the shared caveat is back in {feature!r}'s prompt - it promises a suppression "
            "this lineage does not perform"
        )
        # The gap itself, in words that do not claim the number was withheld. Two independent
        # needles: the threshold (composed from the registry, so it cannot drift) and the
        # not-enforced fact, which is the whole reason this feature differs from the other four.
        assert f"{reg.READ_TIME_COVERAGE.min_ratio:.0%}" in text, (
            f"{feature!r}'s prompt no longer states the read-time threshold at all"
        )
        assert "not enforced on this lineage" in text, (
            f"{feature!r}'s prompt stopped saying the floor is unenforced here, which is the "
            "one fact that distinguishes it from the four features that do suppress"
        )


def test_no_methodology_constant_restates_a_governed_definition():
    """The other half of the same risk: two definitions of one metric in one prompt.

    `_grounding_for` is additive by design - the registry supplies the definition, the constant
    supplies program narrative the registry has no field for. That split only holds while the
    constant does not *also* define the metric. If someone pastes a definition into the
    methodology prose, the prompt carries two statements of the same thing, and they drift apart
    the first time only one of them is corrected. The model then has no way to know which is
    current, and neither does a reader of either file.
    """
    from app.services.ai_context_service import _FEATURE_GROUNDING

    for feature, keys in sorted(reg.FEATURE_METRICS.items()):
        narrative = _FEATURE_GROUNDING.get(feature, "")
        for key in keys:
            definition = reg.get_metric(key).definition
            assert definition not in narrative, (
                f"the methodology constant for {feature!r} restates {key!r}'s registry "
                "definition verbatim - delete the copy; _grounding_for already prepends it"
            )


def test_registered_features_are_not_dead_keys():
    """The same seam from the other side.

    A registered key that no surface calls is a definition nobody reads, and it rots: the prose
    stays while the tile it described is rewritten or removed. Cheaper to catch here than to
    discover when a CEO asks what a stale caveat refers to.
    """
    used = set(_tsx_feature_keys())
    registered = set(reg.FEATURE_METRICS) | set(reg.FEATURE_COVERAGE)
    dead = sorted(registered - used)
    assert not dead, (
        f"registry features no surface calls: {dead} - either wire them up or remove them"
    )


def test_the_mvp_plausibility_ceiling_is_one_number_in_three_places():
    """Same discipline as the read-time floor, and a harder case.

    The magnitude ceiling is enforced in `mvp_dashboard_stats.py` (which grounds the AI
    narrative) and again in `mvpDashboardStats.ts` (which renders the screen), with the registry
    as the third copy. The registry imports the Python constant rather than retyping it, so only
    the TypeScript copy can drift - and if it does, the number on screen and the number the model
    explains would disagree about which radiologists count as improving.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    ts = (src / "utils" / "mvpDashboardStats.ts").read_text(encoding="utf-8")

    m = re.search(r"IMPLAUSIBLE_PCT_MAGNITUDE\s*=\s*([0-9.]+)", ts)
    assert m, "mvpDashboardStats.ts no longer declares IMPLAUSIBLE_PCT_MAGNITUDE"
    assert float(m.group(1)) == _IMPLAUSIBLE_PCT_MAGNITUDE, (
        f"TS ceiling {m.group(1)} != Python {_IMPLAUSIBLE_PCT_MAGNITUDE}"
    )
    # And the registry's gate is derived from the Python constant, not typed a fourth time.
    assert reg.MVP_PLAUSIBILITY.min_ratio == _IMPLAUSIBLE_PCT_MAGNITUDE / 100.0
    assert reg.MVP_PLAUSIBILITY.direction == "max", (
        "the plausibility gate is a ceiling on the value's own magnitude, not a floor under a "
        "coverage ratio - flipping this silently reverses the sentence on the hover card"
    )


def test_the_escalation_owner_map_is_not_retyped():
    """'Program Specific' reports as 'Development' - a rename, not a pass-through.

    It is the one entry a reader would 'correct' on sight, which is exactly why both runtimes
    have to be checked against each other rather than against intuition.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    ts = (src / "utils" / "mvpDashboardStats.ts").read_text(encoding="utf-8")
    for crm, owner in _ESCALATION_OWNER_MAP.items():
        # Quotes are optional on the key: TS leaves identifier-safe keys bare ("Mentorship:")
        # and quotes only the one with a space ("Program Specific":).
        assert re.search(rf'["\']?{re.escape(crm)}["\']?\s*:\s*["\']{re.escape(owner)}["\']', ts), (
            f"mvpDashboardStats.ts does not map {crm!r} -> {owner!r} as Python does"
        )


def test_the_coverage_sentence_is_rendered_not_rebuilt():
    """`AIHoverCard` must read `coverage.sentence`, not compose one from the parts.

    It used to compose one, and the template it used began with a hardcoded "Below {x}" - correct
    for the only spec that existed, and exactly backwards for a `direction="max"` spec, which
    suppresses values *above* its threshold. The composed sentence now lives next to the fields
    it describes so a third gate shape breaks a property loudly rather than mis-describing itself
    quietly on a CEO surface.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    hover = (src / "components" / "AIHoverCard.tsx").read_text(encoding="utf-8")
    assert "coverage.sentence" in hover, "AIHoverCard no longer renders the composed sentence"
    # The list formatter is the structural tell: composing a sentence from `suppresses` and
    # `shows_anyway` requires it, so its absence is what makes recomposition hard to do by
    # accident. Matched with the call parenthesis so the comment recording its removal does not
    # itself trip this.
    assert "listOf(" not in hover, (
        "AIHoverCard is building the coverage sentence again - the direction would be hardcoded"
    )
    # And the property itself still answers both shapes.
    assert reg.READ_TIME_COVERAGE.sentence.startswith("Below ")
    assert reg.MVP_PLAUSIBILITY.sentence.startswith("Above ")


def test_mvp_metrics_declare_no_dimensions_they_cannot_join_on():
    """Dynamics Practice is free text with no MDM key; NPI is the only reliable join.

    §B2 pre-committed to refusing a Practice or Local Region group-by on Deployment rather than
    approximating the join. MVP reads the same table, so the same rule applies one wave early -
    and `allowed_dims=()` is what makes `validate_scope` refuse rather than mis-join.
    """
    for spec in reg.MVP_METRICS:
        assert spec.allowed_dims == (), (
            f"{spec.key} declares dimensions {spec.allowed_dims} - MVP rows come from Dynamics, "
            f"where only NPI joins reliably"
        )
        assert not spec.composable, f"{spec.key} must be composable=False - it is computed in app"
        assert spec.trust == "app", f"{spec.key} is not governed EDW lineage"
        assert spec.grain == "radiologist", f"{spec.key} is not at radiologist grain"


# --------------------------------------------------------------------------------------------
# `lifted_from` - provenance that resolves, or it is just a comment
# --------------------------------------------------------------------------------------------
#
# Every MetricSpec carries `lifted_from`: the file, and usually the symbol, the expression was
# taken from. registry.py:337 describes these as enforced here. Until this test existed they
# were not: `lifted_from` appeared exactly once in this file, inside the *failure message* of
# test_expressions_are_verbatim_substrings. A string that is only ever printed when something
# else fails is not a check - it is a comment with a colon in it, and it rots the moment a
# function is renamed or a module moves.
#
# That is the house failure class restated one level up. The module docstring above warns that
# a hand-written checklist goes stale while still reading as authoritative; a provenance field
# nothing resolves is the same thing wearing a dataclass.

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Lifted strings come in five shapes and a parser that assumes `path:symbol` breaks on three of
# them. In the order they must be handled:
#   1. bare path                       _MVP_SRC
#   2. path:symbol                     f"{_MVP_SRC}:compute_status_funnel"
#   3. path:symbol (qualifier)         f"{_MVP_UI_SRC}:scopeRows (mammo)"
#   4. path (qualifier)                f"{_MVP_SRC} (mentor_match block)"   <- no colon at all
#   5. path:symbolA / symbolB          _EFFICIENCY_SRC, two symbols in one string
# Strip the trailing parenthetical first: in shape 4 it is all that stands between the path and
# a stat() call on "…mvp_dashboard_stats.py (mentor_match block)".
_QUALIFIER_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_lifted(raw: str) -> tuple[str, list[str]]:
    path_and_syms = _QUALIFIER_RE.sub("", raw).strip()
    path, _, blob = path_and_syms.partition(":")
    symbols = [s.strip() for s in blob.split(" / ") if s.strip()]
    return path.strip(), symbols


def _defines(text: str, symbol: str) -> bool:
    """Is `symbol` *defined* here, as opposed to merely mentioned?

    Three forms, all of them actually in use: `def x(` (_rate, scope_rows), a module-level
    constant `X = ` (_VOLUME_MEASURES_SQL, EXCLUSION_REASON_GLOSSARY), and TypeScript's
    `export function x(`. A substring search would pass on a call site or a docstring, which
    is the drift this is meant to catch - the symbol is gone, the callers are not.
    """
    esc = re.escape(symbol)
    return re.search(rf"^(?:async\s+)?def\s+{esc}\s*\(", text, re.M) is not None or (
        re.search(rf"^class\s+{esc}\b", text, re.M) is not None
    ) or re.search(rf"^{esc}\s*(?::[^=\n]+)?=", text, re.M) is not None or (
        re.search(rf"^export\s+(?:async\s+)?function\s+{esc}\s*[(<]", text, re.M) is not None
    )


# Declared one-sided definitions: computed in TypeScript, with no Python counterpart, so the AI
# narrative cannot cite them. registry.py already says so in prose on the metrics themselves
# (see the computeWeeklyEngagementTrend caveat); this records it mechanically.
#
# Deliberately NOT a static string list. A list like this goes stale silently the day someone
# writes the Python half - it would keep licensing a second source of truth that is now a
# genuine parity pair. So the test asserts the absence it claims, and fails if the absence ends.
#
# scopeRows is the worked example of why that matters: it *looks* TypeScript-only and is not.
# backend/app/data/mvp_dashboard_stats.py:95 defines scope_rows, and the registry already points
# a separate metric at it. Listing scopeRows here would have been a false declaration.
_TS_ONLY = {
    "getEffLossPrograms": "eff_loss_programs",
    "computeWeeklyEngagementTrend": "compute_weekly_engagement_trend",
}


def test_every_lifted_from_resolves_to_a_real_file():
    """The path half of `lifted_from` must exist on disk.

    A moved or renamed module is the cheap half of drift and the easy half to catch: nothing
    else in the app reads these strings, so a stale one survives every refactor, every import
    fix and every test run, and is only discovered by a reader who goes looking for the source
    of a number and finds nothing there.
    """
    seen = 0
    for spec in reg._all_specs():
        assert spec.lifted_from, f"{spec.key} declares no provenance at all"
        path, _ = _parse_lifted(spec.lifted_from)
        assert path.startswith(("backend/", "frontend/")), (
            f"{spec.key}: lifted_from must be repo-relative and start at backend/ or frontend/, "
            f"got {path!r} (from {spec.lifted_from!r})"
        )
        assert (_REPO_ROOT / path).is_file(), (
            f"{spec.key}: lifted_from points at {path}, which does not exist. The expression "
            f"was moved or the module was renamed; repoint it at wherever it lives now."
        )
        seen += 1
    # Guards against the whole test passing vacuously if _all_specs() ever returns empty.
    assert seen >= 20, f"only {seen} specs checked - _all_specs() looks broken, not clean"


def test_every_lifted_from_symbol_is_defined_where_it_claims():
    """The symbol half must be *defined* in that file, not merely mentioned in it.

    This is the half that catches a rename. `_rate` becoming `_tbwu_rate` leaves the path valid
    and the provenance wrong, and the registry entry still reads as though a reader could go
    verify the expression against its source.
    """
    checked = 0
    for spec in reg._all_specs():
        path, symbols = _parse_lifted(spec.lifted_from)
        if not symbols:
            continue  # shapes 1 and 4: a whole-module reference claims no symbol.
        text = (_REPO_ROOT / path).read_text(encoding="utf-8")
        for sym in symbols:
            assert _defines(text, sym), (
                f"{spec.key}: lifted_from names {sym!r} in {path}, but nothing there defines it "
                f"(looked for 'def {sym}(', '{sym} =', 'class {sym}', "
                f"'export function {sym}('). Renamed, or the provenance is stale."
            )
            checked += 1
    assert checked >= 20, f"only {checked} symbols checked - the parser matched almost nothing"


def test_the_typescript_only_allow_list_invalidates_itself():
    """Each declared TS-only symbol must still have no Python counterpart.

    §Risks names this exactly: "Python <-> TypeScript hand-sync ... Every registry value
    crossing that boundary needs a parity test or it will drift." The two listed here are
    one-sided *today*, which is a fact about the code and not a permanent property of it. The
    moment someone writes the Python half, the honest state changes from "the narrative cannot
    cite this" to "two runtimes compute this and nothing compares them" - the worse of the two,
    because it reads as covered.

    So the allow-list is asserted, not trusted. If this fails, the fix is to delete the entry
    and repoint `lifted_from` at the Python definition - not to widen the list.
    """
    backend_app = _REPO_ROOT / "backend" / "app"
    sources = list(backend_app.rglob("*.py"))
    assert sources, f"no Python sources found under {backend_app} - the search itself is broken"

    for ts_symbol, py_name in _TS_ONLY.items():
        for py_file in sources:
            text = py_file.read_text(encoding="utf-8")
            assert not _defines(text, py_name), (
                f"{ts_symbol} is declared TypeScript-only, but {py_file.relative_to(_REPO_ROOT)} "
                f"now defines {py_name}. These are two implementations of one number with "
                f"nothing comparing them. Either repoint the metric's lifted_from at the Python "
                f"definition and add a parity assertion, or delete the {ts_symbol} entry from "
                f"_TS_ONLY - do not leave both."
            )

    # scope_rows exists in both runtimes, so it must never be declared one-sided. Stated as its
    # own assertion because this is the mistake the list invites, not a hypothetical.
    assert "scopeRows" not in _TS_ONLY, (
        "scopeRows has a Python twin at backend/app/data/mvp_dashboard_stats.py:scope_rows and "
        "the registry already cites it. It is a parity pair, not a one-sided definition."
    )


def test_frontend_provenance_stays_frontend_and_backend_stays_backend():
    """A `.ts` path may not be claimed by a metric the AI narrative grounds on, and vice versa.

    Cheap, but it pins the one thing the two halves above cannot see: that the *runtime* a
    number is computed in matches the prefix recorded for it. A backend path ending in `.ts`,
    or a frontend one ending in `.py`, means the entry was copy-edited rather than re-derived.
    """
    for spec in reg._all_specs():
        path, _ = _parse_lifted(spec.lifted_from)
        if path.startswith("backend/"):
            assert path.endswith(".py"), f"{spec.key}: backend provenance {path} is not Python"
        else:
            assert path.endswith((".ts", ".tsx")), (
                f"{spec.key}: frontend provenance {path} is not TypeScript"
            )


def test_scorecard_metric_kind_agrees_with_the_registry():
    """`RadMosaicScorecard`'s hand-declared `kind` must match `MetricSpec.is_rate`.

    `kind: "rate"` says "num/den, so the radiologist figure and the practice figure are the
    same kind of number and the gap between them means something". On the Python side
    `is_rate` is `self.denominator is not None` (registry.py:385-387) - structural, not a
    hand-set flag, and *exactly that same claim*. Two independent spellings of one fact is the
    definition of a drift-prone duplicate, and this is the only one of the four hand-declared
    fields that genuinely has a registry counterpart: `ratio`, `noiseFloor` and `minSample` are
    presentation thresholds for this one surface, and `normalizeBy` names a payload column, not
    a registry denominator.

    Reading `kind` from `/api/mosaic/registry` at render time was the other option and it was
    rejected: that client is async and fail-soft by contract - "a missing registry degrades each
    consumer back to exactly what it did before the registry existed" - and a *missing* `kind`
    does not produce a missing number here, it produces a wrong one. Subtracting a practice's
    whole 2,858,482 RPWU from a radiologist's 171 is what `kind: "total"` exists to prevent, and
    it painted every radiologist in every practice red when it was absent. So the value is
    pinned in TSX, and the duplication is paid for here instead.
    """
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    tsx = (src / "pages" / "RadMosaicScorecard.tsx").read_text(encoding="utf-8")

    opener = "const METRICS: MetricDef[] = ["
    start = tsx.index(opener) + len(opener)
    block = tsx[start : tsx.index("\n];", start)]
    # Comment lines carry prose about `kind` and `normalizeBy` - including the literal strings -
    # so they must go before the per-entry regexes run, or the prose parses as an entry.
    entries = [
        ln.strip()
        for ln in block.splitlines()
        if ln.strip().startswith("{") and not ln.strip().startswith("//")
    ]

    # A regex that silently matches nothing makes every assertion below trivially true, so the
    # parse is asserted before it is trusted. Four is not arbitrary: `MetricDef.key` is a closed
    # union of exactly these four literals, so a fifth metric fails the typecheck, not this.
    expected_keys = {"efficiency_rpwu_per_min", "capacity_rpwu", "pct_mosaic", "pct_drafting"}
    assert len(entries) == len(expected_keys), (
        f"parsed {len(entries)} METRICS entries, expected {len(expected_keys)} - the array's "
        f"shape changed and this test is no longer reading it"
    )

    parsed: dict[str, tuple[str, bool]] = {}
    for entry in entries:
        key_m = re.search(r'key:\s*"([a-z_]+)"', entry)
        kind_m = re.search(r'kind:\s*"(rate|total)"', entry)
        assert key_m, f"no key in METRICS entry: {entry[:80]}"
        assert kind_m, f"{key_m.group(1)} declares no kind - the comparison shape is undefined"
        parsed[key_m.group(1)] = (kind_m.group(1), "normalizeBy:" in entry)

    assert set(parsed) == expected_keys, f"METRICS keys drifted: {sorted(parsed)}"

    for key, (kind, has_normalize) in parsed.items():
        spec = reg.METRICS.get(key)
        assert spec is not None, (
            f"RadMosaicScorecard renders {key}, which no longer resolves in the registry - its "
            f"hover card grounds on nothing and its comparison shape is unverifiable"
        )
        assert (kind == "rate") == spec.is_rate, (
            f"{key} is declared kind={kind!r} in RadMosaicScorecard but the registry "
            f"{'stores num/den' if spec.is_rate else 'registers it as an additive total'} "
            f"({'denominator=' + (spec.denominator or '')[:40] if spec.is_rate else 'no denominator'}). "
            f"One of the two moved."
        )
        # The invariant whose violation produced the seven-figure negative: an additive metric
        # compared raw against a practice rollup is comparing one radiologist's output to the
        # practice's entire output. `normalizeBy` is what makes the two sides commensurable, and
        # `comparison()` returns null without it - so the column renders nothing rather than
        # something wrong, which is the right failure but still a silent one.
        if not spec.is_rate:
            assert has_normalize, (
                f"{key} is additive in the registry but declares no normalizeBy - the "
                f"radiologist's own figure would be compared against the practice total"
            )


# =================================================================================================
# The cube (app/db/fact_store.py + app/services/cube_service.py)
#
# Every test below is string-level or pure-function. The cube's write side runs ONE EDW query, and
# a live dual-run against volume_service would need the 150-800s cold connection - which would end
# this file's offline-in-CI property for the sake of re-proving something the registry parity tests
# above already prove transitively: the cube lifts its SQL from the registry, and the registry is
# verbatim-identical to the deployed volume SQL, therefore the cube is identical to the deployed
# volume SQL. Checking the first link is enough, and it is free.
#
# One scope delta is legitimate and deliberate, recorded here so a future diff is not mistaken for
# a defect: the cube filters `final_datetime IS NOT NULL` and looks back 24 months
# (ADD_MONTHS(CURRENT_DATE(), -23)), while get_volume_summary() is unbounded. The cube is a monthly
# fact table - a row with no final_datetime has no month to file under, and an unbounded scan would
# rebuild all of history on every 30-minute refresh.
# =================================================================================================


def _grid_row(**overrides) -> dict:
    """One row shaped like `_grid_sql()`'s output, defaulting to the enterprise grouping set.

    GROUPING() returns 1 for a column that was aggregated away and 0 for one in the grouping set,
    so the enterprise row - the one that groups by month alone - has every flag set.
    """
    row = {
        "month_start": "2026-09-01",
        "practice": None, "team": None, "local_region": None, "npi": None, "rad_name": None,
        "g_practice": 1, "g_team": 1, "g_local_region": 1, "g_npi": 1,
    }
    for spec in cube_service._wave1_specs():
        row[f"{spec.key}__num"] = 10.0
        if spec.is_rate:
            row[f"{spec.key}__den"] = 100.0
    row.update(overrides)
    return row


def test_the_cube_measures_block_is_lifted_from_the_registry():
    grid = cube_service._grid_sql()
    deployed = volume_service._VOLUME_MEASURES_SQL
    for spec in cube_service._wave1_specs():
        for role, expr in (("numerator", spec.numerator), ("denominator", spec.denominator)):
            if not expr:
                continue
            assert expr in grid, (
                f"{spec.key}.{role} is not a verbatim substring of the cube's grid SQL. The cube "
                f"composes its measures from the registry precisely so this cannot drift; if the "
                f"expression was retyped or reformatted on the way in, the cube and the Volume "
                f"page can disagree while both claim the registry as their source.\n  registry: {expr}"
            )
            # The transitive leg. The tests at the top of this file assert registry == deployed
            # volume SQL; this one asserts registry == cube SQL. Together they are the dual-run.
            assert expr in deployed, (
                f"{spec.key}.{role} is in the cube but not in the deployed _VOLUME_MEASURES_SQL. "
                f"The cube would then be answering with a definition the Volume page does not use."
            )


def test_the_cube_covers_every_volume_metric():
    assert cube_service._WAVE1_KEYS == tuple(_VOLUME_KEYS), (
        f"the cube's wave 1 is {list(cube_service._WAVE1_KEYS)} but the registry's Volume domain "
        f"is {_VOLUME_KEYS}. A Volume metric added to the registry and not folded into the cube is "
        f"invisible to /api/mosaic/cube while appearing in /api/mosaic/registry as though it were "
        f"available - the caller gets a 404 for a metric the registry told it existed."
    )


def test_the_cube_refuses_a_non_composable_metric():
    non_composable = {k for k, m in reg.METRICS.items() if not m.composable}
    overlap = non_composable & set(cube_service._WAVE1_KEYS)
    assert not overlap, (
        f"{sorted(overlap)} are declared non-composable but sit in cube wave 1. A non-composable "
        f"metric has no num/den to store - MetricSpec.value_sql() raises for exactly that reason."
    )
    # And the read side refuses them by name rather than returning an empty result set, which the
    # UI cannot tell apart from "this slice genuinely has no data".
    victim = sorted(non_composable)[0]
    try:
        cube_service.query(metrics=[victim])
    except reg.UnsupportedDimensionError as exc:
        assert victim in str(exc), (
            f"the refusal must name the metric it refused; got {exc!r}"
        )
    else:
        raise AssertionError(
            f"cube_service.query({victim!r}) returned instead of refusing. {victim} is computed in "
            f"its own service, so the cube holds no rows for it - an empty answer here reads as "
            f"'no data for this scope' rather than 'wrong endpoint'."
        )
    # The positive control: wave 1 itself resolves, so this test fails loudly if _wave1_specs()
    # ever starts raising for everything.
    assert len(cube_service._wave1_specs()) == len(_VOLUME_KEYS)


def test_fan_out_writes_exactly_the_fact_columns():
    facts = cube_service._fan_out([_grid_row()], cube_service._wave1_specs())
    assert len(facts) == len(_VOLUME_KEYS), (
        f"one grid row should fan out to one fact row per measure; got {len(facts)} for "
        f"{len(_VOLUME_KEYS)} measures"
    )
    expected = set(fact_store._COLUMNS)
    for fact in facts:
        assert set(fact.keys()) == expected, (
            f"fan-out row for {fact.get('measure')!r} does not match fact_store._COLUMNS.\n"
            f"  missing: {sorted(expected - set(fact.keys()))}\n"
            f"  extra:   {sorted(set(fact.keys()) - expected)}\n"
            f"replace_all() executemany's over _COLUMNS in order, so a column present here and "
            f"absent there is dropped silently, and one present there and absent here raises at "
            f"write time - inside the refresh loop, which swallows the exception and logs it."
        )


def test_the_cube_never_stores_a_pre_divided_rate():
    facts = {f["measure"]: f for f in
             cube_service._fan_out([_grid_row()], cube_service._wave1_specs())}
    for key in _VOLUME_KEYS:
        spec = reg.get_metric(key)
        fact = facts[key]
        if spec.is_rate:
            assert fact["value"] is None and fact["den"] is not None, (
                f"{key} is a rate but its fact row carries value={fact['value']!r}. A stored rate "
                f"is a number a caller can SUM or AVG, and AVG(rate) across months weights a "
                f"100-exam month the same as a 100,000-exam one. Rates store num and den; the "
                f"division happens once, in cube_service._divide, after the rollup."
            )
        else:
            assert fact["den"] is None and fact["value"] == fact["num"], (
                f"{key} is an additive count but its fact row carries den={fact['den']!r} / "
                f"value={fact['value']!r}. A count's value is the count."
            )


def test_wave_one_declares_no_coverage():
    gated = [k for k in _VOLUME_KEYS if reg.get_metric(k).gated_by]
    assert not gated, (
        f"{gated} declare gated_by, but _fan_out writes coverage_num/coverage_den as None for "
        f"every wave 1 row. Capacity (wave 2) is where those columns start carrying values; "
        f"folding a gated metric into wave 1 without wiring the gate would render a coverage "
        f"badge of 'no coverage data' on a metric that has a declared threshold."
    )
    for fact in cube_service._fan_out([_grid_row()], cube_service._wave1_specs()):
        assert fact["coverage_num"] is None and fact["coverage_den"] is None
        assert fact["lifecycle_stage"] is None, (
            "lifecycle_stage belongs to Deployment (wave 3). Writing an invented stage would "
            "read as a governed go-live position in Entity 360."
        )


def test_a_rolled_up_rate_is_recomputed_not_averaged():
    # Two months with deliberately lopsided denominators. The pooled rate is 100/1000 = 10%;
    # the mean of the two monthly rates is (90% + 1.1%) / 2 = 45.6%. This 35-point gap is the
    # entire reason the cube stores num/den instead of a rate, and is Fix 3 relocated into the
    # storage schema where it cannot be forgotten by the next person to add an endpoint.
    spec = reg.get_metric("pct_mosaic")
    months = [{"num": 90.0, "den": 100.0}, {"num": 10.0, "den": 900.0}]
    rolled = {"measure": spec.key,
              "num": sum(m["num"] for m in months),
              "den": sum(m["den"] for m in months)}
    pooled = cube_service._divide(rolled, spec)["value"]
    averaged = sum(m["num"] / m["den"] for m in months) / len(months)
    assert abs(pooled - 0.10) < 1e-9, (
        f"SUM(num)/SUM(den) over {months} should be 0.10; got {pooled!r}"
    )
    assert abs(pooled - averaged) > 0.3, (
        f"the pooled rate ({pooled:.4f}) and the averaged rate ({averaged:.4f}) have converged, "
        f"which means this fixture no longer tests anything - pick denominators further apart"
    )


def test_the_rpce_offset_is_applied_once_after_the_rollup():
    spec = reg.get_metric("pct_rpce_reporting")
    assert spec.offset == 0.02, (
        f"this test is pinned to the RPCE +2pp adjustment; the registry now says {spec.offset!r}"
    )
    one_month = cube_service._divide({"measure": spec.key, "num": 50.0, "den": 100.0}, spec)
    two_months = cube_service._divide({"measure": spec.key, "num": 100.0, "den": 200.0}, spec)
    assert abs(one_month["value"] - 0.52) < 1e-9
    assert abs(two_months["value"] - 0.52) < 1e-9, (
        f"rolling two months up gave {two_months['value']!r}, not 0.52. The offset is additive "
        f"and belongs to the grain, not the row: folded into a stored numerator it would be "
        f"multiplied by the number of months summed, so a 24-month view would read +48pp."
    )


def test_a_missing_denominator_yields_no_value_not_zero():
    spec = reg.get_metric("pct_drafting")
    for row in ({"num": 0.0, "den": 0.0}, {"num": None, "den": 100.0}, {"num": 5.0, "den": None}):
        out = cube_service._divide({"measure": spec.key, **row}, spec)
        assert out["value"] is None, (
            f"_divide({row}) returned {out['value']!r}. A rate of 'no data' and a rate of 'zero "
            f"percent' are different answers and the second is the dangerous one to fabricate - "
            f"a 0% drafting rate on an empty denominator reads as a practice refusing to adopt."
        )
    # The count path has no denominator to be missing, and 0 exams really is 0.
    assert cube_service._divide(
        {"measure": "total_exams", "num": 0.0, "den": None}, reg.get_metric("total_exams")
    )["value"] == 0.0


def test_the_radiologist_grain_carries_no_parent_practice():
    cases = {
        "radiologist": _grid_row(g_npi=0, npi="1234567890", rad_name="Doe, Jane",
                                 team="Apex Radiology", g_team=0),
        "practice": _grid_row(g_practice=0, practice="Saint Example"),
        "team": _grid_row(g_team=0, team="Apex Radiology"),
        "local_region": _grid_row(g_local_region=0, local_region="Genesis"),
        "enterprise": _grid_row(),
    }
    for expected_type, row in cases.items():
        entity_type, entity_id, label, parent_practice, parent_team = cube_service._entity_of(row)
        assert entity_type == expected_type, (
            f"grouping flags {{npi:{row['g_npi']}, practice:{row['g_practice']}, "
            f"team:{row['g_team']}, region:{row['g_local_region']}}} resolved to {entity_type!r}, "
            f"expected {expected_type!r}"
        )
        assert entity_id and label, f"{expected_type} row produced a blank entity id or label"
    rad_type, _, _, rad_parent_practice, rad_parent_team = cube_service._entity_of(
        cases["radiologist"])
    assert rad_parent_practice is None, (
        f"the radiologist row carries parent_practice={rad_parent_practice!r}. A radiologist reads "
        f"at up to ~70 managing practices, so there is no single one to name - writing any value "
        f"here is the MAX(practice) AS team conflation that Phase 1 removed from "
        f"get_radiologist_scorecard, re-introduced one layer down in the storage schema."
    )
    assert rad_parent_team == "Apex Radiology", (
        "parent_team IS single-valued for a radiologist - it is their home practice "
        "(provider_local_practice_name_curr) - so it is the one parent the grain can carry."
    )
    # An unattributed group is named, not NULL: entity_id is part of the fact table's primary key,
    # so a NULL there would collapse every unattributed group into one row or be rejected outright.
    _, unknown_id, _, _, _ = cube_service._entity_of(_grid_row(g_practice=0, practice=None))
    assert unknown_id == cube_service.UNATTRIBUTED


def test_the_cube_solution_column_matches_the_registrys_tags():
    expected = {
        "total_exams": "all",
        "mosaic_exams": "reporting", "pct_mosaic": "reporting", "pct_rpce_reporting": "reporting",
        "drafting_exams": "drafting", "pct_drafting": "drafting", "pct_rpce_drafting": "drafting",
    }
    for key, want in expected.items():
        spec = reg.get_metric(key)
        got = cube_service._solution_for(spec)
        assert got == want, (
            f"{key} is filed on the cube's solution axis as {got!r}, expected {want!r} "
            f"(registry solutions={list(spec.solutions)}). The axis is read off the registry so a "
            f"metric cannot be filed under a solution its own definition does not claim; a "
            f"mismatch means the solution filter on the Explorer would hide or double-count it."
        )
        if len(spec.solutions) == 1:
            assert got == spec.solutions[0]
    assert set(expected) == set(_VOLUME_KEYS), (
        f"this test enumerates the solution axis by hand so a new metric cannot slip in "
        f"unclassified; the registry's Volume domain is now {_VOLUME_KEYS}"
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
            # Without this, the first KeyError or TypeError aborts the run mid-suite and every
            # test after it reports neither pass nor fail - it simply vanishes, while the
            # summary line still reads as though the whole suite had been considered.
            failed += 1
            print(f"  ERROR {t.__name__}\n        {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
