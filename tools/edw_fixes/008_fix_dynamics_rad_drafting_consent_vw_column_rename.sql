-- STATUS (2026-10-04): READY TO DEPLOY - verified live via read-only SELECT (not yet run as
-- DDL, read-only EDW tool access can't execute CREATE VIEW). User has admin privileges on
-- edw_prod.enterprise_analytics and will run this directly.
--
-- Root cause (confirmed via SHOW CREATE TABLE): this view's `ranked` CTE selects
-- `mosaic_drafting_consent` straight off edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding,
-- but that column doesn't exist on the live table anymore - DESCRIBE confirms rad_onboarding
-- only has `mosaic_drafting_consent_status` now (plus an unrelated, entirely-NULL
-- `mosaic_drafting_model` column - 5,529/5,529 rows are 'None', confirmed live, not the fix).
-- The raw Dataverse sync renamed this column upstream at some point after the view's own
-- comments were last updated (internally dated "as of 2026-09-03"), and the view definition
-- was never updated to match - every query against it fails immediately with
-- UNRESOLVED_COLUMN, even `SELECT *`, since the broken reference is inside the view's own
-- CTE. mosaic_drafting_metric_vw joins this view (and dynamics_rad_drafting_enablement_vw,
-- see 009_*.sql) and has no independent rad_onboarding reference of its own, so it inherits
-- this same failure and needs no separate fix - confirmed via its SHOW CREATE TABLE, zero
-- hits for "rad_onboarding"/"dataverse_m365".
--
-- Fix: swap the one broken column reference for mosaic_drafting_consent_status. Confirmed
-- live that it holds exactly the values this view's own comment already documents
-- ('Signed IRB', 'No Drafting', 'Sent', 'Declined', 'Term', NULL). Nothing else changes -
-- same output column name (mosaic_drafting_consent), same comments, same logic - this is a
-- pure source-column-name fix, not a semantic change for any consumer.
--
-- Verified live (as a plain SELECT, pre-DDL) - returns sane data, e.g.:
--   npi=1003018342  mosaic_drafting_consent='Signed IRB'  irb_signed_flag=true  ad_group_date=2026-01-29

CREATE OR REPLACE VIEW enterprise_analytics.dynamics_rad_drafting_consent_vw (
  npi COMMENT 'National Provider Identifier of the radiologist, decimal(10,0). Derived from the raw Dynamics string with thousands separators removed (source stores values like 1,902,096,704). Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.reading_provider_npi and to dynamics_rad_drafting_enablement_vw.npi.',
  mosaic_drafting_consent COMMENT 'Mosaic drafting consent (IRB) status for the rad. Valid values as of 2026-09-03: \'Signed IRB\' (consented), \'Sent\' (consent request sent, not yet signed), \'No Drafting\' (opted out), \'Declined\', \'Term\' (radiologist termed), NULL (no outreach recorded; the raw string \'None\' is normalized to NULL). One IRB covers ALL drafting models plus triage; model-specific readiness lives in dynamics_rad_drafting_enablement_vw. The IRB SIGNING DATE is not captured in Dynamics as of 2026-09-02; adding it is an open request with the Clinical Transformation deployment team.',
  irb_signed_flag COMMENT 'TRUE when mosaic_drafting_consent = \'Signed IRB\', else FALSE (including NULL consent). Convenience boolean for counting consented rads.',
  ad_group_date COMMENT 'Earliest date the rad was added to ANY Mosaic drafting AD group (across all models and triage). Computed as the minimum of the per-model added_to_ad_group_* columns from the source rad_onboarding table, parsed from M/d/yyyy strings. NULL means the rad has not been added to any AD group.')
COMMENT 'One row per radiologist (NPI) with their Mosaic drafting consent (IRB) status and earliest AD group date. Purpose: the governed, Genie-facing source of truth for which rads signed the Mosaic drafting IRB. Source: edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding, the Dataverse sync of the Microsoft Dynamics 365 VRA environment maintained by the Clinical Transformation deployment team (some fields are manually edited in Dynamics). Grain: one row per NPI. The source holds a handful of duplicate NPIs (5 as of 2026-09-03, mostly legal name changes); this view keeps only the most recently modified row per NPI. Rows with NULL or \'0\' NPI are excluded (22 rows as of 2026-09-03). Scope rule from the 2026-09-02 governance call: Dynamics is authoritative ONLY for onboarding dimensions (consent, training, AD group); exam volumes and all exam metrics come from tbl_exam_inventory / the MVR semantics, never from Dynamics. Joins: npi = tbl_exam_inventory.reading_provider_npi; npi = dynamics_rad_drafting_enablement_vw.npi. Lifecycle: view over the live Dataverse sync, no scheduled build. FIXED 2026-10-04: source column renamed upstream from mosaic_drafting_consent to mosaic_drafting_consent_status; this view was broken (UNRESOLVED_COLUMN on any query) until this fix.'
WITH SCHEMA COMPENSATION
AS WITH ranked AS (
  SELECT
    CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS npi_clean,
    NULLIF(mosaic_drafting_consent_status, 'None') AS consent,
    TO_DATE(NULLIF(added_to_ad_group_cxr_abd_msk, 'None'), 'M/d/yyyy') AS ad_cxr,
    TO_DATE(NULLIF(added_to_ad_group_ct_head, 'None'), 'M/d/yyyy') AS ad_ct_head,
    TO_DATE(NULLIF(added_to_ad_group_ct_chest, 'None'), 'M/d/yyyy') AS ad_ct_chest,
    TO_DATE(NULLIF(added_to_ad_group_cta_chest, 'None'), 'M/d/yyyy') AS ad_cta_chest,
    TO_DATE(NULLIF(added_to_ad_group_ct_abd_pelvis, 'None'), 'M/d/yyyy') AS ad_ct_abd,
    TO_DATE(NULLIF(added_to_ad_group_ct_cervical_spine, 'None'), 'M/d/yyyy') AS ad_ct_cerv,
    TO_DATE(NULLIF(added_to_ad_group_triage, 'None'), 'M/d/yyyy') AS ad_triage,
    ROW_NUMBER() OVER (
      PARTITION BY REPLACE(npi, ',', '')
      ORDER BY
        TRY_TO_TIMESTAMP(CAST(modified_on AS STRING), 'M/d/yyyy h:mm a') DESC NULLS LAST,
        TRY_TO_TIMESTAMP(CAST(created_on AS STRING), 'M/d/yyyy h:mm a') DESC NULLS LAST
    ) AS rn
  FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
  WHERE npi IS NOT NULL AND npi <> '0'
)
SELECT
  npi_clean                                   AS npi,
  consent                                     AS mosaic_drafting_consent,
  COALESCE(consent = 'Signed IRB', FALSE)     AS irb_signed_flag,
  ARRAY_MIN(ARRAY(ad_cxr, ad_ct_head, ad_ct_chest, ad_cta_chest, ad_ct_abd, ad_ct_cerv, ad_triage)) AS ad_group_date
FROM ranked
WHERE rn = 1
