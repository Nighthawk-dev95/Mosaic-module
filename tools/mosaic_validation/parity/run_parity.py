"""PBI parity runner for the Mosaic Executive Dashboard (Tier A: volume).

Compares every volume KPI in kpi_registry.yaml between the governed metric view and PBI's own
import query (presentation_mosaicdailyvolume_vw with the DAX replicated in SQL), for the last N
closed months, company-wide, per Local Region and per Managing Practice. PBI's Local column is
regenerated from the SWITCH in Daily_Extract.tmdl so the bucket lists can never drift.

Writes PARITY_SIGNOFF.md next to this file. Exit code 1 if any KPI is an unexplained BUG/MISSING.

    python run_parity.py --profile mosaic-app [--months 3]
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TMDL = REPO / "tools/pbi_semantic_extract/mosaic_volume_tmdl/tables/Daily_Extract.tmdl"
COUNT_REL_TOL = 0.0005   # 0.05% relative
PCT_ABS_TOL = 0.0005     # 0.05 percentage points


def run_sql(sql, profile):
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", "--file", f.name,
                          "--profile", profile, "-o", "json"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         shell=(sys.platform == "win32"))
    pathlib.Path(f.name).unlink(missing_ok=True)
    if out.returncode:
        raise RuntimeError((out.stderr or out.stdout).strip()[-600:])
    txt = out.stdout
    return json.loads(txt[txt.index("["):]) if "[" in txt else []


def pbi_local_case():
    """Translate the PBI `column Local = SWITCH(TRUE(), Team IN {...}, "X", ..., "Matrix")`."""
    body = TMDL.read_text(encoding="utf-8")
    block = body[body.index("column Local ="):]
    block = block[:block.index("lineageTag")]
    arms = re.findall(r"IN\s*\{([^}]*)\}\s*,\s*\"([^\"]+)\"", block)
    default = re.findall(r"\"([^\"]+)\"\s*\)\s*$", block.strip())[0]
    sql = "CASE"
    for members, name in arms:
        # DAX string comparison is case-insensitive ("Boca" matches "BOCA")
        vals = ",".join("'" + v.lower().replace("'", "''") + "'" for v in re.findall(r"\"([^\"]*)\"", members))
        sql += f" WHEN LOWER(p.teamro) IN ({vals}) THEN '{name}'"
    return sql + f" ELSE '{default}' END"


def pbi_alt_exprs(cfg):
    alt = {}
    for d in cfg.get("known_divergences", []):
        alt.update(d.get("pbi_expr_alt", {}))
    return alt


def pbi_query(cfg, start, end):
    kpis = cfg["kpis"]
    aggs = ",\n  ".join(f"{k['pbi_expr']} AS `{k['id']}`" for k in kpis)
    alt = pbi_alt_exprs(cfg)
    aggs += "".join(f",\n  {alt.get(k['id'], k['pbi_expr'])} AS `alt__{k['id']}`" for k in kpis)
    return f"""
WITH p AS (
  SELECT p.*, {pbi_local_case()} AS pbi_local, p.Practice_Short_Name AS pbi_practice,
         DATE_TRUNC('MONTH', CAST(p.Final_DateTime AS DATE)) AS pbi_month
  FROM {cfg['pbi_source']} p
  WHERE CAST(p.Final_DateTime AS DATE) >= DATE'{start}' AND CAST(p.Final_DateTime AS DATE) < DATE'{end}')
SELECT CAST(pbi_month AS DATE) AS month,
  CASE WHEN GROUPING(pbi_local) = 0 THEN 'local' WHEN GROUPING(pbi_practice) = 0 THEN 'managing_practice' ELSE 'company' END AS scope,
  COALESCE(pbi_local, pbi_practice, 'ALL') AS member,
  {aggs}
FROM p GROUP BY GROUPING SETS ((pbi_month), (pbi_month, pbi_local), (pbi_month, pbi_practice))"""


def mv_query(cfg, start, end, scope_col, where=None):
    meas = ",\n  ".join(f"MEASURE(`{k['mv_measure']}`) AS `{k['id']}`" for k in cfg["kpis"])
    member = f"`{scope_col}`" if scope_col else "'ALL'"
    group = f", `{scope_col}`" if scope_col else ""
    return f"""
SELECT CAST(`{cfg['mv_month']}` AS DATE) AS month, {member} AS member,
  {meas}
FROM {cfg['metric_view']}
WHERE `Final Date` >= DATE'{start}' AND `Final Date` < DATE'{end}'{f" AND {where}" if where else ""}
GROUP BY `{cfg['mv_month']}`{group}"""


def classify(kind, ref, ours):
    ref = None if ref in ("", None) else ref
    ours = None if ours in ("", None) else ours
    if ref is None and ours is None:
        return "MATCH", 0.0
    if ref is None or ours is None:
        return "MISSING", None
    ref, ours = float(ref), float(ours)
    if kind == "count":
        diff = ours - ref
        rel = abs(diff) / ref if ref else (0.0 if diff == 0 else 1.0)
        return ("MATCH" if diff == 0 else "NEAR" if rel <= COUNT_REL_TOL else "BUG"), diff
    diff = ours - ref
    return ("MATCH" if abs(diff) < 5e-7 else "NEAR" if abs(diff) <= PCT_ABS_TOL else "BUG"), diff


def explain(cfg, k, month, member, diff, status, ref_alt, ours_alt):
    """Downgrade a BUG/MISSING to KNOWN DIVERGENCE only if the documented adjustments close the gap."""
    rules = [d for d in cfg.get("known_divergences", []) if k["id"] in d["kpis"]]
    adj = [d for d in rules if not d.get("waive")]
    if adj and classify(k["kind"], ref_alt, ours_alt)[0] in ("MATCH", "NEAR"):
        return "KNOWN DIVERGENCE", [d["id"] for d in adj]
    for d in rules:
        w = d.get("waive")
        if w and member in w["members"] and month[:7] in w["months"] and diff is not None \
                and abs(diff) <= w["max_abs_diff"]:
            return "KNOWN DIVERGENCE", [d["id"]]
    return status, []


def fmt(kind, v):
    if v in (None, ""):
        return "—"
    v = float(v)
    return f"{v:,.0f}" if kind == "count" else f"{v * 100:.2f}%"


def fmt_diff(kind, d):
    if d is None:
        return "—"
    return f"{d:+,.0f}" if kind == "count" else f"{d * 100:+.3f}pp"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--months", type=int, default=3)
    args = ap.parse_args()

    cfg = yaml.safe_load((HERE / "kpi_registry.yaml").read_text(encoding="utf-8"))["volume"]
    today = date.today()
    end = date(today.year, today.month, 1)
    y, m = end.year, end.month - args.months
    while m <= 0:
        y, m = y - 1, m + 12
    start = date(y, m, 1)

    scope_cols = {"company": None, "local": cfg["scopes"]["local"]["mv"],
                  "managing_practice": cfg["scopes"]["managing_practice"]["mv"]}
    mv_where = " AND ".join(f"({d['mv_where']})" for d in cfg.get("known_divergences", []) if d.get("mv_where"))
    jobs = {"pbi": pbi_query(cfg, start, end)}
    for scope, col in scope_cols.items():
        jobs[scope] = mv_query(cfg, start, end, col)
        if mv_where:
            jobs["alt__" + scope] = mv_query(cfg, start, end, col, mv_where)
    with ThreadPoolExecutor(len(jobs)) as ex:
        res = dict(zip(jobs, ex.map(lambda s: run_sql(s, args.profile), jobs.values())))

    ref = {(r["month"][:10], r["scope"], r["member"]): r for r in res["pbi"]}
    ours, ours_alt = {}, {}
    for scope in scope_cols:
        for r in res[scope]:
            ours[(r["month"][:10], scope, r["member"] or "(blank)")] = r
        for r in res.get("alt__" + scope, res[scope]):
            ours_alt[(r["month"][:10], scope, r["member"] or "(blank)")] = r

    rows = []
    for key in sorted(set(ref) | set(ours)):
        month, scope, member = key
        if member is None:
            continue
        for k in cfg["kpis"]:
            # a member absent on one side entirely means zero activity there, not a missing value
            absent = 0 if k["kind"] == "count" else None
            rv = ref[key].get(k["id"]) if key in ref else absent
            ov = ours[key].get(k["id"]) if key in ours else absent
            status, diff = classify(k["kind"], rv, ov)
            why = []
            if status in ("BUG", "MISSING"):
                status, why = explain(cfg, k, month, member, diff, status,
                                      ref.get(key, {}).get("alt__" + k["id"]), ours_alt.get(key, {}).get(k["id"]))
            rows.append(dict(month=month, scope=scope, member=member, kpi=k, ref=rv, ours=ov,
                             status=status, diff=diff, why=why))

    write_signoff(cfg, rows, start, end)
    bugs = [r for r in rows if r["status"] in ("BUG", "MISSING")]
    for r in rows:
        if r["scope"] == "company":
            print(f"{r['month']}  {r['kpi']['id']:<20} PBI {fmt(r['kpi']['kind'], r['ref']):>14}  "
                  f"DBX {fmt(r['kpi']['kind'], r['ours']):>14}  {fmt_diff(r['kpi']['kind'], r['diff']):>12}  {r['status']}")
    summ = {}
    for r in rows:
        summ.setdefault(r["scope"], {}).setdefault(r["status"], 0)
        summ[r["scope"]][r["status"]] += 1
    print(json.dumps(summ))
    sys.exit(1 if bugs else 0)


def row_md(r):
    k = r["kpi"]
    st = r["status"] + (f" (`{'`, `'.join(r['why'])}`)" if r.get("why") else "")
    return (f"| {r['month'][:7]} | {r['member']} | {k['label']} | {fmt(k['kind'], r['ref'])} | "
            f"{fmt(k['kind'], r['ours'])} | {fmt_diff(k['kind'], r['diff'])} | {st} |")


def write_signoff(cfg, rows, start, end):
    L = [f"# Mosaic Executive Dashboard — PBI parity sign-off (Tier A: Volume)\n",
         f"Generated {date.today()} by `run_parity.py`. Closed months {start} to {end} (exclusive).\n",
         f"- **Reference:** PBI's own import query `{cfg['pbi_source']}` with each DAX measure "
         f"replicated in SQL (see `kpi_registry.yaml`). PBI Local is regenerated from the "
         f"`column Local` SWITCH in `Daily_Extract.tmdl`.",
         f"- **Databricks:** `{cfg['metric_view']}` governed measures (what the dashboard and Genie read).",
         f"- **Tolerance:** counts MATCH = exact, NEAR = within 0.05% (source refresh timing); "
         f"percentages NEAR = within 0.05pp. KNOWN DIVERGENCE = outside tolerance but fully "
         f"explained by a documented rule below (re-checked with the rule's adjustment applied). "
         f"BUG = outside tolerance and unexplained.\n"]
    kd = cfg.get("known_divergences", [])
    if kd:
        L.append("## Known divergences (documented)\n")
        for d in kd:
            n = sum(1 for r in rows if d["id"] in r.get("why", []))
            L.append(f"- **`{d['id']}`** ({n} rows) — {d['reason']}")
        L.append("")
    for scope, title in (("company", "Company-wide"), ("local", "By Local Region")):
        L.append(f"## {title}\n")
        L.append("| Month | Member | KPI | PBI | Databricks | Diff | Status |")
        L.append("|---|---|---|---:|---:|---:|---|")
        for r in rows:
            if r["scope"] == scope:
                L.append(row_md(r))
        L.append("")
    mp = [r for r in rows if r["scope"] == "managing_practice"]
    L.append("## By Managing Practice (summary)\n")
    members = sorted({r["member"] for r in mp})
    by = {}
    for r in mp:
        by.setdefault(r["status"], 0)
        by[r["status"]] += 1
    L.append(f"{len(members)} practices × {len(cfg['kpis'])} KPIs × months: " +
             ", ".join(f"{s} {n}" for s, n in sorted(by.items())) + "\n")
    off = [r for r in mp if r["status"] not in ("MATCH", "NEAR")]
    if off:
        L.append("| Month | Practice | KPI | PBI | Databricks | Diff | Status |")
        L.append("|---|---|---|---:|---:|---:|---|")
        for r in sorted(off, key=lambda r: (r["status"] != "BUG", r["member"], r["month"])):
            L.append(row_md(r))
    (HERE / "PARITY_SIGNOFF.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
