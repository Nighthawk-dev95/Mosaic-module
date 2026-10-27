-- Exact replication of the PBI Mosaic Efficiency "Time Series" page (matrix of measures
-- Mosaic Mode[Mean Work Units per Minmode (With Vol)] and Mosaic Mode[VolumeMode] by Team Rolled Up >
-- Radiologist > Parent Exam x Beginning_of_Month, visual filter has volumemode = 1). Source: 041
-- mosaic_eff_timeseries_month_mv (Outliers = Excluded). The PBI measures bucket on Period_Type, not Is_*_Row:
--   Legacy = Baseline; Mosaic = the selected mode; Both = Baseline + mode.
--   Full Mosaic = Drafting + Reporting, Reporting Only = Reporting, Drafting Only = Drafting (ALL modalities),
--   Capture Only = Drafting with Modality US/BD. (This page has no Drafting + Capture mode.)
-- Baseline and Mosaic contributions are separate rows so SUM() treats blanks exactly as PBI's BLANK + number.
-- Only rows with exams are kept (verified: no row has read time or TBWU without exams), which is PBI's
-- has volumemode = 1 filter. Widgets aggregate: WU/min = 60*SUM(w)/SUM(t), Exams = SUM(x).
-- t is NULLIF(t, 0) per row so a cell's SUM(t) is NULL rather than 0 (PBI DIVIDE -> blank).
WITH mv AS (
  SELECT team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_b, t_b, w_b, x_f, t_f, w_f, x_r, t_r, w_r, x_d, t_d, w_d, x_c, t_c, w_c
  FROM edw_test.enterprise_analytics.mosaic_eff_timeseries_month_mv
),
baseline AS (
  SELECT team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_b AS x, NULLIF(t_b, 0) AS t, w_b AS w
  FROM mv WHERE x_b > 0
),
mosaic AS (
  SELECT 'Full Mosaic' AS mode, team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_f AS x, NULLIF(t_f, 0) AS t, w_f AS w FROM mv WHERE x_f > 0
  UNION ALL
  SELECT 'Reporting Only', team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_r, NULLIF(t_r, 0), w_r FROM mv WHERE x_r > 0
  UNION ALL
  SELECT 'Drafting Only', team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_d, NULLIF(t_d, 0), w_d FROM mv WHERE x_d > 0
  UNION ALL
  SELECT 'Capture Only', team_rolled_up, radiologist, parent_exam, managing_practice, local_region, month_start,
    x_c, NULLIF(t_c, 0), w_c FROM mv WHERE x_c > 0
),
tagged AS (
  SELECT p.platform, m.mode, b.team_rolled_up, b.radiologist, b.parent_exam, b.managing_practice, b.local_region,
    b.month_start, b.x, b.t, b.w
  FROM baseline b
  CROSS JOIN (VALUES ('Legacy'), ('Both')) AS p(platform)
  CROSS JOIN (VALUES ('Full Mosaic'), ('Reporting Only'), ('Drafting Only'), ('Capture Only')) AS m(mode)
  UNION ALL
  SELECT p.platform, s.mode, s.team_rolled_up, s.radiologist, s.parent_exam, s.managing_practice, s.local_region,
    s.month_start, s.x, s.t, s.w
  FROM mosaic s
  CROSS JOIN (VALUES ('Mosaic'), ('Both')) AS p(platform)
)
SELECT platform AS `Platform`, mode AS `Mode`, team_rolled_up AS `Provider Practice`, radiologist AS `Radiologist`,
  parent_exam AS `Parent Exam`, managing_practice AS `Managing Practice`, local_region AS `Local Region`,
  month_start AS `Month`, DATE_FORMAT(month_start, 'yyyy-MM') AS `Month Label`, x, t, w
FROM tagged
