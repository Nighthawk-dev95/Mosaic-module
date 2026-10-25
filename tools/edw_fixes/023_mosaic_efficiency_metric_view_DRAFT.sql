-- Mosaic Efficiency metric view (tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md). DRAFT
-- STATUS: edw_test only per explicit instruction - do not promote to edw_prod without approval.
--
-- Ports the real business measures from the PBI "Mosaic Efficiency Report"'s Parameter, Timeline,
-- and Mode_Lines tables (Readtimeview deliberately excluded - different semantic, different
-- no-baseline-restriction source, deferred as a follow-up). Source:
-- edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw (one row per qualifying exam,
-- already carrying each row's own-NPI-and-procedure baseline efficiency rate plus per-NPI
-- per-mode qualification flags - see that view's own header comment for the full derivation).
--
-- 6 modes, matching the PBI model's own vocabulary exactly:
--   Reporting Only, Drafting Only (CR/CT), Capture Only (US/BD), Drafting + Capture (CR/CT/US/BD),
--   Full Mosaic (Reporting+Drafting), Both (Reporting+Drafting+Baseline).
-- Per mode: Mosaic Exams, Mosaic TBWU, Mosaic Time, Mosaic Efficiency (TBWU/min), Baseline Exams,
-- Baseline Efficiency (time-weighted), Pct Change vs Baseline, Implied Read Time Savings %.
--
-- QUALIFICATION GATE (confirmed live 2026-10-22): Parameter.tmdl's Passes_Min_Exam_Opt /
-- Timeline.tmdl's 'Passes Min Exam Filter Practice' both read a UI slicer ('Mosaic Min Exams':
-- 0, 1, 5, 10, 15, 20, 30, ..., 10000) that isn't captured in the TMDL export (report-layout
-- state, not semantic-model state) - so rather than guess a hardcoded threshold, this is a real
-- metric-view PARAMETER (`min_exams`, default 1, same days_back-parameter pattern as
-- mosaic_volume_metric_view). Default 1 means "show the full dataset" (business confirmed: this
-- is the everyone-visible default; filtering to N min exams is an explicit, user-driven choice at
-- query time via `mosaic_efficiency_metric_view(min_exams)`, not a baked-in exclusion). Every
-- atomic measure is FILTER'd on `source.<mode>_exam_count >= min_exams` - at the default (1) this
-- only excludes a radiologist/grain with LITERALLY ZERO rows in that mode (a no-op against a plain
-- SUM, since zero rows already contribute zero) - the exclusion becomes real once a caller passes
-- a threshold > 1.
--
-- Baseline Efficiency uses baseline_eff_excl (the standard, all-modality baseline rate) for every
-- mode EXCEPT Capture Only, which uses baseline_usbd_eff_excl (the US/BD-specific baseline rate) -
-- matches Parameter.tmdl's Base_Baseline_Eff_Opt exactly ("Drafting + Capture... Use standard
-- baseline since it covers all modalities").
--
-- Percentage measures (Pct Change vs Baseline, Implied Read Time Savings %) return a raw fraction,
-- 0 to 1 (or negative), never pre-multiplied by 100 - matches the established enterprise_analytics
-- convention (see mosaic_volume_metric_view).

CREATE OR REPLACE VIEW edw_test.enterprise_analytics.mosaic_efficiency_metric_view
COMMENT 'MOSAIC EFFICIENCY SEMANTIC LAYER (draft, edw_test only). Governed replacement for the PBI "Mosaic Efficiency Report"''s Parameter/Timeline/Mode_Lines tables: TBWU-per-minute efficiency vs. each radiologist''s own PowerScribe baseline, across 6 modes (Reporting/Drafting/Capture/Drafting+Capture/Full Mosaic/Both), with a qualification gate (min-exams threshold + has-both-baseline-and-mosaic) baked into every measure. Readtimeview''s separate "efficiency vs RP average" semantic is explicitly NOT part of this view - see tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw
parameters:
  - name: min_exams
    data_type: int
    default: 1
comment: 'Mosaic Efficiency: TBWU-per-minute vs. own baseline, 6 modes, qualification-gated. Query with a `min_exams` argument to require that many exams in-mode before a radiologist counts toward any rollup, e.g. `SELECT Practice, MEASURE(`Full Mosaic Mosaic Efficiency`) FROM mosaic_efficiency_metric_view(1000) GROUP BY ALL` -- omit the argument to get the default (1, everyone visible). See the CREATE VIEW table comment for scope and exclusions.'
dimensions:
  - name: NPI
    expr: source.npi
    comment: Radiologist NPI.
    display_name: Radiologist NPI
  - name: Radiologist Name
    expr: source.radiologist_name
  - name: Team
    expr: source.team
    comment: "The radiologist's OWN home pool/provider practice (e.g. 'SEAL Team' is a float/cross-coverage pool, not a billing practice) - NOT the same as Practice. See Practice for the business-facing 'By Practice' grouping."
    synonyms: [Provider Practice]
  - name: Team Rolled Up
    expr: source.team_rolled_up
    comment: Team rolled up to its parent grouping via the migrated team_rollups lookup.
  - name: Local Region
    expr: source.local_region
    comment: One of 6 fixed regions (Special Operations/Apex/Genesis/Maverick/Trailblazer/Matrix), keyed on Team - matches the real DAX '0. Cur'[Local] calculated column.
  - name: Practice
    expr: source.practice
    comment: The MANAGING practice - whose exams are actually being read, regardless of which Team/pool the reading radiologist belongs to. THE business-facing "By Practice" dimension (confirmed explicitly 2026-10-22 - Team spans many Practices for cross-coverage pools like SEAL Team).
    synonyms: [Managing Practice]
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
    comment: Trend-chart grain for the Efficiency Over Time / Efficiency Change Over Time pages.
    format: {type: date, date_format: year_month_day}
measures:
  # ===================== REPORTING ONLY =====================
  - name: Reporting Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)"
    comment: Reporting-period exam count, gated by the min_exams parameter.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Reporting Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Reporting Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Reporting Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Reporting Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)"
    comment: Time-weighted baseline contribution (baseline rate x this exam's own read time); divide by Reporting Mosaic Time Sec to get the time-weighted average baseline rate.
  - name: Reporting Mosaic Efficiency
    expr: "MEASURE(`Reporting Mosaic TBWU`) / (MEASURE(`Reporting Mosaic Time Sec`) / 60)"
    comment: TBWU per minute, Reporting-period exams only.
    display_name: Reporting Mosaic Efficiency
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Reporting Baseline Efficiency
    expr: "MEASURE(`Reporting Baseline Contrib`) / MEASURE(`Reporting Mosaic Time Sec`)"
    comment: Time-weighted average baseline TBWU/min for the same population and time window as Reporting Mosaic Efficiency.
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Reporting Pct Change Vs Baseline
    expr: "(MEASURE(`Reporting Mosaic Efficiency`) - MEASURE(`Reporting Baseline Efficiency`)) / MEASURE(`Reporting Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Reporting Implied Read Time Savings Pct
    expr: "MEASURE(`Reporting Baseline Efficiency`) / MEASURE(`Reporting Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  # ===================== DRAFTING ONLY (CR/CT) =====================
  - name: Drafting Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Drafting Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.drafting_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count >= min_exams)"
  - name: Drafting Mosaic Efficiency
    expr: "MEASURE(`Drafting Mosaic TBWU`) / (MEASURE(`Drafting Mosaic Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Baseline Efficiency
    expr: "MEASURE(`Drafting Baseline Contrib`) / MEASURE(`Drafting Mosaic Time Sec`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Pct Change Vs Baseline
    expr: "(MEASURE(`Drafting Mosaic Efficiency`) - MEASURE(`Drafting Baseline Efficiency`)) / MEASURE(`Drafting Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Drafting Implied Read Time Savings Pct
    expr: "MEASURE(`Drafting Baseline Efficiency`) / MEASURE(`Drafting Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  # ===================== CAPTURE ONLY (US/BD) =====================
  - name: Capture Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Capture Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Capture Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Capture Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Capture Baseline Contrib
    expr: "SUM(source.baseline_usbd_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    comment: Uses baseline_usbd_eff_excl (the US/BD-specific baseline rate), not the standard baseline_eff_excl - matches Parameter.tmdl's Base_Baseline_Eff_Opt for Capture Only.
  - name: Capture Mosaic Efficiency
    expr: "MEASURE(`Capture Mosaic TBWU`) / (MEASURE(`Capture Mosaic Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Capture Baseline Efficiency
    expr: "MEASURE(`Capture Baseline Contrib`) / MEASURE(`Capture Mosaic Time Sec`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Capture Pct Change Vs Baseline
    expr: "(MEASURE(`Capture Mosaic Efficiency`) - MEASURE(`Capture Baseline Efficiency`)) / MEASURE(`Capture Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Capture Implied Read Time Savings Pct
    expr: "MEASURE(`Capture Baseline Efficiency`) / MEASURE(`Capture Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  # ===================== DRAFTING + CAPTURE (CR/CT/US/BD) =====================
  - name: Drafting Capture Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Capture Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Drafting Capture Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Capture Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.drafting_capture_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Drafting Capture Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    comment: "Uses the standard baseline_eff_excl (blended across all modalities) - matches Parameter.tmdl's own comment: 'Blended baseline using both CR/CT and US/BD - use standard baseline since it covers all modalities'."
  - name: Drafting Capture Mosaic Efficiency
    expr: "MEASURE(`Drafting Capture Mosaic TBWU`) / (MEASURE(`Drafting Capture Mosaic Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Capture Baseline Efficiency
    expr: "MEASURE(`Drafting Capture Baseline Contrib`) / MEASURE(`Drafting Capture Mosaic Time Sec`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Drafting Capture Pct Change Vs Baseline
    expr: "(MEASURE(`Drafting Capture Mosaic Efficiency`) - MEASURE(`Drafting Capture Baseline Efficiency`)) / MEASURE(`Drafting Capture Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Drafting Capture Implied Read Time Savings Pct
    expr: "MEASURE(`Drafting Capture Baseline Efficiency`) / MEASURE(`Drafting Capture Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  # ===================== FULL MOSAIC (REPORTING + DRAFTING) =====================
  - name: Full Mosaic Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Full Mosaic Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Full Mosaic Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Full Mosaic Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Full Mosaic Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
  - name: Full Mosaic Mosaic Efficiency
    expr: "MEASURE(`Full Mosaic Mosaic TBWU`) / (MEASURE(`Full Mosaic Mosaic Time Sec`) / 60)"
    comment: "Company-wide / any-grain TBWU per minute across Reporting+Drafting - the real, qualification-gated equivalent of the app's existing 'RP Benchmark' tile when queried with no GROUP BY."
    display_name: Full Mosaic Mosaic Efficiency
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Full Mosaic Baseline Efficiency
    expr: "MEASURE(`Full Mosaic Baseline Contrib`) / MEASURE(`Full Mosaic Mosaic Time Sec`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Full Mosaic Pct Change Vs Baseline
    expr: "(MEASURE(`Full Mosaic Mosaic Efficiency`) - MEASURE(`Full Mosaic Baseline Efficiency`)) / MEASURE(`Full Mosaic Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Full Mosaic Implied Read Time Savings Pct
    expr: "MEASURE(`Full Mosaic Baseline Efficiency`) / MEASURE(`Full Mosaic Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  # ===================== BOTH (REPORTING + DRAFTING + BASELINE) =====================
  - name: Both Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Both Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Both Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Both Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers = 'Excluded' AND source.both_exam_count >= min_exams)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Both Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >= min_exams)"
  - name: Both Mosaic Efficiency
    expr: "MEASURE(`Both Mosaic TBWU`) / (MEASURE(`Both Mosaic Time Sec`) / 60)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Both Baseline Efficiency
    expr: "MEASURE(`Both Baseline Contrib`) / MEASURE(`Both Mosaic Time Sec`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Both Pct Change Vs Baseline
    expr: "(MEASURE(`Both Mosaic Efficiency`) - MEASURE(`Both Baseline Efficiency`)) / MEASURE(`Both Baseline Efficiency`)"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
  - name: Both Implied Read Time Savings Pct
    expr: "MEASURE(`Both Baseline Efficiency`) / MEASURE(`Both Mosaic Efficiency`) - 1"
    format: {type: percentage, decimal_places: {type: max, places: 2}}
$$;
