import re
import subprocess
import sys

sql_file = sys.argv[1] if len(sys.argv) > 1 else "_add_comments_enterprise_analytics.sql"
profile = sys.argv[2] if len(sys.argv) > 2 else "mosaic-app"

with open(sql_file, "r", encoding="utf-8") as f:
    raw = f.read()

# Strip full-line comments, then split on statement-terminating semicolons.
lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
cleaned = "\n".join(lines)
statements = [s.strip() for s in cleaned.split(";") if s.strip()]

print(f"{len(statements)} statements to run")

failures = []
for i, stmt in enumerate(statements, 1):
    result = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", "--profile", profile, stmt],
        capture_output=True, text=True
    )
    ok = result.returncode == 0 and "error" not in result.stdout.lower() and "error" not in result.stderr.lower()
    status = "OK" if ok else "FAIL"
    target = re.search(r"(TABLE|COLUMN)\s+([^\s]+)", stmt)
    label = target.group(2) if target else stmt[:60]
    print(f"[{i}/{len(statements)}] {status} {label}")
    if not ok:
        failures.append((label, result.stdout.strip(), result.stderr.strip()))

print(f"\nDone. {len(statements) - len(failures)} succeeded, {len(failures)} failed.")
for label, out, err in failures:
    print(f"--- FAILED: {label} ---\n{out}\n{err}\n")
