CREATE OR REPLACE TABLE edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail AS
WITH tagged_source AS (
  SELECT
    r.Exam_ID, r.Accession_Number, r.Physician_NPI, r.Radiologist,
    r.Parent_Procedure_name, r.Modality_Code, r.Clinical_Procedure_Code,
    DATE(r.Dictation_Start) AS Exam_Date, r.Adjusted_Read_Time_Sec, r.RP_TBWU,
    r.mosaic_flag, r.mosaic_draft_flag,
    COALESCE(e.provider_local_practice_name_curr, r.Practice) AS Practice,
    CASE
      WHEN r.mosaic_flag = 0 THEN NULL
      WHEN DATE(r.Dictation_Start) < DATE'2026-07-28' THEN 'Mosaic 1.0'
      ELSE m.mosaic_version
    END AS version_tag
  FROM edw_dev.bipa_analytics.presentation_rpt_readtimeswith_draftingadjustedrt_tbl r
  LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_inventory e
    ON r.Accession_Number = e.accession_number
  LEFT JOIN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail m
    ON r.Accession_Number = m.accession_number
    AND DATE(r.Dictation_Start) >= DATE'2026-07-28'
  WHERE r.mosaic_flag = 0 OR (r.Dictation_Start < DATE'2026-07-28') OR m.accession_number IS NOT NULL
),
outlier_calculation AS (
  SELECT *,
    CASE
      WHEN Adjusted_Read_Time_Sec < 1 THEN 'Included'
      WHEN Adjusted_Read_Time_Sec > (
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY Adjusted_Read_Time_Sec) OVER (PARTITION BY Clinical_Procedure_Code)
      ) THEN 'Included'
      ELSE 'Excluded'
    END AS Outliers
  FROM tagged_source
),
classified_data AS (
  SELECT *,
    CASE
      WHEN mosaic_flag = 0 THEN 'Baseline'
      WHEN mosaic_draft_flag = 1 THEN 'Drafting'
      WHEN mosaic_flag = 1 THEN 'Reporting'
      ELSE 'Unknown'
    END AS Period_Type
  FROM outlier_calculation
),
exam_level AS (
  SELECT DISTINCT
    Exam_ID, Physician_NPI, Radiologist, Practice, Parent_Procedure_name, Modality_Code,
    Exam_Date, Outliers, Period_Type, version_tag, Adjusted_Read_Time_Sec, RP_TBWU
  FROM classified_data
),
agg AS (
  SELECT
    Physician_NPI, Radiologist, Practice, Parent_Procedure_name, Modality_Code,
    Period_Type, version_tag, Outliers,
    Exam_Date,
    SUM(Adjusted_Read_Time_Sec) AS TotalTime,
    SUM(RP_TBWU) AS TotalTBWU,
    COUNT(*) AS ExamCount
  FROM exam_level
  GROUP BY 1,2,3,4,5,6,7,8,9
),
baseline_by_procedure AS (
  SELECT Physician_NPI, Parent_Procedure_name,
    SUM(TotalTBWU) AS baseline_tbwu, SUM(TotalTime) AS baseline_time
  FROM agg
  WHERE Period_Type = 'Baseline' AND Outliers = 'Excluded'
  GROUP BY 1,2
),
baseline_eff AS (
  SELECT Physician_NPI, Parent_Procedure_name,
    baseline_tbwu / NULLIF(baseline_time / 60.0, 0) AS baseline_eff_rate
  FROM baseline_by_procedure
),
mosaic_rows_weighted AS (
  SELECT
    a.Physician_NPI, a.Radiologist, a.Practice, a.Parent_Procedure_name, a.Modality_Code,
    a.version_tag, a.Exam_Date, a.TotalTime, a.TotalTBWU, a.ExamCount,
    b.baseline_eff_rate * a.TotalTime AS weighted_baseline_contrib
  FROM agg a
  JOIN baseline_eff b
    ON a.Physician_NPI = b.Physician_NPI AND a.Parent_Procedure_name = b.Parent_Procedure_name
  WHERE a.Period_Type IN ('Drafting','Reporting') AND a.Outliers = 'Excluded' AND a.version_tag IS NOT NULL
)
SELECT
  w.Physician_NPI AS physician_npi,
  w.Radiologist AS radiologist_name,
  w.Practice AS practice,
  COALESCE(pl.local, 'Unmapped') AS local,
  w.Parent_Procedure_name AS procedure_name,
  w.Modality_Code AS modality,
  CASE WHEN w.Modality_Code = 'MG' THEN 'MG' ELSE 'Non-MG' END AS modality_group,
  w.version_tag AS mosaic_version,
  w.Exam_Date AS exam_date,
  w.TotalTime AS total_time_sec,
  w.TotalTBWU AS total_tbwu,
  w.ExamCount AS exam_count,
  w.weighted_baseline_contrib
FROM mosaic_rows_weighted w
LEFT JOIN edw_dev.enterprise_analytics.practice_to_local_mapping pl
  ON w.Practice = pl.practice
