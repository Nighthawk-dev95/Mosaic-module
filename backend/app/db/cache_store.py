import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent.parent / "mosaic_cache.sqlite3"
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    # WAL mode lets readers (e.g. this module's load()) proceed while efficiency_store.py's
    # big writes (784K-row inserts) are in progress on the same underlying file - the default
    # rollback-journal mode blocks readers behind a writer and raises "database is locked".
    # busy_timeout is a backstop: retry for a few seconds instead of failing immediately.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
          name TEXT PRIMARY KEY,
          payload TEXT NOT NULL,
          refreshed_at TEXT NOT NULL
        )
        """
    )
    return conn


def save(name: str, payload: Any) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO cache (name, payload, refreshed_at) VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET payload = excluded.payload, refreshed_at = excluded.refreshed_at
                """,
                (name, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def load(name: str) -> tuple[Any, str] | tuple[None, None]:
    """Returns (payload, refreshed_at_iso) or (None, None) if never refreshed."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload, refreshed_at FROM cache WHERE name = ?", (name,)
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None, None
    payload, refreshed_at = row
    return json.loads(payload), refreshed_at


def all_refresh_times() -> dict[str, str]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT name, refreshed_at FROM cache").fetchall()
        finally:
            conn.close()
    return {name: refreshed_at for name, refreshed_at in rows}
