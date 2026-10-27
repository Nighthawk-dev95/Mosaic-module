-- 042: fact source for the exec dashboard's "Mosaic Efficiency vs Average" section (PBI Mosaic Efficiency page
-- "Mosaic Efficiency vs Average": pivot Team Rolled Up -> Radiologist -> Parent Exam with Rad_Subspecialty_NB,
-- Mosaic_Exams_AllTime_NB, Mosaic_Exams_Period_NB, Mosaic_Efficiency_NB, Mosaic_Efficiency_vs_RP_Avg_Overall,
-- Mosaic_Efficiency_vs_RP_Avg_NB, plus Radiologist_Count_NB and the Benchmark_<mode> cards).
-- PBI fact = radiologist_metrics(1) = edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow, joined to
-- radiologist_summary(1) (043 mosaic_eff_vs_avg_rad_dim_mv) on Physician_NPI. Visual/page filters: Outlier View
-- 'Excluded', Interventional_Flag = 0. Buckets (all NB measures filter on Period_Type + Modality_Code):
--   d  Drafting CR/CT          : Period_Type = 'Drafting' AND Modality CR/CT
--   c  Drafting US/BD          : Period_Type = 'Drafting' AND Modality US/BD
--   a  Drafting all modalities : Period_Type = 'Drafting'
--   r  Reporting               : Period_Type = 'Reporting'
--   b  Baseline                : Period_Type = 'Baseline'
-- Kept at day grain because the page's Mosaic_Calendar slicer is an arbitrary date range and the min-exams test
-- is evaluated over that range. SUM(CASE ...) keeps NULL where a bucket has no rows (PBI BLANK).
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_vs_avg_daily_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow (PBI Mosaic Efficiency radiologist_metrics(1)), Outliers=Excluded, Interventional_Flag=0, pre-summed to Team Rolled Up x Physician_NPI x Radiologist x Parent Exam x Exam_Date by bucket (_d Drafting CR/CT, _c Drafting US/BD, _a Drafting all, _r Reporting, _b Baseline). Team/Radiologist come from mosaic_eff_vs_avg_rad_dim_mv. Feeds the exec dashboard Mosaic Efficiency vs Average page.'
SCHEDULE CRON '0 50 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
WITH src AS (
  SELECT Physician_NPI, Parent_Procedure_name, Exam_Date, ExamCount, TotalTime, TotalTBWU,
    Period_Type = 'Drafting' AND Modality_Code IN ('CR', 'CT') AS is_d,
    Period_Type = 'Drafting' AND Modality_Code IN ('US', 'BD') AS is_c,
    Period_Type = 'Drafting' AS is_a,
    Period_Type = 'Reporting' AS is_r,
    Period_Type = 'Baseline' AS is_b
  FROM edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow
  WHERE Outliers = 'Excluded' AND Interventional_Flag = 0 AND Period_Type IN ('Baseline', 'Drafting', 'Reporting')
)
SELECT dim.team_rolled_up, s.Physician_NPI AS physician_npi, dim.radiologist, s.Parent_Procedure_name AS parent_exam,
  s.Exam_Date AS exam_date,
  SUM(CASE WHEN is_d THEN ExamCount END) AS x_d,
  SUM(CASE WHEN is_d THEN TotalTime END) AS t_d,
  SUM(CASE WHEN is_d THEN TotalTBWU END) AS w_d,
  SUM(CASE WHEN is_c THEN ExamCount END) AS x_c,
  SUM(CASE WHEN is_c THEN TotalTime END) AS t_c,
  SUM(CASE WHEN is_c THEN TotalTBWU END) AS w_c,
  SUM(CASE WHEN is_a THEN ExamCount END) AS x_a,
  SUM(CASE WHEN is_a THEN TotalTime END) AS t_a,
  SUM(CASE WHEN is_a THEN TotalTBWU END) AS w_a,
  SUM(CASE WHEN is_r THEN ExamCount END) AS x_r,
  SUM(CASE WHEN is_r THEN TotalTime END) AS t_r,
  SUM(CASE WHEN is_r THEN TotalTBWU END) AS w_r,
  SUM(CASE WHEN is_b THEN ExamCount END) AS x_b,
  SUM(CASE WHEN is_b THEN TotalTime END) AS t_b,
  SUM(CASE WHEN is_b THEN TotalTBWU END) AS w_b
FROM src s
LEFT JOIN edw_test.enterprise_analytics.mosaic_eff_vs_avg_rad_dim_mv dim ON dim.Physician_NPI = s.Physician_NPI
GROUP BY ALL
