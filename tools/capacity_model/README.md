# Radiologist Capacity Model — working directory

Consolidates every notebook/script involved in RP's real Mosaic capacity-baseline pipeline,
so this app's Capacity tab (`backend/app/services/mosaic_service.py`'s
`get_capacity_with_baseline()` / `get_baseline_proxy_detail()`, `cache_service.py`'s
`get_capacity_baseline_scorecard()`, `frontend/src/pages/CapacityDetail.tsx`) doesn't have to be
cross-referenced against a sibling Claude project's memory folder every time someone touches it.

Source of truth for all 8 files below (not copied here - these are large/binary and change
independently of this repo):
`C:\Users\bhargav.narasimhan\.claude\projects\C--Users-bhargav-narasimhan\memory\Mosaic Impact\`

**This is the one canonical working folder for the capacity model - drop updates here, same
filename, overwrite in place.** Confirmed 2026-09-29 that this convention is what keeps this
useful: an older duplicate (`MIR New Updated Baselines (2).ipynb`, sitting loose in `.claude`
root with a `Model_type` CASE-logic fix the `Mosaic Impact` copy didn't have yet) had gone
stale relative to this folder and has since been cleaned up - the copy in here now has that
fix. Don't recreate that problem: no `(2)`/`(1) (1)`-suffixed copies in other folders, one file
per notebook, always here.

## Pipeline, in dependency order

1. **`mosaic_rebaseline_notebook (1) (1).py`** (read in full) - the notebook that actually
   computes the "20% Mosaic utilization, 6 months prior" baseline period and writes `Exact`
   rows into `edw_dev.bipa_analytics.stg_mosaic_baseline_master`. See **Confirmed algorithm**
   below - this is the piece the earlier MIR-notebook research pass couldn't find (it doesn't
   live in that notebook at all).
2. **`Baselines Proxies.sql`** (read ~150 of ~1000+ lines - the setup/feature-engineering half)
   - similarity-matching pipeline that assigns a borrowed baseline to shifts the notebook above
   couldn't baseline directly (insufficient own history). Writes `Proxy` rows into the same
   master table, plus the full scored-candidate table
   `stg_mosaic_proxy_all_candidates_2026` our `get_baseline_proxy_detail()` reads directly.
3. **`Manual Review Baselines.ipynb`** (read in full) - exports the subset of ambiguous matches
   (`Baseline_Type = 'Manual Review'`, 51 shift-types / 82 rads as of the last run) to Excel
   with the top-5 ranked proxy candidates, color-coded, for a human manager to pick from.
4. **`Manual Review to Proxy Conversion.ipynb`** (read in full) - takes the manager's approved
   picks back out of that Excel file and converts those rows from `Manual Review` to `Proxy`
   in the master table. Confirms `Manual Review` is a transient queue state, not a permanent
   third category - don't assume it stays at whatever count you last observed.
5. **`SEAL Team Re-Baselining.ipynb`** (read in full) - parallel pipeline for SEAL Team,
   producing `edw_dev.bipa_analytics.stg_seal_baseline_master` (keyed by NPI + Onsite/Remote,
   not Task_ID). **Its own final cell documents an unfixed bug**: the downstream join meant to
   wire this into reporting compares raw task names against literal `'Remote'`/`'Onsite'`
   strings and never matches. SEAL also hasn't cut over from the old live
   `edw_prod.vra.stg_baselines_seal` yet - this is why v1 of our Capacity tab explicitly
   excludes SEAL Team rather than attempting a join to a table that isn't wired up on the
   source side either.
6. **`MIR New Updated Baselines.ipynb`** (read in full via a research agent) - a downstream
   reporting-view rebuild (`presentation_rpt_vra_capacity_enhancetest_vw`, staged in `edw_dev`,
   not yet promoted to the production view). Does NOT compute baselines - it's a consumer of
   `stg_mosaic_baseline_master`, and its main contribution is a join fix (fallback on
   normalized Shift_Name when exact Task_ID doesn't match) that recovers ~30K rows there. We
   didn't wait for this to be promoted - `get_capacity_with_baseline()` applies the same fix
   directly against the live production view.
7. **`mosaic_impact_report.yaml`** (targeted search) - confirms `RPWU` = `TBWU` as far as the
   Impact Report's own unit-toggle DAX is concerned (every "TBWU/Hour" option literally reads
   an `_RPWU_per_hour` column).
8. **`Mosaic_Master_Semantic_Contract (2).md`** and **`Adenikinju  Baseline.xlsx`** - **not
   read**. The first is the cross-model semantic contract (1.9MB); the yaml above already
   answered what we needed from the Impact Report specifically, and nothing so far suggested
   the other 5 models (Deployment/Feedback/Volume/Read Times/Efficiency) define capacity
   differently. The second is a single rad's (Adenikinju, NPI 1558758607) old manual baseline
   snapshot, referenced only as an illustrative comparison point in the SEAL notebook's own
   validation cell (explicitly "not a target to match" since the old snapshot used a different,
   pre-automation baseline window). Read either if a discrepancy shows up that these might
   explain.

## Confirmed algorithm (from file 1 above)

- **Utilization** = `SUM(mosaic_flag) / SUM(on_shift_flag)` per shift instance - case-count
  based, not TBWU-weighted.
- **Crossing date** = `MIN(ShiftDate)` where that shift's utilization first reaches `>= 0.20`.
- **Baseline window** = `[crossing_date - 6 months, crossing_date)`. Shifts before the window
  are `Pre-Baseline (Excluded)`; an NPI with no crossing date at all is
  `No Mosaic Crossing (Excluded)`; everything at/after the crossing date is `Current`.
- **Per-shift-type average**: grouped by `(NPI, ShiftName)` (resolved to the rad's *current*
  Team/Practice if they switched mid-window, not whatever practice a given historical shift
  happened to carry), averaged across every Baseline-labeled instance of that exact shift name.
- **Practice exclusion is per-radiologist, not per-shift**: an NPI with *any* shift tied to an
  excluded practice (`Matrix`, `RP East Florida`, `SEAL Team`, `RP North Florida`, `DRSRP`,
  `Spec Ops Reserve`, `RP Palm Beach`, `PRA`, `RP RAH`) gets **no Exact baseline at all**, even
  for shifts at a different, non-excluded practice. This is exactly why those practices show
  ~99-100% "no baseline" in our scorecard - working as designed upstream, not a bug in our join.
- **`Shift_Baseline_TBWU_2026` is Place-of-Service-adjusted**, not raw TBWU: each exam's TBWU is
  multiplied by an ER/IP/OP adjustment factor (`procedure_metrics_hist_dim_vw`'s `ER Adj`/
  `IP Adj`/`OP Adj` against `model_ref_place_of_service_classification_vw`) before averaging.
  Confirmed identically in both the main notebook and the SEAL notebook (which explicitly
  tracks raw vs. adjusted as two separate columns, `Shift_Baseline_TBWU` vs.
  `Shift_Baseline_TBWU_2026`, specifically to avoid collapsing them into the same number).

## POS-adjustment question - RESOLVED (2026-09-30)

User's call: `Shift_Baseline_TBWU_2026` (the Place-of-Service-adjusted value) is the correct,
current TBWU/RPWU convention to use - not a mismatch to fix. `get_capacity_with_baseline()`
already reads this field for the baseline side; no code change needed. Not chasing an
equivalent POS-adjustment for the live "actual capacity" side unless a future finding shows
it actually distorts numbers in practice.

## What our app actually does differently from any of the notebooks above

We don't re-run any of this pipeline - `stg_mosaic_baseline_master` and
`stg_mosaic_proxy_all_candidates_2026` are read as already-computed, trusted inputs. Our own
contribution is exactly one thing: re-homing the MIR notebook's join fix (exact NPI+Task_ID,
falling back to NPI+normalized Shift_Name) directly onto the *live* production view instead of
waiting for `presentation_rpt_vra_capacity_enhancetest_vw` to be promoted - verified live this
takes baseline coverage from 8.6% to 46.0% of shifts having a real baseline attached.
