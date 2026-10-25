-- Mosaic Impact (Capacity) metric view. DRAFT STATUS: edw_test only - do not promote to
-- edw_prod without approval.
--
-- Scope (confirmed explicitly 2026-10-22): Shift Baseline, On-Shift Capacity, On-Shift
-- Efficiency, Utilization %, On-Shift Capacity vs Baseline, plus the full category case-mix
-- breakdown, baselined from the migrated tbl_mosaic_baseline_master (027) rather than a live
-- Exact/Proxy re-derivation. Deliberately OUT of scope (not requested): Rad Equivalents Created /
-- Annualized Capacity Increase (2.Top N shift Table / 3.Summary Table) - those depend on a
-- Top-N ranking slicer mechanic and an "annualize + standard rad capacity" formula not
-- recoverable from the TMDL alone (the underlying columns are plain pass-through from an opaque
-- materialized Delta table, confirmed via SHOW CREATE TABLE this session), and the user's
-- explicit list didn't include them - flag as a follow-up if wanted later.
--
-- All rate measures (Per Hour, Per 9Hour, Utilization %, Efficiency) are composed as
-- SUM(numerator)/SUM(denominator) at the metric-view layer, NOT read from a pre-divided
-- per-row column - summing per-row rates across shifts of different lengths would silently
-- give the wrong weighted average (see tbl_capacity_shift_level_vw's own header comment).
--
-- Utilization % commonly hits its 1.0 cap (~92% of shifts, confirmed live) - a known,
-- already-documented read-time/TAT inflation characteristic from upstream data (see memory:
-- upstream_readtime_island_bug), not a bug introduced here; mosaic_service.py's own
-- _CAPACITY_MEASURES_SQL applies the identical cap for the same reason.

CREATE OR REPLACE VIEW edw_test.enterprise_analytics.mosaic_capacity_metric_view
COMMENT 'MOSAIC IMPACT (CAPACITY) SEMANTIC LAYER (draft, edw_test only). Governed replacement for the PBI "Mosaic Impact Report": on-shift TBWU/RVU capacity vs. each radiologist''s own POS-adjusted baseline (from the real re-baselining pipeline''s trusted output, tbl_mosaic_baseline_master), utilization %, efficiency, and the full case-mix breakdown (modality/priority/place-of-service/mosaic-drafting-capture/assignment-method/VRA). See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_test.enterprise_analytics.tbl_capacity_shift_level_vw
comment: 'Mosaic Impact (Capacity): on-shift TBWU/RVU capacity vs. own baseline, utilization %, efficiency, case-mix. See the CREATE VIEW table comment for scope.'
dimensions:
  - name: NPI
    expr: source.npi
    display_name: Radiologist NPI
  - name: Radiologist Name
    expr: source.radiologist_name
  - name: Team
    expr: source.team
  - name: Practice
    expr: source.practice
    comment: Managing practice - see tbl_efficiency_exam_level_vw's own Team-vs-Practice note; same convention applied here.
  - name: Shift Name
    expr: source.shift_name
  - name: Shift Date
    expr: source.shift_date
    format: {type: date, date_format: year_month_day}
  - name: Shift Month
    expr: "DATE_TRUNC('MONTH', source.shift_date)"
    format: {type: date, date_format: year_month_day}
  - name: Baseline Type
    expr: source.baseline_type
    comment: "Exact/Proxy/Manual Review/NULL (no baseline matched) - from the migrated tbl_mosaic_baseline_master."
  - name: Is RPCE Source
    expr: source.is_rpce_source
    comment: "TRUE for RPCE-sourced exams (Source_System_Code IN rpceMidwest/rpceSouthwest). Generally correlates with reliable dictation timestamps, but NOT universally - confirmed live 2026-10-22 that RP Valley is ~100% RPCE-classified yet still has 88.7% missing dictation timestamps. Use Pct Exams With Valid Read Time as the authoritative per-slice trust signal, not this flag alone."
measures:
  - name: On Shift Cases
    expr: SUM(source.on_shift_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Total Hours
    expr: SUM(source.no_hours)
    format: {type: number, decimal_places: {type: max, places: 1}}
  # ===================== CAPACITY =====================
  - name: On Shift Capacity RPWU
    expr: SUM(source.on_shift_capacity_rpwu)
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: On Shift Capacity RVU
    expr: SUM(source.on_shift_capacity_rvu)
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: On Shift Capacity RPWU Per Hour
    expr: "MEASURE(`On Shift Capacity RPWU`) / MEASURE(`Total Hours`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: On Shift Capacity RPWU Per 9Hour
    expr: "MEASURE(`On Shift Capacity RPWU Per Hour`) * 9"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: On Shift Capacity RVU Per Hour
    expr: "MEASURE(`On Shift Capacity RVU`) / MEASURE(`Total Hours`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: On Shift Capacity RVU Per 9Hour
    expr: "MEASURE(`On Shift Capacity RVU Per Hour`) * 9"
    format: {type: number, decimal_places: {type: max, places: 2}}
  # ===================== BASELINE =====================
  - name: Shift Baseline RPWU
    expr: SUM(source.shift_baseline_rpwu)
    comment: "NULL-safe sum - only includes shifts with a matched baseline (Baseline Type IS NOT NULL)."
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Shift Baseline RPWU Per Hour
    expr: "MEASURE(`Shift Baseline RPWU`) / MEASURE(`Total Hours`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: Shift Baseline RPWU Per 9Hour
    expr: "MEASURE(`Shift Baseline RPWU Per Hour`) * 9"
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: Shifts With Baseline
    expr: "SUM(CASE WHEN source.baseline_type IS NOT NULL THEN 1 ELSE 0 END)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Shifts With Baseline
    expr: "MEASURE(`Shifts With Baseline`) / COUNT(1)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CAPACITY VS BASELINE =====================
  - name: On Shift Capacity Vs Baseline RPWU
    expr: "MEASURE(`On Shift Capacity RPWU`) - MEASURE(`Shift Baseline RPWU`)"
    comment: Positive = producing more than baseline; negative = less.
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: On Shift Capacity Vs Baseline RPWU Per Hour
    expr: "MEASURE(`On Shift Capacity RPWU Per Hour`) - MEASURE(`Shift Baseline RPWU Per Hour`)"
    format: {type: number, decimal_places: {type: max, places: 3}}
  - name: On Shift Above Baseline RPWU
    expr: "SUM(GREATEST(source.on_shift_capacity_rpwu - COALESCE(source.shift_baseline_rpwu, source.on_shift_capacity_rpwu), 0))"
    comment: The portion of capacity exceeding baseline, summed (0 for shifts at/under baseline or with no baseline match).
    format: {type: number, decimal_places: {type: max, places: 2}}
  - name: On Shift Up To Baseline RPWU
    expr: "SUM(LEAST(source.on_shift_capacity_rpwu, COALESCE(source.shift_baseline_rpwu, source.on_shift_capacity_rpwu)))"
    comment: The portion of capacity at/under baseline, summed - pairs with On Shift Above Baseline RPWU for a stacked view.
    format: {type: number, decimal_places: {type: max, places: 2}}
  # ===================== UTILIZATION & EFFICIENCY =====================
  - name: Read Minutes
    expr: SUM(source.shift_read_minutes)
    format: {type: number, decimal_places: {type: max, places: 1}}
  - name: Exams With Valid Read Time
    expr: SUM(source.exams_with_valid_read_time)
    comment: "Count of exams with usable dictation timestamps (start/end/final all present) - the population Read Minutes/Efficiency/Utilization are actually computed over."
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Exams With Valid Read Time
    expr: "MEASURE(`Exams With Valid Read Time`) / MEASURE(`On Shift Cases`)"
    comment: "ALWAYS CHECK THIS before trusting On Shift Efficiency/Utilization for a slice - coverage varies enormously by practice (confirmed live: from 0.03% to 66%+), independent of the Is RPCE Source flag."
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: On Shift Utilization Pct
    expr: "LEAST(MEASURE(`Read Minutes`) / (MEASURE(`Total Hours`) * 60), 1.0)"
    comment: "Capped at 100% - see this view's header comment for why the cap is hit so often."
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: On Shift Efficiency RPWU
    expr: "MEASURE(`On Shift Capacity RPWU`) / MEASURE(`Read Minutes`)"
    comment: TBWU per read-minute.
    format: {type: number, decimal_places: {type: max, places: 4}}
  - name: On Shift Efficiency RVU
    expr: "MEASURE(`On Shift Capacity RVU`) / MEASURE(`Read Minutes`)"
    format: {type: number, decimal_places: {type: max, places: 4}}
  # ===================== CASE MIX: MODALITY =====================
  - name: CT Cases
    expr: SUM(source.ct_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct CT Of Shift
    expr: "MEASURE(`CT Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: XR Cases
    expr: SUM(source.xr_cases)
    comment: "Plain film is 'CR' in the source modality code, labeled XR here for display - same convention as the Volume metric view."
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct XR Of Shift
    expr: "MEASURE(`XR Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: US Cases
    expr: SUM(source.us_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct US Of Shift
    expr: "MEASURE(`US Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: MR Cases
    expr: SUM(source.mr_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct MR Of Shift
    expr: "MEASURE(`MR Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: NM Cases
    expr: SUM(source.nm_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct NM Of Shift
    expr: "MEASURE(`NM Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: PT Cases
    expr: SUM(source.pt_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct PT Of Shift
    expr: "MEASURE(`PT Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: MG Cases
    expr: SUM(source.mg_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct MG Of Shift
    expr: "MEASURE(`MG Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: IR Cases
    expr: SUM(source.ir_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct IR Of Shift
    expr: "MEASURE(`IR Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Other Modality Cases
    expr: SUM(source.other_modality_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Other Modality Of Shift
    expr: "MEASURE(`Other Modality Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CASE MIX: PRIORITY =====================
  - name: Routine Cases
    expr: SUM(source.routine_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Routine Of Shift
    expr: "MEASURE(`Routine Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Stat Cases
    expr: SUM(source.stat_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Stat Of Shift
    expr: "MEASURE(`Stat Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Stroke Cases
    expr: SUM(source.stroke_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Stroke Of Shift
    expr: "MEASURE(`Stroke Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Trauma Cases
    expr: SUM(source.trauma_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Trauma Of Shift
    expr: "MEASURE(`Trauma Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: OtherP Cases
    expr: SUM(source.otherp_cases)
    comment: Priority values outside Routine/Stat/Stroke/Trauma.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct OtherP Of Shift
    expr: "MEASURE(`OtherP Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CASE MIX: PLACE OF SERVICE =====================
  - name: ER Cases
    expr: SUM(source.er_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct ER Of Shift
    expr: "MEASURE(`ER Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Inpatient Cases
    expr: SUM(source.inpatient_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Inpatient Of Shift
    expr: "MEASURE(`Inpatient Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Outpatient Cases
    expr: SUM(source.outpatient_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Outpatient Of Shift
    expr: "MEASURE(`Outpatient Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CASE MIX: MOSAIC / DRAFTING / CAPTURE =====================
  - name: Mosaic Cases
    expr: SUM(source.mosaic_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Mosaic Of Shift
    expr: "MEASURE(`Mosaic Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Mosaic Drafting Cases
    expr: SUM(source.drafting_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Mosaic Drafting Of Shift
    expr: "MEASURE(`Mosaic Drafting Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Captured US In Mosaic Cases
    expr: SUM(source.captured_us_in_mosaic_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Captured US In Mosaic Of Shift
    expr: "MEASURE(`Captured US In Mosaic Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CASE MIX: ASSIGNMENT METHOD =====================
  - name: Assigned Cases
    expr: SUM(source.assigned_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Assigned Of Shift
    expr: "MEASURE(`Assigned Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Pool Cases
    expr: SUM(source.pool_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Pool Of Shift
    expr: "MEASURE(`Pool Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Autonext Cases
    expr: SUM(source.autonext_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct Autonext Of Shift
    expr: "MEASURE(`Autonext Cases`) / MEASURE(`On Shift Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  # ===================== CASE MIX: VRA ASSISTED =====================
  - name: VRA Assisted Cases
    expr: SUM(source.assisted_cases)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Non IR Stroke Trauma Cases
    expr: SUM(source.non_ir_stroke_trauma_cases)
    comment: Denominator for Pct VRA Assisted, matching the real DAX formula exactly (not On Shift Cases).
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Pct VRA Assisted
    expr: "MEASURE(`VRA Assisted Cases`) / MEASURE(`Non IR Stroke Trauma Cases`)"
    format: {type: percentage, decimal_places: {type: max, places: 1}}
$$;
