-- Table and column comments for all edw_prod.enterprise_analytics* objects owned by
-- bhargav.narasimhan@radpartners.com. Metadata-only (no data touched) - safe to re-run.

-- =========================================================================
-- enterprise_analytics.mosaic_version_exam_lookup
-- =========================================================================
COMMENT ON TABLE edw_prod.enterprise_analytics.mosaic_version_exam_lookup IS 'Base, append-only lookup of which Mosaic reporting platform version (1.0 vs 2.0) processed each exam, one row per accession number. Synced from the raw AWS radpair_instance/CloudWatch logs (rp-prod = Mosaic 1.0, rp-mg = Mosaic 2.0) via tools/mosaic_version_pipeline/sync_exam_lookup.py, run manually (not scheduled). Only covers exams logged from the Mosaic 2.0 go-live (2026-07-28) onward. This is the raw feed; enterprise_analytics_ref.mosaic_version_exam_detail is the enriched, dashboard-facing version (adds practice/Local/radiologist name) and should be used for reporting instead of this table directly.';

COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.accession_number IS 'Exam accession number. Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.accession_number.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.mosaic_version IS 'Which Mosaic reporting platform version processed this exam: Mosaic 1.0 or Mosaic 2.0, derived from the radpair_instance value in the raw AWS log (rp-prod = 1.0, rp-mg = 2.0).';
COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.npi IS 'Reading radiologist National Provider Identifier, stored as a string.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.enterprise_analytics.mosaic_version_exam_lookup.log_date IS 'Calendar date this exam was logged/processed in AWS; used as the exam date for version-adoption tracking.';

-- =========================================================================
-- enterprise_analytics_ref.mosaic_version_exam_detail
-- =========================================================================
COMMENT ON TABLE edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail IS 'Enriched, dashboard-facing version of enterprise_analytics.mosaic_version_exam_lookup: joins in the exam''s provider (reading) practice, its fixed Local grouping (via enterprise_analytics.practice_to_local_mapping in edw_dev), and the reading radiologist''s name. One row per accession number. Powers the Mosaic Reporting Version Adoption Lakeview dashboard and the post-go-live version tagging used by mosaic_efficiency_detail. Only covers exams from the Mosaic 2.0 go-live (2026-07-28) onward.';

COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.accession_number IS 'Exam accession number. Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.accession_number and enterprise_analytics.mosaic_version_exam_lookup.accession_number.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.log_date IS 'Calendar date this exam was logged/processed; used as the exam date for version-adoption tracking.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.npi IS 'Reading radiologist National Provider Identifier, stored as a string.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.radiologist_name IS 'Reading radiologist full name, resolved from NPI.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.practice IS 'Provider (reading) practice for this exam - NOT the managing practice. Resolved from tbl_exam_inventory.provider_local_practice_name_curr.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.local IS 'One of the 6 fixed Local groupings (Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix), resolved via the authoritative practice_to_local_mapping table. Value is Unmapped when the practice has no mapping yet.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.mosaic_version IS 'Which Mosaic reporting platform version processed this exam: Mosaic 1.0 or Mosaic 2.0.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.is_v2 IS 'Convenience flag: 1 when mosaic_version = Mosaic 2.0, else 0. Lets adoption-rate measures use SUM(is_v2)/COUNT(*) instead of a CASE expression.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_version_exam_detail.npi_v2 IS 'Reading radiologist NPI repeated here only when mosaic_version = Mosaic 2.0, else NULL. Convenience column for COUNT(DISTINCT npi_v2) without a CASE expression.';

-- =========================================================================
-- enterprise_analytics_ref.mosaic_efficiency_detail
-- =========================================================================
COMMENT ON TABLE edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail IS 'Fine-grain efficiency-change dataset powering the Efficiency Impact page of the Mosaic Reporting Version Adoption dashboard. One row per (radiologist, practice, procedure, modality, Mosaic version, exam date) group, already restricted to the Drafting/Reporting periods with outliers excluded - Baseline-period rows are consumed only to compute each radiologist''s own case-mix-weighted baseline rate (weighted_baseline_contrib) and are not emitted as rows here. Outlier rule: a reading is excluded when Adjusted_Read_Time_Sec < 1 second or > the 99th percentile of Adjusted_Read_Time_Sec for its Clinical_Procedure_Code. Efficiency = TBWU per minute of read time. Rebuilt from edw_dev.bipa_analytics.presentation_rpt_readtimeswith_draftingadjustedrt_tbl via _materialize_efficiency_detail.sql (point-in-time snapshot, re-run manually, not scheduled).';

COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.physician_npi IS 'Reading radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.radiologist_name IS 'Reading radiologist full name.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.practice IS 'Provider (reading) practice for these exams - NOT the managing practice.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.local IS 'One of the 6 fixed Local groupings, resolved via practice_to_local_mapping. Unmapped when the practice has no mapping yet.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.procedure_name IS 'Parent procedure name (Parent_Procedure_name), the case-mix key this radiologist''s baseline is computed against.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.mosaic_version IS 'Mosaic 1.0 or Mosaic 2.0. Every row in this table already has a resolved version tag - Baseline-period, pre-launch, and unmatched rows are excluded upstream, so there is no NULL/other value to filter out.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.exam_date IS 'Calendar date of the exam (DATE(Dictation_Start)).';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.total_time_sec IS 'Summed Adjusted_Read_Time_Sec (reading/dictation seconds) across all exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.total_tbwu IS 'Summed RP_TBWU (This Body Work Units) across all exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.exam_count IS 'Number of distinct exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.enterprise_analytics_ref.mosaic_efficiency_detail.weighted_baseline_contrib IS 'This radiologist''s own historical baseline efficiency rate for this procedure (TBWU per minute, computed from their Baseline-period/outlier-excluded reads only) multiplied by total_time_sec. To get the case-mix-weighted baseline rate for any slice: SUM(weighted_baseline_contrib) / SUM(total_time_sec). Compare against the actual rate SUM(total_tbwu) / (SUM(total_time_sec)/60.0) to compute pct_change = (actual - baseline) / baseline. This is the core building block for every efficiency-change KPI on the dashboard.';

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
-- enterprise_analytics.tbl_exam_category_lookup_xwalk  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk.ParentRpt IS 'Parent procedure/report code (RPID- or RAD-prefixed procedure identifier). Join key to tbl_exam_inventory.RPID_parent_code.';
COMMENT ON COLUMN edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk.Category IS 'Canonical exam category this procedure code rolls up to (e.g. DEXA, CT, MG, US). Use this crosswalk, not an ILIKE description search, as the source of truth for Category groupings.';

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
