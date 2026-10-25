-- Mosaic Impact (Capacity) semantic migration. edw_test ONLY. Governed, shift-grain view
-- extending backend/app/services/mosaic_service.py's own validated _CAPACITY_SHIFT_CTE_SQL
-- (one row per (NPI, ShiftDate, ShiftName, Task_ID)) with the full case-mix breakdown the real
-- PBI "0. Cur" table carries, plus a join to the migrated tbl_mosaic_baseline_master (027) for
-- the baseline side - replacing mosaic_service.py's own live Exact/Proxy re-derivation per
-- explicit instruction to use the trusted notebook output directly.
--
-- Case-mix categories covered (confirmed live column mapping): Modality (CT/XR/US/MR/NM/PT/MG/
-- IR/Other via exam_Modality_Code - note CR is "XR" here, matching the Volume semantic's own
-- "plain film is CR, never XR" gotcha reversed for display), Priority (Routine/Stat/Stroke/
-- Trauma/OtherP via Priority_Name), Place of Service (ER/Inpatient/Outpatient via care_setting -
-- same "proxy, not exact PBI match" caveat as the Volume metric view's Care Setting dimension),
-- Mosaic/Drafting/Captured-US-in-Mosaic (mosaic_read_flag/mosaic_draft_flag/US+drafting),
-- Assigned/Pool/Autonext (self_assigned_flag/autonext_flag/neither), VRA-Assisted (VRA_Flag) with
-- its Non-IR-Stroke-Trauma denominator (matches the real DAX '% VRA Assisted' formula exactly).
--
-- Two-tier baseline join (same as mosaic_service.get_capacity_with_baseline): exact
-- (NPI, Task_ID) first, falling back to (NPI, normalized Shift_Name) - picking the
-- Exact-over-Proxy-over-Manual-Review tier if more than one candidate matches on the fallback.
-- Shift_Baseline_TBWU_2026 is a per-canonical-shift-length TOTAL (Shift_Length hours), rescaled
-- to this shift instance's own no_hours, matching the established rescaling rationale (a rad's
-- canonical "12-hour weekend shift" baseline still needs rescaling for a 10-hour version of it).
--
-- READ TIME FIX (confirmed live 2026-10-22, corrected from an initial draft): read-minutes is
-- NOT sourced from tat_unread_to_final_minutes - that column is turnaround time (queue wait +
-- read time, order-available-to-finalized), not active dictation duration, and can legitimately
-- span days for a low-priority exam that sat unread. Summing it raw produced a nonsense ~36.6
-- DAYS of "read time" per shift on average (confirmed live) and made Efficiency/Utilization
-- meaningless. This is the same column mosaic_service.py's own shipped _CAPACITY_SHIFT_CTE_SQL
-- uses (get_capacity_by_radiologist/get_capacity_by_practice have the identical latent issue,
-- just never flagged before now) - flagging as a known pre-existing issue, not fixing that
-- function here. Fixed HERE by reusing tbl_efficiency_exam_level_vw's proven LAG-based, 3600-sec-
-- capped Adjusted_Read_Time_Sec derivation instead, computed at exam grain before rolling up to
-- shift grain. Scoping difference from the Efficiency semantic: LAG here partitions over only
-- shift-attributed exams (this view is shift-centric by design), not every exam for the NPI/day -
-- a deliberate, documented narrowing, not an oversight.

CREATE OR REPLACE VIEW edw_test.enterprise_analytics.tbl_capacity_shift_level_vw
COMMENT 'Mosaic Impact (Capacity) semantic: one row per shift instance, with on-shift TBWU/RVU capacity, POS-adjusted baseline (from the migrated stg_mosaic_baseline_master), utilization %, efficiency, capacity-vs-baseline, and the full case-mix breakdown (modality/priority/place-of-service/mosaic-drafting-capture/assignment-method/VRA). Source for mosaic_capacity_metric_view. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
AS
WITH shift_exams AS (
  SELECT
    e.exam_id,
    e.reading_provider_npi AS npi,
    e.reading_provider_name_full AS radiologist_name,
    e.provider_local_practice_name_curr AS team,
    e.managing_local_practice_name_curr AS practice,
    e.scheduled_shift_id AS task_id,
    e.scheduled_shift_task_name AS shift_name,
    CAST(e.scheduled_shift_start_datetime_utc AS DATE) AS shift_date,
    e.scheduled_shift_start_datetime_utc AS schedule_start_datetime,
    e.scheduled_shift_end_datetime_utc AS schedule_end_datetime,
    e.final_TBWU AS rp_tbwu,
    e.estimated_wrvu AS estimated_rvu,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime,
    e.mosaic_read_flag, e.mosaic_draft_flag,
    e.exam_Modality_Code AS modality_code,
    e.Priority_Name AS priority_name,
    e.care_setting,
    e.VRA_Flag AS vra_flag,
    e.self_assigned_flag, e.autonext_flag,
    e.Source_System_Code AS source_system_code
  FROM edw_test.enterprise_analytics.tbl_exam_inventory e
  WHERE e.scheduled_shift_id IS NOT NULL
    AND e.scheduled_shift_start_datetime_utc IS NOT NULL
    AND e.scheduled_shift_end_datetime_utc IS NOT NULL
    AND CAST(e.scheduled_shift_start_datetime_utc AS DATE) >= DATE'2024-10-01'
),
with_lag AS (
  SELECT *,
    LAG(final_datetime) OVER (
      PARTITION BY npi, DATE(dictation_start_datetime)
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
    e.npi, MAX(e.radiologist_name) AS radiologist_name, MAX(e.team) AS team, MAX(e.practice) AS practice,
    e.shift_date, e.shift_name, e.task_id,
    MAX(TIMESTAMPDIFF(MINUTE, e.schedule_start_datetime, e.schedule_end_datetime)) / 60.0 AS no_hours,
    CAST(SUM(e.rp_tbwu) AS DECIMAL(10,2)) AS shift_tbwu,
    CAST(SUM(e.estimated_rvu) AS DECIMAL(10,2)) AS shift_rvu,
    COUNT(*) AS shift_cases,
    SUM(e.adjusted_read_time_sec) / 60.0 AS shift_read_minutes,
    SUM(CASE WHEN e.adjusted_read_time_sec IS NOT NULL THEN 1 ELSE 0 END) AS exams_with_valid_read_time,
    MAX(CASE WHEN e.source_system_code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END) AS is_rpce_source,
    SUM(CASE WHEN e.mosaic_read_flag THEN 1 ELSE 0 END) AS mosaic_cases,
    SUM(CASE WHEN e.mosaic_draft_flag THEN 1 ELSE 0 END) AS drafting_cases,
    SUM(CASE WHEN e.modality_code = 'US' AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_us_in_mosaic_cases,
    SUM(CASE WHEN e.self_assigned_flag THEN 1 ELSE 0 END) AS assigned_cases,
    SUM(CASE WHEN e.autonext_flag THEN 1 ELSE 0 END) AS autonext_cases,
    SUM(CASE WHEN NOT e.self_assigned_flag AND NOT e.autonext_flag THEN 1 ELSE 0 END) AS pool_cases,
    SUM(CASE WHEN e.vra_flag THEN 1 ELSE 0 END) AS assisted_cases,
    SUM(CASE WHEN e.modality_code = 'CT' THEN 1 ELSE 0 END) AS ct_cases,
    SUM(CASE WHEN e.modality_code = 'CR' THEN 1 ELSE 0 END) AS xr_cases,
    SUM(CASE WHEN e.modality_code = 'US' THEN 1 ELSE 0 END) AS us_cases,
    SUM(CASE WHEN e.modality_code = 'MR' THEN 1 ELSE 0 END) AS mr_cases,
    SUM(CASE WHEN e.modality_code = 'NM' THEN 1 ELSE 0 END) AS nm_cases,
    SUM(CASE WHEN e.modality_code = 'PT' THEN 1 ELSE 0 END) AS pt_cases,
    SUM(CASE WHEN e.modality_code = 'MG' THEN 1 ELSE 0 END) AS mg_cases,
    SUM(CASE WHEN e.modality_code = 'IR' THEN 1 ELSE 0 END) AS ir_cases,
    SUM(CASE WHEN e.modality_code NOT IN ('CT', 'CR', 'US', 'MR', 'NM', 'PT', 'MG', 'IR') THEN 1 ELSE 0 END) AS other_modality_cases,
    SUM(CASE WHEN e.priority_name = 'ROUTINE' THEN 1 ELSE 0 END) AS routine_cases,
    SUM(CASE WHEN e.priority_name = 'STAT' THEN 1 ELSE 0 END) AS stat_cases,
    SUM(CASE WHEN e.priority_name = 'STROKE' THEN 1 ELSE 0 END) AS stroke_cases,
    SUM(CASE WHEN e.priority_name = 'TRAUMA' THEN 1 ELSE 0 END) AS trauma_cases,
    SUM(CASE WHEN e.priority_name NOT IN ('ROUTINE', 'STAT', 'STROKE', 'TRAUMA') THEN 1 ELSE 0 END) AS otherp_cases,
    SUM(CASE WHEN e.priority_name NOT IN ('STROKE', 'TRAUMA') AND e.modality_code != 'IR' THEN 1 ELSE 0 END) AS non_ir_stroke_trauma_cases,
    SUM(CASE WHEN e.care_setting = 'ED' THEN 1 ELSE 0 END) AS er_cases,
    SUM(CASE WHEN e.care_setting = 'Inpatient' THEN 1 ELSE 0 END) AS inpatient_cases,
    SUM(CASE WHEN e.care_setting = 'Outpatient' THEN 1 ELSE 0 END) AS outpatient_cases
  FROM with_read_time e
  GROUP BY e.npi, e.shift_date, e.shift_name, e.task_id
),
baseline_candidates AS (
  SELECT
    NPI AS npi, Task_ID AS task_id, Shift_Name AS shift_name, Shift_Length AS shift_length,
    Shift_Baseline_TBWU_2026 AS shift_baseline_tbwu_2026, Baseline_Type AS baseline_type,
    ROW_NUMBER() OVER (
      PARTITION BY NPI, UPPER(TRIM(Shift_Name))
      ORDER BY CASE Baseline_Type WHEN 'Exact' THEN 1 WHEN 'Proxy' THEN 2 ELSE 3 END
    ) AS rn
  FROM edw_test.enterprise_analytics.tbl_mosaic_baseline_master
)
SELECT
  v.npi, v.radiologist_name, v.team, v.practice, v.shift_date, v.shift_name, v.task_id, v.no_hours,
  -- RAW TOTALS only (capacity/baseline/no_hours) - NOT pre-divided into per-hour/per-9hour rates
  -- here, since SUM-of-per-row-rates != a correctly weighted rate at any grouped grain (the
  -- classic "average of rates != rate of averages" pitfall). The metric view composes
  -- Per Hour/Per 9Hour as SUM(capacity)/SUM(no_hours) [*9], same pattern as every other rate
  -- measure in this project (see mosaic_efficiency_metric_view).
  v.shift_tbwu AS on_shift_capacity_rpwu,
  v.shift_rvu AS on_shift_capacity_rvu,
  COALESCE(b_exact.shift_baseline_tbwu_2026, b_fallback.shift_baseline_tbwu_2026) / NULLIF(COALESCE(b_exact.shift_length, b_fallback.shift_length), 0) * v.no_hours AS shift_baseline_rpwu,
  COALESCE(b_exact.baseline_type, b_fallback.baseline_type) AS baseline_type,
  -- Read minutes exposed raw (not pre-divided into a per-shift rate) for the same reason as
  -- above. exams_with_valid_read_time / is_rpce_source let a consumer judge trustworthiness
  -- directly: dictation-timestamp coverage is NOT uniform (confirmed live 2026-10-22 - RASF
  -- 99.97% missing, RP Valley 88.7% missing, vs. ARA/Synergy at 44%/34%). Per explicit
  -- confirmation: these are non-RPCE practices whose timestamp data is not reliable - RPCE-source
  -- practices (Source_System_Code IN rpceMidwest/rpceSouthwest) have the trustworthy, complete
  -- dictation timestamps this whole Adjusted_Read_Time_Sec derivation depends on. Filter to
  -- Is RPCE Source = true in the metric view (or check Pct Exams With Valid Read Time directly)
  -- before trusting Efficiency/Utilization for a non-RPCE-heavy slice.
  v.shift_read_minutes AS shift_read_minutes,
  v.exams_with_valid_read_time AS exams_with_valid_read_time,
  v.is_rpce_source = 1 AS is_rpce_source,
  v.shift_cases AS on_shift_cases,
  v.mosaic_cases, v.drafting_cases, v.captured_us_in_mosaic_cases,
  v.assigned_cases, v.autonext_cases, v.pool_cases, v.assisted_cases, v.non_ir_stroke_trauma_cases,
  v.ct_cases, v.xr_cases, v.us_cases, v.mr_cases, v.nm_cases, v.pt_cases, v.mg_cases, v.ir_cases, v.other_modality_cases,
  v.routine_cases, v.stat_cases, v.stroke_cases, v.trauma_cases, v.otherp_cases,
  v.er_cases, v.inpatient_cases, v.outpatient_cases
FROM raw_shifts v
LEFT JOIN baseline_candidates b_exact ON v.npi = b_exact.npi AND v.task_id = b_exact.task_id AND b_exact.rn = 1
LEFT JOIN baseline_candidates b_fallback
  ON v.npi = b_fallback.npi AND UPPER(TRIM(v.shift_name)) = UPPER(TRIM(b_fallback.shift_name)) AND b_fallback.rn = 1
WHERE v.practice IS NOT NULL;
