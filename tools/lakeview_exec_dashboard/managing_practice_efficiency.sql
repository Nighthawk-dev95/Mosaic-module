-- Exact replication of PBI Mosaic Efficiency "By Managing Practice" (Managing Practice -> Site) INCLUDING its
-- visual-level filters (Passes Min Exam Filter Practice, RTFILTERFLAG Practice, Show Site Practice Row = 1), for
-- every 'Mosaic Mode Selector' mode. Proven on PBI-extracted site sums (Aug 2026), all 5 modes: total, every
-- practice and every site row, every column. Source: 039 mosaic_eff_managing_site_modes_mv.
-- Managing Practice = radiologist_metrics.Practice (the exam site's practice), NOT the radiologist's home practice.
--
-- A site SURVIVES when, in the window: Mosaic exams > 0, read time > 0, TBWU and baseline contribution non-null,
-- baseline and Mosaic efficiency both non-zero, and its practice has >= 1 Mosaic exam across all its sites.
--   Site rows     : Baseline = c/t, Mosaic = 60*w/t (time-weighted).
--   Practice rows : pooled over surviving sites (SUM(c)/SUM(t), 60*SUM(w)/SUM(t)); exam counts are summed.
--   Total row     : the same pooling over every surviving site.
-- Exam columns (blank when <= 0, as in PBI):
--   Site Total Mosaic Exams : mode rows by radiologists present in radiologist_summary, ALL dates (PBI ignores the window)
--   Baseline Exams          : baseline rows (mode modalities), ALL dates, NPI and name both matching radiologist_summary
--   Mosaic Exams            : mode rows by radiologists present in radiologist_summary, in the window
-- {START} / {END} are replaced by the dashboard's date-range parameter; {FINAL} picks the output level.
WITH site_sums AS (
  SELECT managing_practice AS pr, site,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_f END) x_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_f END) t_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_f END) w_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_f END) c_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN xn_f END) mx_f,
    SUM(xn_f) ste_f,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_r END) x_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_r END) t_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_r END) w_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_r END) c_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN xn_r END) mx_r,
    SUM(xn_r) ste_r,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_d END) x_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_d END) t_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_d END) w_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_d END) c_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN xn_d END) mx_d,
    SUM(xn_d) ste_d,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_c END) x_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_c END) t_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_c END) w_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_c END) c_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN xn_c END) mx_c,
    SUM(xn_c) ste_c,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_dc END) x_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_dc END) t_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_dc END) w_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN c_dc END) c_dc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN xn_dc END) mx_dc,
    SUM(xn_dc) ste_dc,
    SUM(bx_all) bx_all, SUM(bx_crct) bx_crct, SUM(bx_usbd) bx_usbd, SUM(bx_dc) bx_dc
  FROM edw_test.enterprise_analytics.mosaic_eff_managing_site_modes_mv
  GROUP BY ALL
),
site AS (
  SELECT 'Full Mosaic' AS mode, pr, site, x_f x, t_f t, w_f w, c_f c, mx_f mx, ste_f ste, bx_all bx FROM site_sums
  UNION ALL
  SELECT 'Reporting Only', pr, site, x_r, t_r, w_r, c_r, mx_r, ste_r, bx_all FROM site_sums
  UNION ALL
  SELECT 'Drafting Only', pr, site, x_d, t_d, w_d, c_d, mx_d, ste_d, bx_crct FROM site_sums
  UNION ALL
  SELECT 'Capture Only', pr, site, x_c, t_c, w_c, c_c, mx_c, ste_c, bx_usbd FROM site_sums
  UNION ALL
  SELECT 'Drafting + Capture', pr, site, x_dc, t_dc, w_dc, c_dc, mx_dc, ste_dc, bx_dc FROM site_sums
),
surv AS (
  SELECT s.* FROM site s
  JOIN (SELECT mode, pr, SUM(x) px FROM site GROUP BY ALL) p ON p.mode = s.mode AND p.pr <=> s.pr
  WHERE s.x > 0 AND s.t > 0 AND s.c IS NOT NULL AND s.w IS NOT NULL AND p.px >= 1
    AND try_divide(s.c, s.t) <> 0 AND try_divide(s.w, s.t) <> 0
),
practice_rows AS (
  SELECT mode, 'Total' AS `Managing Practice`, 0 AS sort_key, COUNT(*) AS `Sites`,
    SUM(ste) ste, SUM(bx) bx, SUM(mx) mx, SUM(c) / SUM(t) b, 60 * SUM(w) / SUM(t) m
  FROM surv GROUP BY ALL
  UNION ALL
  SELECT mode, pr, 1, COUNT(*), SUM(ste), SUM(bx), SUM(mx), SUM(c) / SUM(t), 60 * SUM(w) / SUM(t)
  FROM surv GROUP BY ALL
),
site_rows AS (
  SELECT mode, pr AS `Managing Practice`, site AS `Site`, ste, bx, mx, c / t b, 60 * w / t m
  FROM surv
)
SELECT mode AS `Mode`, * EXCEPT (mode, ste, bx, mx, b, m),
  CASE WHEN ste > 0 THEN ste END AS `Site Total Mosaic Exams`,
  CASE WHEN bx > 0 THEN bx END AS `Baseline Exams`,
  CASE WHEN mx > 0 THEN mx END AS `Mosaic Exams`,
  b AS `Baseline Efficiency`, m AS `Mosaic Efficiency`,
  try_divide(m - b, b) AS `Pct Change Vs Baseline`,
  1 - try_divide(b, m) AS `Implied Read Time Savings Pct`,
  {START} AS `Window Start`, {END} AS `Window End`
FROM {FINAL}
