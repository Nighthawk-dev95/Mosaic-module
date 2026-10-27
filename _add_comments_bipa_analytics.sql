-- Table and column comments for the 3 tables migrated from edw_prod.enterprise_analytics(_ref)
-- to edw_prod.bipa_analytics (2026-10-26), so Genie readability isn't lost just because the
-- schema changed. Same comment text as the enterprise_analytics(_ref) originals, repointed.

COMMENT ON TABLE edw_prod.bipa_analytics.mosaic_version_exam_lookup IS 'Base, append-only lookup of which Mosaic reporting platform version (1.0 vs 2.0) processed each exam, one row per accession number. Synced from the raw AWS radpair_instance/CloudWatch logs (rp-prod = Mosaic 1.0, rp-mg = Mosaic 2.0) via tools/mosaic_version_pipeline/sync_exam_lookup.py, run manually (not scheduled). Only covers exams logged from the Mosaic 2.0 go-live (2026-07-28) onward. This is the raw feed - bipa_analytics.mosaic_version_exam_detail is the enriched, dashboard-facing version (adds practice/Local/radiologist name) and should be used for reporting instead of this table directly.';

COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.accession_number IS 'Exam accession number. Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.accession_number.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.mosaic_version IS 'Which Mosaic reporting platform version processed this exam: Mosaic 1.0 or Mosaic 2.0, derived from the radpair_instance value in the raw AWS log (rp-prod = 1.0, rp-mg = 2.0).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.npi IS 'Reading radiologist National Provider Identifier, stored as a string.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_lookup.log_date IS 'Calendar date this exam was logged/processed in AWS, used as the exam date for version-adoption tracking.';

COMMENT ON TABLE edw_prod.bipa_analytics.mosaic_version_exam_detail IS 'Enriched, dashboard-facing version of bipa_analytics.mosaic_version_exam_lookup: joins in the exam''s provider (reading) practice, its fixed Local grouping (via enterprise_analytics.practice_to_local_mapping in edw_dev), and the reading radiologist''s name. One row per accession number. Powers the Mosaic Reporting Version Adoption Lakeview dashboard and the post-go-live version tagging used by mosaic_efficiency_detail. Only covers exams from the Mosaic 2.0 go-live (2026-07-28) onward.';

COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.accession_number IS 'Exam accession number. Join key to edw_prod.enterprise_analytics.tbl_exam_inventory.accession_number and bipa_analytics.mosaic_version_exam_lookup.accession_number.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.log_date IS 'Calendar date this exam was logged/processed, used as the exam date for version-adoption tracking.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.npi IS 'Reading radiologist National Provider Identifier, stored as a string.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.radiologist_name IS 'Reading radiologist full name, resolved from NPI.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.practice IS 'Provider (reading) practice for this exam - NOT the managing practice. Resolved from tbl_exam_inventory.provider_local_practice_name_curr.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.local IS 'One of the 6 fixed Local groupings (Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix), resolved via the authoritative practice_to_local_mapping table. Value is Unmapped when the practice has no mapping yet.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.mosaic_version IS 'Which Mosaic reporting platform version processed this exam: Mosaic 1.0 or Mosaic 2.0.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.is_v2 IS 'Convenience flag: 1 when mosaic_version = Mosaic 2.0, else 0. Lets adoption-rate measures use SUM(is_v2)/COUNT(*) instead of a CASE expression.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_version_exam_detail.npi_v2 IS 'Reading radiologist NPI repeated here only when mosaic_version = Mosaic 2.0, else NULL. Convenience column for COUNT(DISTINCT npi_v2) without a CASE expression.';

COMMENT ON TABLE edw_prod.bipa_analytics.mosaic_efficiency_detail IS 'Fine-grain efficiency-change dataset powering the Efficiency Impact page of the Mosaic Reporting Version Adoption dashboard. One row per (radiologist, practice, procedure, modality, Mosaic version, exam date) group, already restricted to the Drafting/Reporting periods with outliers excluded - Baseline-period rows are consumed only to compute each radiologist''s own case-mix-weighted baseline rate (weighted_baseline_contrib) and are not emitted as rows here. Outlier rule: a reading is excluded when Adjusted_Read_Time_Sec < 1 second or > the 99th percentile of Adjusted_Read_Time_Sec for its Clinical_Procedure_Code. Efficiency = TBWU per minute of read time. Rebuilt via tools/jobs/refresh_mosaic_efficiency_detail.sql (scheduled) from edw_dev.bipa_analytics.presentation_rpt_readtimeswith_draftingadjustedrt_tbl.';

COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.physician_npi IS 'Reading radiologist National Provider Identifier.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.radiologist_name IS 'Reading radiologist full name.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.practice IS 'Provider (reading) practice for these exams - NOT the managing practice.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.local IS 'One of the 6 fixed Local groupings, resolved via practice_to_local_mapping. Unmapped when the practice has no mapping yet.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.procedure_name IS 'Parent procedure name (Parent_Procedure_name), the case-mix key this radiologist''s baseline is computed against.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.modality IS 'Exam modality code (CT, MG, US, XR, etc.).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.modality_group IS 'Simplified modality grouping: MG (mammography) or Non-MG (everything else).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.mosaic_version IS 'Mosaic 1.0 or Mosaic 2.0. Every row in this table already has a resolved version tag - Baseline-period, pre-launch, and unmatched rows are excluded upstream, so there is no NULL/other value to filter out.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.exam_date IS 'Calendar date of the exam (DATE(Dictation_Start)).';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.total_time_sec IS 'Summed Adjusted_Read_Time_Sec (reading/dictation seconds) across all exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.total_tbwu IS 'Summed RP_TBWU (This Body Work Units) across all exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.exam_count IS 'Number of distinct exams in this row''s grouping.';
COMMENT ON COLUMN edw_prod.bipa_analytics.mosaic_efficiency_detail.weighted_baseline_contrib IS 'This radiologist''s own historical baseline efficiency rate for this procedure (TBWU per minute, computed from their Baseline-period/outlier-excluded reads only) multiplied by total_time_sec. To get the case-mix-weighted baseline rate for any slice: SUM(weighted_baseline_contrib) / SUM(total_time_sec). Compare against the actual rate SUM(total_tbwu) / (SUM(total_time_sec)/60.0) to compute pct_change = (actual - baseline) / baseline. This is the core building block for every efficiency-change KPI on the dashboard.';
