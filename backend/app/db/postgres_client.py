"""First real use of the Lakebase Postgres resource attached to this app
(practice-command-bhargav's "database" resource, dev-bhargav branch of the practice-command-db
project - created by Yaro).

Everything written here lives under a mosaic_ prefix, since this branch was forked from
production and already carries a real copy of PCC's schema - this module must never assume
it owns the whole database.

This starts with one real, low-risk use: a durable refresh-run log (app/services/
refresh_service.py's _last_error dict is in-memory only and lost on every restart - this
survives it, and is queryable by anyone else with access to this Postgres branch, not just
this app's own /refresh/status endpoint).

Auth: Databricks Apps connect to Lakebase via short-lived (1hr) OAuth tokens minted through the
SDK, not a static password - see https://docs.databricks.com/aws/en/oltp/projects/
tutorial-databricks-apps-autoscaling. A custom psycopg.Connection subclass mints a fresh token
on every new physical connection; the pool recycles connections over time so no token is ever
reused past expiry.

Best-effort by design: local dev has no ENDPOINT_NAME/real PGUSER configured (those are this
app's own service-principal values, set in app.yaml for the deployed app only), so every
function here degrades to a no-op + logged warning rather than crashing the refresh loop if the
pool can't be built or a write fails. Postgres logging is additive observability, never a
dependency the SQLite-backed read path relies on.
"""

import json
import os
import threading
from datetime import date, datetime
from typing import Any

_lock = threading.Lock()
_pool = None
_unavailable_reason: str | None = None


def _build_pool():
    """Lazy, once-per-process pool construction - import errors or missing env vars (local
    dev) are caught here and remembered, not retried on every refresh call."""
    global _unavailable_reason

    required = ["PGHOST", "PGDATABASE", "PGUSER", "ENDPOINT_NAME"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        _unavailable_reason = f"missing env vars (expected when running locally): {', '.join(missing)}"
        return None

    try:
        import psycopg
        from databricks.sdk import WorkspaceClient
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        _unavailable_reason = f"psycopg/databricks-sdk not available: {exc}"
        return None

    workspace_client = WorkspaceClient()
    endpoint_name = os.environ["ENDPOINT_NAME"]

    conninfo = (
        f"dbname={os.environ['PGDATABASE']} user={os.environ['PGUSER']} "
        f"host={os.environ['PGHOST']} port={os.environ.get('PGPORT', '5432')} "
        f"sslmode={os.environ.get('PGSSLMODE', 'require')}"
    )

    class OAuthConnection(psycopg.Connection):
        @classmethod
        def connect(cls, conninfo="", **kwargs):
            try:
                credential = workspace_client.postgres.generate_database_credential(endpoint=endpoint_name)
            except Exception as exc:  # noqa: BLE001 - surfaced here since psycopg_pool swallows worker errors
                print(f"[postgres] credential generation failed for endpoint={endpoint_name!r}: {exc!r}", flush=True)
                raise
            kwargs["password"] = credential.token
            kwargs["connect_timeout"] = kwargs.get("connect_timeout", 10)
            try:
                return super().connect(conninfo, **kwargs)
            except Exception as exc:  # noqa: BLE001
                print(f"[postgres] psycopg connect failed: {exc!r}", flush=True)
                raise

    try:
        pool = ConnectionPool(
            conninfo=conninfo,
            connection_class=OAuthConnection,
            min_size=1,
            max_size=5,
            open=True,
            timeout=20,
        )
        with pool.connection(timeout=20) as conn:
            with conn.cursor() as cur:
                # public belongs to PCC's own forked-production schema (confirmed live:
                # CREATE on public is rejected for this app's role) - Mosaic gets its own
                # schema instead, rather than assuming write access to the shared one.
                cur.execute("CREATE SCHEMA IF NOT EXISTS mosaic AUTHORIZATION CURRENT_USER")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mosaic.refresh_log (
                        id BIGSERIAL PRIMARY KEY,
                        dataset_name TEXT NOT NULL,
                        started_at TIMESTAMPTZ NOT NULL,
                        duration_seconds DOUBLE PRECISION,
                        row_count INTEGER,
                        status TEXT NOT NULL,
                        error TEXT
                    )
                    """
                )
                # Durable human review trail for the Baseline Review Queue - a reviewer's
                # accept/override/reject decision on a (npi, target_shift) pair that the
                # proxy-matching algorithm flagged as a weak ("Manual Review") match.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mosaic.baseline_review_decisions (
                        id BIGSERIAL PRIMARY KEY,
                        npi BIGINT NOT NULL,
                        target_shift TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('accepted', 'overridden', 'rejected_no_match')),
                        chosen_proxy_shift TEXT,
                        chosen_rank INTEGER,
                        note TEXT,
                        reviewed_at TIMESTAMPTZ NOT NULL,
                        UNIQUE (npi, target_shift)
                    )
                    """
                )
                # Freeform notes, attachable to either a radiologist (entity_key = NPI as
                # string) or a practice (entity_key = practice name) - one polymorphic table
                # rather than two, since the CRUD is identical either way and entity_type
                # keeps them distinguishable. Mirrors PCC's own notes/journal pattern (its
                # bundle documents a real, searchable notes system tied to entity records).
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mosaic.notes (
                        id BIGSERIAL PRIMARY KEY,
                        entity_type TEXT NOT NULL CHECK (entity_type IN ('radiologist', 'practice')),
                        entity_key TEXT NOT NULL,
                        note_text TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS notes_entity_idx ON mosaic.notes (entity_type, entity_key)"
                )
                # Audit log for the Radiologist Lookup page - every time someone opens an
                # individual radiologist's drilldown, a row lands here. Mirrors PCC's own
                # privacy discipline for this exact kind of view ("views are still logged",
                # confirmed from its own changelog) - write-only from the app's perspective
                # for now, nothing reads this back yet, but durable from day one rather than
                # bolted on after the fact.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mosaic.radiologist_lookup_views (
                        id BIGSERIAL PRIMARY KEY,
                        npi BIGINT NOT NULL,
                        search_query TEXT,
                        viewed_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                # One row per (scope, week-ending-Friday) - the real "reproduce this weekly"
                # artifact's persisted history. funnel/impact/escalations are JSON-encoded
                # (app/data/mvp_dashboard_stats.py's compute_* outputs) rather than JSONB, to
                # avoid pulling in psycopg's jsonb adapter for a value this app only ever
                # round-trips through Python, never queries with SQL JSON operators.
                # UNIQUE + ON CONFLICT means re-generating the same week overwrites it instead
                # of duplicating - someone may click "Generate" more than once before a week
                # is considered final.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mosaic.mvp_weekly_snapshots (
                        id BIGSERIAL PRIMARY KEY,
                        scope TEXT NOT NULL CHECK (scope IN ('overview', 'mammo')),
                        week_ending DATE NOT NULL,
                        funnel TEXT NOT NULL,
                        impact TEXT NOT NULL,
                        escalations TEXT NOT NULL,
                        key_insights TEXT,
                        focus_next_week TEXT,
                        generated_at TIMESTAMPTZ NOT NULL,
                        UNIQUE (scope, week_ending)
                    )
                    """
                )
        return pool
    except Exception as exc:  # noqa: BLE001 - genuinely any connection/driver error is non-fatal here
        _unavailable_reason = f"pool construction failed: {exc}"
        return None


def _get_pool():
    global _pool
    if _pool is None and _unavailable_reason is None:
        with _lock:
            if _pool is None and _unavailable_reason is None:
                _pool = _build_pool()
    return _pool


def log_refresh(
    dataset_name: str,
    started_at: datetime,
    duration_seconds: float,
    row_count: int | None,
    status: str,
    error: str | None = None,
) -> None:
    """Best-effort durable record of one refresh_one() run - never raises, so a Postgres
    hiccup can never take down the SQLite-backed refresh loop that actually serves the app."""
    pool = _get_pool()
    if pool is None:
        print(f"[postgres] skipping log_refresh for {dataset_name!r}: {_unavailable_reason}", flush=True)
        return
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mosaic.refresh_log (dataset_name, started_at, duration_seconds, row_count, status, error)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (dataset_name, started_at, duration_seconds, row_count, status, error),
                )
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] log_refresh failed for {dataset_name!r}: {exc}", flush=True)


def recent_refresh_log(limit: int = 100) -> list[dict[str, Any]]:
    """Read-path for the durable log - used by the /refresh/history route, separate from
    /refresh/status (which stays SQLite/in-memory-backed, unchanged)."""
    pool = _get_pool()
    if pool is None:
        return []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT dataset_name, started_at, duration_seconds, row_count, status, error
                    FROM mosaic.refresh_log
                    ORDER BY started_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                columns = [c.name for c in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] recent_refresh_log failed: {exc}", flush=True)
        return []


def save_review_decision(
    npi: int,
    target_shift: str,
    status: str,
    chosen_proxy_shift: str | None,
    chosen_rank: int | None,
    note: str | None,
    reviewed_at: datetime,
) -> bool:
    """Upsert a reviewer's decision for one (npi, target_shift) - re-reviewing an item updates
    its existing row instead of creating a duplicate. Returns whether the write succeeded;
    the route uses this to report success/failure back to the UI (unlike log_refresh, this is
    a direct user action, not best-effort background telemetry, so the caller needs to know)."""
    pool = _get_pool()
    if pool is None:
        print(f"[postgres] skipping save_review_decision for npi={npi}: {_unavailable_reason}", flush=True)
        return False
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mosaic.baseline_review_decisions
                        (npi, target_shift, status, chosen_proxy_shift, chosen_rank, note, reviewed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (npi, target_shift) DO UPDATE SET
                        status = EXCLUDED.status,
                        chosen_proxy_shift = EXCLUDED.chosen_proxy_shift,
                        chosen_rank = EXCLUDED.chosen_rank,
                        note = EXCLUDED.note,
                        reviewed_at = EXCLUDED.reviewed_at
                    """,
                    (npi, target_shift, status, chosen_proxy_shift, chosen_rank, note, reviewed_at),
                )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] save_review_decision failed for npi={npi}, target_shift={target_shift!r}: {exc}", flush=True)
        return False


def list_review_decisions() -> list[dict[str, Any]]:
    """All saved review decisions - used by the Baseline Review Queue to filter already-
    reviewed items out of the active queue."""
    pool = _get_pool()
    if pool is None:
        return []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT npi, target_shift, status, chosen_proxy_shift, chosen_rank, note, reviewed_at
                    FROM mosaic.baseline_review_decisions
                    ORDER BY reviewed_at DESC
                    """
                )
                columns = [c.name for c in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] list_review_decisions failed: {exc}", flush=True)
        return []


def save_note(entity_type: str, entity_key: str, note_text: str, created_at: datetime) -> bool:
    """A direct user action (like save_review_decision, not best-effort background
    telemetry) - the route needs to know if the write actually succeeded."""
    pool = _get_pool()
    if pool is None:
        print(f"[postgres] skipping save_note for {entity_type}={entity_key!r}: {_unavailable_reason}", flush=True)
        return False
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mosaic.notes (entity_type, entity_key, note_text, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (entity_type, entity_key, note_text, created_at),
                )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] save_note failed for {entity_type}={entity_key!r}: {exc}", flush=True)
        return False


def list_notes(entity_type: str, entity_key: str) -> list[dict[str, Any]]:
    pool = _get_pool()
    if pool is None:
        return []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT entity_type, entity_key, note_text, created_at
                    FROM mosaic.notes
                    WHERE entity_type = %s AND entity_key = %s
                    ORDER BY created_at DESC
                    """,
                    (entity_type, entity_key),
                )
                columns = [c.name for c in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] list_notes failed for {entity_type}={entity_key!r}: {exc}", flush=True)
        return []


def log_radiologist_lookup_view(npi: int, search_query: str | None, viewed_at: datetime) -> None:
    """Best-effort audit entry - never blocks the lookup response on a Postgres hiccup,
    same philosophy as log_refresh."""
    pool = _get_pool()
    if pool is None:
        print(f"[postgres] skipping log_radiologist_lookup_view for npi={npi}: {_unavailable_reason}", flush=True)
        return
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mosaic.radiologist_lookup_views (npi, search_query, viewed_at)
                    VALUES (%s, %s, %s)
                    """,
                    (npi, search_query, viewed_at),
                )
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] log_radiologist_lookup_view failed for npi={npi}: {exc}", flush=True)


def save_weekly_snapshot(
    scope: str,
    week_ending: date,
    funnel: dict,
    impact: dict,
    escalations: dict,
    key_insights: str | None,
    focus_next_week: str | None,
    generated_at: datetime,
) -> bool:
    """Upsert this week's MVP dashboard snapshot (app/services/mvp_weekly_report_service.py) -
    a direct user action (the "Generate This Week's Snapshot" button), so like
    save_review_decision/save_note the caller needs to know if the write actually succeeded."""
    pool = _get_pool()
    if pool is None:
        print(f"[postgres] skipping save_weekly_snapshot for scope={scope!r}: {_unavailable_reason}", flush=True)
        return False
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mosaic.mvp_weekly_snapshots
                        (scope, week_ending, funnel, impact, escalations, key_insights, focus_next_week, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scope, week_ending) DO UPDATE SET
                        funnel = EXCLUDED.funnel,
                        impact = EXCLUDED.impact,
                        escalations = EXCLUDED.escalations,
                        key_insights = EXCLUDED.key_insights,
                        focus_next_week = EXCLUDED.focus_next_week,
                        generated_at = EXCLUDED.generated_at
                    """,
                    (
                        scope,
                        week_ending,
                        json.dumps(funnel),
                        json.dumps(impact),
                        json.dumps(escalations),
                        key_insights,
                        focus_next_week,
                        generated_at,
                    ),
                )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] save_weekly_snapshot failed for scope={scope!r}: {exc}", flush=True)
        return False


def get_weekly_snapshots(scope: str, limit: int = 12) -> list[dict[str, Any]]:
    """Most recent snapshots for one scope, newest week first - funnel/impact/escalations
    decoded back into dicts so callers never deal with the TEXT-column JSON encoding."""
    pool = _get_pool()
    if pool is None:
        return []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scope, week_ending, funnel, impact, escalations, key_insights, focus_next_week, generated_at
                    FROM mosaic.mvp_weekly_snapshots
                    WHERE scope = %s
                    ORDER BY week_ending DESC
                    LIMIT %s
                    """,
                    (scope, limit),
                )
                columns = [c.name for c in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
                for row in rows:
                    row["week_ending"] = row["week_ending"].isoformat()
                    row["funnel"] = json.loads(row["funnel"])
                    row["impact"] = json.loads(row["impact"])
                    row["escalations"] = json.loads(row["escalations"])
                return rows
    except Exception as exc:  # noqa: BLE001
        print(f"[postgres] get_weekly_snapshots failed for scope={scope!r}: {exc}", flush=True)
        return []