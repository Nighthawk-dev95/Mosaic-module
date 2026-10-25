-- Mosaic Efficiency validation queries (Phase B).
-- Run live against edw_test.enterprise_analytics.mosaic_efficiency_metric_view and
-- mosaic_efficiency_vs_rp_avg_metric_view (both repointed to live edw_prod data as part of Phase A).
-- See VALIDATION_REPORT_EFFICIENCY.md for results and dispositions.

-- 1. Qualification/min-exams gate: confirm it's a no-op at the default (1) but has real effect at
-- higher thresholds.
SELECT MEASURE(`Full Mosaic Mosaic Exams`) AS exams_at_1 FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view(1);
SELECT MEASURE(`Full Mosaic Mosaic Exams`) AS exams_at_100 FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view(100);
SELECT MEASURE(`Full Mosaic Mosaic Exams`) AS exams_at_5000, MEASURE(`Full Mosaic Mosaic Efficiency`) AS eff_at_5000
FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view(5000);

-- 2. Fixed-LOD RP-average benchmark: confirm exactly 1 distinct value regardless of grouping.
SELECT COUNT(DISTINCT ROUND(rp_avg, 6)) AS distinct_values FROM (
  SELECT `Team Rolled Up`, MEASURE(`Full Mosaic RP Avg Efficiency`) AS rp_avg
  FROM edw_test.enterprise_analytics.mosaic_efficiency_vs_rp_avg_metric_view()
  GROUP BY ALL
);

-- 3. DAX modality-restriction symmetry: confirm BOTH the individual (Own) and population (RP Avg)
-- side of "Drafting" are CR/CT-restricted (the deliberate fix vs the original asymmetric PBI DAX).
-- Checked by reading the deployed YAML directly: Drafting Own Exams/TBWU/Time Sec and the
-- rp_avg_drafting_tbwu/time source columns both filter modality_code IN ('CR','CT'). Confirmed.

-- 4. Efficiency Vs RP Avg ratio-not-percentage framing: confirm dashboard format is "number", not
-- "number-percent" (checked via lakeview get + string search, not SQL -- see report).

-- 5. Team/Practice conflation: confirm genuinely distinct, not accidentally collapsed.
SELECT `Team`, `Practice`, MEASURE(`Full Mosaic Mosaic Exams`) AS exam_count
FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view()
WHERE `Team` != `Practice`
GROUP BY ALL
ORDER BY 3 DESC
LIMIT 10;

-- 6. Full independent reconciliation of the exam-level source view against mosaic_service.py's
-- literal _MER_BASE_CTE_SQL + _MER_BASELINE_CTE_SQL, reconstructed from the Python source and run
-- directly against edw_prod (not through the view) -- see reconcile_against_mosaic_service.sql.
