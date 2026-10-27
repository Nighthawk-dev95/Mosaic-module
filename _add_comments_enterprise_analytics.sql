-- Table and column comments for all edw_prod.enterprise_analytics* objects owned by
-- bhargav.narasimhan@radpartners.com. Metadata-only (no data touched) - safe to re-run.
--
-- REMOVED 2026-10-26: mosaic_version_exam_lookup, mosaic_version_exam_detail, and
-- mosaic_efficiency_detail no longer live here - migrated to edw_prod.bipa_analytics (Yaro's
-- request to keep enterprise_analytics reserved for certified/Genie-governed datasets). Their
-- comments are now in _add_comments_bipa_analytics.sql, repointed to the new location. The
-- enterprise_analytics(_ref) copies of these 3 tables were dropped the same day.

-- =========================================================================
-- enterprise_analytics_ref.mosaic_efficiency_change_by_version  (DEPRECATED)
-- =========================================================================
COMMENT ON TABLE edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version IS 'DEPRECATED (2026-10-22) - superseded by enterprise_analytics_ref.mosaic_efficiency_detail. This was the first-pass, pre-aggregated snapshot for the Efficiency Impact dashboard page; it is no longer refreshed or used by any dashboard/report. Do not use for new analysis - use mosaic_efficiency_detail instead, which supports arbitrary slicing instead of these fixed report_type cuts. Kept temporarily for reference only.';

COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.report_type IS 'Which fixed pre-aggregated report slice this row belongs to: overall, by_modality, by_practice, v1_vs_v2, top_procedure_v2, top_practice_v2, or top_radiologist_v2.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.entity IS 'The dimension value for this report_type row (e.g. a modality code for by_modality, a practice name for by_practice, a procedure name for top_procedure_v2). NULL for the overall report_type.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.version_tag IS 'Mosaic 1.0 or Mosaic 2.0.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.exams IS 'Exam count in this slice.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.rads IS 'Distinct radiologist count in this slice.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.actual_eff IS 'Actual TBWU-per-minute efficiency rate for this slice.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.baseline_eff IS 'Case-mix-weighted baseline TBWU-per-minute rate for this slice.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_change_by_version.pct_change IS '(actual_eff - baseline_eff) / baseline_eff, as a fraction (0.0566 = +5.66%).';

-- =========================================================================
-- enterprise_analytics_ref.drafting_eligible_rpids_vw  (table comment only - columns already documented)
-- =========================================================================
COMMENT ON TABLE edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw IS 'One row per RPID procedure code with a declared AI-drafting-model or capturable-category mapping (XR/MSK, US Capturable, CT Abd/Pel, CT Chest, CT Spine, DEXA Capturable, CT Head). Governed replacement for edw_prod.bipa_analytics.draftingeligiblerpids_vw, renamed 2026-09-28. This is DECLARED coverage only - a code''s absence here means unmapped, not undraftable; observed drafting behavior comes from tbl_exam_inventory.rpid_draftable_flag instead.';

-- =========================================================================
-- enterprise_analytics_ref.ref_exam_category_lookup_xwalk  (table comment already set)
-- Relocated 2026-10-26 by 047 out of enterprise_analytics (reference data, not a certified
-- dataset); the old enterprise_analytics.tbl_exam_category_lookup_xwalk was dropped the same
-- day, so these two statements must target the _ref copy or they will fail.
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk.ParentRpt IS 'Parent procedure/report code (RPID- or RAD-prefixed procedure identifier). Join key to tbl_exam_inventory.RPID_parent_code.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.ref_exam_category_lookup_xwalk.Category IS 'Canonical exam category this procedure code rolls up to (e.g. DEXA, CT, MG, US). Use this crosswalk, not an ILIKE description search, as the source of truth for Category groupings.';

-- =========================================================================
-- enterprise_analytics.tbl_mosaic_shift_utilization  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.npi IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.radiologist_name IS 'Radiologist name, Last, First format.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.practice IS 'Practice the shift was worked for.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.shift_date IS 'Calendar date of the shift, stored as an ISO-formatted (YYYY-MM-DD) string rather than a DATE type. Sorts and compares correctly as text, but cast to DATE for date arithmetic.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.utilization_pct IS 'reading_minutes / shift_total_minutes, as a fraction (0-1). The core TBWU-based read-time utilization measure for the shift.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.reading_minutes IS 'Total minutes of reading/dictation time logged during the shift.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.shift_total_minutes IS 'Scheduled length of the shift, in minutes.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.pct_mosaic_read IS 'Fraction (0-1) of the shift''s reads that were read on any Mosaic version (1.0 or 2.0) rather than a legacy/non-Mosaic platform.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mosaic_shift_utilization.pct_ai_drafted IS 'Fraction (0-1) of the shift''s Mosaic reads that had an AI draft available/used.';

-- =========================================================================
-- enterprise_analytics.tbl_mvp_rad_onboarding  (table comment already set; optimization_last_updated already commented)
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.npi IS 'Radiologist National Provider Identifier, cast to DECIMAL(10,0) from the comma-formatted Dynamics source string.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.rad_name IS 'Radiologist name as entered in Dynamics, Last, First format.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.practice IS 'Practice label as entered in Dynamics. Free text maintained by the deployment team, not an MDM practice key - do not join on this field, route through NPI instead.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.mvp_cohort IS 'MVP (efficiency-coaching) outreach cohort this radiologist was assigned to (e.g. Cohort 1, Cohort 2 (Mammo)). NULL when the radiologist was excluded from MVP entirely before a cohort was assigned - see exclusion_reason.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.exclusion_reason IS 'Free-text reason this radiologist was excluded from MVP outreach entirely (e.g. Not on RPCE, Heavy Mammo, Reads <500 dx cases/mo). NULL when the radiologist was included in a cohort.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.mvp_target_outreach_week IS 'Planned calendar week for this radiologist''s initial MVP outreach, free text from the source tracker.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.reads_500_plus_dx_cases IS 'Yes/No flag (stored as text) for whether the radiologist reads 500+ diagnostic cases per month - one of the MVP eligibility screens.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.baseline_capacity_tbwu_9h IS 'Radiologist''s baseline TBWU capacity normalized to a 9-hour shift, stored as text from the source tracker.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.full_mosaic_efficiency_change_pct IS 'All-time efficiency change vs baseline across all Mosaic reading, as a text percentage (e.g. -27 means -27%) from the source tracker. Manually populated/refreshed by the deployment team, not auto-computed.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.xr_drafting_efficiency_change_pct IS 'All-time efficiency change vs baseline, XR drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.ct_head_efficiency_change_pct IS 'All-time efficiency change vs baseline, CT Head drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.us_capture_efficiency_change_pct IS 'All-time efficiency change vs baseline, US capture only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.drafting_captured_efficiency_change_pct IS 'All-time efficiency change vs baseline, combined drafting + capture. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.efficiency_change_last_30d_pct IS 'Trailing 30-day efficiency change vs baseline, all Mosaic reading. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.full_mosaic_change_l7d_pct IS 'Trailing 7-day efficiency change vs baseline, all Mosaic reading. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.full_mosaic_change_l14d_pct IS 'Trailing 14-day efficiency change vs baseline, all Mosaic reading. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.full_mosaic_change_l30d_pct IS 'Trailing 30-day efficiency change vs baseline, all Mosaic reading. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.xr_drafting_change_l7d_pct IS 'Trailing 7-day efficiency change vs baseline, XR drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.xr_drafting_change_l14d_pct IS 'Trailing 14-day efficiency change vs baseline, XR drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.xr_drafting_change_l30d_pct IS 'Trailing 30-day efficiency change vs baseline, XR drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.ct_head_change_l7d_pct IS 'Trailing 7-day efficiency change vs baseline, CT Head drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.ct_head_change_l14d_pct IS 'Trailing 14-day efficiency change vs baseline, CT Head drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.ct_head_change_l30d_pct IS 'Trailing 30-day efficiency change vs baseline, CT Head drafting only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.us_capture_change_l7d_pct IS 'Trailing 7-day efficiency change vs baseline, US capture only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.us_capture_change_l14d_pct IS 'Trailing 14-day efficiency change vs baseline, US capture only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.us_capture_change_l30d_pct IS 'Trailing 30-day efficiency change vs baseline, US capture only. Text percentage, manually populated.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.mosaic_mentor IS 'Name of the peer mentor assigned to help this radiologist with Mosaic adoption, if any.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.mosaic_mentor_status IS 'Status of the mentor assignment/engagement for this radiologist.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.optimization_support_status IS 'Current stage of this radiologist''s 1:1 optimization-support workflow (e.g. 9 Closed (MVP Completed)).';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.optimization_support_notes IS 'Free-text notes on the optimization support engagement for this radiologist.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding.utilization_plan_notes IS 'Dated, free-text running log of optimization-session activity and efficiency-trend check-ins for this radiologist, newest entry first. Append-only notes field from the source tracker.';

-- =========================================================================
-- enterprise_analytics.tbl_seal_baseline_master  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.NPI IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Practice IS 'Practice name. KNOWN CAVEAT: for radiologists who read across multiple SEAL databases, this currently shows SEAL Team rather than their actual home practice - a known data-quality gap, not yet corrected.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Radiologist IS 'Radiologist name, Last, First [Middle] format.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Shift_Name IS 'Shift type: Onsite or Remote.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Shift_Baseline IS 'Baseline RVU-equivalent productivity rate for this shift, before TBWU conversion.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Shift_Length IS 'Shift length, in hours.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Units IS 'Unit of measure for Shift_Baseline. Currently always RVU.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Qgenda_Company_Key IS 'QGenda company/tenant identifier the shift schedule was sourced from.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Shift_Baseline_TBWU IS 'Shift_Baseline converted to TBWU (This Body Work Units) using the 2025 conversion ratio.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Conversion_Ratio_2025_local IS 'RVU-to-TBWU conversion ratio used for the 2025 figure. Currently always NULL in this table - the ratio is applied upstream and not stored here.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Shift_Baseline_TBWU_2026 IS 'Shift_Baseline_TBWU recalculated under the 2026 RVU-to-TBWU conversion ratio. Despite the column name, this is the baseline figure to use for current reporting.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Baseline_Window IS 'Historical date range this radiologist''s baseline was computed over, as free text (e.g. 2025-06-01 -> 2025-11-30).';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_baseline_master.Baseline_Type IS 'How this row''s baseline was established: Exact (computed from an exact-length shift match) or Manual Review (set by manual review when no exact match existed).';

-- =========================================================================
-- enterprise_analytics.tbl_seal_roster  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_roster.NPI IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_roster.Last_Name IS 'Radiologist last name.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_roster.First_Name IS 'Radiologist first name.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_seal_roster.Is_Active IS 'TRUE if the radiologist is an active member of the SEAL roster as of the last refresh, FALSE if removed/departed.';
