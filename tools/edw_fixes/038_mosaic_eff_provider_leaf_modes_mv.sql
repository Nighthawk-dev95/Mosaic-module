-- 038: all-modes version of 037, for the exec dashboard's "By Provider Practice" Mode selector.
-- Same grain and source as 037 (Team Rolled Up x Radiologist x Parent Exam x Exam_Date over
-- edw_dev.bipa_analytics.radiologist_metrics_optimized, Outliers = 'Excluded'). 037 only carried Full Mosaic and
-- Drafting Only; this new object carries every PBI 'Mosaic Mode Selector' mode (037 is left untouched).
-- Mode row filters are copied from PBI's *_Opt measures:
--   *_f  Full Mosaic        : Is_Mosaic_Row
--   *_r  Reporting Only     : Is_Reporting_Row
--   *_d  Drafting Only      : Is_Drafting_Row AND Modality CR/CT
--   *_c  Capture Only       : Is_Capture_Row AND Modality US/BD
--   *_dc Drafting + Capture : (Is_Drafting_Row AND CR/CT) OR (Is_Capture_Row AND US/BD)
--   ('Both' is not handled by any PBI SWITCH, so it falls through to Full Mosaic.)
-- Baseline exam counts (baselineexams_opt, Is_Baseline_Row, no date filter): bx_all (Full, Reporting),
-- bx_crct (Drafting), bx_usbd (Capture), bx_dc (Drafting + Capture).
-- be_proc / be_usbd = Baseline_Eff_Proc_Excl / Baseline_USBD_Eff_Proc_Excl. PBI shows MAX() of these on parent exam
-- rows (Base_Baseline_Eff_Opt). Verified constant per NPI x Parent Exam and identical with or without the outlier
-- filter (434,008 leaves, 0 differences), so a MAX over these rows equals PBI's unfiltered MAX.
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_provider_leaf_modes_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_optimized (PBI Mosaic Efficiency fact), Outliers=Excluded, pre-summed to Team Rolled Up x Radiologist x Parent Exam x Exam_Date for every PBI Mosaic Mode (_f Full, _r Reporting, _d Drafting CR/CT, _c Capture US/BD, _dc Drafting+Capture) plus parent-exam baselines. Feeds the exec dashboard By Provider Practice table.'
SCHEDULE CRON '0 20 7 * * ?' AT TIME ZONE 'America/Chicago'
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
  SELECT Physician_NPI, Parent_Procedure_name, Exam_Date, ExamCount, TotalTime, TotalTBWU, Weighted_Baseline_Contrib_Excl,
    Baseline_Eff_Proc_Excl, Baseline_USBD_Eff_Proc_Excl,
    Modality_Code IN ('CR', 'CT') AS crct, Modality_Code IN ('US', 'BD') AS usbd,
    Is_Mosaic_Row = 1 AS is_m, Is_Reporting_Row = 1 AS is_r, Is_Drafting_Row = 1 AS is_d,
    Is_Capture_Row = 1 AS is_c, Is_Baseline_Row = 1 AS is_b
  FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
  WHERE Outliers = 'Excluded'
    AND (Is_Mosaic_Row = 1 OR Is_Reporting_Row = 1 OR Is_Drafting_Row = 1 OR Is_Capture_Row = 1 OR Is_Baseline_Row = 1)
),
flagged AS (
  SELECT *, (is_d AND crct) AS is_dd, (is_c AND usbd) AS is_cc, ((is_d AND crct) OR (is_c AND usbd)) AS is_dc
  FROM src
)
SELECT dim.team_rolled_up, dim.radiologist, s.Parent_Procedure_name AS parent_exam, s.Exam_Date AS exam_date,
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
  SUM(CASE WHEN is_dc THEN Weighted_Baseline_Contrib_Excl END) AS c_dc,
  SUM(CASE WHEN is_b THEN ExamCount END) AS bx_all,
  SUM(CASE WHEN is_b AND crct THEN ExamCount END) AS bx_crct,
  SUM(CASE WHEN is_b AND usbd THEN ExamCount END) AS bx_usbd,
  SUM(CASE WHEN is_b AND (crct OR usbd) THEN ExamCount END) AS bx_dc,
  MAX(Baseline_Eff_Proc_Excl) AS be_proc,
  MAX(Baseline_USBD_Eff_Proc_Excl) AS be_usbd
FROM flagged s
LEFT JOIN dim ON dim.Physician_NPI = s.Physician_NPI
GROUP BY ALL
