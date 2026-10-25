-- STATUS: RUN 2026-10-19, via the `mosaic-app` PAT profile's SEC-AZ-DBX-P-EA-ADM group
-- membership (same mechanism as 011/013). Table created and verified: 86,155 rows, matching the
-- row count already confirmed live via query_edw before this table existed; sample rows show
-- correct fraction scale (0-1) on utilization_pct/pct_mosaic_read/pct_ai_drafted.
--
-- WHY: Shift Utilization (the per-radiologist shift-utilization/AI-drafting heatmap) needs
-- edw_dev.bipa_analytics.presentation_deneb_vw, joined to tbl_exam_inventory for
-- mosaic_read_flag/mosaic_draft_flag. Per explicit instruction (2026-10-19): the deployed app's
-- service principal cannot be granted edw_dev.bipa_analytics access - same wall 011/013 already
-- hit (service principal scoped to edw_prod.enterprise_analytics only, confirmed via SHOW GRANTS,
-- see backend/app/config.py's own comment) - so this follows the identical fix: materialize a
-- governed copy into enterprise_analytics via CTAS, run under the `mosaic-app` PAT profile,
-- which carries SEC-AZ-DBX-P-EA-ADM group membership (ALL PRIVILEGES on
-- edw_prod.enterprise_analytics, confirmed live in 011) - no new grant needed for this, unlike
-- widening access into a dev catalog.
--
-- APPROACH: unlike 011/013 (which copy small reference tables near-verbatim), this migrates the
-- ALREADY-AGGREGATED shape the app actually needs - one row per (NPI, shift date), not the raw
-- 29.5M-row bar-level source - using the exact shifts/exam_flags CTE logic already live-verified
-- and shipped in mosaic_service.get_shift_utilization_by_radiologist(). This keeps the migrated
-- table small (~86K rows for a 90-day window, confirmed live via query_edw 2026-10-19) and means
-- the join against tbl_exam_inventory happens once here, not on every app refresh cycle. A plain
-- CTAS, not a VIEW, for the same reason as 011/013: a cross-catalog view still runs under the
-- QUERYING principal's own privileges in Unity Catalog, so it would 403 one hop later.
--
-- STALENESS: point-in-time snapshot of the last 90 days as of whenever this is (re-)run - same
-- tradeoff already accepted for the SEAL/MVP tables (013's own wording). Re-run the INSERT
-- OVERWRITE at the bottom of this file whenever fresh shift data is needed; no automated
-- recurring job exists yet.

CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization
COMMENT 'Governed, periodically-refreshed snapshot of per-(radiologist, shift date) utilization - materialized from edw_dev.bipa_analytics.presentation_deneb_vw joined to tbl_exam_inventory, so the mosaic-module app (service principal scoped to enterprise_analytics only) can read it without a cross-catalog grant. Point-in-time snapshot of a rolling 90-day window as of creation/last refresh, not live - re-run the INSERT OVERWRITE at the bottom of tools/edw_fixes/014_migrate_shift_utilization_to_enterprise_analytics.sql to refresh. utilization_pct/pct_mosaic_read/pct_ai_drafted are fractions (0-1).'
AS
WITH shifts AS (
  SELECT
    NPI AS npi,
    MAX(Radiologist) AS radiologist_name,
    MAX(Practice_Short_Name) AS practice,
    CAST(Calendar_Date AS DATE) AS shift_date,
    shift_start_dt,
    MAX(utilization_pct) / 100.0 AS utilization_pct,
    MAX(reading_minutes) AS reading_minutes,
    MAX(shift_total_minutes) AS shift_total_minutes
  FROM edw_dev.bipa_analytics.presentation_deneb_vw
  WHERE Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
    AND shift_start_dt IS NOT NULL
  GROUP BY NPI, CAST(Calendar_Date AS DATE), shift_start_dt
),
exam_flags AS (
  SELECT
    d.NPI AS npi,
    CAST(d.Calendar_Date AS DATE) AS shift_date,
    d.shift_start_dt,
    COUNT(DISTINCT CASE WHEN e.mosaic_read_flag THEN d.Accession_Number END)
      / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_mosaic_read,
    COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN d.Accession_Number END)
      / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_ai_drafted
  FROM edw_dev.bipa_analytics.presentation_deneb_vw d
  LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_inventory e
    ON d.Accession_Number = e.accession_number
  WHERE d.Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
    AND d.bar_type = 'Reading Time'
    AND d.Accession_Number IS NOT NULL
  GROUP BY d.NPI, CAST(d.Calendar_Date AS DATE), d.shift_start_dt
)
SELECT
  s.npi, s.radiologist_name, s.practice,
  CAST(s.shift_date AS STRING) AS shift_date,
  s.utilization_pct, s.reading_minutes, s.shift_total_minutes,
  f.pct_mosaic_read, f.pct_ai_drafted
FROM shifts s
LEFT JOIN exam_flags f
  ON s.npi = f.npi AND s.shift_date = f.shift_date AND s.shift_start_dt = f.shift_start_dt;

-- To re-sync after the first run (CREATE TABLE IF NOT EXISTS above only creates once):
--   INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization
--   WITH shifts AS (
--     SELECT
--       NPI AS npi,
--       MAX(Radiologist) AS radiologist_name,
--       MAX(Practice_Short_Name) AS practice,
--       CAST(Calendar_Date AS DATE) AS shift_date,
--       shift_start_dt,
--       MAX(utilization_pct) / 100.0 AS utilization_pct,
--       MAX(reading_minutes) AS reading_minutes,
--       MAX(shift_total_minutes) AS shift_total_minutes
--     FROM edw_dev.bipa_analytics.presentation_deneb_vw
--     WHERE Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
--       AND shift_start_dt IS NOT NULL
--     GROUP BY NPI, CAST(Calendar_Date AS DATE), shift_start_dt
--   ),
--   exam_flags AS (
--     SELECT
--       d.NPI AS npi,
--       CAST(d.Calendar_Date AS DATE) AS shift_date,
--       d.shift_start_dt,
--       COUNT(DISTINCT CASE WHEN e.mosaic_read_flag THEN d.Accession_Number END)
--         / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_mosaic_read,
--       COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN d.Accession_Number END)
--         / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_ai_drafted
--     FROM edw_dev.bipa_analytics.presentation_deneb_vw d
--     LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_inventory e
--       ON d.Accession_Number = e.accession_number
--     WHERE d.Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
--       AND d.bar_type = 'Reading Time'
--       AND d.Accession_Number IS NOT NULL
--     GROUP BY d.NPI, CAST(d.Calendar_Date AS DATE), d.shift_start_dt
--   )
--   SELECT
--     s.npi, s.radiologist_name, s.practice,
--     CAST(s.shift_date AS STRING) AS shift_date,
--     s.utilization_pct, s.reading_minutes, s.shift_total_minutes,
--     f.pct_mosaic_read, f.pct_ai_drafted
--   FROM shifts s
--   LEFT JOIN exam_flags f
--     ON s.npi = f.npi AND s.shift_date = f.shift_date AND s.shift_start_dt = f.shift_start_dt;
