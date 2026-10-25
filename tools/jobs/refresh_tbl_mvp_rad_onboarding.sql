-- Scheduled refresh for edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.
-- Same logic as the commented-out re-sync block at the bottom of
-- tools/edw_fixes/013_migrate_mvp_rad_onboarding_to_enterprise_analytics.sql, extracted into its
-- own runnable file for this job. INSERT OVERWRITE preserves the table/column comments already
-- set on this table.
--
-- FIXED 2026-10-24: the 2026-10-24 scheduled run failed with
-- DELTA_INSERT_COLUMN_ARITY_MISMATCH (target table has 32 columns, this SELECT had 31) - the
-- original 013 SELECT list predates 016_add_optimization_last_updated_to_mvp_rad_onboarding.sql
-- (run 2026-10-20), which ADD COLUMNed optimization_last_updated onto the table but was never
-- back-ported into this refresh script. Added it below as a straight passthrough, matching 016's
-- own MERGE (no CAST/cleanup - it's a raw Dynamics timestamp string). No data was lost: Delta
-- validates column count before committing an INSERT OVERWRITE, so the failed run left the
-- existing 2,609 rows untouched.

INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
SELECT
  CAST(REGEXP_REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS npi,
  rad_name, practice, mvp_cohort, exclusion_reason, mvp_target_outreach_week,
  `500_dx_cases` AS reads_500_plus_dx_cases,
  CAST(REGEXP_REPLACE(mvp_tbwus_9h_shift_may_jul_26, ',', '') AS DOUBLE) AS baseline_capacity_tbwu_9h,
  CAST(REGEXP_REPLACE(full_mosaic_efficiency_change_may_jul_26, ',', '') AS DOUBLE) AS full_mosaic_efficiency_change_pct,
  CAST(REGEXP_REPLACE(xr_drafting_efficiency_change_may_jul_26, ',', '') AS DOUBLE) AS xr_drafting_efficiency_change_pct,
  CAST(REGEXP_REPLACE(ct_head_efficiency_change_may_jul_26, ',', '') AS DOUBLE) AS ct_head_efficiency_change_pct,
  CAST(REGEXP_REPLACE(us_capture_efficiency_change_may_jul_26, ',', '') AS DOUBLE) AS us_capture_efficiency_change_pct,
  CAST(REGEXP_REPLACE(drafting___captured_efficiency_change_may_jul_26, ',', '') AS DOUBLE) AS drafting_captured_efficiency_change_pct,
  CAST(REGEXP_REPLACE(mosaic_efficiency_change_last_30_days, ',', '') AS DOUBLE) AS efficiency_change_last_30d_pct,
  CAST(REGEXP_REPLACE(full_mosaic_efficiency_change_l7d, ',', '') AS DOUBLE) AS full_mosaic_change_l7d_pct,
  CAST(REGEXP_REPLACE(full_mosaic_efficiency_change_l14d, ',', '') AS DOUBLE) AS full_mosaic_change_l14d_pct,
  CAST(REGEXP_REPLACE(full_mosaic_efficiency_change_l30d, ',', '') AS DOUBLE) AS full_mosaic_change_l30d_pct,
  CAST(REGEXP_REPLACE(xr_drafting_efficiency_change_l7d, ',', '') AS DOUBLE) AS xr_drafting_change_l7d_pct,
  CAST(REGEXP_REPLACE(xr_drafting_efficiency_change_l14d, ',', '') AS DOUBLE) AS xr_drafting_change_l14d_pct,
  CAST(REGEXP_REPLACE(xr_drafting_efficiency_change_l30d, ',', '') AS DOUBLE) AS xr_drafting_change_l30d_pct,
  CAST(REGEXP_REPLACE(ct_head_efficiency_change_l7d, ',', '') AS DOUBLE) AS ct_head_change_l7d_pct,
  CAST(REGEXP_REPLACE(ct_head_efficiency_change_l14d, ',', '') AS DOUBLE) AS ct_head_change_l14d_pct,
  CAST(REGEXP_REPLACE(ct_head_efficiency_change_l30d, ',', '') AS DOUBLE) AS ct_head_change_l30d_pct,
  CAST(REGEXP_REPLACE(us_capture_efficiency_change_l7d, ',', '') AS DOUBLE) AS us_capture_change_l7d_pct,
  CAST(REGEXP_REPLACE(us_capture_efficiency_change_l14d, ',', '') AS DOUBLE) AS us_capture_change_l14d_pct,
  CAST(REGEXP_REPLACE(us_capture_efficiency_change_l30d, ',', '') AS DOUBLE) AS us_capture_change_l30d_pct,
  my_mosaic_mentor AS mosaic_mentor, mosaic_mentor_status,
  mosaic_optimization_support_status AS optimization_support_status,
  mosaic_optimization_support_notes AS optimization_support_notes,
  utilization_plan_notes,
  optimization_last_updated
FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
WHERE npi IS NOT NULL AND npi != '' AND npi != '0'
  AND (mvp_cohort IS NOT NULL OR exclusion_reason IS NOT NULL);
