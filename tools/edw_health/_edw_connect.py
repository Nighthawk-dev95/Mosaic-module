"""Minimal standalone Databricks connector for the EDW Mosaic Health scripts.

Deliberately not importing backend.app.db.databricks_client - that module keeps one
shared connection alive for a whole FastAPI process's lifetime, which these short-lived,
once-a-day scripts don't need. Same credentials/env vars, same underlying connector
package (already installed in backend/.venv, confirmed working there), just a plain
connect-run-close for a single script invocation.

Confirmed this session: a brand-new connection's FIRST query pays a large, highly
variable one-time cost (observed 150s-800s+) - normal for a daily batch job, not
something to work around here. All queries in one script run share ONE connection so
that cost is paid once per run, not once per query.
"""
from __future__ import annotations

import os
from typing import Any

from databricks import sql


def get_connection():
    return sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def run_query(conn, query: str) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
