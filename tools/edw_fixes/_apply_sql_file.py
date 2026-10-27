"""Apply one .sql file as a single statement through the Databricks SQL warehouse.

The CLI's `experimental aitools tools query` takes the SQL as a command-line argument, which
Windows caps at 32,767 characters - the metric-view FLOW files are 40KB+, so they cannot be
applied that way. This reads the file instead.

    backend/.venv/Scripts/python.exe tools/edw_fixes/_apply_sql_file.py <file.sql> <profile> [warehouse_id]

Leading `--` comment lines and blank lines are stripped; everything from the first non-comment
line on is sent verbatim as ONE statement (these files each hold a single CREATE OR REPLACE).
A trailing `;` is trimmed - the statement API rejects it.
"""
import sys
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

DEFAULT_WAREHOUSE = "fe0ad987563c672a"


def main() -> int:
    path, profile = sys.argv[1], sys.argv[2]
    warehouse = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_WAREHOUSE

    lines = open(path, encoding="utf-8").read().splitlines()
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            start = i
            break
    sql = "\n".join(lines[start:]).strip().rstrip(";")

    print(f"{path}: {len(sql)} chars, first line: {sql.splitlines()[0][:90]}")

    w = WorkspaceClient(profile=profile)
    resp = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=warehouse, wait_timeout="50s"
    )
    state = resp.status.state if resp.status else None
    print(f"state={state}")
    if state != StatementState.SUCCEEDED:
        if resp.status and resp.status.error:
            print(f"ERROR: {resp.status.error.message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
