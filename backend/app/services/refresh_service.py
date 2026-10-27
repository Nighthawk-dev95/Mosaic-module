import threading
import time
import traceback
from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel

from app.db import cache_store, efficiency_store, postgres_client
from app.services import ai_context_service, baseline_overrides, cube_service
from app.services import mosaic_service as edw
from app.services import volume_service

REFRESH_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def _dump(value):
    """Coerce a fetch result into something json.dumps can encode.

    The dict and date/datetime branches are not theoretical. Fetches that return Pydantic
    models are safe because model_dump(mode="json") already stringifies dates, but the fetches
    that return a raw list[dict] straight from run_query get no such pass - a DATE()/TIMESTAMP
    column arrives as a datetime.date and nothing coerces it. Without a dict branch, _dump
    recursed into the list, hit a dict, and fell through to `return value`, leaving the date in
    place to blow up inside cache_store.save. That is exactly how
    shift_utilization_by_radiologist ("Object of type date is not JSON serializable", from
    `DATE(s.shift_start) AS shift_date`) failed every cycle in production for weeks: refresh_one
    swallows the exception, so the only symptom was one permanently empty tab.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    if isinstance(value, (datetime, date)):
        # isoformat() on both, matching what Pydantic's mode="json" emits, so a dataset reads
        # back identically whether its fetch returns models or raw dicts.
        return value.isoformat()
    if isinstance(value, Decimal):
        # float, not str: every consumer of these cached values does arithmetic on them.
        return float(value)
    return value


def _store_efficiency_matrix(rows: list[dict]) -> None:
    efficiency_store.replace_all(rows)
    # efficiency_matrix's real data lives in its own SQLite table (see app/db/efficiency_store.py),
    # not the generic JSON cache - this just records a refresh timestamp so it shows up
    # alongside the other datasets in /refresh/status.
    cache_store.save("efficiency_matrix", {"row_count": len(rows)})


# (cache key, edw fetch callable, store callable) - each fetch callable takes no arguments
# and returns either a single Pydantic model or a list of them. store defaults to the
# generic JSON cache_store; efficiency_matrix overrides it to write into its own indexed
# SQLite table instead, since it's ~780K rows and too large to parse as JSON per request.
# Anything a route needs to filter/paginate on (roster filters, deployment/capacity
# pagination, efficiency population-by-slice) is handled in cache_service.py / efficiency_store.py
# over the already-cached dataset, since the underlying EDW queries are no longer called
# per-request.
DATASETS: list[tuple[str, object, object]] = [
    ("mosaic_intelligence_snapshot", lambda: edw.get_mosaic_intelligence_snapshot(), None),
    ("mosaic_intelligence_by_practice", lambda: edw.get_mosaic_intelligence_by_practice(), None),
    ("rpce_trend", lambda: edw.get_rpce_trend(), None),
    ("rpce_trend_by_practice", lambda: edw.get_rpce_trend_by_practice(), None),
    ("rad_summary_stats", lambda: edw.get_rad_summary_stats(), None),
    ("radiologist_roster", lambda: edw.get_radiologist_roster(limit=5000), None),
    ("utilization_by_practice", lambda: edw.get_utilization_by_practice(days_back=30), None),
    ("drafting_blockers_by_practice", lambda: edw.get_drafting_blockers_by_practice(), None),
    ("ct_abdpel_blockers_by_practice", lambda: edw.get_ct_abdpel_blockers_by_practice(), None),
    ("efficiency_matrix", lambda: edw.get_efficiency_matrix(), _store_efficiency_matrix),
    ("efficiency_trend_by_category", lambda: edw.get_efficiency_trend_by_category(), None),
    ("mvp_rad_onboarding_raw", lambda: edw.get_mvp_rad_onboarding(), None),
    # Depends on mvp_rad_onboarding_raw above having just been refreshed in this same cycle
    # (DATASETS runs sequentially in refresh_all) - reads it straight back from cache_store
    # rather than re-querying EDW, since this is a pure computation over that same data.
    ("mvp_program_narrative", lambda: ai_context_service.generate_mvp_program_narrative(cache_store.load("mvp_rad_onboarding_raw")[0] or []), None),
    ("mvp_overview_narrative", lambda: ai_context_service.generate_mvp_overview_narrative(cache_store.load("mvp_rad_onboarding_raw")[0] or []), None),
    ("mvp_mammo_narrative", lambda: ai_context_service.generate_mvp_mammo_narrative(cache_store.load("mvp_rad_onboarding_raw")[0] or []), None),
    ("mammo_screening_trend", lambda: edw.get_mammo_screening_trend(), None),
    ("efficiency_trend_by_practice_category", lambda: edw.get_efficiency_trend_by_practice_category(), None),
    ("efficiency_trend_rp_avg", lambda: edw.get_efficiency_trend_rp_avg(), None),
    ("capture_overview", lambda: edw.get_capture_overview(), None),
    ("capture_by_practice", lambda: edw.get_capture_by_practice(), None),
    ("capture_by_radiologist", lambda: edw.get_capture_by_radiologist(), None),
    ("capture_utilization_trend_weekly_by_practice", lambda: edw.get_capture_utilization_trend_by_practice("week"), None),
    ("capture_utilization_trend_monthly_by_practice", lambda: edw.get_capture_utilization_trend_by_practice("month"), None),
    ("capture_utilization_trend_weekly_by_radiologist", lambda: edw.get_capture_utilization_trend_by_radiologist("week"), None),
    ("capture_utilization_trend_monthly_by_radiologist", lambda: edw.get_capture_utilization_trend_by_radiologist("month"), None),
    ("capture_efficiency_trend_weekly_by_practice", lambda: edw.get_capture_efficiency_trend_by_practice("week"), None),
    ("capture_efficiency_trend_monthly_by_practice", lambda: edw.get_capture_efficiency_trend_by_practice("month"), None),
    ("capture_efficiency_trend_weekly_by_radiologist", lambda: edw.get_capture_efficiency_trend_by_radiologist("week"), None),
    ("capture_efficiency_trend_monthly_by_radiologist", lambda: edw.get_capture_efficiency_trend_by_radiologist("month"), None),
    ("capacity_by_radiologist", lambda: edw.get_capacity_by_radiologist(limit=5000), None),
    ("capacity_by_practice", lambda: edw.get_capacity_by_practice(), None),
    ("radiologist_scorecard", lambda: edw.get_radiologist_scorecard(), None),
    ("undrafted_analysis", lambda: edw.get_undrafted_analysis(), None),
    ("draft_insights_raw", lambda: edw.get_draft_insights_raw(), None),
    ("capacity_with_baseline_raw", lambda: edw.get_capacity_with_baseline(), None),
    ("baseline_proxy_detail_raw", lambda: edw.get_baseline_proxy_detail(), None),
    ("baseline_proxy_candidates_raw", lambda: edw.get_baseline_proxy_candidates(), None),
    ("shift_utilization_by_radiologist", lambda: edw.get_shift_utilization_by_radiologist(), None),
    ("volume_summary", lambda: volume_service.get_volume_summary(), None),
    ("volume_by_practice", lambda: volume_service.get_volume_by_practice(), None),
    ("volume_by_team", lambda: volume_service.get_volume_by_team(), None),
    ("volume_by_local_region", lambda: volume_service.get_volume_by_local_region(), None),
    ("volume_trend", lambda: volume_service.get_volume_trend(), None),
    ("volume_filter_options", lambda: volume_service.get_volume_filter_options(), None),
    # Appended, never inserted: the three mvp_*_narrative entries above read
    # cache_store.load("mvp_rad_onboarding_raw") written by the entry directly above them in this
    # same cycle, so the order of everything preceding this line is load-bearing.
    # Like efficiency_matrix, the bulk lands in its own SQLite table (app/db/fact_store.py) and
    # only a summary goes to the JSON cache, so this shows a refreshed_at in /refresh/status.
    ("mosaic_cube", lambda: cube_service.fetch_rows(), cube_service.store_rows),
]

_refresh_lock = threading.Lock()
_last_error: dict[str, str] = {}
_in_progress = False


def refresh_one(name: str, fetch, store=None) -> None:
    global _last_error
    t0 = time.time()
    started_at = datetime.now(timezone.utc)
    print(f"[refresh] {name}: starting...", flush=True)
    try:
        result = fetch()
        if store is not None:
            store(result)
        else:
            cache_store.save(name, _dump(result))
        _last_error.pop(name, None)
        duration = time.time() - t0
        row_count = len(result) if isinstance(result, list) else (1 if result is not None else 0)
        print(f"[refresh] {name}: done in {duration:.1f}s", flush=True)
        postgres_client.log_refresh(name, started_at, duration, row_count, "success")
    except Exception as exc:
        duration = time.time() - t0
        _last_error[name] = str(exc)
        print(f"[refresh] {name}: FAILED after {duration:.1f}s - {exc}", flush=True)
        traceback.print_exc()
        postgres_client.log_refresh(name, started_at, duration, None, "failed", error=str(exc))


def refresh_all() -> None:
    global _in_progress
    if not _refresh_lock.acquire(blocking=False):
        print("[refresh] refresh_all already running, skipping this call", flush=True)
        return
    try:
        _in_progress = True
        print(f"[refresh] starting full refresh of {len(DATASETS)} datasets", flush=True)
        for name, fetch, store in DATASETS:
            refresh_one(name, fetch, store)
        try:
            baseline_overrides.recompute_capacity_with_overrides()
        except Exception as exc:  # noqa: BLE001 - never let the override merge break the refresh cycle
            print(f"[refresh] recompute_capacity_with_overrides failed: {exc}", flush=True)
        print("[refresh] full refresh complete", flush=True)
    finally:
        _in_progress = False
        _refresh_lock.release()


def refresh_status() -> dict:
    return {
        "refreshed_at": cache_store.all_refresh_times(),
        "errors": dict(_last_error),
        "in_progress": _in_progress,
        # Lets the frontend tell "first refresh since a restart hasn't finished yet - some
        # modules may still be genuinely empty" apart from "a routine background refresh is
        # running, but every dataset already has data from last cycle" - same count, very
        # different user-facing meaning.
        "total_datasets": len(DATASETS),
    }


def start_background_loop() -> None:
    def loop():
        while True:
            refresh_all()
            time.sleep(REFRESH_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, daemon=True, name="mosaic-refresh-loop")
    thread.start()
