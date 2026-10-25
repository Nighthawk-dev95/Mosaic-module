-- Mosaic Efficiency vs RP Average metric view (Readtimeview.tmdl). DRAFT STATUS: edw_test only -
-- do not promote to edw_prod without approval.
--
-- Ports Readtimeview.tmdl's real business measures: RP_Avg_Efficiency / Benchmark_*_Overall (the
-- population-wide average TBWU/min per mode, over qualifying radiologists only) and
-- Efficiency_vs_RP_Avg_NB/Overall (each radiologist's own efficiency as a ratio of that average).
-- This is a DIFFERENT semantic from mosaic_efficiency_metric_view (efficiency change vs OWN
-- baseline) - deliberately a separate metric view over a separate, no-baseline-restriction
-- source (tbl_efficiency_rp_avg_source_vw, itself over the migrated
-- radiologist_metrics_minexams_rtupdatedshadow/dim_radiologist_rtupdated_shadow tables - see 024).
--
-- Same 6 modes as the main Efficiency metric view (Reporting/Drafting-CR-CT/Capture-US-BD/
-- Drafting+Capture/Full Mosaic/Both). The RP Avg side of each ratio is a FIXED, grain-independent
-- value (Fixed LOD via ANY_VALUE() over the source view's unpartitioned window columns - see that
-- view's own header comment) - it does not change whether you group by NPI, Team, or nothing.
-- The qualification threshold baked into the RP Avg population itself is a fixed >=1 exam (can't
-- be a runtime parameter - the population average must be constant at view-definition time); the
-- `min_exams` PARAMETER below only gates the INDIVIDUAL radiologist's own side of the ratio,
-- same days_back-style pattern as mosaic_volume_metric_view / mosaic_efficiency_metric_view.
--
-- Efficiency Vs RP Avg > 1 means above the company average; < 1 means below. NOT a percentage -
-- do not apply number-percent formatting (matches the real DAX: Efficiency_vs_RP_Avg_NB has no
-- "x minus 1" subtraction, unlike the main semantic's Pct Change Vs Baseline measures).

CREATE OR REPLACE VIEW edw_test.enterprise_analytics.mosaic_efficiency_vs_rp_avg_metric_view
COMMENT 'MOSAIC EFFICIENCY VS RP AVERAGE (draft, edw_test only). Governed replacement for the PBI "Mosaic Efficiency Report"''s Readtimeview.tmdl: each radiologist''s own TBWU-per-minute efficiency as a ratio of the qualifying-radiologist company-wide average, across 6 modes - a DIFFERENT semantic from mosaic_efficiency_metric_view (which compares to each radiologist''s OWN baseline, not to peers). See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw
parameters:
  - name: min_exams
    data_type: int
    default: 1
comment: 'Efficiency vs RP Average: each radiologist''s own TBWU/min as a ratio of the company-wide qualifying-radiologist average, 6 modes. Query with a `min_exams` argument to require that many all-time exams in-mode before an INDIVIDUAL radiologist counts, e.g. `SELECT `Radiologist Name`, MEASURE(`Full Mosaic Efficiency Vs RP Avg`) FROM mosaic_efficiency_vs_rp_avg_metric_view(100) GROUP BY ALL` -- omit for the default (1, everyone visible). The RP Avg side of the ratio is always computed over a fixed >=1-exam qualifying population (see source view).'
dimensions:
  - name: NPI
    expr: source.npi
    display_name: Radiologist NPI
  - name: Radiologist Name
    expr: source.radiologist_name
  - name: Team
    expr: source.team
  - name: Team Rolled Up
    expr: source.team_rolled_up
  - name: Local Region
    expr: source.local_region
  - name: Practice
    expr: source.practice
  - name: Subspecialty
    expr: source.subspecialty
  - name: Modality
    expr: source.modality_code
  - name: Parent Procedure Name
    expr: source.parent_procedure_name
  - name: Exam Category
    expr: source.exam_category
  - name: Exam Month
    expr: "DATE_TRUNC('MONTH', source.exam_date)"
    format: {type: date, date_format: year_month_day}
measures:
  # ===================== REPORTING ONLY =====================
  - name: Reporting Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Reporting Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Reporting Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Reporting Own Efficiency
    expr: "MEASURE(`Reporting Own TBWU`) / (MEASURE(`Reporting Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Reporting RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_reporting_tbwu) / (ANY_VALUE(source.rp_avg_reporting_time) / 60)"
    comment: Fixed company-wide average, constant regardless of query grouping.
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Reporting Efficiency Vs RP Avg
    expr: "MEASURE(`Reporting Own Efficiency`) / MEASURE(`Reporting RP Avg Efficiency`)"
    comment: "Ratio, not a percent change: 1.0 = exactly average, >1 = above average, <1 = below."
    format: {type: number, decimal_places: {type: max, places: 3}}
  # ===================== DRAFTING ONLY (CR/CT) =====================
  - name: Drafting Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.rad_total_drafting_cr_ct_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.rad_total_drafting_cr_ct_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Drafting Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.rad_total_drafting_cr_ct_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Own Efficiency
    expr: "MEASURE(`Drafting Own TBWU`) / (MEASURE(`Drafting Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_drafting_tbwu) / (ANY_VALUE(source.rp_avg_drafting_time) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Efficiency Vs RP Avg
    expr: "MEASURE(`Drafting Own Efficiency`) / MEASURE(`Drafting RP Avg Efficiency`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  # ===================== CAPTURE ONLY (US/BD) =====================
  - name: Capture Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.rad_total_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Capture Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.rad_total_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Capture Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.rad_total_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Capture Own Efficiency
    expr: "MEASURE(`Capture Own TBWU`) / (MEASURE(`Capture Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Capture RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_capture_tbwu) / (ANY_VALUE(source.rp_avg_capture_time) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Capture Efficiency Vs RP Avg
    expr: "MEASURE(`Capture Own Efficiency`) / MEASURE(`Capture RP Avg Efficiency`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  # ===================== DRAFTING + CAPTURE (CR/CT/US/BD) =====================
  - name: Drafting Capture Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.rad_total_drafting_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Capture Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.rad_total_drafting_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Drafting Capture Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.rad_total_drafting_capture_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Capture Own Efficiency
    expr: "MEASURE(`Drafting Capture Own TBWU`) / (MEASURE(`Drafting Capture Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Capture RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_drafting_capture_tbwu) / (ANY_VALUE(source.rp_avg_drafting_capture_time) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Capture Efficiency Vs RP Avg
    expr: "MEASURE(`Drafting Capture Own Efficiency`) / MEASURE(`Drafting Capture RP Avg Efficiency`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  # ===================== FULL MOSAIC (REPORTING + DRAFTING) =====================
  - name: Full Mosaic Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Full Mosaic Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Full Mosaic Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Full Mosaic Own Efficiency
    expr: "MEASURE(`Full Mosaic Own TBWU`) / (MEASURE(`Full Mosaic Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Full Mosaic RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_full_mosaic_tbwu) / (ANY_VALUE(source.rp_avg_full_mosaic_time) / 60)"
    comment: "The real, qualification-gated RP_Avg_Efficiency / Benchmark_FullMosaic_Only_Overall from Readtimeview.tmdl - the headline company-wide benchmark."
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Full Mosaic Efficiency Vs RP Avg
    expr: "MEASURE(`Full Mosaic Own Efficiency`) / MEASURE(`Full Mosaic RP Avg Efficiency`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  # ===================== BOTH (REPORTING + DRAFTING + BASELINE) =====================
  - name: Both Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Both Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Both Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Both Own Efficiency
    expr: "MEASURE(`Both Own TBWU`) / (MEASURE(`Both Own Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Both RP Avg Efficiency
    expr: "ANY_VALUE(source.rp_avg_both_tbwu) / (ANY_VALUE(source.rp_avg_both_time) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Both Efficiency Vs RP Avg
    expr: "MEASURE(`Both Own Efficiency`) / MEASURE(`Both RP Avg Efficiency`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
$$;
