# Mosaic Executive Dashboard — PBI parity sign-off (Capacity)

Checked 2026-10-26. Month: September 2026, company-wide.

- **Reference:** PowerBI Desktop, Mosaic Impact Report, *Practice Summary* page at its saved defaults
  (Unit = TBWU 26/Shift, Shifts with Baselines, report shift-length filter, Rank_TopN = All Shifts,
  visual filter `Has_Baseline_For_Selected_Unit` = 1). PBI model last refreshed **2026-10-12**.
- **Databricks:** dashboard dataset `tools/lakeview_exec_dashboard/capacity_practice_summary.sql`
  over `edw_test.enterprise_analytics.mosaic_capacity_pbi_shift_vw` (044a). Genie reads the same rows
  through `mosaic_capacity_pbi_metric_view` (044b). Both use identical measure definitions.
- Measure definitions are in `kpi_registry.yaml` → `capacity`.

| KPI (PBI name) | PBI | Databricks | Diff | Status |
|---|---:|---:|---:|---|
| Selected Shift Ct | 19,551 | 18,021 | −1,530 | DATA DRIFT |
| Average Baseline | 65.52 | 64.10 | −1.42 | DATA DRIFT |
| New Capacity | 72.43 | 71.40 | −1.03 | DATA DRIFT |
| Add'l Capacity/Shift | +6.91 | +7.30 | +0.39 | DATA DRIFT |
| % Add'l Capacity | 10.55% | 11.39% | +0.84pp | DATA DRIFT |
| % Mosaic | 92.2% | 90.4% | −1.8pp | DATA DRIFT |
| % Mosaic Drafting | 49.6% | 47.3% | −2.3pp | DATA DRIFT |
| New Efficiency | 0.259 | 0.295 | +0.036 | DATA DRIFT |
| New Utilization | 63.4% | 54.6% | −8.8pp | DATA DRIFT |

## Disposition: logic MATCH, residuals are DATA DRIFT

The SQL reproduces each DAX measure (per-shift AVERAGEX, efficiency > 1 ignored, SUM/SUM case shares,
group-level baseline visual filter). Shifts that have the same source data in both systems give the same
baseline and capacity. The remaining differences come from the data, not the logic:

1. **Stale PBI model.** PBI was last refreshed 2026-10-12. Databricks reads the current upstream view.
2. **Upstream read-time fix.** The `ref_exam_adjusted_readtime` island-merge fix landed after the PBI
   refresh. It changes per-shift read time, so efficiency and utilization move even on shifts that are
   otherwise identical. Example: Jefferson's shifts match one-for-one, but their efficiency and
   utilization differ. This is the expected direction: false mega-islands no longer inflate utilization.
3. **Matrix lost its TBWU 26 baselines upstream.** PBI had 1,724 Matrix shifts at an average baseline of
   83.92. The current source has no TBWU 26 baseline for Matrix, so the visual filter drops the whole
   practice. That accounts for most of the shift-count gap and the lower average baseline.
   **Raise with the EDW team.**

**To close fully:** refresh the PBI model (only with the user's go-ahead) and re-run this comparison. The
expected result is MATCH apart from Matrix.

## Known intentional divergence

- **Time Series page.** PBI's capacity Time Series page uses utilization at the RPWU25_per_9hours unit with
  Data Quality = Good. The dashboard uses the Practice Summary definition (TBWU 26/Shift) on every
  capacity widget, so the trend lines agree with the counters.
- **Trend start.** Trend lines begin in Jan 2024. Dec 2023 holds stub data only.
