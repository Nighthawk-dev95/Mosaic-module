-- Mosaic Efficiency "vs RP Average" semantic (Readtimeview.tmdl). edw_test ONLY. Governed,
-- per-row view over the no-baseline-restriction shadow tables (see 024), exposing both each
-- row's own mode-scoped all-time exam count (for the min_exams qualification gate) AND a
-- GLOBAL, population-wide RP Avg TBWU/min per mode, precomputed via an unpartitioned window
-- function (Fixed LOD pattern - create-patterns.md Pattern 10) so it stays constant no matter
-- what grain a query later groups by (NPI, Team, or nothing).
--
-- 6 modes, matching the main Efficiency semantic's vocabulary (tbl_efficiency_exam_level_vw):
-- Reporting, Drafting (CR/CT), Capture (US/BD), Drafting+Capture, Full Mosaic, Both.
-- NOTE on a DAX inconsistency found live: Mosaic_Efficiency_Raw_NB (the individual radiologist's
-- own number) does NOT modality-restrict "Drafting Only", while every Benchmark_*_Overall measure
-- (the population side) DOES restrict to CR/CT. Comparing an all-modality individual number
-- against a CR/CT-only population average would be apples-to-oranges. Deliberately fixed here:
-- BOTH sides of every ratio use the same modality restriction, consistent with the main
-- Efficiency semantic's convention.
--
-- RP Avg qualification threshold is hardcoded to >=1 exam ("show everyone" default, same as
-- min_exams default in mosaic_efficiency_metric_view) - a TRUE query-time parameter isn't
-- feasible here because the population average must be FIXED (unpartitioned window) at view-
-- definition time; only the metric view's own `min_exams` parameter (applied to the INDIVIDUAL
-- radiologist side of the ratio) can be dynamic. See MIGRATION_PLAYBOOK.md.

CREATE OR REPLACE VIEW edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw
COMMENT 'Mosaic Efficiency vs RP Average semantic: per-row exam-metric data (no baseline restriction - broader population than tbl_efficiency_exam_level_vw) plus a precomputed, grain-independent company-wide RP Avg TBWU/min per mode. Source for mosaic_efficiency_vs_rp_avg_metric_view. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
AS
WITH base AS (
  SELECT
    m.Physician_NPI AS npi,
    m.Radiologist AS radiologist_name,
    m.Team AS team,
    m.Practice AS practice,
    m.working_subspecialty AS subspecialty,
    m.Modality_Code AS modality_code,
    m.Parent_Procedure_name AS parent_procedure_name,
    m.mpcat AS exam_category,
    m.Exam_Date AS exam_date,
    m.Period_Type AS period_type,
    m.Outliers AS outliers,
    m.TotalTBWU AS tbwu,
    m.TotalTime AS time_sec,
    m.ExamCount AS exam_count,
    m.Rad_Total_Drafting_ExclOutliers AS rad_total_drafting_all_excl,
    m.Rad_Total_Reporting_ExclOutliers AS rad_total_reporting_all_excl,
    m.Rad_Total_FullMosaic_ExclOutliers AS rad_total_full_mosaic_all_excl
  FROM edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow m
),
with_rad_totals AS (
  SELECT *,
    SUM(CASE WHEN period_type = 'Drafting' AND outliers = 'Excluded' AND modality_code IN ('CR', 'CT') THEN exam_count ELSE 0 END)
      OVER (PARTITION BY npi) AS rad_total_drafting_cr_ct_all_excl,
    SUM(CASE WHEN period_type = 'Drafting' AND outliers = 'Excluded' AND modality_code IN ('US', 'BD') THEN exam_count ELSE 0 END)
      OVER (PARTITION BY npi) AS rad_total_capture_all_excl,
    SUM(CASE WHEN period_type = 'Drafting' AND outliers = 'Excluded' AND modality_code IN ('CR', 'CT', 'US', 'BD') THEN exam_count ELSE 0 END)
      OVER (PARTITION BY npi) AS rad_total_drafting_capture_all_excl,
    SUM(CASE WHEN period_type IN ('Reporting', 'Drafting', 'Baseline') AND outliers = 'Excluded' THEN exam_count ELSE 0 END)
      OVER (PARTITION BY npi) AS rad_total_both_all_excl
  FROM base
)
SELECT
  w.npi, w.radiologist_name, w.team,
  tr.Team_Roll_Up AS team_rolled_up,
  CASE
    WHEN w.team IN (
      'ESR','LFI','Jefferson','GLI','RAI','RP Cascade','RP Crossroads','JR','DRSRP',
      'RP East Florida','RP North Florida','RP Palm Beach','RP Florida West','PRA',
      'ESRMH Garnet','ESRMH Hackensack','ESRMH Legacy','ESR Long Island','ESR Metro Hudson',
      'SEAL Team','SEAL Legacy','vRad','Spec Ops Reserve'
    ) THEN 'Special Operations'
    WHEN w.team IN (
      'ADI','ADR','CRC Central','CRC NW','CRC SW','Midstate','NEOH','Rad Alliance',
      'RP Kentucky','RP Bluegrass','RAC','RACSW','RPKY','RPBG','RA','ADR Legacy','CRC',
      'Rad Alliance Legacy','Rad Alliance NorthCrest','RP Bluegrass Legacy'
    ) THEN 'Apex'
    WHEN w.team IN (
      'Coastal','Greensboro','MBB','Northside','Greensboro Canopy','RAF','RP Florida',
      'RP Sandhills','RP South Carolina','SOAR','BOCA','GR','NRA','RASF','MBB Legacy',
      'MBB Phoebe Putney','Northside Radiology','RAF East Coast','RAF Panhandle',
      'RAF Sarasota','RAF Tampa','RAF Tele','RASF Miami','RASF Naples','RP Florida Legacy'
    ) THEN 'Genesis'
    WHEN w.team IN (
      'Advanced Radiology','Alaska','CIR','Desert','GIMA','RP SoCal','IAM','IAMSE','MIA',
      'Mountain','NIR','RAA','MXC','Red Rock','RIMA','RP Sol','RP Sun City','RP Chicago',
      'RP Forest City','Saline Valley','RP Valley Radiologists','SVDI','Western Colorado',
      'WIR','RP IOWA','GSIA','SVL','MR','DR','NWIR','ARSC','DR Legacy','DR DRS',
      'IAMSE Hurley','IAM Marquette','IAM Midlands','Lakefront Imaging','Mountain Legacy',
      'Mountain Yampa','RP NWIR','RP SMIL','RP SoCal Lakewood','RP SoCal Legacy',
      'RP SoCal Palmdale','RP Valley','SVDI Legacy','SVDI San Ramon','SMI','RIMA California'
    ) THEN 'Maverick'
    WHEN w.team IN (
      'Access Alexandria','ARA','BR Academic','BR Community','CIRPA','Community','RP Eagle',
      'EBI','GIA','Lake Charles','RP Borderlands','RP Brazosport','RP Corpus Christi',
      'RP Dallas','RP El Paso','RP Gulf Coast','RP Houston','RP Laredo','RP Victoria','BR',
      'Slidell','ACC','RPNM','EAG','RPEP','RPGC','RPH','Other','EXTHMC',
      'RP Singleton Academic','RP Singleton Community','RP Singleton','Rose',
      'RP North Houston','Synergy','Access Lake Charles','Community Laredo',
      'Community Legacy','Community Victoria','Elite','RP Borderlands Legacy',
      'RP Borderlands Lovelace','RP Helios'
    ) THEN 'Trailblazer'
    ELSE 'Matrix'
  END AS local_region,
  w.practice, w.subspecialty, w.modality_code, w.parent_procedure_name, w.exam_category,
  w.exam_date, w.period_type, w.outliers, w.tbwu, w.time_sec, w.exam_count,
  w.rad_total_reporting_all_excl, w.rad_total_drafting_cr_ct_all_excl, w.rad_total_capture_all_excl,
  w.rad_total_drafting_capture_all_excl, w.rad_total_full_mosaic_all_excl, w.rad_total_both_all_excl,
  -- Fixed-LOD RP Avg building blocks (unpartitioned window = one constant value for the whole
  -- view, regardless of query grouping), threshold >=1 exam, same modality scoping as the
  -- Benchmark_*_Overall DAX measures.
  SUM(CASE WHEN w.period_type = 'Reporting' AND w.outliers = 'Excluded' AND w.rad_total_reporting_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_reporting_tbwu,
  SUM(CASE WHEN w.period_type = 'Reporting' AND w.outliers = 'Excluded' AND w.rad_total_reporting_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_reporting_time,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('CR', 'CT') AND w.rad_total_drafting_cr_ct_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_drafting_tbwu,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('CR', 'CT') AND w.rad_total_drafting_cr_ct_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_drafting_time,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('US', 'BD') AND w.rad_total_capture_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_capture_tbwu,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('US', 'BD') AND w.rad_total_capture_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_capture_time,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('CR', 'CT', 'US', 'BD') AND w.rad_total_drafting_capture_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_drafting_capture_tbwu,
  SUM(CASE WHEN w.period_type = 'Drafting' AND w.outliers = 'Excluded' AND w.modality_code IN ('CR', 'CT', 'US', 'BD') AND w.rad_total_drafting_capture_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_drafting_capture_time,
  SUM(CASE WHEN w.period_type IN ('Reporting', 'Drafting') AND w.outliers = 'Excluded' AND w.rad_total_full_mosaic_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_full_mosaic_tbwu,
  SUM(CASE WHEN w.period_type IN ('Reporting', 'Drafting') AND w.outliers = 'Excluded' AND w.rad_total_full_mosaic_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_full_mosaic_time,
  SUM(CASE WHEN w.period_type IN ('Reporting', 'Drafting', 'Baseline') AND w.outliers = 'Excluded' AND w.rad_total_both_all_excl >= 1 THEN w.tbwu ELSE 0 END) OVER () AS rp_avg_both_tbwu,
  SUM(CASE WHEN w.period_type IN ('Reporting', 'Drafting', 'Baseline') AND w.outliers = 'Excluded' AND w.rad_total_both_all_excl >= 1 THEN w.time_sec ELSE 0 END) OVER () AS rp_avg_both_time
FROM with_rad_totals w
LEFT JOIN edw_test.enterprise_analytics.tbl_team_rollups tr ON tr.Team = w.team;
