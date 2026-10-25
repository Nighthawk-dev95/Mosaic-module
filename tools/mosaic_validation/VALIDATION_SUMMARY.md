# Mosaic Validation — Cross-Report Summary (Phases A–C complete)

Full detail in `VALIDATION_REPORT_VOLUME.md` / `_EFFICIENCY.md` / `_CAPACITY.md`. This is the
roll-up for a quick read before Phase D (Lakeview polish) and Phase E (custom-app wiring).

## The one fix that mattered most: all 3 reports were reading stale data

Every metric view's base data was frozen in a 6-day-stale snapshot (`edw_test`'s copy of
`tbl_exam_inventory` was a materialized table, not a live passthrough to `edw_prod`). Fixed by
repointing all three source views directly at `edw_prod.enterprise_analytics.tbl_exam_inventory`.
This affected every number on every page equally, independent of any individual measure's
correctness — see Volume report, item 0.

## Resolved during validation

- **Allocated TBWU** (Volume) — user decided not to use it; deprecated on the view, confirmed not
  referenced on any dashboard page.

## Confirmed correct (exact or near-exact reconciliation against `mosaic_service.py`)

8 of 9 direct reconciliation checks across all three reports matched exactly; the 9th (Capacity's
`On Shift Cases`/`Read Minutes`) matched to 0.00014% — immaterial, explained by one omitted filter
in the hand-reconstruction, not a real discrepancy.

## Confirmed intentional divergences (will never match PBI/legacy numbers, by design — don't
"fix" these later)

- Volume: `Draftable`/`Drafted Exam Count` vs `mosaic_drafting_metric_vw` (different definitions)
- Efficiency: DAX modality-restriction symmetry (migrated version restricts both sides of
  "Drafting Only" to CR/CT; original PBI only restricted one side)

## Open items still needing a decision or deeper investigation

1. **Capacity's Utilization 1.0 cap rate: 29.2% now vs ~92% previously documented** — real,
   material, large swing. Root cause not fully confirmed this pass (ruled out grain artifacts and
   "app still has the old bug" — `mosaic_service.py` already carries the same fix). Most likely
   explanation is the original figure was measured on stale/narrower data, but this wasn't
   independently confirmed. **Recommend treating 29.2% as current and correct, but worth a second
   look from whoever ran the original ~92% measurement.**
2. **Efficiency's Readtimeview source table variant** (`tbl_readtime_radiologist_metrics_shadow`)
   — business question: is this the specific percentile/shadow variant actually wanted. Not
   resolvable from SQL.
3. **Volume's Modality "CR not XR" documentation** — confirmed FALSE as written (52,781 exams
   genuinely have `Modality = 'XR'`, plus other small stray values). Not fixed this pass (low
   volume, ~0.04% of exams) — just corrected the record so nobody relies on the "zero rows"
   guarantee.
4. **Volume's VRA Flag** — structurally sound (real native boolean, sane distribution), but
   semantic equivalence to the original PBI compound condition can't be confirmed without a live
   PBI comparison (the PBI authoring MCP connection has been down this session).
5. **Capacity's baseline coverage** — newly quantified: 56% of shifts have NO baseline match at
   all (`Baseline Type = None`). Not a bug, but worth surfacing on the dashboard itself (Phase D)
   so a capacity-vs-baseline number isn't read as applying to the whole population.

## What this means for Phase D/E

- Phase D should surface items 1, 3, 4, and 5 above directly on the relevant dashboard pages (text
  widgets near the KPI), not just in this report — an exec reading a number shouldn't have to find
  this file to know its caveats.
- Phase E's "same numbers, no discrepancy" goal is in good shape: every reconciliation check that
  could be run matched exactly or near-exactly. The two genuinely open questions (items 1 and 2
  above) should get resolved before any corresponding app page ships, not deferred indefinitely.
