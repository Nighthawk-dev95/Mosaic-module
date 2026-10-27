-- Exact replication of PBI Mosaic Efficiency page "Mosaic Efficiency vs Average": the Team Rolled Up -> Radiologist ->
-- Parent Exam pivot (Rad_Subspecialty_NB, Mosaic_Exams_AllTime_NB, Mosaic_Exams_Period_NB, Mosaic_Efficiency_NB,
-- Efficiency_vs_RP_Avg_Overall, Efficiency_vs_RP_Avg_NB), Radiologist_Count_NB and the Benchmark_<mode> /
-- Benchmark_<mode>_Overall cards, for every 'Mosaic Mode Selector' mode the dashboard offers.
-- Sources: 042 mosaic_eff_vs_avg_daily_mv (fact by bucket) + 043 mosaic_eff_vs_avg_rad_dim_mv (radiologist dim).
--
-- Per-mode buckets (d = Drafting CR/CT, c = Drafting US/BD, a = Drafting all, r = Reporting), as the PBI measures use them:
--   mode               | qualify (Rad_Qualifies_NB) | period exams | efficiency (Raw) | all-time (parent row) | benchmark
--   Drafting Only      | d                          | d            | a                | d                     | d
--   Reporting Only     | r                          | r            | r                | r                     | r
--   Capture Only       | c                          | a+r          | c                | a+r                   | c
--   Drafting + Capture | d+c                        | d+c          | a+r              | d+c                   | d+c
--   Full Mosaic        | a+r                        | a+r          | a+r              | a+r                   | a+r
-- Visual filter (VF): a (team, radiologist, parent exam) leaf is shown when the radiologist's period exams across all
-- parent exams >= Min exams AND the leaf has period exams > 0 AND a non-blank efficiency (time > 0, TBWU non-null).
-- Team / radiologist rows sum VF leaves only. Efficiency = 60 * TBWU / time.
-- Benchmarks, per radiologist over the window, efficiency = SUM(TBWU) / (SUM(time) / 60) over qualifying radiologists:
--   Pop Avg (card, Benchmark_<mode>)              : exams >= Min AND time > 0, all radiologists.
--   RP Avg Overall (card, Benchmark_<mode>_Overall): exams >= Min only.
--   Shown-population benchmark (pivot ALLSELECTED): radiologists with a VF leaf, summed over the (team, parent exam)
--     pairs present in VF, exams >= Min AND time > 0. The pivot's Total-row efficiency IS this benchmark and every
--     row's "vs RP Avg" divides by it; "vs RP Avg Overall" divides by the Overall card.
-- All-time exams: parent rows = the leaf's all-dates exams; radiologist / team / total rows = the dim's all-time totals
--   (043 rad_total_drafting / _reporting / _fullmosaic; Capture uses Full Mosaic) for the VF radiologists, except
--   Drafting + Capture, which sums the VF leaves' all-dates d+c exams.
-- {START} / {END} = the dashboard's period parameter, {MIN_EXAMS} = its min-exams parameter, {FINAL} = output level.
WITH lf AS (
  SELECT team_rolled_up AS team, radiologist AS rad, parent_exam AS proc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_d END) xd,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_d END) td,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_d END) wd,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_c END) xc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_c END) tc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_c END) wc,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_a END) xa,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_a END) ta,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_a END) wa,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN x_r END) xr,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN t_r END) tr,
    SUM(CASE WHEN exam_date BETWEEN {START} AND {END} THEN w_r END) wr,
    SUM(x_d) all_d, SUM(x_c) all_c, SUM(x_a) all_a, SUM(x_r) all_r,
    MAX(CASE WHEN exam_date BETWEEN {START} AND {END} THEN 1 END) in_window
  FROM edw_test.enterprise_analytics.mosaic_eff_vs_avg_daily_mv
  GROUP BY ALL
),
lw AS (
  SELECT *,
    CASE WHEN xd IS NOT NULL OR xc IS NOT NULL THEN COALESCE(xd, 0) + COALESCE(xc, 0) END xdc,
    CASE WHEN td IS NOT NULL OR tc IS NOT NULL THEN COALESCE(td, 0) + COALESCE(tc, 0) END tdc,
    CASE WHEN wd IS NOT NULL OR wc IS NOT NULL THEN COALESCE(wd, 0) + COALESCE(wc, 0) END wdc,
    CASE WHEN xa IS NOT NULL OR xr IS NOT NULL THEN COALESCE(xa, 0) + COALESCE(xr, 0) END xf,
    CASE WHEN ta IS NOT NULL OR tr IS NOT NULL THEN COALESCE(ta, 0) + COALESCE(tr, 0) END tf,
    CASE WHEN wa IS NOT NULL OR wr IS NOT NULL THEN COALESCE(wa, 0) + COALESCE(wr, 0) END wf,
    CASE WHEN all_d IS NOT NULL OR all_c IS NOT NULL THEN COALESCE(all_d, 0) + COALESCE(all_c, 0) END all_dc,
    CASE WHEN all_a IS NOT NULL OR all_r IS NOT NULL THEN COALESCE(all_a, 0) + COALESCE(all_r, 0) END all_f
  FROM lf WHERE in_window = 1
),
leaf AS (
  SELECT 'Drafting Only' AS mode, team, rad, proc, xd q, xd p, ta et, wa ew, all_d ax, xd bx, td bt, wd bw FROM lw
  UNION ALL
  SELECT 'Reporting Only', team, rad, proc, xr, xr, tr, wr, all_r, xr, tr, wr FROM lw
  UNION ALL
  SELECT 'Capture Only', team, rad, proc, xc, xf, tc, wc, all_f, xc, tc, wc FROM lw
  UNION ALL
  SELECT 'Drafting + Capture', team, rad, proc, xdc, xdc, tf, wf, all_dc, xdc, tdc, wdc FROM lw
  UNION ALL
  SELECT 'Full Mosaic', team, rad, proc, xf, xf, tf, wf, all_f, xf, tf, wf FROM lw
),
rad_q AS (
  SELECT mode, team, rad, COALESCE(SUM(q), 0) >= {MIN_EXAMS} AS qualifies FROM leaf GROUP BY ALL
),
vf AS (
  SELECT l.* FROM leaf l JOIN rad_q r ON r.mode = l.mode AND r.team <=> l.team AND r.rad <=> l.rad
  WHERE r.qualifies AND l.p > 0 AND l.et > 0 AND l.ew IS NOT NULL
),
card_rad AS (
  SELECT mode, rad, SUM(bx) bx, SUM(bt) bt, SUM(bw) bw, SUM(q) q, SUM(p) p, SUM(et) et, SUM(ew) ew
  FROM leaf GROUP BY ALL
),
cards AS (
  SELECT mode,
    COUNT(CASE WHEN COALESCE(q, 0) >= {MIN_EXAMS} AND p > 0 AND et > 0 AND ew IS NOT NULL THEN 1 END) AS radiologists,
    SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} AND bt > 0 THEN bw END)
      / (SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} AND bt > 0 THEN bt END) / 60) AS pop_avg,
    SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} THEN bw END)
      / (SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} THEN bt END) / 60) AS overall_avg
  FROM card_rad GROUP BY ALL
),
tp AS (SELECT DISTINCT mode, team, proc FROM vf),
shown_rad AS (
  SELECT l.mode, l.rad, SUM(l.bx) bx, SUM(l.bt) bt, SUM(l.bw) bw
  FROM leaf l
  JOIN (SELECT DISTINCT mode, rad FROM vf) r ON r.mode = l.mode AND r.rad <=> l.rad
  JOIN tp ON tp.mode = l.mode AND tp.team <=> l.team AND tp.proc <=> l.proc
  GROUP BY ALL
),
bench AS (
  SELECT c.mode, c.radiologists, c.pop_avg, c.overall_avg,
    s.bw / (s.bt / 60) AS shown_avg
  FROM cards c LEFT JOIN (
    SELECT mode, SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} AND bt > 0 THEN bw END) bw,
      SUM(CASE WHEN COALESCE(bx, 0) >= {MIN_EXAMS} AND bt > 0 THEN bt END) bt
    FROM shown_rad GROUP BY ALL
  ) s ON s.mode = c.mode
),
dim AS (
  SELECT team_rolled_up AS team, radiologist AS rad, MAX(subspecialty) AS subspecialty,
    SUM(rad_total_drafting) tot_d, SUM(rad_total_reporting) tot_r, SUM(rad_total_fullmosaic) tot_f
  FROM edw_test.enterprise_analytics.mosaic_eff_vs_avg_rad_dim_mv GROUP BY ALL
),
vf_rad AS (
  SELECT v.mode, v.team, v.rad, SUM(v.p) p, SUM(v.et) et, SUM(v.ew) ew,
    CASE v.mode WHEN 'Drafting Only' THEN MAX(dm.tot_d) WHEN 'Reporting Only' THEN MAX(dm.tot_r)
      WHEN 'Drafting + Capture' THEN SUM(v.ax) ELSE MAX(dm.tot_f) END AS alltime,
    MAX(dm.subspecialty) AS subspecialty
  FROM vf v LEFT JOIN dim dm ON dm.team <=> v.team AND dm.rad <=> v.rad
  GROUP BY ALL
),
card_rows AS (
  SELECT mode, CASE mode WHEN 'Drafting Only' THEN 1 WHEN 'Capture Only' THEN 2 WHEN 'Drafting + Capture' THEN 3
      WHEN 'Reporting Only' THEN 4 ELSE 5 END AS sort_key, radiologists AS `Radiologists`, pop_avg AS `Pop Avg Efficiency`,
    overall_avg AS `RP Avg Efficiency Overall`, shown_avg AS `Shown Population Benchmark`
  FROM bench
),
team_rows AS (
  SELECT r.mode, r.team AS `Provider Practice`, 1 AS sort_key, COUNT(*) AS `Radiologists`,
    SUM(r.alltime) AS `Mosaic Exams All Time`, SUM(r.p) AS `Mosaic Exams Period`,
    SUM(r.ew) / (SUM(r.et) / 60) AS `Mosaic Efficiency`,
    SUM(r.ew) / (SUM(r.et) / 60) / MAX(b.overall_avg) AS `Vs RP Avg Overall`,
    SUM(r.ew) / (SUM(r.et) / 60) / MAX(b.shown_avg) AS `Vs RP Avg`
  FROM vf_rad r JOIN bench b ON b.mode = r.mode GROUP BY ALL
  UNION ALL
  SELECT r.mode, 'Total', 0, COUNT(DISTINCT r.rad), SUM(r.alltime), SUM(r.p),
    MAX(b.shown_avg), MAX(b.shown_avg) / MAX(b.overall_avg), 1.0
  FROM vf_rad r JOIN bench b ON b.mode = r.mode GROUP BY ALL
),
radiologist_rows AS (
  SELECT r.mode, r.team AS `Provider Practice`, r.rad AS `Radiologist`, r.subspecialty AS `Subspecialty`,
    r.alltime AS `Mosaic Exams All Time`, r.p AS `Mosaic Exams Period`, r.ew / (r.et / 60) AS `Mosaic Efficiency`,
    r.ew / (r.et / 60) / b.overall_avg AS `Vs RP Avg Overall`, r.ew / (r.et / 60) / b.shown_avg AS `Vs RP Avg`
  FROM vf_rad r JOIN bench b ON b.mode = r.mode
),
parent_exam_rows AS (
  SELECT v.mode, v.team AS `Provider Practice`, v.rad AS `Radiologist`, v.proc AS `Parent Exam`,
    dm.subspecialty AS `Subspecialty`, v.ax AS `Mosaic Exams All Time`, v.p AS `Mosaic Exams Period`,
    v.ew / (v.et / 60) AS `Mosaic Efficiency`, v.ew / (v.et / 60) / b.overall_avg AS `Vs RP Avg Overall`,
    v.ew / (v.et / 60) / b.shown_avg AS `Vs RP Avg`
  FROM vf v JOIN bench b ON b.mode = v.mode LEFT JOIN dim dm ON dm.team <=> v.team AND dm.rad <=> v.rad
)
SELECT mode AS `Mode`, * EXCEPT (mode), {START} AS `Window Start`, {END} AS `Window End`
FROM {FINAL}
