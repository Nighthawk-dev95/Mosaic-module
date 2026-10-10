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

import os
import threading
from datetime import datetime
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