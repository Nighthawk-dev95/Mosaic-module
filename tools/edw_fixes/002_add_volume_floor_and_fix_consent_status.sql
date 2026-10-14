-- Reconciles examsnotdraftedbutdraftable_vw against the documented methodology in
-- "Drafting Enablement Gaps to Close - Aug 2026.xlsx" (Definitions & Methodology / Data
-- Dictionary sheets), per the 2026-09-17 review of 3 discrepancies found:
--
--   1. Weekly re-evaluation + 10% drafted-volume threshold (model_enabled_by_week) - KEPT
--      AS-IS. Not a discrepancy: this was explicit VP feedback, not something the Excel's
--      simpler "any drafted volume > 0 over the whole reporting period" methodology
--      accounted for. The Excel and this view are intentionally different in this respect.
--
--   2. Minimum draftable-volume floor - ADDED. The Excel applies a per-model minimum
--      volume before judging enablement at all ("to avoid identifying gaps where there is
--      little or no meaningful drafting opportunity"): XR >=25, CT Head/CT A/P/CT Chest/
--      CT C-Spine >=5. Applied here as a per-(rad, model, week) floor: if a rad's case
--      count for a model in a given week is below that model's threshold, there isn't
--      enough signal to judge - week_enabled defaults to TRUE (i.e. don't penalize/flag as
--      "not enabled" on a statistically meaningless small sample) rather than applying the
--      10% ratio. Model-name mapping: this view's 'XR/MSK' = Excel's 'XR', 'CT Abd/Pel' =
--      'CT A/P', 'CT Spine' = 'CT C-Spine' (same models, different labels).
--
--   3. Consent-status exclusion list - FIXED. Was ('DECLINED', 'NO DRAFTING', 'DISABLED');
--      the Excel's three documented reliable exclusionary statuses are 'No Drafting',
--      'Declined', 'Termed' - 'DISABLED' was not one of them. Checked the live distinct
--      values in rad_onboarding.mosaic_drafting_consent_status before making this change:
--      neither 'DISABLED' nor 'TERMED' (the Excel's literal wording) actually exist in the
--      data (distinct values: SIGNED IRB, NO DRAFTING, SENT, DECLINED, TERM - 30 records).
--      Used 'TERM', the real value - 'TERMED' would have silently matched zero rows, the
--      same failure mode as the original 'DISABLED'.
--
--   4. Current in-progress week - NOW INCLUDED. Previously the final WHERE clause
--      (`DATE_ADD(week_end, 6) < CURRENT_DATE()`) dropped any week that hadn't fully
--      completed (Monday-Sunday) yet, so e.g. on 2026-09-17 the most recent week shown was
--      the one starting 2026-09-07, not 2026-09-14 - a 10-day-old ceiling that reads as
--      missing/broken data to anyone looking at the dashboard mid-week. That WHERE clause
--      is removed (no upper bound needed - the underlying exam data can't extend past
--      today anyway) and a new `is_partial_week` column is added instead: true for the
--      current week (and would be true for any future week, though none exist in the
--      data). Consumers should treat is_partial_week=true rows as still accumulating, not
--      comparable day-for-day against a completed week - this app's own query
--      (mosaic_service.py's get_undrafted_analysis, ~line 1101) uses an explicit column
--      list, not SELECT *, so it is unaffected until someone deliberately adds
--      is_partial_week to it and updates the frontend to flag it visually.
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

-- Only used now for the three consent values still treated as reliable exclusions.
-- 'TERM' replaces 'DISABLED' here - see file header, item 3.
ro_dedup AS (
  SELECT NPI, mosaic_drafting_consent
  FROM (
    SELECT
      CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) AS NPI,
      mosaic_drafting_consent_status AS mosaic_drafting_consent,
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
-- NEW: a per-model minimum weekly volume floor (see file header, item 2). Below the floor,
-- week_enabled defaults to TRUE - there isn't enough case volume that week to treat a low
-- drafted-ratio as evidence of an actual enablement gap, so this rad/model/week isn't
-- categorized as "not enabled" on that basis.
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
  -- NEW: true for the still-in-progress week (see file header, item 4). Was previously
  -- dropped entirely by a WHERE clause here - now surfaced, but flagged so consumers don't
  -- mistake a partial week's lower volume for a real trend change.
  DATE_ADD(week_end, 6) >= CURRENT_DATE() AS is_partial_week,
  COUNT(*) AS exam_count,
  SUM(TBWU) AS tbwu
FROM categorized
GROUP BY week_end, Team, local_practice, site, Radiologist, exam_category, drafting_model, category,
  DATE_ADD(week_end, 6) >= CURRENT_DATE()
