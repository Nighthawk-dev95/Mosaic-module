"""The governed metric registry - one declaration per Mosaic metric, no SQL scattered through
services.

Why this module exists
----------------------
Today a metric's *number* lives in a service module's f-string and its *definition* lives in a
hand-written methodology constant in `ai_context_service`, a tooltip in TSX, and a column comment
in EDW. Four copies, no mechanism keeping them equal. This module is the single place all four
read from, so the figure shown and the prose explaining it cannot drift apart.

Three invariants, each of which exists because the opposite has already gone wrong here:

1.  **Store num/den, never a pre-divided rate.** `SUM(num)/SUM(den)` re-aggregates correctly at
    any grain; `AVG(rate)` does not. This is Fix 3 from the capacity work made structural rather
    than remembered.
2.  **Team and Practice are separate, named dimensions** backed by different columns.
    `provider_local_practice_name_curr` is the radiologist's *home* practice (Team);
    `managing_local_practice_name_curr` is the *site where the exam was performed* (Practice).
    A radiologist has exactly one of the first and up to ~70 of the second. Conflating them is
    the single most-repeated defect in this codebase (`MAX(practice) AS team` in
    `get_radiologist_scorecard`, `home_practice` doing double duty in the roster). Here it is a
    schema-level impossibility, not a convention.
3.  **The parity guarantee is a test, not a comment.** `tests/test_registry_parity.py` asserts
    every expression below appears verbatim in the service module it was lifted from, and that
    the composed SELECT list is SQL-equivalent to the original. A comment claiming parity is
    exactly how three "live" bugs stayed on a stale checklist for months.

Plain frozen dataclasses, not YAML: YAML block-style lists silently corrupt inside
`CREATE VIEW ... WITH METRICS` once a list gains a second item (MIGRATION_PLAYBOOK.md, Bug 1).
That failure mode stays in the EDW serialization layer and out of the application.

Wave 1 (this file) folds in Volume. Wave 2 is Capacity + Efficiency. Wave 3 is Deployment, and
is blocked on the three additive CTAS objects that give Dynamics a practice-grain key.

MVP (the Mosaic Value Project) is folded in alongside Wave 2 rather than waiting for Wave 3,
because it is not a Deployment metric despite sharing Deployment's source table. Deployment
asks "has this radiologist been switched on"; MVP asks "has a human been sent to help this
radiologist, and did it work". The first is a date pipeline, the second is a support funnel
with its own vocabulary, its own escalation ownership, and its own outcome test. They are
folded in separately so a surface cannot quietly substitute one for the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.data.mvp_dashboard_stats import (
    _ESCALATION_OWNER_MAP,
    _IMPLAUSIBLE_PCT_MAGNITUDE,
)
from app.db.efficiency_store import _MODE_EXPRS
from app.services.mosaic_service import (
    _MIN_READ_TIME_COVERAGE,
    _RPCE_PCT_ADJUSTMENT,
    _RPCE_SOURCE_SYSTEMS_SQL,
    _gated_utilization_sql,
)
from app.services.volume_service import _LOCAL_REGION_CASE_SQL

_EXAM_INVENTORY = f"{settings.qualified}.tbl_exam_inventory"

# Bumped when the *shape* of what this module serves changes, not when a metric's prose is
# reworded. The frontend caches a snapshot per process; this is how it knows the cache is stale.
# 1.2.0: MVP folded in (10 feature keys, 14 metrics, a second CoverageSpec), and every coverage
# payload gained `direction` / `threshold_label` / `sentence`. The second half is why this is a
# minor bump rather than a patch - a cached 1.1.0 snapshot has no `sentence`, and AIHoverCard now
# renders that field instead of building the sentence itself.
REGISTRY_VERSION = "1.2.0"

# The one string every surface shows when grounded context is unavailable. It lives here rather
# than in `ai_context_service` because it crosses the Python/TypeScript boundary - it was
# hardcoded a second time in `AIHoverCard.tsx`, and a fallback that disagrees with itself is a
# small thing that looks exactly like a bug. Served on the registry route so TSX reads it.
AI_FALLBACK_TEXT = "No additional context is available for this value right now."


# --------------------------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Dimension:
    """One legal way to group a metric.

    `sql` is the SELECT expression, `group_sql` the GROUP BY expression - they differ whenever the
    select side casts for presentation (see `month`). `required_filter` travels with the dimension
    because some groupings are only well-defined over a subset of rows, and the filter has to
    follow the dimension to every query that uses it rather than being remembered per call site.
    """

    key: str
    label: str
    sql: str
    note: str
    group_sql: str | None = None
    required_filter: str | None = None

    @property
    def group_by_sql(self) -> str:
        return self.group_sql or self.sql


DIMENSIONS: dict[str, Dimension] = {
    # The two that must never be collapsed into one. Labels here are the labels the UI shows;
    # changing either is a deliberate, reviewable act rather than an incidental rename.
    "practice": Dimension(
        key="practice",
        label="Practice",
        sql="managing_local_practice_name_curr",
        note=(
            "Managing Practice - the site where the exam was performed. A radiologist reads at "
            "many of these. Matches Power BI's 'Practice' column."
        ),
    ),
    "team": Dimension(
        key="team",
        label="Team",
        sql="provider_local_practice_name_curr",
        note=(
            "Provider Practice - the radiologist's own home practice or float pool ('SEAL Team' "
            "is a cross-coverage pool, not a billing practice). Single-valued per radiologist. "
            "Matches Power BI's 'Team Rolled up' column."
        ),
    ),
    "local_region": Dimension(
        key="local_region",
        label="Local Region",
        sql=_LOCAL_REGION_CASE_SQL,
        note=(
            "One of 6 fixed regions (Special Operations / Apex / Genesis / Maverick / Trailblazer "
            "/ Matrix), keyed on Team - i.e. on where the radiologist is rostered, not where the "
            "exam was performed. Expression copied verbatim from the governed metric view."
        ),
    ),
    "month": Dimension(
        key="month",
        label="Final Month",
        sql="CAST(CAST(DATE_TRUNC('MONTH', final_datetime) AS DATE) AS STRING)",
        group_sql="DATE_TRUNC('MONTH', final_datetime)",
        # The filter is not optional tidying. Leaving the NULL bucket in let a null `period`
        # reach VolumeTrendPoint's `period: str` field as a Python None and 500 the endpoint
        # (confirmed live 2026-10-24). ~22.6M exams, present on the Lakeview dashboard's own
        # Final Month dimension too - not introduced here.
        required_filter="final_datetime IS NOT NULL",
        note=(
            "Calendar month of final sign-off. Excludes the ~22.6M exams with no final_datetime, "
            "so a monthly series does not sum to the company-wide total - query the total "
            "ungrouped instead of adding up the months."
        ),
    ),
}


# --------------------------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageSpec:
    """A declared instrumentation threshold: below `min_ratio`, named metrics are not shown.

    Coverage is a property of the *site's instrumentation*, not of the radiologist. A rad reading
    at a site that emits no dictation timestamps is indistinguishable, in the data, from one who
    produced nothing - which is why the threshold has to travel with the metric rather than being
    re-decided per surface.

    `min_ratio` is imported from `mosaic_service`, never redefined here. That module is what
    actually NULLs a value, so it is authoritative, and `registry` already imports from it - the
    dependency only runs one way (registry -> services), so defining the threshold here and
    importing it back would be a cycle.
    """

    key: str
    label: str
    min_ratio: float
    measured_by: str
    # Display labels, not metric keys - these are rendered as a sentence ("Below 75%, X is
    # suppressed and Y is still shown"), and the gate itself is declared per-metric via
    # `MetricSpec.gated_by`, which is what actually enforces it. Keeping these as prose means
    # the sentence stays readable when a threshold covers a family of columns rather than one.
    suppresses: tuple[str, ...]
    shows_anyway: tuple[str, ...]
    caveat: str
    note: str
    # Which side of the threshold is the bad side. Two genuinely different gate shapes exist and
    # they are opposites, so this cannot be left implicit:
    #
    #   "min" - a floor under an *instrumentation* ratio. Read-time coverage: below 75% of exams
    #           carrying usable dictation timestamps, the value is withheld. The number itself is
    #           fine; we just do not have enough of the population to stand behind it.
    #   "max" - a ceiling on the *magnitude of the value itself*. MVP efficiency change: a rad
    #           with a two-exam baseline can post +1724%, which is a divide-by-almost-nothing
    #           artifact rather than an efficiency gain. There is no coverage column to consult -
    #           the value's own size is the evidence it is wrong.
    #
    # Until this field existed the dataclass could only express "min", and `AIHoverCard` rendered
    # a hardcoded "Below {x}, ... is suppressed" sentence. A max-shaped gate declared as
    # `min_ratio=1.0` would have rendered "100%" correctly by coincidence and then described the
    # rule exactly backwards - the one failure mode this registry exists to make impossible.
    direction: str = "min"

    @property
    def min_pct_label(self) -> str:
        return f"{self.min_ratio * 100:.0f}%"

    @property
    def threshold_label(self) -> str:
        """The threshold with its comparator attached, so a reader never has to infer which way
        it runs: "below 75%" / "above 100%"."""
        side = "below" if self.direction == "min" else "above"
        return f"{side} {self.min_pct_label}"

    @property
    def sentence(self) -> str:
        """The whole rule as one rendered sentence.

        This lives here rather than in TSX because the sentence and the gate have to be the same
        statement. `AIHoverCard` previously built it from the parts and in doing so hardcoded the
        direction; the moment a second, opposite-facing spec was added that template became a
        lie. Composing it next to the fields it describes means adding a third gate shape breaks
        this property loudly instead of mis-describing itself quietly on a CEO surface.
        """
        verb = "is" if len(self.suppresses) == 1 else "are"
        parts = [
            f"{self.threshold_label.capitalize()}, {_list_of(self.suppresses)} {verb} "
            f'suppressed and shown as "—".'
        ]
        if self.shows_anyway:
            still = "is" if len(self.shows_anyway) == 1 else "are"
            parts.append(f"{_list_of(self.shows_anyway)} {still} still shown.")
        return " ".join(parts)


def _list_of(items: tuple[str, ...]) -> str:
    """"A", "A and B", "A, B and C". Mirrors `listOf` in AIHoverCard.tsx, which stays because the
    TSX still formats the metric lists; this one exists so `sentence` is composed server-side."""
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} and {items[-1]}"


READ_TIME_COVERAGE = CoverageSpec(
    key="read_time",
    label="Read-Time Coverage",
    min_ratio=_MIN_READ_TIME_COVERAGE,
    measured_by="pct_exams_with_valid_read_time",
    suppresses=("On-Shift Utilization",),
    # Read-Time Savings sits here rather than in `suppresses` for the same reason Efficiency
    # does, and it is worth being explicit because the instinct is the opposite: a metric whose
    # name is "read time" looks like the first thing low read-time coverage should withhold. It
    # is a ratio of the two population-matched rates, so the coverage fraction cancels - both
    # sides are computed over the same covered exams. What does not cancel is `note`'s
    # small-sample warning, which a ratio inherits twice over.
    shows_anyway=("Reading Efficiency", "Read-Time Savings", "Capacity"),
    # The canonical wording. `ai_context_service` imports this rather than defining its own copy,
    # and the route serves it so the TSX tooltip stops carrying a third paraphrase of it.
    caveat=(
        "Both Utilization and Efficiency depend on read time, which is derived from dictation "
        "timestamps - and those timestamps are missing for a large share of exams at some "
        "practices (measured 24 Oct 2026: coverage ranges from 0% to ~99%, and 20 of 84 practices "
        "sit below 75%). The two metrics are affected differently. Efficiency is repaired by "
        "matching populations: its numerator now counts TBWU only from the same exams that "
        "contributed read minutes to its denominator, so it is correct at any coverage level. "
        "Utilization cannot be repaired that way, because a scheduled shift has no 'covered "
        "subset' to match against - covered-only read minutes over full scheduled hours "
        "understates it by roughly the coverage fraction. So below 75% read-time coverage "
        "Utilization is deliberately suppressed and shows '—' rather than a number that is "
        "wrong in a knowable direction. A '—' there means withheld, not missing. Until this was "
        "added, two practices with literally zero read-time coverage displayed a perfect 100% "
        "utilization, because Spark's LEAST() skips NULL arguments and the 100% cap became the "
        "answer. The raw coverage % is rendered beside the metric so the suppression is visible."
    ),
    note=(
        "Population-matching protects Efficiency from bias, not from small-sample noise: on a "
        "thin slice it is computed from a fraction of the entity's exams and should be read as "
        "directional at best. RASF, at 0.055% coverage, produced 158.7 TBWU/min this way."
    ),
)

MVP_PLAUSIBILITY = CoverageSpec(
    key="mvp_plausibility",
    label="Efficiency-Change Plausibility",
    # Imported, never retyped - same discipline as `_MIN_READ_TIME_COVERAGE` above. The constant
    # that actually discards the value lives in `mvp_dashboard_stats`, and is hand-mirrored into
    # `mvpDashboardStats.ts` (which is the copy the UI renders). Three places, one number:
    # `test_registry_parity` asserts all three agree.
    min_ratio=_IMPLAUSIBLE_PCT_MAGNITUDE / 100.0,
    direction="max",
    # Not an instrumentation column. The value's own magnitude is the test, which is exactly why
    # `direction` had to become explicit - there is nothing else to measure coverage against.
    measured_by="abs(efficiency change %) vs a fixed plausibility ceiling",
    suppresses=("Baseline D&C Efficiency Change", "Rolling 30-Day Mosaic Change"),
    # The funnel is a count of statuses and never divides by anything, so no magnitude artifact
    # can reach it. Stated rather than left out: the two gates on this surface cover different
    # halves of it, and a reader who sees one suppressed tile should not assume the rest is gone.
    shows_anyway=("MVP Status Funnel", "Escalations by Owner", "Weekly Engagement Trend"),
    # Lifted verbatim from mvpDashboardStats.ts:105-109 and mvp_dashboard_stats.py, which is
    # where the rule is enforced. Re-wording it here would create the fourth copy this module
    # exists to prevent.
    caveat=(
        "Confirmed live (2026-10-22) that drafting_captured_efficiency_change_pct and "
        "full_mosaic_change_l30d_pct range as high as +916% / +1724% on 7-11 of 643 rows. Those "
        "are tiny-denominator blowups, not real efficiency gains: a radiologist whose baseline "
        "was built from a handful of exams divides by almost nothing. Unfiltered, a single "
        "+1724% artifact gets classified 'At/Above Baseline' and drags the impact breakdown with "
        "it. Any change whose magnitude exceeds 100% is therefore treated as insufficient_data - "
        "the same bucket as a missing value - rather than as a result. This suppresses real "
        "outliers too; that is the intended trade, because at this sample size a genuine +150% "
        "and an artifact are indistinguishable from the row alone."
    ),
    note=(
        "efficiency_change_last_30d_pct is confirmed live (2026-10-21) to be 100% NULL across "
        "the entire post-engagement population - 0 of 510 rows. full_mosaic_change_l30d_pct is "
        "the rolling figure that is actually populated (427 of 510) and serves the same 'how is "
        "this radiologist doing right now' role. A surface that reads the first column will show "
        "an empty cohort and look like a data outage rather than a wrong column choice."
    ),
)

COVERAGE: dict[str, CoverageSpec] = {
    READ_TIME_COVERAGE.key: READ_TIME_COVERAGE,
    MVP_PLAUSIBILITY.key: MVP_PLAUSIBILITY,
}


# --------------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricSpec:
    """One metric. The SQL fragments are lifted verbatim from the service module named in
    `lifted_from`; `test_registry_parity.py` enforces that they still match it."""

    key: str
    label: str
    domain: str  # deployment | utilization | efficiency | capacity | mvp
    solutions: tuple[str, ...]
    source: str
    numerator: str
    definition: str
    lifted_from: str
    denominator: str | None = None  # None => a count, not a rate
    # A constant added to the ratio *after* the division. Declared rather than folded into the
    # numerator because an additive offset only re-aggregates correctly when applied once per
    # grain, after dividing - fold it in and a company-wide rollup picks the offset up N times.
    offset: float = 0.0
    # Redundant in Spark, which already returns DOUBLE from `/`. Retained because the deployed
    # metric view carries it and this registry's job is to reproduce that string, not to tidy it.
    numerator_scale: str = ""
    allowed_dims: tuple[str, ...] = ()
    grain: str = "exam"
    caveats: tuple[str, ...] = ()
    trust: str = "governed"  # governed = reconciled to a deployed metric view; app = ours alone
    owner: str = "Mosaic Clinical Transformation"
    version: str = "1.0.0"
    # The output column name, when it cannot be the key. Two domains legitimately ship a column
    # called `pct_mosaic` over *different denominators* - Volume's is Mosaic exams over all
    # exams, Capacity's is Mosaic cases over on-shift cases - and a registry keyed by column
    # name would silently serve one where the other was meant. So the key is globally unique and
    # the column is whatever the deployed SQL already emits. The two must stay separable: this
    # exact conflation (exam-count adoption read as time utilization) has already shipped once.
    column: str = ""
    # Coverage gate. When set, `value_sql()` delegates to the gate builder in `mosaic_service`
    # rather than emitting a bare ratio, so the suppression and the registry cannot disagree -
    # the gate is built by the same function that every deployed utilization already goes
    # through. `gate_numerator / gate_denominator` are the coverage ratio, not the metric's.
    gated_by: str = ""  # a COVERAGE key
    gate_numerator: str = ""
    gate_denominator: str = ""
    # False for metrics whose value is computed outside Spark - the Efficiency pair is derived
    # in `efficiency_store` over SQLite, including a /60 on one side and not the other. A
    # composer that emitted plausible SQL for those would be a second implementation of a
    # calculation whose subtlety is the whole point, so it refuses instead.
    composable: bool = True

    @property
    def output_name(self) -> str:
        return self.column or self.key

    @property
    def is_rate(self) -> bool:
        return self.denominator is not None

    def value_sql(self) -> str:
        """The SELECT expression for this metric at whatever grain the caller groups by."""
        if not self.composable:
            raise ValueError(
                f"{self.key!r} is computed in {self.lifted_from}, not composed here - "
                f"read its numerator/denominator as documentation, not as SQL"
            )
        if self.gated_by:
            return _gated_utilization_sql(
                self.numerator, self.denominator, self.gate_numerator, self.gate_denominator
            )
        if self.denominator is None:
            return self.numerator
        ratio = f"{self.numerator}{self.numerator_scale} / NULLIF({self.denominator}, 0)"
        if self.offset:
            return f"({ratio}) + {self.offset}"
        return ratio


# The exam-level flag pairs, written once. Everything in the Volume domain is one of these two
# numerators over one of two denominators.
_MOSAIC_READ = "SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END)"
_MOSAIC_DRAFT = "SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END)"
_ALL_EXAMS = "COUNT(*)"
_RPCE_EXAMS = f"SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END)"

_VOLUME_DIMS = ("practice", "team", "local_region", "month")
_VOLUME_SRC = "backend/app/services/volume_service.py:_VOLUME_MEASURES_SQL"

# The % RPCE pair divides by RPCE-sourced exams rather than all exams, so it is not a share of
# anything the other measures are a share of, and it can exceed 100%. Stated here once so the
# tooltip, the AI explanation and the registry all say the same thing.
_RPCE_CAVEATS = (
    "Denominator is RPCE-sourced exams only, not all exams - this is adoption within the RPCE "
    "footprint, not enterprise adoption, and the two are not comparable.",
    f"Carries a flat +{_RPCE_PCT_ADJUSTMENT * 100:.0f}pp adjustment present in the source DAX "
    "model; confirmed with the business owner as intentional, not a leftover.",
    "Can exceed 100% where Mosaic reads exist outside the RPCE source systems.",
)

_NEVER_AVERAGE = "Never average across groups - recompute from numerator/denominator."

VOLUME_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="total_exams",
        label="Exam Count",
        domain="utilization",
        solutions=("reporting", "drafting", "capture"),
        source=_EXAM_INVENTORY,
        numerator=_ALL_EXAMS,
        definition="All exams in the inventory, Mosaic and legacy alike.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
    ),
    MetricSpec(
        key="mosaic_exams",
        label="Mosaic Exam Count",
        domain="utilization",
        solutions=("reporting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_READ,
        definition="Exams read on Mosaic rather than the legacy voice recognition system.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
    ),
    MetricSpec(
        key="pct_mosaic",
        label="% Mosaic",
        domain="utilization",
        solutions=("reporting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_READ,
        denominator=_ALL_EXAMS,
        definition=(
            "Share of exams read on Mosaic. This is adoption measured by exam count - it is NOT "
            "time-based utilization, which is a separate metric with a different denominator."
        ),
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
        caveats=(_NEVER_AVERAGE,),
    ),
    MetricSpec(
        key="drafting_exams",
        label="Drafting Exam Count",
        domain="utilization",
        solutions=("drafting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_DRAFT,
        definition="Exams where an AI draft was produced for the radiologist.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
    ),
    MetricSpec(
        key="pct_drafting",
        label="% Drafting",
        domain="utilization",
        solutions=("drafting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_DRAFT,
        denominator=_ALL_EXAMS,
        definition="Share of all exams that received an AI draft.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
        caveats=(_NEVER_AVERAGE,),
    ),
    MetricSpec(
        key="pct_rpce_reporting",
        label="% RPCE Reporting",
        domain="utilization",
        solutions=("reporting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_READ,
        denominator=_RPCE_EXAMS,
        offset=_RPCE_PCT_ADJUSTMENT,
        numerator_scale=" * 1.0",
        definition="Mosaic reads as a share of exams originating in the RPCE source systems.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
        caveats=(_NEVER_AVERAGE,) + _RPCE_CAVEATS,
    ),
    MetricSpec(
        key="pct_rpce_drafting",
        label="% RPCE Drafting",
        domain="utilization",
        solutions=("drafting",),
        source=_EXAM_INVENTORY,
        numerator=_MOSAIC_DRAFT,
        denominator=_RPCE_EXAMS,
        offset=_RPCE_PCT_ADJUSTMENT,
        numerator_scale=" * 1.0",
        definition="AI drafts as a share of exams originating in the RPCE source systems.",
        lifted_from=_VOLUME_SRC,
        allowed_dims=_VOLUME_DIMS,
        caveats=(_NEVER_AVERAGE,) + _RPCE_CAVEATS,
    ),
)

# --------------------------------------------------------------------------------------------
# Wave 2a - Capacity
# --------------------------------------------------------------------------------------------
#
# Lifted from `_CAPACITY_MEASURES_SQL`, in its order, including the columns that are honest
# placeholders. Those matter more than they look: `baseline_rvu`, `baseline_rpwu` and
# `baseline_rvu_per_hour` are `CAST(NULL AS DOUBLE)` and `adjustment_rvu` / `adjustment_tbwu`
# are `CAST(0 AS DOUBLE)`, and until now a reader of the payload had no way to tell a measured
# zero from an unreachable source. Declaring them with `trust="unavailable"` turns five silent
# NULLs into five stated gaps - the registry's job is to describe the deployed SQL truthfully,
# not to describe the SQL we wish were deployed.
#
# The grain is the *shift*, not the exam, which is why none of these carry `allowed_dims`. The
# capacity CTE aliases its two entity columns `team` and `localpractice`; those are not the
# `DIMENSIONS` expressions (`provider_local_practice_name_curr` /
# `managing_local_practice_name_curr`), so declaring the dimensions here would compose SQL that
# does not run. Wave 2 states the grain honestly and leaves the unification to the cube.

_CAPACITY_SRC = "backend/app/services/mosaic_service.py:_CAPACITY_MEASURES_SQL"
_SHIFT_CASES = "SUM(shift_cases)"
_COVERED_EXAMS = "SUM(exams_with_valid_read_time)"
_UNAVAILABLE = "CAST(NULL AS DOUBLE)"

# Both utilization columns and both efficiency columns are the *same expression twice*. The
# RVU/RPWU split is a survival from the old Power BI model, which carried two genuinely
# different work units; `tbl_exam_inventory` exposes one TBWU-based numerator, so the pair
# collapsed. Writing the fragment once here makes that identity structural rather than a
# coincidence two editors could break independently.
_EFFICIENCY_PER_MIN_NUM = "SUM(shift_TBWU_with_read_time)"
_READ_MINUTES = "SUM(shift_read_minutes)"

_RVU_RPWU_IDENTICAL = (
    "The RVU and RPWU variants are the same expression - tbl_exam_inventory exposes one "
    "TBWU-based work unit, not two. Do not read a difference between them as signal."
)
_SHIFT_GRAIN_CAVEAT = (
    "Shift-grain: counts only exams read while on a matched scheduled shift. ~25% of exams "
    "match no shift, so these denominators are smaller than the exam-inventory totals."
)


def _capacity(key: str, label: str, numerator: str, definition: str, **kw) -> MetricSpec:
    """Capacity specs share nine fields; only the four that vary are worth reading at each site."""
    return MetricSpec(
        key=key,
        label=label,
        domain="capacity",
        solutions=("reporting", "drafting", "capture"),
        source=_EXAM_INVENTORY,
        numerator=numerator,
        definition=definition,
        lifted_from=_CAPACITY_SRC,
        grain="shift",
        **kw,
    )


CAPACITY_METRICS: tuple[MetricSpec, ...] = (
    _capacity(
        "total_shifts", "Shift Count", "COUNT(1)",
        "Scheduled shifts in scope, after exam-to-shift matching.",
        caveats=(_SHIFT_GRAIN_CAVEAT,),
    ),
    _capacity(
        "total_hours", "Scheduled Hours", "SUM(no_hours)",
        "Total scheduled shift duration in hours - the denominator of Utilization.",
    ),
    _capacity(
        "capacity_rvu", "Capacity (RVU)", "SUM(shift_RVU)",
        "Work units produced on shift, under the RVU label.",
        caveats=(_RVU_RPWU_IDENTICAL,),
    ),
    _capacity(
        "capacity_rpwu", "Capacity (RPWU)", "SUM(shift_TBWU)",
        "TBWU produced on shift. This is the capacity figure the scorecard shows.",
        caveats=(_RVU_RPWU_IDENTICAL, _SHIFT_GRAIN_CAVEAT),
    ),
    _capacity(
        "baseline_rvu", "Baseline (RVU)", _UNAVAILABLE,
        "Not computed in this query. The real baseline is derived per procedure in "
        "get_capacity_with_baseline; this column is a typed NULL so the row shape matches.",
        trust="unavailable",
    ),
    _capacity(
        "baseline_rpwu", "Baseline (RPWU)", _UNAVAILABLE,
        "Not computed in this query - see baseline_rvu.",
        trust="unavailable",
    ),
    # The two gated columns. `gated_by` makes the suppression a declared property rather than
    # something a reader has to infer from a CASE expression, and `value_sql()` rebuilds it by
    # calling the very function the deployed SQL calls - so a change to the gate cannot leave
    # the registry describing the old one.
    _capacity(
        "utilization_rvu_pct", "On-Shift Utilization (RVU)", _READ_MINUTES,
        "Share of scheduled shift time spent actively reading, capped at 100%.",
        denominator="SUM(no_hours)",
        gated_by=READ_TIME_COVERAGE.key,
        gate_numerator=_COVERED_EXAMS,
        gate_denominator=_SHIFT_CASES,
        trust="app",
        caveats=(_RVU_RPWU_IDENTICAL, _NEVER_AVERAGE),
    ),
    _capacity(
        "utilization_rpwu_pct", "On-Shift Utilization", _READ_MINUTES,
        "Share of scheduled shift time spent actively reading, capped at 100%. Suppressed "
        "below the read-time coverage threshold rather than shown wrong.",
        denominator="SUM(no_hours)",
        gated_by=READ_TIME_COVERAGE.key,
        gate_numerator=_COVERED_EXAMS,
        gate_denominator=_SHIFT_CASES,
        trust="app",
        caveats=(_RVU_RPWU_IDENTICAL, _NEVER_AVERAGE),
    ),
    _capacity(
        "efficiency_rvu_per_min", "Reading Efficiency (RVU)", _EFFICIENCY_PER_MIN_NUM,
        "TBWU per minute of read time, over the coverage-matched population.",
        denominator=_READ_MINUTES,
        trust="app",
        caveats=(_RVU_RPWU_IDENTICAL, _NEVER_AVERAGE),
    ),
    _capacity(
        "efficiency_rpwu_per_min", "Reading Efficiency", _EFFICIENCY_PER_MIN_NUM,
        "TBWU per minute of read time. The numerator counts TBWU only from exams that also "
        "contributed read minutes to the denominator, so the two populations match and the "
        "rate is unbiased at any coverage level - but on a thin slice it is still noisy.",
        denominator=_READ_MINUTES,
        trust="app",
        caveats=(_RVU_RPWU_IDENTICAL, _NEVER_AVERAGE, READ_TIME_COVERAGE.note),
    ),
    _capacity(
        "capacity_rvu_per_hour", "Capacity per Hour", "SUM(shift_RVU)",
        "Work units produced per scheduled hour - the figure compared against baseline.",
        denominator="SUM(no_hours)",
        caveats=(_NEVER_AVERAGE,),
    ),
    _capacity(
        "baseline_rvu_per_hour", "Baseline per Hour", _UNAVAILABLE,
        "Not computed in this query - see baseline_rvu.",
        trust="unavailable",
    ),
    _capacity(
        "on_shift_cases", "On-Shift Exams", _SHIFT_CASES,
        "Exams read while on a matched scheduled shift.",
        caveats=(_SHIFT_GRAIN_CAVEAT,),
    ),
    _capacity(
        "mosaic_cases", "Mosaic Exams (On Shift)", "SUM(mosaic_cases)",
        "On-shift exams read on Mosaic rather than legacy voice recognition.",
    ),
    _capacity(
        "drafting_cases", "Drafted Exams (On Shift)", "SUM(drafting_cases)",
        "On-shift exams where an AI draft was produced.",
    ),
    # The key collision this registry exists to prevent. Volume already owns `pct_mosaic` over
    # *all exams*; this one divides by on-shift cases, so the two differ by the shift-match rate
    # (~75%) and answer different questions. Keyed apart, columned the same - and
    # `_validate_registry` refuses a duplicate key outright, so a future fold-in cannot
    # reintroduce the silent overwrite by picking the obvious name.
    _capacity(
        "capacity_pct_mosaic", "% Mosaic (On Shift)", "SUM(mosaic_cases)",
        "Share of on-shift exams read on Mosaic. Distinct from the enterprise % Mosaic, which "
        "divides by all exams including those that matched no shift.",
        denominator=_SHIFT_CASES,
        column="pct_mosaic",
        caveats=(_NEVER_AVERAGE, _SHIFT_GRAIN_CAVEAT),
    ),
    _capacity(
        "capacity_pct_drafting", "% Drafting (On Shift)", "SUM(drafting_cases)",
        "Share of on-shift exams that received an AI draft. Distinct from the enterprise "
        "% Drafting, which divides by all exams.",
        denominator=_SHIFT_CASES,
        column="pct_drafting",
        caveats=(_NEVER_AVERAGE, _SHIFT_GRAIN_CAVEAT),
    ),
    _capacity(
        "avg_rvu_per_case", "Avg Work Units per Exam", "SUM(shift_RVU)",
        "Average work units per on-shift exam - the case-mix term that separates 'reading more' "
        "from 'reading heavier'.",
        denominator=_SHIFT_CASES,
        caveats=(_NEVER_AVERAGE,),
    ),
    _capacity("ct_cases", "CT Exams", "SUM(ct_cases)", "On-shift CT exams."),
    _capacity("xr_cases", "XR Exams", "SUM(xr_cases)", "On-shift X-ray exams."),
    _capacity("us_cases", "US Exams", "SUM(us_cases)", "On-shift ultrasound exams."),
    _capacity("mr_cases", "MR Exams", "SUM(mr_cases)", "On-shift MR exams."),
    _capacity("ir_cases", "IR Exams", "SUM(ir_cases)", "On-shift interventional exams."),
    _capacity(
        "adjustment_rvu", "Shift Credit Adjustment (RVU)", "CAST(0 AS DOUBLE)",
        "Always 0. The QGenda shift-credit-adjustment source is not reachable under this "
        "application's grants, so this is an unavailable value, not a measured zero.",
        trust="unavailable",
    ),
    _capacity(
        "adjustment_tbwu", "Shift Credit Adjustment (TBWU)", "CAST(0 AS DOUBLE)",
        "Always 0 - see adjustment_rvu.",
        trust="unavailable",
    ),
    # The coverage measure itself. It is a metric like any other, and registering it is what
    # lets the badge's feature resolve to a definition instead of to coverage prose alone.
    _capacity(
        "pct_exams_with_valid_read_time", "Read-Time Coverage", _COVERED_EXAMS,
        "Share of on-shift exams carrying a usable dictation timestamp. This is an "
        "instrumentation property of the site, not a property of the radiologist: a rad reading "
        "at a site that emits no timestamps is indistinguishable from one who produced nothing.",
        denominator=_SHIFT_CASES,
        trust="app",
        caveats=(_NEVER_AVERAGE,),
    ),
    _capacity(
        "pct_shifts_rpce_source", "% RPCE-Sourced Shifts",
        "SUM(CASE WHEN is_rpce_source = 1 THEN shift_cases ELSE 0 END)",
        "Share of on-shift exams originating in an RPCE source system. Related to read-time "
        "coverage but not the same thing - coverage varies widely within the RPCE footprint.",
        denominator=_SHIFT_CASES,
        trust="app",
        caveats=(_NEVER_AVERAGE,),
    ),
)


# --------------------------------------------------------------------------------------------
# Wave 2b - Efficiency, and the solution axis
# --------------------------------------------------------------------------------------------
#
# Reporting / Drafting / Capture are the three *solutions* Mosaic ships - the dimension that,
# crossed with the metrics above, makes this a product model rather than a metric list. They
# have lived until now as a bare dict of column triples inside `efficiency_store`, unnamed and
# undescribed. Naming them here is what lets a surface ask "how is Drafting doing" as a
# first-class question.
#
# The column triples are held *by reference*, not retyped: `exprs=_MODE_EXPRS["reporting"]` is
# the same tuple object the SQLite aggregation uses, so the parity test asserts identity (`is`)
# rather than equality. The same discipline as `_LOCAL_REGION_CASE_SQL`.


@dataclass(frozen=True)
class SolutionMode:
    key: str
    label: str
    description: str
    exprs: tuple[str, str, str]  # (tbwu, time, baseline-contribution) columns in efficiency_matrix


EFFICIENCY_MODES: dict[str, SolutionMode] = {
    "reporting": SolutionMode(
        key="reporting",
        label="Reporting",
        description=(
            "Dictation on Mosaic instead of the legacy voice recognition system. The base "
            "solution - a radiologist is on Reporting before Drafting or Capture can apply."
        ),
        exprs=_MODE_EXPRS["reporting"],
    ),
    "drafting": SolutionMode(
        key="drafting",
        label="AI Drafting",
        description=(
            "An AI-generated draft report is presented for the radiologist to edit and sign "
            "rather than dictate from scratch. Requires enrollment plus a covered procedure."
        ),
        exprs=_MODE_EXPRS["drafting"],
    ),
    "capture": SolutionMode(
        key="capture",
        label="Capture",
        description=(
            "Structured measurement capture at acquisition, feeding the report. Ultrasound and "
            "DEXA today - a different workflow from Drafting, not a subset of it."
        ),
        exprs=_MODE_EXPRS["capture"],
    ),
    "full_mosaic": SolutionMode(
        key="full_mosaic",
        label="All Mosaic",
        description=(
            "Reporting + Drafting combined, matching the source ETL's Is_Mosaic_Row "
            "(= Is_Reporting_Row OR Is_Drafting_Row). Capture is deliberately NOT included, "
            "because the upstream flag does not include it - this mirrors the ETL rather than "
            "improving on it, so the app and the warehouse agree on what 'Mosaic' counts."
        ),
        exprs=_MODE_EXPRS["full_mosaic"],
    ),
}

_EFFICIENCY_SRC = "backend/app/db/efficiency_store.py:_rate / _baseline_rate"

# The asymmetry that makes these two non-composable, recorded where someone will read it.
# `_rate` divides seconds by 60 to reach TBWU-per-minute. `_baseline_rate` does not, because
# `baseline_contrib` is already a per-minute value pre-multiplied by TotalTime-in-seconds as a
# weight, so dividing by SUM(TotalTime) directly yields the time-weighted average. Emitting
# "equivalent" SQL for this pair would be a second implementation of exactly the step that is
# easy to get wrong, which is why `composable=False` refuses instead of guessing.
_EFFICIENCY_ASYMMETRY = (
    "Mosaic and baseline rates are NOT computed the same way. The Mosaic rate divides TBWU by "
    "time/60; the baseline divides a pre-weighted contribution by raw seconds, because that "
    "column already carries the per-minute value multiplied by its own duration as a weight. "
    "Applying either formula to the other column is wrong by a factor of 60."
)
_POPULATION_MATCHED = (
    "Population-matched against the baseline: both sides are computed over the same exam mix, "
    "so a difference between them is a change in reading speed, not a change in case mix."
)

EFFICIENCY_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="mosaic_tbwu_per_min",
        label="Mosaic Efficiency",
        domain="efficiency",
        solutions=("reporting", "drafting", "capture"),
        source="efficiency_matrix (SQLite cube, refreshed from EDW)",
        numerator="SUM(<mode>_tbwu)",
        denominator="SUM(<mode>_time) / 60.0",
        definition=(
            "TBWU produced per minute of read time on Mosaic, for the selected solution. "
            "Computed per solution mode - Reporting, AI Drafting, Capture, or all Mosaic."
        ),
        lifted_from=_EFFICIENCY_SRC,
        grain="exam",
        trust="app",
        composable=False,
        caveats=(_NEVER_AVERAGE, _POPULATION_MATCHED, _EFFICIENCY_ASYMMETRY),
    ),
    MetricSpec(
        key="baseline_tbwu_per_min",
        label="Baseline Efficiency",
        domain="efficiency",
        solutions=("reporting", "drafting", "capture"),
        source="efficiency_matrix (SQLite cube, refreshed from EDW)",
        numerator="SUM(<mode>_baseline_contrib)",
        denominator="SUM(<mode>_time)",
        definition=(
            "The same radiologist's pre-Mosaic reading rate on the same mix of exams - the "
            "comparator the Mosaic rate is measured against, not an enterprise average."
        ),
        lifted_from=_EFFICIENCY_SRC,
        grain="exam",
        trust="app",
        composable=False,
        caveats=(_NEVER_AVERAGE, _POPULATION_MATCHED, _EFFICIENCY_ASYMMETRY),
    ),
    MetricSpec(
        key="read_time_change_pct",
        label="Read-Time Savings",
        domain="efficiency",
        solutions=("reporting", "drafting", "capture"),
        source="derived from the two efficiency rates above",
        # Documentation, not SQL (composable=False). The shape is real, though: a ratio of the
        # two rates with a -1 offset, which is why `offset` carries it rather than the numerator -
        # an additive offset folded into a numerator is picked up once per group and so is wrong
        # at every rollup above the grain it was written for.
        numerator="baseline_tbwu_per_min",
        denominator="mosaic_tbwu_per_min",
        offset=-1.0,
        definition=(
            "The change in time needed to produce the same unit of work, versus the legacy "
            "voice recognition system. Negative is the good direction: -0.12 means the same "
            "work now takes 12% less reading time. Derived from the efficiency ratio "
            "(baseline rate / Mosaic rate) - 1, over a population-matched exam mix."
        ),
        lifted_from="backend/app/services/cache_service.py:_read_time_change",
        grain="exam",
        trust="app",
        composable=False,
        caveats=(
            # The single most likely misread on the surface, so it leads.
            "Sign convention: NEGATIVE means less time needed (a saving). A positive value "
            "means the same work is taking longer than it did before Mosaic.",
            # The honesty caveat. It is the reason this is labelled "Implied" in Power BI.
            "Implied, not measured. This is inferred from the efficiency ratio, not from a "
            "separate observation of reading time - it inherits every limitation of the two "
            "rates it divides, including their read-time instrumentation coverage.",
            "Matches Power BI's Parameter[Implied_RTS_Opt]; the two should never disagree.",
            "Undefined when the Mosaic rate is zero - reported as no value rather than as 0%.",
            _NEVER_AVERAGE,
            _POPULATION_MATCHED,
        ),
    ),
)

# --------------------------------------------------------------------------------------------
# MVP - the Mosaic Value Project
# --------------------------------------------------------------------------------------------
#
# The most-tracked surface in the product and, until this block, the least governed: six tabs
# calling ten distinct `AIHoverCard` feature keys, none of which resolved to a definition. Every
# one of those cards rendered AI commentary with no governed statement of what the number was.
#
# MVP is a *support funnel*, not a deployment pipeline. A radiologist enters because their
# efficiency on Mosaic is below where it should be, a human is assigned to work with them, and
# the program tracks whether that intervention moved the number. So the metrics here are counts
# of people at stages and changes in a rate - never exam counts, and never composed as SQL.
#
# All of them are `composable=False` and `trust="app"`. The values are computed in Python over
# cached Dynamics rows (`mvp_dashboard_stats.py`) and, separately, in TypeScript over the same
# rows (`mvpDashboardStats.ts`, which is the copy the UI actually renders). Their numerator and
# denominator fields are documentation of the classification rule, not SQL a composer may emit.
#
# `allowed_dims` is empty on every entry, deliberately. These rows come from Dynamics, where
# Practice is free text with no MDM key - the only reliable join to the exam world is NPI. A
# Local Region or Practice group-by would have to approximate that join, and `validate_scope`
# refusing outright is the rule this registry already pre-committed to for Deployment. The same
# reasoning applies here one wave early.

_MVP_SRC = "backend/app/data/mvp_dashboard_stats.py"
_MVP_UI_SRC = "frontend/src/utils/mvpDashboardStats.ts"

# Shared caveats. Each is stated once and referenced, so a correction lands everywhere at once.

_MVP_HAND_SYNC = (
    f"Computed twice from the same rows, in two runtimes with no shared code: {_MVP_SRC} "
    f"grounds the AI narrative and {_MVP_UI_SRC} renders the screen. "
    "test_registry_parity.py asserts the shared definitions still agree."
)

# The one exception to _MVP_HAND_SYNC. Priority tiering is the only MVP number not computed by
# the mvp_dashboard_stats pair - it has its own two implementations, in different files, in
# different layers. Pointing a reader at the stats pair would send them somewhere the formula
# does not appear, which is worse than saying nothing: they would conclude it is not duplicated.
_MVP_PRIORITY_HAND_SYNC = (
    "Computed twice from the same rows, in two runtimes with no shared code: "
    "backend/app/services/ai_context_service.py::_priority_tier_counts grounds the AI narrative "
    "and frontend/src/pages/mvp/MvpAllRadiologists.tsx::computePriorities renders the badge. "
    "test_registry_parity.py asserts the four thresholds and the cutoff still agree."
)

_MVP_BUCKETING_ASYMMETRY = (
    "The funnel's three buckets are not symmetric across stages, and the asymmetry is "
    "deliberate rather than a bug: the four open stages split on whether the status string "
    "contains 'Escalated' and can never increment 'declined', while Closed splits on the "
    "outcome keywords (Declined Support, Resigning, Mentor Declined, Not Progressing) and can "
    "never increment 'escalated'. An escalation is a state you are currently in; a decline is "
    "how you left. Summing 'escalated' across all five stages therefore counts live "
    "escalations only, and will not match a count of radiologists who were ever escalated."
)

_MVP_PRE_FUNNEL_EXCLUDED = (
    "Statuses '1 Identified' and '2 Confirmed' are pre-funnel and excluded from every stage "
    "count. They are tracked separately as 'not yet engaged' in the weekly trend. This is what "
    "makes the funnel total reconcile to the weekly deck (n=368 for the 10/16 snapshot)."
)

_MVP_THREE_CENSUSES = (
    "Three MVP population numbers circulate and they deliberately do not reconcile: ~409 "
    "actively tracked in EDW, 368 in the weekly deck funnel, and 400/370/259 in the staffing "
    "model. They count different things (tracked, engaged, and planned-for), so a surface that "
    "makes two of them agree has silently redefined one of them."
)

_MVP_BASELINE_WINDOW = (
    "Baseline is the May-Jul 2026 window, before the radiologist's MVP engagement began. It is "
    "the same radiologist's own prior rate, not a peer or enterprise average."
)

_MVP_IMPLAUSIBLE = (
    "Any change whose magnitude exceeds 100% is discarded as a tiny-denominator artifact and "
    "bucketed as insufficient_data, identical to a missing value. See the "
    "Efficiency-Change Plausibility threshold."
)

_MVP_APPROXIMATED_DATES = (
    "Approximated from optimization_last_updated ('last touched'), not from a true "
    "stage-transition log - see "
    "016_add_optimization_last_updated_to_mvp_rad_onboarding.sql for full provenance. A "
    "radiologist whose record was edited for an unrelated reason moves weeks. Must always be "
    "captioned as an approximation wherever it is rendered."
)

MVP_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="mvp_funnel_rads",
        label="MVP Status Funnel",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.mosaic_optimization_support_status (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) WHERE _stage_bucket(status) = <stage>",
        definition=(
            "Radiologists at each of the five MVP support stages - Outreached, Scheduled, "
            "Solutioning, Monitoring, Closed - split within each stage into on-track, escalated "
            "and declined. The funnel total is the sum of all five stages and is the number the "
            "weekly deck reports."
        ),
        lifted_from=f"{_MVP_SRC}:compute_status_funnel",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            _MVP_PRE_FUNNEL_EXCLUDED,
            _MVP_BUCKETING_ASYMMETRY,
            _MVP_THREE_CENSUSES,
            _MVP_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_escalations_by_owner",
        label="Escalations by Owner",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.mosaic_optimization_support_status (Dynamics CRM)",
        numerator=(
            "COUNT(DISTINCT npi) WHERE status LIKE '7 Solutioning (Escalated - %)', "
            "grouped by the parsed suffix"
        ),
        definition=(
            "Open escalations grouped by the team that owns resolving them: Mentorship, IT, or "
            "Development. The owner is parsed from the status string's own suffix, so it is the "
            "CRM's routing decision rather than an inference about the problem."
        ),
        lifted_from=f"{_MVP_SRC}:compute_escalations_by_owner",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            # The mapping is one-way and renames one of its three values, which is exactly the
            # kind of thing a reader will otherwise assume is a typo.
            "'Program Specific' in the CRM is reported as 'Development' - the status vocabulary "
            "and the owning team use different words for the same queue. The other two map to "
            "themselves.",
            "Only stage-7 strings are parsed. An escalation recorded at stage 4 ('Outreached "
            "(Escalated)') carries no owner suffix, so it counts in the funnel's escalated "
            "bucket but has no owner to attribute - it is not silently assigned to one.",
            _MVP_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_post_engagement_rads",
        label="Post-Engagement Radiologists",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) WHERE stage IN (Solutioning, Monitoring, Closed)",
        definition=(
            "Radiologists far enough through the funnel that an intervention has actually "
            "happened and a post-engagement efficiency figure can be read. Outreached and "
            "Scheduled are excluded: nothing has been done yet, so measuring them would dilute "
            "the impact rate with people the program has not treated."
        ),
        lifted_from=f"{_MVP_SRC}:compute_impact_breakdown",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(_MVP_THREE_CENSUSES, _MVP_HAND_SYNC),
    ),
    MetricSpec(
        key="mvp_impact_breakdown_rads",
        label="Impact on MVP Radiologists",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) per impact bucket",
        denominator="COUNT(DISTINCT npi) WHERE stage IN (Solutioning, Monitoring, Closed)",
        definition=(
            "Post-engagement radiologists split four ways: at-or-above baseline (post >= 0), "
            "improving (post > baseline but still below 0), not improving, and insufficient "
            "data. The first two are the program's success measures and they are different "
            "questions - 'are they whole again' versus 'are they moving the right way'."
        ),
        lifted_from=f"{_MVP_SRC}:compute_impact_breakdown",
        grain="radiologist",
        trust="app",
        composable=False,
        gated_by="",  # enforced in Python, not composed - see MVP_PLAUSIBILITY
        caveats=(
            "At-or-above baseline and improving are evaluated in that order and are mutually "
            "exclusive. A radiologist who is back above baseline is not also counted as "
            "improving, so the four buckets sum to the post-engagement population exactly once.",
            _MVP_IMPLAUSIBLE,
            "A missing baseline or a missing post value lands in insufficient_data rather than "
            "in not-improving. Absence of evidence is not counted as evidence of failure.",
            _MVP_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_dc_efficiency_change_pct",
        label="Baseline D&C Efficiency Change",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.drafting_captured_efficiency_change_pct",
        numerator="drafting_captured_efficiency_change_pct",
        definition=(
            "The radiologist's combined Drafting-and-Capture reading efficiency versus their own "
            "May-Jul 2026 baseline, as a percentage change. Negative means slower than before "
            "Mosaic - which is why the radiologist is in MVP at all."
        ),
        lifted_from=_MVP_SRC,
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "Sign convention is the opposite of Read-Time Savings: here NEGATIVE is the problem "
            "(reading more slowly), because this is a change in efficiency, not in time. The two "
            "appear on adjacent surfaces and are read in opposite directions.",
            _MVP_BASELINE_WINDOW,
            "Program-wide, the figures this is measured against are ~20% reduced efficiency on "
            "Drafted exams and ~37% on Captured exams versus the legacy voice recognition "
            "system.",
            _MVP_IMPLAUSIBLE,
            _MVP_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_rolling_30d_change_pct",
        label="Rolling 30-Day Mosaic Change",
        domain="mvp",
        solutions=("reporting", "drafting", "capture"),
        source="rad_onboarding.full_mosaic_change_l30d_pct",
        numerator="full_mosaic_change_l30d_pct",
        definition=(
            "Full-Mosaic efficiency change over the trailing 30 days, against the same May-Jul "
            "2026 baseline. This is the 'how is this radiologist doing right now' figure, as "
            "distinct from the cumulative since-baseline change beside it."
        ),
        lifted_from=_MVP_SRC,
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            # The single most expensive column-choice mistake available on this surface.
            "Read full_mosaic_change_l30d_pct, never efficiency_change_last_30d_pct. The latter "
            "is confirmed 100% NULL across the entire post-engagement population (0 of 510 rows, "
            "2026-10-21); the former is populated for 427 of 510. A surface reading the wrong "
            "one renders an empty cohort that looks like a data outage.",
            "A rolling window is noisier than the cumulative figure by construction - a "
            "radiologist with a light 30 days moves sharply on this and not at all on the other.",
            _MVP_IMPLAUSIBLE,
            _MVP_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_program_efficiency_change_pct",
        label="Per-Program Efficiency Change",
        domain="mvp",
        solutions=("drafting", "capture"),
        source=(
            "rad_onboarding.xr_drafting_efficiency_change_pct / "
            "ct_head_efficiency_change_pct / us_capture_efficiency_change_pct"
        ),
        numerator="<program>_efficiency_change_pct",
        definition=(
            "Efficiency change against the May-Jul 2026 baseline for one specific exam-prep "
            "program - XR Drafting, CT Head Drafting, or US Capture - rather than for the "
            "radiologist's whole Mosaic workload."
        ),
        lifted_from=f"{_MVP_UI_SRC}:getEffLossPrograms",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            # This is the entire reason Priority 3 exists as a tier, so it belongs on the metric.
            "A radiologist can look fine on the combined D&C number and still be badly down on "
            "one program - the combined figure is volume-weighted, so a small struggling program "
            "disappears inside a large healthy one. Reading only the combined number is what "
            "Priority 3 exists to catch.",
            "Loss attribution reports XR, CT and US where each is negative, and falls back to "
            "'D&C' only when all three are non-negative or absent but the combined figure is "
            "negative - so the fallback means 'the loss is real but not localised to a program'.",
            _MVP_BASELINE_WINDOW,
            _MVP_IMPLAUSIBLE,
        ),
    ),
    MetricSpec(
        key="mvp_priority_tier_rads",
        label="Derived MVP Priority Tier",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="derived in-app from baseline capacity + the efficiency-change columns",
        numerator="COUNT(DISTINCT npi) per derived tier",
        definition=(
            "Priority 1 is high baseline productivity with flat-or-negative D&C efficiency - the "
            "largest capacity at risk. Priority 2 is the same efficiency picture at average "
            "productivity. Priority 3 is a radiologist whose combined number looks acceptable "
            "but who is sharply down on at least one specific program."
        ),
        lifted_from="backend/app/services/ai_context_service.py:_priority_tier_counts",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            # Stating this plainly is the honest move: the deck never defined a formula, and a
            # tier label on a named radiologist implies more rigour than the input supports.
            "Derived here, not supplied by the CRM. The methodology deck defines the three tiers "
            "in prose but never codified a formula, so this uses defensible stand-ins: "
            "'high productivity' is the top third of baseline capacity across the active cohort, "
            "'low or negative' D&C change is below +5%, and 'very negative' on a program is "
            "below -20% (XR, CT Head) or -37% (US Capture) - the same figures cited in the "
            "program narrative.",
            "Productivity is a percentile rank within the active cohort, so a radiologist's tier "
            "can change when other radiologists enter or leave MVP, with no change to their own "
            "numbers.",
            "Excluded radiologists and those with no baseline capacity are assigned no tier "
            "rather than a default one.",
            _MVP_PRIORITY_HAND_SYNC,
        ),
    ),
    MetricSpec(
        key="mvp_baseline_capacity_tbwu_9h",
        label="Baseline Capacity (TBWU/9h shift)",
        domain="mvp",
        solutions=("reporting", "drafting", "capture"),
        source="rad_onboarding.baseline_capacity_tbwu_9h",
        numerator="baseline_capacity_tbwu_9h",
        definition=(
            "Time-Based Work Units the radiologist produced per nine-hour shift during the "
            "baseline window - the productivity scale used to decide how much capacity is at "
            "risk if their efficiency does not recover."
        ),
        lifted_from=_MVP_SRC,
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "A baseline figure, not a current one. It does not move as the radiologist improves; "
            "it is the yardstick the improvement is measured against.",
            "This is the input to the 'high productivity' half of the priority tiers, which is "
            "why a radiologist with no baseline capacity gets no tier at all.",
            # Keeps it from being read as the Capacity domain's metric of the same family.
            "Distinct from the Capacity domain's RPWU figures, which are computed from exam "
            "inventory at shift grain. This one travels with the Dynamics row.",
        ),
    ),
    MetricSpec(
        key="mvp_cohort_rads",
        label="MVP Cohort",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.mvp_cohort (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) per cohort label",
        definition=(
            "Which MVP intake a radiologist belongs to. Two scopes are read off the label: the "
            "Mammo cohort is every row whose cohort contains '(Mammo)', and the Overview scope "
            "is every row with a cohort set that is neither Mammo nor '(Ops or Self Referred)'."
        ),
        lifted_from=f"{_MVP_SRC}:scope_rows",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "The two scopes are disjoint by construction and neither is the whole table - "
            "'(Ops or Self Referred)' rows appear in neither, so Overview plus Mammo is less "
            "than the tracked population rather than equal to it.",
            "Scoping is a substring test on a free-text CRM label. A cohort renamed in Dynamics "
            "silently leaves both scopes rather than erroring.",
            _MVP_THREE_CENSUSES,
        ),
    ),
    MetricSpec(
        key="mvp_excluded_rads",
        label="Excluded Radiologists",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.exclusion_reason (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) WHERE exclusion_reason IS NOT NULL",
        definition=(
            "Radiologists carrying an exclusion reason - identified as MVP candidates but "
            "deliberately not worked. Excluding them is a decision that was made and recorded, "
            "not an absence of data."
        ),
        lifted_from="backend/app/data/mvp_context.py:EXCLUSION_REASON_GLOSSARY",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "26 distinct reasons are observed live (2026-10-17). Only three are named in the "
            "methodology deck - Q3 go-live practice, under 100 exams, no efficiency loss. The "
            "rest are the CRM's own finer-grained reasons, glossed in mvp_context.py.",
            "An exclusion is not a judgement about the radiologist. The most common reasons are "
            "about measurability (too little volume, not yet on RPCE) or local-practice "
            "leadership guidance.",
            "Excluded radiologists are held out of the priority tiers and the active cohort "
            "count, but remain in the table - so a raw row count overstates the worked "
            "population.",
        ),
    ),
    MetricSpec(
        key="mvp_mentor_matched_rads",
        label="Peer-Coach Matching Status",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding mentorship fields (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) per matching_status",
        definition=(
            "Where a radiologist stands in the peer-coach programme: whether a mentor has been "
            "identified, matched, and engaged. Mentorship is the intervention behind the "
            "Solutioning stage, so this is the operational detail under that stage's count."
        ),
        lifted_from=f"{_MVP_SRC} (mentor_match block)",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "Mentorship is also one of the three escalation owners. A radiologist can be both "
            "matched to a coach and escalated to the Mentorship queue - the second means the "
            "match is not working, not that it is missing.",
            "A declined match ('Mentor Declined') is one of the keywords that buckets a Closed "
            "radiologist as declined rather than completed.",
        ),
    ),
    MetricSpec(
        key="mvp_weekly_engaged_rads",
        label="Weekly Engagement Trend",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding.optimization_last_updated (Dynamics CRM)",
        numerator="COUNT(DISTINCT npi) WHERE _stage_bucket(status) IS NOT NULL",
        denominator="COUNT(DISTINCT npi) in the cohort scope",
        definition=(
            "Radiologists in the funnel versus not yet engaged, bucketed by ISO week (Monday "
            "start) over the trailing six weeks. It answers how fast the programme is picking "
            "people up, which the point-in-time funnel cannot show."
        ),
        lifted_from=f"{_MVP_UI_SRC}:computeWeeklyEngagementTrend",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            # Leads, because this is the caveat the chart itself is captioned with.
            _MVP_APPROXIMATED_DATES,
            "Each radiologist appears in exactly one week - the week they were last touched, not "
            "every week they were engaged. So this is an arrivals chart, not a running total, "
            "and the bars do not accumulate to the funnel count.",
            _MVP_PRE_FUNNEL_EXCLUDED,
            "TypeScript-only today: computeWeeklyEngagementTrend has no Python counterpart, so "
            "the AI narrative cannot cite these numbers. test_registry_parity records it as a "
            "known one-sided definition rather than failing on the absence.",
        ),
    ),
    MetricSpec(
        key="mammo_screening_efficiency_change_pct",
        label="Screening Mammo Efficiency Change",
        domain="mvp",
        solutions=("drafting", "capture"),
        source="rad_onboarding, Mammo cohort scope",
        numerator="efficiency change %, Mammo cohort",
        definition=(
            "Screening-mammography reading efficiency over time, shown for the MVP Mammo cohort "
            "against RP Overall. The comparison is the point: a cohort selected for being behind "
            "should converge toward the enterprise line if the intervention is working."
        ),
        lifted_from=f"{_MVP_UI_SRC}:scopeRows (mammo)",
        grain="radiologist",
        trust="app",
        composable=False,
        caveats=(
            "The two series are not independent - MVP Mammo radiologists are inside RP Overall, "
            "so the enterprise line moves with them. A converging gap is partly the cohort "
            "pulling the benchmark toward itself.",
            "Cohort membership is a substring test on the free-text CRM cohort label.",
            _MVP_IMPLAUSIBLE,
            # Named explicitly because this is the one place the comparator legitimately differs.
            "CRC, NEOH and RAC are tracked against their own Mosaic-efficiency-over-time trend "
            "rather than the legacy voice-recognition baseline, so they are not comparable to "
            "the rest of this series.",
        ),
    ),
)

# --------------------------------------------------------------------------------------------
# Next best action - the ranking, not the taxonomy
# --------------------------------------------------------------------------------------------
#
# The worklist's headline figure is the one number on that surface someone challenges out loud,
# and until this block it was the only number on it with no governed definition. The card there
# resolved to `non_drafted_reason`, which defines the six *leakage categories* - the right
# grounding for the breakdown inside an expanded row, and silent about why a team is ranked
# first. A reader hovering the headline got a confident answer to a question they had not asked.
#
# `composable=False` and `trust="app"`, for the same reason the MVP block is: these are computed
# in Python over cached rows, not in Spark. The `numerator` fields below are the classification
# and arithmetic rules written out, deliberately readable as documentation and deliberately
# unemittable as SQL - `value_sql()` refuses on both.
#
# The methodology prose is NOT restated here. `next_best_action_service.METHODOLOGY` is the one
# copy, interpolated into the live `basis` string the panel prints and injected verbatim into the
# AI grounding; a third copy in this file is exactly the drift the registry exists to prevent.
# These caveats carry only what METHODOLOGY does not: the shape of the number and how it fails.

_NBA_SRC = "backend/app/services/next_best_action_service.py"

_NBA_NOT_A_FORECAST = (
    "Not a forecast and not a target. It is the volume that would convert if this team reached "
    "a draft rate comparable teams already achieve in the same window, with everything else "
    "held still - so the defensible challenge to it is 'those peers are not comparable', not "
    "'your projection is wrong'."
)

_NBA_ADDRESSABLE_ONLY = (
    "Scoped to the three operator-movable leakage categories only: already Drafted, Draftable - "
    "Rad Not Enrolled, and Draftable - Not Drafted (Workflow). Volume blocked by practice "
    "enablement or by uncovered procedures is excluded from both the rate and the unlock, and "
    "reported beside it, because neither converts by anything the person working this list can "
    "do - they escalate to Deployment and to the model roadmap instead. Summing expected unlock "
    "across teams therefore understates the total opportunity, on purpose."
)

_NBA_SMALL_TEAM_FLOOR = (
    "Teams under the minimum addressable volume are dropped from the ranking *and* from the "
    "benchmark. A handful of exams sits at 0% or 100% by chance, and left in, those teams drag "
    "the peer frontier somewhere no team of real size could follow."
)

ACTION_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="expected_unlock_tbwu",
        label="Expected Unlock (TBWU)",
        domain="utilization",
        solutions=("drafting",),
        source="mosaic_drafting_metric_vw (via the cached undrafted analysis)",
        numerator=(
            "(peer benchmark draft rate - this team's draft rate) * this team's addressable "
            "draftable TBWU"
        ),
        definition=(
            "Draftable workload this team would convert by reaching the peer benchmark draft "
            "rate - the ranking key for the drafting worklist. Zero when a team is already at "
            "or above the benchmark, so the list contains only teams with somewhere to move."
        ),
        lifted_from=f"{_NBA_SRC}:rank",
        grain="team",
        trust="app",
        composable=False,
        caveats=(_NBA_NOT_A_FORECAST, _NBA_ADDRESSABLE_ONLY, _NBA_SMALL_TEAM_FLOOR),
    ),
    MetricSpec(
        key="peer_benchmark_draft_rate",
        label="Peer Benchmark Draft Rate",
        domain="utilization",
        solutions=("drafting",),
        source="mosaic_drafting_metric_vw (via the cached undrafted analysis)",
        numerator=(
            "percentile(draft rate across qualifying teams, benchmark_pctile) over the trailing "
            "window"
        ),
        definition=(
            "The draft rate the ranking measures every team against: a percentile of the rates "
            "peer teams actually recorded in the window, selectable on the panel between the "
            "median peer and the top decile. It moves when peers move, which is the point - the "
            "bar is observed, not set."
        ),
        lifted_from=f"{_NBA_SRC}:rank",
        grain="team",
        trust="app",
        composable=False,
        caveats=(
            _NBA_SMALL_TEAM_FLOOR,
            "Raising the percentile raises every team's gap at once. A team moving up the list "
            "after a percentile change has not got worse - the comparator did.",
        ),
    ),
)

# The domain tuples, named once. `METRICS` and `_validate_registry` both need this list, and
# until a fifth domain was added they each carried their own copy - so the new tuple landed in
# `METRICS` and not in the validator, which then reported "METRICS lost entries to duplicate
# keys" about a registry that had no duplicates at all. The check that exists to catch a typo
# in a tuple cannot itself be a second list of the tuples.
#
# Held as *names*, resolved through `globals()` at call time, rather than as the tuple objects.
# `test_capacity_and_volume_adoption_do_not_collide` proves the duplicate-key guard by
# reassigning `reg.CAPACITY_METRICS` and re-running the validator; a list of objects captured at
# import would not see that reassignment, and the guard would pass by never being exercised.
_METRIC_SOURCE_NAMES: tuple[str, ...] = (
    "VOLUME_METRICS",
    "CAPACITY_METRICS",
    "EFFICIENCY_METRICS",
    "MVP_METRICS",
    "ACTION_METRICS",
)


def _all_specs() -> tuple[MetricSpec, ...]:
    return tuple(spec for name in _METRIC_SOURCE_NAMES for spec in globals()[name])


METRICS: dict[str, MetricSpec] = {m.key: m for m in _all_specs()}


# --------------------------------------------------------------------------------------------
# The feature bridge
# --------------------------------------------------------------------------------------------
#
# `AIHoverCard` is keyed by a UI *feature* string; this registry is keyed by *metric*. Something
# has to map one to the other, and if the frontend does it the mapping becomes a fifth copy. So
# the registry owns it and serves it on the route - backend grounding and frontend tooltip read
# the same table by construction.
#
# Wave 2 fills in the Capacity and Efficiency features. One deliberate omission is listed
# below: mapping a feature to a metric that is *not* the one on screen is the plausible-but-
# wrong failure this project keeps hitting, so a feature whose lineage is not folded in stays
# coverage-only rather than being given the nearest available metric.

FEATURE_METRICS: dict[str, tuple[str, ...]] = {
    "adoption_rollout": ("pct_mosaic", "pct_drafting"),
    # --- Utilization / Volume ------------------------------------------------------------------
    # The VolumeDetail KPI row is four tiles and three keys. `adoption_rollout` above already
    # covers the share tile and is reused there rather than duplicated; these two cover the
    # tiles it cannot.
    #
    # `volume_counts` carries all three count metrics because the exam total and the solution
    # count sit side by side and are *nested*, not disjoint - the one thing a reader can get
    # wrong here is adding them, and a card that defined only the metric under the cursor would
    # leave the other half of that mistake undefined.
    "volume_counts": ("total_exams", "mosaic_exams", "drafting_exams"),
    # Separate from `adoption_rollout` despite both rendering a percentage, because they do not
    # share a denominator: these two divide by RPCE-sourced exams only. Filing them under the
    # adoption key would have attached the wrong denominator to the number on screen, which is
    # the plausible-but-wrong failure this bridge exists to prevent.
    #
    # Deliberately NOT in FEATURE_COVERAGE below: this is volume lineage, counted from exam
    # flags with no read-time dependency at all. Declaring READ_TIME_COVERAGE here would promise
    # a gate that never runs on this data - the `shift_utilization` mistake, which took a
    # rewrite of that lineage to repair, not a prose change. Same reasoning for `volume_counts`.
    "volume_rpce": ("pct_rpce_reporting", "pct_rpce_drafting"),
    "capacity_coverage": ("pct_exams_with_valid_read_time", "pct_shifts_rpce_source"),
    "capacity_figure": ("capacity_rpwu", "capacity_rvu_per_hour"),
    "shift_utilization": ("utilization_rpwu_pct",),
    # All three, because the Efficiency tile renders all three and carries exactly one hover
    # card: AIHoverCard does not stopPropagation, so a nested card for the read-time figure
    # would fire both. The definition has to travel on the card that is actually there.
    "efficiency_metric": ("mosaic_tbwu_per_min", "baseline_tbwu_per_min", "read_time_change_pct"),
    # Deliberately absent: "read_time_savings". It was registered for "surfaces that show
    # read-time savings on its own, away from the rate pair" - a surface that does not exist.
    # EfficiencyDetail renders the figure inside the three-metric tile, which `efficiency_metric`
    # already covers. A speculative key is worse than no key: the prose stays while the tile it
    # described is rewritten, and nothing fails. `test_registered_features_are_not_dead_keys`
    # catches that now. The metric itself (`read_time_change_pct`) is unaffected and stays.
    # Deliberately absent: "capacity_additional_pct". It renders (current - baseline) / baseline
    # from `get_capacity_with_baseline`, a separate query whose per-procedure baseline is not
    # folded into this registry. The tempting entry is `capacity_rvu_per_hour`, which is the
    # *current* side only - a hover that defined the delta as its own numerator would be worse
    # than no definition. It keeps its coverage threshold below and gains a metric in Wave 3.
    #
    # --- MVP ----------------------------------------------------------------------------------
    # Ten feature keys, all of which rendered AI commentary against no definition at all before
    # this block. They are listed in the order a reader meets them on the Cockpit surface.
    #
    # Each maps to every metric the card's tile actually renders, for the same reason
    # `efficiency_metric` carries three: AIHoverCard does not stopPropagation, so one card has to
    # carry the whole tile's lineage or part of the tile goes undefined.
    # Both the funnel chart and the escalations donut call this one key - they sit in the same
    # card pair and share a card, so the definition has to cover both or half the pair is
    # undefined. The key spelling is the TSX's, not a tidier one: a feature key that does not
    # match the call site resolves to null and silently degrades to ungrounded commentary,
    # which looks identical to working.
    "mvp_status_funnel": ("mvp_funnel_rads", "mvp_escalations_by_owner"),
    "mvp_impact": ("mvp_impact_breakdown_rads", "mvp_post_engagement_rads"),
    # The roster's per-radiologist efficiency column set. The rolling figure is named separately
    # from the cumulative one because reading the wrong column is the live failure mode here.
    "mvp_efficiency_change": (
        "mvp_dc_efficiency_change_pct",
        "mvp_rolling_30d_change_pct",
        "mvp_program_efficiency_change_pct",
    ),
    "mvp_capacity": ("mvp_baseline_capacity_tbwu_9h",),
    "mvp_priority": ("mvp_priority_tier_rads", "mvp_baseline_capacity_tbwu_9h"),
    "mvp_exclusion": ("mvp_excluded_rads",),
    "mvp_cohort": ("mvp_cohort_rads",),
    "mvp_mentor_match": ("mvp_mentor_matched_rads",),
    "mvp_weekly_trend": ("mvp_weekly_engaged_rads",),
    "mammo_screening_trend": ("mammo_screening_efficiency_change_pct",),
    # --- Next best action ----------------------------------------------------------------------
    # Both, because the panel's headline and its benchmark selector sit inside one card: the
    # unlock figure is meaningless without the rate it is measured against, and a hover that
    # defined only the first would invite exactly the "compared to what?" it exists to answer.
    "next_best_action": ("expected_unlock_tbwu", "peer_benchmark_draft_rate"),
    # --- Movers & drivers ------------------------------------------------------------------------
    # Both sides of the gap, for the same reason as above: the waterfall's headline is a
    # *difference* between two TBWU/min rates, and its hover card sits on the whole tile. A card
    # that defined only the group's own rate would leave the thing it is subtracted from
    # undefined, which is precisely the ambiguity the decomposition exists to remove.
    #
    # `read_time_change_pct` is deliberately NOT here even though `efficiency_metric` carries it:
    # the waterfall never renders a percent change. It splits a levels gap into mix and rate, and
    # a definition for a figure the tile does not show is prose nobody can check against a number.
    "efficiency_movers": ("mosaic_tbwu_per_min", "baseline_tbwu_per_min"),
}

# Features whose displayed value is governed by an instrumentation threshold. These resolve
# today even though their metrics do not, because the threshold is real and already enforced in
# `mosaic_service` - it is the metric *definitions* that are still waiting on Wave 2.
FEATURE_COVERAGE: dict[str, str] = {
    "capacity_coverage": READ_TIME_COVERAGE.key,
    "capacity_additional_pct": READ_TIME_COVERAGE.key,
    "capacity_figure": READ_TIME_COVERAGE.key,
    "efficiency_metric": READ_TIME_COVERAGE.key,
    # Same lineage, same standing - and `shows_anyway` is why this is a declaration rather than a
    # suppression. The decomposition divides population-matched TBWU by population-matched read
    # minutes inside every bucket, so the coverage fraction cancels there exactly as it does for
    # `efficiency_metric`, and no bucket is withheld for low coverage. What does not cancel is the
    # caveat's small-sample half, and a bucket is a thinner slice than the whole group: declaring
    # the gate here is what puts that warning in front of a reader about to act on one row.
    "efficiency_movers": READ_TIME_COVERAGE.key,
    # This one used to be the exception. The lineage behind it carried no coverage column, so the
    # threshold was declared here and enforced nowhere - a surface that promised suppression and
    # rendered every value, including ones built from almost no read time. It now computes read
    # time at exam grain the same way Capacity does and routes through the same gate, so the entry
    # below means what the other five mean.
    "shift_utilization": READ_TIME_COVERAGE.key,
    # --- MVP ----------------------------------------------------------------------------------
    # A different gate shape entirely: a ceiling on the value's own magnitude, not a floor under
    # an instrumentation ratio. See MVP_PLAUSIBILITY's `direction="max"` and the comment on
    # `CoverageSpec.direction` for why that distinction had to become a field rather than stay a
    # convention - a max-shaped gate described by the old min-shaped sentence template read
    # exactly backwards.
    #
    # Only the features that render a percentage change are listed. A count of radiologists at a
    # funnel stage divides by nothing and so cannot produce the tiny-denominator artifact this
    # gate exists to catch; gating it would suppress a sound number and imply a data problem that
    # is not there.
    "mvp_efficiency_change": MVP_PLAUSIBILITY.key,
    "mvp_impact": MVP_PLAUSIBILITY.key,
    "mammo_screening_trend": MVP_PLAUSIBILITY.key,
    # Gated because the tier is *derived from* the gated columns: an implausible D&C change
    # would otherwise classify a radiologist into Priority 1 or 2 on the strength of an
    # artifact, which is worse than leaving them untiered.
    "mvp_priority": MVP_PLAUSIBILITY.key,
}


# The third state. A feature key is either registered above, or listed here with the reason it
# will never be - and nothing else is legal.
#
# This list lived in `tests/test_registry_parity.py` until now, which put the exemption in a
# different file from the thing it exempts. Three costs, all of them real:
#   1. `_validate_registry()` could not see it, so a key could be both registered AND exempted
#      and nothing would fail.
#   2. `snapshot()` could not see it, so these four features were absent entirely from
#      `GET /api/mosaic/registry` - the hover card could not tell "deliberately undefined"
#      apart from "typo in the feature prop", and rendered both as bare AI text.
#   3. The reasons - which are the good part - were visible only to whoever opened the test.
#
# The test still guards completeness (a new unregistered key in TSX fails it); it just no
# longer owns the declaration.
UNREGISTERED_FEATURES: dict[str, str] = {
    "non_drafted_reason": (
        "The six leakage categories are a taxonomy, not a metric - there is no num/den to "
        "declare. Folds in with the funnel endpoint, not with a MetricSpec."
    ),
    "sentiment": (
        "rad_survey.py, 810 respondents. The only non-telemetry source in the product, and the "
        "one thing in it that is not an EDW measure at all."
    ),
    "baseline_review_match": (
        "A workflow state on the review queue, not a measurement of radiologist performance."
    ),
    "mvp_notes_summary": (
        "The one feature whose value is not a number: it carries the raw case-note text, and "
        "`ai_context_service` gives it a summarization prompt rather than the explain-this-"
        "data-point framing. A MetricSpec would have nothing to put in `numerator`."
    ),
    "value_chain": (
        "One component rendering four different stage metrics - a head count at Deploy, an "
        "adoption rate at Use, an efficiency change at Perform, a read-time change at Return. "
        "Declaring the union under FEATURE_METRICS would attach all four definitions to every "
        "card, which is the wrong-denominator failure this bridge exists to prevent, and the "
        "Deploy head counts have no MetricSpec at all. Each card names its own metric in "
        "`metricLabel`; the grounding explains the chain the four sit on."
    ),
    "mvp_journey": (
        "A position in a five-step process, not a measurement - the value is a step number read "
        "off the program's own mosaic_optimization_support_status vocabulary. There is no "
        "num/den, and no coverage question: a radiologist either has a recorded status or does "
        "not, which the position itself reports."
    ),
}


# --------------------------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------------------------


class UnknownMetricError(KeyError):
    """Raised with the legal alternatives listed, never with a bare key."""


class UnsupportedDimensionError(ValueError):
    """Raised with the legal alternatives listed, never with a bare key."""


def get_metric(key: str) -> MetricSpec:
    try:
        return METRICS[key]
    except KeyError:
        raise UnknownMetricError(
            f"unknown metric: {key!r}. Known metrics: {', '.join(sorted(METRICS))}"
        ) from None


def get_dimension(key: str) -> Dimension:
    try:
        return DIMENSIONS[key]
    except KeyError:
        raise UnsupportedDimensionError(
            f"unknown dimension: {key!r}. Known dimensions: {', '.join(sorted(DIMENSIONS))}"
        ) from None


def validate_scope(metric_keys: list[str], dim_keys: list[str]) -> None:
    """Reject an illegal metric x dimension combination *by name*, before any SQL is built.

    Refusing with a listed alternative is the whole point: a silently mis-joined grouping renders
    a plausible wrong number, which is worse than an error. Deployment metrics in Wave 3 will key
    off this - Dynamics Practice is free text with no MDM key, so a Local Region group-by on a
    Deployment metric has to be refused rather than approximated.
    """
    for mk in metric_keys:
        spec = get_metric(mk)
        for dk in dim_keys:
            get_dimension(dk)
            if dk not in spec.allowed_dims:
                # A metric with *no* allowed dims is the normal case for the 19 non-composable
                # ones, and listing its alternatives then yields "Supported for this metric: "
                # with nothing after the colon - which reads to a caller as a broken suggester
                # rather than as an answer. Say the real reason instead, and take the grain from
                # the spec rather than assuming it: the Efficiency pair is exam-grain but computed
                # outside Spark (no SQL GROUP BY to attach a dimension to), while Capacity is
                # shift-grain (its CTE's entity columns are not the cube's dimensions). Same
                # shape as the refusal `scope.py` builds for the Ask path - that one intersects
                # allowed_dims across several metrics, which this single-metric check cannot do.
                if spec.allowed_dims:
                    detail = f"Supported for this metric: {', '.join(spec.allowed_dims)}"
                else:
                    detail = (
                        f"{spec.label} ({spec.grain} grain) has no breakdown in this registry "
                        "yet - it is available enterprise-wide only. Ask for it without a "
                        "breakdown, or pick a metric that supports one."
                    )
                raise UnsupportedDimensionError(
                    f"metric {mk!r} cannot be grouped by {dk!r}. {detail}"
                )


def select_sql(metric_keys: list[str], indent: str = "    ") -> str:
    """The measure SELECT list for the given metrics, in the order asked for.

    Aliases to `output_name`, not to the key: the Capacity fold-in has two metrics whose
    deployed column name is already taken by a Volume metric with a different denominator, and
    reproducing the deployed SQL means reproducing its column names.
    """
    return ",\n".join(
        f"{indent}{get_metric(k).value_sql()} AS {get_metric(k).output_name}" for k in metric_keys
    )


def required_filters(dim_keys: list[str]) -> list[str]:
    """Filters the chosen dimensions require. Travels with the dimension, not the call site."""
    out: list[str] = []
    for dk in dim_keys:
        f = get_dimension(dk).required_filter
        if f and f not in out:
            out.append(f)
    return out


def describe(metric_key: str) -> dict:
    """The payload `GET /api/mosaic/registry` serves and `AIHoverCard` renders, so no definition
    is ever hardcoded in TSX."""
    m = get_metric(metric_key)
    return {
        "key": m.key,
        "label": m.label,
        # The column this metric arrives in on an API payload, which is not always its key -
        # see `MetricSpec.column`. A consumer mapping a response field back to a definition
        # needs this; mapping by key alone would silently resolve Capacity's `pct_mosaic` to
        # Volume's.
        "column": m.output_name,
        "domain": m.domain,
        "solutions": list(m.solutions),
        # "" when ungated. Set means the value can legitimately arrive NULL by policy, so a
        # surface can say "withheld" instead of "missing".
        "gated_by": m.gated_by,
        "definition": m.definition,
        "caveats": list(m.caveats),
        "grain": m.grain,
        "is_rate": m.is_rate,
        "trust": m.trust,
        "source": m.source,
        "owner": m.owner,
        "version": m.version,
        "allowed_dims": [
            {"key": d, "label": DIMENSIONS[d].label, "note": DIMENSIONS[d].note}
            for d in m.allowed_dims
            if d in DIMENSIONS
        ],
    }


def describe_dimension(dim_key: str) -> dict:
    """Dimension metadata standalone, not nested under some metric that happens to allow it.

    The Team/Practice note is the single most-needed piece of prose in this product and it was
    only reachable by first picking a metric - which is backwards, since the distinction is a
    property of the dimension.
    """
    d = get_dimension(dim_key)
    return {
        "key": d.key,
        "label": d.label,
        "note": d.note,
        "required_filter": d.required_filter,
        "metrics": [k for k, m in METRICS.items() if dim_key in m.allowed_dims],
    }


def describe_coverage(coverage_key: str) -> dict:
    """The threshold, in the form a badge and a tooltip both need."""
    try:
        c = COVERAGE[coverage_key]
    except KeyError:
        raise UnknownMetricError(
            f"unknown coverage spec: {coverage_key!r}. Known: {', '.join(sorted(COVERAGE))}"
        ) from None
    return {
        "key": c.key,
        "label": c.label,
        "min_ratio": c.min_ratio,
        "min_pct_label": c.min_pct_label,
        "direction": c.direction,
        "threshold_label": c.threshold_label,
        # The rendered rule, composed here so the TSX stops building it from parts and can no
        # longer get the direction wrong. `suppresses`/`shows_anyway` stay on the payload for
        # callers that want the lists themselves (the badge groups by them).
        "sentence": c.sentence,
        "measured_by": c.measured_by,
        "suppresses": list(c.suppresses),
        "shows_anyway": list(c.shows_anyway),
        "caveat": c.caveat,
        "note": c.note,
    }


def grounding_for(feature: str) -> str:
    """Registry-owned prompt grounding for one UI feature, or `""` if it maps to no metric.

    Returns *metric* text only - definitions and caveats. It deliberately does not append the
    coverage caveat, even for coverage-bearing features: the methodology constants in
    `ai_context_service` already end with that exact string (they import it from here), so
    adding it would put ~200 identical words into the prompt twice.

    That same single-copy discipline is applied *within* this function. Composing per metric and
    pasting each one's caveats inline re-emitted every shared caveat once per metric carrying it,
    which measured at 8 repeated sentences on `mvp_efficiency_change`, 7 on `efficiency_metric`,
    5 on `efficiency_movers` and 4 on `volume_rpce` - all of it paid for on every hover.

    Why only *universal* caveats are hoisted, and partial ones are left inline: some caveats are
    carried by some but not all of a feature's metrics. `efficiency_metric` has one of three
    (Mosaic and baseline rates are not computed the same way) and `mvp_efficiency_change` has two
    of three. Moving those to a trailing sentence would read as qualifying the whole feature and
    quietly widen their scope onto metrics they are not true of - a worse outcome than the
    repetition, because it is wrong rather than merely long. So a caveat is hoisted only when
    *every* metric in the feature carries it, and only when there is more than one metric, which
    makes single-metric features byte-identical to the previous output.
    """
    metrics = [METRICS[k] for k in FEATURE_METRICS.get(feature, ()) if k in METRICS]
    if not metrics:
        return ""

    shared: tuple[str, ...] = ()
    if len(metrics) > 1:
        # Ordered by the first metric's own caveat order, so the trailer reads in the sequence
        # its author wrote rather than in set order.
        shared = tuple(c for c in metrics[0].caveats if all(c in m.caveats for m in metrics[1:]))

    parts: list[str] = []
    for m in metrics:
        text = f"{m.label}: {m.definition}"
        own = [c for c in m.caveats if c not in shared]
        if own:
            text += " " + " ".join(own)
        parts.append(text)
    if shared:
        parts.append(" ".join(shared))
    return " ".join(parts)


def describe_mode(mode_key: str) -> dict:
    """One solution of the product - the axis that makes this a cube and not a metric list."""
    m = EFFICIENCY_MODES[mode_key]
    return {"key": m.key, "label": m.label, "description": m.description}


def describe_feature(feature: str) -> dict:
    """What one `AIHoverCard` feature resolves to.

    Three honest states, all of which this can return:
      - metrics set              -> a governed definition exists
      - metrics empty + coverage -> the threshold is declared, the metric is still waiting on
                                    its wave
      - `unregistered_reason`    -> there will never be a metric here, and this says why

    The third is the one that used to be indistinguishable from a typo in the `feature` prop.
    """
    cov_key = FEATURE_COVERAGE.get(feature)
    return {
        "feature": feature,
        "metrics": [describe(k) for k in FEATURE_METRICS.get(feature, ())],
        "coverage": describe_coverage(cov_key) if cov_key else None,
        "grounding": grounding_for(feature),
        "unregistered_reason": UNREGISTERED_FEATURES.get(feature, ""),
    }


def snapshot() -> dict:
    """The whole registry, as `GET /api/mosaic/registry` serves it.

    Fetched once per frontend process and held, so it is a snapshot rather than a per-hover
    lookup: every definition rendered in TSX comes from here, and `version` is how the client
    knows a cached copy went stale. Builds from in-memory dataclasses only - no EDW, no cache,
    no I/O of any kind, which is what makes it safe to serve from a route in an app whose single
    shared Databricks connection sits behind one lock.
    """
    return {
        "version": REGISTRY_VERSION,
        "generated_from": "backend/app/semantics/registry.py",
        "waves_folded_in": ["volume", "capacity", "efficiency", "mvp"],
        "ai_fallback_text": AI_FALLBACK_TEXT,
        "metrics": [describe(k) for k in METRICS],
        "modes": [describe_mode(k) for k in EFFICIENCY_MODES],
        "dimensions": [describe_dimension(k) for k in DIMENSIONS],
        "coverage": [describe_coverage(k) for k in COVERAGE],
        # The three-way union, not the two-way one: a deliberately undefined feature is served
        # *with its reason* so the client can say so, instead of resolving to nothing and being
        # indistinguishable from a misspelled `feature` prop.
        "features": [
            describe_feature(f)
            for f in sorted(set(FEATURE_METRICS) | set(FEATURE_COVERAGE) | set(UNREGISTERED_FEATURES))
        ],
    }


def _validate_registry() -> None:
    """A typo in a tuple above becomes an ImportError at startup rather than a KeyError inside a
    request handler. This is the thing plain Python buys us over YAML."""
    # A dict comprehension silently keeps the last of any duplicate key, which is precisely how
    # Capacity's pct_mosaic would have erased Volume's. Count the source tuples, not the dict.
    all_specs = _all_specs()
    seen: dict[str, MetricSpec] = {}
    for spec in all_specs:
        if spec.key in seen:
            raise ValueError(
                f"duplicate metric key {spec.key!r} ({seen[spec.key].lifted_from} and "
                f"{spec.lifted_from}) - one would silently overwrite the other in METRICS"
            )
        seen[spec.key] = spec
    if len(seen) != len(METRICS):  # pragma: no cover - unreachable given the loop above
        raise ValueError("METRICS lost entries to duplicate keys")

    for spec in METRICS.values():
        for dim in spec.allowed_dims:
            if dim not in DIMENSIONS:
                raise ValueError(f"metric {spec.key!r} declares undefined dimension {dim!r}")
        if spec.offset and spec.denominator is None:
            raise ValueError(f"metric {spec.key!r} declares an offset but is not a rate")
        if spec.numerator_scale and spec.denominator is None:
            raise ValueError(f"metric {spec.key!r} scales a numerator it never divides")
        if spec.gated_by:
            if spec.gated_by not in COVERAGE:
                raise ValueError(
                    f"metric {spec.key!r} is gated by undefined coverage spec {spec.gated_by!r}"
                )
            # A gate with no coverage ratio would compose `try_divide(, ) >= 0.75`, which is a
            # syntax error at query time rather than here - so it is checked here.
            if not (spec.gate_numerator and spec.gate_denominator and spec.denominator):
                raise ValueError(
                    f"metric {spec.key!r} declares a gate without a complete coverage ratio "
                    f"and metric denominator"
                )
        if spec.column and spec.column == spec.key:
            raise ValueError(
                f"metric {spec.key!r} sets column to its own key - drop the field rather than "
                f"creating a second place the name has to be kept in sync"
            )

    # Two metrics may share an output column (that is the whole point of `column`), but not
    # within one SELECT list. Nothing composes across domains today; this records the rule so
    # the cube's column planner has something to assert against when it does.
    for domain in {s.domain for s in all_specs}:
        cols: dict[str, str] = {}
        for spec in all_specs:
            if spec.domain != domain:
                continue
            if spec.output_name in cols:
                raise ValueError(
                    f"metrics {cols[spec.output_name]!r} and {spec.key!r} both emit column "
                    f"{spec.output_name!r} in domain {domain!r} - they cannot be selected together"
                )
            cols[spec.output_name] = spec.key

    for mode in EFFICIENCY_MODES.values():
        if mode.exprs is not _MODE_EXPRS[mode.key]:
            raise ValueError(
                f"solution mode {mode.key!r} holds a copy of its column triple rather than the "
                f"tuple efficiency_store actually aggregates with"
            )

    # The feature bridge is the one table edited by two different kinds of change - a UI rename
    # and a metric rename - so it is the one most likely to rot. Fail at import, not at hover.
    for feature, keys in FEATURE_METRICS.items():
        for key in keys:
            if key not in METRICS:
                raise ValueError(f"feature {feature!r} maps to undefined metric {key!r}")
    for feature, cov in FEATURE_COVERAGE.items():
        if cov not in COVERAGE:
            raise ValueError(f"feature {feature!r} maps to undefined coverage spec {cov!r}")

    # Registered and exempted are mutually exclusive by construction. Without this, folding a
    # feature in during its wave while forgetting to drop it from the exemption list leaves a
    # stale "there is no metric here" reason attached to a feature that now has one - and
    # `describe_feature` would serve both, contradicting itself in the same payload.
    both = (set(FEATURE_METRICS) | set(FEATURE_COVERAGE)) & set(UNREGISTERED_FEATURES)
    if both:
        raise ValueError(
            "features are both registered and exempted: "
            + ", ".join(sorted(both))
            + " - drop them from UNREGISTERED_FEATURES now that they have a definition"
        )
    for feature, reason in UNREGISTERED_FEATURES.items():
        if not reason.strip():
            raise ValueError(
                f"feature {feature!r} is exempted with an empty reason - the reason is the "
                "entire point of the list, since it is what the hover card renders"
            )


_validate_registry()
