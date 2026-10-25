-- Mosaic Program (MVP) metric view. DRAFT STATUS: edw_test only - do not promote to edw_prod
-- without approval.
--
-- WHY: the Executive Dashboard's Program page and the curated Mosaic Genie space need the MVP
-- (Dynamics CRM) program state as a governed metric view, so Genie stays metric-view-only (no raw
-- tables mixed in) and the dashboard, Genie, and the app's own MVP page all read the same
-- definitions.
--
-- SOURCE: edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding - a manually re-run snapshot of
-- Dynamics rad_onboarding (013/016), one row per radiologist (NPI unique, confirmed live
-- 2026-10-24: 2,609 rows / 2,609 NPIs). No PBI counterpart exists, so parity is to the app's own
-- MVP page and the Weekly Update PDF it reproduces: the Funnel Stage / Funnel Outcome / Impact
-- Status dimensions below are a line-for-line SQL port of
-- backend/app/data/mvp_dashboard_stats.py (_stage_bucket, _is_declined_outcome,
-- compute_status_funnel, compute_impact_breakdown, the +/-100% implausible-value rule) - keep the
-- two in sync by hand. Validated by tools/mosaic_validation/validate_program.py, which runs those
-- Python functions over the same rows and diffs against this view.
--
-- Deliberately NOT included: mosaic_mentor / mosaic_mentor_status / reads_500_plus_dx_cases -
-- confirmed live 2026-10-24 to be effectively unpopulated in the snapshot (1 mentor row of 2,609;
-- mentor status all NULL; 500+ flag "No" on every row including active cohort rads), so any
-- measure on them would be misleading. Practice is Dynamics free text (not an MDM key), so this
-- view cannot be filtered by Local Region/Team alongside the other Mosaic metric views.
--
-- ADDITIVE ONLY: plain CREATE VIEW (no OR REPLACE) - fails rather than overwrite if the name
-- already exists.

CREATE VIEW edw_test.enterprise_analytics.mosaic_program_metric_view
COMMENT 'MOSAIC PROGRAM (MVP) SEMANTIC LAYER (draft, edw_test only). MVP efficiency-coaching program state from the Dynamics CRM snapshot tbl_mvp_rad_onboarding: cohort, exclusions, optimization-support funnel stage, and post-engagement impact. Definitions mirror backend/app/data/mvp_dashboard_stats.py. Efficiency-change inputs are manually populated by the deployment team in Dynamics, not computed from EDW.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding
comment: 'Mosaic MVP program (Dynamics CRM snapshot). One row per radiologist. See CREATE VIEW comment.'
dimensions:
  - name: NPI
    expr: source.npi
    display_name: Radiologist NPI
  - name: Radiologist Name
    expr: source.rad_name
  - name: Dynamics Practice
    expr: source.practice
    comment: Free-text practice label typed in Dynamics - not an MDM practice key and not the same values as Practice/Team in the other Mosaic metric views.
  - name: MVP Cohort
    expr: source.mvp_cohort
    comment: Full cohort label, e.g. Cohort 2 (Mammo). NULL = excluded before a cohort was assigned.
  - name: Cohort Wave
    expr: "REGEXP_EXTRACT(source.mvp_cohort, '^(Cohort [0-9]+)', 1)"
    comment: Cohort 1..4 without the (Mammo)/(Ops or Self Referred) suffix.
  - name: Program Track
    expr: "CASE WHEN source.mvp_cohort IS NULL THEN 'Not In A Cohort' WHEN source.mvp_cohort LIKE '%(Mammo)%' THEN 'Mammo' WHEN source.mvp_cohort LIKE '%(Ops or Self Referred)%' THEN 'Ops or Self Referred' ELSE 'Core' END"
    comment: Core = the app's MVP Overview scope (cohort assigned, not Mammo, not Ops/Self Referred); Mammo = the app's Mammo scope.
  - name: Is Actively Tracked
    expr: source.exclusion_reason IS NULL
    comment: TRUE when no exclusion reason is recorded.
  - name: Exclusion Reason
    expr: source.exclusion_reason
  - name: Optimization Support Status
    expr: source.optimization_support_status
    comment: Raw Dynamics status, e.g. 9 Closed (MVP Completed).
  - name: Funnel Stage
    expr: "CASE WHEN source.optimization_support_status IS NULL OR source.optimization_support_status = '' THEN NULL WHEN source.optimization_support_status IN ('1 Identified', '2 Confirmed') THEN NULL WHEN source.optimization_support_status LIKE '3 Outreached%' OR source.optimization_support_status LIKE '4 Outreached%' THEN '1 Outreached' WHEN source.optimization_support_status LIKE '5 Scheduled%' THEN '2 Scheduled' WHEN source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' THEN '3 Solutioning' WHEN source.optimization_support_status LIKE '8 Monitoring%' THEN '4 Monitoring' WHEN source.optimization_support_status LIKE '9 Closed%' THEN '5 Closed' ELSE NULL END"
    comment: Weekly Update funnel stage (number prefix only for sort order). NULL = not yet in the funnel (no status, 1 Identified, 2 Confirmed). Port of mvp_dashboard_stats._stage_bucket.
  - name: Funnel Outcome
    expr: "CASE WHEN source.optimization_support_status LIKE '9 Closed%' THEN CASE WHEN source.optimization_support_status LIKE '%Declined Support%' OR source.optimization_support_status LIKE '%Resigning%' OR source.optimization_support_status LIKE '%Mentor Declined%' OR source.optimization_support_status LIKE '%Not Progressing%' THEN 'Declined' ELSE 'On Track' END WHEN source.optimization_support_status LIKE '3 Outreached%' OR source.optimization_support_status LIKE '4 Outreached%' OR source.optimization_support_status LIKE '5 Scheduled%' OR source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%' THEN CASE WHEN source.optimization_support_status LIKE '%Escalated%' THEN 'Escalated' ELSE 'On Track' END ELSE NULL END"
    comment: On Track / Escalated / Declined split within each funnel stage. Port of mvp_dashboard_stats.compute_status_funnel.
  - name: Escalation Owner
    expr: "CASE source.optimization_support_status WHEN '7 Solutioning (Escalated - Mentorship)' THEN 'Mentorship' WHEN '7 Solutioning (Escalated - IT)' THEN 'IT' WHEN '7 Solutioning (Escalated - Program Specific)' THEN 'Development' ELSE NULL END"
    comment: Who owns an escalated Solutioning case. Port of mvp_dashboard_stats.compute_escalations_by_owner (Program Specific is reported as Development).
  - name: Impact Status
    expr: "CASE WHEN NOT (source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%') OR source.optimization_support_status IS NULL THEN NULL WHEN TRY_CAST(source.drafting_captured_efficiency_change_pct AS DOUBLE) IS NULL OR TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE) IS NULL OR ABS(TRY_CAST(source.drafting_captured_efficiency_change_pct AS DOUBLE)) > 100 OR ABS(TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)) > 100 THEN 'Insufficient Data' WHEN TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE) >= 0 THEN 'At Or Above Baseline' WHEN TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE) > TRY_CAST(source.drafting_captured_efficiency_change_pct AS DOUBLE) THEN 'Improving' ELSE 'Not Improving' END"
    comment: Post-engagement (Solutioning/Monitoring/Closed) radiologists only - trailing-30-day Full Mosaic change vs all-time drafting+capture change. Values beyond +/-100% are tiny-denominator artifacts and count as Insufficient Data. Port of mvp_dashboard_stats.compute_impact_breakdown.
measures:
  - name: Radiologists
    expr: COUNT(DISTINCT source.npi)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Cohort Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.mvp_cohort IS NOT NULL THEN source.npi END)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Actively Tracked Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.exclusion_reason IS NULL THEN source.npi END)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Excluded Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.exclusion_reason IS NOT NULL THEN source.npi END)
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Funnel Radiologists
    expr: "COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '3 Outreached%' OR source.optimization_support_status LIKE '4 Outreached%' OR source.optimization_support_status LIKE '5 Scheduled%' OR source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%' THEN source.npi END)"
    comment: Radiologists in the Weekly Update funnel (Outreached through Closed) - the PDF's funnel total.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Post Engagement Radiologists
    expr: "COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%' THEN source.npi END)"
    comment: Reached at least Solutioning - the population Impact Status is computed over.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Closed Completed Radiologists
    expr: "COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '9 Closed%' AND NOT (source.optimization_support_status LIKE '%Declined Support%' OR source.optimization_support_status LIKE '%Resigning%' OR source.optimization_support_status LIKE '%Mentor Declined%' OR source.optimization_support_status LIKE '%Not Progressing%') THEN source.npi END)"
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Escalated Radiologists
    expr: "COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '%Escalated%' AND (source.optimization_support_status LIKE '3 Outreached%' OR source.optimization_support_status LIKE '4 Outreached%' OR source.optimization_support_status LIKE '5 Scheduled%' OR source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%') THEN source.npi END)"
    comment: Open (not Closed) funnel cases currently escalated - same rule as Funnel Outcome = Escalated.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Median Full Mosaic L30D Change Pct
    expr: "MEDIAN(CASE WHEN ABS(TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)) <= 100 THEN TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE) / 100 END)"
    comment: Median trailing-30-day Full Mosaic efficiency change vs baseline, over radiologists with a plausible (within +/-100%) manually populated value. Not a PBI measure - Dynamics tracker figure.
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Radiologists With L30D Change
    expr: "COUNT(DISTINCT CASE WHEN ABS(TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)) <= 100 THEN source.npi END)"
    comment: Denominator behind Median Full Mosaic L30D Change Pct - always show alongside it.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Latest Dynamics Activity
    expr: "MAX(TRY_TO_TIMESTAMP(source.optimization_last_updated, 'M/d/yyyy h:mm a'))"
    comment: Most recent optimization_last_updated across the slice - a freshness signal for the manually refreshed snapshot, not a snapshot load timestamp.
$$;
