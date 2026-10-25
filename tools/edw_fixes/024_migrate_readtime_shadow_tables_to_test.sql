-- Mosaic Efficiency "vs RP Average" semantic (Readtimeview.tmdl) migration. edw_test ONLY per
-- the session's no-prod instruction. Migrates the two shadow tables Readtimeview's measures are
-- actually built on (radiologist_metrics(1)/radiologist_summary(1) in the TMDL, confirmed via
-- SHOW CREATE TABLE): a DIFFERENT, no-baseline-restriction population from the main Efficiency
-- semantic's radiologist_metrics_optimized lineage - this is deliberately a separate source, not
-- a re-use of tbl_efficiency_exam_level_vw. 37.8M rows / 3705 NPIs (vs. 2758 in the
-- baseline-restricted population - 947 more radiologists who lack a qualifying baseline but still
-- have Mosaic exams, which is the whole point of this semantic: "efficiency vs peer average" for
-- radiologists who can't be compared to their own baseline).
--
-- Both tables already carry Outliers/Period_Type pre-computed (unlike tbl_exam_inventory, which
-- needed the LAG/2-stdev pipeline reimplemented) - no base-CTE reimplementation needed here,
-- just a governed pass-through.

CREATE TABLE IF NOT EXISTS edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow
COMMENT 'Governed copy of edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow - the no-baseline-restriction exam-metrics table backing the PBI Efficiency report''s Readtimeview.tmdl ("efficiency vs RP average") measures. 37.8M rows / 3705 NPIs as of 2026-10-22. Source for the Mosaic Efficiency vs RP Avg metric view - see tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
AS SELECT * FROM edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow;

CREATE TABLE IF NOT EXISTS edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow
COMMENT 'Governed copy of edw_dev.bipa_analytics.dim_radiologist_rtupdated_shadow - per-radiologist dimension counterpart of tbl_readtime_radiologist_metrics_shadow. 4126 rows as of 2026-10-22.'
AS SELECT * FROM edw_dev.bipa_analytics.dim_radiologist_rtupdated_shadow;

-- To re-sync after the first run:
--   INSERT OVERWRITE edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow
--   SELECT * FROM edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow;
--   INSERT OVERWRITE edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow
--   SELECT * FROM edw_dev.bipa_analytics.dim_radiologist_rtupdated_shadow;
