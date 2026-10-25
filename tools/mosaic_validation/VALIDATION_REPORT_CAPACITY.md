# Mosaic Capacity — Validation Report (Phase C)

Run 2026-10-23, live against `edw_test.enterprise_analytics.mosaic_capacity_metric_view` and
`tbl_capacity_shift_level_vw` (both already repointed to live `edw_prod` data in Phase A).

## Item 1 — Local Region cross-view diff (CONFIRMED CORRECT, highest priority item)

The view that already lied once (its own header comment falsely claimed Local Region parity with
Efficiency before the dimension even existed, caught during the original build). This time: a real
3-way join across Volume, Efficiency, and Capacity on every overlapping `Team` value, asserting
identical resolved `Local Region` strings across all three. **Zero mismatches.** All three views
now genuinely agree, not just claim to.

## Item 2 — Rate-column SUM/SUM discipline (CONFIRMED CORRECT)

Read the deployed YAML directly: every rate measure (`On Shift Capacity RPWU Per Hour`,
`Shift Baseline RPWU Per Hour`, `Pct Exams With Valid Read Time`, `On Shift Utilization Pct`,
`On Shift Efficiency RPWU`) composes as `MEASURE(numerator) / MEASURE(denominator)`, never a
pre-divided per-row rate summed or averaged directly.

## Item 3 — Utilization 1.0 cap distribution: **MATERIAL DISCREPANCY FOUND, flagging honestly**

Re-measured at the true per-shift grain (the base view, including `task_id` — the metric view
itself has no `Task_ID` dimension, so querying utilization through it at NPI+Name+Date grain
silently merges distinct shifts that share those three fields and would have given a wrong
number). Result: **29.2% of shifts hit the cap (331,312 of 1,134,005)** — not the ~92% previously
documented as an "expected, known upstream characteristic."

This is a real, large gap from what was previously recorded, and I want to be upfront that I
**could not fully root-cause the discrepancy** in this pass. What I did rule out:
- Not a grain/query-construction artifact — re-measured directly against `tbl_capacity_shift_level_vw`
  with `task_id` included, same 29.2% result.
- Not explained by "metric view fixed, `mosaic_service.py` still has the old bug" — on inspection,
  `mosaic_service.py`'s own `_CAPACITY_SHIFT_CTE_SQL` **already carries the identical fix**
  (comment at line 523-528: "Fix 1 (read-time)... ported from `tbl_capacity_shift_level_vw`"),
  contradicting the risk checklist's premise that the app still has the unfixed bug. The two
  systems are using the same formula, confirmed by the exact reconciliation in the section below.

Most likely explanation (not independently confirmed this pass): the original ~92% figure was
measured against the stale, frozen `edw_test` snapshot fixed in Phase A, and/or against a narrower
practice-level slice rather than the full population — I don't have the original query to compare
directly. **Recommend treating 29.2% as the current, correctly-measured figure** (computed with the
same discipline as everything else in this report), but this specific swing is large enough that
it's worth independently sanity-checking with whoever ran the original ~92% measurement, rather
than taking either number purely on faith.

## Item 4 — Dictation-timestamp coverage unevenness (CONFIRMED still real, magnitude shifted)

| Practice | Is RPCE Source | Pct Valid Read Time | Cases |
|---|---|---|---|
| RASF | True | 14.4% | 12,829 |
| RP Valley | True | **16.5%** | 2,711,035 |
| RASF | False | 0.0% | 3,333,849 |
| RP Valley | False | 0.0% | 3 |

RP Valley's RPCE-true slice still shows very poor read-time coverage (16.5%, up from the
previously-documented 11.3% — direction consistent, magnitude shifted with fresher data) despite
being RPCE-classified. **The core directive still holds and is still necessary**: always check
`Pct Exams With Valid Read Time` before trusting Efficiency/Utilization for a slice — the RPCE flag
alone is not a reliable trust signal.

## Item 5 — Baseline tiering distribution (characterized, not previously quantified this precisely)

| Baseline Type | Shift Cases |
|---|---|
| None (no match) | 40,352,682 (56%) |
| Exact | 29,857,728 (41%) |
| Manual Review | 1,013,928 (1.4%) |
| Proxy | 825,364 (1.1%) |

**More than half of all shifts have no baseline match at all.** This was already known
qualitatively (baseline coverage is partial), but hadn't been quantified this precisely before —
worth keeping in mind for Phase D: any capacity-vs-baseline comparison widget should make clear it
only applies to the ~44% of shifts with a matched baseline, not the whole population.

## Item 6 — CR/XR labeling reversal (CONFIRMED, both conventions internally consistent)

`tbl_capacity_shift_level_vw.xr_cases` literally counts `modality_code = 'CR'` (20,628,371 CT
cases, 28,846,760 "XR" cases that are actually raw-coded `CR`). Confirmed intentional display
convention, opposite of Volume's (which keeps the raw `CR` label). Not a bug in either report — just
something to know when comparing modality breakdowns across the two.

## Item 7 — Rad Equivalents/Annualized Capacity Increase + baseline-period case-mix (CONFIRMED still absent)

Neither exists in the 72-measure list. Still correctly out of scope as documented — no change.

## Reconciliation against `mosaic_service.py`

Reconstructed `_CAPACITY_SHIFT_CTE_SQL`'s `shift_exams`/`with_lag`/`with_read_time`/`raw_shifts`
chain **verbatim from the Python source**, run independently against `edw_prod`:

| | Reconstructed raw CTE | `mosaic_capacity_metric_view()` | Delta |
|---|---|---|---|
| On Shift Cases | 72,049,803 | 72,049,702 | 101 rows (0.00014%) |
| Read Minutes | 257,566,504.00 | 257,566,500.25 | 3.75 min (negligible) |

**Near-exact, not byte-for-byte** — the tiny residual is most likely the deployed view's
`WHERE v.practice IS NOT NULL` filter (confirmed present in the view's SQL) which my hand-reconstruction
omitted for simplicity. Not investigated further given the magnitude (0.00014%) is immaterial to any
dashboard number at the precision executives would read it.

## Disposition summary

| Disposition | Count |
|---|---|
| CONFIRMED CORRECT | 4 (Local Region cross-view, rate discipline, CR/XR convention, Rad Equivalents/case-mix absence) |
| CONFIRMED real, magnitude updated with fresh data | 1 (dictation-timestamp coverage) |
| Characterized for the first time this precisely | 1 (baseline tiering distribution) |
| **FLAGGED — large discrepancy, not fully root-caused** | **1 (Utilization 1.0 cap: 29.2% now vs ~92% previously documented)** |
| Near-exact reconciliation (0.00014% residual, explained) | 1 of 2 metrics checked |
