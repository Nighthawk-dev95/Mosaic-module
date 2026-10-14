-- STATUS (2026-10-04): READY TO DEPLOY - same root cause and fix as 008_*.sql (deploy
-- together), for the sibling enablement view. See 008_*.sql's header for the full
-- investigation: rad_onboarding.mosaic_drafting_consent was renamed to
-- mosaic_drafting_consent_status upstream; this view's `ranked` CTE still references the old
-- name, so every query fails with UNRESOLVED_COLUMN. mosaic_drafting_metric_vw joins both
-- this view and dynamics_rad_drafting_consent_vw and has no independent rad_onboarding
-- reference of its own (confirmed via its own SHOW CREATE TABLE), so fixing these two cascades
-- up and fixes it too - no separate file needed for it.
--
-- Verified live (as a plain SELECT, pre-DDL, reduced to the XR/CXR-ABD-MSK model column set
-- to keep the test query short - the fix is identical for all 6 models' unpivoted rows):
--   npi=1003018342  mosaic_drafting_consent='Signed IRB'  xr_drafting_enabled_flag=true

CREATE OR REPLACE VIEW enterprise_analytics.dynamics_rad_drafting_enablement_vw (
  npi COMMENT 'National Provider Identifier of the radiologist, decimal(10,0). Derived from the raw Dynamics string with thousands separators removed. Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.reading_provider_npi and to dynamics_rad_drafting_consent_vw.npi.',
  radiologist_name COMMENT 'Radiologist full name as maintained in Dynamics (Last, First). Display convenience only; it can lag legal name changes and is manually editable in Dynamics. Use MDM or Workday for the authoritative provider name.',
  practice_name COMMENT 'Practice label as entered in Dynamics rad onboarding. Free text maintained by the Clinical Transformation deployment team, NOT an MDM practice key. Do not join on this field; route the rad through NPI to MDM for governed practice attribution.',
  drafting_model COMMENT 'Mosaic drafting model family this row describes. Values as of 2026-09-03: \'XR (CXR/ABD/MSK)\' (chest, abdomen and MSK X-ray drafting), \'CT Head\', \'CT Abd Pelvis\', \'CT Chest\' (staged rollout, roughly 22 practices as of 2026-09-02), \'CT Cervical Spine\' (rollout started 2026-09-01), \'CTA Chest\' (early deployment; as of 2026-09-03 the source holds only placeholder 1900-01-01 AD group dates for it, which this view normalizes to NULL, so CTA Chest has no rows yet and will populate as the rollout starts). Triage has an AD group in the source but no training fields and is not a drafting model, so it is intentionally excluded. Which procedures (RPIDs) each model covers is defined by the Mosaic AI engineering team; that RPID-to-model mapping is a separate reference, not in this view.',
  training_sent_date COMMENT 'Date the model-specific drafting training was sent to the rad. Source: the drafting_training_sent_* column for this model, a M/d/yyyy string parsed to DATE; the raw string \'None\' is normalized to NULL. NULL means no training send recorded for this model.',
  training_completed_date COMMENT 'Date the rad completed the model-specific training. Per the deployment team, completing training triggers the IAM automation that adds the rad to the model AD group, so this usually equals ad_group_added_date; the two are stored separately on purpose so breaks in that automation are measurable rather than assumed away. Source: drafting_training_completed_* (note the source spells the CT Abd Pelvis column drafting_training_complete_ct_abd_pelvis, without the d).',
  ad_group_added_date COMMENT 'Date the rad was added to this model\'s AD group through Okta, which is what actually turns the model on for the rad. Use this as the start date of the rad\'s enablement on the model. KNOWN CAVEAT (2026-09-02): the Okta-to-Dynamics automation is partially broken and IAM is backfilling records, so recent dates can be missing or lag reality. The source uses 1900-01-01 as a placeholder date (seen on CTA Chest); this view normalizes it to NULL.',
  mosaic_drafting_consent COMMENT 'Rad-level Mosaic drafting consent (IRB) status, repeated on each model row for convenience. Same definition and caveats as dynamics_rad_drafting_consent_vw.mosaic_drafting_consent. One IRB covers all models; only the training and AD group are model-specific.',
  drafting_enabled_flag COMMENT 'TRUE when the rad signed the IRB (mosaic_drafting_consent = \'Signed IRB\') AND has an ad_group_added_date for this model. This is the Clinical Transformation definition of a rad being live on a drafting model. Whether a given exam was actually drafted comes from the exam-level drafting flags in tbl_exam_inventory, not from this view.')
COMMENT 'One row per radiologist (NPI) per Mosaic drafting model with any recorded enablement activity (training sent, training completed, or added to the AD group). Purpose: the governed, Genie-facing source of truth for per-model drafting enablement, answering which rads are enabled for which drafting model and since when. Source: edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding (Dataverse sync of Microsoft Dynamics 365 VRA), unpivoted from the per-model wide columns. Grain: one row per NPI x drafting_model; rad-model pairs with no activity at all are omitted. Duplicate source NPIs are deduplicated to the most recently modified row; rows with NULL or \'0\' NPI are excluded. Enablement rule (2026-09-02 call): a rad is live on a model when they signed the one-time IRB, completed the model-specific training, and were added to the model AD group via Okta/IAM. Scope rule: Dynamics is authoritative ONLY for these onboarding dimensions; exam volumes and metrics come from tbl_exam_inventory / MVR. KNOWN CAVEAT: the Okta-to-Dynamics automation is partially broken and IAM is backfilling enablement records as of 2026-09-02. Joins: npi = tbl_exam_inventory.reading_provider_npi; npi = dynamics_rad_drafting_consent_vw.npi. Lifecycle: view over the live Dataverse sync, no scheduled build. FIXED 2026-10-04: source column renamed upstream from mosaic_drafting_consent to mosaic_drafting_consent_status; this view was broken (UNRESOLVED_COLUMN on any query) until this fix.'
WITH SCHEMA COMPENSATION
AS WITH ranked AS (
  SELECT
    CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS npi_clean,
    radiologist,
    practice,
    NULLIF(mosaic_drafting_consent_status, 'None') AS consent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_cxr_abd_msk AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS xr_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_completed_cxr_abd_msk AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS xr_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_cxr_abd_msk AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS xr_ad,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_ct_head AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cthead_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_completed_ct_head AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cthead_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_ct_head AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cthead_ad,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_ct_abd_pelvis AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctabd_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_complete_ct_abd_pelvis AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctabd_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_ct_abd_pelvis AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctabd_ad,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_ct_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctchest_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_completed_ct_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctchest_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_ct_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS ctchest_ad,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_ct_cervical_spine AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS spine_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_completed_ct_cervical_spine AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS spine_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_ct_cervical_spine AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS spine_ad,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_sent_cta_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cta_sent,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(drafting_training_completed_cta_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cta_done,
    NULLIF(TRY_TO_DATE(NULLIF(CAST(added_to_ad_group_cta_chest AS STRING), 'None'), 'M/d/yyyy'), DATE'1900-01-01') AS cta_ad,
    ROW_NUMBER() OVER (
      PARTITION BY REPLACE(npi, ',', '')
      ORDER BY
        TRY_TO_TIMESTAMP(CAST(modified_on AS STRING), 'M/d/yyyy h:mm a') DESC NULLS LAST,
        TRY_TO_TIMESTAMP(CAST(created_on AS STRING), 'M/d/yyyy h:mm a') DESC NULLS LAST
    ) AS rn
  FROM edw_prod.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
  WHERE npi IS NOT NULL AND npi <> '0'
),
unpivoted AS (
  SELECT
    npi_clean,
    radiologist,
    practice,
    consent,
    STACK(6,
      'XR (CXR/ABD/MSK)', xr_sent,      xr_done,      xr_ad,
      'CT Head',           cthead_sent,  cthead_done,  cthead_ad,
      'CT Abd Pelvis',     ctabd_sent,   ctabd_done,   ctabd_ad,
      'CT Chest',          ctchest_sent, ctchest_done, ctchest_ad,
      'CT Cervical Spine', spine_sent,   spine_done,   spine_ad,
      'CTA Chest',         cta_sent,     cta_done,     cta_ad
    ) AS (drafting_model, training_sent_date, training_completed_date, ad_group_added_date)
  FROM ranked
  WHERE rn = 1
)
SELECT
  npi_clean                                   AS npi,
  radiologist                                 AS radiologist_name,
  practice                                    AS practice_name,
  drafting_model,
  training_sent_date,
  training_completed_date,
  ad_group_added_date,
  consent                                     AS mosaic_drafting_consent,
  COALESCE(consent = 'Signed IRB', FALSE)
    AND ad_group_added_date IS NOT NULL       AS drafting_enabled_flag
FROM unpivoted
WHERE training_sent_date IS NOT NULL
   OR training_completed_date IS NOT NULL
   OR ad_group_added_date IS NOT NULL
