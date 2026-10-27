"""Tests for the mix-vs-rate decomposition.

The decomposition's whole claim to being usable on a CEO surface is that it is *exact* - the
bars sum to the headline gap with no residual, so no one has to wonder what the leftover means.
That is an algebraic identity, and these tests assert it on data shaped like the awkward cases
rather than on a tidy symmetric fixture where almost any wrong formula would also pass.

Run: ./.venv/Scripts/python.exe tests/test_movers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.movers_service import decompose  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def row(bucket, t_tbwu=0.0, t_time=0.0, t_base=0.0, p_tbwu=0.0, p_time=0.0, p_base=0.0):
    return {
        "bucket": bucket,
        "target_tbwu": t_tbwu,
        "target_time": t_time,
        "target_baseline": t_base,
        "peer_tbwu": p_tbwu,
        "peer_time": p_time,
        "peer_baseline": p_base,
    }


def rate(num, sec):
    return num / (sec / 60.0)


# ---------------------------------------------------------------------------
# The identity, on a plain two-bucket case
# ---------------------------------------------------------------------------
print("\nmix + rate == gap")

rows = [
    row("CT", t_tbwu=200.0, t_time=6000.0, p_tbwu=900.0, p_time=30000.0),
    row("XR", t_tbwu=120.0, t_time=1200.0, p_tbwu=1400.0, p_time=12000.0),
]
d = decompose(rows, comparison="peers")
check("decomposes", d["available"] is True)
check(
    "components sum to the gap",
    abs(d["mix_effect"] + d["rate_effect"] - d["gap"]) < 1e-9,
    f"mix={d['mix_effect']} rate={d['rate_effect']} gap={d['gap']}",
)
check(
    "per-bucket totals sum to the gap",
    abs(sum(b["total"] for b in d["buckets"]) - d["gap"]) < 1e-9,
)
check(
    "target rate is SUM(num)/SUM(den), not an average of bucket rates",
    abs(d["target_rate"] - rate(320.0, 7200.0)) < 1e-12,
    f"got {d['target_rate']}, expected {rate(320.0, 7200.0)}",
)

# ---------------------------------------------------------------------------
# Mix alone: identical within-bucket rates, different blends.
# This is the case the whole module exists for - the target looks slower on the
# headline while being exactly as fast as its peers on every single bucket.
# ---------------------------------------------------------------------------
print("\npure mix: same rates, different blend")

# CT runs at 2 TBWU/min, XR at 6. Target is 75% CT by time; peers are 25% CT.
rows = [
    row("CT", t_tbwu=2 * 90, t_time=5400.0, p_tbwu=2 * 30, p_time=1800.0),
    row("XR", t_tbwu=6 * 30, t_time=1800.0, p_tbwu=6 * 90, p_time=5400.0),
]
d = decompose(rows, comparison="peers")
check("target is genuinely behind on the headline", d["gap"] < -0.5, f"gap={d['gap']}")
check(
    "every point of it is mix",
    abs(d["rate_effect"]) < 1e-9,
    f"rate_effect={d['rate_effect']} should be 0 - the rates are identical per bucket",
)
check("mix carries the whole gap", abs(d["mix_effect"] - d["gap"]) < 1e-9)

# ---------------------------------------------------------------------------
# Rate alone: identical blends, different within-bucket speed.
# ---------------------------------------------------------------------------
print("\npure rate: same blend, different speed")

rows = [
    row("CT", t_tbwu=2 * 60, t_time=3600.0, p_tbwu=3 * 60, p_time=3600.0),
    row("XR", t_tbwu=5 * 60, t_time=3600.0, p_tbwu=6 * 60, p_time=3600.0),
]
d = decompose(rows, comparison="peers")
check("mix is zero when the blends match", abs(d["mix_effect"]) < 1e-9, f"mix={d['mix_effect']}")
check("rate carries the whole gap", abs(d["rate_effect"] - d["gap"]) < 1e-9)
check("the gap is negative - target is slower", d["gap"] < 0)

# ---------------------------------------------------------------------------
# Edge: a bucket the peers never touch. The imputed peer rate must not break
# exactness, because such a bucket has peer weight zero.
# ---------------------------------------------------------------------------
print("\nedge: bucket present in target, absent from peers")

rows = [
    row("CT", t_tbwu=200.0, t_time=6000.0, p_tbwu=900.0, p_time=30000.0),
    row("Breast MRI", t_tbwu=40.0, t_time=3000.0),  # peers: nothing at all
]
d = decompose(rows, comparison="peers")
check("still exact with an imputed peer rate", abs(d["mix_effect"] + d["rate_effect"] - d["gap"]) < 1e-9)
imputed = [b for b in d["buckets"] if b["bucket"] == "Breast MRI"]
check("the imputed bucket survives folding", len(imputed) == 1)
if imputed:
    b = imputed[0]
    check("it is flagged as imputed so the UI can caveat it", b["imputed_peer_rate"] is True)
    check("its peer rate is reported as unknown, not as the fallback", b["peer_rate"] is None)
    check("its mix is positive - doing unusual work is a mix effect", b["mix"] > 0)

# ---------------------------------------------------------------------------
# Edge: a bucket the target never touches. r_c is None here, and a naive
# w * (r_c - p_c) would raise rather than return zero.
# ---------------------------------------------------------------------------
print("\nedge: bucket present in peers, absent from target")

rows = [
    row("CT", t_tbwu=200.0, t_time=6000.0, p_tbwu=900.0, p_time=30000.0),
    row("Nuclear Medicine", p_tbwu=50.0, p_time=6000.0),  # target: nothing at all
]
d = decompose(rows, comparison="peers")
check("does not raise on a None target rate", d["available"] is True)
check("still exact", abs(d["mix_effect"] + d["rate_effect"] - d["gap"]) < 1e-9)
absent = [b for b in d["buckets"] if b["bucket"] == "Nuclear Medicine"]
if absent:
    check("its rate contribution is exactly zero", absent[0]["rate"] == 0.0)
    check("its mix is negative - not doing peers' work removes their weight", absent[0]["mix"] < 0)

# ---------------------------------------------------------------------------
# Refusals. A decomposition with nothing to decompose must say so rather than
# render a waterfall of zeros, which reads as "no difference found".
# ---------------------------------------------------------------------------
print("\nrefusals")

d = decompose([row("CT", p_tbwu=900.0, p_time=30000.0)], comparison="peers")
check("no target time -> unavailable", d["available"] is False)
check("and says why", "No reading time" in d["reason"], d.get("reason", ""))

d = decompose([row("CT", t_tbwu=200.0, t_time=6000.0)], comparison="peers")
check("no peers -> unavailable", d["available"] is False)
check("and names the reason correctly", "entire population" in d["reason"], d.get("reason", ""))

d = decompose([], comparison="peers")
check("empty input -> unavailable, not a crash", d["available"] is False)

# ---------------------------------------------------------------------------
# vs_baseline: same exams both sides, so no mix term exists.
# ---------------------------------------------------------------------------
print("\nvs baseline (Mosaic vs legacy voice recognition)")

# baseline_contrib is already per-minute pre-multiplied by seconds, so a legacy
# rate of 1.5 TBWU/min over 6000s is stored as 9000.
rows = [
    row("CT", t_tbwu=2.0 * 100, t_time=6000.0, t_base=1.5 * 6000.0),
    row("XR", t_tbwu=5.0 * 20, t_time=1200.0, t_base=4.0 * 1200.0),
]
d = decompose(rows, comparison="baseline")
check("decomposes", d["available"] is True)
check("mosaic rate", abs(d["target_rate"] - rate(300.0, 7200.0)) < 1e-12)
check("baseline rate", abs(d["comparison_rate"] - (9000.0 + 4800.0) / 7200.0) < 1e-12)
check(
    "contributions sum exactly to the lift",
    abs(sum(b["rate"] for b in d["buckets"]) - d["gap"]) < 1e-9,
    f"sum={sum(b['rate'] for b in d['buckets'])} gap={d['gap']}",
)
check("mix is declared structurally zero, not merely measured as zero", d["mix_is_structurally_zero"] is True)
check("and is zero", d["mix_effect"] == 0.0)
check("Mosaic is ahead of the legacy baseline here", d["gap"] > 0)

d = decompose([row("CT", t_tbwu=200.0, t_time=6000.0)], comparison="baseline")
check("no baseline recorded -> unavailable", d["available"] is False)
check("and says so", "legacy baseline" in d["reason"], d.get("reason", ""))

# ---------------------------------------------------------------------------
# Tail folding must not change any total - it is presentation, not arithmetic.
# ---------------------------------------------------------------------------
print("\ntail folding")

big = [row("CT", t_tbwu=400.0, t_time=12000.0, p_tbwu=1800.0, p_time=60000.0)]
# 30 slivers, each well under the 1% share floor, each slightly off-rate.
for i in range(30):
    big.append(row(f"sliver {i}", t_tbwu=1.0 + i * 0.01, t_time=30.0, p_tbwu=40.0, p_time=1200.0))
d = decompose(big, comparison="peers")
check("folds to a readable number of rows", len(d["buckets"]) <= 13, f"got {len(d['buckets'])}")
check("still exact after folding", abs(sum(b["total"] for b in d["buckets"]) - d["gap"]) < 1e-9)
tail = [b for b in d["buckets"] if b.get("is_tail")]
check("there is exactly one tail row", len(tail) == 1)
if tail:
    check("the tail names how many buckets it hides", "(" in tail[0]["bucket"])
    check(
        "the tail reports no rate - a blend of 30 unrelated buckets has no meaningful one",
        tail[0]["target_rate"] is None,
    )
    check("tail shares add up with the head to 1.0", abs(sum(b["target_share"] for b in d["buckets"]) - 1.0) < 1e-9)

# A small bucket where the group is wildly off-rate is the finding, not noise -
# it must survive on |total|, not be dropped for being small.
loud = [
    row("CT", t_tbwu=400.0, t_time=12000.0, p_tbwu=1800.0, p_time=60000.0),
    row("Loud outlier", t_tbwu=600.0, t_time=600.0, p_tbwu=20.0, p_time=600.0),
]
d = decompose(loud, comparison="peers")
check(
    "a small-but-extreme bucket is ranked first, not folded away",
    d["buckets"][0]["bucket"] == "Loud outlier",
    f"got {[b['bucket'] for b in d['buckets']]}",
)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
