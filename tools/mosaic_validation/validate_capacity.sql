-- Mosaic Capacity validation queries (Phase C).
-- Run live against edw_test.enterprise_analytics.mosaic_capacity_metric_view and
-- tbl_capacity_shift_level_vw (repointed to live edw_prod data as part of Phase A).
-- See VALIDATION_REPORT_CAPACITY.md for results and dispositions.

-- 1. Local Region cross-view diff (highest priority -- the view that already lied once in an
-- earlier phase). Real join across Volume/Efficiency/Capacity on overlapping Team values.
WITH vol AS (
  SELECT DISTINCT Team, `Local Region` AS lr_vol FROM edw_test.enterprise_analytics.mosaic_volume_metric_view() GROUP BY ALL
),
eff AS (
  SELECT DISTINCT Team, `Local Region` AS lr_eff FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view() GROUP BY ALL
),
cap AS (
  SELECT DISTINCT Team, `Local Region` AS lr_cap FROM edw_test.enterprise_analytics.mosaic_capacity_metric_view() GROUP BY ALL
)
SELECT v.Team, v.lr_vol, e.lr_eff, c.lr_cap
FROM vol v JOIN eff e ON e.Team = v.Team JOIN cap c ON c.Team = v.Team
WHERE v.lr_vol != e.lr_eff OR v.lr_vol != c.lr_cap OR e.lr_eff != c.lr_cap;
-- RESULT: 0 rows. All 3 views resolve Local Region identically for every overlapping Team.

-- 2. Rate-column SUM/SUM discipline: confirmed by reading the deployed YAML directly -- every
-- rate measure (On Shift Capacity RPWU Per Hour, Shift Baseline RPWU Per Hour, Pct Exams With
-- Valid Read Time, On Shift Utilization Pct, On Shift Efficiency RPWU) composes via
-- MEASURE(numerator)/MEASURE(denominator), never a pre-divided row average.

-- 3. Utilization 1.0 cap distribution -- re-measured at the TRUE per-shift grain (base view, not
-- the metric view, since the metric view has no Task_ID dimension and would silently merge
-- distinct shifts sharing the same NPI/Name/Date).
WITH per_shift AS (
  SELECT npi, shift_date, shift_name, task_id,
    LEAST(shift_read_minutes / (no_hours * 60), 1.0) AS utilization
  FROM edw_test.enterprise_analytics.tbl_capacity_shift_level_vw
  WHERE no_hours > 0
)
SELECT COUNT(*) AS total_shifts, COUNT(CASE WHEN utilization >= 1.0 THEN 1 END) AS capped_shifts,
  ROUND(COUNT(CASE WHEN utilization >= 1.0 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_capped
FROM per_shift;
-- RESULT: 29.2% capped (331,312 of 1,134,005 shifts) -- see report for the discrepancy vs the
-- previously-documented ~92% figure.

-- 4. Dictation-timestamp coverage unevenness -- reconfirm RP Valley exception.
SELECT Practice, `Is RPCE Source`, MEASURE(`Pct Exams With Valid Read Time`) AS pct_valid, MEASURE(`On Shift Cases`) AS cases
FROM edw_test.enterprise_analytics.mosaic_capacity_metric_view()
WHERE Practice IN ('RP Valley', 'RASF')
GROUP BY ALL;

-- 5. Baseline tiering distribution.
SELECT `Baseline Type`, MEASURE(`On Shift Cases`) AS shift_cases
FROM edw_test.enterprise_analytics.mosaic_capacity_metric_view()
GROUP BY ALL;

-- 6. CR/XR labeling reversal: confirm Capacity's xr_cases column literally counts modality_code='CR'.
SELECT SUM(ct_cases) AS CT_Cases, SUM(xr_cases) AS XR_Cases FROM edw_test.enterprise_analytics.tbl_capacity_shift_level_vw;

-- 7. Rad Equivalents/Annualized Capacity Increase and baseline-period case-mix: confirmed still
-- absent from the measure list (checked via SHOW CREATE TABLE, not re-derived in SQL here).

-- 8. Reconciliation: tbl_capacity_shift_level_vw vs mosaic_service.py's _CAPACITY_SHIFT_CTE_SQL,
-- reconstructed verbatim and run independently -- see reconcile_against_mosaic_service.sql.
