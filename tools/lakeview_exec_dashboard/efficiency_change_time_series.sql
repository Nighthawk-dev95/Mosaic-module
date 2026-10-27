-- Exact replication of PBI Mosaic Efficiency "Efficiency Change, Time Series" (measure
-- Mode_Lines[Efficiency_Change_By_Mode_Line], tooltips Tooltip_ExamCount_Line / Tooltip_RadCount_Line) for every
-- Mosaic mode. Source: 040 mosaic_eff_rad_daily_modes_mv (Outliers = Excluded).
-- PBI gates each radiologist (fact Radiologist name) per mode on ALL-TIME sums, independent of every filter:
--   exams >= Min Exams (default 0), read time non-zero and non-null, TBWU and baseline contribution non-null.
-- Output keeps daily rows for gated radiologists only, so the dashboard's date filter clips weeks/months exactly as
-- PBI does (a point = period intersected with the selected window). Widgets aggregate:
--   Efficiency Change = (60*SUM(w)/SUM(t) - SUM(c)/SUM(t)) / (SUM(c)/SUM(t)),
--   Exams = SUM(x), Radiologists = COUNT(DISTINCT radiologist).
WITH modes AS (
  SELECT 'Full Mosaic' AS mode, radiologist, team_rolled_up, managing_practice, local_region, exam_date, x_f x, t_f t, w_f w, c_f c
  FROM edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
  UNION ALL
  SELECT 'Reporting Only', radiologist, team_rolled_up, managing_practice, local_region, exam_date, x_r, t_r, w_r, c_r
  FROM edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
  UNION ALL
  SELECT 'Drafting Only', radiologist, team_rolled_up, managing_practice, local_region, exam_date, x_d, t_d, w_d, c_d
  FROM edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
  UNION ALL
  SELECT 'Capture Only', radiologist, team_rolled_up, managing_practice, local_region, exam_date, x_c, t_c, w_c, c_c
  FROM edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
  UNION ALL
  SELECT 'Drafting + Capture', radiologist, team_rolled_up, managing_practice, local_region, exam_date, x_dc, t_dc, w_dc, c_dc
  FROM edw_test.enterprise_analytics.mosaic_eff_rad_daily_modes_mv
),
rows AS (SELECT * FROM modes WHERE x IS NOT NULL OR t IS NOT NULL OR w IS NOT NULL OR c IS NOT NULL),
gate AS (
  SELECT mode, radiologist FROM rows GROUP BY ALL
  HAVING COALESCE(SUM(x), 0) >= {MIN_EXAMS} AND SUM(t) <> 0 AND SUM(w) IS NOT NULL AND SUM(c) IS NOT NULL
)
SELECT r.mode AS `Mode`, r.radiologist AS `Radiologist`, r.team_rolled_up AS `Provider Practice`,
  r.managing_practice AS `Managing Practice`, r.local_region AS `Local Region`, r.exam_date AS `Exam Date`,
  r.x, r.t, r.w, r.c
FROM rows r JOIN gate g ON g.mode = r.mode AND g.radiologist <=> r.radiologist
