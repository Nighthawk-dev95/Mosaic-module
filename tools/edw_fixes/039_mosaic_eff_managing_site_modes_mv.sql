-- 039: companion to 038 for the exec dashboard's "By Managing Practice" table (PBI Mosaic Efficiency page of the
-- same name). Grain: Managing Practice (radiologist_metrics.Practice, tied to the exam site) x Site (Location_Name)
-- x Exam_Date over edw_dev.bipa_analytics.radiologist_metrics_optimized, Outliers = 'Excluded'.
-- Mode row filters are the same as 038 (_f Full, _r Reporting, _d Drafting CR/CT, _c Capture US/BD, _dc Drafting+Capture).
-- PBI's Managing Practice visual also counts exams through radiologist_summary, so two name-matched variants are kept:
--   xn_*  ExamCount where the row's Radiologist is one of radiologist_summary's names (NPI-suffix-stripped
--         dim_radiologist_optimized names). Summed over all dates = "Mosaic Exams (STE)"; in-period = "Mosaic Exams".
--   bx_*  Is_Baseline_Row ExamCount (mode modalities) where the row's NPI maps, in the dim, to the row's own Radiologist
--         name (PBI filters baseline exams through both radiologist_summary[Physician_NPI] and [Radiologist]).
-- Proven on PBI-extracted site sums, Aug 2026, all 5 modes: every total, practice and site row identical.
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_managing_site_modes_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_optimized (PBI Mosaic Efficiency fact), Outliers=Excluded, pre-summed to Managing Practice x Site (Location_Name) x Exam_Date for every PBI Mosaic Mode (_f Full, _r Reporting, _d Drafting CR/CT, _c Capture US/BD, _dc Drafting+Capture). xn_* = exams by radiologists present in radiologist_summary, bx_* = baseline exams whose NPI maps to the same radiologist name. Feeds the exec dashboard By Managing Practice table.'
SCHEDULE CRON '0 25 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
WITH dim AS (
  SELECT DISTINCT d.Physician_NPI,
    CASE WHEN LENGTH(d.Radiologist) > 10 AND RIGHT(d.Radiologist, 10) RLIKE '^[0-9]{10}$'
         THEN TRIM(LEFT(d.Radiologist, LENGTH(d.Radiologist) - 10)) ELSE d.Radiologist END AS radiologist
  FROM edw_dev.bipa_analytics.dim_radiologist_optimized d
),
names AS (
  SELECT DISTINCT radiologist FROM dim
),
src AS (
  SELECT m.Practice, m.Location_Name, m.Exam_Date, m.ExamCount, m.TotalTime, m.TotalTBWU, m.Weighted_Baseline_Contrib_Excl,
    m.Modality_Code IN ('CR', 'CT') AS crct, m.Modality_Code IN ('US', 'BD') AS usbd,
    m.Is_Mosaic_Row = 1 AS is_m, m.Is_Reporting_Row = 1 AS is_r, m.Is_Drafting_Row = 1 AS is_d,
    m.Is_Capture_Row = 1 AS is_c, m.Is_Baseline_Row = 1 AS is_b,
    n.radiologist IS NOT NULL AS in_sum,
    ok.radiologist IS NOT NULL AS npi_ok
  FROM edw_dev.bipa_analytics.radiologist_metrics_optimized m
  LEFT JOIN names n ON n.radiologist = m.Radiologist
  LEFT JOIN dim ok ON ok.Physician_NPI = m.Physician_NPI AND ok.radiologist = m.Radiologist
  WHERE m.Outliers = 'Excluded'
    AND (m.Is_Mosaic_Row = 1 OR m.Is_Reporting_Row = 1 OR m.Is_Drafting_Row = 1 OR m.Is_Capture_Row = 1 OR m.Is_Baseline_Row = 1)
),
flagged AS (
  SELECT *, (is_d AND crct) AS is_dd, (is_c AND usbd) AS is_cc, ((is_d AND crct) OR (is_c AND usbd)) AS is_dc
  FROM src
)
SELECT Practice AS managing_practice, Location_Name AS site, Exam_Date AS exam_date,
  SUM(CASE WHEN is_m THEN ExamCount END) AS x_f,
  SUM(CASE WHEN is_m THEN TotalTime END) AS t_f,
  SUM(CASE WHEN is_m THEN TotalTBWU END) AS w_f,
  SUM(CASE WHEN is_m THEN Weighted_Baseline_Contrib_Excl END) AS c_f,
  SUM(CASE WHEN is_m AND in_sum THEN ExamCount END) AS xn_f,
  SUM(CASE WHEN is_r THEN ExamCount END) AS x_r,
  SUM(CASE WHEN is_r THEN TotalTime END) AS t_r,
  SUM(CASE WHEN is_r THEN TotalTBWU END) AS w_r,
  SUM(CASE WHEN is_r THEN Weighted_Baseline_Contrib_Excl END) AS c_r,
  SUM(CASE WHEN is_r AND in_sum THEN ExamCount END) AS xn_r,
  SUM(CASE WHEN is_dd THEN ExamCount END) AS x_d,
  SUM(CASE WHEN is_dd THEN TotalTime END) AS t_d,
  SUM(CASE WHEN is_dd THEN TotalTBWU END) AS w_d,
  SUM(CASE WHEN is_dd THEN Weighted_Baseline_Contrib_Excl END) AS c_d,
  SUM(CASE WHEN is_dd AND in_sum THEN ExamCount END) AS xn_d,
  SUM(CASE WHEN is_cc THEN ExamCount END) AS x_c,
  SUM(CASE WHEN is_cc THEN TotalTime END) AS t_c,
  SUM(CASE WHEN is_cc THEN TotalTBWU END) AS w_c,
  SUM(CASE WHEN is_cc THEN Weighted_Baseline_Contrib_Excl END) AS c_c,
  SUM(CASE WHEN is_cc AND in_sum THEN ExamCount END) AS xn_c,
  SUM(CASE WHEN is_dc THEN ExamCount END) AS x_dc,
  SUM(CASE WHEN is_dc THEN TotalTime END) AS t_dc,
  SUM(CASE WHEN is_dc THEN TotalTBWU END) AS w_dc,
  SUM(CASE WHEN is_dc THEN Weighted_Baseline_Contrib_Excl END) AS c_dc,
  SUM(CASE WHEN is_dc AND in_sum THEN ExamCount END) AS xn_dc,
  SUM(CASE WHEN is_b AND npi_ok THEN ExamCount END) AS bx_all,
  SUM(CASE WHEN is_b AND npi_ok AND crct THEN ExamCount END) AS bx_crct,
  SUM(CASE WHEN is_b AND npi_ok AND usbd THEN ExamCount END) AS bx_usbd,
  SUM(CASE WHEN is_b AND npi_ok AND (crct OR usbd) THEN ExamCount END) AS bx_dc
FROM flagged
GROUP BY ALL
