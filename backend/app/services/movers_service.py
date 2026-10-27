"""Movers & drivers: why is this group's efficiency different from the thing it's compared to?

A headline rate gap has two completely different causes that look identical on a bar chart:

  **Mix**  - the group reads a different *blend* of work. A practice doing mostly Head CT will
             post a lower TBWU/min than one doing mostly plain film, and neither radiologist is
             any faster than the other.
  **Rate** - the group genuinely reads faster or slower *within* the same kind of work.

Only the second is actionable, and conflating them is how a practice gets put on an improvement
plan for having a hard case mix. This module splits a gap into the two, exactly - the parts sum
back to the headline with no residual - and attributes each part to the buckets that caused it.

Shift-share, with the target's weights carrying the rate term:

    R_t - R_b  =  SUM_c (w_c - W_c) * p_c     <- mix: different weighting, valued at peer rates
               +  SUM_c  w_c * (r_c - p_c)    <- rate: same weighting, valued at the rate delta

where for bucket c: w_c / W_c are the target's / peers' share of total minutes, and r_c / p_c
are their TBWU-per-minute within the bucket. Expanding shows the cross terms cancel into
SUM(w*r) - SUM(W*p) = R_t - R_b, so the decomposition is an identity, not an approximation.
The unit tests assert that rather than trusting this comment.

**This is a cross-sectional decomposition, not week-over-week.** `efficiency_matrix` has no
period column - its grain is (npi, practice, subspecialty, modality, parent procedure, exam
category) and nothing else - so "what moved since last month" is genuinely unavailable here and
is not faked. It needs the Phase-2 cube's `period_start`/`grain`. What this answers is the
comparison a CEO actually opens the page for: this group versus its peers, and Mosaic versus
the legacy voice-recognition baseline it replaced.
"""

from typing import Any, Literal

Comparison = Literal["peers", "baseline"]

# Past this many buckets the rest are folded into one "All other" row. Not cosmetic: a 300-row
# waterfall has the same information content as a 12-row one and none of its legibility. The
# cut is by effect size, not by volume - see _fold_tail.
_MAX_BUCKETS = 12

METHODOLOGY = (
    "Shift-share decomposition. The gap between two reading-efficiency rates is split into a "
    "MIX component - the group reads a different blend of work than the comparison, and "
    "different work has different intrinsic TBWU/min - and a RATE component, the group reading "
    "faster or slower within the same kind of work. Both are computed from summed numerators "
    "and denominators, never from averaged rates, and they sum exactly to the headline gap. "
    "Only the RATE component reflects how the group is working; the MIX component reflects "
    "what work it was given. This is a cross-sectional comparison against the current "
    "population, not a week-over-week movement."
)


def _safe_div(num: float | None, den: float | None) -> float | None:
    if not den:
        return None
    return (num or 0) / den


def decompose(
    rows: list[dict[str, Any]],
    comparison: Comparison = "peers",
    bucket_label: str = "exam_category",
) -> dict[str, Any]:
    """Split a rate gap into mix and rate, attributed per bucket.

    `rows` is `efficiency_store.decomposition_rows()` output: per bucket, the target's and the
    peers' summed TBWU / time-in-seconds / baseline contribution.

    `comparison="peers"` compares the target against everyone else and returns both components.
    `comparison="baseline"` compares the target's Mosaic rate against its *own* legacy baseline
    over the *same* exams - so the weights are identical on both sides and the mix component is
    zero by construction, not by luck. That case returns per-bucket lift contributions and says
    so, rather than drawing a mix bar that is structurally always zero.
    """
    if comparison == "baseline":
        return _decompose_vs_baseline(rows, bucket_label)
    return _decompose_vs_peers(rows, bucket_label)


def _decompose_vs_peers(rows: list[dict[str, Any]], bucket_label: str) -> dict[str, Any]:
    # Minutes, because _rate() in efficiency_store reports TBWU per *minute*. Doing the whole
    # decomposition in seconds and converting at the end would be equivalent; doing half of it
    # in each is how a 60x error gets into a CEO deck.
    target_min = sum((r["target_time"] or 0) for r in rows) / 60.0
    peer_min = sum((r["peer_time"] or 0) for r in rows) / 60.0
    target_tbwu = sum((r["target_tbwu"] or 0) for r in rows)
    peer_tbwu = sum((r["peer_tbwu"] or 0) for r in rows)

    target_rate = _safe_div(target_tbwu, target_min)
    peer_rate = _safe_div(peer_tbwu, peer_min)
    if target_rate is None or peer_rate is None:
        return {
            "comparison": "peers",
            "available": False,
            "reason": (
                "No reading time recorded for this group"
                if target_rate is None
                else "No comparison group - this group is the entire population"
            ),
            "methodology": METHODOLOGY,
        }

    buckets: list[dict[str, Any]] = []
    for r in rows:
        t_min = (r["target_time"] or 0) / 60.0
        p_min = (r["peer_time"] or 0) / 60.0
        if not t_min and not p_min:
            continue
        w = t_min / target_min if target_min else 0.0
        big_w = p_min / peer_min if peer_min else 0.0
        r_c = _safe_div(r["target_tbwu"], t_min)
        p_c = _safe_div(r["peer_tbwu"], p_min)

        # A bucket the peers never touch has no peer rate to value the mix against. Imputing
        # the peers' *overall* rate keeps the identity intact - such a bucket has big_w == 0,
        # so it contributes nothing to SUM(W*p) and the imputed value cancels out of the total
        # entirely. It only decides how that bucket's own contribution is split, and the split
        # it gives is the honest one: "doing work your peers don't do at all" is a mix effect.
        p_hat = p_c if p_c is not None else peer_rate

        mix = (w - big_w) * p_hat
        # w is 0 when the target never touches the bucket, so the rate term is 0 regardless of
        # r_c - which is None there and would otherwise raise.
        rate = 0.0 if not t_min or r_c is None else w * (r_c - p_hat)

        buckets.append(
            {
                "bucket": r["bucket"],
                "target_share": w,
                "peer_share": big_w,
                "target_rate": r_c,
                "peer_rate": p_c,
                "mix": mix,
                "rate": rate,
                "total": mix + rate,
                "imputed_peer_rate": p_c is None,
            }
        )

    buckets = _fold_tail(buckets, keys=("mix", "rate", "total"))
    return {
        "comparison": "peers",
        "available": True,
        "bucket_label": bucket_label,
        "target_rate": target_rate,
        "comparison_rate": peer_rate,
        "gap": target_rate - peer_rate,
        "mix_effect": sum(b["mix"] for b in buckets),
        "rate_effect": sum(b["rate"] for b in buckets),
        "buckets": buckets,
        "methodology": METHODOLOGY,
    }


def _decompose_vs_baseline(rows: list[dict[str, Any]], bucket_label: str) -> dict[str, Any]:
    """Mosaic versus the legacy baseline, over the same exams.

    No mix term exists here and none is invented. Both rates are measured over the identical
    set of exams, so the weights cancel and every point of the gap is rate. What varies, and
    what this returns, is *which buckets produced the lift*.

    Note the asymmetric divisors, which are correct and must not be "tidied" into symmetry:
    TBWU is a raw total so its rate divides by minutes, while baseline_contrib is already a
    per-minute figure pre-multiplied by seconds as its weight, so it divides by seconds. Same
    convention as efficiency_store._rate / _baseline_rate.
    """
    target_sec = sum((r["target_time"] or 0) for r in rows)
    target_tbwu = sum((r["target_tbwu"] or 0) for r in rows)
    target_base = sum((r["target_baseline"] or 0) for r in rows)

    mosaic_rate = _safe_div(target_tbwu, target_sec / 60.0 if target_sec else 0)
    # A zero baseline total is "no legacy figure on file", not "the legacy system produced
    # nothing" - and the difference matters, because the second reading renders as an infinite
    # improvement attributable to Mosaic. Refuse rather than publish that.
    baseline_rate = _safe_div(target_base, target_sec) if target_base else None
    if mosaic_rate is None or baseline_rate is None:
        return {
            "comparison": "baseline",
            "available": False,
            "reason": "No legacy baseline recorded for this group's exams",
            "methodology": METHODOLOGY,
        }

    buckets: list[dict[str, Any]] = []
    for r in rows:
        sec = r["target_time"] or 0
        if not sec:
            continue
        w = sec / target_sec
        r_c = _safe_div(r["target_tbwu"], sec / 60.0)
        b_c = _safe_div(r["target_baseline"], sec)
        if r_c is None or b_c is None:
            continue
        buckets.append(
            {
                "bucket": r["bucket"],
                "target_share": w,
                "target_rate": r_c,
                "peer_rate": b_c,
                "mix": 0.0,
                "rate": w * (r_c - b_c),
                "total": w * (r_c - b_c),
                "imputed_peer_rate": False,
            }
        )

    buckets = _fold_tail(buckets, keys=("mix", "rate", "total"))
    return {
        "comparison": "baseline",
        "available": True,
        "bucket_label": bucket_label,
        "target_rate": mosaic_rate,
        "comparison_rate": baseline_rate,
        "gap": mosaic_rate - baseline_rate,
        # Stated explicitly rather than left for the reader to notice: the same exams on both
        # sides means there is no case-mix difference to find here.
        "mix_effect": 0.0,
        "mix_is_structurally_zero": True,
        "rate_effect": sum(b["rate"] for b in buckets),
        "buckets": buckets,
        "methodology": METHODOLOGY,
    }


def _fold_tail(buckets: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Keep the buckets that moved the number; sum the rest into one honest "All other" row.

    Ranked by |total| rather than by share: a tiny bucket where the group is wildly off-rate is
    exactly what the reader came for, and dropping it because it is small is how the one real
    finding on the page gets folded away.
    """
    ranked = sorted(buckets, key=lambda b: abs(b["total"]), reverse=True)
    # Ranked purely by effect, with no share floor. An earlier version gated on
    # `target_share >= _TAIL_SHARE` and that quietly discarded the single most interesting
    # row available: a bucket the group does *none* of has target_share exactly 0, so
    # "this practice has stopped doing the work its peers do" - a large, negative, entirely
    # real mix effect - got folded into "All other" every time.
    head = ranked[:_MAX_BUCKETS]
    tail = ranked[_MAX_BUCKETS:]
    if not tail:
        return head
    folded = {
        "bucket": f"All other ({len(tail)})",
        "target_share": sum(b["target_share"] for b in tail),
        "peer_share": sum(b.get("peer_share", 0.0) for b in tail),
        # Deliberately null, not a blended number: an "All other" row spanning 40 unrelated
        # procedures has no meaningful rate, and printing one invites it to be read as one.
        "target_rate": None,
        "peer_rate": None,
        "imputed_peer_rate": any(b["imputed_peer_rate"] for b in tail),
        "is_tail": True,
    }
    for k in keys:
        folded[k] = sum(b[k] for b in tail)
    return head + [folded]
