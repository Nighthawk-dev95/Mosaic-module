-- 041: source for the exec dashboard's "Time Series" section (PBI Mosaic Efficiency page "Time Series": monthly
-- pivot Team Rolled Up -> Radiologist -> Parent Exam, measures Mosaic Mode[Mean Work Units per Minmode (With Vol)]
-- and Mosaic Mode[VolumeMode], visual filter has volumemode = 1).
-- Unlike the other Efficiency pages, these measures filter on Period_Type, not on the Is_*_Row flags:
--   b  Legacy (Baseline)  : Period_Type = 'Baseline'
--   f  Full Mosaic        : Period_Type IN ('Drafting', 'Reporting')
--   r  Reporting Only     : Period_Type = 'Reporting'
--   d  Drafting Only      : Period_Type = 'Drafting' (ALL modalities; no CR/CT restriction on this page)
--   c  Capture Only       : Period_Type = 'Drafting' AND Modality US/BD
-- Platform 'Both' = Baseline + selected mode (DAX BLANK + x = x). Outlier View default 'Excluded'.
-- Grain: Team Rolled Up x Radiologist (radiologist_summary, via Physician_NPI) x Parent Exam x Managing Practice
--   (radiologist_metrics.Practice) x Local (PBI radiologist_metrics[Local] SWITCH on the fact Team) x Beginning_of_Month
--   (PBI calculated column = first day of Exam_Date's month).
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_timeseries_month_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_optimized (PBI Mosaic Efficiency fact), Outliers=Excluded, pre-summed to Team Rolled Up x Radiologist x Parent Exam x Managing Practice x Local x Beginning_of_Month by Period_Type bucket (_b Baseline, _f Drafting+Reporting, _r Reporting, _d Drafting all modalities, _c Drafting US/BD). Feeds the exec dashboard Time Series pivot (PBI Mean Work Units per Minmode / VolumeMode).'
SCHEDULE CRON '0 40 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
WITH dim AS (
  SELECT d.Physician_NPI,
    CASE WHEN LENGTH(d.Radiologist) > 10 AND RIGHT(d.Radiologist, 10) RLIKE '^[0-9]{10}$'
         THEN TRIM(LEFT(d.Radiologist, LENGTH(d.Radiologist) - 10)) ELSE d.Radiologist END AS radiologist,
    COALESCE(tr.`Team Roll Up (KS)`, CASE WHEN d.Team = 'Access Slidell' THEN 'Access Alexandria' ELSE d.Team END) AS team_rolled_up
  FROM edw_dev.bipa_analytics.dim_radiologist_optimized d
  LEFT JOIN edw_dev.bipa_analytics.team_rollups tr ON tr.Team = d.Team
),
src AS (
  SELECT Physician_NPI, Parent_Procedure_name, Practice, DATE_TRUNC('MONTH', Exam_Date) AS month_start,
    ExamCount, TotalTime, TotalTBWU,
    CASE
      WHEN Team IN ('ESR', 'LFI', 'Jefferson', 'GLI', 'RAI', 'RP Cascade', 'RP Crossroads', 'JR', 'DRSRP', 'RP East Florida',
        'RP North Florida', 'RP Palm Beach', 'RP Florida West', 'PRA', 'ESRMH Garnet', 'ESRMH Hackensack', 'ESRMH Legacy',
        'ESR Long Island', 'ESR Metro Hudson', 'SEAL Team', 'SEAL Legacy', 'vRad', 'Spec Ops Reserve') THEN 'Special Operations'
      WHEN Team IN ('ADI', 'ADR', 'CRC Central', 'CRC NW', 'CRC SW', 'Midstate', 'NEOH', 'Rad Alliance', 'RP Kentucky',
        'RP Bluegrass', 'RAC', 'RACSW', 'RPKY', 'RPBG', 'RA', 'ADR Legacy', 'CRC', 'Rad Alliance Legacy',
        'Rad Alliance NorthCrest', 'RP Bluegrass Legacy') THEN 'Apex'
      WHEN Team IN ('Coastal', 'Greensboro', 'MBB', 'Northside', 'Greensboro Canopy', 'RAF', 'RP Florida', 'RP Sandhills',
        'RP South Carolina', 'SOAR', 'BOCA', 'GR', 'NRA', 'RASF', 'MBB Legacy', 'MBB Phoebe Putney', 'Northside Radiology',
        'RAF East Coast', 'RAF Panhandle', 'RAF Sarasota', 'RAF Tampa', 'RAF Tele', 'RASF Miami', 'RASF Naples',
        'RP Florida Legacy', 'RP Florida West') THEN 'Genesis'
      WHEN Team IN ('Advanced Radiology', 'Alaska', 'CIR', 'Desert', 'GIMA', 'RP SoCal', 'IAM', 'IAMSE', 'MIA', 'Mountain', 'NIR',
        'RAA', 'MXC', 'Red Rock', 'RIMA', 'RP Sol', 'RP Sun City', 'RP Chicago', 'RP Forest City', 'Saline Valley',
        'RP Valley Radiologists', 'SVDI', 'Western Colorado', 'WIR', 'RP IOWA', 'GSIA', 'SVL', 'MR', 'DR', 'NWIR', 'ARSC',
        'DR Legacy', 'DR DRS', 'IAMSE Hurley', 'IAM Marquette', 'IAM Midlands', 'Lakefront Imaging', 'Mountain Legacy',
        'Mountain Yampa', 'RP NWIR', 'RP SMIL', 'RP SoCal Lakewood', 'RP SoCal Legacy', 'RP SoCal Palmdale', 'RP Valley',
        'SVDI Legacy', 'SVDI San Ramon', 'SMI', 'RIMA California') THEN 'Maverick'
      WHEN Team IN ('Access Alexandria', 'ARA', 'BR Academic', 'BR Community', 'CIRPA', 'Community', 'RP Eagle', 'EBI', 'GIA',
        'Lake Charles', 'RP Borderlands', 'RP Brazosport', 'RP Corpus Christi', 'RP Dallas', 'RP El Paso', 'RP Gulf Coast',
        'RP Houston', 'RP Laredo', 'RP Victoria', 'BR', 'Slidell', 'ACC', 'RPNM', 'EAG', 'RPEP', 'RPGC', 'RPH', 'Other',
        'EXTHMC', 'RP Singleton Academic', 'RP Singleton Community', 'RP Singleton', 'Rose', 'RP North Houston', 'Synergy',
        'Access Lake Charles', 'Community Laredo', 'Community Legacy', 'Community Victoria', 'Elite', 'RP Borderlands Legacy',
        'RP Borderlands Lovelace', 'RP Helios') THEN 'Trailblazer'
      ELSE 'Matrix'
    END AS local_region,
    Period_Type = 'Baseline' AS is_b, Period_Type IN ('Drafting', 'Reporting') AS is_f,
    Period_Type = 'Reporting' AS is_r, Period_Type = 'Drafting' AS is_d,
    Period_Type = 'Drafting' AND Modality_Code IN ('US', 'BD') AS is_c
  FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
  WHERE Outliers = 'Excluded' AND Period_Type IN ('Baseline', 'Drafting', 'Reporting')
)
SELECT dim.team_rolled_up, dim.radiologist, s.Parent_Procedure_name AS parent_exam, s.Practice AS managing_practice,
  s.local_region, CAST(s.month_start AS DATE) AS month_start,
  SUM(CASE WHEN is_b THEN ExamCount END) AS x_b,
  SUM(CASE WHEN is_b THEN TotalTime END) AS t_b,
  SUM(CASE WHEN is_b THEN TotalTBWU END) AS w_b,
  SUM(CASE WHEN is_f THEN ExamCount END) AS x_f,
  SUM(CASE WHEN is_f THEN TotalTime END) AS t_f,
  SUM(CASE WHEN is_f THEN TotalTBWU END) AS w_f,
  SUM(CASE WHEN is_r THEN ExamCount END) AS x_r,
  SUM(CASE WHEN is_r THEN TotalTime END) AS t_r,
  SUM(CASE WHEN is_r THEN TotalTBWU END) AS w_r,
  SUM(CASE WHEN is_d THEN ExamCount END) AS x_d,
  SUM(CASE WHEN is_d THEN TotalTime END) AS t_d,
  SUM(CASE WHEN is_d THEN TotalTBWU END) AS w_d,
  SUM(CASE WHEN is_c THEN ExamCount END) AS x_c,
  SUM(CASE WHEN is_c THEN TotalTime END) AS t_c,
  SUM(CASE WHEN is_c THEN TotalTBWU END) AS w_c
FROM src s
LEFT JOIN dim ON dim.Physician_NPI = s.Physician_NPI
GROUP BY ALL
