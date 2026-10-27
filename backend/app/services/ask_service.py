"""Ask Mosaic: a question in, a *governed scope* out - plan §E-1b, text-to-scope.

The division of labour this module enforces, and why it is drawn here:

  the model          proposes registry keys, and nothing else
  `semantics/scope`  decides whether the proposal stands
  Genie              answers the numbers, with the resolved scope as its grounding

The model never writes SQL, never names a table, and never picks between two metrics that share
a word. Its entire job is to map English onto a key space it is handed verbatim. Everything that
could produce a confident wrong number - choosing between Volume's `pct_mosaic` and Capacity's,
or reading adoption % as time utilization - happens in `scope.resolve()`, deterministically, in
code that a reviewer can read and a test can pin.

That ordering is the point. Text-to-SQL over this warehouse would be a machine for generating
plausible wrong answers in the most persuasive available format: prose, with a number in it. A
scope resolver can be wrong too, but it is wrong *visibly* - it names what it could not resolve
and what the alternatives were.

Degradation: every failure path returns a scope, not an error. If the model is unreachable the
keyword resolver still runs over the raw question, which handles the common shapes ("efficiency
by local region") without any model at all.
"""

from __future__ import annotations

import json
import re

from app.config import settings
from app.semantics import registry as reg
from app.semantics import scope as scope_mod
from app.services import ai_context_service

_PROPOSAL_SYSTEM = """You map a question about the Mosaic radiology reporting program onto a \
fixed set of metric keys. You do not answer the question and you do not write SQL.

Return ONLY a JSON object, no prose, no markdown fence, with these keys:
  "metrics":  array of metric keys from the list below (use the KEY, not the label)
  "group_by": array of dimension keys, or [] if the question asks for a single total
  "solution": one solution key, or "full_mosaic" if the question does not name one
  "entity":   the practice, team or radiologist named in the question, verbatim, or ""
  "period":   the time range named in the question, verbatim, or ""

Rules:
- Only use keys that appear in the lists. Never invent a key, and never return a label.
- If a word in the question matches more than one metric, return BOTH candidate keys. Do not \
pick. Returning two is how you signal ambiguity; a downstream validator asks the user.
- If nothing in the question maps to a metric, return "metrics": [].
"""

# Rebuilt per call from the registry rather than frozen into the prompt string: a metric added in
# Wave 3 becomes askable with no edit here, which is the same discipline as the alias tables.
def _vocabulary_block() -> str:
    v = scope_mod.vocabulary()
    return (
        "METRICS:\n"
        + "\n".join(f"  {k} = {label}" for k, label in v["metrics"].items())
        + "\n\nDIMENSIONS:\n"
        + "\n".join(f"  {k} = {label}" for k, label in v["dimensions"].items())
        + "\n\nSOLUTIONS:\n"
        + "\n".join(f"  {k} = {label}" for k, label in v["solutions"].items())
    )


def _extract_json(text: str) -> dict:
    """Models wrap JSON in fences, prose, or both. Take the outermost object and parse it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _keyword_proposal(question: str) -> dict:
    """The no-model fallback, and the floor the model is measured against.

    Scans the question for any alias the resolver already knows, longest first so "shift
    utilization" wins over "utilization" - which matters, because the longer phrase is
    unambiguous and the shorter one is the single worst ambiguity in this product.
    """
    text = scope_mod._slug(question)
    metrics, group_by, solution, solution_alias = [], [], "", ""

    def _already_covered(phrase: str) -> bool:
        """Is this phrase just a shorter way of saying something already matched?

        Compares in slug space on both sides, which is the whole point. `metrics` now holds a
        mix of registry keys (`capacity_pct_mosaic`, from the literal scan below) and alias
        phrases ("mosaic exams"), and a raw `in` between those two forms silently fails: the
        alias "pct mosaic" is not a substring of "capacity_pct_mosaic", so a question naming the
        capacity key outright also proposed the ambiguous phrase - and got refused for the one
        term it had been most precise about.
        """
        return any(phrase in scope_mod._slug(m) for m in metrics)
    # A literal registry key, matched against the *unslugged* question and before anything else.
    #
    # `_slug("pct_mosaic")` is "pct mosaic", which is exactly the colloquial phrase the ambiguity
    # table refuses. So slugging first made someone who typed the globally unique key
    # indistinguishable from someone who said the ambiguous words - and since the refusal's own
    # advice is "ask for `pct_mosaic` or `utilization_rpwu_pct` instead", taking that advice
    # produced the identical refusal. The alternatives were unreachable from the UI that offers
    # them. Matching the key before the alias table is what closes that loop.
    lowered = question.lower()
    for key in sorted(reg.METRICS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", lowered) and key not in metrics:
            metrics.append(key)
    for alias in sorted(scope_mod._METRIC_ALIASES, key=len, reverse=True):
        if alias and re.search(rf"\b{re.escape(alias)}\b", text):
            # Keep the alias itself, not its key: an ambiguous phrase must reach `resolve()` as a
            # phrase so it can be refused. Resolving it here would be picking.
            if scope_mod._METRIC_ALIASES[alias] in metrics:
                continue  # the key form was already matched above; the alias is the same ask
            # Longest-phrase-wins has to hold *across* the two tables, not just within this one.
            # "pct mosaic" is in both, so the containment check below already suppresses the
            # bare "mosaic" inside it - but "mosaic utilization" and "percent mosaic" are only
            # ambiguities, so nothing stopped "mosaic" from matching inside them and resolving
            # to `pct_mosaic`. The result was the worst possible shape: a scope that answers
            # "what is mosaic utilization" with adoption % *and* refuses the ambiguity beside
            # it. A question this module cannot answer must not come back with a number.
            if any(
                alias != phrase and alias in phrase and re.search(rf"\b{re.escape(phrase)}\b", text)
                for phrase in scope_mod._AMBIGUOUS
            ):
                continue
            if not _already_covered(alias):
                metrics.append(alias)
    # Three of the four solution names are also words inside metric names, so matching the
    # solution axis is not a plain scan. Two rules, both earned by a wrong reading:
    #
    #   skip a mode word that is part of a longer metric phrase - "drafting rate" is a metric,
    #   so "for capture" is what names the solution in a question containing both;
    #
    #   then, if the mode word also stands alone as a metric and something else was measured,
    #   drop it from the metrics - "drafting efficiency" asks one question, not two. A bare
    #   "how is drafting doing" keeps it, because adoption is the honest reading of that.
    for alias in sorted(scope_mod._MODE_ALIASES, key=len, reverse=True):
        if not alias or not re.search(rf"\b{re.escape(alias)}\b", text):
            continue
        if any(alias != m and alias in m for m in metrics):
            continue
        solution, solution_alias = scope_mod._MODE_ALIASES[alias], alias
        break
    if solution_alias in metrics and len(metrics) > 1:
        metrics.remove(solution_alias)
    for alias in sorted(scope_mod._AMBIGUOUS, key=len, reverse=True):
        # Same containment rule as above, and it is load-bearing here: "shift utilization" is
        # the disambiguated phrase, so finding bare "utilization" inside it and raising the
        # ambiguity anyway would refuse a question the user had already asked precisely.
        if not re.search(rf"\b{re.escape(alias)}\b", text) or _already_covered(alias):
            continue
        # Naming one of the candidates outright settles the ambiguity - that is what the refusal
        # asked the user to do. Raising it again against the answer to it would be a loop.
        if any(candidate in metrics for candidate in scope_mod._AMBIGUOUS[alias][1]):
            continue
        metrics.append(alias)
    for alias, key in scope_mod._DIM_ALIASES.items():
        if alias and re.search(rf"\b{re.escape(alias)}\b", text) and key not in group_by:
            group_by.append(key)
    return {"metrics": metrics[:4], "group_by": group_by[:2], "solution": solution}


def _entity_match(entity: str, forced: str = "") -> dict:
    """Decide *what kind of thing* the question named, against the deployed vocabulary.

    The resolver treats `entity` as an opaque string lifted from the question, which is right for
    a module that must stay pure - it has no roster to check against. But an unclassified entity
    is a real hazard here, for the reason the user has stated twice:

        Team     = provider_local_practice_name_curr = the radiologist's *home* practice
        Practice = managing_local_practice_name_curr = the *site* where the exam was read

    One radiologist belongs to exactly one Team and reads at as many as seventy Practices, so
    "how is Boca doing" is two different questions with two different numbers depending on which
    column answers it. Handing Genie the bare word lets Genie pick.

    Why this defaults instead of refusing
    -------------------------------------
    The first cut raised an ambiguity whenever a name appeared in both lists, by analogy with
    the metric ambiguities. Checked against the deployed vocabulary, that was wrong: 86 Practice
    names and 96 Team names overlap almost entirely, because an organisation is normally both a
    home practice and a site. Refusing on overlap would have fired on nearly every question
    anyone asks, and a clarifier that always fires is one people learn to click past.

    So the overlap case resolves to **Practice**, matching what the filter bar's own "Practice"
    dropdown means (`volume_service.py:171` builds it from `managing_local_practice_name_curr`),
    and reports `assumed: True` so the UI can show it as a stated, switchable default rather
    than a hidden one. `forced` is that switch coming back.

    An entity the vocabulary has never heard of is `kind: "unknown"` - passed through to Genie
    verbatim and unqualified, because inventing a column for a name we cannot place is the
    silent-wrong-number failure this whole module exists to avoid.
    """
    if not entity:
        return {"kind": "", "value": "", "candidates": [], "assumed": False}
    try:
        from app.services import cache_service

        options = cache_service.get_volume_filter_options()
        # Order is the preference order used when a name lands in more than one.
        buckets = {
            "practice": options.practices,
            "team": options.teams,
            "local_region": options.local_regions,
        }
    except Exception as exc:  # noqa: BLE001 - classification is an enhancement, never a gate
        print(f"[ask] entity vocabulary unavailable: {exc}", flush=True)
        return {"kind": "unknown", "value": entity, "candidates": [], "assumed": False}

    needle = entity.strip().lower()
    hits: list[dict] = []
    for kind, names in buckets.items():
        for name in names or ():
            if name and name.strip().lower() == needle:
                # The vocabulary's own casing, not the question's - "BOCA" asked about "Boca".
                hits.append({"kind": kind, "value": name})
                break
    if not hits:
        return {"kind": "unknown", "value": entity, "candidates": [], "assumed": False}
    chosen = next((h for h in hits if h["kind"] == forced), hits[0])
    return {
        **chosen,
        # Only the alternatives, and only when there are any: a single-list name has nothing to
        # switch to, and rendering a one-item chooser would imply a choice that does not exist.
        "candidates": hits if len(hits) > 1 else [],
        "assumed": len(hits) > 1 and not forced,
    }


def propose(question: str) -> tuple[dict, str]:
    """Ask the model for a key proposal. Returns (proposal, how) - `how` is reported to the
    caller so a degraded answer is visibly degraded rather than quietly worse."""
    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        response = ai_context_service._get_client().serving_endpoints.query(
            name=settings.ai_context_serving_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=_PROPOSAL_SYSTEM + "\n" + _vocabulary_block()),
                ChatMessage(role=ChatMessageRole.USER, content=question),
            ],
            max_tokens=800,
        )
        raw = ai_context_service._extract_text(response.choices[0].message.content)
        proposal = _extract_json(raw)
        if proposal.get("metrics"):
            return proposal, "model"
        # An empty proposal is not necessarily a model failure - the question may genuinely name
        # no metric. Fall through to keywords anyway; if they find nothing either, the refusal
        # that follows is well-founded rather than a timeout in disguise.
    except Exception as exc:  # noqa: BLE001 - a scope is still returned below
        print(f"[ask] proposal failed, falling back to keywords: {exc}", flush=True)
        return _keyword_proposal(question), "keywords (model unavailable)"
    return _keyword_proposal(question), "keywords"


def genie_prompt(question: str, spec: scope_mod.ScopeSpec, entity_match: dict | None = None) -> str:
    """The question Genie is actually asked, with the resolved scope bolted on.

    This is the whole reason to resolve before asking. Genie is a capable open-ended query
    engine over the same warehouse, which means it is equally capable of dividing by the wrong
    denominator. Handing it the governed definitions - including the two that share the name
    `pct_mosaic` - converts an open question into a constrained one.
    """
    lines = [question.strip(), "", "Use these governed definitions. Do not substitute your own:"]
    for key in spec.metrics:
        m = reg.get_metric(key)
        lines.append(f"- {m.label} ({m.output_name}): {m.definition} Grain: {m.grain}.")
        for c in m.caveats:
            lines.append(f"    caveat: {c}")
    if spec.group_by:
        lines.append("")
        for dk in spec.group_by:
            d = reg.get_dimension(dk)
            lines.append(f"- Group by {d.label}: {d.note}")
    for f in reg.required_filters(list(spec.group_by)):
        lines.append(f"- Required filter: {f}")
    if spec.solution != "full_mosaic":
        mode = reg.EFFICIENCY_MODES[spec.solution]
        lines.append(f"- Restrict to the {mode.label} solution: {mode.description}")
    if spec.entity:
        # Name the *column*, not just the value, whenever the vocabulary placed one. "Boca"
        # alone leaves Genie to choose between the radiologist's home practice and the site the
        # exam was read at; those are different populations and different numbers. A name the
        # vocabulary has never seen goes through unqualified on purpose - picking a column for a
        # name we cannot place would be a guess invisible in the answer.
        kind = (entity_match or {}).get("kind")
        dim = reg.DIMENSIONS.get(kind) if kind else None
        if dim:
            # The column name only when it *is* a column. `local_region` is a fifty-line CASE
            # over the Team list, and pasting that into a prompt buries the instruction it is
            # meant to sharpen; the governed note carries the same meaning in one sentence.
            sql = dim.sql.strip()
            qualifier = f" ({sql})" if sql.isidentifier() else ""
            lines.append(f"- Restrict to {dim.label}{qualifier} = {spec.entity}")
            lines.append(f"    {dim.note}")
        else:
            lines.append(f"- Restrict to: {spec.entity}")
    if spec.period:
        lines.append(f"- Period: {spec.period}")
    for n in spec.notes:
        lines.append(f"- {n}")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------
# Action intent - the question this module structurally cannot resolve to a scope
# --------------------------------------------------------------------------------------------
#
# "Where should we focus next week" is the question the operators running Mosaic actually ask,
# and it is the one shape text-to-scope has no answer for. A scope names *what to measure*; this
# question asks *which row to work*, which is a ranking over a computed worklist rather than a
# slice of a cube. Pushed through the resolver unchanged it degrades badly but quietly: "focus"
# and "next" match no alias, so the scope comes back empty, the UI reports it cannot answer, and
# the governed ranking that answers it exactly sits one module away, already computed.
#
# So the worklist is attached *alongside* the scope, never instead of it. A question can carry
# both intents - "where should we focus on drafting in Boca" has a real scope and a real action
# answer - and dropping either half to serve the other would be the same mistake in the other
# direction. `needs_clarification` is likewise left to the scope resolver: an action answer does
# not make an ambiguous metric unambiguous.
_ACTION_INTENT = re.compile(
    r"\b("
    r"where (should|do|can|would) (we|i|they)"
    r"|what should (we|i|they) (do|work|focus|prioriti[sz]e|tackle)"
    r"|next best action|worklist|work list"
    # Every alternative has to be a *whole* word: the group closes on `\b`, so a prefix like
    # `opportunit` never matches - the "y" that follows it is a word character and the boundary
    # fails. The pattern reads as though it matches "biggest opportunity" and silently does not.
    r"|(biggest|best|largest|highest|top) (opportunit(y|ies)|unlocks?|upside|wins?|levers?)"
    r"|(who|which) (team|practice|teams|practices) (should|to) (we|i|be)"
    # Verb forms only. "priority" and "priorities" are ordinary nouns in measurement language -
    # "how many rads are in the priority tier" is a count question, and matching it here would
    # attach a ranked worklist to it. Someone who means the action asks us to *prioritise*.
    r"|prioriti[sz]e[sd]?|prioriti[sz]ing"
    r"|focus (on|next|our|this|where)"
    r"|most (impact|upside|opportunity)"
    r")\b",
    re.IGNORECASE,
)

# How many ranked rows ride along on an answer. The panel ships 25; a chat reply is read, not
# scanned, and a list long enough to need scrolling stops being a recommendation.
_ASK_WORKLIST_LIMIT = 5


def _worklist_for(entity: str, entity_match: dict) -> dict | None:
    """The governed ranking, narrowed to the named entity when one was placed.

    Returns `None` rather than an empty payload when the question carried no action intent or
    the cache is cold - the caller omits the key entirely in that case, so a surface can tell
    "no action answer" from "no actions to take", which are different things to show a user.
    """
    try:
        from app.services import cache_service
    except Exception as exc:  # pragma: no cover - import-time failure, not a data condition
        print(f"[ask] worklist unavailable: {exc}", flush=True)
        return None

    try:
        ranked = cache_service.get_next_best_actions(limit=_ASK_WORKLIST_LIMIT)
    except Exception as exc:
        # A cold cache is the ordinary case on a fresh process, not an error worth failing the
        # whole answer over. The scope half of the response is still useful without this.
        print(f"[ask] worklist unavailable: {exc}", flush=True)
        return None

    rows = [a.model_dump() for a in ranked.actions]

    # Narrowed only when the vocabulary placed the name as a *Team*. The worklist's `team` column
    # is `provider_local_practice_name_curr` - the radiologist's home practice - and filtering it
    # by a name the user meant as a Practice (the site the exam was read at) would return an
    # empty list that looks like "nothing to do here" rather than "wrong column". When the name
    # is a Practice the full ranking is returned unfiltered, with `scoped_to` left empty so the
    # surface can say which it did.
    scoped_to = ""
    if entity and entity_match.get("kind") == "team":
        matched = [r for r in rows if scope_mod._slug(r["team"]) == scope_mod._slug(entity)]
        if matched:
            rows, scoped_to = matched, entity

    return {
        "scoped_to": scoped_to,
        "actions": rows,
        # Verbatim from the ranking, never re-worded here. It carries the live benchmark, team
        # count and window, and it is the same string the worklist panel prints - a second
        # rendering is how the chat answer and the screen end up describing different rankings.
        "basis": ranked.basis,
        "benchmark_draft_rate": ranked.benchmark_draft_rate,
        "window_start": ranked.window_start,
        "window_end": ranked.window_end,
    }


def ask(question: str, page_scope: dict | None = None) -> dict:
    """Resolve a question to a governed scope.

    `page_scope` is whatever the surface the user is standing on already has filtered - it seeds
    entity and solution so "how are we doing" means something on a page about one practice.
    Explicit terms in the question always win over it; the page is a default, not an override.
    """
    proposal, how = propose(question)
    page_scope = page_scope or {}
    for field in ("entity", "period", "solution"):
        if not proposal.get(field) and page_scope.get(field):
            proposal[field] = page_scope[field]

    spec = scope_mod.resolve(proposal)
    # `entity_kind` is the Team/Practice switch coming back from the UI, not something the
    # question said. It rides in on `page_scope` rather than a new field because it is scope the
    # surface is carrying, which is exactly what `page_scope` already means.
    entity_match = _entity_match(spec.entity, str(page_scope.get("entity_kind") or ""))

    # Intent is read off the raw question, not off the proposal. The model is instructed to
    # return metric keys and nothing else, so an action question produces an *empty* proposal -
    # there is nothing in its output to detect intent from. Reading the user's own words is the
    # only place the signal survives.
    worklist = _worklist_for(spec.entity, entity_match) if _ACTION_INTENT.search(question) else None

    result = {
        "question": question,
        "resolved_by": how,
        "scope": spec.as_dict(),
        # What kind of thing the named entity is - Team, Practice, Local Region, or unknown.
        # Separate from `scope` because the resolver cannot know it: `semantics` holds no roster
        # and makes no network call, which is what lets its tests run offline.
        "entity_match": entity_match,
        # Present even when unanswerable, so the UI can show what *would* have been sent. An
        # empty-metric scope produces a prompt with no definitions, which is exactly the
        # ungoverned question we are refusing to ask.
        "genie_prompt": genie_prompt(question, spec, entity_match) if spec.is_answerable else "",
        # Note what is deliberately *not* here: `entity_match["assumed"]`. A metric ambiguity
        # blocks because there is no defensible default - adoption % and time utilization are
        # different questions. The Team/Practice default is defensible (it is the same column
        # the filter bar means) and is shown on the answer with one click to the other, so
        # blocking on it would stop nearly every question for a choice the user can already see.
        "needs_clarification": bool(spec.refusals) or not spec.is_answerable,
    }
    # Omitted entirely rather than sent as null when there is no action intent. A surface that
    # reads `"worklist" in response` can distinguish "this was not that kind of question" from
    # "this was, and there is nothing to work" - and the second of those is a real answer.
    if worklist is not None:
        result["worklist"] = worklist
    return result
