-- Table and column comments for owned objects in edw_dev.enterprise_analytics and
-- edw_test.enterprise_analytics. Metadata-only (no data touched) - safe to re-run.
-- Scope: only objects where table_owner = bhargav.narasimhan@radpartners.com.
-- Excludes the 5 METRIC_VIEW objects in edw_test (mosaic_capacity_metric_view,
-- mosaic_efficiency_metric_view, mosaic_efficiency_vs_rp_avg_metric_view,
-- mosaic_resident_utilization_metric_view, mosaic_volume_metric_view) - those carry
-- comments inside their YAML definition (dimensions/measures), not via COMMENT ON
-- COLUMN, and are a draft, in-progress object type handled separately.

-- =========================================================================
-- edw_dev.enterprise_analytics.practice_to_local_mapping
-- =========================================================================
COMMENT ON TABLE edw_dev.enterprise_analytics.practice_to_local_mapping IS 'Authoritative practice-to-Local mapping, sourced from Practice_to_Local_Mapping.xlsx (maintained by the business, not derived from any EDW column). The single source of truth for the Local dimension everywhere else in enterprise_analytics - do not use edw_prod''s managing_local_name_curr column for this, it is unreliable. One row per practice.';
COMMENT ON COLUMN edw_dev.enterprise_analytics.practice_to_local_mapping.practice IS 'Short practice code/name, the join key used by downstream tables (e.g. mosaic_version_exam_detail.practice, mosaic_efficiency_detail.practice).';
COMMENT ON COLUMN edw_dev.enterprise_analytics.practice_to_local_mapping.practice_long_name IS 'Full display name of the practice.';
COMMENT ON COLUMN edw_dev.enterprise_analytics.practice_to_local_mapping.local IS 'One of the 6 fixed Local groupings: Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix.';

-- =========================================================================
-- edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw.ad_group_added_date IS 'Earliest AD-group-added date across any drafting model for this NPI.';
COMMENT ON COLUMN edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw.training_sent_date IS 'Earliest drafting-training-sent date across any drafting model for this NPI.';
COMMENT ON COLUMN edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw.training_completed_date IS 'Earliest drafting-training-completed date across any drafting model for this NPI.';
COMMENT ON COLUMN edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw.drafting_enabled_flag IS 'TRUE if this radiologist is enabled (signed IRB, completed training, added to AD group) for ANY drafting model.';
COMMENT ON COLUMN edw_test.enterprise_analytics.dynamics_rad_drafting_enablement_by_npi_vw.mosaic_drafting_consent IS 'Rad-level Mosaic drafting consent (IRB) status, same values/definition as the source dynamics_rad_drafting_consent_vw.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_capacity_shift_level_vw
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.radiologist_name IS 'Radiologist full name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.team IS 'Radiologist''s own home pool/provider practice (e.g. SEAL Team is a float/cross-coverage pool, not a billing practice) - not the same as practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.practice IS 'Managing practice - whose exams are actually being read during this shift, regardless of which team/pool the reading radiologist belongs to.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.shift_date IS 'Calendar date of the shift.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.no_hours IS 'Scheduled length of the shift, in hours.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.on_shift_capacity_rpwu IS 'Capacity actually delivered during this shift, in RPWU (RVU-based productivity units). NULL when no exams with valid read time exist for the shift.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.on_shift_capacity_rvu IS 'Capacity actually delivered during this shift, in raw RVU. NULL when no exams with valid read time exist for the shift.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.shift_baseline_rpwu IS 'This radiologist''s POS-adjusted baseline RPWU for a shift of this type/length, matched from tbl_mosaic_baseline_master. NULL when no matching baseline exists yet.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.baseline_type IS 'How shift_baseline_rpwu was matched (e.g. Exact shift-type/length match). NULL when no baseline match exists.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.shift_read_minutes IS 'Total reading/dictation minutes logged during the shift.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.exams_with_valid_read_time IS 'Count of exams in this shift with a usable (non-null, non-zero) read time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.is_rpce_source IS 'TRUE when this shift''s case counts came from the RPCE (reporting coverage engine) source rather than a fallback source.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.on_shift_cases IS 'Total exam count read during this shift.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.mosaic_cases IS 'Of on_shift_cases, how many were read on any Mosaic version.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.drafting_cases IS 'Of mosaic_cases, how many had AI drafting applied.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.captured_us_in_mosaic_cases IS 'Of mosaic_cases, how many were US (ultrasound) capture exams.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.assigned_cases IS 'Of on_shift_cases, how many were assigned directly to this radiologist rather than pulled from a pool or AutoNext.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.autonext_cases IS 'Of on_shift_cases, how many were picked up via AutoNext auto-assignment.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.pool_cases IS 'Of on_shift_cases, how many came from a shared pool rather than direct assignment.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.assisted_cases IS 'Of on_shift_cases, how many were VRA (virtual radiology assistant)-assisted.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.non_ir_stroke_trauma_cases IS 'Of on_shift_cases, how many were routine cases (excludes IR, stroke, and trauma cases).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.ct_cases IS 'Of on_shift_cases, modality breakdown: CT exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.xr_cases IS 'Of on_shift_cases, modality breakdown: XR exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.us_cases IS 'Of on_shift_cases, modality breakdown: US exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.mr_cases IS 'Of on_shift_cases, modality breakdown: MR exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.nm_cases IS 'Of on_shift_cases, modality breakdown: NM exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.pt_cases IS 'Of on_shift_cases, modality breakdown: PET exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.mg_cases IS 'Of on_shift_cases, modality breakdown: MG (mammography) exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.ir_cases IS 'Of on_shift_cases, modality breakdown: IR (interventional) exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.other_modality_cases IS 'Of on_shift_cases, exam count for modalities outside the named CT/XR/US/MR/NM/PT/MG/IR breakdown.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.routine_cases IS 'Of on_shift_cases, priority breakdown: routine-priority exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.stat_cases IS 'Of on_shift_cases, priority breakdown: STAT-priority exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.stroke_cases IS 'Of on_shift_cases, clinical-priority breakdown: stroke-protocol exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.trauma_cases IS 'Of on_shift_cases, clinical-priority breakdown: trauma-protocol exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.otherp_cases IS 'Of on_shift_cases, clinical-priority breakdown: exam count outside the named routine/stat/stroke/trauma priorities.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.er_cases IS 'Of on_shift_cases, place-of-service breakdown: emergency-room exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.inpatient_cases IS 'Of on_shift_cases, place-of-service breakdown: inpatient exam count.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_capacity_shift_level_vw.outpatient_cases IS 'Of on_shift_cases, place-of-service breakdown: outpatient exam count.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.team_rolled_up IS 'Team rolled up to its parent grouping via the migrated team_rollups lookup.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.local_region IS 'One of the 6 fixed Local regions (Special Operations/Apex/Genesis/Maverick/Trailblazer/Matrix), keyed on team.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.exam_category IS 'Canonical exam category from tbl_exam_category_lookup_xwalk (e.g. US Capturable, CT Abd/Pel).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.exam_date IS 'Calendar date of the exam.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.period_type IS 'Baseline, Drafting, or Reporting - which stage of Mosaic adoption this exam was read in.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.outliers IS 'Excluded or Included - whether this exam''s read time was excluded as a statistical outlier. Only Excluded rows feed efficiency measures.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.adjusted_read_time_sec IS 'Reading/dictation time for this exam, in seconds.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.baseline_eff_excl IS 'This radiologist''s own historical baseline TBWU-per-minute rate for this procedure (Baseline period, outliers excluded) - the comparison point for efficiency-change measures.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.baseline_usbd_eff_excl IS 'Same as baseline_eff_excl but computed on the US/BD (ultrasound/bone density) modality subset only - used for Capture-mode efficiency comparisons.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.reporting_exam_count IS 'This radiologist''s qualifying exam count for the Reporting-mode efficiency measures - gates whether they clear the min-exams qualification threshold.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.drafting_exam_count IS 'This radiologist''s qualifying exam count for the Drafting-mode efficiency measures - gates the min-exams qualification threshold.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.capture_exam_count IS 'This radiologist''s qualifying exam count for the Capture-mode efficiency measures - gates the min-exams qualification threshold.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.drafting_capture_exam_count IS 'This radiologist''s qualifying exam count for the Drafting+Capture-mode efficiency measures - gates the min-exams qualification threshold.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.full_mosaic_exam_count IS 'This radiologist''s qualifying exam count for the Full Mosaic-mode efficiency measures - gates the min-exams qualification threshold.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw.both_exam_count IS 'This radiologist''s qualifying exam count for the Both-mode (broadest) efficiency measures - gates the min-exams qualification threshold.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.npi IS 'Reading radiologist National Provider Identifier (NPI).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.radiologist_name IS 'Radiologist full name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.team IS 'Radiologist''s own home pool/provider practice - not the same as practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.team_rolled_up IS 'Team rolled up to its parent grouping via the migrated team_rollups lookup.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.local_region IS 'One of the 6 fixed Local regions (Special Operations/Apex/Genesis/Maverick/Trailblazer/Matrix), keyed on team.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.practice IS 'Managing practice - whose exams are actually being read, regardless of which team/pool the reading radiologist belongs to.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.subspecialty IS 'Radiologist''s primary working subspecialty.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.modality_code IS 'Exam modality code.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.parent_procedure_name IS 'Parent procedure name/code (RPID-based).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.exam_category IS 'Canonical exam category from tbl_exam_category_lookup_xwalk.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.exam_date IS 'Calendar date of the exam.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.period_type IS 'Baseline, Drafting, or Reporting - which stage of Mosaic adoption this exam was read in.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.outliers IS 'Excluded or Included - whether this exam''s read time was excluded as a statistical outlier.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.tbwu IS 'TBWU (This Body Work Units) for this exam.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.time_sec IS 'Reading/dictation time for this exam, in seconds.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.exam_count IS 'Exam count for this row''s grouping (always 1 at the exam grain, present for consistent aggregation).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_reporting_all_excl IS 'This radiologist''s total qualifying exam count across all Reporting-mode exams (outliers excluded), independent of any single row''s filters.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_drafting_cr_ct_all_excl IS 'This radiologist''s total qualifying exam count across all Drafting-mode CR/CT exams (outliers excluded).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_capture_all_excl IS 'This radiologist''s total qualifying exam count across all Capture-mode (US/BD) exams (outliers excluded).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_drafting_capture_all_excl IS 'This radiologist''s total qualifying exam count across all Drafting+Capture-mode exams (outliers excluded).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_full_mosaic_all_excl IS 'This radiologist''s total qualifying exam count across all Full-Mosaic-mode exams (outliers excluded).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rad_total_both_all_excl IS 'This radiologist''s total qualifying exam count across the broadest (Both-mode) exam population (outliers excluded).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_reporting_tbwu IS 'Company-wide average TBWU per qualifying Reporting-mode exam, precomputed and repeated on every row (grain-independent).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_reporting_time IS 'Company-wide average read time (seconds) per qualifying Reporting-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_drafting_tbwu IS 'Company-wide average TBWU per qualifying Drafting-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_drafting_time IS 'Company-wide average read time (seconds) per qualifying Drafting-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_capture_tbwu IS 'Company-wide average TBWU per qualifying Capture-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_capture_time IS 'Company-wide average read time (seconds) per qualifying Capture-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_drafting_capture_tbwu IS 'Company-wide average TBWU per qualifying Drafting+Capture-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_drafting_capture_time IS 'Company-wide average read time (seconds) per qualifying Drafting+Capture-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_full_mosaic_tbwu IS 'Company-wide average TBWU per qualifying Full-Mosaic-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_full_mosaic_time IS 'Company-wide average read time (seconds) per qualifying Full-Mosaic-mode exam, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_both_tbwu IS 'Company-wide average TBWU per qualifying exam across the broadest (Both-mode) population, precomputed and repeated on every row.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw.rp_avg_both_time IS 'Company-wide average read time (seconds) per qualifying exam across the broadest (Both-mode) population, precomputed and repeated on every row.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_exam_category_lookup_xwalk  (test-schema copy, table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_exam_category_lookup_xwalk.ParentRpt IS 'Parent procedure/report code (RPID- or RAD-prefixed procedure identifier).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_exam_category_lookup_xwalk.Category IS 'Canonical exam category this procedure code rolls up to (e.g. DEXA, CT, MG, US).';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_mosaic_baseline_master  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.NPI IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Practice IS 'Practice name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Radiologist IS 'Radiologist name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Name IS 'Canonical shift type name this baseline applies to.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Length IS 'Shift length, in hours, this baseline was computed for.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Count IS 'Number of historical shifts of this type/length used to compute the baseline.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Baseline IS 'Baseline productivity rate for this (NPI, shift type) pair, pre-TBWU-conversion.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Units IS 'Unit of measure for Shift_Baseline.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Prevalence IS 'How common this shift type is for this radiologist historically, used to judge whether this baseline is representative.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Target IS 'Target productivity level for this shift type, used as a reference alongside Shift_Baseline.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Data_Time_Range IS 'Historical date range (free text) this baseline was computed over.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Task_ID IS 'Source QGenda shift/task identifier used to compute this baseline.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Baseline_Type IS 'How this row''s baseline was established (e.g. Exact match).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Shift_Baseline_TBWU_2026 IS 'Shift_Baseline converted to TBWU under the 2026 (current) RVU-to-TBWU conversion ratio. Use this, not Shift_Baseline, for current-reporting comparisons.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_mosaic_baseline_master.Matched_Shift_Name IS 'The actual historical shift name this radiologist''s shift was matched against when an exact Shift_Name match was not available.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Physician_NPI IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Radiologist IS 'Radiologist name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Team IS 'Radiologist''s own home pool/provider practice - not the same as Practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Practice IS 'Managing practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_Drafting_ExclOutliers IS 'This radiologist''s total Drafting-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_Drafting_InclOutliers IS 'This radiologist''s total Drafting-mode exam count including outliers, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_Reporting_ExclOutliers IS 'This radiologist''s total Reporting-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_Reporting_InclOutliers IS 'This radiologist''s total Reporting-mode exam count including outliers, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_FullMosaic_ExclOutliers IS 'This radiologist''s total Full-Mosaic-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_dim_radiologist_shadow.Rad_Total_FullMosaic_InclOutliers IS 'This radiologist''s total Full-Mosaic-mode exam count including outliers, across all time.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Radiologist IS 'Radiologist name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Physician_NPI IS 'Radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Team IS 'Radiologist''s own home pool/provider practice - not the same as Practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Parent_Procedure_name IS 'Parent procedure name/code (RPID-based).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Practice IS 'Managing practice.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Location_Name IS 'Reading location name.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.working_subspecialty IS 'Radiologist''s primary working subspecialty.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Place_of_Service IS 'Place-of-service code for the exam (e.g. inpatient, outpatient, ER).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Priority_Description IS 'Exam priority (e.g. routine, STAT).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Modality_Code IS 'Exam modality code.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Interventional_Flag IS '1 if this was an interventional-radiology exam, else 0.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Exam_Date IS 'Calendar date of the exam.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Exam_Category IS 'Canonical exam category from the exam category crosswalk.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.mpcat IS 'Source modality/procedure category code (pre-canonical-category mapping).';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.mpproc IS 'Source modality/procedure code (RPID), pre-parent-procedure resolution.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.vra_assisted_flag IS '1 if this exam was VRA (virtual radiology assistant)-assisted, else 0.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Outliers IS 'Excluded or Included - whether this exam''s read time was excluded as a statistical outlier.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Period_Type IS 'Baseline, Drafting, or Reporting - which stage of Mosaic adoption this exam was read in.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.TotalTime IS 'Reading/dictation time for this exam grouping, in seconds.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.TotalRVU IS 'Summed RVU for this exam grouping.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.TotalTBWU IS 'Summed TBWU (This Body Work Units) for this exam grouping.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.ExamCount IS 'Number of exams in this grouping.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_Drafting_ExclOutliers IS 'This radiologist''s total Drafting-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_Drafting_InclOutliers IS 'This radiologist''s total Drafting-mode exam count including outliers, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_Reporting_ExclOutliers IS 'This radiologist''s total Reporting-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_Reporting_InclOutliers IS 'This radiologist''s total Reporting-mode exam count including outliers, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_FullMosaic_ExclOutliers IS 'This radiologist''s total Full-Mosaic-mode exam count with outliers excluded, across all time.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_readtime_radiologist_metrics_shadow.Rad_Total_FullMosaic_InclOutliers IS 'This radiologist''s total Full-Mosaic-mode exam count including outliers, across all time.';

-- =========================================================================
-- edw_test.enterprise_analytics.tbl_team_rollups  (table comment already set)
-- =========================================================================
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_team_rollups.Team IS 'QGenda Team name, the fine-grain practice/pool key used throughout the efficiency and capacity views.';
COMMENT ON COLUMN edw_test.enterprise_analytics.tbl_team_rollups.Team_Roll_Up IS 'Parent grouping (KS label) this Team rolls up to.';
