"""Live, LLM-generated "what does this mean" explanations for a hovered data point - the one
new reusable primitive behind both the MVP and Capacity tabs' AiHoverCard component. Confirmed
via `databricks serving-endpoints query databricks-claude-haiku-5-5` that the configured
Foundation Model API endpoint speaks the standard OpenAI-style chat-completion shape
(`response.choices[0].message.content`), same shape the databricks-sdk's
`serving_endpoints.query(messages=[...])` returns.

This is decorative context, not load-bearing data: every call is wrapped so a cold-start,
timeout, or quota error degrades to a short static fallback string instead of a 500 - a failed
hover explanation should never be visible as an error to the end user.
"""
import threading
from typing import Sequence

from app.config import settings
from app.data import mvp_context, mvp_dashboard_stats, mvp_mentor_matching
from app.semantics import registry
# Safe to import at module scope: both are pure Python over dicts with no cache, network or
# Pydantic import, deliberately so (see their module docstrings - `movers_service` imports
# nothing but `typing`). Nothing here imports back into this module, so there is no cycle to
# create.
from app.services import movers_service, next_best_action_service

# Both of these are declared in app/semantics/registry.py and imported, not re-typed. The
# fallback string was independently hardcoded in AIHoverCard.tsx, and the coverage caveat below
# existed here, in mosaic_service's threshold, and again as a TSX string literal - the registry
# exists to end exactly that. The import direction is one-way: registry imports from the service
# modules, so nothing in registry may import this module back.
_FALLBACK = registry.AI_FALLBACK_TEXT

# Read-time coverage governs both Utilization and Efficiency, so it is appended to both
# methodologies rather than paraphrased twice. Leading space because it is concatenated onto the
# end of a sentence below; the registry stores the canonical text without it.
_READ_TIME_COVERAGE_CAVEAT = " " + registry.READ_TIME_COVERAGE.caveat

_CAPACITY_METHODOLOGY = (
    "Capacity = TBWU/hour scheduled. Baseline Capacity comes from each radiologist's own "
    "pre-Mosaic history for that shift type (edw_dev.bipa_analytics.stg_mosaic_baseline_master); "
    "when a shift type has no history of its own, a similar shift type's rate is borrowed as a "
    "'Proxy' baseline, scored across subspecialty, modality, TBWU, duration, location, and "
    "weekday/weekend match. 'No baseline' means neither an exact nor a confident proxy match "
    "exists for that practice/radiologist yet. Additional Capacity % is only shown when a "
    "practice has decent baseline coverage - low-coverage practices intentionally show '—' "
    "instead of a number computed from too little real history to trust."
) + _READ_TIME_COVERAGE_CAVEAT

_ADOPTION_ROLLOUT = (
    "This is Radiology Partners' enterprise rollout of Mosaic, RP's AI-assisted radiology "
    "reporting platform. Rollout has three independent tracks that can each be at a different "
    "stage for the same radiologist/practice: Reporting (RPCE - the core AI reporting engine), "
    "Drafting (AI drafts a structured report the radiologist edits, per exam type: XR, CT Head, "
    "CT Abd/Pel, CT Chest), and Capture (AI pulls structured findings from tech worksheets for "
    "US/DEXA exams). A radiologist or practice can be 'fully on RPCE' (all tracks live), 'split "
    "integration' (some tracks live, others not), or 'not on RPCE' at all. Enablement for a "
    "given track requires training completion, IRB/drafting consent, and being added to that "
    "model's AD group - a radiologist can be blocked at any one of those steps."
)

_EFFICIENCY_METHODOLOGY = (
    "Efficiency here means TBWU (total billed work units) per minute of dictation/review time - "
    "higher is better, more value produced per minute spent. It's compared against each "
    "radiologist's own pre-Mosaic baseline rate for the same exam type, never against another "
    "radiologist's rate, since case mix and speed vary enormously by subspecialty. Utilization is "
    "the fraction of scheduled shift time actually spent reading exams. Additional capacity per "
    "shift is the gap between a radiologist's actual throughput and what their baseline implies "
    "they could produce in the same shift - a positive number means Mosaic is freeing up capacity, "
    "a negative number means something (technical friction, a new workflow habit, case-mix shift) "
    "is currently costing them time versus their own pre-Mosaic history."
) + _READ_TIME_COVERAGE_CAVEAT

_BASELINE_REVIEW_METHODOLOGY = (
    "This is a human-in-the-loop review queue for the Capacity tab's baseline-matching algorithm. "
    "When a radiologist worked a shift type too rarely before Mosaic to have its own reliable "
    "baseline rate, the algorithm looks for a different shift type that SAME radiologist worked "
    "often enough pre-Mosaic, and borrows that rate as a 'proxy' - scored across subspecialty "
    "overlap, modality mix, TBWU/exam, shift duration, location (onsite/remote), weekday/weekend "
    "pattern, and time of day. A total score below 40 lands here for manual review rather than "
    "being auto-accepted, since borrowing a weakly-matched shift's rate would produce a "
    "misleading baseline comparison. A human picks the best candidate, overrides to a different "
    "one, or marks 'no good match' if none of the candidates are close enough to trust."
)

_SENTIMENT_METHODOLOGY = (
    "This is radiologist sentiment toward Mosaic, drawn from direct feedback (survey responses "
    "or live submitted comments), not usage/efficiency metrics. NPS (Net Promoter Score) is "
    "promoters minus detractors as a percentage of respondents, on a standard 0-10 "
    "likely-to-recommend question - negative NPS is common in enterprise software rollouts "
    "generally and doesn't by itself mean adoption is failing; it should be read alongside the "
    "actual usage and efficiency numbers, not in isolation."
)

# Read-time gated in the registry, and deliberately NOT carrying `_READ_TIME_COVERAGE_CAVEAT`.
#
# That text promises suppression - "below 75% Utilization is suppressed and shows '-'" - and on
# this surface the promise is false. `tbl_shift_utilization` (tools/edw_fixes/014) carries no
# coverage column, so the floor is declared and unenforced here; see the comment beside
# `FEATURE_COVERAGE["shift_utilization"]` in the registry. Pasting the shared caveat in would put
# a guarantee into the prompt that the data does not keep, and the model would then read a low
# number as certainly real *because* it believed the untrustworthy ones had been withheld. That
# is a worse failure than silence: it is confident, specific, and wrong.
#
# So: the same facts, the opposite enforcement status, composed from the same registry fields so
# the threshold is stated in one place and cannot drift between the two paragraphs.
_SHIFT_UTILIZATION_COVERAGE_CAVEAT = (
    " One caveat specific to this surface. The numerator is read time, derived from dictation "
    "timestamps, and those timestamps are missing for a large share of exams at some practices; "
    "covered-only read minutes over full scheduled hours understates utilization by roughly the "
    f"coverage fraction. Elsewhere in Mosaic a {registry.READ_TIME_COVERAGE.min_ratio:.0%} floor "
    f"on {registry.READ_TIME_COVERAGE.measured_by} suppresses such a number rather than show it "
    "wrong in a knowable direction, but that floor is not enforced on this lineage - it has no "
    "coverage column - so every value here renders, including ones built from almost no read "
    "time. Treat a low figure as a question about instrumentation first and radiologist "
    "behaviour second, and never imply the untrustworthy ones were filtered out."
)

_SHIFT_UTILIZATION_METHODOLOGY = (
    "Shift utilization is reading-time divided by scheduled shift duration, sourced from RP's own "
    "shift-timeline data (the same source powering their Deneb shift visualizations) - it answers "
    "how much of a scheduled shift was actually spent reading, not how productive each minute was. "
    "% Mosaic read and % AI drafted are computed separately, over that same shift's exams: the "
    "first is any exam read on the Mosaic platform, the second is the subset where AI produced the "
    "draft report the radiologist reviewed and signed off - drafting is always a subset of Mosaic "
    "reads, never larger. Low utilization on a given shift can reflect light exam volume, schedule "
    "gaps, or non-reading duties, not necessarily underperformance."
) + _SHIFT_UTILIZATION_COVERAGE_CAVEAT

_MVP_STATUS_FUNNEL_METHODOLOGY = (
    "This funnel mirrors the real MVP Weekly Update report sent to leadership: each radiologist "
    "signaling Drafting/Capture or Mammo-screening efficiency loss moves through Outreached -> "
    "Scheduled -> Solutioning -> Monitoring -> Closed, tracked via the program's own "
    "mosaic_optimization_support_status field. 'Escalated' means the case needed extra help "
    "(from Mentorship, IT, or the product/Development team) beyond standard outreach; within "
    "Closed, the on-track/declined split is whether the case resolved (optimization complete) "
    "or the radiologist/practice declined support partway through."
)

_MVP_IMPACT_METHODOLOGY = (
    "This compares each radiologist's fixed May-Jul 2026 baseline efficiency change against "
    "their current rolling 30-day figure, for radiologists who've reached Solutioning or later "
    "(genuinely 'post-engagement', not just identified). At/above baseline means they're now at "
    "or better than their own pre-engagement baseline; Improving Towards Baseline means still "
    "negative but better than before; Not Improving means flat or worse; insufficient data means "
    "one of the two figures isn't available yet to compare."
)

_MVP_WEEKLY_TREND_METHODOLOGY = (
    "This is an approximation, not an exact engagement-date log: rad_onboarding has no "
    "stage-transition history, so this buckets radiologists by the week their optimization case "
    "was last touched (optimization_last_updated) as a proxy for when they became engaged. "
    "Treat the shape (declining 'to be engaged', growing 'engaged') as directionally real, not "
    "the exact week-by-week counts the published weekly report would show."
)

_MAMMO_SCREENING_TREND_METHODOLOGY = (
    "Screening volume and efficiency change for Mammo Screening exams specifically (not "
    "Diagnostic Mammo) - identified via the procedure description carrying 'SCREENING' wording. "
    "Efficiency change combines Reporting and Drafting into one Full-Mosaic-style figure versus "
    "each radiologist's own baseline, since Mammo Screening isn't otherwise split by reporting-"
    "vs-drafting anywhere else in this app."
)

_MVP_PRIORITY_METHODOLOGY = (
    "Priority tiers here are a derived approximation of the MVP methodology deck's own "
    "qualitative Priority 1/2/3 definitions, computed live from rad_onboarding figures since the "
    "deck's exact formula was never codified: Priority 1 = baseline capacity in the top third of "
    "the active cohort (a stand-in for 'high productivity') combined with a less-than-5% overall "
    "Drafting/Capture efficiency change; Priority 2 = the same efficiency condition at average "
    "(non-top-third) capacity; Priority 3 = a very negative change on one specific exam-prep "
    "program (XR/CT Head Drafting below -20%, or US Capture below -37%, the same magnitudes "
    "cited in the program's own narrative) even when the combined Drafting/Capture number looks "
    "fine. This is an approximation of RP's own tiers, not their literal formula - treat it as "
    "directional, not authoritative."
)

_MVP_MENTOR_MATCH_METHODOLOGY = (
    mvp_context.MENTORSHIP_PROGRAM_SUMMARY + " " + mvp_mentor_matching.PEER_COACH_QUALIFICATION_THRESHOLDS
)

_NON_DRAFTED_METHODOLOGY = (
    "This breaks down exams that were eligible for AI drafting but weren't actually drafted, by "
    "reason. 'Rad declined' means the radiologist chose not to use the draft for that specific "
    "exam (a real, logged choice, not a system failure). 'Incomplete process' covers radiologists "
    "who've signed drafting consent but haven't yet been added to that exam type's AD group - an "
    "enablement-pipeline gap, not a radiologist decision. Other reasons reflect technical or "
    "eligibility constraints (exam type, practice program status, etc.) rather than a choice by "
    "anyone."
)

_VOLUME_COUNTS_METHODOLOGY = (
    "The exam counts on this surface are enterprise-wide and unfiltered - the summary query runs "
    "with no WHERE clause, so the practice/region filters on the page govern the table below "
    "them, not the headline tiles. The two Mosaic flags overlap and must never be added "
    "together: an exam that got an AI draft is also a Mosaic read, so Mosaic and Drafting counts "
    "are nested subsets of the exam total, not slices of a pie. The three grouping cuts answer "
    "genuinely different questions - 'By Practice' groups on the managing practice, the site "
    "where the exam was actually read; 'By Team' groups on the reading radiologist's own home or "
    "float-pool practice (SEAL Team, for instance, is a cross-coverage pool rather than a "
    "billing practice); and 'By Local Region' rolls up one of six fixed regions keyed on that "
    "home Team, so a radiologist covering a site outside their own region still counts under "
    "their home region. The same radiologist therefore appears under one Team and potentially "
    "many Practices. These counts use the same measure SQL as the governed "
    "mosaic_volume_metric_view, so a company-wide total here reconciles with the dashboard's by "
    "construction rather than by coincidence."
)

_VOLUME_RPCE_METHODOLOGY = (
    "The RPCE percentages are not comparable to the adoption percentage beside them, because "
    "they do not share a denominator. Their denominator is exams from exactly two source "
    "systems, rpceMidwest and rpceSouthwest, while the numerator counts Mosaic reads (or AI "
    "drafts) across every source system - which is why the figure can legitimately exceed 100% "
    "wherever Mosaic activity exists outside those two systems. Both measures also carry a flat "
    "+2 percentage point adjustment inherited from the source DAX model; it was raised with the "
    "business owner and confirmed as an intentional, known adjustment to retain rather than a "
    "leftover hack, and it is still applied in the SQL behind these tiles. Treat these as "
    "source-system penetration measures for the two RPCE regions, not as an enterprise adoption "
    "rate."
)

# feature -> grounding text injected into the system prompt, so the model explains using RP's
# actual program language instead of guessing. Keep each entry short - this is prompt context
# for a one-paragraph tooltip, not a document to summarize.
#
# Measured and rejected: retiring these constants in favour of `registry.grounding_for()`.
# The plan called for it ("retire the 13 `_*_METHODOLOGY` constants"), so it was tested rather
# than assumed - every key below was split into sentences, normalized, and intersected with the
# registry's output for the same key. The overlap is **zero sentences on all 24 keys**. The two
# sources answer different questions: the registry says what a metric *is* (label, definition,
# caveats), these say why it is computed that way, which table it comes from, and what a reader
# will otherwise misread. `_grounding_for()` below therefore concatenates them deliberately -
# see its docstring. Two further reasons a grep-driven pass would get this wrong:
#   - Five keys get `""` back from the registry (`baseline_review_match`, `capacity_additional_pct`,
#     `mvp_notes_summary`, `non_drafted_reason`, `sentiment`), so the constant is their *only*
#     grounding. Four are in `UNREGISTERED_FEATURES`; `capacity_additional_pct` is coverage-only
#     until Wave 3 lands Deployment.
#   - `_ADOPTION_ROLLOUT` is a grounding constant that does not end in `_METHODOLOGY`, so a sweep
#     over `_*_METHODOLOGY` silently drops it while appearing complete.
# The real prompt-budget problem was inside `registry.grounding_for()`, which re-emitted shared
# caveats once per metric; that is fixed there, not here.
_FEATURE_GROUNDING: dict[str, str] = {
    "mvp_cohort": mvp_context.PROGRAM_NARRATIVE,
    "mvp_exclusion": mvp_context.PROGRAM_NARRATIVE,
    "mvp_capacity": mvp_context.PROGRAM_NARRATIVE,
    "mvp_efficiency_change": mvp_context.PROGRAM_NARRATIVE,
    "mvp_priority": _MVP_PRIORITY_METHODOLOGY,
    "mvp_notes_summary": mvp_context.PROGRAM_NARRATIVE,
    "mvp_mentor_match": _MVP_MENTOR_MATCH_METHODOLOGY,
    "mvp_status_funnel": _MVP_STATUS_FUNNEL_METHODOLOGY,
    "mvp_impact": _MVP_IMPACT_METHODOLOGY,
    "mvp_weekly_trend": _MVP_WEEKLY_TREND_METHODOLOGY,
    "mammo_screening_trend": _MAMMO_SCREENING_TREND_METHODOLOGY,
    "capacity_coverage": _CAPACITY_METHODOLOGY,
    "capacity_additional_pct": _CAPACITY_METHODOLOGY,
    "capacity_figure": _CAPACITY_METHODOLOGY,
    "adoption_rollout": _ADOPTION_ROLLOUT,
    # Utilization's two volume keys. `adoption_rollout` sits between them on the same KPI row and
    # is reused rather than duplicated - it already explains the rollout tracks these percentages
    # measure. What it does not explain is what is inside the counts, or why the RPCE denominator
    # is a different one, so those get their own keys rather than being folded into it.
    "volume_counts": _VOLUME_COUNTS_METHODOLOGY,
    "volume_rpce": _VOLUME_RPCE_METHODOLOGY,
    "efficiency_metric": _EFFICIENCY_METHODOLOGY,
    "baseline_review_match": _BASELINE_REVIEW_METHODOLOGY,
    "sentiment": _SENTIMENT_METHODOLOGY,
    "non_drafted_reason": _NON_DRAFTED_METHODOLOGY,
    "shift_utilization": _SHIFT_UTILIZATION_METHODOLOGY,
    # The worklist rows reused `non_drafted_reason`, which is the right grounding for *what the
    # six categories mean* and the wrong grounding for *why this team is ranked first*. The
    # expected-unlock figure is the one number on that page someone will challenge out loud, and
    # it was the one with no methodology behind it: the model would have explained the leakage
    # taxonomy and said nothing about the peer frontier the ranking rests on.
    #
    # Imported, not restated - `next_best_action_service.METHODOLOGY` is the same string the
    # live `basis` field is built around, so the tooltip and the response cannot describe
    # different rankings.
    "next_best_action": _NON_DRAFTED_METHODOLOGY + "\n\n" + next_best_action_service.METHODOLOGY,
    # Same two-part shape, for the same reason. `_EFFICIENCY_METHODOLOGY` says what the rate is;
    # `movers_service.METHODOLOGY` says what the *split* of a difference between two rates means,
    # and without it the model has no way to know that mix and rate are the two halves of an exact
    # identity rather than two independent estimates it should hedge against each other.
    #
    # The prefix is `_EFFICIENCY_METHODOLOGY` specifically, not a new constant: it already ends
    # with the read-time coverage caveat imported from the registry, so `efficiency_movers` being
    # declared in `FEATURE_COVERAGE` resolves to exactly one copy of that text in the prompt -
    # which is what `test_the_coverage_caveat_reaches_the_prompt_exactly_once` requires.
    "efficiency_movers": _EFFICIENCY_METHODOLOGY + "\n\n" + movers_service.METHODOLOGY,
}


def _grounding_for(feature: str) -> str:
    """Registry metric definitions first, then this module's program narrative.

    Additive, not a replacement, because the two carry different things. The registry knows what
    `% Mosaic` *is* (exam-count adoption, not time utilization - the conflation this product has
    actually shipped); the constants above carry program narrative with no metric equivalent, and
    six of the keys are pure MVP program context from `mvp_context`. Swapping one for the other
    in either direction deletes real content.

    `registry.grounding_for` deliberately omits the coverage caveat so this stays single-copy:
    `_CAPACITY_METHODOLOGY` and `_EFFICIENCY_METHODOLOGY` already end with it, from the same
    registry string.
    """
    parts = [registry.grounding_for(feature), _FEATURE_GROUNDING.get(feature, "")]
    return " ".join(p for p in parts if p)


_lock = threading.Lock()
_cache: dict[tuple, str] = {}
_client = None


def _get_client():
    global _client
    if _client is None:
        from databricks.sdk import WorkspaceClient

        if settings.in_databricks_app:
            # Same auto-detect as app.db.databricks_client - DATABRICKS_CLIENT_ID/_SECRET are
            # injected into the app's runtime automatically.
            _client = WorkspaceClient()
        else:
            from databricks.sdk.core import Config

            _client = WorkspaceClient(
                config=Config(
                    host=f"https://{settings.databricks_server_hostname}",
                    token=settings.databricks_token,
                )
            )
    return _client


def _extract_text(content) -> str:
    """Handles both response shapes confirmed live from this endpoint: a plain string for
    simple prompts, or a list of content blocks (a "reasoning" block plus a "text" block) when
    the model's extended-thinking mode kicks in on a more complex prompt."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    return ""


def explain_data_point(
    feature: str, entity_label: str, metric_label: str, value: str, extra: dict[str, str] | None = None
) -> str:
    """Returns a short (2-3 sentence) plain-language explanation of one data point, generated
    live by the configured Foundation Model endpoint. Cached in-process (process-lifetime only -
    resets on redeploy, which is fine, regenerating is cheap) keyed by the exact inputs, so
    repeat hovers of the same cell across any user's session are instant after the first."""
    extra = extra or {}
    cache_key = (feature, entity_label, metric_label, value, tuple(sorted(extra.items())))

    with _lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        grounding = _grounding_for(feature)
        extra_lines = "\n".join(f"- {k}: {v}" for k, v in extra.items())
        if feature == "mvp_notes_summary":
            # `value` carries the full raw case-note text here (not a metric reading) - a
            # summarization prompt, not the generic "explain this data point" framing below.
            system_prompt = (
                "You summarize a radiologist's chronological case-note history from an internal "
                "MVP (Mosaic Value Project) optimization program, for the person opening their "
                "record. Name the actual blockers, sessions, and outcomes mentioned, in the "
                "order they happened. 2-4 sentences maximum, plain language, no markdown, no "
                "preamble like 'Here is a summary'. "
                f"Program context: {grounding}"
            )
            user_prompt = (
                f"Radiologist: {entity_label}.\nRaw case notes (chronological):\n{value}\n\n"
                "Summarize the engagement history: what's been tried, the current blocker, and "
                "where things stand now."
            )
        else:
            system_prompt = (
                "You explain one data point from an internal radiology-practice analytics "
                "dashboard to the person hovering over it. Be concrete and specific to the actual "
                "numbers given - never generic. 2-3 sentences maximum, plain language, no "
                "markdown, no bullet points, no preamble like 'This shows...'. "
                f"Program context: {grounding}"
            )
            user_prompt = (
                f"Data point: {metric_label} = {value}, for {entity_label}.\n"
                + (extra_lines and f"Additional context:\n{extra_lines}\n")
                + "Explain what this number means and why it might look the way it does."
            )

        response = _get_client().serving_endpoints.query(
            name=settings.ai_context_serving_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=ChatMessageRole.USER, content=user_prompt),
            ],
            # Confirmed live: this endpoint defaults to extended-thinking mode on non-trivial
            # prompts, returning `content` as a list of blocks (a "reasoning" block with an
            # empty summary, then a "text" block with the real answer) instead of a plain
            # string - 200 tokens was consumed entirely by the reasoning block, leaving no
            # budget for the actual text. 800 leaves enough room for both.
            max_tokens=800,
        )
        explanation = (_extract_text(response.choices[0].message.content) or "").strip() or _FALLBACK
    except Exception as exc:  # noqa: BLE001 - decorative context, must never surface as a 500
        print(f"[ai-context] explain_data_point failed for {feature}/{entity_label}/{metric_label}: {exc}", flush=True)
        explanation = _FALLBACK

    with _lock:
        _cache[cache_key] = explanation
    return explanation


def _to_float(value) -> float | None:
    """The raw rad_onboarding dicts this module reads straight from cache_store (bypassing
    Pydantic's usual lax-mode string->float coercion) mix numeric and string representations of
    the same column across rows - confirmed live (e.g. drafting_captured_efficiency_change_pct
    arriving as a plain str for some rows) - so every numeric read here needs an explicit,
    failure-safe conversion rather than assuming a Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _priority_tier_counts(rows: list[dict]) -> dict[str, int]:
    """Mirrors Mvp.tsx's client-side computePriorities() exactly - kept in sync by hand since
    there's no shared code between the frontend and backend runtimes (see the matching comment
    there if either ever changes). Used only to ground the precomputed program narrative below in
    real counts; the authoritative per-radiologist Priority badge is still computed client-side."""
    active = [r for r in rows if not r.get("exclusion_reason") and _to_float(r.get("baseline_capacity_tbwu_9h")) is not None]
    ranked = sorted(active, key=lambda r: _to_float(r["baseline_capacity_tbwu_9h"]), reverse=True)
    high_cutoff = -(-len(ranked) // 3)  # ceil(len/3)
    high_npis = {r["npi"] for r in ranked[:high_cutoff]}

    counts = {"Priority 1": 0, "Priority 2": 0, "Priority 3": 0}
    for r in active:
        is_high = r["npi"] in high_npis
        dc = _to_float(r.get("drafting_captured_efficiency_change_pct"))
        low_or_negative_dc = dc is not None and dc < 5
        very_negative_modality = any(
            _to_float(r.get(key)) is not None and _to_float(r.get(key)) < threshold
            for key, threshold in (
                ("xr_drafting_efficiency_change_pct", -20),
                ("ct_head_efficiency_change_pct", -20),
                ("us_capture_efficiency_change_pct", -37),
            )
        )
        if is_high and low_or_negative_dc:
            counts["Priority 1"] += 1
        elif not is_high and low_or_negative_dc:
            counts["Priority 2"] += 1
        elif very_negative_modality:
            counts["Priority 3"] += 1
    return counts


def generate_mvp_program_narrative(rows: list[dict]) -> str:
    """Precomputed (not on-hover) "state of the program this week" paragraph - generated once per
    refresh cycle (see refresh_service.DATASETS), never on page load, so the MVP tab never blocks
    on a live LLM call. Falls back to the static CURRENT_STATUS_NOTES text if generation fails,
    same fail-closed contract as explain_data_point but at refresh-cycle granularity."""
    active = [r for r in rows if not r.get("exclusion_reason")]
    excluded = len(rows) - len(active)
    cohort_counts: dict[str, int] = {}
    for r in active:
        cohort = r.get("mvp_cohort")
        if cohort:
            cohort_counts[cohort] = cohort_counts.get(cohort, 0) + 1
    tiers = _priority_tier_counts(rows)

    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        system_prompt = (
            "You write a short 'state of the program this week' paragraph for an internal "
            "radiology-practice leadership dashboard, about the Mosaic Value Project (MVP) "
            "radiologist-engagement program. Be concrete and specific to the real numbers given "
            "below - never generic filler. 3-5 sentences maximum, plain language, no markdown, "
            "no bullet points, no preamble like 'Here is a summary'. "
            f"Program background: {mvp_context.PROGRAM_NARRATIVE} "
            f"Program history: {mvp_context.PROGRAM_HISTORY} "
            f"Latest weekly update from the program team: {mvp_context.LATEST_WEEKLY_NARRATIVE}"
        )
        user_prompt = (
            f"Current live counts from the tracking system: {len(active)} actively tracked "
            f"radiologists, {excluded} excluded from engagement, cohort breakdown "
            f"{cohort_counts}, and this session's derived priority distribution {tiers} (see "
            "program background for what the tiers mean).\n"
            "Write the paragraph summarizing where the program stands right now."
        )
        response = _get_client().serving_endpoints.query(
            name=settings.ai_context_serving_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=ChatMessageRole.USER, content=user_prompt),
            ],
            # This prompt (long grounding text + a 3-5 sentence ask) is meaningfully heavier than
            # explain_data_point's single-data-point tooltip, for which 800 was confirmed enough -
            # confirmed live this session that 800 here gets entirely consumed by this endpoint's
            # extended-thinking "reasoning" block, leaving nothing for the actual text block (no
            # exception raised, just an empty string - silently falls through to the static
            # fallback below, which is correct behavior but not what we want when the model is
            # perfectly capable of answering given enough room).
            max_tokens=2000,
        )
        text = (_extract_text(response.choices[0].message.content) or "").strip()
        if not text:
            print("[ai-context] generate_mvp_program_narrative: empty text from model response, using fallback", flush=True)
        return text or mvp_context.CURRENT_STATUS_NOTES
    except Exception as exc:  # noqa: BLE001 - must never break the refresh cycle
        print(f"[ai-context] generate_mvp_program_narrative failed: {exc}", flush=True)
        return mvp_context.CURRENT_STATUS_NOTES


_MVP_DASHBOARD_FALLBACK = (
    "Real-time dashboard narrative is temporarily unavailable - see the status funnel and "
    "impact breakdown above for the current numbers."
)


def _generate_mvp_dashboard_narrative(scope_label: str, grounding: str, rows: list[dict]) -> str:
    """Shared by generate_mvp_overview_narrative/generate_mvp_mammo_narrative - same
    precomputed-at-refresh-cycle, never-live, fail-closed contract as
    generate_mvp_program_narrative above."""
    funnel = mvp_dashboard_stats.compute_status_funnel(rows)
    impact = mvp_dashboard_stats.compute_impact_breakdown(rows)
    escalations = mvp_dashboard_stats.compute_escalations_by_owner(rows)

    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        system_prompt = (
            f"You write a short 'key insights this week' paragraph for an internal radiology-"
            f"practice leadership dashboard, about the {scope_label} slice of the Mosaic Value "
            "Project (MVP) program. Be concrete and specific to the real numbers given below - "
            "never generic filler. 3-5 sentences maximum, plain language, no markdown, no "
            "bullet points, no preamble like 'Here is a summary'. "
            f"Program background: {grounding}"
        )
        user_prompt = (
            f"Current live status funnel (radiologist counts by stage, each split on-track/"
            f"escalated/declined): {funnel}.\n"
            f"Impact breakdown among radiologists who've reached Solutioning or later: "
            f"{impact}.\n"
            f"Solutioning escalations by owning team: {escalations}.\n"
            "Write the paragraph summarizing where this part of the program stands right now "
            "and what's worth watching."
        )
        response = _get_client().serving_endpoints.query(
            name=settings.ai_context_serving_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=ChatMessageRole.USER, content=user_prompt),
            ],
            max_tokens=2000,
        )
        text = (_extract_text(response.choices[0].message.content) or "").strip()
        if not text:
            print(f"[ai-context] generate_mvp_dashboard_narrative({scope_label}): empty text from model response", flush=True)
        return text or _MVP_DASHBOARD_FALLBACK
    except Exception as exc:  # noqa: BLE001 - must never break the refresh cycle
        print(f"[ai-context] generate_mvp_dashboard_narrative({scope_label}) failed: {exc}", flush=True)
        return _MVP_DASHBOARD_FALLBACK


def generate_mvp_overview_narrative(rows: list[dict]) -> str:
    """Overview (Drafting/Capture) dashboard's AI-generated 'key insights' - scoped to the D&C
    population (excludes Mammo and Ops/Self-Referred cohorts, matching the PDF's own Area
    dashboards' stated exclusion)."""
    scoped = mvp_dashboard_stats.scope_rows(rows, "overview")
    return _generate_mvp_dashboard_narrative("Drafting/Capture", mvp_context.PROGRAM_NARRATIVE, scoped)


def generate_mvp_mammo_narrative(rows: list[dict]) -> str:
    """Mammo Screening dashboard's AI-generated 'key insights' - scoped to the Mammo cohort."""
    scoped = mvp_dashboard_stats.scope_rows(rows, "mammo")
    return _generate_mvp_dashboard_narrative("Mammo Screening", mvp_context.PROGRAM_NARRATIVE, scoped)


def _weekly_report_fallback(sections: "Sequence[tuple[str, str, dict, dict]]") -> str:
    """The text shown when the narrative model is unreachable - naming this scope's own blocks.

    It used to be `_MVP_DASHBOARD_FALLBACK`, which points the reader at "the status funnel and
    impact breakdown above". That is accurate on the MVP pages and nowhere else: on the
    enterprise Drafting briefing it sends a reader to two blocks that are not on the page, in
    the one message whose entire job is to say the prose is missing and the numbers are not.

    A fallback is read precisely when something has already gone wrong, so it is the worst place
    to carry a second, quieter error - and the least likely to be caught, since it only renders
    when the serving endpoint is down.
    """
    labels = [label for label, *_ in sections]
    if not labels:
        return "Narrative is temporarily unavailable - the numbers above are current."
    named = labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"
    return f"Narrative is temporarily unavailable - see {named} above for the current numbers."


def generate_weekly_report_narrative(
    scope_label: str,
    grounding: str,
    sections: Sequence[tuple[str, str, dict, dict]],
    has_previous: bool,
) -> dict[str, str]:
    """The weekly briefing's two-part insight text - mirrors the real MVP PDF's own "Key
    insights this week" / "Focus next week" sections exactly, unlike
    _generate_mvp_dashboard_narrative's single blended paragraph. Grounded in real week-over-week
    deltas when a prior snapshot exists, honestly flagged as a first baseline when it doesn't
    (never fabricates a "vs last week" claim with nothing to compare against). Same
    precomputed-at-generate-time, fail-closed contract as every other narrative generator here.

    `sections` is `(label, description, values, deltas)` per block, and it is what made this
    reusable past MVP (plan item E-5). The previous signature took `funnel`, `impact` and
    `escalations` as named arguments and wrote three MVP sentences around them - "radiologist
    counts by stage", "radiologists who've reached Solutioning or later", "escalations by owning
    team". Any other program handed to it got those numbers introduced as MVP onboarding stages,
    and the model wrote confident prose about a funnel that did not exist. The description now
    travels with the numbers from the scope that defined them, so the model is never told what a
    block means by a function that cannot know.

    The program name is likewise not hardcoded: `scope_label` plus `grounding` carry it. MVP's
    scopes pass `mvp_context.PROGRAM_NARRATIVE`; the Drafting scope passes its own.
    """
    # Built before the try, not inside the except arm that uses it: an exception raised while
    # building the fallback is the one exception this function's `except Exception` cannot
    # absorb, and it would surface as a 500 on a request that had already succeeded.
    fallback = _weekly_report_fallback(sections)

    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

        system_prompt = (
            f"You write the 'Key insights this week' and 'Focus next week' sections of a weekly "
            f"status report for an internal radiology-practice leadership audience, about "
            f"{scope_label}. Be concrete and specific to the real numbers given below - never "
            "generic filler. Respond with exactly two sections, each 2-4 sentences, plain "
            "language, no markdown, no bullet points, no preamble, in this exact format:\n"
            "KEY_INSIGHTS: <text>\n"
            "FOCUS_NEXT_WEEK: <text>\n"
            f"Program background: {grounding}"
        )
        comparison_note = (
            "Deltas are versus last week's snapshot - cite specific week-over-week "
            "changes where they're notable."
            if has_previous
            else "This is the first snapshot ever generated for this scope - there is no prior "
            "week to compare against, so do not claim any week-over-week change; describe the "
            "current state as a starting baseline instead."
        )
        # Each block introduces itself with the description its scope supplied, then its numbers,
        # then its own deltas directly underneath - rather than collecting every delta into a
        # trailing paragraph the model has to re-pair with the right block by name.
        blocks = "\n".join(
            f"{label} ({description}): {values}.\n"
            f"  Week-over-week change, same shape, None where there is nothing to compare: {delta}."
            for label, description, values, delta in sections
        )
        user_prompt = f"{blocks}\n{comparison_note}\nWrite both sections now."
        response = _get_client().serving_endpoints.query(
            name=settings.ai_context_serving_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=ChatMessageRole.USER, content=user_prompt),
            ],
            max_tokens=2000,
        )
        text = (_extract_text(response.choices[0].message.content) or "").strip()
        if not text:
            print(f"[ai-context] generate_weekly_report_narrative({scope_label}): empty text from model response", flush=True)
            return {"key_insights": fallback, "focus_next_week": fallback}

        key_insights, focus_next_week = fallback, fallback
        if "FOCUS_NEXT_WEEK:" in text:
            before, after = text.split("FOCUS_NEXT_WEEK:", 1)
            focus_next_week = after.strip() or fallback
            key_insights = before.replace("KEY_INSIGHTS:", "").strip() or fallback
        else:
            # Model didn't follow the marker format - still real text, just not split; show it
            # as the key-insights half rather than discarding it.
            key_insights = text.replace("KEY_INSIGHTS:", "").strip() or fallback
        return {"key_insights": key_insights, "focus_next_week": focus_next_week}
    except Exception as exc:  # noqa: BLE001 - must never break the snapshot-generation request
        print(f"[ai-context] generate_weekly_report_narrative({scope_label}) failed: {exc}", flush=True)
        return {"key_insights": fallback, "focus_next_week": fallback}
