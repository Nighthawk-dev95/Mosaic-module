-- Exact replication of the PBI Mosaic Efficiency page "9 Mosaic Efficiency, Time Series Viz" (Deneb line chart of
-- Mode_Lines_NB1[ModeLine] x [Benchmark_By_Mode_Line1] by YearMonth, tooltips Rad_Count_By_Month,
-- Exam_Count_By_Month, Exam_Count_Drafting / _Reporting / _Full_Mosaic). Page filters Interventional_Flag = 0 and
-- Outlier View = Excluded are already applied in the 042 source.
--   Qualification (_qualifiedRads): a radiologist NAME qualifies when its all-time Drafting + Reporting exams
--   (every modality, ignoring the month slicer) reach Min exams (PBI default 0 when unselected).
--   Drafting Only = Drafting on CR/CT; Non-Drafted = Reporting; Full Mosaic = Drafting + Reporting (all modalities),
--   each pooled over qualified radiologists in the month: 60 * SUM(TBWU) / SUM(time).
--   RP Avg lines use ALL(radiologist_summary): every radiologist in the month, no qualification, unaffected by
--   Provider Practice / Radiologist selections -> carried as company-wide monthly columns on every row.
--   They are shown only when the selected radiologists have rows in that bucket that month (_hasDraftingData /
--   _hasFullMosaicData), which counts rows regardless of qualification -> n_d / n_f.
-- Qualified-only measure columns are NULL for radiologists below Min exams so their rows still feed n_d / n_f.
WITH base AS (
  SELECT DATE_TRUNC('MONTH', exam_date) AS month_start, team_rolled_up, radiologist,
    x_d, t_d, w_d, x_r, t_r, w_r, x_a, t_a, w_a
  FROM edw_test.enterprise_analytics.mosaic_eff_vs_avg_daily_mv
),
monthly AS (
  SELECT month_start, team_rolled_up, radiologist,
    SUM(x_d) AS x_d, SUM(t_d) AS t_d, SUM(w_d) AS w_d,
    SUM(x_r) AS x_r, SUM(t_r) AS t_r, SUM(w_r) AS w_r,
    SUM(x_a) AS x_a, SUM(t_a) AS t_a, SUM(w_a) AS w_a,
    COUNT(x_d) AS n_d, COUNT(x_a) + COUNT(x_r) AS n_f
  FROM base
  GROUP BY ALL
),
pooled AS (
  SELECT *,
    COALESCE(x_a, 0) + COALESCE(x_r, 0) AS x_f_raw,
    CASE WHEN x_a IS NOT NULL OR x_r IS NOT NULL THEN COALESCE(t_a, 0) + COALESCE(t_r, 0) END AS t_f_raw,
    CASE WHEN w_a IS NOT NULL OR w_r IS NOT NULL THEN COALESCE(w_a, 0) + COALESCE(w_r, 0) END AS w_f_raw,
    SUM(COALESCE(x_a, 0) + COALESCE(x_r, 0)) OVER (PARTITION BY radiologist) AS exams_all_time,
    SUM(w_d) OVER (PARTITION BY month_start) AS rp_w_d,
    SUM(t_d) OVER (PARTITION BY month_start) AS rp_t_d,
    SUM(COALESCE(w_a, 0) + COALESCE(w_r, 0)) OVER (PARTITION BY month_start) AS rp_w_f,
    SUM(COALESCE(t_a, 0) + COALESCE(t_r, 0)) OVER (PARTITION BY month_start) AS rp_t_f
  FROM monthly
),
tagged AS (
  SELECT *, exams_all_time >= {MIN_EXAMS} AS q FROM pooled
)
SELECT month_start AS `Month`, DATE_FORMAT(month_start, 'yyyy-MM') AS `Month Label`,
  team_rolled_up AS `Provider Practice`, radiologist AS `Radiologist`, exams_all_time AS `Exams All Time`,
  CASE WHEN q THEN x_d END AS x_d, CASE WHEN q THEN t_d END AS t_d, CASE WHEN q THEN w_d END AS w_d,
  CASE WHEN q THEN x_r END AS x_r, CASE WHEN q THEN t_r END AS t_r, CASE WHEN q THEN w_r END AS w_r,
  CASE WHEN q THEN x_f_raw END AS x_f, CASE WHEN q THEN t_f_raw END AS t_f, CASE WHEN q THEN w_f_raw END AS w_f,
  CASE WHEN q AND x_f_raw > 0 THEN radiologist END AS active_rad,
  n_d, n_f, rp_w_d, rp_t_d, rp_w_f, rp_t_f
FROM tagged
