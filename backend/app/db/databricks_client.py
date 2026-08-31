import threading
import time
from decimal import Decimal
from typing import Any

from databricks import sql

from app.config import settings


def _coerce(value: Any) -> Any:
    # Databricks returns DECIMAL columns as decimal.Decimal, which Pydantic silently accepts
    # for float fields but which sqlite3's executemany cannot bind at all (raises
    # "Error binding parameter: type 'decimal.Decimal' is not supported"). Converting once
    # here, for every query result, means every caller downstream - Pydantic-validated or
    # raw dicts written straight to SQLite (e.g. efficiency_store) - gets a plain float.
    if isinstance(value, Decimal):
        return float(value)
    return value

# A brand-new connection's FIRST query pays a huge, highly variable one-time cost (observed
# 150s-800s+) - confirmed via a controlled test where two back-to-back queries on the SAME
# connection took ~750s and ~800s respectively (i.e. it's not about warmup within a
# connection, it's about the connection/session itself being new). A connection that has
# already run one query stays fast for every query after that. The long-running MCP query
# tool used throughout this session's debugging stayed fast because it reuses one
# connection for its whole lifetime; every fresh per-request connection paid this tax again.
# So: hold ONE shared connection for this process's entire lifetime instead of one per
# request. This reintroduces a real risk - the Databricks SQL connector's session isn't
# safe for concurrent use from multiple threads - so the whole query lifecycle (not just
# connection creation) is serialized behind one lock.
_lock = threading.Lock()
_connection = None


def _get_shared_connection():
    global _connection
    if _connection is None:
        _connection = sql.connect(
            server_hostname=settings.databricks_server_hostname,
            http_path=settings.databricks_http_path,
            access_token=settings.databricks_token,
        )
    return _connection


def _reset_shared_connection() -> None:
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
    _connection = None


def run_query(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a SELECT and return rows as a list of dicts, on the one shared, long-lived connection.

    Always pass user-influenced values (filters, limits) via `params`, never
    string-interpolated into `query`, to avoid SQL injection.
    """
    tag = " ".join(query.split())[:120]
    t0 = time.time()
    with _lock:
        print(f"[dbx] {tag!r} got lock after {time.time() - t0:.1f}s, connecting...", flush=True)
        t1 = time.time()
        conn = _get_shared_connection()
        print(f"[dbx] {tag!r} connection ready after {time.time() - t1:.1f}s, executing...", flush=True)
        t2 = time.time()
        try:
            with conn.cursor() as cursor:
                if params:
                    cursor.execute(query, parameters=params)
                else:
                    cursor.execute(query)
                print(f"[dbx] {tag!r} executed after {time.time() - t2:.1f}s, fetching...", flush=True)
                columns = [col[0] for col in cursor.description]
                result = [
                    {col: _coerce(value) for col, value in zip(columns, row)}
                    for row in cursor.fetchall()
                ]
                print(f"[dbx] {tag!r} total {time.time() - t0:.1f}s, {len(result)} rows", flush=True)
                return result
        except Exception:
            # Connection may have gone stale (warehouse restarted, network blip) - drop it so
            # the next call reconnects (and pays the cold-start tax again), then re-raise.
            _reset_shared_connection()
            raise


def run_query_one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = run_query(query, params)
    return rows[0] if rows else None
