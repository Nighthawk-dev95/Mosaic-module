CREATE VIEW edw_test.enterprise_analytics.mosaic_resident_utilization_metric_view
COMMENT 'RESIDENT UTILIZATION SEMANTIC LAYER (draft). Governed replacement for the PBI "Mosaic Volume Report" Resident Utilization table''s 12 measures, grain = one row per exam read by a resident (reading_provider_resident_flag = ''Y''). (No explicit outer column list -- see mosaic_volume_metric_view''s comment for why.)
Scope reference: edw_dev.mosaictechops.mv_mosaic_resident (NOT reachable -- reference only). Its 5 achievable measures (Exams This Period, Mosaic Exams This Period, Pct Mosaic Exams, First Mosaic Exam, First Mosaic Draft Exam) are all ported below with the same names used in this view''s own naming convention, plus In Window variants. Confirmed with the user and excluded entirely (not a gap): the per-resident "Fully Utilizing (Resident)"/"Count Fully Utilizing Residents" threshold-on-a-rate rollup (redundant concept, same as the practice-level cluster in mosaic_volume_metric_view), and the Eligible Exam Count family (all exams in Mosaic are eligible now) -- see tools/pbi_semantic_extract/mosaic_volume_measure_inventory.md.
FORMAT CONVENTION: every percentage measure returns a RAW FRACTION between 0 and 1.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: "(SELECT * FROM edw_test.enterprise_analytics.tbl_exam_inventory WHERE reading_provider_resident_flag = 'Y')"

parameters:
  - name: days_back
    data_type: int
    default: 14

comment: |-
  RESIDENT UTILIZATION SEMANTIC LAYER (draft). See the CREATE VIEW table comment above.
  Query with a `days_back` argument for the two In Window measures below, same calling
  convention as mosaic_volume_metric_view(N).

dimensions:
  - name: Exam Id
    expr: exam_id

  - name: Resident NPI
    expr: resident_radiologist_npi
    display_name: Resident NPI

  - name: Resident Name
    expr: resident_radiologist_name_full
    display_name: Resident Name

  - name: Radiologist Name
    expr: reading_provider_name_full
    comment: "Supervising/attending radiologist of record on the exam."

  - name: Modality
    expr: exam_Modality_Code
    comment: "Plain film is 'CR', never 'XR'."

  - name: Source System Code
    expr: Source_System_Code

  - name: Final Date
    expr: CAST(final_datetime AS DATE)
    comment: "Apply `WHERE \\`Final Date\\` >= CURRENT_DATE - INTERVAL N DAYS` at query time in place of PBI's hardcoded Last-14d resident measures."
    format:
      type: date
      date_format: year_month_day

  - name: Care Setting
    expr: care_setting

measures:
  - name: Exam Count
    expr: COUNT(*)
    comment: "PBI's 'Exams This Period'/'Resident Total Mosaic Exams (All Time)' denominator."
    display_name: Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Mosaic Exam Count
    expr: COUNT(*) FILTER (WHERE mosaic_read_flag)
    comment: "PBI's 'Mosaic Exams This Period'/'Resident Total Mosaic Exams (All Time)'."
    display_name: Mosaic Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Mosaic Exams
    expr: "MEASURE(`Mosaic Exam Count`) / MEASURE(`Exam Count`)"
    comment: "Absorbs 'Resident % Mosaic Exams' and 'Resident % Mosaic Last 14d' (window applied via the Final Date dimension at query time)."
    display_name: Pct Mosaic Exams
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE CAST(final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Exams This Period' when scoped to the report's rolling window. Query via `mosaic_resident_utilization_metric_view(N)`."
    display_name: Exam Count In Window
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Mosaic Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE mosaic_read_flag AND CAST(final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Mosaic Exams This Period'."
    display_name: Mosaic Exam Count In Window
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Mosaic Exams In Window
    expr: "MEASURE(`Mosaic Exam Count In Window`) / MEASURE(`Exam Count In Window`)"
    comment: "PBI's 'Resident % Mosaic Last 14d'."
    display_name: Pct Mosaic Exams In Window
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: First Mosaic Exam Date
    expr: MIN(CAST(final_datetime AS DATE)) FILTER (WHERE mosaic_read_flag)
    comment: "PBI's 'Resident First Mosaic Exam'. Group by Resident NPI at query time."
    format: { type: date, date_format: year_month_day }

  - name: First Mosaic Drafting Exam Date
    expr: MIN(CAST(final_datetime AS DATE)) FILTER (WHERE mosaic_draft_flag)
    comment: "PBI's 'Resident First Mosaic Draft Exam'."
    format: { type: date, date_format: year_month_day }

$$;
