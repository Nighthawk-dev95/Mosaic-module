# Mosaic validation

Companion to `tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md` — that file documents how the 3
Mosaic metric views (Volume, Efficiency, Capacity) were built; this directory re-verifies the
result against the live deployed objects, ahead of putting them in front of C-suite/execs who need
to trust the numbers.

## Why a separate directory, and why live queries only

Every check here runs against the **deployed** `edw_test.enterprise_analytics` objects (via
`databricks experimental aitools tools query` or the `mcp__databricks-edw__query_edw` tool) — never
inferred from re-reading SQL/TMDL files or comments. The Capacity "Local Region" incident during
migration (a confident header COMMENT claimed parity with a sibling view; `SHOW CREATE TABLE`
proved the dimensions didn't exist at all) is proof that documentation can be wrong even when it
reads as authoritative. The stale-source-data finding below is a second, larger proof of the same
principle.

## Files

- `validate_volume.sql` / `VALIDATION_REPORT_VOLUME.md` — Phase A
- `validate_efficiency.sql` / `VALIDATION_REPORT_EFFICIENCY.md` — Phase B (not yet run)
- `validate_capacity.sql` / `VALIDATION_REPORT_CAPACITY.md` — Phase C (not yet run)
- `reconcile_against_mosaic_service.sql` — direct metric-view-vs-`mosaic_service.py` diffs, shared
  across all 3 phases, appended to as each phase runs
- `VALIDATION_SUMMARY.md` — cross-report roll-up (written after Phase C)

## Disposition convention

Every checked item gets exactly one of:
- **CONFIRMED CORRECT** — re-verified live, matches expectation
- **CONFIRMED BUG** — real defect found; fixed inline (new `tools/edw_fixes/0NN_*.sql` if the fix
  is small) or flagged as OPEN if it needs a business call first
- **CONFIRMED INTENTIONAL DIVERGENCE** — migrated number will never match the original PBI/
  `mosaic_service.py` number, by design — documented so it's never mistaken for a bug later
- **OPEN — needs a decision** — real, material finding that only the business/user can resolve

## Headline finding so far (Phase A)

All 3 metric views' base data was frozen in a stale `edw_test` snapshot of `tbl_exam_inventory` (6
days / 963K rows behind live `edw_prod`, compounding daily) — fixed by repointing all three source
views/metric views at `edw_prod.enterprise_analytics.tbl_exam_inventory` directly. See
`VALIDATION_REPORT_VOLUME.md` item 0 for full detail.
