-- 040: source for the exec dashboard's "Efficiency Change, Time Series" (PBI Mosaic Efficiency page of the same
-- name, measure Mode_Lines[Efficiency_Change_By_Mode_Line]). PBI gates radiologists on their ALL-TIME per-mode sums
-- keyed on the fact's Radiologist name, so this keeps that name at the grain:
--   Radiologist (fact name) x Team Rolled Up (radiologist_summary, via Physician_NPI) x Managing Practice
--   (radiologist_metrics.Practice) x Local (PBI calculated column radiologist_metrics[Local], a SWITCH on the
--   fact's Team, ported verbatim incl. its first-match order) x Exam_Date
-- over edw_dev.bipa_analytics.radiologist_metrics_optimized, Outliers = 'Excluded'.
-- Mode row filters are the same as 038/039 (_f Full, _r Reporting, _d Drafting CR/CT, _c Capture US/BD, _dc both).
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_optimized (PBI Mosaic Efficiency fact), Outliers=Excluded, pre-summed to Radiologist (fact name) x Team Rolled Up x Managing Practice x Local x Exam_Date for every PBI Mosaic Mode (_f Full, _r Reporting, _d Drafting CR/CT, _c Capture US/BD, _dc Drafting+Capture). Feeds the exec dashboard Efficiency Change time series (PBI all-time per-radiologist gate).'
SCHEDULE CRON '0 30 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
WITH dim AS (
  SELECT d.Physician_NPI,
    COALESCE(tr.`Team Roll Up (KS)`, CASE WHEN d.Team = 'Access Slidell' THEN 'Access Alexandria' ELSE d.Team END) AS team_rolled_up
  FROM edw_dev.bipa_analytics.dim_radiologist_optimized d
  LEFT JOIN edw_dev.bipa_analytics.team_rollups tr ON tr.Team = d.Team
),
src AS (
  SELECT Radiologist, Physician_NPI, Practice, Exam_Date, ExamCount, TotalTime, TotalTBWU, Weighted_Baseline_Contrib_Excl,
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
    Modality_Code IN ('CR', 'CT') AS crct, Modality_Code IN ('US', 'BD') AS usbd,
    Is_Mosaic_Row = 1 AS is_m, Is_Reporting_Row = 1 AS is_r, Is_Drafting_Row = 1 AS is_d, Is_Capture_Row = 1 AS is_c
  FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
  WHERE Outliers = 'Excluded'
    AND (Is_Mosaic_Row = 1 OR Is_Reporting_Row = 1 OR Is_Drafting_Row = 1 OR Is_Capture_Row = 1)
),
flagged AS (
  SELECT *, (is_d AND crct) AS is_dd, (is_c AND usbd) AS is_cc, ((is_d AND crct) OR (is_c AND usbd)) AS is_dc
  FROM src
)
SELECT s.Radiologist AS radiologist, dim.team_rolled_up, s.Practice AS managing_practice, s.local_region,
  s.Exam_Date AS exam_date,
  SUM(CASE WHEN is_m THEN ExamCount END) AS x_f,
  SUM(CASE WHEN is_m THEN TotalTime END) AS t_f,
  SUM(CASE WHEN is_m THEN TotalTBWU END) AS w_f,
  SUM(CASE WHEN is_m THEN Weighted_Baseline_Contrib_Excl END) AS c_f,
  SUM(CASE WHEN is_r THEN ExamCount END) AS x_r,
  SUM(CASE WHEN is_r THEN TotalTime END) AS t_r,
  SUM(CASE WHEN is_r THEN TotalTBWU END) AS w_r,
  SUM(CASE WHEN is_r THEN Weighted_Baseline_Contrib_Excl END) AS c_r,
  SUM(CASE WHEN is_dd THEN ExamCount END) AS x_d,
  SUM(CASE WHEN is_dd THEN TotalTime END) AS t_d,
  SUM(CASE WHEN is_dd THEN TotalTBWU END) AS w_d,
  SUM(CASE WHEN is_dd THEN Weighted_Baseline_Contrib_Excl END) AS c_d,
  SUM(CASE WHEN is_cc THEN ExamCount END) AS x_c,
  SUM(CASE WHEN is_cc THEN TotalTime END) AS t_c,
  SUM(CASE WHEN is_cc THEN TotalTBWU END) AS w_c,
  SUM(CASE WHEN is_cc THEN Weighted_Baseline_Contrib_Excl END) AS c_c,
  SUM(CASE WHEN is_dc THEN ExamCount END) AS x_dc,
  SUM(CASE WHEN is_dc THEN TotalTime END) AS t_dc,
  SUM(CASE WHEN is_dc THEN TotalTBWU END) AS w_dc,
  SUM(CASE WHEN is_dc THEN Weighted_Baseline_Contrib_Excl END) AS c_dc
FROM flagged s
LEFT JOIN dim ON dim.Physician_NPI = s.Physician_NPI
GROUP BY ALL
