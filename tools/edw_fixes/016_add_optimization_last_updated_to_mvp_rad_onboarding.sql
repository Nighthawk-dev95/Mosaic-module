-- STATUS: RUN 2026-10-20, via the `mosaic-app` PAT profile. ALTER succeeded; MERGE updated all
-- 2,609 existing rows (0 inserted/deleted, confirming this touched only the new column).
-- Verified: 765/2,609 rows have a non-null optimization_last_updated value.
--
-- WHY: The MVP Weekly Update rebuild (see declarative-dancing-willow.md plan,
-- "MVP module rebuild: reproduce the real Weekly Update report") needs a per-radiologist "last
-- touched" timestamp to approximate the PDF's "MVP Engaged Weekly" week-by-week trend. There is
-- no stage-transition audit log in this Dataverse schema (confirmed live: SHOW TABLES ON SCHEMA
-- edw_prod.`dataverse_m365-vra-dynamics-prod` returns only accounts/contacts/rad_onboarding, no
-- history table). `modified_on` looked promising but is a bulk-sync timestamp (confirmed live:
-- ~every row reads the same sync day regardless of real content change - useless as a signal).
-- `optimization_last_updated` is genuinely varied per-row and plausibly tracks when a
-- radiologist's optimization/support case was last worked - confirmed live this session
-- (DATE_TRUNC('WEEK', ...) bucketing over the active MVP population produces a believable
-- declining-activity shape that sums close to the already-known "409 actively tracked" figure).
-- This is a "last touched" proxy, NOT a true "date entered this stage" log - the weekly trend
-- built on it must be captioned as an approximation, never presented as exact history.
--
-- APPROACH: ADDITIVE ONLY, per this repo's hard rule (never overwrite/replace anything
-- pre-existing in enterprise_analytics). tbl_mvp_rad_onboarding already exists (013) - this adds
-- exactly one new column via ALTER TABLE, then backfills it via MERGE (an UPDATE-shaped
-- operation touching only the new column, not re-creating or overwriting the table or any of
-- its existing columns/rows).
--
-- Run via the `mosaic-app` PAT profile, same mechanism as 011/013/014.

ALTER TABLE edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
ADD COLUMNS (optimization_last_updated STRING COMMENT 'Raw Dynamics "last touched" timestamp for this radiologist''s optimization/support case (e.g. "10/19/2026 2:04 PM") - a last-updated proxy, NOT a true stage-transition log. Added 2026-10-20, see 016_add_optimization_last_updated_to_mvp_rad_onboarding.sql for provenance.');

MERGE INTO edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding AS tgt
USING (
  SELECT
    CAST(REGEXP_REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS npi,
    optimization_last_updated
  FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
  WHERE npi IS NOT NULL AND npi != '' AND npi != '0'
    AND (mvp_cohort IS NOT NULL OR exclusion_reason IS NOT NULL)
) AS src
ON tgt.npi = src.npi
WHEN MATCHED THEN UPDATE SET tgt.optimization_last_updated = src.optimization_last_updated;

-- To re-sync (re-run both statements above - ALTER is a no-op once the column exists, MERGE
-- re-backfills from the current live Dynamics values):
--   (same two statements)
