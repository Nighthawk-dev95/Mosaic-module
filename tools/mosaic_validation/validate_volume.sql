-- Mosaic Volume validation queries (Phase A).
-- Every block below is run live against the deployed edw_test.enterprise_analytics.mosaic_volume_metric_view
-- (and, where relevant, the edw_prod base tables it reads from) -- never inferred from reading SQL/TMDL files alone.
-- See tools/mosaic_validation/VALIDATION_REPORT_VOLUME.md for results and dispositions.

-- 1. Allocated TBWU: allocated_tbwu_current vs plain allocated_tbwu -- how often do they differ, and by how much?
SELECT
  COUNT(*) AS total_rows,
  COUNT(CASE WHEN allocated_tbwu_current != allocated_tbwu THEN 1 END) AS rows_differ,
  SUM(allocated_tbwu_current) AS sum_current,
  SUM(allocated_tbwu) AS sum_plain,
  SUM(allocated_tbwu_current) - SUM(allocated_tbwu) AS delta
FROM edw_prod.enterprise_analytics.tbl_exam_inventory
WHERE allocated_tbwu_current IS NOT NULL OR allocated_tbwu IS NOT NULL;

-- 2. VRA Flag: confirm it's a real native column (not a derived compound condition), and check its
-- value distribution against the PBI-documented compound condition it's meant to replace.
SELECT VRA_Flag, COUNT(*) AS exam_count
FROM edw_prod.enterprise_analytics.tbl_exam_inventory
GROUP BY ALL;

-- 3. Care Setting: value distribution, to characterize the proxy gap vs PBI's Place_Of_Service_Name
-- (no live PBI comparison possible right now -- this documents what IS present, not a diff).
SELECT `Care Setting`, MEASURE(`Exam Count`) AS exam_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL
ORDER BY 2 DESC;

-- 4. AD Group Added Date: confirm dynamics_rad_drafting_enablement_by_npi_vw is genuinely unique on npi
-- (the MIN()-collapse only matches its own documentation if the join doesn't fan out).
SELECT npi, COUNT(*) AS row_count
FROM edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw
GROUP BY npi
HAVING COUNT(*) > 1;

-- 5. Drafted But Not Enabled: reconfirm the drafting_model IS NOT NULL scope is actually enforced
-- (re-run the original 7.4M-vs-1.0M sanity check: with scope vs without).
SELECT
  MEASURE(`Drafted But Not Enabled Exam Count`) AS scoped_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();

SELECT COUNT(*) AS unscoped_count
FROM edw_prod.enterprise_analytics.tbl_exam_inventory
WHERE mosaic_draft_flag = TRUE;

-- 6. Modality: confirm no "XR" literal exists anywhere in the live data (plain film is "CR").
SELECT DISTINCT `Modality`
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL;

-- 7. Fan-out/row-count check: total Exam Count via the metric view (post-3-joins) vs a raw count of the
-- base table with the same date filter the view's own header documents (final_datetime >= 2024-11-01
-- per the Efficiency sibling's convention -- Volume has no such filter documented, so compare unfiltered).
SELECT MEASURE(`Exam Count`) AS metric_view_exam_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();

SELECT COUNT(*) AS raw_table_exam_count
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;

-- 8. Draftable/Drafted Exam Count vs mosaic_drafting_metric_vw: confirm the two are NOT expected to
-- reconcile (different definitions -- this just captures both current numbers side by side).
SELECT MEASURE(`Draftable Exam Count`) AS volume_draftable, MEASURE(`Drafted Exam Count`) AS volume_drafted
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();

SELECT
  COUNT(*) FILTER (WHERE exam_draftable_flag) AS drafting_vw_draftable,
  COUNT(*) FILTER (WHERE exam_draftable_flag AND mosaic_draft_flag) AS drafting_vw_drafted
FROM edw_prod.enterprise_analytics.mosaic_drafting_metric_vw;

-- 9. working_subspecialty gap: confirm still absent from the metric view's exposed dimensions
-- (informational -- SHOW CREATE TABLE column list is the real check, done separately).

-- 10. Practice vs Managing Practice: confirm they actually diverge for at least one real NPI
-- (a cross-coverage pool like SEAL Team is the expected case).
SELECT `Team`, `Practice`, `Managing Practice`, MEASURE(`Exam Count`) AS exam_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
WHERE `Team` != `Managing Practice`
GROUP BY ALL
ORDER BY 4 DESC
LIMIT 20;

-- 11. Pct RPCE Reporting/Drafting +0.02 adjustment: direct reconciliation against mosaic_service.py's
-- raw formula (_RPCE_SOURCE_SYSTEMS_SQL + _RPCE_PCT_ADJUSTMENT), computed on the exact same base table.
WITH raw AS (
  SELECT
    (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
      / NULLIF(SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END), 0))
      + 0.02 AS raw_pct_rpce_reporting,
    (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
      / NULLIF(SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END), 0))
      + 0.02 AS raw_pct_rpce_drafting
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory
)
SELECT * FROM raw;

SELECT MEASURE(`Pct RPCE Reporting`) AS mv_pct_rpce_reporting, MEASURE(`Pct RPCE Drafting`) AS mv_pct_rpce_drafting
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();

-- 12. Is RPCE Source reconciliation.
SELECT `Is RPCE Source`, MEASURE(`Exam Count`) AS mv_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL;

SELECT
  SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END) AS raw_rpce_true,
  SUM(CASE WHEN Source_System_Code NOT IN ('rpceMidwest', 'rpceSouthwest') OR Source_System_Code IS NULL THEN 1 ELSE 0 END) AS raw_rpce_false
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;

-- 13. Estimated RVU and TBWU reconciliation.
SELECT MEASURE(`Estimated RVU`) AS mv_estimated_rvu, MEASURE(`TBWU`) AS mv_tbwu
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();

SELECT SUM(estimated_wrvu) AS raw_estimated_rvu, SUM(final_TBWU) AS raw_tbwu
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;

-- 14. Reporting Status vocabulary reconciliation (Drafting > Reporting > Baseline).
SELECT `Reporting Status`, MEASURE(`Exam Count`) AS mv_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL;

SELECT
  CASE WHEN mosaic_draft_flag THEN 'Drafting' WHEN mosaic_read_flag THEN 'Reporting' ELSE 'Baseline' END AS raw_status,
  COUNT(*) AS raw_count
FROM edw_prod.enterprise_analytics.tbl_exam_inventory
GROUP BY ALL;
