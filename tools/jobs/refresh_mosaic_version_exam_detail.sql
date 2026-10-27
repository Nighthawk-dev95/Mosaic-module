-- Scheduled refresh for edw_prod.bipa_analytics.mosaic_version_exam_detail.
-- INSERT OVERWRITE (not CREATE OR REPLACE TABLE) so the table/column comments already set
-- on this table are preserved - CREATE OR REPLACE would silently wipe them.
-- Verified 2026-10-23 to reproduce the live table exactly (10-row spot check + exact row
-- count match, 6,540,579 rows) before being wired into this job.
--
-- MIGRATED 2026-10-26 from edw_prod.enterprise_analytics(_ref) to edw_prod.bipa_analytics, per
-- Yaro's request to keep enterprise_analytics reserved for certified/Genie-governed datasets -
-- bipa_analytics chosen over edw_dev because the dashboard's existing viewers (incl. Yaro)
-- already hold SELECT there. tbl_exam_inventory and practice_to_local_mapping are NOT part of
-- this migration and stay exactly where they were.
--
-- Depends on edw_prod.bipa_analytics.mosaic_version_exam_lookup already being current -
-- that table's own refresh (tools/mosaic_version_pipeline/sync_exam_lookup.py) is NOT part of
-- this job because it pulls from the AWS workspace (p_use1_rp_aws_dbx_workspace01) via the
-- `databricks` CLI and local OAuth profiles, which a job task on this (Azure) workspace cannot
-- reach without its own cross-workspace auth setup. Keep running sync_exam_lookup.py manually
-- (or from wherever it's scheduled) before this job fires.

INSERT OVERWRITE edw_prod.bipa_analytics.mosaic_version_exam_detail
SELECT
  l.accession_number,
  l.log_date,
  l.npi,
  e.reading_provider_name_full AS radiologist_name,
  COALESCE(e.provider_local_practice_name_curr, 'Unknown') AS practice,
  COALESCE(pl.local, 'Unmapped') AS local,
  l.modality,
  l.modality_group,
  l.mosaic_version,
  CASE WHEN l.mosaic_version = 'Mosaic 2.0' THEN 1 ELSE 0 END AS is_v2,
  CASE WHEN l.mosaic_version = 'Mosaic 2.0' THEN l.npi ELSE NULL END AS npi_v2
FROM edw_prod.bipa_analytics.mosaic_version_exam_lookup l
LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_inventory e
  ON l.accession_number = e.accession_number
LEFT JOIN edw_dev.enterprise_analytics.practice_to_local_mapping pl
  ON e.provider_local_practice_name_curr = pl.practice;
