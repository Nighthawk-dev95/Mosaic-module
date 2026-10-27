-- Supersedes 051 (daily gate fix, carried forward unchanged here) and 052
-- (draft_not_available_by_hour_vw.sql, a separate view) - merged into one object per user
-- request, so Genie and PBI both query a single source instead of two: "its all in one view and
-- users can easily query that through Genie."
--
-- Adds hour_of_day_read (= v.hour, the view's pre-existing "7am-8am"-style label, same field
-- already confirmed to equal HOUR(Dictation_Start_DateTime) and to match the model's existing
-- Hour_order sort table) as a new column, flowing through every category - not just the 2
-- DRAFT-not-available ones. Verified live before writing this: adding it to the GROUP BY takes
-- the view from 5,806,989 rows to 9,324,756 (1.6x) - a real but modest increase, not a blow-up,
-- since most other categories collapse hour down heavily (an exam that was never opened, for
-- instance, has no Dictation_Start_DateTime and so no hour at all). Acceptable for a single
-- Genie-facing source.
--
-- NULL hour note: exams with no Dictation_Start_DateTime (never opened, or opened but dictation
-- never started) get hour_of_day_read = NULL. Left in rather than filtered - those rows are
-- still valid for every other dimension (week, category, practice, etc.), they just can't be
-- plotted on an hour-of-day axis. Anyone building that specific chart (PBI or Genie) should add
-- `WHERE hour_of_day_read IS NOT NULL` themselves, same as 052 did internally.
--
-- 052_draft_not_available_by_hour_vw.sql is superseded by this file and the standalone
-- "Draftable By Hour" PBI table built from it should be removed once this is deployed and the
-- main Draftable table's PBI query is refreshed to pick up the new column - ask before deleting
-- it, don't assume.
--
-- Everything else (CTEs, categorization CASE, go-live gating, consent/launch_group exclusions)
-- is byte-for-byte identical to 051.

CREATE OR REPLACE VIEW bipa_analytics.examsnotdraftedbutdraftable_vw (
  week_end,
  Calendar_Date COMMENT 'Daily exam date within the week ending on week_end. Added 2026-10-23 to give the PBI Draftable table a true daily grain.',
  hour_of_day_read COMMENT 'Hour the radiologist opened/began dictating the exam, as a "7am-8am"-style label (= v.hour from presentation_mosaicdailyvolume_vw, equivalent to HOUR(Dictation_Start_DateTime)). NULL when the exam was never opened or dictation never started - filter those out for an hour-of-day chart. This is "time read," not "time ordered" - no reliable join to an order-time field was found (see 052''s header for what was checked and ruled out).',
  Team,
  local_practice,
  site,
  Radiologist,
  exam_category,
  drafting_model COMMENT 'Declared AI drafting model or capturable category for this RPID. Seven values as of 2026-09-28: XR/MSK 342, US Capturable 178, CT Abd/Pel 45, CT Chest 37, CT Spine 13, DEXA Capturable 9, CT Head 3. This is DECLARED coverage, not observed drafting behaviour -- do NOT confuse it with tbl_exam_inventory.rpid_draftable_flag, which is an empirical trailing-30-day drafted-share threshold. A code absent from this view is unmapped, not undraftable.',
  category,
  npi,
  category_sort_order,
  exam_count,
  tbwu)
WITH SCHEMA COMPENSATION
AS WITH drafting_codes AS (
  SELECT DISTINCT rpid_procedure_code AS ProcCode, drafting_model
  FROM edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw
),

xwalk_dedup AS (
  SELECT ParentRpt, MIN(Category) AS Category
  FROM edw_dev.bipa_analytics.exam_category_lookup_xwalk
  GROUP BY ParentRpt
),

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
    v.Calendar_Date,
    DATE_SUB(
      CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
           ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
      6
    ) AS week_end,
    v.Team, v.local_practice_short_name AS local_practice, v.Location_Name AS site, v.Radiologist, v.npi,
    x.Category AS exam_category, v.TBWU, dc.drafting_model,
    v.mosaic_draft_flag,
    UPPER(TRIM(NULLIF(ro.mosaic_drafting_consent, 'None'))) AS consent_upper,
    me.week_enabled,
    v.Unread_DateTime,
    v.hour AS hour_of_day_read,
    e.go_live_date AS practice_model_go_live_date,
    (v.Unread_DateTime IS NOT NULL AND v.Dictation_Start_DateTime IS NOT NULL
     AND (UNIX_TIMESTAMP(v.Dictation_Start_DateTime) - UNIX_TIMESTAMP(v.Unread_DateTime)) < 300) AS read_within_5min
  FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw v
  INNER JOIN drafting_codes dc ON dc.ProcCode = v.Clinical_Procedure_Code
  LEFT JOIN ro_dedup ro ON ro.NPI = v.NPI
  LEFT JOIN xwalk_dedup x ON x.ParentRpt = v.Clinical_Procedure_Code
  LEFT JOIN edw_dev.bipa_analytics.drafting_model_practice_enablement e
    ON e.local_practice = v.local_practice_short_name AND e.drafting_model = dc.drafting_model
  LEFT JOIN model_enabled_by_week me
    ON me.NPI = v.NPI AND me.drafting_model = dc.drafting_model
    AND me.week_end = DATE_SUB(
          CASE WHEN DAYOFWEEK(v.Calendar_Date) = 1 THEN v.Calendar_Date
               ELSE NEXT_DAY(v.Calendar_Date, 'SUN') END,
          6)
  WHERE v.Mosaic_flag = 1
    AND NOT (dc.drafting_model = 'CT Chest' AND v.Calendar_Date < '2026-07-06')
    AND NOT (dc.drafting_model = 'CT Spine' AND v.Calendar_Date < '2026-08-31')
    AND (ro.launch_group IS NULL OR ro.launch_group NOT IN ('Do Not Launch', 'Do Not Revisit'))
),

categorized AS (
  SELECT *,
    CASE
      WHEN mosaic_draft_flag = 1 THEN 'Drafted'
      WHEN drafting_model = 'CT Chest' AND NOT (
        (practice_model_go_live_date IS NOT NULL AND Calendar_Date >= practice_model_go_live_date)
        OR Team IN ('Matrix','SEAL Team')
      ) THEN 'PRACTICE not enabled for model'
      WHEN drafting_model = 'CT Spine' AND NOT (
        (practice_model_go_live_date IS NOT NULL AND Calendar_Date >= practice_model_go_live_date)
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
  week_end, Calendar_Date, hour_of_day_read, Team, local_practice, site, Radiologist, exam_category, drafting_model, category, npi,
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
WHERE Calendar_Date < CURRENT_DATE()
GROUP BY week_end, Calendar_Date, hour_of_day_read, Team, local_practice, site, Radiologist, exam_category, drafting_model, category, npi
