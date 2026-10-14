"""Closes the loop between the Baseline Review Queue's durable decisions (Postgres,
app/db/postgres_client.py) and the Capacity tab's live numbers (EDW, app/services/
mosaic_service.py). Without this, a reviewer's accept/override/reject never changes what
get_capacity_baseline_scorecard() actually shows - it would just be an audit trail nobody reads.

Deliberately never mutates "capacity_with_baseline_raw" (the pristine EDW output) - this always
recomputes "capacity_with_baseline_merged" fresh from (raw EDW rows, candidate rates, current
decisions), so running it twice in a row is a no-op, not a double-application bug.
"""

from app.db import cache_store, postgres_client

RAW_KEY = "capacity_with_baseline_raw"
MERGED_KEY = "capacity_with_baseline_merged"


def recompute_capacity_with_overrides() -> None:
    raw_rows, _ = cache_store.load(RAW_KEY)
    if raw_rows is None:
        return  # capacity_with_baseline_raw hasn't refreshed yet this process - nothing to merge

    candidate_rows, _ = cache_store.load("baseline_proxy_candidates_raw")
    candidate_rate: dict[tuple, float | None] = {
        (c["npi"], c["target_shift"], c["rank"]): c.get("baseline_tbwu_per_hour") for c in (candidate_rows or [])
    }

    decisions = postgres_client.list_review_decisions()
    decision_by_key = {(d["npi"], d["target_shift"]): d for d in decisions}

    merged = []
    for row in raw_rows:
        row = dict(row)  # never mutate the cached original
        key = (row.get("npi"), row.get("target_shift"))
        decision = decision_by_key.get(key)
        if decision is not None:
            status = decision["status"]
            if status == "rejected_no_match":
                row["baseline_type"] = None
                row["shift_baseline_rpwu_fixed"] = None
            elif status == "overridden":
                rate = candidate_rate.get((key[0], key[1], decision.get("chosen_rank")))
                if rate is not None:
                    row["shift_baseline_rpwu_fixed"] = rate * (row.get("no_hours") or 0)
                    row["baseline_type"] = "Proxy"
            # "accepted" - chosen_rank is always 1, already the algorithm's own default; no change.
        merged.append(row)

    cache_store.save(MERGED_KEY, merged)
