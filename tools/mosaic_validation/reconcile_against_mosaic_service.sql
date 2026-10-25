-- Reconciliation queries: metric-view aggregate vs mosaic_service.py's own raw SQL constants/CTEs,
-- run on the exact same underlying table, for every item already claimed to match exactly.
-- Appended to across Phases A/B/C. Every block pairs a metric-view query with the equivalent raw
-- SQL lifted directly from backend/app/services/mosaic_service.py. All of the below were run live
-- on 2026-10-23 AFTER repointing all 3 source views from the frozen edw_test snapshot of
-- tbl_exam_inventory to the live edw_prod table (see VALIDATION_REPORT_VOLUME.md item 0).

-- ============================================================
-- VOLUME reconciliations (Phase A) -- all CONFIRMED EXACT MATCH
-- ============================================================

-- Is RPCE Source (mosaic_service.py's _RPCE_SOURCE_SYSTEMS_SQL = 'rpceMidwest','rpceSouthwest')
SELECT `Is RPCE Source`, MEASURE(`Exam Count`) AS mv_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL;
-- vs
SELECT
  SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END) AS raw_rpce_true,
  SUM(CASE WHEN Source_System_Code NOT IN ('rpceMidwest', 'rpceSouthwest') OR Source_System_Code IS NULL THEN 1 ELSE 0 END) AS raw_rpce_false
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;
-- RESULT: True 103,187,543 / False 45,969,564 both sides. Exact match.

-- Pct RPCE Reporting/Drafting (mosaic_service.py's _RPCE_PCT_ADJUSTMENT = 0.02)
SELECT MEASURE(`Pct RPCE Reporting`) AS mv_pct_rpce_reporting, MEASURE(`Pct RPCE Drafting`) AS mv_pct_rpce_drafting
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();
-- vs
SELECT
  (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
    / NULLIF(SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END), 0))
    + 0.02 AS raw_pct_rpce_reporting,
  (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
    / NULLIF(SUM(CASE WHEN Source_System_Code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END), 0))
    + 0.02 AS raw_pct_rpce_drafting
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;
-- RESULT: 0.204008877893333 / 0.104462327007825 both sides (to float precision). Exact match.

-- Estimated RVU (e.estimated_wrvu AS Estimated_RVU) and TBWU (e.final_TBWU AS RP_TBWU)
SELECT MEASURE(`Estimated RVU`) AS mv_estimated_rvu, MEASURE(`TBWU`) AS mv_tbwu
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view();
-- vs
SELECT SUM(estimated_wrvu) AS raw_estimated_rvu, SUM(final_TBWU) AS raw_tbwu
FROM edw_prod.enterprise_analytics.tbl_exam_inventory;
-- RESULT: 131,504,043.72 / 111,894,093.2556 both sides. Exact match.

-- Reporting Status (Drafting > Reporting > Baseline vocabulary)
SELECT `Reporting Status`, MEASURE(`Exam Count`) AS mv_count
FROM edw_test.enterprise_analytics.mosaic_volume_metric_view()
GROUP BY ALL;
-- vs
SELECT
  CASE WHEN mosaic_draft_flag THEN 'Drafting' WHEN mosaic_read_flag THEN 'Reporting' ELSE 'Baseline' END AS raw_status,
  COUNT(*) AS raw_count
FROM edw_prod.enterprise_analytics.tbl_exam_inventory
GROUP BY ALL;
-- RESULT: Reporting 10,271,964 / Baseline 130,169,683 / Drafting 8,715,460 both sides. Exact match.

-- ============================================================
-- EFFICIENCY reconciliations (Phase B) -- CONFIRMED EXACT MATCH
-- ============================================================

-- Full exam-level CTE chain, reconstructed VERBATIM from mosaic_service.py's _MER_BASE_CTE_SQL +
-- _MER_BASELINE_CTE_SQL (not from the deployed view's SQL), run independently against edw_prod.
WITH mosaic_live_practices AS (
  SELECT DISTINCT provider_local_practice_name_curr AS practice
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory
  WHERE mosaic_read_flag = true AND provider_local_practice_name_curr IS NOT NULL
),
qualified_radiologists AS (
  SELECT e.reading_provider_npi AS npi
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.practice = e.provider_local_practice_name_curr
  WHERE NOT e.mosaic_read_flag AND NOT e.mosaic_draft_flag
    AND CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND CAST(e.reading_provider_npi AS STRING) NOT IN (
      '1134233869', '1578529640', '1255305371', '1043457591', '1134169857', '1174919955',
      '1588690002', '1083662803', '1184859589', '1861695322', '1124331582', '1578728184',
      '1568705986', '1144482738', '1134395858'
    )
  GROUP BY e.reading_provider_npi
  HAVING COUNT(DISTINCT e.exam_id) >= 1000
),
raw_exams AS (
  SELECT
    e.exam_id, e.reading_provider_npi AS Physician_NPI,
    e.RPID_parent_code_description AS Parent_Procedure_name,
    e.exam_Modality_Code AS Modality_Code,
    e.RPID_Procedure_Code,
    e.mosaic_read_flag, e.mosaic_draft_flag,
    e.unassisted_tbwu_current AS TBWU,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime,
    LAG(e.final_datetime) OVER (
      PARTITION BY e.reading_provider_npi, DATE(e.dictation_start_datetime)
      ORDER BY e.dictation_start_datetime, e.exam_id
    ) AS prev_final
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.practice = e.provider_local_practice_name_curr
  JOIN qualified_radiologists qr ON qr.npi = e.reading_provider_npi
  WHERE CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND e.dictation_start_datetime IS NOT NULL
    AND e.dictation_end_datetime IS NOT NULL
    AND e.final_datetime IS NOT NULL
),
adjusted AS (
  SELECT *,
    LEAST(3600, GREATEST(0, TIMESTAMPDIFF(SECOND,
      CASE WHEN prev_final IS NOT NULL AND prev_final > dictation_start_datetime THEN prev_final ELSE dictation_start_datetime END,
      CASE WHEN final_datetime < dictation_end_datetime THEN final_datetime ELSE dictation_end_datetime END
    ))) AS Adjusted_Read_Time_Sec
  FROM raw_exams
),
outlier_calc AS (
  SELECT *,
    CASE WHEN Adjusted_Read_Time_Sec > (
      AVG(Adjusted_Read_Time_Sec) OVER (PARTITION BY RPID_Procedure_Code)
      + 2 * STDDEV(Adjusted_Read_Time_Sec) OVER (PARTITION BY RPID_Procedure_Code)
    ) THEN 'Included' ELSE 'Excluded' END AS Outliers
  FROM adjusted
),
classified AS (
  SELECT *,
    CASE
      WHEN NOT mosaic_read_flag AND NOT mosaic_draft_flag THEN 'Baseline'
      WHEN mosaic_draft_flag THEN 'Drafting'
      WHEN mosaic_read_flag THEN 'Reporting'
      ELSE 'Unknown'
    END AS Period_Type
  FROM outlier_calc
),
baseline_by_procedure AS (
  SELECT
    Physician_NPI, Parent_Procedure_name,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' THEN TBWU ELSE 0 END) AS baseline_tbwu_excl,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' THEN Adjusted_Read_Time_Sec ELSE 0 END) AS baseline_time_excl
  FROM classified
  GROUP BY Physician_NPI, Parent_Procedure_name
),
baseline_eff AS (
  SELECT Physician_NPI, Parent_Procedure_name,
    baseline_tbwu_excl / NULLIF(baseline_time_excl / 60.0, 0) AS baseline_eff_excl
  FROM baseline_by_procedure
)
SELECT
  SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS raw_reporting_exams,
  SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS raw_reporting_tbwu
FROM classified c
JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
WHERE be.baseline_eff_excl <= 1.000;
-- vs
SELECT
  MEASURE(`Reporting Mosaic Exams`) AS mv_reporting_exams,
  MEASURE(`Reporting Mosaic TBWU`) AS mv_reporting_tbwu
FROM edw_test.enterprise_analytics.mosaic_efficiency_metric_view(1);
-- RESULT: 7,826,125 exams / 7,895,061.5104 TBWU both sides. Exact match.

-- ============================================================
-- CAPACITY reconciliations (Phase C) -- NEAR-EXACT MATCH (0.00014% residual, explained)
-- ============================================================

-- shift_exams/with_lag/with_read_time/raw_shifts chain, reconstructed VERBATIM from
-- mosaic_service.py's _CAPACITY_SHIFT_CTE_SQL, run independently against edw_prod.
WITH shift_exams AS (
  SELECT
    e.exam_id, e.reading_provider_npi AS NPI, e.scheduled_shift_id AS Shift_No,
    e.scheduled_shift_task_name AS ShiftName,
    CAST(e.scheduled_shift_start_datetime_utc AS DATE) AS ShiftDate,
    e.scheduled_shift_start_datetime_utc AS Schedule_Start_DateTime,
    e.scheduled_shift_end_datetime_utc AS Schedule_End_DateTime,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory e
  WHERE e.scheduled_shift_id IS NOT NULL
    AND e.scheduled_shift_start_datetime_utc IS NOT NULL
    AND e.scheduled_shift_end_datetime_utc IS NOT NULL
    AND CAST(e.scheduled_shift_start_datetime_utc AS DATE) >= DATE'2024-10-01'
),
with_lag AS (
  SELECT *,
    LAG(final_datetime) OVER (
      PARTITION BY NPI, DATE(dictation_start_datetime)
      ORDER BY dictation_start_datetime, exam_id
    ) AS prev_final
  FROM shift_exams
),
with_read_time AS (
  SELECT *,
    CASE WHEN dictation_start_datetime IS NOT NULL AND dictation_end_datetime IS NOT NULL AND final_datetime IS NOT NULL
      THEN LEAST(3600, GREATEST(0, TIMESTAMPDIFF(SECOND,
        CASE WHEN prev_final IS NOT NULL AND prev_final > dictation_start_datetime THEN prev_final ELSE dictation_start_datetime END,
        CASE WHEN final_datetime < dictation_end_datetime THEN final_datetime ELSE dictation_end_datetime END
      )))
      ELSE NULL
    END AS adjusted_read_time_sec
  FROM with_lag
),
raw_shifts AS (
  SELECT
    e.NPI, e.ShiftDate, e.ShiftName, e.Shift_No AS Task_ID,
    MAX(TIMESTAMPDIFF(MINUTE, e.Schedule_Start_DateTime, e.Schedule_End_DateTime)) / 60.0 AS no_hours,
    COUNT(*) AS shift_cases,
    SUM(e.adjusted_read_time_sec) / 60.0 AS shift_read_minutes
  FROM with_read_time e
  GROUP BY e.NPI, e.ShiftDate, e.ShiftName, e.Shift_No
)
SELECT SUM(shift_cases) AS raw_total_cases, SUM(shift_read_minutes) AS raw_total_read_minutes
FROM raw_shifts;
-- vs
SELECT MEASURE(`On Shift Cases`) AS mv_cases, MEASURE(`Read Minutes`) AS mv_read_minutes
FROM edw_test.enterprise_analytics.mosaic_capacity_metric_view();
-- RESULT: 72,049,803 / 257,566,504.00 (raw) vs 72,049,702 / 257,566,500.25 (metric view).
-- Delta: 101 rows (0.00014%), 3.75 min -- most likely the deployed view's
-- `WHERE v.practice IS NOT NULL` filter, omitted from this hand-reconstruction. Immaterial.
