"""Generate 050_metadata/<view>.sql: the 8 exec metric views re-created with business metadata (comment,
display_name, synonyms) on every dimension and measure, for Genie and dashboard users.

Logic is NEVER changed: the YAML comes from the LIVE definition (SHOW CREATE TABLE), only the comment /
display_name / synonyms keys are merged in from tools/edw_fixes/metric_view_metadata/<view>.json, and the
script asserts every name, expr, source, filter and join is identical before writing. edw_test only; these
views are owned by this repo, so CREATE OR REPLACE re-syncs them.

    python tools/edw_fixes/_enrich_metric_view_metadata.py fetch --profile mosaic-app   # refresh live defs
    python tools/edw_fixes/_enrich_metric_view_metadata.py build                         # write 050_metadata/*.sql
"""
import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
META = HERE / "metric_view_metadata"
LIVE = META / "live"
OUT = HERE / "050_metadata"
S = "edw_test.enterprise_analytics"
VIEWS = ["mosaic_volume_metric_view", "mosaic_resident_utilization_metric_view", "mosaic_efficiency_metric_view",
         "mosaic_efficiency_vs_rp_avg_metric_view", "mosaic_capacity_metric_view", "mosaic_program_metric_view",
         "mosaic_draftable_metric_view", "mosaic_capacity_pbi_metric_view"]
MAX_SYNONYMS = 10


def fetch(profile):
    LIVE.mkdir(parents=True, exist_ok=True)
    for v in VIEWS:
        out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query",
                              f"SHOW CREATE TABLE {S}.{v}", "--profile", profile],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        stmt = json.loads(out.replace("\r", ""))[0]["createtab_stmt"]
        (LIVE / f"{v}.sql").write_text(stmt, encoding="utf-8")
        print(f"fetched {v} ({len(stmt)} chars)")


def parse_live(v):
    stmt = (LIVE / f"{v}.sql").read_text(encoding="utf-8")
    head, body, _ = stmt.split("$$")
    m = re.search(r"\nCOMMENT '((?:[^'\\]|\\.)*)'\nWITH METRICS", head)
    table_comment = m.group(1).replace("\\'", "'") if m else None
    return table_comment, yaml.safe_load(body)


def merge_field(field, meta):
    if meta.get("comment"):
        field["comment"] = meta["comment"].strip()
    if meta.get("display_name"):
        field["display_name"] = meta["display_name"].strip()
    drop = {x.lower() for x in meta.get("drop_synonyms") or []}  # retire a wrong live synonym
    syn = [x for x in field.get("synonyms") or [] if x.lower() not in drop] + list(meta.get("synonyms") or [])
    seen, merged = set(), []
    for s in syn:
        if s.strip() and s.strip().lower() not in seen:
            seen.add(s.strip().lower())
            merged.append(s.strip())
    if merged:
        field["synonyms"] = merged[:MAX_SYNONYMS]
    else:
        field.pop("synonyms", None)
    order = ["name", "expr", "comment", "display_name", "synonyms"]
    return {k: field[k] for k in order if k in field} | {k: x for k, x in field.items() if k not in order}


def logic(doc):
    """Everything except the metadata keys - must be identical before and after."""
    d = copy.deepcopy(doc)
    d.pop("comment", None)
    for sec in ("dimensions", "measures"):
        for f in d.get(sec, []):
            for k in ("comment", "display_name", "synonyms"):
                f.pop(k, None)
    return d


def build_view(v):
    table_comment, doc = parse_live(v)
    meta = json.loads((META / f"{v}.json").read_text(encoding="utf-8"))
    before = logic(doc)
    if meta.get("source"):
        # the one sanctioned logic change: repoint to a SELECT * snapshot of the same source (e.g. 049)
        doc["source"] = before["source"] = meta["source"]
    problems = []
    for sec in ("dimensions", "measures"):
        names = {f["name"] for f in doc.get(sec, [])}
        for n in set(meta.get(sec, {})) - names:
            problems.append(f"{sec}: metadata for unknown field {n!r}")
        doc[sec] = [merge_field(f, meta.get(sec, {}).get(f["name"], {})) for f in doc.get(sec, [])]
    if meta.get("view_comment"):
        table_comment = meta["view_comment"].strip()
        doc["comment"] = table_comment
    assert logic(doc) == before, f"{v}: logic changed"

    fields = doc.get("dimensions", []) + doc.get("measures", [])
    labels = {}
    for f in fields:
        if not f.get("comment"):
            problems.append(f"no comment: {f['name']}")
        if not f.get("display_name"):
            problems.append(f"no display_name: {f['name']}")
        for lbl in [f["name"], f.get("display_name")]:
            if lbl:
                labels.setdefault(lbl.lower(), set()).add(f["name"])
    for f in fields:
        if not f.get("synonyms"):
            problems.append(f"no synonyms: {f['name']}")
        for s in f.get("synonyms", []):
            owners = labels.get(s.lower(), set()) - {f["name"]}
            if owners:
                problems.append(f"synonym {s!r} of {f['name']!r} is the name of {sorted(owners)}")
    syn_owner = {}
    for f in fields:
        for s in f.get("synonyms", []):
            syn_owner.setdefault(s.lower(), []).append(f["name"])
    for s, owners in syn_owner.items():
        if len(owners) > 1:
            problems.append(f"synonym {s!r} shared by {owners}")

    yml = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120, default_flow_style=False)
    assert "$$" not in yml
    assert yaml.safe_load(yml) == doc
    tc = (table_comment or "").replace("'", "''")
    sql = (f"-- 050: {v} re-created with business metadata (GENERATED by _enrich_metric_view_metadata.py from the\n"
           f"-- live definition + metric_view_metadata/{v}.json). Logic identical to live (asserted). edw_test only.\n"
           f"CREATE OR REPLACE VIEW {S}.{v}\nCOMMENT '{tc}'\nWITH METRICS\nLANGUAGE YAML\nAS\n$$\n{yml}$$\n")
    OUT.mkdir(exist_ok=True)
    (OUT / f"{v}.sql").write_text(sql, encoding="utf-8")
    print(f"{v}: {len(doc.get('dimensions', []))} dims, {len(doc.get('measures', []))} measures, "
          f"{len(problems)} problems -> 050_metadata/{v}.sql")
    for p in problems:
        print("   ", p)
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build"])
    ap.add_argument("--profile")
    ap.add_argument("--views", nargs="*", default=VIEWS)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.profile)
    else:
        ok = [build_view(v) for v in a.views if (META / f"{v}.json").exists()]
        print(f"{sum(ok)}/{len(ok)} views clean")


if __name__ == "__main__":
    main()
