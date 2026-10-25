# Mosaic Efficiency — Validation Report (Phase B)

Run 2026-10-23, live against `edw_test.enterprise_analytics.mosaic_efficiency_metric_view` and
`mosaic_efficiency_vs_rp_avg_metric_view` (both already repointed to live `edw_prod` data in Phase
A's stale-source fix).

## High-risk items

1. **Qualification/min-exams gate — CONFIRMED CORRECT, no-op only at the default.**
   `Full Mosaic Mosaic Exams`: 14,911,601 at `min_exams=1`, 14,905,663 at `min_exams=100` (small,
   real drop), **13,259,329 at `min_exams=5000`** (11% drop — clearly material). Confirms the gate
   genuinely filters out low-volume radiologists once set high enough; it only looks like a no-op
   at the trivial default threshold because "has at least 1 exam" is true for nearly everyone in an
   already-qualifying population. Behaves exactly as intended.

2. **Fixed-LOD RP-average benchmark — CONFIRMED CORRECT.** `SELECT DISTINCT` on
   `Full Mosaic RP Avg Efficiency`, grouped by `Team Rolled Up`, returns exactly 1 distinct value.
   The `ANY_VALUE()`-over-unpartitioned-window pattern is doing what it's supposed to: one constant
   company-wide number regardless of query grouping.

3. **DAX modality-restriction symmetry — CONFIRMED correctly implemented as the deliberate fix.**
   Read the deployed YAML directly: `Drafting Mosaic Exams`/`Drafting Own Exams` (individual side)
   both filter `modality_code IN ('CR', 'CT')`; the `rp_avg_drafting_tbwu`/`rp_avg_drafting_time`
   source columns (population/benchmark side) apply the identical restriction. Both sides are
   symmetric in the migrated version — **this means migrated numbers will NOT match the original
   PBI DAX's own (asymmetric) numbers for "Drafting Only," by design.** CONFIRMED INTENTIONAL
   DIVERGENCE, correctly implemented.

4. **`Efficiency Vs RP Avg` ratio-not-percentage framing — CONFIRMED CORRECT on the dashboard.**
   Checked the live `serialized_dashboard` JSON directly: every `*Efficiency Vs RP Avg` column uses
   `"format": {"type": "number", ...}`, never `"number-percent"`. Displayed as a plain ratio
   (`"Vs RP Avg (1.0 = average)"`), not a mis-formatted percentage.

5. **RP Avg qualification population fixed at view-definition time — confirmed by design, not a
   bug.** The `>= 1` gate inside `rp_avg_*` column computation (in
   `tbl_efficiency_rp_avg_source_vw`) is baked into the SQL at the view layer, not exposed as a
   runtime parameter the way `min_exams` is on the individual side. This is consistent with the
   view's own documented intent (a fixed, stable company benchmark) — not re-litigated here, just
   confirmed the behavior matches what was designed.

6. **Team/Practice conflation — CONFIRMED genuinely distinct, not conflated.** Found real,
   substantial divergent populations (Matrix/ESR Long Island: 241K exams; DR/Red Rock: 168K exams;
   SEAL Team/ESR Metro Hudson: 132K exams) — same pattern as Volume's equivalent check in Phase A.

7. **Readtimeview source table variant (`tbl_readtime_radiologist_metrics_shadow`) — still OPEN,
   needs business/user confirmation.** This is a business question ("is this the percentile/shadow
   variant you actually want represented"), not something re-derivable from SQL alone. Not resolved
   this pass — flagged for the user explicitly.

## Reconciliation against `mosaic_service.py` (full exam-level CTE chain)

Reconstructed `_MER_BASE_CTE_SQL` + `_MER_BASELINE_CTE_SQL` **verbatim from the Python source** (not
from reading the deployed view's SQL) and ran it directly against `edw_prod`, independent of the
metric view entirely. Compared against the metric view's own measure at `min_exams=1`:

| | Reconstructed raw CTE | `mosaic_efficiency_metric_view(1)` | Match |
|---|---|---|---|
| Reporting Mosaic Exams | 7,826,125 | 7,826,125 | Exact |
| Reporting Mosaic TBWU | 7,895,061.5104 | 7,895,061.5104 | Exact |

Both rows and TBWU sum match exactly, computed via two independently-written queries against the
same live table — the strongest confirmation available without a live PBI comparison.

## Disposition summary

| Disposition | Count |
|---|---|
| CONFIRMED CORRECT | 4 |
| CONFIRMED INTENTIONAL DIVERGENCE | 1 (DAX modality-restriction symmetry) |
| Confirmed by design (not re-litigated) | 1 (RP Avg fixed qualification population) |
| OPEN — needs business/user input | 1 (Readtimeview source variant) |
| **Exact reconciliation matches (full CTE chain)** | **2 / 2** |
