-- Points examsnotdraftedbutdraftable_vw's drafting_model classification at
-- edw_prod.bipa_analytics.draftingeligiblerpids_vw (built/validated 2026-09-23) instead of
-- maintaining a second, separately-drifting copy of the same CASE logic against
-- edw_dev.bipa_analytics.251212_xr_drafting_procedure_codes. One source of truth for
-- "what drafting model is this procedure code" from here on - fix it once in
-- draftingeligiblerpids_vw, both views (and anything else that reads it) get the update.
--
-- DEPLOY ORDER MATTERS: this file assumes 004_add_drafting_model_to_rpids.sql (the version
-- with the whitespace fix, CTA CHEST handling, CT Neck -> CT Head, and RAD2008 -> CT Chest)
-- is already deployed. If it isn't yet, this view will inherit whatever stale classification
-- is currently live on draftingeligiblerpids_vw - deploy 004 first.
--
-- Verified live before writing this: the 3 Procedure Codes with duplicate rows in
-- draftingeligiblerpids_vw (RAD2311, RAD2526, RPID2590 - all name-variant duplicates, e.g.
-- "XR ABDOMEN 4 VIEWS MINIMUM WITH AP CHEST (ABD ACUTE SERIES)" vs "...- ABD ACUTE SERIES")
-- each map to exactly one distinct drafting_model, so no classification conflict - but
-- SELECT DISTINCT is still used below to avoid a join fan-out (duplicate ProcCode rows
-- would otherwise double/triple-count exam volume for those specific codes when joined to
-- presentation_mosaicdailyvolume_vw).
--
-- Everything else in this view (model_enabled_by_week, base, categorized, the volume floor,
-- the practice-enablement lists, the consent-status/launch_group exclusions) is unchanged
-- from 003_exclude_do_not_launch_revisit.sql - only the drafting_codes CTE's definition
-- changes here.
--
-- This file has NOT been run - the Databricks connector available to this session is
-- read-only. A human with CREATE VIEW on edw_dev.bipa_analytics needs to run it.
--
-- Dependency check (2026-09-30): confirmed 004 is already live - draftingeligiblerpids_vw
-- has 627 rows / 7 distinct drafting_model values as expected.
--
-- PRE-DEPLOY FIX (2026-09-30): this file was missing `npi` entirely (base CTE, final
-- SELECT, and GROUP BY) - comparing against `SHOW CREATE TABLE` on the current live view
-- (which already has 002/003 applied) showed `npi` present throughout there. Deploying this
-- file as originally written would have silently dropped that column from the view,
-- breaking any NPI-level drill-down against it. Added `v.npi` to the base CTE and `npi` to
-- the final SELECT/GROUP BY to match.
--
-- SCOPE CHANGE worth knowing before you deploy (not a bug): since draftingeligiblerpids_vw
-- (file 004) now includes US Capturable/DEXA Capturable codes alongside the XR/CT drafting
-- models, this view will start surfacing Capture-eligible-but-not-captured exams too, not
-- just drafting gaps - confirmed live, rows with drafting_model = 'US Capturable' /
-- 'DEXA Capturable' now appear in the query output that didn't exist under the old
-- CASE-based classification (which only ever produced XR/MSK or a CT Head/Chest/Spine/Abd-Pel
-- value).
--
-- Re-ran this file's full WITH...SELECT body (with the npi fix, LIMIT 5) against current EDW
-- and it executes clean, output shape now matches the live view's shape exactly. Safe to
-- deploy now.
--
-- STATUS (2026-09-30): user deployed this logic to a NEW, separate object -
-- edw_prod.bipa_analytics.examsnotdraftedbutdraftableNEW_vw (different catalog AND name from
-- this file's own edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw target) - as a
-- validation copy, not a replacement. Verified live: column shape matches exactly (12
-- columns), and all 7 drafting_model values appear with real volume including US Capturable
-- (1.26M exams) / DEXA Capturable (159K exams), confirming it's reading the corrected
-- crosswalk classification, not the old CASE logic. The app (mosaic_service.py's
-- get_undrafted_analysis()) still queries the original edw_dev location - user explicitly
-- said leave that as-is for now, this NEW object is validation only. Don't assume a
-- production cutover has happened; check with the user before repointing the app.
--
-- UPDATE (2026-10-13): this file's own drafting_codes swap (described in the header above) was
-- still sitting on edw_prod.bipa_analytics.draftingeligiblerpids_vw - re-pointed to the newer
-- edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw instead (the same data, just the
-- object that got the "_" naming cleanup on 2026-10-06; confirmed byte-identical drafting_model
-- distribution between the two live before making this change). Column name there is
-- `rpid_procedure_code`, not `` `Procedure Code` `` - updated accordingly, no more backticked
-- space needed.
--
-- Also added a wave of new CT Chest practices that went live today (list supplied by the
-- user) to the CT Chest PRACTICE-enablement allowlist in `categorized` - one name
-- (`RP Bluegrass`) had a trailing space in the supplied list, trimmed since it's a SQL string
-- literal exact-match, not a pattern match. Checked for overlap with the existing CT Chest
-- list first - no duplicates.
--
-- Still not deployed to the real edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw target -
-- same read-only-tool constraint as before, and the app still queries that same live location,
-- so this still needs a human to run it.

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

-- Only used now for the three consent values still treated as reliable exclusions.
-- 'TERM' replaces 'DISABLED' here - see file header, item 3.
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
    v.Team, v.local_practice_short_name AS local_practice, v.Location_Name AS site, v.Radiologist, v.npi,
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
    -- Drop rads flagged 'Do Not Launch' or 'Do Not Revisit' from the whole analysis.
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
          'MIA','RP NWIR','RP Houston','RP Singleton','RP Gulf Coast',
          -- New CT Chest go-live wave, added 2026-10-13
          'RP West Texas','Spec Ops Reserve','Community','Lakefront Imaging','RP Palm Beach',
          'Western Colorado','MXC','RP Tucson','Access Alexandria','Access Lake Charles','ARSC',
          'ARA','Alaska','CIR','CIRPA','Coastal','GIMA','GLI','IAM','IAMSE Hurley','Mountain','PRA',
          'RAC','RACSW','RAI','RedRock','RP Bluegrass','RP Borderlands','RP Brazosport','RP Cascade',
          'RP Corpus Christi','RP Chicago','RP Dallas','RP Eagle','RP East Florida','RP North Florida',
          'RP El Paso','RP Florida West','RP Kentucky','RP SoCal','RP Sol','RP South Carolina',
          'Saline Valley','SOAR','SVDI','RP Helios')
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
