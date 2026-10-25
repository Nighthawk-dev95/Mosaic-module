-- Validates edw_test.enterprise_analytics.mosaic_program_metric_view (tools/edw_fixes/033_*)
-- against plain SQL on its source table. Every row should show diff = 0.
-- Companion: validate_program.py runs the app's own mvp_dashboard_stats.py over the same rows
-- (independent implementation of the funnel/impact logic) and diffs against this view.

WITH mv AS (
  SELECT
    MEASURE(`Radiologists`)                   AS radiologists,
    MEASURE(`Cohort Radiologists`)            AS cohort_rads,
    MEASURE(`Actively Tracked Radiologists`)  AS active_rads,
    MEASURE(`Excluded Radiologists`)          AS excluded_rads,
    MEASURE(`Funnel Radiologists`)            AS funnel_rads,
    MEASURE(`Post Engagement Radiologists`)   AS post_rads,
    MEASURE(`Closed Completed Radiologists`)  AS closed_completed,
    MEASURE(`Escalated Radiologists`)         AS escalated,
    MEASURE(`Radiologists With L30D Change`)  AS with_l30d,
    MEASURE(`Median Full Mosaic L30D Change Pct`) AS median_l30d,
    MEASURE(`Latest Dynamics Activity`)       AS latest_activity
  FROM edw_test.enterprise_analytics.mosaic_program_metric_view
),
raw AS (
  SELECT
    COUNT(DISTINCT npi) AS radiologists,
    COUNT(DISTINCT IF(mvp_cohort IS NOT NULL, npi, NULL)) AS cohort_rads,
    COUNT(DISTINCT IF(exclusion_reason IS NULL, npi, NULL)) AS active_rads,
    COUNT(DISTINCT IF(exclusion_reason IS NOT NULL, npi, NULL)) AS excluded_rads,
    COUNT(DISTINCT IF(LEFT(optimization_support_status, 2) IN ('3 ','4 ','5 ','6 ','7 ','8 ','9 '), npi, NULL)) AS funnel_rads,
    COUNT(DISTINCT IF(LEFT(optimization_support_status, 2) IN ('6 ','7 ','8 ','9 '), npi, NULL)) AS post_rads,
    COUNT(DISTINCT IF(LEFT(optimization_support_status, 2) = '9 '
      AND NOT optimization_support_status RLIKE 'Declined Support|Resigning|Mentor Declined|Not Progressing', npi, NULL)) AS closed_completed,
    COUNT(DISTINCT IF(LEFT(optimization_support_status, 2) IN ('3 ','4 ','5 ','6 ','7 ','8 ')
      AND INSTR(optimization_support_status, 'Escalated') > 0, npi, NULL)) AS escalated,
    COUNT(DISTINCT IF(ABS(TRY_CAST(full_mosaic_change_l30d_pct AS DOUBLE)) <= 100, npi, NULL)) AS with_l30d,
    PERCENTILE(IF(ABS(TRY_CAST(full_mosaic_change_l30d_pct AS DOUBLE)) <= 100,
      TRY_CAST(full_mosaic_change_l30d_pct AS DOUBLE), NULL), 0.5) / 100 AS median_l30d,
    MAX(TRY_TO_TIMESTAMP(optimization_last_updated, 'M/d/yyyy h:mm a')) AS latest_activity
  FROM edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
)
SELECT 'radiologists' AS measure, mv.radiologists AS metric_view, raw.radiologists AS plain_sql, mv.radiologists - raw.radiologists AS diff FROM mv, raw
UNION ALL SELECT 'cohort_rads', mv.cohort_rads, raw.cohort_rads, mv.cohort_rads - raw.cohort_rads FROM mv, raw
UNION ALL SELECT 'active_rads', mv.active_rads, raw.active_rads, mv.active_rads - raw.active_rads FROM mv, raw
UNION ALL SELECT 'excluded_rads', mv.excluded_rads, raw.excluded_rads, mv.excluded_rads - raw.excluded_rads FROM mv, raw
UNION ALL SELECT 'funnel_rads', mv.funnel_rads, raw.funnel_rads, mv.funnel_rads - raw.funnel_rads FROM mv, raw
UNION ALL SELECT 'post_rads', mv.post_rads, raw.post_rads, mv.post_rads - raw.post_rads FROM mv, raw
UNION ALL SELECT 'closed_completed', mv.closed_completed, raw.closed_completed, mv.closed_completed - raw.closed_completed FROM mv, raw
UNION ALL SELECT 'escalated', mv.escalated, raw.escalated, mv.escalated - raw.escalated FROM mv, raw
UNION ALL SELECT 'with_l30d', mv.with_l30d, raw.with_l30d, mv.with_l30d - raw.with_l30d FROM mv, raw
UNION ALL SELECT 'median_l30d_x10000', ROUND(mv.median_l30d * 10000), ROUND(raw.median_l30d * 10000), ROUND((mv.median_l30d - raw.median_l30d) * 10000) FROM mv, raw
UNION ALL SELECT 'latest_activity_epoch', UNIX_TIMESTAMP(mv.latest_activity), UNIX_TIMESTAMP(raw.latest_activity), UNIX_TIMESTAMP(mv.latest_activity) - UNIX_TIMESTAMP(raw.latest_activity) FROM mv, raw;
