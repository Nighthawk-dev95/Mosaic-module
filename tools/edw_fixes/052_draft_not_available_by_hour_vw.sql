-- New view for the hour-of-day "Draft Not Available" page: stacked bar, 2 stacks (<5 min /
-- >5 min), one bar per hour of day (0-23). Same base population as
-- examsnotdraftedbutdraftable_vw (051_examsnotdraftedbutdraftable_daily_gate_fix.sql must be
-- deployed first/alongside - this view duplicates those CTEs rather than reading the other view,
-- same pattern as every other file in this folder, so it has no deploy-order dependency on it),
-- restricted to just the two DRAFT-not-available categories.
--
-- HOUR BASIS - "time read" only, NOT "time ordered":
-- "Time read" = HOUR(Dictation_Start_DateTime), i.e. when the radiologist actually started
-- dictating/opening the study. Confirmed live that this is exactly what
-- presentation_mosaicdailyvolume_vw's own Time_Hour/hour columns already compute (spot-checked
-- 10 rows, all matched HOUR(Dictation_Start_DateTime) exactly) - using it here is not a new
-- concept, just reusing the view's existing convention at exam grain instead of pre-bucketed.
--
-- "Time ordered" (order_datetime) is NOT included - could not find a reliable join from
-- presentation_mosaicdailyvolume_vw to tbl_exam_inventory (which is where order_datetime lives).
-- Checked and ruled out live:
--   - Exam_ID: zero matches on 20 sampled Mosaic-flagged exam_ids from presentation_mosaicdailyvolume_vw
--     against tbl_exam_inventory.exam_id - different ID spaces entirely, not just unmatched rows.
--   - Accession_Number: formats don't correspond either (e.g. "00000CT260035002HFC" in this view
--     vs "PR-002283824TRIPR" in tbl_exam_inventory) - looks like genuinely different source
--     pipelines, not a formatting quirk of the same key.
--   - No dedicated bridge/crosswalk table exists (checked information_schema for
--     exam*bridge/xwalk/crosswalk/map patterns - only hit was the unrelated
--     ref_exam_category_lookup_xwalk).
-- If "time ordered" still matters for the GPU-capacity question, that needs a confirmed join key
-- between the two tables first (flag to the team maintaining the Enterprise Analytics migration -
-- they may already have solved this) - do not guess one (e.g. NPI + date) here, since a wrong
-- join silently fans out or drops rows rather than erroring.

CREATE OR REPLACE VIEW bipa_analytics.draft_not_available_by_hour_vw (
  week_end,
  Calendar_Date COMMENT 'Exam date. Same day-level gate as examsnotdraftedbutdraftable_vw (051) - excludes only today, not the whole in-progress week.',
  hour_of_day_read COMMENT 'HOUR(Dictation_Start_DateTime), 0-23 - when the radiologist started dictating/opened the study. See file header for why time-ordered is not available here.',
  Team,
  local_practice,
  site,
  drafting_model,
  category,
  exam_count,
  tbwu)
WITH SCHEMA COMPENSATION
AS WITH drafting_codes AS (
  SELECT DISTINCT rpid_procedure_code AS ProcCode, drafting_model
  FROM edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw
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
    v.Team, v.local_practice_short_name AS local_practice, v.Location_Name AS site,
    v.TBWU, dc.drafting_model, v.mosaic_draft_flag,
    UPPER(TRIM(NULLIF(ro.mosaic_drafting_consent, 'None'))) AS consent_upper,
    me.week_enabled,
    v.Unread_DateTime, v.Dictation_Start_DateTime,
    HOUR(v.Dictation_Start_DateTime) AS hour_of_day_read,
    e.go_live_date AS practice_model_go_live_date,
    (v.Unread_DateTime IS NOT NULL AND v.Dictation_Start_DateTime IS NOT NULL
     AND (UNIX_TIMESTAMP(v.Dictation_Start_DateTime) - UNIX_TIMESTAMP(v.Unread_DateTime)) < 300) AS read_within_5min
  FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw v
  INNER JOIN drafting_codes dc ON dc.ProcCode = v.Clinical_Procedure_Code
  LEFT JOIN ro_dedup ro ON ro.NPI = v.NPI
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
    -- Only exams that were ever opened at all can land in one of the 2 target categories -
    -- prune here rather than in the outer category CASE, since it also makes hour_of_day_read
    -- non-null for every remaining row (an hour axis cannot plot a NULL hour).
    AND v.Unread_DateTime IS NOT NULL
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
      WHEN read_within_5min THEN 'DRAFT not available - Exam opened in <5 min'
      ELSE 'DRAFT not available - Exam opened in >5 min'
    END AS category
  FROM base
)

SELECT
  week_end, Calendar_Date, hour_of_day_read, Team, local_practice, site, drafting_model, category,
  COUNT(*) AS exam_count,
  SUM(TBWU) AS tbwu
FROM categorized
WHERE category IN ('DRAFT not available - Exam opened in <5 min', 'DRAFT not available - Exam opened in >5 min')
  AND Calendar_Date < CURRENT_DATE()
GROUP BY week_end, Calendar_Date, hour_of_day_read, Team, local_practice, site, drafting_model, category
