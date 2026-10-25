# PowerBI → Databricks semantic-model migration playbook

Written after the Mosaic Volume migration (2026-10-20 to 2026-10-22). Read this FIRST in any
new session migrating another PowerBI semantic model (Efficiency, Capacity, Draft vs Final,
Capture, Readtimes, etc.) — it exists so you don't rediscover the two bugs below the hard way.

## End goal and current phase

Overall goal: migrate every PowerBI "Mosaic" report to a Databricks App. **Current phase is
dashboards, not the app** — each semantic model becomes a Unity Catalog Metric View, validated,
then a page on a shared AI/BI (Lakeview) dashboard. The app build is deliberately deferred until
all/most semantics have a validated dashboard page. Decided 2026-10-22: sessions working on
different semantics run in parallel, combine by each adding its own page(s) to the **same shared
dashboard** rather than merging metric views or code.

**Shared dashboard**: "Mosaic Volume Report", dashboard_id `01f1ce304a0c128f913f243dc8ad0ad1`,
at `/Workspace/Users/bhargav.narasimhan@radpartners.com/dashboards`. Add new pages to this same
dashboard via `databricks lakeview update <id> --dataset-catalog edw_test --dataset-schema
enterprise_analytics --serialized-dashboard "$(cat updated.json)"` (always re-pass
`--dataset-catalog`/`--dataset-schema` on update, or it nulls them and breaks every query) — do
NOT `create` a second dashboard. `GET` it first (`databricks lakeview get <id>`) to pull the
current `serialized_dashboard` JSON, add your page(s) to its `pages[]` array, and your dataset(s)
to its `datasets[]` array, then `update` + `publish`.

## The pipeline (repeat per semantic model)

1. **Connect to the live PBI Desktop report** via the `powerbi-authoring-local` MCP server
   (`connection_operations` → `ListLocalInstances` → `Connect`). Confirm the correct report is
   open (parentWindowTitle) before connecting — ask the user to open it if the search comes back
   empty, don't guess.
2. **Export the full TMDL** via `database_operations` → `ExportToTmdlFolder`, to
   `tools/pbi_semantic_extract/<semantic>_tmdl/`. This is the ground truth for every measure's
   exact DAX — you won't need the live PBI connection again after this step.
3. **Build a measure inventory**: read every measure's DAX, classify each as business /
   disconnected-slicer-selector / dynamic-title-string / test-debug / duplicate-of-X. Only
   "business" measures become real metric-view measures. Dynamic-title and slicer-selector
   measures have no SQL equivalent — document them, don't implement them.
4. **Find the real `enterprise_analytics` source table(s)** the PBI measures actually correspond
   to (ask `backend/app/services/mosaic_service.py` first — it already solved most of these
   column-mapping problems for Capacity/Efficiency/Capture; don't re-derive from scratch). For
   Volume this was `tbl_exam_inventory`. Cross-check column names and types with
   `databricks experimental aitools tools discover-schema`, never assume a PBI column name maps
   1:1 by name.
5. **Author the metric view YAML** — see the two bugs below before writing a single join or a
   second list item. Deploy to `edw_test.enterprise_analytics.<name>_metric_view` first (now that
   grants exist — see below), validate numbers, THEN promote the same DDL to `edw_prod`.
6. **Add a dashboard page** to the shared dashboard (see above), using the validated metric view
   as the `asset_name` dataset.

## Two confirmed bugs — do not relearn these

### Bug 1: block-style (indentation-based) YAML silently corrupts in `CREATE VIEW ... WITH METRICS`

Submitting a `CREATE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$` statement via
`databricks experimental aitools tools query` (any of `--file`, positional arg, or stdin — all
three were tested, all three fail identically) corrupts normal YAML block-style sequences
(`dimensions:\n  - name: X\n    expr: Y`) the moment there's a **second item** in ANY list,
anywhere in the document — joins, dimensions, or measures. The error is either a YAML parse error
("expected `<block end>`, but found `-`") or a bogus "Missing required creator property" error,
depending on exactly where the second item falls. **Confirmed NOT a content problem**: the exact
same YAML parses perfectly with PyYAML locally; this is specific to however this CLI path
submits the statement to the Databricks backend.

**Fix: write the entire YAML body in flow style** (`{key: value, key2: [...]}`) instead of block
style. A Python script that round-trips through `yaml.safe_load()` then
`yaml.dump(..., default_flow_style=True, sort_keys=False, width=100000)` does this correctly —
see `tools/edw_fixes/_to_flow_style.py` (reusable as-is). One subtlety: flatten any multi-line
string values (collapse `\n` to a single space) BEFORE the flow-style dump, or PyYAML emits a
multi-line single-quoted scalar whose continuation-line indentation is exactly the kind of thing
that triggers Bug 1 again. `_to_flow_style.py` already does this (`flatten_strings()`).

Practical workflow: author/edit the metric view YAML in normal, readable block style (inside a
full `CREATE VIEW ...` SQL file, backslash-line-continuations in `comment:` fields are fine and
get collapsed by `tools/edw_fixes/_collapse.py`), then run both scripts in sequence
(collapse → extract YAML body between the `$$` markers → flow-convert → reassemble the SQL
file) before every `databricks experimental aitools tools query --file` deploy. Don't try to
author flow-style YAML by hand — it's unreadable and error-prone; only the deployed artifact
needs to be flow-style.

### Bug 2: a join whose `'on'` condition references a sibling join's resolved column corrupts that sibling's own dimension — nesting doesn't fix it correctly either

If join B's `'on'` clause references a column from join A (e.g., `A.category = B.category`), two
bad things can happen depending on how you structure it:

- As **sibling joins** (both direct children of `source`): fails outright with
  `UNRESOLVED_COLUMN` — A's alias isn't in scope inside B's `'on'` clause as a sibling.
- As a **nested join** (B nested inside A, per the "Snowflake Schema" pattern — which the
  official skill docs present as the correct fix for exactly this kind of dependency): the SQL
  silently SUCCEEDS but produces wrong data. Confirmed directly: for the exact same source-table
  value (`RPID22`), some rows correctly resolved join A's dimension (`drafting_model = 'CT Head'`)
  while OTHER rows with the identical value got NULL instead — purely because join B (nested
  inside A) failed to find its own match for those specific rows. This cut the overall dimension's
  true cardinality from 7 categories down to 2 silently (no error, no warning) and would have
  shipped wrong numbers (`Draftable Exam Count` under-counted by ~89%) if not caught by an
  independent plain-SQL cross-check.

**Fix: avoid the dependency entirely.** Don't give join B an `'on'` condition that needs to match
on a composite key tying it to another join's own data. Instead, collapse join B's source to be
uniquely keyed on whatever `source`'s own natural key already is (NPI, in our case), via a plain
aggregating helper view (`MIN()`/`MAX()`/`ANY_VALUE()` across whatever dimension you're dropping),
and join that as an ordinary sibling. You lose some specificity (in our case, "AD Group Added
Date" became "earliest AD-group date across ANY drafting category for this radiologist" instead
of being scoped to the one category matching the current exam row) — that's a real but acceptable
trade for correctness. **Always independently verify a new join with a plain SQL JOIN query
outside the metric view** before trusting the metric view's own dimension output — this is what
caught Bug 2; the metric view's own error-free deploy gave no signal that anything was wrong.

## Grants / access (already done, reusable)

Your personal account (`bhargav.narasimhan@radpartners.com`) now has `ALL PRIVILEGES` (via
group membership) on `enterprise_analytics` in all three catalogs: `SEC-AZ-DBX-P-EA-ADM` (prod,
pre-existing), `SEC-AZ-DBX-D-EA-ADM` (dev, granted 2026-10-22), `SEC-AZ-DBX-T-EA-ADM` (test,
granted 2026-10-22). No further grant requests needed for this work. Unity Catalog has NO
separate "CREATE VIEW" privilege — `CREATE TABLE` on the schema is what's actually required and
covers views (including metric views) too.

## Reference objects already confirmed reachable (exam grain, `enterprise_analytics`)

- `tbl_exam_inventory` — the exam-grain fact table every "Volume"-style semantic should source
  from (confirmed the `enterprise_analytics` equivalent of `edw_dev.bipa_analytics.
  presentation_mosaicdailyvolume_vw`). 148.2M rows in `edw_test`, same schema shape as `edw_prod`
  (test is actually a superset — a few extra columns not yet in prod).
- `edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw` — RPID-procedure-code → one of 7
  drafting-model categories (CT Abd/Pel, CT Chest, CT Head, CT Spine, DEXA Capturable, US
  Capturable, XR/MSK). Confirmed unique on `rpid_procedure_code`.
- `edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk` — the WIDER (26-category,
  969-procedure-code) clinical exam-category taxonomy, joined on `RPID_parent_code = ParentRpt`.
  Do not conflate with drafting-model category — different vocabulary, different purpose.
- `edw_prod.enterprise_analytics.dynamics_rad_drafting_enablement_vw` — per-(npi, drafting_model)
  AD-group/training/consent status. Only safely joinable per-category if you avoid Bug 2 above;
  `edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw` is the already-built
  per-NPI-collapsed safe version (only exists in `edw_test` so far — recreate in `edw_prod` when
  promoting anything that uses it).
- `edw_prod.enterprise_analytics.mosaic_drafting_metric_vw` — an existing, mature, already-shipped
  metric view with rich `comment`/`display_name`/`synonyms` on every field; good style reference
  for format conventions, and already has governed Drafting Coverage/Adoption Rate measures at the
  fleet level — don't re-derive those, point to this view instead if a new semantic needs them.
- `edw_prod.enterprise_analytics.tbl_exam_inventory_metric_view` — an existing general
  operational-performance metric view (TAT/SLA/backlog/efficiency/TBWU) over the same base table.
  Complementary, not overlapping, with the Volume semantic — don't duplicate its measures either.

## Naming conventions

- Metric view names: `<semantic>_metric_view` (e.g. `mosaic_volume_metric_view`,
  `mosaic_resident_utilization_metric_view`), matching the established local convention in
  `enterprise_analytics` (NOT the `mv_mosaic_*` convention used in the separate, unreachable
  `edw_dev.mosaictechops` schema — don't mix the two naming styles).
- Every measure/dimension gets a `comment:` — this is a Genie-consumption surface too (see
  `mosaic_drafting_metric_vw`'s style), not just internal documentation.
- Percentage measures always return a raw fraction (0-1), never pre-multiplied by 100 — matches
  both the established `enterprise_analytics` convention and the AI/BI dashboard skill's
  `number-percent` format expectation.
- A `days_back` `parameters:` block (default 14) on any measure PBI itself treated as a rolling
  window (named `... In Window` in the metric view) — confirmed working, requires calling the
  view as a table-valued function (`metric_view(7)` or `metric_view()` for the default), not a
  `WHERE days_back = N` filter.

## Dashboard conventions (so pages look consistent across semantics)

- Theme: Okabe-Ito colorblind-safe palette, already set as the shared dashboard's
  `uiSettings.theme` — don't redefine it per page, it's dashboard-wide already.
  `visualizationColors`: `#0072B2 #E69F00 #009E73 #CC79A7 #D55E00 #56B4E9 #F0E442`.
- Dataset per page: use the `asset_name` shorthand pointed straight at the metric view (not
  `queryLines: SELECT * FROM view()`) — this is the officially recommended mechanism for
  metric-view-backed datasets.
- High-cardinality dimensions (we hit `Practice`: 96 distinct, `Modality`: ~20 distinct including
  a junk long tail) → table widget, not a chart. Charts need ≤8-10 clean categories — filter out
  known junk/low-volume values explicitly with a `query.filters` expression rather than relying on
  an implicit top-N (this JSON format has no native `LIMIT`/top-N on a widget query).
- `query.filters: [{"expression": "<SQL boolean>"}]` is the per-widget filter mechanism — use it
  to scope one page's widgets (e.g., excluding null/placeholder rows) without needing a second
  dataset.

## Mosaic Efficiency migration (2026-10-22) — new findings

Efficiency's source tables (`radiologist_metrics`/`radiologist_summary` in the PBI model) and the
`enterprise_analytics.tbl_exam_inventory`-based SQL reimplementation of them already existed in
`mosaic_service.py` (`_MER_BASE_CTE_SQL`/`_MER_BASELINE_CTE_SQL`) before this migration — that was
the ground truth, not a fresh DAX port. New objects: `tbl_efficiency_exam_level_vw` (exam grain,
in `edw_test` only per explicit instruction — nothing from this migration has been promoted to
`edw_prod`), `mosaic_efficiency_metric_view` (`edw_test`), `tbl_team_rollups` (small lookup,
migrated to **both** `edw_test` and `edw_prod` — team_rollups has no sensitive logic and was
already created in `edw_prod` before the no-prod instruction landed; left in place with the
user's agreement rather than dropped).

**Team vs Practice are NOT interchangeable, even though `mosaic_service.py`'s existing code
conflates them as one `Practice` column.** Confirmed live via `SHOW CREATE TABLE` on
`radiologist_metrics_optimized`'s real lineage: `Team` = `tbl_exam_inventory
.provider_local_practice_name_curr` (the radiologist's own home/float pool — e.g. "SEAL Team" is
cross-coverage, not a billing practice), `Practice` = `managing_local_practice_name_curr` (the
practice whose exams are actually being read — what "By Practice" reporting means business-wise).
Confirmed live: SEAL Team's provider rows span 90+ distinct managing practices. Any new semantic
built on `tbl_exam_inventory` should use `managing_local_practice_name_curr` for a "By Practice"
dimension, not `provider_local_practice_name_curr` — re-check whether the Volume/Capacity/Capture
metric views already shipped got this right or inherited the same conflation.

**Qualification/min-exams gates only have a numeric effect once the threshold is > 1.** A
"radiologist qualifies for mode X" flag built as "has >= N exams in mode X" is a no-op against a
plain `SUM`/`COUNT` whenever N <= 1, because a row that already passes the mode's own filter
condition trivially proves its own NPI has at least one such row — there's nothing left to
exclude. Verified live: a hand-built boolean gate produced byte-identical output to the ungated
SUM. The fix: expose the gate as a real metric-view **parameter** (`min_exams`, default 1 — "show
everyone" is the confirmed business default) compared against a per-NPI all-time exam-count column
computed via a window function in the source view, the same `parameters:` pattern as Volume's
`days_back`. Query `mosaic_efficiency_metric_view(1000)` etc. to actually exercise the gate — the
default call shows the full population.

**Readtimeview is a different semantic from Parameter/Timeline/Mode_Lines — don't conflate them.**
Readtimeview's measures (`RP_Avg_Efficiency`, `Efficiency_vs_RP_Avg_*`, `Benchmark_*`) are built on
`radiologist_metrics(1)`/`radiologist_summary(1)`, confirmed via TMDL + `SHOW CREATE TABLE` to
source `edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow` /
`dim_radiologist_rtupdated_shadow` — a **no-baseline-restriction** population (built on
`presentation_rpt_readtimeswith_draftingadjustedrtshadow_tbl`, one of a whole family of
experimental shadow variants: p97/p98/p99/p100 percentile cutoffs, lognormal, minexams variants —
only `radiologist_metrics_minexams_rtupdatedshadow`/`dim_radiologist_rtupdated_shadow` themselves
have been migrated, as `tbl_readtime_radiologist_metrics_shadow`/`tbl_readtime_dim_radiologist_shadow`
in `edw_test`). This is for "efficiency vs. RP average" population comparisons, a genuinely
different question from "efficiency change vs. own baseline" (Parameter/Timeline/Mode_Lines, built
on the normal `radiologist_metrics_optimized` lineage) — **built as a separate metric view**
(`mosaic_efficiency_vs_rp_avg_metric_view`, `edw_test` only), not folded into
`mosaic_efficiency_metric_view`.

**Fixed-LOD pattern for a population-wide benchmark that must stay constant across any query
grouping** (create-patterns.md Pattern 10): the naive approach — a measure that's just
`AVG(tbwu)/AVG(time)` over the whole source — re-aggregates PER GROUP when a query adds
`GROUP BY NPI` or `GROUP BY Team`, which is wrong for a measure that's supposed to be "the single
company-wide number, shown next to every row for comparison." Fix: precompute the population
aggregate in the SOURCE VIEW via an **unpartitioned window function** (`SUM(...) OVER ()` — no
`PARTITION BY` at all), which Spark computes once over the entire row set; then the metric view
measure uses `ANY_VALUE(source.rp_avg_tbwu_col)` (not `SUM`/`AVG`) to pick that one constant value
regardless of grouping grain. Verified live: `SELECT DISTINCT rp_avg_full_mosaic_tbwu, ...` over
the 37.8M-row source view returned exactly one row, and the deployed metric view returned the
identical RP Avg figure whether queried with no grouping, `GROUP BY NPI`, or `GROUP BY
\`Team Rolled Up\``. The per-NPI qualification threshold baked into that population average is
necessarily a **fixed** value at view-definition time (window functions can't read a metric-view
runtime parameter) — only the INDIVIDUAL radiologist's own side of the ratio can use a real
`min_exams` parameter.

**A DAX inconsistency found live, deliberately NOT reproduced**: `Mosaic_Efficiency_Raw_NB` (the
individual radiologist's own number) does not modality-restrict "Drafting Only," while every
`Benchmark_*_Overall` measure (the population side of the same ratio) does restrict to CR/CT. The
migrated version applies the same CR/CT (or US/BD for Capture) restriction to both sides of every
ratio, matching the main Efficiency semantic's own convention — comparing an all-modality
individual number against a CR/CT-only population average would have been apples-to-oranges.

**CLI/tooling gotchas specific to this session:**
- `databricks lakeview get/update/publish` need a profile with the `dashboards` OAuth scope —
  `mosaic-app` (the PAT profile used for all the DDL above) does NOT have it and fails with
  `Provided access token does not have required scopes: dashboards`. Use `mosaic-oauth` for every
  `lakeview` command instead.
- A `--serialized-dashboard` value of any real size blows past Windows' command-line length limit
  (`Argument list too long`) even quoted. Use `--json @path/to/body.json` instead, where
  `body.json` is `{"serialized_dashboard": "<the JSON, as an escaped STRING value>"}` —
  `--dataset-catalog`/`--dataset-schema` still have to stay as separate flags either way (the
  `--json` body silently drops them if included there, same rule as `create`).
- `databricks lakeview publish` is classified as a **production-deploy action** by this session's
  auto-mode permission classifier and gets blocked even against a dashboard whose datasets point at
  `edw_test` — publishing makes the draft visible to every dashboard viewer, which the classifier
  (reasonably) treats the same as any other prod rollout. `update` (saving the draft) is not
  blocked. Expect to hand `publish` to the user rather than run it yourself when "don't deploy to
  prod" is in effect for the session.

## Mosaic Impact (Capacity) migration (2026-10-22) — new findings

Scope (confirmed explicitly): Shift Baseline, On-Shift Capacity, On-Shift Efficiency,
Utilization %, Capacity vs Baseline, the full case-mix breakdown, sourced from the migrated
`stg_mosaic_baseline_master` rather than a live Exact/Proxy re-derivation. New objects, `edw_test`
only: `tbl_mosaic_baseline_master` (migrated), `tbl_capacity_shift_level_vw` (shift-grain, extends
`mosaic_service.py`'s own `_CAPACITY_SHIFT_CTE_SQL`), `mosaic_capacity_metric_view` (9 dimensions,
72 measures). Deliberately out of scope (not requested, and the real formula isn't recoverable —
see below): Rad Equivalents Created / Annualized Capacity Increase (`2.Top N shift Table` /
`3.Summary Table`), which depend on a Top-N ranking slicer mechanic.

**The PBI model's own base table (`'0. Cur'`) is a dead end for formula recovery.** Its partition
M query is a literal `SELECT * FROM edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw`
(confirmed via TMDL), and that view is itself `SELECT * FROM
edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhance_tbl` (confirmed via `SHOW CREATE
TABLE`) — a materialized Delta table with no further SQL lineage. Every "on_shift_*"/"baseline_*"
column is ETL-populated by an opaque upstream job, not a DAX or SQL view formula. Don't waste time
trying to reverse-engineer these from TMDL/SQL alone — re-derive the business logic from
`mosaic_service.py`'s already-validated CTEs (same lesson as Efficiency's exam-level view) and
from the project's own `tools/capacity_model/README.md`, which documents the real algorithm from
the actual notebook source.

**"Rate" columns must be rolled up as `SUM(numerator)/SUM(denominator)`, never as a pre-divided
per-row column summed across rows.** `_CAPACITY_SHIFT_CTE_SQL`-derived values (capacity-per-hour,
utilization %, efficiency) are only valid at the exact row grain they were divided at; summing or
averaging a pre-divided rate across shifts of different lengths silently produces the wrong
weighted result. Fixed here by exposing only raw totals (`on_shift_capacity_rpwu`, `no_hours`,
`shift_read_minutes`) in the source view and composing every rate as a metric-view `MEASURE()`
ratio — same discipline as the Fixed-LOD lesson from the Readtimeview migration, different
failure mode (this one silently gives a *plausible-looking but wrong* number, not an obviously
broken one).

**`tat_unread_to_final_minutes` is turnaround time, not active read time — do not use it as a
read-time denominator.** It includes queue-wait time and can span days for a low-priority exam
that sat unread; summing it raw produced ~36.6 days of "read time" per shift on average (confirmed
live) before the fix. `mosaic_service.py`'s own shipped `_CAPACITY_SHIFT_CTE_SQL` has this exact
same latent issue in `get_capacity_by_radiologist`/`get_capacity_by_practice` — flagged, not fixed
there (out of scope for this migration), but **this migration's view does not use that column**.
Fixed by reusing `tbl_efficiency_exam_level_vw`'s proven LAG-based, 3600-sec-capped
`Adjusted_Read_Time_Sec` derivation, recomputed at exam grain (scoped to shift-attributed exams
only, a deliberate narrowing) before rolling up to shift grain.

**Dictation-timestamp coverage is wildly uneven across practices, and does NOT cleanly track the
RPCE/non-RPCE source-system split.** Confirmed live: RASF 99.97% of exams missing dictation
timestamps (reasonable — RASF is ~99.6% non-RPCE), but RP Valley is 88.7% missing despite being
~100% RPCE-classified (`Source_System_Code` IN rpceMidwest/rpceSouthwest) — an outright exception
to "RPCE = reliable timestamps." Per explicit decision: don't suppress or threshold-gate
Efficiency/Utilization — instead, `mosaic_capacity_metric_view` exposes both an `Is RPCE Source`
dimension AND a `Pct Exams With Valid Read Time` measure, and the dashboard page leads with "always
check Data Coverage % before trusting Efficiency/Utilization for a slice." Confirmed this measure
correctly flags the bad slices live (RASF: 0.06% coverage, nonsense 158.7 TBWU/min "efficiency";
RAF: 96.3% coverage, sane 0.18). **Use the coverage measure as the authoritative trust signal, not
the RPCE flag alone** — the flag is directionally useful but has confirmed exceptions.

## Mosaic Volume full-page recreation (2026-10-22) — new findings

A different kind of phase: not building a new metric view from scratch, but opening the real
PBI Desktop report (`Mosaic Volume Report.pbix`) page by page and recreating each page's actual
charts/filters/tables on the shared dashboard with 1:1 fidelity, rather than a handful of
"reasonable headline" KPI tiles. User-confirmed scope: Deployment Dashboard, Volume Trend Visual,
Rad Summary Statistics, Volume by Team/Rad/Practice & Site/Practice (all "Time Series" pages) —
explicitly skipped: Report Overview, Self-Service Data, Utilization Week Over Week, % XR Drafted
Time Series, % VRA prepped US (both variants), Resident Summary Statistics, Resident Volume Time
Series.

**Extracting a legacy-format .pbix's page layout without Power BI Desktop running.** A `.pbix` is
a ZIP archive; its `Report/Layout` entry is UTF-16LE-encoded JSON (this is the pre-PBIR/TMDL report
format, unrelated to the model-side TMDL export) containing `sections[]` (pages), each with
`visualContainers[]`. Don't extract the whole archive (the `DataModel` entry alone was ~190MB here)
— pull just the one small entry:
```bash
unzip -o "<path>.pbix" "Report/Layout" -d .
iconv -f UTF-16LE -t UTF-8 "Report/Layout" > layout_utf8.json
```
Each `visualContainer.config` field is itself a JSON **string** requiring a second `json.loads()`.
The visual's actual field bindings live under `config.singleVisual.prototypeQuery.Select[]`, where
each entry is one of `Column`/`Measure`/`Aggregation`/`HierarchyLevel` — the `Entity` naming the
source table is buried several `Expression`/`SourceRef` levels deep and position varies by select
kind, so a recursive "find the first `SourceRef.Entity`" walk is more robust than hardcoding the
path per kind. A per-page extraction script (`.tmp_work/extract_page.py` this session, not kept)
that dumps visual type/position/title/projections/selects in one pass made the page-by-page
classification tractable across ~10 pages this phase.

**Bash's `/tmp` and the `py -3` Python interpreter do not see the same filesystem on this box.**
Confirmed again this phase (same issue noted in the Readtimeview-era sessions): a file Bash just
wrote to `/tmp/...` reliably 404s as `FileNotFoundError` from a `py -3` script. Routine fix: `cp`
anything Bash produces in `/tmp` into a repo-relative `.tmp_work/...` path before any Python script
touches it. Applied to the unzipped `layout_utf8.json` specifically.

**Disconnected-slicer "Mosaic Metric" / "Threshold" / volume-filter patterns recur across nearly
every Volume page, not just one.** Confirmed by reading the actual DAX (not just inferring from
naming): `ThresholdSlicer`, `Utilizing 90 Filter`, and `Drafting Groups` are all disconnected
`DATATABLE(...)`-sourced tables whose sole purpose is a `SELECTEDVALUE`-driven `SWITCH`/`FILTER`
that changes what a *different* table's rows show or hide — the same non-portable "dynamic
measure switch" pattern first seen on the Volume Trend page's `LineChartMetricSelector`, just
applied to row-filtering instead of column-switching. Every one of the 4 "Volume by X, Time
Series" pages in the real report turned out to be this exact pattern wearing a different grain
(Team / Rad / Practice & Site / Practice) — recognize the shape (a `DATATABLE` partition +
`SELECTEDVALUE` + `SWITCH` over `NAMEOF(...)` comparisons) once and the rest classify in seconds.
**Convention for all of them, consistently applied**: replace the single disconnected-slicer pivot
with one plain table showing every real measure as its own always-visible column, at that page's
native grain — no SQL/metric-view equivalent of a DAX measure switch exists, and building 5 nearly
identical tables (one per hardcoded "Mosaic Metric" choice) would be worse than one table with 5
columns.

**New dimensions added to `mosaic_volume_metric_view` this phase**: `Priority Description`
(`source.Priority_Name`) and `Interventional Flag` (`source.exam_interventional_Ind`) — both plain
passthrough columns confirmed live on `tbl_exam_inventory`, added via the same safe
fetch-DDL/`yaml.safe_load`/modify-dict/flow-convert/redeploy/validate cycle as the earlier
Team/Site/Day Type additions, zero regression on total Exam Count (148,194,067) both times.
**Deliberately not added** (would need a net-new join or didn't exist on the base table):
`physician_type` (not a tbl_exam_inventory column — lives elsewhere, needs a join), `Week of First
Mosaic Case` (a derived calculated column off `First Mosaic Exam Date`, cheaper to just `WEEK()` it
at query time than carry as its own dimension), `working_subspecialty` (real column, just not yet
plumbed into this view — flagged as a gap, not pursued this phase), and the PBI page's
`Mosaicdraftingeligible`/`Query (3).vrarp_fullyutilizingname` slicers (the latter is literally the
"Fully Utilizing" cluster the user already confirmed excluding from this view entirely, back in
the original Volume metric view build).

**Reusable page-builder helper module** (`.tmp_work/dash_common.py`, not committed — lives only
for the duration of a multi-page build session): `PageBuilder.add_filter_row()` now always widens
the *last* row in a filter group to sum to 12 (originally it used a fixed `12 // per_row` width
for every row including a short trailing row, which left a visible gap — e.g. 7 filters at
`per_row=4` left the trailing 3-filter row summing to 9, not 12). Fixed by computing
`12 // len(row)` per row instead of once globally. Same class of bug, same fix shape, as the
Deployment Dashboard page's trailing-KPI-row fix from the previous phase — this is now clearly a
recurring gotcha worth checking on literally every filter/KPI row, not just the last one.

**Lakeview table-column conditional formatting — schema confirmed, but only for one-sided
thresholds.** The `serialized_dashboard` JSON schema for per-cell styling is undocumented by
Databricks; the only source that reverse-engineered it (`github.com/bspt628/databricks-lakeview-
skills`, MIT-licensed, built by inspecting 9 real dashboards/137 widgets) confirms the real shape:
```json
{
  "fieldName": "measure(`Pct Mosaic Exams`)",
  "format": {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}},
  "style": {
    "type": "basic",
    "rules": [
      {"condition": {"operand": {"type": "data-value", "value": "0.5"}, "operator": "<"},
       "foregroundColor": {"themeColorType": "visualizationColors", "position": 4}}
    ]
  }
}
```
`operator` is one of `< > <= >= == !=` — **there is no documented "between" operator**, so a true
two-sided band (the real DAX's 50–80% amber zone, `'Mosaic Exam % Color'`/`'...Colorfont'`
measures) cannot be expressed as a single rule. Applied here as two independent one-sided rules
instead: `< 0.5` → red foreground (`position: 4`, the one value this phase actually confirmed
against a real exported dashboard) and `>= 0.8` → green background (`position: 2`, an **unverified
guess** — only position 0=blue-default and 4=red are confirmed by the source material). The
50–80% middle band is deliberately left unstyled rather than guessing a third, unconfirmed color.
**If a future session needs the amber band or wants to confirm the green position, build one
colored cell by hand in the Lakeview UI's own conditional-formatting editor, then `lakeview get`
and diff the JSON** — don't keep guessing palette positions blind.

## Mosaic Efficiency dashboard pages (2026-10-22) — new findings

User-confirmed scope: By Provider Practice, By Managing Practice, By Exam, Time Series, Efficiency
Change Time Series Viz, Mosaic Efficiency vs Average, Mosaic Efficiency Time Series Viz —
`mosaic_efficiency_metric_view` and `mosaic_efficiency_vs_rp_avg_metric_view` (both from the
already-approved Efficiency migration plan) turned out to already be fully built and deployed in
`edw_test` from an earlier phase, so this round was pure dashboard-JSON authoring on top of
existing semantics, same as the Volume pages. **Positive Rads Time Series (the 8th requested page)
is explicitly NOT yet built** — it needs net-new measures (`Case_Buckets`/`Case_Buckets_Cumulative`
DAX: monthly distinct-radiologist "qualifies AND has both baseline+mosaic" counts, "positive"
(pct-change > 0) counts, and exam-volume-tier cumulative counts), not just a dashboard
recreation — flagged to the user as a separate scoping decision rather than silently skipped or
silently built as a guess.

**Databricks AI/BI dashboards cap out at 15 pages — hard limit, not configurable.** Hit this
exactly when deploying the 16th page (`efficiency_by_exam`) onto the shared Volume dashboard:
`lakeview update` fails outright with `Error: number of pages reaches the per-dashboard limit
[15]`. **Resolved by splitting into a second dashboard** rather than retiring any of the 15
existing pages — created a new "Mosaic Efficiency Report" dashboard (`lakeview create`) containing
just the two Efficiency datasets (`ds_efficiency`, `ds_efficiency_rp_avg`) and the 4
Efficiency-specific pages that existed so far (`efficiency`, `efficiency_rp_avg`,
`efficiency_by_provider_practice`, `efficiency_by_managing_practice`, pulled straight out of the
shared dashboard's `serialized_dashboard.pages`/`.datasets` arrays), then `lakeview update`d the
original dashboard with those 4 pages/2 datasets removed. **Plan ahead for this on any future
multi-semantic migration**: budget roughly one dashboard per PBI report (Volume / Efficiency /
Impact), not one shared dashboard for everything — 15 pages fills up fast once per-mode/per-grain
page recreation is in scope. `lakeview create` needs `warehouse_id` + `display_name` +
`serialized_dashboard` in the JSON body; reuse the same `uiSettings` block (theme/palette) from the
dashboard being split so the new one matches visually.

**The visualizationColors theme palette is now fully confirmed for this specific dashboard's
theme** (pulled straight from its own `uiSettings.theme.visualizationColors` array, not
reverse-engineered or guessed): `["#0072B2" (blue), "#E69F00" (amber), "#009E73" (green),
"#CC79A7" (pink), "#D55E00" (red/orange), "#56B4E9" (light blue), "#F0E442" (yellow)]` — i.e.
**position 2 IS a real green**, confirming the earlier "unverified guess" used for the Volume
pages' conditional formatting was correct for this dashboard, and position 4 is red/orange as
the widget-table skill's own source material had already confirmed. Still true that a genuine
two-sided "between" range (the amber 50–80% band) has no operator support — only the two
one-sided ends are stylable.

**New dimension added to `mosaic_efficiency_metric_view` this phase**: `Exam Week`
(`DATE_TRUNC('WEEK', source.exam_date)`), inserted right after `Exam Month` — needed because the
real PBI "Efficiency Change, Time Series Viz" page trends at `Week_Date` grain, one level finer
than the `Exam Month` grain the view already had (confirmed via the Mode_Lines.tmdl DAX using
`ALLSELECTED(...[Beginning_of_Month], ...[Week_Date])` together). Same safe extend-the-view cycle
as every prior dimension addition this session, zero joins on this view so no Bug-2 risk at all
(`SHOW CREATE TABLE` confirms `joins: 0` on both Efficiency metric views — team/local-region
rollups are baked into `tbl_efficiency_exam_level_vw` itself, not joined at the metric-view layer).

**The "6 modes x N measures" column family is now a shared, parameterized helper**
(`dash_common.py`'s `mode_measure_fields_and_columns()` for the baseline-comparison view's
`<Mode> Mosaic/Baseline Exams/Efficiency/Pct Change/Implied RTS` naming, `rp_avg_mode_fields_and_
columns()` for the peer-comparison view's `<Mode> Own Exams/Efficiency/Efficiency Vs RP Avg`
naming) rather than hand-writing 6x duplicated column blocks per page — built once for By Provider
Practice, reused unchanged for By Managing Practice, By Exam, and Mosaic Efficiency vs Average.
Conditional formatting is baked into the generator itself (red `<0`/green `>0` on every `% Change`
column, red `<1`/green `>=1` on every `vs RP Avg` ratio column) so it doesn't have to be
re-specified per page either.

**Sharing a dashboard outside the builder's own identity needs a DIFFERENT grant check than
building it.** A user tried sharing the Volume dashboard with their boss and got "error loading
dataset schema" — `SHOW GRANTS ON SCHEMA edw_test.enterprise_analytics` showed `SELECT`/`USE
SCHEMA` granted only to the builder's own user and one admin group (`SEC-AZ-DBX-T-EA-ADM`), despite
`USE CATALOG` on `edw_test` itself being wide open to `account users`. **Catalog-level access does
not imply schema-level access** — don't assume a broad `USE CATALOG` grant means a colleague can
actually read the metric views underneath it; check the schema grant specifically before promising
a dashboard is shareable. Two fixes, neither performable by the assistant: (1) a Lakeview
dashboard-level "Run as owner" credential-mode setting (not exposed via the `lakeview` CLI surface
checked this session — UI-only) so viewers borrow the builder's credentials instead of needing
their own grant, or (2) an actual `GRANT SELECT` to the viewer/their group on the schema. Both are
genuinely the user's call, not something to silently do — (2) especially, since widening access to
a **test** catalog to more people works against the whole reason this migration has stayed
`edw_test`-only all session.

## Dashboard page-budget juggling (2026-10-22) — new findings

Before Capacity's pages could be added, the single shared dashboard needed room: user directed
combining Volume's 3 "by X, Time Series" pages into one (`volume_time_series_combined`), deleting
`volume_by_practice` outright, and promoting the standalone Efficiency dashboard's 9 pages back
into this one — which immediately re-hit the 15-page cap (8 Volume + 9 Efficiency = 17). Resolved
over two more rounds of user-directed trims: dropped `resident`/`capacity` (the old placeholder
pages, since Capacity was about to get a full rebuild anyway) to land the merge at exactly 15, then
for Capacity itself: deleted `overview`/`drafting`/`efficiency_time_series`, merged
`volume_trend`'s widgets into `deployment_dashboard` (simple y-offset append — no field/layout
changes needed since each source page's rows already summed to 12 independently), and combined the
requested "Rad Summary" + "Practice Summary" pages into one — landing the final 15-page dashboard
at exactly 4 new Capacity pages added. **Takeaway for any future page-budget crunch**: merging two
already-built pages by y-offset-appending one page's `layout` array onto another's (checking for
widget-name collisions first, which are rare since names are usually page-prefixed) is cheap and
loses zero content/fidelity — prefer it over deleting real content when the only problem is the
page count, and ask the user each time rather than silently picking what to cut, since every round
of "which pages" this session got a different, non-obvious answer than what seemed like the
"obvious" one to suggest.

## Mosaic Impact (Capacity) dashboard pages (2026-10-22) — new findings

Built from the live `Mosaic Impact Report.pbix`, 5 user-confirmed visible pages (Report Overview
skipped same as always): Rad Detail, Rad Summary (combined with Practice Summary per the page-
budget crunch above), Time Series, Shift Baselines.

**The view's own header comment was wrong — always re-verify a "same as the sibling view" claim
with `SHOW CREATE TABLE`, don't trust the prose.** `mosaic_capacity_metric_view`'s COMMENT claimed
its Local Region mapping was "the same mapping used in the Efficiency and Capacity metric views"
(written when the Efficiency view was built), but the Capacity view's own dimension list had
neither `Team Rolled Up` nor `Local Region` at all — confirmed via `SHOW CREATE TABLE` and
`information_schema.columns` on the base `tbl_capacity_shift_level_vw` (only a flat `team` column,
no rollup/region column, no existing join). Both real PBI Time-Series/Detail pages group by
Local/Team-Rolled-Up, so this was a genuine, not cosmetic, gap. Fixed via the Volume-style
join-at-the-metric-view-layer pattern (new `dim_team_rollup` join on `tbl_team_rollups`, `source.
team = dim_team_rollup.Team`; flat CASE expression for Local Region copied verbatim from Volume's
own dimension, substituting `source.team` for `source.provider_local_practice_name_curr`) rather
than Efficiency's flat-baked-into-the-source-view approach, since editing
`tbl_capacity_shift_level_vw` itself would have been a bigger, separate change. Zero regression
confirmed (On Shift Cases total unchanged: 71,434,242 before and after).

**The "Top N shift Table" mechanic is the SAME excluded Rad-Equivalents/Annualized-Capacity-
Increase ranking-selection slicer flagged in the original Capacity migration plan — but don't
assume that means the whole page is unbuildable.** It dominates Rad Detail/Rad Summary/Practice
Summary's visuals (nearly every measure on all three pages routes through `Top N shift
Table`/`2.Top N shift Table` DAX: `Selected Shift Ct.`, `New Capacity/Efficiency/Utilization(Top
N)`, `% Add'l Capacity(Top N)`, `Average Baseline(Top N)`, `% Mosaic(Top N)`). On inspection, only
the ranking/selection mechanic ITSELF (picking a user-chosen top-N subset of shifts to rank) is the
unrecoverable part — the underlying, non-ranked, full-population versions of every one of those
measures were already sitting in the metric view (`On Shift Capacity RPWU` ≈ New Capacity, `On
Shift Capacity Vs Baseline RPWU` ≈ Add'l Capacity, `On Shift Utilization Pct` ≈ New Utilization(Top
N), `On Shift Efficiency RPWU` ≈ New Efficiency(Top N), `Pct Mosaic Of Shift` ≈ %Mosaic(Top N)).
Built Rad Detail/Rad Summary/Practice Summary using these real, always-visible, full-population
measures instead — same "replace the disconnected mechanic with the real always-visible measure"
convention as every other phase, just a case where the real measure was already there and only
needed recognizing, not adding.

**Baseline-period case mix (modality/priority breakdown of the HISTORICAL baseline window) isn't
tracked anywhere in this view — only the CURRENT shift's case mix is.** The real Rad Detail page's
100%-stacked-column charts compare modality/priority mix at two "States" (Baseline vs Current);
only the Current side has a real equivalent here (`Pct XR/CT/.../Of Shift`, `Pct Routine/Stat/.../
Of Shift`). Built the Current-state mix as two small tables (not stacked bars — table is the safer
fallback per the playbook's own established convention when a chart type is non-trivial to get
right) and documented the Baseline-side gap in the page header rather than silently dropping it or
fabricating a baseline-mix number.

**Shift Baselines queries a plain Unity Catalog table directly, not a metric view — a genuinely
different widget-JSON shape, and the session's `validate_page.py` SQL-reconstruction helper breaks
on it.** `tbl_mosaic_baseline_master` (the real migrated name — NOT `stg_mosaic_baseline_master` as
the PBI model's own table name would suggest) has no `()` call syntax and no `MEASURE()` wrapping;
aggregates are plain SQL expressions (`COUNT(*)`) passed through `dim_field()`'s free-form
`expr` parameter, same helper used for ordinary dimensions since metric-view and plain-table
datasets share the same `{name, expression}` field shape in the widget JSON. The validator script
built for metric-view pages assumes `FROM {asset}()` and "field name == physical column name" for
every non-`MEASURE()` field — both assumptions break for a plain-table dataset with a derived
alias like `Baseline Row Count` (`COUNT(*) AS \`Baseline Row Count\``). Fix was to hand-verify this
one page's SQL directly against the real column list instead of trusting the generic validator —
worth hand-checking the validator's actual reconstructed SQL text (not just its pass/fail count)
whenever a page's dataset isn't a metric view. Also note: the migrated table's own columns don't
1:1 match the PBI measure set either — no `RVU_Baseline` or `TBWU25_Baseline` column exists, only
`Shift_Baseline` (TBWU) and `Shift_Baseline_TBWU_2026`.

**UTF-16LE→UTF-8 `Report/Layout` conversion needs an explicit `encoding="utf-8"` on the Python
`open()` call, not just the `iconv` step.** The Impact `.pbix`'s converted layout JSON failed with
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d...` on a bare `open(path)` — Python was
falling back to the Windows box's default `cp1252` locale encoding rather than UTF-8, despite the
file already being correctly iconv-converted. Volume's and Efficiency's layout files happened not
to contain a byte sequence that triggered this, so the bug was latent until this third file. Fixed
globally in `extract_page.py`/`extract_page_compact.py` with `open(layout_file, encoding="utf-8")`
— apply this to any future `.pbix` layout extraction from the start rather than waiting to hit it
again.

## Numbers validation phase begins (2026-10-23) — all 3 metric views were reading stale data

Before putting the dashboard/app in front of C-suite, a validation pass started
(`tools/mosaic_validation/`, see its own README) to re-verify every flagged assumption from this
playbook against the live deployed objects, not just re-read the files. First check run (Volume's
row-count/fan-out sanity check) immediately surfaced the single biggest finding of the whole
migration so far:

**All 3 metric views were built on a frozen, drifting-stale snapshot, not live data.** Every one of
`mosaic_volume_metric_view`'s `source:`, `tbl_efficiency_exam_level_vw`'s `FROM`, and
`tbl_capacity_shift_level_vw`'s `FROM` pointed at `edw_test.enterprise_analytics.tbl_exam_inventory`
— which is a **materialized Delta table** (confirmed via `SHOW CREATE TABLE`: literally `CREATE
TABLE`, not a view/alias), independently copied into the test catalog at some point and never
refreshed since. Confirmed live: `edw_prod`'s copy had `MAX(final_datetime) = 2026-10-22` /
149,157,107 rows; `edw_test`'s had `MAX(final_datetime) = 2026-10-16` / 148,194,067 rows — 6 days
and 963,040 rows behind, and getting worse every day it went unnoticed. This affected every single
number on every page of both dashboards equally, independent of any individual measure's own
correctness.

**Fixed by repointing all three to `edw_prod.enterprise_analytics.tbl_exam_inventory` directly**
(user's explicit choice, over "add a refresh job" or "investigate why the copy exists first" — the
pragmatic case: no new copy to maintain, numbers are always current). Each of the other 4
referenced lookup/reference objects (`tbl_team_rollups`, `dynamics_rad_drafting_enablement_by_npi_
vw`, `tbl_mosaic_baseline_master`, `tbl_readtime_radiologist_metrics_shadow`) was individually
confirmed via `SHOW TABLES IN edw_prod.enterprise_analytics LIKE '...'` to **not exist in
`edw_prod` at all** — these are genuinely new, edw_test-only objects this migration itself created,
not stale copies of something live, so they were correctly left alone. One exception worth noting:
`tbl_exam_category_lookup_xwalk` exists in BOTH catalogs with identical row counts (969=969,
low-churn reference data) — Volume already joined the `edw_prod` copy, Efficiency/Capacity still
join the `edw_test` copy; harmless today given the identical count, but worth unifying later for
consistency.

**Lesson for any future metric-view work in this project**: when a metric view's `source:` or a
base view's `FROM` references an `edw_test`-schema object, don't assume it's a thin passthrough to
`edw_prod` just because the catalog name suggests "test env, same data underneath" — check with
`SHOW CREATE TABLE` whether it's actually a `CREATE TABLE` (a real, independently-aging copy) or a
`CREATE VIEW` (a live passthrough), and if it's the former, check `MAX()` on a date/timestamp column
against the `edw_prod` original before trusting it's current. This is the second time a confident-
sounding structural assumption about `edw_test` turned out to be wrong on direct inspection (the
first was the Capacity Local Region comment) — treat every `edw_test`-schema reference as "stale
until proven otherwise," not the reverse.

Full validation methodology, remaining checklist items, and per-report reports live in
`tools/mosaic_validation/` — see that directory's own `README.md`.

## Validation phases B and C complete (2026-10-23)

Efficiency and Capacity validated with the same discipline as Volume (live queries against
deployed objects, independent `mosaic_service.py` reconciliations). Full detail in
`tools/mosaic_validation/VALIDATION_REPORT_EFFICIENCY.md`/`_CAPACITY.md`/`VALIDATION_SUMMARY.md`.
Two things worth remembering for future sessions specifically:

**A previously-compiled risk checklist item was itself stale — `mosaic_service.py`'s
`_CAPACITY_SHIFT_CTE_SQL` no longer has the "unfixed read-time bug" it was flagged for.** Reading
the deployed backend code directly (not trusting an earlier research pass) showed it already
carries the identical LAG-based, 3600s-capped read-time fix, explicitly ported from
`tbl_capacity_shift_level_vw` (comment at that file's line ~523: "Fix 1 (read-time)... ported from
tbl_capacity_shift_level_vw (edw_test)"). The app and the metric view now use the same formula —
confirmed via a live reconciliation query (0.00014% residual, explained by one filter difference in
the hand-reconstruction). **Lesson**: a risk checklist compiled by reading files is itself a
snapshot — re-verify it against the live, current code before acting on it, the same discipline
applied to the metric views themselves.

**Capacity's Utilization 1.0 cap rate came back at 29.2% of shifts, not the ~92% previously
documented as an "expected upstream characteristic."** Ruled out a query-grain artifact (re-measured
at the true per-shift grain using `tbl_capacity_shift_level_vw` directly, including `task_id` — the
metric view itself has no `Task_ID` dimension, so querying utilization through it at NPI+Name+Date
grain would silently merge distinct shifts and give a wrong answer). Also ruled out "app still has
the old bug" per the point above. **Root cause not fully confirmed this pass** — most likely the
original ~92% figure was measured against the stale/frozen `edw_test` snapshot (same root cause as
the dashboard-wide staleness fix) or a narrower slice, but this wasn't independently proven. Flagged
in `VALIDATION_SUMMARY.md` as needing a second look from whoever ran the original measurement,
rather than silently overwriting one number with another on an assumption.

## Phase E: custom-app wiring (2026-10-23) — new Volume domain added, no Efficiency/Capacity code changes needed

New `/volume` tab added to the custom Databricks App, following `EfficiencyDetail.tsx`'s exact
shape: `backend/app/services/volume_service.py` (new module, kept physically separate from
`mosaic_service.py` per the plan — the governed-vs-legacy boundary stays visible at a glance),
6 new cached routes (`/api/mosaic/volume/summary|by-practice|by-team|by-local-region|trend|
filters`), registered in `refresh_service.DATASETS`, new `frontend/src/pages/VolumeDetail.tsx` +
`VolumeTrendChart.tsx`, new route + nav tab.

**Reused `mosaic_service.py`'s own `_RPCE_SOURCE_SYSTEMS_SQL`/`_RPCE_PCT_ADJUSTMENT` constants by
import rather than redefining them** — guarantees the app's Volume numbers and the Lakeview
dashboard's numbers can never silently drift apart on this specific adjustment, since both now
trace to the literal same Python constant. Local Region's CASE expression was copied verbatim from
the deployed metric view's YAML (confirmed identical 2026-10-23) since the app's service principal
can't reach `tbl_team_rollups` (edw_test-only) for a real `Team Rolled Up` join — that one grouping
was deliberately left out of the app's Volume page rather than faked.

**Verified the new Volume SQL against live `edw_prod` independently of the running app** (the
`efficiency_matrix` dataset ahead of it in the sequential refresh queue is slow enough — several
minutes, pre-existing, not something this phase introduced — that waiting for the full 44-dataset
refresh to reach the new entries wasn't practical this session): ran the exact SQL text pulled from
the deployed `volume_service.py` module directly against EDW and confirmed an **exact match** with
the already-validated dashboard numbers (`total_exams`: 149,157,107 both sides; `pct_rpce_reporting`/
`pct_rpce_drafting`: identical to 15 decimal places both sides).

**Caught three real bugs via this verification before/just after they shipped**, none visible from
reading the code casually:
1. `VolumeSummary`'s Pydantic model has no field defaults (matching the rest of the codebase's
   convention for required numeric fields) — but `get_volume_summary()` initially did
   `VolumeSummary(**(payload or {}))`, which would raise a validation error (not a graceful empty
   state) the moment this route is hit before the first refresh cycle completes. Confirmed live:
   hit exactly this failure mode on a fresh server start. Fixed with an explicit
   `_EMPTY_VOLUME_SUMMARY` dict, the same pattern `_empty_mosaic_intelligence_snapshot` already
   established elsewhere in `cache_service.py` — should have copied that convention from the start
   rather than assuming an empty dict would satisfy a model with no defaults.
2. The page's top `FilterBar` practice dropdown is populated from Managing Practice values, which
   only lines up with the "By Practice" grouping toggle — switching to "By Team" or "By Local
   Region" with a practice filter still applied would have silently filtered every row to nothing,
   since Team/Local-Region label sets don't overlap with Practice names. Fixed by only applying the
   practice filter when `groupBy === "practice"`.
3. **Found only after a real overnight refresh cycle, not by local reasoning**: the NULL-
   `final_datetime` bucket (~22.6M exams, same one confirmed identical on the Lakeview dashboard's
   own Final Month dimension in the Phase A write-up) reaches `get_volume_trend()` as a row with
   `period: None`. `VolumeTrendPoint.period` is typed `str` (no `| None`), so constructing that one
   model instance raised a Pydantic `ValidationError` that 500'd the *entire* `/volume/trend`
   endpoint — confirmed live via the actual stack trace after the real refresh populated the cache
   with that row. A `trend.data.filter((d) => d.period)` had already been added on the frontend
   during initial build, which hid the symptom in the one quick smoke-test done that session but
   did nothing for the real failure, since the crash happens server-side before any frontend code
   ever runs. Real fix: `WHERE final_datetime IS NOT NULL` in the query itself (a null period isn't
   a real calendar month, so excluding it from the trend specifically — not from
   `VolumeSummary`'s company-wide totals, which still count it — changes no KPI number), with the
   now-redundant frontend filter removed. **Lesson: a client-side filter patching over a "shouldn't
   happen" row is not a fix if the data never reaches the client in the first place — trace symptoms
   to where they actually originate before patching the first layer that happens to be visible.**

**Efficiency/Capacity reconciliation needed no code changes.** The plan called for a metric-by-
metric swap of `EfficiencyDetail`/`CapacityDetail`'s data sources for any measure confirmed to
match the governed views — but Phases B and C's reconciliation work already proved
`mosaic_service.py`'s existing `_MER_BASE_CTE_SQL`/`_CAPACITY_SHIFT_CTE_SQL` produce exact or
near-exact (0.00014%, explained) matches with the deployed metric views, using the SAME SQL shape
already. There was nothing to swap — the existing app code was already correct, just not yet
proven so until this validation pass.

**Still open, flagged not fixed**: the existing Genie Space (`mosaictechops` schema, `mv_mosaic_*`
views) doesn't cover any of the 3 new metric views or the new Volume domain — Genie-based natural-
language queries won't currently find Volume/Efficiency/Capacity data through that surface. A
separate decision, not resolved this phase.
