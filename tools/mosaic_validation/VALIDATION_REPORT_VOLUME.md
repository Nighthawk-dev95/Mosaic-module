# Mosaic Volume — Validation Report (Phase A)

Run 2026-10-23, live against `edw_test.enterprise_analytics.mosaic_volume_metric_view` and the
`edw_prod.enterprise_analytics.tbl_exam_inventory` base table it sources from (post-fix — see item
0). Every query in `validate_volume.sql` was executed against the deployed objects, not inferred
from reading SQL files. Dispositions: **CONFIRMED CORRECT** / **CONFIRMED BUG** (fixed or flagged)
/ **CONFIRMED INTENTIONAL DIVERGENCE** / **OPEN — needs a decision**.

## Item 0 — Stale source data (CONFIRMED BUG, FIXED)

`mosaic_volume_metric_view`'s `source:` pointed at `edw_test.enterprise_analytics.tbl_exam_inventory`
— a **frozen materialized Delta table**, not a live view into prod. Confirmed live:

| | max(final_datetime) | row count |
|---|---|---|
| `edw_prod.enterprise_analytics.tbl_exam_inventory` | 2026-10-22 | 149,157,107 |
| `edw_test.enterprise_analytics.tbl_exam_inventory` (before fix) | 2026-10-16 | 148,194,067 |

6 days / 963,040 rows stale, compounding daily. **This affected Efficiency's and Capacity's source
views too** (`tbl_efficiency_exam_level_vw`, `tbl_capacity_shift_level_vw` both read the same
frozen `edw_test` copy) — same fix applied to all three as part of this phase, per user direction.
Confirmed the 4 join/lookup tables each view also references (`tbl_team_rollups`,
`dynamics_rad_drafting_enablement_by_npi_vw`, `tbl_mosaic_baseline_master`,
`tbl_readtime_radiologist_metrics_shadow`) do **not** exist in `edw_prod` at all — they're
genuinely new, edw_test-only reference objects from this migration, not stale copies of something
live, so they were left alone. `tbl_exam_category_lookup_xwalk` exists in both catalogs with
identical row counts (969=969) — low-churn reference data, not meaningfully stale, left as-is for
now (minor consistency note: Volume joins the `edw_prod` copy, Efficiency/Capacity join the
`edw_test` copy of this same lookup — harmless today, worth unifying eventually).

**Fix applied**: `mosaic_volume_metric_view`'s `source:` repointed to
`edw_prod.enterprise_analytics.tbl_exam_inventory`. Post-fix Exam Count now **exactly** matches a
raw `COUNT(*)` on the live prod table (149,157,107 = 149,157,107) — confirms no fan-out from the 3
sibling joins either (see item 7 below, superseded by this fix).

## High-risk items

1. **`Allocated TBWU` (`allocated_tbwu_current` vs plain `allocated_tbwu`) — RESOLVED: measure not
   used.** These are NOT interchangeable: 7,413,486 of 147,789,323 rows (5.0%) differ between the
   two columns, netting a **-569,603 (-0.44%) delta** in the summed total (`allocated_tbwu_current`
   sums lower) — a real, measurable modeling choice, not a rounding artifact. Rather than pick a
   variant, the user decided this measure isn't needed. Confirmed it isn't referenced on any
   deployed dashboard page (`lakeview get` + search for the string returned no matches), so no
   widget changes were needed. Marked deprecated on the metric view itself (see
   `tools/edw_fixes/032_mosaic_volume_metric_view_deprecate_allocated_tbwu_FLOW.sql`) so a future
   session doesn't pick it back up without knowing about the discrepancy.

2. **`Modality` "CR not XR" — CONFIRMED BUG IN DOCUMENTATION, not in the view itself.** The
   playbook's own claim ("a filter written against 'XR' matches zero rows") is **false**: live data
   has 52,781 exams with `Modality = 'XR'` literally, plus several other unnormalized stray values
   (`MRI`: 2,065, `Ultrasound`: 10, `Mammography`: 6, `Plain Film/ Xray/ CR`: 3, `PET`: 1, `BM`: 26).
   Small in volume (~0.04% of 148M total) but real — any filter written against only `'CR'` for
   plain film silently drops these rows. Recommend either normalizing these stray values into their
   canonical codes in a future fix, or at minimum correcting the misleading comment so nobody
   trusts the "zero rows" guarantee.

3. **`Drafted But Not Enabled` counts — CONFIRMED the documented bug fix is live.** Scoped
   (`drafting_model IS NOT NULL`) count is 257,995 against a total of 8,715,460 unscoped
   `mosaic_draft_flag=TRUE` exams — small, sane fraction, consistent with the fix being in place
   (the pre-fix bug inflated this toward the unscoped total).

4. **`Draftable`/`Drafted Exam Count` vs `mosaic_drafting_metric_vw` — CONFIRMED INTENTIONAL
   DIVERGENCE, as documented.** Volume: 92,765,958 draftable / 8,704,512 drafted. 
   `mosaic_drafting_metric_vw`: 11,047,736 draftable / 8,436,039 drafted. The ~8.4x gap on
   "draftable" is expected — Volume's definition is "RPID maps to any known drafting category,"
   `mosaic_drafting_metric_vw` layers on practice-in-program + rad-enrolled gates on top. Not a bug.

5. **`VRA Flag` — CONFIRMED STRUCTURALLY SOUND, PBI semantic equivalence unverified.** It's a real
   native boolean column (`source.VRA_Flag`, not a derived compound condition), with a sane
   distribution (144,476,522 False / 4,680,585 True, ~3.1%). Whether this native column is a
   faithful stand-in for the PBI compound condition it replaces can't be confirmed without a live
   PBI comparison — flagged as pending once the PBI authoring MCP connection is back.

6. **`Care Setting` — proxy gap characterized, not resolved (matches documented caveat).**
   Distribution: Outpatient 62.6M, ED 51.3M, Inpatient 23.6M, **NULL 6.4M (4.3%)**, Pre-Admit 3.2M,
   Observation 685K, Unknown 268K, Recurring Patient 86K. Confirms this is a real, non-trivial
   population with no PBI `Place_Of_Service_Name` equivalent — not something this validation pass
   can resolve, just confirms the gap's actual size.

7. **`AD Group Added Date` join — CONFIRMED CORRECT, no fan-out risk.**
   `dynamics_rad_drafting_enablement_by_npi_vw` is genuinely unique on `npi` (0 rows with
   `COUNT(*) > 1`), so the MIN()-collapse business-meaning change (earliest AD-group date across
   ANY category, not the specific exam's category) is the only caveat here — the join itself is
   safe.

8. **`Practice` vs `Managing Practice` — CONFIRMED genuinely distinct, not conflated.** Found real,
   substantial populations where `Team != Managing Practice` (e.g. Synergy/RP North Houston: 863K
   exams; Matrix/RP SoCal: 718K exams; SEAL Team/ESR Metro Hudson: 472K exams) — confirms these are
   NOT accidentally collapsed into one column anywhere in this view, addressing the cross-report
   conflation risk flagged during the Efficiency build.

9. **`working_subspecialty` — CONFIRMED still absent**, as previously documented. Not plumbed into
   the view's dimension list.

10. **Row-count/fan-out across the 3 sibling joins — CONFIRMED CORRECT post-fix** (superseded by
    item 0 — see above, exact match once pointed at live prod data).

## Reconciliation against `mosaic_service.py` (5/5 CONFIRMED EXACT MATCH)

All five items already claimed to match `mosaic_service.py`'s own raw SQL reconciled **exactly** —
see `reconcile_against_mosaic_service.sql` for the paired queries:

| Measure | Metric view | Raw `mosaic_service.py` formula | Match |
|---|---|---|---|
| Is RPCE Source | True 103,187,543 / False 45,969,564 | same | Exact |
| Pct RPCE Reporting | 0.204008877893333 | same | Exact |
| Pct RPCE Drafting | 0.104462327007825 | same | Exact |
| Estimated RVU | 131,504,043.72 | same | Exact |
| TBWU | 111,894,093.2556 | same | Exact |
| Reporting Status (Drafting/Reporting/Baseline) | 8,715,460 / 10,271,964 / 130,169,683 | same | Exact |

## Not independently re-verifiable this pass

- **Green conditional-formatting threshold** on Volume's own pages — requires a visual check in
  the Lakeview UI, not a SQL query. Deferred to Phase D.
- **`DRAFT STATUS: not yet executed, not yet reviewed`** banner — this validation pass IS that
  review. Recommend updating the view's header comment to reflect that Phase A validation has run
  (see Phase D for the actual comment edit, bundled with other dashboard-facing caveat text).

## Disposition summary

| Disposition | Count |
|---|---|
| CONFIRMED CORRECT | 6 |
| CONFIRMED BUG, FIXED | 1 (stale source — item 0) |
| CONFIRMED BUG IN DOCUMENTATION (not the view) | 1 (Modality CR/XR) |
| CONFIRMED INTENTIONAL DIVERGENCE | 1 (Draftable vs mosaic_drafting_metric_vw) |
| RESOLVED — decided not to use | 1 (Allocated TBWU) |
| Unverifiable without live PBI | 1 (VRA Flag semantic equivalence) |
| Documented gap, not actionable this pass | 2 (Care Setting proxy, working_subspecialty) |
| Deferred to Phase D (visual, not SQL) | 1 (conditional formatting) |
| **Exact reconciliation matches** | **5 / 5** |
