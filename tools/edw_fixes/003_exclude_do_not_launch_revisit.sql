-- Excludes radiologists flagged 'Do Not Launch' or 'Do Not Revisit' (rad_onboarding.launch_group)
-- from examsnotdraftedbutdraftable_vw entirely, per 2026-09-18 request - these rads should
-- never appear in this analysis at all, not just be recategorized.
--
-- Confirmed live values in rad_onboarding.launch_group (most-recent row per NPI, same dedup
-- already used for consent status): 'Do Not Launch' (2,401 rads), 'Do Not Revisit' (340 rads) -
-- exact match for what was asked, no naming variants to reconcile.
--
-- Built on top of the current live view definition (confirmed via SHOW CREATE TABLE on
-- 2026-09-18 - the 002 migration's volume floor + TERM fix are already deployed; its
-- is_partial_week change is NOT yet deployed, so this file preserves the WHERE clause exactly
-- as currently live rather than re-introducing that unrelated pending change here).
--
-- Change: ro_dedup now also carries launch_group (same NPI, same modified_on-desc dedup - no
-- new join, no new performance cost). base's WHERE clause excludes rows where the rad's
-- most-recent launch_group is one of the two excluded values. NULL/blank launch_group is NOT
-- excluded - only an explicit 'Do Not Launch'/'Do Not Revisit' removes a rad.
--
-- This file has NOT been run - the Databricks connector available to this session is
-- read-only. A human with CREATE VIEW on edw_dev.bipa_analytics needs to run it.

CREATE OR REPLACE VIEW edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw AS

WITH drafting_codes AS (
  SELECT DISTINCT
    `Procedure Code` AS ProcCode,
    CASE
      WHEN UPPER(`Procedure Name`) LIKE '%SPINE%' THEN 'CT Spine'
      WHEN UPPER(`Procedure Name`) LIKE 'CT CHEST%' THEN 'CT Chest'
      WHEN UPPER(`Procedure Name`) LIKE 'CT HEAD%' THEN 'CT Head'
      WHEN `Procedure Code` IN (
        'CT3PHLIV','RPID152-3D','RPID1060-3D','RPID1449','RPID279','RPID140','RAD2508','RPID152','RPID1060',
        'RPID1459','CTAPRENALMA','RPID1643D','RPID164','RAD2260','RAD2262','RAD2261','RPID145','RPID145-RC',
        'RPID144','RPID144RC','RPID144-RC','RPID198','RPID198-IVP3D','RPID198-RC','RPID5','RPID3','RPID4',
        'RAD2345','RAD2346','RAD2011','RPID48-B','RPID46-B','RAD2266','RAD2012','RAD2013','RAD2014','RPID64',
        'RPID48','RPID48MR','RPID68-MIP','RPID48-RC','RPID46','RPID47','RPID47MR','RPID47-RC','CT4PHLIV',
        'RAD2852','RAD2853','RPID46-RC','RAD2854','RAD2986','RAD2987'
      ) THEN 'CT Abd/Pel'
      ELSE 'XR/MSK'
    END AS drafting_model
  FROM edw_dev.bipa_analytics.`251212_xr_drafting_procedure_codes`
),

xwalk_dedup AS (
  SELECT ParentRpt, MIN(Category) AS Category
  FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk
  GROUP BY ParentRpt
),

-- Now carries launch_group too (see file header) alongside the three consent values still
-- treated as reliable exclusions.
ro_dedup AS (
  SELECT NPI, mosaic_drafting_consent, launch_group
  FROM (
    SELECT
      CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS NPI,
      mosaic_drafting_consent_status AS mosaic_drafting_consent,
      launch_group,
      ROW_NUMBER() OVER (PARTITION BY CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0))
                         ORDER BY modified_on DESC) AS rn
    FROM `edw_prod`.`dataverse_m365-vra-dynamics-prod`.rad_onboarding
    WHERE npi IS NOT NULL AND REPLACE(npi, ',', '') <> '0'
  ) WHERE rn = 1
),

-- Week-by-week volume-based enablement: a rad is "on" a model for a given week if >=10% of
-- their cases of that model were drafted that same week - re-evaluated fresh every week, not a
-- one-time cumulative fact. This is what makes it resilient to (a) an isolated erroneously-
-- flagged exam, which gets diluted below 10% by the rest of that week's volume instead of
-- permanently flipping the rad to "enabled," and (b) a rad who later drops out of drafting,
-- whose subsequent weeks correctly revert to "not enabled" once their weekly % falls back to 0,
-- rather than staying locked in from one early success.
--
-- Per-model minimum weekly volume floor: below the floor, week_enabled defaults to TRUE -
-- there isn't enough case volume that week to treat a low drafted-ratio as evidence of an
-- actual enablement gap, so this rad/model/week isn't categorized as "not enabled" on that basis.
model_enabled_by_week AS (
  SELECT
    v.NPI, dc.drafting_model,
    DATE_SUB(
      CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
           ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
      6
    ) AS week_end,
    CASE
      WHEN COUNT(*) < CASE dc.drafting_model
             WHEN 'XR/MSK' THEN 25
             ELSE 5
           END
      THEN TRUE
      ELSE (SUM(CASE WHEN v.mosaic_draft_flag = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) >= 0.10
    END AS week_enabled
  FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw v
  INNER JOIN drafting_codes dc ON dc.ProcCode = v.Clinical_Procedure_Code
  WHERE v.Mosaic_flag = 1
  GROUP BY v.NPI, dc.drafting_model,
    DATE_SUB(
      CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
           ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
      6
    )
),

base AS (
  SELECT
    DATE_SUB(
      CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
           ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
      6
    ) AS week_end,
    v.Team, v.local_practice_short_name AS local_practice, v.Location_Name AS site, v.Radiologist,
    x.Category AS exam_category, v.TBWU, dc.drafting_model,
    v.mosaic_draft_flag,
    UPPER(TRIM(NULLIF(ro.mosaic_drafting_consent, 'None'))) AS consent_upper,
    me.week_enabled,
    v.Unread_DateTime,
    (v.Unread_DateTime IS NOT NULL AND v.Dictation_Start_DateTime IS NOT NULL
     AND (UNIX_TIMESTAMP(v.Dictation_Start_DateTime) - UNIX_TIMESTAMP(v.Unread_DateTime)) < 300) AS read_within_5min
  FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw v
  INNER JOIN drafting_codes dc ON dc.ProcCode = v.Clinical_Procedure_Code
  LEFT JOIN ro_dedup ro ON ro.NPI = v.NPI
  LEFT JOIN xwalk_dedup x ON x.ParentRpt = v.Clinical_Procedure_Code
  LEFT JOIN model_enabled_by_week me
    ON me.NPI = v.NPI AND me.drafting_model = dc.drafting_model
    AND me.week_end = DATE_SUB(
          CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
               ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
          6)
  WHERE v.Mosaic_flag = 1
    AND NOT (dc.drafting_model = 'CT Chest' AND v.Calendar_Date < '2026-07-06')
    AND NOT (dc.drafting_model = 'CT Spine' AND v.Calendar_Date < '2026-08-31')
    -- NEW: drop rads flagged 'Do Not Launch' or 'Do Not Revisit' from the whole analysis.
    -- NULL/blank launch_group is NOT excluded - only these two explicit values are.
    AND (ro.launch_group IS NULL OR ro.launch_group NOT IN ('Do Not Launch', 'Do Not Revisit'))
),

categorized AS (
  SELECT *,
    CASE
      WHEN mosaic_draft_flag = 1 THEN 'Drafted'
      WHEN drafting_model = 'CT Chest' AND NOT (
        local_practice IN ('CRC','NEOH','Rad Alliance','ADI','ADR','RAF','RP Florida','MBB','Greensboro',
          'DRSRP','ESR Long Island','ESR Metro Hudson','ESRMH Garnet','ESRMH Hackensack','ESRMH Legacy',
          'ESRMH NY Metro','ESRMH Westchester','Jefferson','RP Crossroads','RIMA','DR','DR DRS','DR Legacy',
          'MIA','RP NWIR','RP Houston','RP Singleton','RP Gulf Coast')
        OR Team IN ('Matrix','SEAL Team')
      ) THEN 'PRACTICE not enabled for model'
      WHEN drafting_model = 'CT Spine' AND NOT (
        local_practice IN ('CRC','NEOH','Rad Alliance','ADI','RAC','RAF','MBB','Greensboro','SOAR',
          'RIMA','MIA','RP NWIR','RP Chicago','Jefferson','DRSRP','ESR Long Island','ESR Metro Hudson',
          'RP Florida','RP East Florida','RP Singleton','RP Houston')
        OR Team IN ('Matrix','SEAL Team')
      ) THEN 'PRACTICE not enabled for model'
      WHEN consent_upper = 'DECLINED' THEN 'RAD not enabled - Rad declined'
      WHEN consent_upper IN ('NO DRAFTING', 'TERM') THEN 'RAD not enabled - Ops declined'
      WHEN NOT week_enabled THEN 'RAD not enabled - Incomplete process'
      WHEN Unread_DateTime IS NULL THEN 'Exam never opened, not drafted'
      WHEN read_within_5min THEN 'DRAFT not available - Exam opened in <5 min'
      ELSE 'DRAFT not available - Exam opened in >5 min'
    END AS category
  FROM base
)

SELECT
  week_end, Team, local_practice, site, Radiologist, exam_category, drafting_model, category,
  CASE category
    WHEN 'Drafted' THEN 0
    WHEN 'RAD not enabled - Rad declined' THEN 1
    WHEN 'RAD not enabled - Ops declined' THEN 2
    WHEN 'RAD not enabled - Incomplete process' THEN 3
    WHEN 'PRACTICE not enabled for model' THEN 4
    WHEN 'DRAFT not available - Exam opened in <5 min' THEN 5
    WHEN 'DRAFT not available - Exam opened in >5 min' THEN 6
    WHEN 'Exam never opened, not drafted' THEN 7
  END AS category_sort_order,
  COUNT(*) AS exam_count,
  SUM(TBWU) AS tbwu
FROM categorized
WHERE DATE_ADD(week_end, 6) < CURRENT_DATE()
GROUP BY week_end, Team, local_practice, site, Radiologist, exam_category, drafting_model, category
