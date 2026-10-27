-- STATUS: SUPERSEDED BY 047. Run 2026-10-15 via the `mosaic-app` PAT profile's
-- SEC-AZ-DBX-P-EA-ADM group membership (ALL PRIVILEGES on edw_prod.enterprise_analytics) - same
-- mechanism as 011_migrate_seal_reference_tables_to_enterprise_analytics.sql. The table this
-- script created, edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk, was RELOCATED
-- on 2026-10-26 to edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk and the copy
-- here was DROPPED - a 969-row lookup is reference data, not a certified dataset, so it belongs
-- in the _ref schema. Do not re-run this script; run 047 instead. Everything below is retained
-- because the WHY still explains why the crosswalk exists at all and which join key is correct.
--
-- WHY: Root cause of the "Efficiency numbers don't match" bug (2026-10-15). The Efficiency
-- pipeline's `mpcat` column (backend/app/services/mosaic_service.py's _MER_BASE_CTE_SQL) was
-- sourced from edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw.drafting_model -
-- but that view only covers 7 narrow drafting-eligibility buckets (XR/MSK, CT Head/Chest/
-- Abd-Pel/Spine, US/DEXA Capturable, 969 procedure codes total), NOT the real, full clinical
-- category taxonomy. Confirmed live: querying mpcat = 'Mammo Diagnostic' against the old
-- source returned ZERO rows - the category doesn't exist in that vocabulary at all. The code's
-- own comment claimed "confirmed identical category values live" - that claim was wrong (or
-- only spot-checked the few categories that DO overlap, like 'US Capturable', not coverage of
-- the full category list).
--
-- The real source, edw_dev.bipa_analytics.exam_category_lookup_xwalk (969 rows, 26 distinct
-- categories, see memory: exam_category_lookup_xwalk_reference.md), is unreachable under the
-- app's enterprise_analytics-only grant - same access gap as the SEAL tables. Migrating a
-- governed copy here, joined the same way the original MER Current Method notebook's cell-0
-- does (ParentRpt = RPID_parent_code, NOT RPID_Procedure_Code - confirmed live: joining on
-- RPID_parent_code covers 79.2M of 88.1M exams since 2024-11-01, 90%, vs the old source's
-- narrow coverage).
--
-- APPROACH: plain CREATE TABLE AS SELECT (materialized copy), not a view - same reasoning as
-- 011: a view would still require edw_dev access at query time for the app's service
-- principal, since Unity Catalog views run with the querying principal's own privileges.

CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk
COMMENT 'Governed copy of edw_dev.bipa_analytics.exam_category_lookup_xwalk, materialized so the mosaic-module app (service principal scoped to enterprise_analytics only) can read it without a cross-catalog grant. This is the canonical ParentRpt-to-Category source for the Efficiency pipeline - join on ParentRpt = tbl_exam_inventory.RPID_parent_code, NOT RPID_Procedure_Code. Re-run via INSERT OVERWRITE if the source table is ever updated with new categories/codes. 969 rows / 26 categories as of 2026-10-15.'
AS SELECT
  ParentRpt,
  Category
FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk;

-- To re-sync after the first run:
--   INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk
--   SELECT ParentRpt, Category FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk;
