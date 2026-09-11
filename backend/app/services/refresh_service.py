import threading
import time
import traceback
from datetime import datetime, timezone

from pydantic import BaseModel

from app.db import cache_store, efficiency_store
from app.services import mosaic_service as edw

REFRESH_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def _dump(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
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
    ("deployment_by_radiologist", lambda: edw.get_deployment_by_radiologist(limit=5000), None),
    ("deployment_by_practice", lambda: edw.get_deployment_by_practice(), None),
    ("deployment_funnel_reporting", lambda: edw.get_deployment_funnel_reporting(), None),
    ("deployment_funnel_drafting", lambda: edw.get_deployment_funnel_drafting(), None),
    ("drafting_blockers_by_practice", lambda: edw.get_drafting_blockers_by_practice(), None),
    ("deployment_funnel_ct_abdpel", lambda: edw.get_deployment_funnel_ct_abdpel(), None),
    ("ct_abdpel_blockers_by_practice", lambda: edw.get_ct_abdpel_blockers_by_practice(), None),
    ("efficiency_matrix", lambda: edw.get_efficiency_matrix(), _store_efficiency_matrix),
    ("efficiency_trend_by_category", lambda: edw.get_efficiency_trend_by_category(), None),
    ("mvp_efficiency_by_radiologist", lambda: edw.get_mvp_efficiency_by_radiologist(), None),
    ("mvp_capacity_by_radiologist", lambda: edw.get_mvp_capacity_by_radiologist(), None),
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
]

_refresh_lock = threading.Lock()
_last_error: dict[str, str] = {}
_in_progress = False


def refresh_one(name: str, fetch, store=None) -> None:
    global _last_error
    t0 = time.time()
    print(f"[refresh] {name}: starting...", flush=True)
    try:
        result = fetch()
        if store is not None:
            store(result)
        else:
            cache_store.save(name, _dump(result))
        _last_error.pop(name, None)
        print(f"[refresh] {name}: done in {time.time() - t0:.1f}s", flush=True)
    except Exception as exc:
        _last_error[name] = str(exc)
        print(f"[refresh] {name}: FAILED after {time.time() - t0:.1f}s - {exc}", flush=True)
        traceback.print_exc()


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
        print("[refresh] full refresh complete", flush=True)
    finally:
        _in_progress = False
        _refresh_lock.release()


def refresh_status() -> dict:
    return {
        "refreshed_at": cache_store.all_refresh_times(),
        "errors": dict(_last_error),
        "in_progress": _in_progress,
    }


def start_background_loop() -> None:
    def loop():
        while True:
            refresh_all()
            time.sleep(REFRESH_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, daemon=True, name="mosaic-refresh-loop")
    thread.start()
