"""Static + live check of exec_dashboard.json before it is pushed to Lakeview.

Static: every encoding fieldName is produced by its query; every grid row sums to 12; every
filter/widget dataset exists. Live: each widget query is rebuilt as SQL against its asset and run
on the warehouse (unfiltered), so a misspelled measure or dimension fails here, not on the canvas.
Counters that come back NULL are reported (they would render blank for execs).

Usage: python tools/lakeview_exec_dashboard/validate_exec_dashboard.py --profile <profile>
"""

import argparse
import collections
import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent


def run_sql(sql, profile):
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         shell=(sys.platform == "win32"))
    if out.returncode:
        return None, (out.stderr or out.stdout).strip().splitlines()[-1][:300]
    txt = out.stdout
    return (json.loads(txt[txt.index("["):]) if "[" in txt else []), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    profile = ap.parse_args().profile
    sd = json.loads((HERE / "exec_dashboard.json").read_text(encoding="utf-8"))
    assets = {ds["name"]: ds["asset_name"] for ds in sd["datasets"]}
    problems, jobs = [], []

    for page in sd["pages"]:
        rows = collections.defaultdict(int)
        for item in page["layout"]:
            pos, w = item["position"], item["widget"]
            if page["pageType"] == "PAGE_TYPE_CANVAS":
                rows[pos["y"]] += pos["width"]
            spec = w.get("spec", {})
            for q in w.get("queries", []):
                qd = q["query"]
                if qd["datasetName"] not in assets:
                    problems.append(f"{w['name']}: unknown dataset {qd['datasetName']}")
                    continue
                names = {f["name"] for f in qd["fields"]}
                enc = spec.get("encodings", {})
                used = [f["fieldName"] for f in enc.get("fields", []) if f.get("queryName") == q["name"]]
                used += [c["fieldName"] for c in enc.get("columns", [])]
                for k in ("value", "x", "color"):
                    if k in enc and "fieldName" in enc[k]:
                        used.append(enc[k]["fieldName"])
                y = enc.get("y", {})
                used += [f["fieldName"] for f in y.get("fields", [])] + ([y["fieldName"]] if "fieldName" in y else [])
                for u in used:
                    if u not in names:
                        problems.append(f"{w['name']}: encoding {u!r} not in query fields")
                sel = ", ".join(f"{f['expression']} AS `{f['name'].replace('`', '')}`" for f in qd["fields"])
                tail = "" if qd.get("disaggregated") else " GROUP BY ALL"
                jobs.append((page["name"], w["name"], spec.get("widgetType"),
                             f"SELECT {sel} FROM {assets[qd['datasetName']]}{tail} LIMIT 3"))
        for y, total in rows.items():
            if total > 12:
                problems.append(f"{page['name']} row y={y} width {total} > 12")

    print(f"static: {len(problems)} problems; running {len(jobs)} widget queries...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda j: run_sql(j[3], profile), jobs))
    blanks = []
    for (page, name, wtype, sql), (rows, err) in zip(jobs, results):
        if err:
            problems.append(f"{page}/{name}: SQL error: {err}\n    {sql}")
        elif not rows:
            problems.append(f"{page}/{name}: returned 0 rows")
        elif wtype == "counter" and all(v is None for v in rows[0].values()):
            blanks.append(f"{page}/{name}")
        elif wtype == "counter":
            print(f"  {page:14} {name:28} {list(rows[0].values())[0]}")
    for b in blanks:
        print(f"  BLANK counter: {b}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    print("PASS" if not problems and not blanks else f"FAIL: {len(problems)} problems, {len(blanks)} blank counters")
    return 1 if problems or blanks else 0


if __name__ == "__main__":
    sys.exit(main())
