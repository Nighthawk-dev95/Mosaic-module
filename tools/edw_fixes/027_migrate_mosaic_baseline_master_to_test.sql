-- Mosaic Impact (Capacity) semantic migration. edw_test ONLY per the session's no-prod
-- instruction. Migrates edw_dev.bipa_analytics.stg_mosaic_baseline_master (12,075 rows / 1453
-- NPIs) - the real, already-computed per-(NPI, canonical shift type) baseline output of
-- mosaic_rebaseline_notebook + Baselines Proxies.sql + the Manual Review workflow (see
-- tools/capacity_model/README.md for the full pipeline this is the trusted output of).
--
-- Per explicit instruction: use this table directly as the baseline source, rather than
-- mosaic_service.py's own live Exact/Proxy re-derivation (_CAPACITY_EXACT_CTE_SQL/
-- _CAPACITY_PROXY_CTE_SQL) - this is the more authoritative source (the actual notebook output,
-- no re-derivation drift risk) now that this session can reach edw_dev.bipa_analytics directly
-- (same discovery as the Readtimeview shadow-table migration, 024).
--
-- Shift_Baseline_TBWU_2026 is the Place-of-Service-adjusted, "correct, current" TBWU baseline
-- convention (user-confirmed per capacity_model/README.md's "POS-adjustment question -
-- RESOLVED"). Units is always NULL/blank (confirmed live) - there is no RVU-denominated
-- baseline in this table; RVU-side capacity-vs-baseline measures will be NULL, matching
-- mosaic_service.py's own existing `baseline_rvu = NULL` precedent (not fabricated).

CREATE TABLE IF NOT EXISTS edw_test.enterprise_analytics.tbl_mosaic_baseline_master
COMMENT 'Governed copy of edw_dev.bipa_analytics.stg_mosaic_baseline_master: per-(NPI, canonical shift type) baseline TBWU, the trusted output of the real re-baselining notebook pipeline (see tools/capacity_model/README.md). Shift_Baseline_TBWU_2026 is the POS-adjusted, current convention. 12,075 rows / 1453 NPIs as of 2026-10-22. Source for mosaic_capacity_metric_view.'
AS SELECT * FROM edw_dev.bipa_analytics.stg_mosaic_baseline_master;

-- To re-sync after the first run:
--   INSERT OVERWRITE edw_test.enterprise_analytics.tbl_mosaic_baseline_master
--   SELECT * FROM edw_dev.bipa_analytics.stg_mosaic_baseline_master;
