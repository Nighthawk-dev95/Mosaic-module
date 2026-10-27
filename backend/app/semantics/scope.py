"""Turns a question into a *governed scope*, or refuses it by name.

This is the validator half of plan §E-1b (text-to-scope, never text-to-SQL). The language model
proposes; this module disposes. Nothing the model returns reaches a query until every metric,
dimension and solution in it has been matched against `registry.py` - and anything that does not
match comes back as a refusal carrying the legal alternatives, never as a nearest guess.

Why refusal is the feature
--------------------------
The failure this product keeps hitting is not the error message; it is the plausible wrong
number. Two practices with no dictation timestamps once displayed a flawless 100% utilization.
Capacity's `pct_mosaic` and Volume's `pct_mosaic` are different numbers under one name. A
text-to-SQL layer over this warehouse would generate exactly those confusions at machine speed
and present them in prose, which is the most persuasive possible format for a wrong answer.

So this module has one rule: **when a term does not resolve to exactly one governed thing, say
so and name the candidates.** An answer that says "did you mean adoption % or time utilization?"
is worth more than one that picks.

Three ambiguities are hard-coded as such, because each has already produced a wrong reading:

  "utilization"  - adoption % (share of exams on Mosaic) vs time utilization (share of shift
                   spent reading). The metric view's own comment warns these are not the same
                   thing, and the UI once conflated them.
  "% mosaic"     - enterprise (all exams) vs on-shift (matched-shift cases only, ~25% smaller
                   denominator).
  "practice"     - the rad's home practice (Team) vs the site where the exam was read
                   (Practice). Standing instruction from the user, stated twice.

Purity
------
No network, no LLM, no fastapi. `app.semantics` is importable under a bare Python with no
dependencies installed, which is what lets `tests/test_registry_parity.py` run offline, and the
same property should hold here. The model call that *produces* the dict this module validates
lives in `app/services/ask_service.py`, one layer out.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from app.semantics import registry as reg


@dataclass(frozen=True)
class Refusal:
    """One thing the question asked for that this registry does not define.

    Carried back to the user rather than raised, because a question is usually mostly
    resolvable: "efficiency for Boca by subspecialty" should answer the efficiency part and say
    plainly that subspecialty is not a dimension here, rather than failing whole.
    """

    term: str
    reason: str
    alternatives: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"term": self.term, "reason": self.reason, "alternatives": list(self.alternatives)}


@dataclass(frozen=True)
class ScopeSpec:
    """A question reduced to registry keys. Every field here is a key that exists."""

    metrics: tuple[str, ...] = ()
    solution: str = "full_mosaic"
    group_by: tuple[str, ...] = ()
    # Free text, deliberately not resolved here: entity names are data, not registry vocabulary,
    # and this module has no database. The surface that holds the roster resolves it.
    entity: str = ""
    period: str = ""
    refusals: tuple[Refusal, ...] = field(default_factory=tuple)
    # Things that are true of the resolved scope and would change how a reader reads the answer -
    # a coverage gate that may withhold the value, a Team/Practice distinction that is easy to
    # misread. Distinct from refusals: nothing was dropped, but the answer comes with conditions.
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_answerable(self) -> bool:
        """At least one metric survived. A scope with none is a refusal, not a narrow answer."""
        return bool(self.metrics)

    def as_dict(self) -> dict:
        return {
            "metrics": [reg.describe(k) for k in self.metrics],
            "solution": reg.describe_mode(self.solution),
            "group_by": [reg.describe_dimension(k) for k in self.group_by],
            "entity": self.entity,
            "period": self.period,
            "refusals": [r.as_dict() for r in self.refusals],
            "notes": list(self.notes),
            "is_answerable": self.is_answerable,
            "registry_version": reg.REGISTRY_VERSION,
        }


# ------------------------------------------------------------------------------------------
# Vocabulary
# ------------------------------------------------------------------------------------------
#
# Built from the registry at import, not hand-listed: a metric added in Wave 3 becomes askable
# without anyone remembering to update a second table. The hand-written part is only the
# *colloquial* half - the words a CEO says that are not any metric's label.

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_METRIC_ALIASES: dict[str, str] = {}
for _key, _spec in reg.METRICS.items():
    _METRIC_ALIASES[_slug(_key)] = _key
    # Labels collide across domains by design (two "On-Shift Utilization" variants differing only
    # in the RVU/RPWU suffix, which is the same expression twice). First writer wins, and the
    # ambiguity table below catches the cases where that would mislead.
    _METRIC_ALIASES.setdefault(_slug(_spec.label), _key)

_DIM_ALIASES: dict[str, str] = {}
for _key, _dim in reg.DIMENSIONS.items():
    _DIM_ALIASES[_slug(_key)] = _key
    _DIM_ALIASES.setdefault(_slug(_dim.label), _key)

_MODE_ALIASES: dict[str, str] = {}
for _key, _mode in reg.EFFICIENCY_MODES.items():
    _MODE_ALIASES[_slug(_key)] = _key
    _MODE_ALIASES.setdefault(_slug(_mode.label), _key)
_MODE_ALIASES.update({
    "all": "full_mosaic", "mosaic": "full_mosaic", "all mosaic": "full_mosaic",
    "ai drafting": "drafting", "draft": "drafting", "drafts": "drafting",
    "rpce": "reporting", "dictation": "reporting",
    "us": "capture", "ultrasound": "capture", "dexa": "capture",
})

# The colloquial layer. These are words that map cleanly onto one governed key and would
# otherwise fail - not words that are ambiguous. Ambiguity goes in `_AMBIGUOUS`, below.
_METRIC_ALIASES.update({
    "adoption": "pct_mosaic",
    "mosaic adoption": "pct_mosaic",
    "drafting rate": "pct_drafting",
    "drafting adoption": "pct_drafting",
    "draft rate": "pct_drafting",
    "volume": "total_exams",
    "exams": "total_exams",
    "exam count": "total_exams",
    "efficiency": "mosaic_tbwu_per_min",
    "reading efficiency": "mosaic_tbwu_per_min",
    "speed": "mosaic_tbwu_per_min",
    "baseline": "baseline_tbwu_per_min",
    "capacity": "capacity_rpwu",
    "coverage": "pct_exams_with_valid_read_time",
    "read time coverage": "pct_exams_with_valid_read_time",
    "data quality": "pct_exams_with_valid_read_time",
    "shifts": "total_shifts",
    "hours": "total_hours",
    # Page names, because people ask for what the nav calls it. "Shift utilization" is
    # unambiguous where bare "utilization" is not - the word "shift" is exactly the disambiguator.
    "shift utilization": "utilization_rpwu_pct",
    "time utilization": "utilization_rpwu_pct",
    "on shift utilization": "utilization_rpwu_pct",
    "idle time": "utilization_rpwu_pct",
})

# Terms that name more than one governed metric, where picking one has already produced a wrong
# reading in this product. Each entry is (reason, candidate keys). The resolver refuses these
# *even when the model confidently picks* - the model's confidence is not evidence.
_AMBIGUOUS: dict[str, tuple[str, tuple[str, ...]]] = {
    "utilization": (
        "'Utilization' names two different measurements here. Adoption % is the share of exams "
        "read on Mosaic; time utilization is the share of a scheduled shift spent actively "
        "reading. The governed metric view's own comment warns these are not interchangeable.",
        ("pct_mosaic", "utilization_rpwu_pct"),
    ),
    "mosaic utilization": (
        "Same split as 'utilization': adoption share versus share of shift time.",
        ("pct_mosaic", "utilization_rpwu_pct"),
    ),
    "pct mosaic": (
        "Two deployed columns carry this name over different denominators: the enterprise one "
        "divides by all exams, the capacity one by on-shift cases only (~25% fewer, because "
        "roughly a quarter of exams match no scheduled shift).",
        ("pct_mosaic", "capacity_pct_mosaic"),
    ),
    "percent mosaic": (
        "Two deployed columns carry this name over different denominators.",
        ("pct_mosaic", "capacity_pct_mosaic"),
    ),
}

# Deliberately NOT ambiguous: "practice".
#
# It names two different columns in the *codebase* - three UI labels still conflate them - but it
# is not ambiguous in this product's vocabulary, because the convention has been set explicitly:
# Team is the Provider Practice (the radiologist's home practice), Practice is the Managing
# Practice (the site where the exam was read). `DIMENSIONS` already encodes exactly that. Adding
# "practice" to `_AMBIGUOUS` would make the resolver interrogate the user about a word they have
# already defined, which is not rigour - it is refusing to read the spec. The distinction still
# travels with every answer as the dimension's own `note`.
_TEAM_PRACTICE_NOTE = (
    "Team = the radiologist's home practice (provider). Practice = the site where the exam was "
    "read (managing). One radiologist can appear under dozens of Practices but exactly one Team."
)


def suggest(term: str, pool: dict[str, str], limit: int = 3) -> tuple[str, ...]:
    """Nearest governed keys for an unmatched term, so a refusal is actionable.

    Matches against the alias pool (keys *and* labels) but returns registry keys, deduplicated
    and order-preserved - suggesting "Reading Efficiency" to a caller that has to send
    `mosaic_tbwu_per_min` would be a refusal that cannot be acted on.
    """
    hits = difflib.get_close_matches(_slug(term), list(pool), n=limit * 2, cutoff=0.6)
    out: list[str] = []
    for h in hits:
        key = pool[h]
        if key not in out:
            out.append(key)
    return tuple(out[:limit])


def resolve_metric(term: str) -> tuple[str, Refusal | None]:
    """One term to one metric key, or a refusal naming the candidates."""
    s = _slug(term)
    # An exact registry key is never ambiguous, and must be checked before the ambiguity table.
    # `_slug("pct_mosaic")` is "pct mosaic", which is precisely the phrase we refuse when a human
    # says it - but a caller who typed the globally unique key has been as specific as the
    # vocabulary allows. Refusing that is the resolver declining to read its own key space.
    if term in reg.METRICS:
        return term, None
    if s in _AMBIGUOUS:
        reason, candidates = _AMBIGUOUS[s]
        return "", Refusal(term=term, reason=reason, alternatives=candidates)
    key = _METRIC_ALIASES.get(s)
    if key:
        return key, None
    near = suggest(term, _METRIC_ALIASES)
    return "", Refusal(
        term=term,
        reason=(
            "Not a metric this registry defines."
            if near
            else f"Not a metric this registry defines, and nothing is close to it. "
                 f"{len(reg.METRICS)} metrics are available - see /api/mosaic/registry."
        ),
        alternatives=near,
    )


def resolve_dimension(term: str) -> tuple[str, Refusal | None]:
    key = _DIM_ALIASES.get(_slug(term))
    if key:
        return key, None
    return "", Refusal(
        term=term,
        reason="Not a dimension this registry can group by.",
        alternatives=suggest(term, _DIM_ALIASES),
    )


def resolve_solution(term: str) -> tuple[str, Refusal | None]:
    key = _MODE_ALIASES.get(_slug(term))
    if key:
        return key, None
    return "", Refusal(
        term=term,
        reason="Not one of the Mosaic solutions.",
        alternatives=tuple(reg.EFFICIENCY_MODES),
    )


def m_allowed(metric_key: str) -> bool:
    """Whether a metric supports any breakdown at all. Named rather than inlined because the
    reason it can be False differs by domain - see the refusal wording in `resolve`."""
    return bool(reg.get_metric(metric_key).allowed_dims)


def resolve(raw: dict) -> ScopeSpec:
    """Validate a proposed scope - typically an LLM's JSON - into a `ScopeSpec`.

    Everything that fails to resolve becomes a `Refusal` on the returned spec rather than an
    exception, because a half-answerable question deserves half an answer plus a clear statement
    of what was dropped. The one thing that never happens is a term being quietly replaced by its
    nearest match: suggestions are offered, never applied.

    The metric x dimension legality check runs last and *through the registry*
    (`reg.validate_scope`), so the rule that Capacity metrics cannot be grouped by the exam-grain
    dimensions is enforced by the same code the SQL composer uses.
    """
    refusals: list[Refusal] = []

    metrics: list[str] = []
    for term in raw.get("metrics") or []:
        key, refusal = resolve_metric(str(term))
        if refusal:
            refusals.append(refusal)
        elif key not in metrics:
            metrics.append(key)

    group_by: list[str] = []
    for term in raw.get("group_by") or []:
        key, refusal = resolve_dimension(str(term))
        if refusal:
            refusals.append(refusal)
        elif key not in group_by:
            group_by.append(key)

    solution = "full_mosaic"
    if raw.get("solution"):
        key, refusal = resolve_solution(str(raw["solution"]))
        if refusal:
            refusals.append(refusal)
        else:
            solution = key

    # Legality, not spelling: a metric and a dimension can both exist and still not combine.
    # Drop the offending *dimension*, not the metric - the user asked a question about a number,
    # and answering it at a coarser grain beats refusing it outright, as long as we say so.
    legal_dims: list[str] = []
    for dim in group_by:
        try:
            reg.validate_scope(metrics, [dim])
        except reg.UnsupportedDimensionError as exc:
            # When *no* dimension is legal, an empty alternatives list reads as a broken suggester
            # rather than an explanation - so say the real reason, and take the grain from the
            # spec rather than assuming. The two causes are genuinely different: Capacity is
            # shift-grain (its CTE's entity columns are not the cube's dimensions), while the
            # Efficiency pair is exam-grain but computed outside Spark, so there is no SQL
            # GROUP BY to attach a dimension to at all.
            # Intersection, not union. A union would offer `local_region` as the alternative to
            # `local_region` whenever one of several requested metrics happened to allow it -
            # technically true per-metric, useless as advice, and it reads as a bug. What the
            # caller can actually ask for is the set legal across *every* metric in the scope.
            allowed_sets = [set(reg.get_metric(m).allowed_dims) for m in metrics]
            alternatives = tuple(sorted(set.intersection(*allowed_sets))) if allowed_sets else ()
            blockers = ", ".join(
                reg.get_metric(m).label for m in metrics if dim not in reg.get_metric(m).allowed_dims
            )
            reason = f"{blockers} cannot be broken down by {reg.get_dimension(dim).label}."
            if alternatives:
                reason += f" Legal for every metric asked for: {', '.join(alternatives)}."
            if not alternatives:
                blocked = [reg.get_metric(m) for m in metrics if not m_allowed(m)]
                names = ", ".join(s.label for s in blocked)
                grains = ", ".join(sorted({s.grain for s in blocked}))
                reason = (
                    f"{names} ({grains} grain) has no breakdown in this registry yet - it is "
                    f"available enterprise-wide only. Ask for it without a breakdown, or pick a "
                    f"metric that supports one."
                )
            refusals.append(Refusal(term=dim, reason=reason, alternatives=alternatives))
        else:
            legal_dims.append(dim)

    # Conditions on the answer, gathered from the registry rather than written here. The gate note
    # is the one that matters most: a gated metric can come back NULL *by policy*, and an answer
    # that says "no data" where the truth is "withheld below 75% read-time coverage" is the same
    # wrong impression the suppression was built to prevent.
    notes: list[str] = []
    if "team" in legal_dims or "practice" in legal_dims:
        notes.append(_TEAM_PRACTICE_NOTE)
    for m in metrics:
        spec = reg.get_metric(m)
        if spec.gated_by:
            cov = reg.COVERAGE[spec.gated_by]
            note = (
                f"{spec.label} is withheld, not estimated, where {cov.label.lower()} is below "
                f"{cov.min_pct_label}. A blank is a suppression, not a zero."
            )
            if note not in notes:
                notes.append(note)
        if spec.trust == "unavailable":
            notes.append(f"{spec.label} is not computed in this app - its source is unreachable.")

    return ScopeSpec(
        metrics=tuple(metrics),
        solution=solution,
        group_by=tuple(legal_dims),
        entity=str(raw.get("entity") or "").strip(),
        period=str(raw.get("period") or "").strip(),
        refusals=tuple(refusals),
        notes=tuple(notes),
    )


def vocabulary() -> dict:
    """The askable surface, for a prompt or a UI hint list.

    Deliberately compact. The model does not need every caveat at proposal time - it needs the
    legal key space, because its only job is to *propose keys*, and `resolve()` is what decides
    whether the proposal stands.
    """
    return {
        "metrics": {k: m.label for k, m in reg.METRICS.items()},
        "dimensions": {k: d.label for k, d in reg.DIMENSIONS.items()},
        "solutions": {k: m.label for k, m in reg.EFFICIENCY_MODES.items()},
        "ambiguous_terms": sorted(_AMBIGUOUS),
    }
