-- 045_fix_rad_onboarding_vw_schema_drift.sql
--
-- FIXES
--   [BAD_REQUEST] [INCOMPATIBLE_VIEW_SCHEMA_CHANGE] The SQL query of view
--   `edw_prod`.`edw_gold`.`dataverse_m365-vra-dynamics-prod_rad_onboarding_vw`
--   has an incompatible schema change and column
--   _vrarp_residentworkflowrequirement_value cannot be resolved.
--
-- ROOT CAUSE
--   The view is a plain `SELECT *` passthrough over the Dataverse sync table
--   edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding, but it was created
--   WITH SCHEMA COMPENSATION (the Databricks default), which pins an explicit
--   188-column list into the view definition.
--
--   The upstream Dataverse table has since drifted to 191 columns:
--
--     DROPPED from base (still pinned in the view -> this is what breaks it):
--       _vrarp_residentworkflowrequirement_value
--
--     ADDED to base (silently invisible through the view):
--       _vrarp_residentworkflowrequirement1_value   <- the renamed lookup
--       added_to_ad_group_ct_test
--       drafting_training_completed_ct_test
--       drafting_training_sent_ct_test
--
--   This is NOT a simple column rename. DESCRIBE HISTORY + time travel on the
--   base table show the swap landed in exactly one sync run -- version 243,
--   2026-10-26 13:04:48, job EDW_Dataverse_to_Datawarehouse (372971618141786),
--   which does a daily CREATE OR REPLACE TABLE AS SELECT with
--   canOverwriteSchema=true. The two GUID columns never coexisted in this table.
--
--   What actually happened is that the lookup's VALUES MOVED from the raw GUID
--   column into the resolved label column:
--
--     VERSION AS OF 242 (2026-10-25)
--       _vrarp_residentworkflowrequirement_value   75 non-null / 2 distinct GUIDs
--       resident_workflow_requirement               0 non-null / 0 distinct
--
--     VERSION AS OF 243 (2026-10-26, current)
--       _vrarp_residentworkflowrequirement_value   DROPPED
--       _vrarp_residentworkflowrequirement1_value   0 non-null / 0 distinct  (EMPTY)
--       resident_workflow_requirement              75 non-null / 2 distinct labels
--                                                    "Drafts Reports Only"              43
--                                                    "Dual WF: Drafts Reports + Sends
--                                                     Preliminary Reports"              32
--
--   Same 75 rows, same cardinality of 2 -- the sync now emits the resolved lookup
--   TEXT in `resident_workflow_requirement` instead of a raw GUID. No data lost.
--
--   The new `_vrarp_residentworkflowrequirement1_value` is a DIFFERENT field and
--   is currently empty. The PBI semantic models
--   (tools/pbi_semantic_extract/.../RadPipeline.tmdl) confirm two separate
--   Dataverse lookups exist, with distinct display names:
--     vrarp_residentworkflowrequirementname  -> "Resident Workflow Requirement"
--     vrarp_residentworkflowrequirement1name -> "Resident Workflow Requirement 2"
--
--   NOT CONFIRMED ON THE DATAVERSE SIDE: whether the underlying field was
--   renamed, deleted, or re-pointed in Dynamics cannot be verified from here --
--   Dataverse CLI auth is still blocked pending tenant admin consent. The
--   evidence above is all Databricks-side. Confirm with the Dynamics/VRA team
--   that dropping the GUID column was intentional.
--
-- FIX
--   Recreate the view WITH SCHEMA EVOLUTION instead of SCHEMA COMPENSATION.
--   EVOLUTION lets a column-list-free `SELECT *` view absorb added, dropped,
--   renamed and retyped columns automatically, so routine Dataverse column churn
--   stops breaking this view. COMPENSATION/BINDING will keep re-breaking on every
--   upstream rename.
--   Requires DBR 15.3+ / Databricks SQL. Sibling dataverse_*_vw views in edw_gold
--   are the same plain `SELECT *` shape, so this keeps the pattern consistent.
--
-- IMPACT
--   After this runs the view exposes 191 columns.
--   `_vrarp_residentworkflowrequirement_value` disappears from the view (it no
--   longer exists upstream).
--
--   Downstream consumers must migrate to `resident_workflow_requirement`, which
--   now carries the 75 values as resolved text. Do NOT point them at
--   `_vrarp_residentworkflowrequirement1_value` -- that is a different, empty
--   field. Consumers that joined on the old GUID need to switch to matching on
--   the label instead.
--
--   Nothing in this repo selects the dropped column from this view; the only
--   hits are PBI TMDL column definitions.
--
-- WHO MUST RUN THIS
--   NOT runnable by bhargav.narasimhan@radpartners.com. edw_prod.edw_gold grants
--   SEC-AZ-DBX-P-EA-ADM only SELECT / USE SCHEMA / EXECUTE / READ VOLUME -- no
--   CREATE TABLE or MODIFY. The view is owned by pxp.priv@radpartners.com.
--   Hand this to the EDW platform team (view owner) or a metastore admin.
--
-- Verified against edw_prod on 2026-10-26.

CREATE OR REPLACE VIEW edw_prod.edw_gold.`dataverse_m365-vra-dynamics-prod_rad_onboarding_vw`
WITH SCHEMA EVOLUTION
AS
SELECT * FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding;


-- ---------------------------------------------------------------------------
-- VERIFICATION (run after the DDL above)
-- ---------------------------------------------------------------------------

-- 1. View resolves again and column count matches the base table (expect 191/191).
SELECT
  (SELECT COUNT(*) FROM edw_prod.information_schema.columns
     WHERE table_schema = 'edw_gold'
       AND table_name   = 'dataverse_m365-vra-dynamics-prod_rad_onboarding_vw') AS view_cols,
  (SELECT COUNT(*) FROM edw_prod.information_schema.columns
     WHERE table_schema = 'dataverse_m365-vra-dynamics-prod'
       AND table_name   = 'rad_onboarding')                                     AS base_cols;

-- 2. No residual drift (expect zero rows).
WITH v AS (
  SELECT column_name FROM edw_prod.information_schema.columns
  WHERE table_schema = 'edw_gold'
    AND table_name   = 'dataverse_m365-vra-dynamics-prod_rad_onboarding_vw'
), t AS (
  SELECT column_name FROM edw_prod.information_schema.columns
  WHERE table_schema = 'dataverse_m365-vra-dynamics-prod'
    AND table_name   = 'rad_onboarding'
)
SELECT COALESCE(v.column_name, t.column_name) AS column_name,
       CASE WHEN v.column_name IS NULL THEN 'ONLY_IN_BASE' ELSE 'ONLY_IN_VIEW' END AS status
FROM v FULL OUTER JOIN t ON v.column_name = t.column_name
WHERE v.column_name IS NULL OR t.column_name IS NULL;

-- 3. The lookup values survived the swap (expect 75 non-null / 2 distinct labels,
--    and 0 non-null for the new, empty GUID column).
SELECT COUNT(*)                                            AS total,
       COUNT(resident_workflow_requirement)                AS label_nonnull,
       COUNT(DISTINCT resident_workflow_requirement)       AS distinct_labels,
       COUNT(_vrarp_residentworkflowrequirement1_value)    AS new_guid_nonnull
FROM edw_prod.edw_gold.`dataverse_m365-vra-dynamics-prod_rad_onboarding_vw`;

-- 4. Confirm the binding mode stuck (look for WITH SCHEMA EVOLUTION, no column list).
SHOW CREATE TABLE edw_prod.edw_gold.`dataverse_m365-vra-dynamics-prod_rad_onboarding_vw`;
