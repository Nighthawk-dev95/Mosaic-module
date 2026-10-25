-- STATUS (2026-10-21): READY TO DEPLOY - fixes the root cause found investigating why
-- historical weeks (9/28, 10/5) retroactively changed after the 2026-10-13 CT Chest practice
-- allowlist expansion (see 005_examsnotdraftedbutdraftable_use_rpids_view.sql's history).
--
-- Root cause: examsnotdraftedbutdraftable_vw's CASE logic gates CT Chest/CT Spine
-- "PRACTICE not enabled for model" on a flat, undated IN-list. The view has no concept of
-- "as of this historical week" - every query recomputes categorization using TODAY's list.
-- When 45 practices were added to the CT Chest list on 10/13, every one of THEIR exams from
-- EVERY past week got reclassified too - previously bucketed as "PRACTICE not enabled for
-- model", now falling through to "RAD not enabled - Incomplete process" instead, since they're
-- new to the model and haven't hit the 10% weekly-drafted threshold yet. Verified live: this
-- alone explains the jump from ~18K to ~22.7-22.9K "Incomplete process" exams for weeks 9/28
-- and 10/5 (reverting just the allowlist, keeping everything else current, reproduced
-- 19,572 / 18,753 - matching what the business user remembered).
--
-- Fix: replace the flat practice IN-list with a real (practice, model, go_live_date) table,
-- and gate on Calendar_Date >= go_live_date instead of static list membership. A practice/
-- model pair with no row here (or whose go_live_date is in the future relative to the exam)
-- is "not enabled" for that exam's date, same as "not in the list" today - but a practice
-- added to the model LATER no longer retroactively reclassifies its OWN past exams, because
-- those exams' Calendar_Date is before its own go_live_date.
--
-- Dates assigned from this project's own recent edits, not invented:
--   - CT Chest original ~28-practice list (live before 10/13) -> go_live_date = 2026-07-07
--     (the user's own "CT Chest Limited Release Date", one day after the 2026-07-06 hard
--     cutoff already baked into this view's WHERE clause).
--   - CT Chest +45 practices added 2026-10-13 -> go_live_date = 2026-10-13 (the user's own
--     "CT Chest Full Release Date" - this IS that rollout, not a coincidence).
--   - CT Spine's existing 21-practice list -> go_live_date = 2026-09-01 (the user's "CT Spine
--     Limited Release Date"; Full Release is still TBD, so there is no second wave yet).
--
-- CT Abd/Pel is explicitly OUT OF SCOPE for this file - it currently has NO practice-
-- enablement gate at all in this view (confirmed: only CT Chest and CT Spine have a
-- "PRACTICE not enabled for model" branch), even though the user tracks Limited/Full Release
-- dates for it too. Adding that gate needs the user to confirm which practices were in CT
-- Abd/Pel's Limited Release cohort vs added later - parked as an explicit follow-up, not
-- silently done here.
--
-- "RP Tucson" and "RP West Texas" (from the original 45-practice list) are intentionally
-- omitted below - confirmed earlier this investigation that neither exists as a real
-- local_practice_short_name; they're almost certainly informal names for RP Sol / RP Eagle,
-- both of which are already in this list under their real names with the same go-live date.
--
-- Verified live (as plain SELECTs, pre-DDL): the rewritten CASE reproduces sane category
-- counts for weeks 9/28 and 10/5 - see verification query run alongside this file.

CREATE TABLE IF NOT EXISTS edw_dev.bipa_analytics.drafting_model_practice_enablement (
  drafting_model STRING COMMENT 'Must match drafting_eligible_rpids_vw.drafting_model exactly.',
  local_practice STRING COMMENT 'Must match presentation_mosaicdailyvolume_vw.local_practice_short_name exactly.',
  go_live_date DATE COMMENT 'First date this practice counts as enabled for this drafting model. Exams dated before this are NOT drafting-eligible for this practice/model and fall into PRACTICE not enabled for model, not RAD not enabled - Incomplete process.',
  release_wave STRING COMMENT 'Which release wave this practice/model pairing belongs to, for audit/traceability only - e.g. "CT Chest Limited Release", "CT Chest Full Release 2026-10-13", "CT Spine Limited Release".'
)
COMMENT 'Date-effective practice enablement for Mosaic drafting models, read by examsnotdraftedbutdraftable_vw. Replaces the old flat practice-name allowlist (which had no concept of "as of when" and retroactively reclassified historical weeks every time a practice was added - see 011_date_effective_practice_enablement.sql header). Additive table, append new (practice, model, go_live_date) rows as new practices/models launch; never delete or backdate an existing row once historical reporting has been run against it.';

INSERT INTO edw_dev.bipa_analytics.drafting_model_practice_enablement
  (drafting_model, local_practice, go_live_date, release_wave)
VALUES
  ('CT Chest', 'CRC', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'NEOH', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'Rad Alliance', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ADI', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ADR', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RAF', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP Florida', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'MBB', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'Greensboro', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'DRSRP', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESR Long Island', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESR Metro Hudson', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESRMH Garnet', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESRMH Hackensack', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESRMH Legacy', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESRMH NY Metro', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'ESRMH Westchester', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'Jefferson', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP Crossroads', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RIMA', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'DR', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'DR DRS', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'DR Legacy', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'MIA', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP NWIR', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP Houston', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP Singleton', DATE'2026-07-07', 'CT Chest Limited Release'),
  ('CT Chest', 'RP Gulf Coast', DATE'2026-07-07', 'CT Chest Limited Release'),

  ('CT Chest', 'Spec Ops Reserve', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Community', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Lakefront Imaging', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Palm Beach', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Western Colorado', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'MXC', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Access Alexandria', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Access Lake Charles', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'ARSC', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'ARA', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Alaska', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'CIR', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'CIRPA', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Coastal', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'GIMA', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'GLI', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'IAM', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'IAMSE Hurley', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Mountain', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'PRA', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RAC', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RACSW', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RAI', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Red Rock', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Bluegrass', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Borderlands', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Brazosport', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Cascade', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Corpus Christi', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Chicago', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Dallas', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Eagle', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP East Florida', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP North Florida', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP El Paso', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Florida West', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Kentucky', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP SoCal', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Sol', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP South Carolina', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'Saline Valley', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'SOAR', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'SVDI', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),
  ('CT Chest', 'RP Helios', DATE'2026-10-13', 'CT Chest Full Release 2026-10-13'),

  ('CT Spine', 'CRC', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'NEOH', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'Rad Alliance', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'ADI', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RAC', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RAF', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'MBB', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'Greensboro', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'SOAR', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RIMA', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'MIA', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP NWIR', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP Chicago', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'Jefferson', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'DRSRP', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'ESR Long Island', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'ESR Metro Hudson', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP Florida', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP East Florida', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP Singleton', DATE'2026-09-01', 'CT Spine Limited Release'),
  ('CT Spine', 'RP Houston', DATE'2026-09-01', 'CT Spine Limited Release');

CREATE OR REPLACE VIEW edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw AS

WITH drafting_codes AS (
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
  week_end, Team, local_practice, site, Radiologist, exam_category, drafting_model, category, npi,
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
GROUP BY week_end, Team, local_practice, site, Radiologist, exam_category, drafting_model, category, npi
