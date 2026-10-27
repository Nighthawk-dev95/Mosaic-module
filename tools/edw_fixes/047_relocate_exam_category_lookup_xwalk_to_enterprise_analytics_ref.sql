-- Relocate the governed exam-category crosswalk out of edw_prod.enterprise_analytics into
-- edw_prod.enterprise_analytics_ref, under that schema's own naming convention.
--
-- STATUS: COMPLETE. Both steps RUN 2026-10-26 via the `mosaic-app` PAT profile's
-- SEC-AZ-DBX-P-EA-ADM group membership (ALL PRIVILEGES + MANAGE on
-- edw_prod.enterprise_analytics_ref, confirmed live via SHOW GRANTS).
--   step 1 (CREATE)  - run; 969 rows / 969 distinct ParentRpt / 26 categories, bidirectional
--                      EXCEPT against the old copy returned 0 rows both ways.
--   step 2 (DROP)    - run, on the user's explicit approval, after every consumer below was
--                      repointed and re-applied. SHOW TABLES IN edw_prod.enterprise_analytics
--                      LIKE 'tbl_exam_category*' now returns zero rows.
--
-- WHY: enterprise_analytics is the certified/Genie-facing dataset schema. A 969-row ParentRpt ->
-- Category lookup is reference data, not a certified dataset, and belongs in the _ref schema that
-- already holds exactly this class of object (ref_tbwu_care_setting_multiplier_crosswalk,
-- ref_qgenda_engage_category_map, ref_exam_compensation_multiplier, ...). Nothing about the
-- original rationale changes: this is still a materialized CTAS rather than a view, because a view
-- would still require edw_dev access at query time for the app's service principal, since Unity
-- Catalog views run with the querying principal's own privileges (see 012, 013).
--
-- NAMING: enterprise_analytics_ref uses no `tbl_` prefix anywhere across its ~110 objects. Its
-- reference/lookup/crosswalk family is `ref_*`. Hence ref_exam_category_lookup_xwalk, not
-- tbl_exam_category_lookup_xwalk.
--
-- ACCESS: no new grant is needed. SHOW GRANTS ON SCHEMA edw_prod.enterprise_analytics_ref confirms
-- SELECT + USE SCHEMA for every practice-command app service principal, including the deploy
-- target practice-command-bhargav (4a77686c-5d36-4e88-9233-7c29f93f1b81). The app already reads
-- enterprise_analytics_ref.drafting_eligible_rpids_vw today.
--
-- DEPENDENCY SURFACE (verified live 2026-10-26 against information_schema.views for edw_prod,
-- edw_test and edw_dev with the CATALOG PINNED in the pattern - '%edw_prod.enterprise_analytics.
-- tbl_exam_category_lookup_xwalk%' - plus SHOW CREATE TABLE on all 8 edw_test mosaic metric views,
-- since metric views do not appear in information_schema.views and must be checked separately.
-- TWO consumers bind this table. BOTH ARE NOW REPOINTED (2026-10-26):
--   edw_prod : none. Zero views, zero metric views.
--   edw_test : enterprise_analytics.mosaic_volume_metric_view      (METRIC_VIEW, joins: dim_category)
--              DONE - 036_mosaic_volume_metric_view_pbi_local_FLOW.sql repointed and RE-APPLIED.
--              Live SHOW CREATE TABLE confirms the dim_category source now reads
--              edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk and contains zero
--              occurrences of the old path. Smoke-tested: GROUP BY `Exam Category` returns the
--              expected taxonomy (XR - MSK, CT HEAD, CT AB/PEL, US Capturable, ...).
--   app      : backend/app/services/mosaic_service.py:65  (DONE - now reads the _ref copy)
--
-- The pinned views sweep returned zero rows across all three catalogs. An earlier unpinned sweep
-- ('%enterprise_analytics.tbl_exam_category_lookup_xwalk%') wrongly flagged
-- edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw - SHOW CREATE TABLE on the deployed
-- view shows it joins the edw_test copy of the crosswalk, a separate object this script does not
-- touch (see 022_create_efficiency_exam_level_view_TEST.sql:74). A pattern that omits the catalog
-- cannot tell edw_prod.X from edw_test.X.
-- mosaic_draftable_metric_view names the crosswalk only in a column comment; it reads from
-- mosaic_draftable_snapshot_mv and does not bind the table.
--
-- NOTE: edw_test.enterprise_analytics.tbl_exam_category_lookup_xwalk still exists under the old
-- name. It is out of scope here - this script moves the edw_prod copy only.
--
-- additive-only: this CREATEs a new object in a new schema and touches nothing pre-existing (see
-- memory: never_overwrite_enterprise_analytics). The DROP at the bottom removes only the copy this
-- project itself created on 2026-10-15 via script 012.

CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk
COMMENT 'Governed copy of edw_dev.bipa_analytics.exam_category_lookup_xwalk. Canonical ParentRpt-to-Category source for the Mosaic Efficiency and Volume semantics - join on ParentRpt = tbl_exam_inventory.RPID_parent_code, NOT RPID_Procedure_Code. Materialized rather than exposed as a view so the mosaic-module app''s service principal can read it without an edw_dev grant (Unity Catalog views run with the querying principal''s own privileges). Relocated here from edw_prod.enterprise_analytics 2026-10-26 (047) - reference data, not a certified dataset. Re-sync via INSERT OVERWRITE if the source gains new categories/codes. 969 rows / 969 distinct ParentRpt / 26 categories as of 2026-10-26.'
AS SELECT
  ParentRpt,
  Category
FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk;

-- To re-sync after the first run (safe: overwrites only this table, which this project owns):
--   INSERT OVERWRITE edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk
--   SELECT ParentRpt, Category FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk;

-- Verification (expect 969 / 969 / 26, matching the source and the old copy exactly):
--   SELECT COUNT(*) AS rows, COUNT(DISTINCT ParentRpt) AS keys, COUNT(DISTINCT Category) AS cats
--   FROM edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk;

-- ---------------------------------------------------------------------------------------------
-- STEP 2 - EXECUTED 2026-10-26 on the user's explicit approval, after both consumers above were
-- repointed and re-applied so nothing read the old copy any more:
--
--   DROP TABLE edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk;
--
-- Permitted under the never-overwrite rule because this project created that table itself on
-- 2026-10-15 (012); it is not pre-existing enterprise_analytics content.
--
-- Carried across before the drop: the two column comments that lived on the old table are now on
-- the _ref copy (ParentRpt, Category) - see _add_comments_enterprise_analytics.sql, which was
-- repointed in the same change so a re-run does not fail on the dropped table.
--
-- Post-drop verification: SHOW TABLES IN edw_prod.enterprise_analytics LIKE 'tbl_exam_category*'
-- returns zero rows, and the Volume metric view's `Exam Category` group-by still resolves.
-- ---------------------------------------------------------------------------------------------
