-- Exact replication of PBI Mosaic Efficiency "By Provider Practice" INCLUDING its visual-level filters
-- (Hasbothmetricseff_Opt = 1, RTFILTERFLAG_Opt = 1), for every 'Mosaic Mode Selector' mode: Full Mosaic,
-- Reporting Only, Drafting Only (CR/CT), Capture Only (US/BD), Drafting + Capture (CR/CT/US/BD).
-- Proven on the PBI model (Aug 2026), every mode, practice + total + radiologist + parent exam rows.
-- Source: 038 mosaic_eff_provider_leaf_modes_mv.
--
-- Leaf = (practice, radiologist, parent exam). A leaf SURVIVES (S) the visual filter when the radiologist
-- qualifies on their full values (exams >= 1, baseline > 0, Mosaic non-blank) AND the leaf has Mosaic exams,
-- baseline exams (all dates, mode modalities), baseline > 0 and a non-blank Mosaic efficiency (time > 0, TBWU non-null).
--   Radiologist rows : S leaves only.
--   Parent Exam rows : S leaves. PBI shows the exam's own baseline here (Base_Baseline_Eff_Opt =
--                      MAX(Baseline_Eff_Proc_Excl), US/BD version for Capture Only), not the time-weighted one.
--   Practice rows : radiologists with >= 1 S leaf, over S leaves + R leaves (failing leaves whose
--                   (practice, parent exam) survives for some radiologist in that practice) -- the DAX context
--                   transition drops the rad column from the tuple filter. So a practice row != sum of its rads.
--   Total row     : the same S + R values merged by radiologist across practices.
-- Rows are re-qualified, then time-weighted pooled: baseline = SUM(c)/SUM(t), Mosaic = 60*SUM(w)/SUM(t).
-- {START} / {END} are replaced by the dashboard's date-range parameter; {FINAL} picks the output level.
WITH tri AS (
  SELECT team_rolled_up AS team, radiologist AS rad, parent_exam AS proc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_f END) x_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_f END) t_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_f END) w_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_f END) c_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_r END) x_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_r END) t_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_r END) w_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_r END) c_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_d END) x_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_d END) t_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_d END) w_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_d END) c_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_c END) x_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_c END) t_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_c END) w_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_c END) c_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_dc END) x_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_dc END) t_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_dc END) w_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_dc END) c_dc,
    SUM(bx_all) bx_all, SUM(bx_crct) bx_crct, SUM(bx_usbd) bx_usbd, SUM(bx_dc) bx_dc,
    MAX(be_proc) be_proc, MAX(be_usbd) be_usbd
  FROM edw_test.enterprise_analytics.mosaic_eff_provider_leaf_modes_mv
  WHERE bx_all IS NOT NULL OR exam_date BETWEEN {START} AND {END}
  GROUP BY ALL
),
leaf AS (
  SELECT 'Full Mosaic' AS mode, team, rad, proc, x_f x, t_f t, w_f w, c_f c, bx_all bx, be_proc be FROM tri WHERE x_f IS NOT NULL
  UNION ALL
  SELECT 'Reporting Only', team, rad, proc, x_r, t_r, w_r, c_r, bx_all, be_proc FROM tri WHERE x_r IS NOT NULL
  UNION ALL
  SELECT 'Drafting Only', team, rad, proc, x_d, t_d, w_d, c_d, bx_crct, be_proc FROM tri WHERE x_d IS NOT NULL
  UNION ALL
  SELECT 'Capture Only', team, rad, proc, x_c, t_c, w_c, c_c, bx_usbd, be_usbd FROM tri WHERE x_c IS NOT NULL
  UNION ALL
  SELECT 'Drafting + Capture', team, rad, proc, x_dc, t_dc, w_dc, c_dc, bx_dc, be_proc FROM tri WHERE x_dc IS NOT NULL
),
rad_full AS (
  SELECT mode, team, rad, SUM(x) >= 1 AND SUM(t) > 0 AND SUM(c) / SUM(t) > 0 AND SUM(w) IS NOT NULL AS rad_q
  FROM leaf GROUP BY ALL
),
leaf_s AS (
  SELECT l.*, r.rad_q AND l.x > 0 AND COALESCE(l.bx, 0) > 0 AND l.t > 0 AND l.c / l.t > 0 AND l.w IS NOT NULL AS s
  FROM leaf l JOIN rad_full r ON r.mode = l.mode AND r.team <=> l.team AND r.rad <=> l.rad
),
tp AS (SELECT DISTINCT mode, team, proc FROM leaf_s WHERE s),
leaf_c AS (
  SELECT l.*, CASE WHEN l.s THEN 'S' WHEN tp.proc IS NOT NULL THEN 'R' ELSE 'D' END AS cls
  FROM leaf_s l LEFT JOIN tp ON tp.mode = l.mode AND tp.team <=> l.team AND tp.proc <=> l.proc
),
rad_sr AS (
  SELECT mode, team, rad, SUM(x) x, SUM(t) t, SUM(w) w, SUM(c) c
  FROM leaf_c WHERE cls <> 'D' GROUP BY ALL HAVING MAX(CASE WHEN cls = 'S' THEN 1 END) = 1
),
practice_rows AS (
  SELECT mode, team AS `Provider Practice`, 1 AS sort_key, COUNT(*) AS `Radiologists`, SUM(x) AS `Mosaic Exams`,
    SUM(c) / SUM(t) AS `Baseline Efficiency`, 60 * SUM(w) / SUM(t) AS `Mosaic Efficiency`
  FROM rad_sr WHERE x >= 1 AND t > 0 AND c / t > 0 AND w IS NOT NULL GROUP BY ALL
  UNION ALL
  SELECT mode, 'Total', 0, COUNT(*), SUM(x), SUM(c) / SUM(t), 60 * SUM(w) / SUM(t)
  FROM (SELECT mode, rad, SUM(x) x, SUM(t) t, SUM(w) w, SUM(c) c FROM rad_sr GROUP BY ALL)
  WHERE x >= 1 AND t > 0 AND c / t > 0 AND w IS NOT NULL GROUP BY ALL
),
radiologist_rows AS (
  SELECT mode, team AS `Provider Practice`, rad AS `Radiologist`, SUM(x) AS `Mosaic Exams`,
    SUM(c) / SUM(t) AS `Baseline Efficiency`, 60 * SUM(w) / SUM(t) AS `Mosaic Efficiency`
  FROM leaf_c WHERE cls = 'S' GROUP BY ALL
),
parent_exam_rows AS (
  SELECT mode, team AS `Provider Practice`, rad AS `Radiologist`, proc AS `Parent Exam`, x AS `Mosaic Exams`,
    be AS `Baseline Efficiency`, 60 * w / t AS `Mosaic Efficiency`
  FROM leaf_c WHERE cls = 'S'
)
SELECT mode AS `Mode`, * EXCEPT (mode), try_divide(`Mosaic Efficiency` - `Baseline Efficiency`, `Baseline Efficiency`) AS `Pct Change Vs Baseline`,
  {START} AS `Window Start`, {END} AS `Window End`
FROM {FINAL}
