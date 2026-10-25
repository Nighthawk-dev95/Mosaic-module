-- STATUS: RUN 2026-10-17, RE-RUN 2026-10-17 (v2 - numeric cast fix), via the `mosaic-app` PAT
-- profile's SEC-AZ-DBX-P-EA-ADM group membership (ALL PRIVILEGES on edw_prod.
-- enterprise_analytics) - same mechanism as 011/012.
--
-- WHY: Rebuilding the MVP tab to read the real Mosaic Value Project program's own live
-- CRM-tracked fields (cohort, exclusion reason, outreach week, baseline capacity, efficiency-
-- change figures, mentor status, case-manager notes) directly from
-- edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding, instead of approximating the
-- program with an EDW heuristic that couldn't see any of this (see backend/app/services/
-- mosaic_service.py's get_mvp_rad_onboarding()). Confirmed live via SHOW GRANTS ON SCHEMA
-- edw_prod.`dataverse_m365-vra-dynamics-prod` that only Genie_Pilot_User_Group has access -
-- the deployed app's own service principal cannot reach it, same access gap as 011/012.
--
-- APPROACH: plain CREATE TABLE AS SELECT (materialized copy), same reasoning as 011/012 - a
-- view would still require the Dataverse schema grant at query time, since Unity Catalog views
-- run under the querying principal's own privileges. Only the ~27 columns the MVP tab actually
-- uses are copied (not all 168 raw columns) - keeps the copy small and the NPI cast is baked in
-- once here instead of repeated on every read.
--
-- v2 FIX: every column in the raw Dataverse table is typed STRING (confirmed via DESCRIBE -
-- Dynamics exports everything as text, with no exception for numeric fields), and a small
-- number of extreme efficiency-change values carry a thousands-separator comma (e.g.
-- "2,107.86") - confirmed live this broke Pydantic validation on
-- us_capture_efficiency_change_l14d/l30d for at least one radiologist. Every numeric column
-- below now goes through the same REGEXP_REPLACE(..., ',', '')+CAST(... AS DOUBLE) pattern
-- already used for npi, not just the two that happened to surface the bug on the first run -
-- any of the ~19 efficiency-change/capacity columns could carry the same issue for a different
-- radiologist on a future refresh.
--
-- STALENESS: rad_onboarding is a live, same-day-updated CRM table; this copy is a point-in-time
-- snapshot, refreshed only when this script is re-run (manually, via `mosaic-app` PAT) - same
-- tradeoff already accepted for the SEAL reference tables. Re-run before any session that needs
-- current MVP state, or on whatever cadence proves necessary in practice.

CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
COMMENT 'Governed, periodically-refreshed copy of the MVP-relevant columns from edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding, materialized so the mosaic-module app (service principal scoped to enterprise_analytics only) can read it without a cross-schema grant. NPI and every efficiency-change/capacity column are cleaned of thousands-separator commas and cast to DOUBLE/DECIMAL here - the source stores every column as STRING. Point-in-time snapshot, not live - re-sync via INSERT OVERWRITE (see bottom of this file) whenever current MVP state is needed. Snapshot as of 2026-10-17 (v2).'
AS SELECT
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
  utilization_plan_notes
FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
WHERE npi IS NOT NULL AND npi != '' AND npi != '0'
  AND (mvp_cohort IS NOT NULL OR exclusion_reason IS NOT NULL);

-- To re-sync (this exact SELECT, via INSERT OVERWRITE - table already exists after first run):
--   INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
--   SELECT ... (same SELECT as above) ...
