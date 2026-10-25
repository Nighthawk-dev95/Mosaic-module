-- Scheduled refresh for edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.
-- Same logic as the commented-out re-sync block at the bottom of
-- tools/edw_fixes/014_migrate_shift_utilization_to_enterprise_analytics.sql, extracted into its
-- own runnable file for this job. INSERT OVERWRITE preserves the table/column comments already
-- set on this table.

INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization
WITH shifts AS (
  SELECT
    NPI AS npi,
    MAX(Radiologist) AS radiologist_name,
    MAX(Practice_Short_Name) AS practice,
    CAST(Calendar_Date AS DATE) AS shift_date,
    shift_start_dt,
    MAX(utilization_pct) / 100.0 AS utilization_pct,
    MAX(reading_minutes) AS reading_minutes,
    MAX(shift_total_minutes) AS shift_total_minutes
  FROM edw_dev.bipa_analytics.presentation_deneb_vw
  WHERE Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
    AND shift_start_dt IS NOT NULL
  GROUP BY NPI, CAST(Calendar_Date AS DATE), shift_start_dt
),
exam_flags AS (
  SELECT
    d.NPI AS npi,
    CAST(d.Calendar_Date AS DATE) AS shift_date,
    d.shift_start_dt,
    COUNT(DISTINCT CASE WHEN e.mosaic_read_flag THEN d.Accession_Number END)
      / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_mosaic_read,
    COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN d.Accession_Number END)
      / NULLIF(COUNT(DISTINCT d.Accession_Number), 0)  AS pct_ai_drafted
  FROM edw_dev.bipa_analytics.presentation_deneb_vw d
  LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_inventory e
    ON d.Accession_Number = e.accession_number
  WHERE d.Calendar_Date >= DATE_SUB(CURRENT_DATE(), 90)
    AND d.bar_type = 'Reading Time'
    AND d.Accession_Number IS NOT NULL
  GROUP BY d.NPI, CAST(d.Calendar_Date AS DATE), d.shift_start_dt
)
SELECT
  s.npi, s.radiologist_name, s.practice,
  CAST(s.shift_date AS STRING) AS shift_date,
  s.utilization_pct, s.reading_minutes, s.shift_total_minutes,
  f.pct_mosaic_read, f.pct_ai_drafted
FROM shifts s
LEFT JOIN exam_flags f
  ON s.npi = f.npi AND s.shift_date = f.shift_date AND s.shift_start_dt = f.shift_start_dt;
