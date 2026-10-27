-- 037: daily snapshot of the PBI Efficiency model's fact (radiologist_metrics_optimized), for the exec
-- dashboard's "By Provider Practice" table -- the numbers used in the monthly CEO send-outs.
--
-- Why a snapshot: edw_dev.bipa_analytics.radiologist_metrics_optimized recomputes outlier windows over
-- full history on every read (~1 min even for a bare COUNT). PBI imports it once a day; this MV does the same.
-- Logic is NOT changed here. This MV only pre-sums rmo rows (Outliers = 'Excluded') to the leaf x day grain
-- PBI's visual works on: Team Rolled Up x Radiologist x Parent Exam x Exam_Date. SUM is null-preserving
-- (a leaf whose TotalTBWU is all-null stays NULL), which the visual filter depends on.
--   * team_rolled_up : PBI dim_radiologist_optimized.Team via team_rollups[Team Roll Up (KS)], with PBI's
--                      Access Slidell -> Access Alexandria fallback (= PBI 'Team Rolled up' = Provider Practice).
--   * radiologist    : PBI's display name (trailing 10-digit NPI stripped).
--   * *_f = Full Mosaic (Is_Mosaic_Row), *_d = Drafting Only (Is_Drafting_Row AND Modality CR/CT).
--   * bx_f / bx_d    = baseline exam counts (Is_Baseline_Row; Drafting side CR/CT only). PBI uses these with
--                      NO date filter, so the dashboard query sums them across all dates.
-- The visual-level filter logic (Hasbothmetricseff_Opt / RTFILTERFLAG_Opt) lives in the dashboard dataset
-- (tools/lakeview_exec_dashboard/provider_practice_efficiency.sql), because it depends on the selected window.
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_eff_provider_leaf_daily_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.radiologist_metrics_optimized (PBI Mosaic Efficiency fact), Outliers=Excluded, pre-summed to Team Rolled Up x Radiologist x Parent Exam x Exam_Date for Full Mosaic (_f) and Drafting Only CR/CT (_d). Feeds the exec dashboard By Provider Practice table.'
SCHEDULE CRON '0 15 7 * * ?' AT TIME ZONE 'America/Chicago'
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
    Modality_Code IN ('CR', 'CT') AS crct, Is_Mosaic_Row = 1 AS is_m, Is_Drafting_Row = 1 AS is_d, Is_Baseline_Row = 1 AS is_b
  FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
  WHERE Outliers = 'Excluded' AND (Is_Mosaic_Row = 1 OR Is_Drafting_Row = 1 OR Is_Baseline_Row = 1)
)
SELECT dim.team_rolled_up, dim.radiologist, s.Parent_Procedure_name AS parent_exam, s.Exam_Date AS exam_date,
  SUM(CASE WHEN is_m THEN ExamCount END) AS x_f,
  SUM(CASE WHEN is_m THEN TotalTime END) AS t_f,
  SUM(CASE WHEN is_m THEN TotalTBWU END) AS w_f,
  SUM(CASE WHEN is_m THEN Weighted_Baseline_Contrib_Excl END) AS c_f,
  SUM(CASE WHEN is_b THEN ExamCount END) AS bx_f,
  SUM(CASE WHEN is_d AND crct THEN ExamCount END) AS x_d,
  SUM(CASE WHEN is_d AND crct THEN TotalTime END) AS t_d,
  SUM(CASE WHEN is_d AND crct THEN TotalTBWU END) AS w_d,
  SUM(CASE WHEN is_d AND crct THEN Weighted_Baseline_Contrib_Excl END) AS c_d,
  SUM(CASE WHEN is_b AND crct THEN ExamCount END) AS bx_d
FROM src s
LEFT JOIN dim ON dim.Physician_NPI = s.Physician_NPI
GROUP BY ALL
