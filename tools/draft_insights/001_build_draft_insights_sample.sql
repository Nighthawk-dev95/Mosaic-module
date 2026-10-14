-- Builds edw_prod.enterprise_analytics.tbl_mosaic_draft_insights and populates it with an
-- AI (ai_query, databricks-claude-sonnet-4) quality assessment comparing Mosaic AI draft
-- findings against the radiologist's final signed report - retention %, an overall
-- usefulness rating, and what the radiologist added/removed/reworded, each as free text
-- plus a controlled-vocabulary category list.
--
-- Adapted from the user's own "Mosaic Draft Insights" notebook (source of truth for the
-- CREATE TABLE shape, the ai_query prompt/schema, and the MERGE/SCD2 logic below - all
-- unchanged from that notebook). The one change is the `new_accessions` CTE: the notebook's
-- own version selects every drafted exam since 2026-08-01 (multi-million rows -> multi-
-- million ai_query calls). This version instead pulls a bounded, stratified RECENT SAMPLE -
-- trailing 14 days, capped at 1200 exams per modality (ROW_NUMBER, random order) so low-
-- volume modalities aren't swamped by CR/CT/US volume. Verified live against
-- edw_prod.edw_gold.aws_prod_report_signed_events_default_mosaicreporting_vw joined to
-- edw_prod.enterprise_analytics.tbl_exam_inventory on 2026-09-22: trailing 14 days has only
-- 7 distinct modalities (CR 336K, CT 161K, US 57K, BD 4.1K, RF/UNK/OT single digits-to-
-- tens), so this cap yields ~4,800 total accessions to assess - CR/CT/US/BD each capped to
-- 1200, the rest fully included since they're already under the cap.
--
-- Safe to re-run: the NOT EXISTS clause (same as the notebook) skips any accession already
-- assessed, so a second run only assesses what's newly in the trailing-14-day window.
--
-- THIS FILE HAS NOT BEEN RUN. The Databricks connector available to Claude Code sessions in
-- this repo is read-only (see tools/edw_fixes/003_exclude_do_not_launch_revisit.sql for the
-- same constraint) - it cannot CREATE TABLE, MERGE, or invoke ai_query's paid model calls.
-- A human with write access on edw_prod.enterprise_analytics needs to run this in a
-- Databricks SQL editor or notebook. Statement 1 (CREATE TABLE) only needs to run once, ever.

-- =============================================================================
-- Statement 1: Create SCD2 table (run once)
-- =============================================================================
CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics.tbl_mosaic_draft_insights (
  -- SCD2 surrogate key
  insight_sk        BIGINT GENERATED ALWAYS AS IDENTITY COMMENT 'Auto-generated surrogate key for SCD Type 2 versioning. Each version of an accession assessment receives a unique key.',
  -- Business key
  accession_number  STRING NOT NULL COMMENT 'Business key. The radiology exam accession number that was Mosaic-drafted and assessed. Join key to tbl_exam_inventory.accession_number and aws_prod_report_signed_events_default_mosaicreporting_vw.accession_number.',
  -- Source data
  drafting_findings_raw  STRING COMMENT 'Raw Mosaic AI-generated draft findings text as presented to the radiologist before editing. Source: aws_prod_report_signed_events_default_mosaicreporting_vw.drafting_findings_raw.',
  final_report           STRING COMMENT 'Final signed radiology report text after the radiologist reviewed and edited the draft. Source: aws_prod_report_signed_events_default_mosaicreporting_vw.final_report.',
  -- AI assessment fields
  retention_pct          INT COMMENT 'AI-estimated percentage (0-100) of draft findings content retained in the final report. Higher values indicate more of the draft was kept as-is.',
  added_by_radiologist   STRING COMMENT 'AI-generated summary of key content the radiologist added to the final report that was NOT present in the original draft.',
  removed_from_draft     STRING COMMENT 'AI-generated summary of key draft content that was removed or significantly changed by the radiologist.',
  overall_assessment     STRING COMMENT 'AI-assigned draft quality category. Values: Highly Useful, Moderately Useful, Slightly Useful, Not Useful.',
  formatting             STRING COMMENT 'AI-generated description of changes the radiologist made to report structure, headings, or template. NULL if no formatting changes detected.',
  clinical_interpretation STRING COMMENT 'AI-generated description of clinical interpretations, impressions, or diagnoses the radiologist added. NULL if none detected.',
  additional_findings    STRING COMMENT 'AI-generated description of new observations or findings the radiologist added that were NOT in the draft. NULL if none detected.',
  removed_content        STRING COMMENT 'AI-generated description of draft content the radiologist omitted or significantly changed. NULL if none detected.',
  terminology            STRING COMMENT 'AI-generated description of rewording or medical terminology changes the radiologist made. NULL if none detected.',
  -- Assessment metadata
  model_used             STRING COMMENT 'Identifier of the LLM used to generate the assessment (e.g. databricks-claude-sonnet-4). Tracked for reproducibility and model version comparison.',
  -- SCD2 tracking
  effective_from         TIMESTAMP NOT NULL COMMENT 'SCD2 row start timestamp. The moment this assessment version became the current record.',
  effective_to           TIMESTAMP COMMENT 'SCD2 row end timestamp. NULL for the current active record; set to the effective_from of the superseding row when expired.',
  is_current             BOOLEAN NOT NULL COMMENT 'SCD2 current-row flag. TRUE for the latest assessment of each accession, FALSE for expired historical versions.'
)
USING DELTA
COMMENT 'SCD2 table storing AI-generated draft quality assessments for Mosaic-drafted radiology exams. Business key: accession_number.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- =============================================================================
-- Statement 2: Recent-sample load - stratified by modality, trailing 14 days
-- =============================================================================
WITH candidate_pool AS (
  SELECT
    m.accession_number,
    m.drafting_findings_raw,
    m.final_report,
    ROW_NUMBER() OVER (PARTITION BY ei.exam_Modality_Code ORDER BY RAND()) AS modality_rn
  FROM edw_prod.edw_gold.aws_prod_report_signed_events_default_mosaicreporting_vw m
  JOIN edw_prod.enterprise_analytics.tbl_exam_inventory ei
    ON m.accession_number = ei.accession_number
  WHERE ei.mosaic_draft_flag = 1
    AND ei.final_datetime >= CURRENT_DATE() - INTERVAL 14 DAYS
    AND m.drafting_findings_raw IS NOT NULL AND m.drafting_findings_raw <> ''
    AND m.final_report IS NOT NULL AND m.final_report <> ''
    AND NOT EXISTS (
      SELECT 1
      FROM edw_prod.enterprise_analytics.tbl_mosaic_draft_insights t
      WHERE t.accession_number = m.accession_number
        AND t.is_current = true
    )
),
new_accessions AS (
  SELECT accession_number, drafting_findings_raw, final_report
  FROM candidate_pool
  WHERE modality_rn <= 1200
),
assessed AS (
  -- Run AI assessment on the sampled accessions only
  SELECT accession_number,
         drafting_findings_raw,
         final_report,
         ai_query(
           'databricks-claude-sonnet-4',
           CONCAT(
             'You are a radiology report quality assessor. Compare the draft findings to the final radiology report and assess how much of the draft content was retained in the final report.

Draft Findings:
', COALESCE(drafting_findings_raw, '(empty)'), '

Final Report:
', COALESCE(final_report, '(empty)'), '

Provide your assessment as JSON with these fields:
- retention_pct: estimated percentage (0-100) of draft findings content that made it into the final report
- added_by_radiologist: brief summary of key content the radiologist added that was NOT in the draft
- added_by_radiologist_categories: comma-separated list from ONLY these values: "Complete Report Build" (radiologist built entire report from minimal draft), "Structural Formatting" (added report template/sections/headings), "Pertinent Negatives" (added negative/normal findings like no fracture, normal alignment), "Clinical Impression Added" (added formal impression or conclusion), "New Pathology Identified" (added new diagnosis or finding not in draft), "Systematic Review" (added systematic evaluation of additional anatomical structures), "Recommendation Added" (added clinical recommendations for follow-up/imaging)
- removed_from_draft: brief summary of key draft content that was removed or significantly changed
- removed_from_draft_categories: comma-separated list from ONLY these values: "None Removed" (nothing meaningful removed), "Diagnosis Revised" (changed or corrected a diagnosis), "Content Omitted" (specific findings dropped entirely), "Description Simplified" (condensed verbose or uncertain language)
- overall_assessment: one of "Highly Useful", "Moderately Useful", "Slightly Useful", "Not Useful"
- formatting: What the radiologist changed in report structure, headings, or template. Return null if no formatting changes.
- formatting_categories: comma-separated list from ONLY these values: "Full Report Template Added" (added complete EXAM/COMPARISON/FINDINGS/IMPRESSION structure), "Section Headings Added" (added anatomical subsection headings within findings), "Numbered Impression Created" (created formal numbered impression list), "No Formatting Changes" (no structural changes)
- clinical_interpretation: What clinical interpretations, impressions, or diagnoses the radiologist added. Return null if none.
- clinical_interpretation_categories: comma-separated list from ONLY these values: "Normal/Negative Conclusion" (impression of no acute/significant abnormality), "Specific Diagnosis Added" (identified a definitive clinical diagnosis), "Diagnosis Refined" (changed/narrowed/corrected the draft interpretation), "Findings Summarized" (reorganized findings into structured impression), "Recommendation Added" (added clinical recommendation), "None" (no clinical interpretation changes)
- additional_findings: New observations or findings the radiologist added that were NOT in the draft. Return null if none.
- additional_findings_categories: comma-separated list from ONLY these values: "Pertinent Negatives" (documented absence of conditions), "Anatomical System Review" (systematic evaluation of additional body parts), "New Pathology" (identified new pathological finding), "Incidental Finding" (secondary observation unrelated to primary indication), "None" (no additional findings)
- removed_content: Draft content the radiologist omitted or significantly changed. Return null if none.
- terminology: Rewording or medical terminology changes the radiologist made. Return null if none.

Return ONLY the JSON object, no markdown fences or extra text.'),
           modelParameters => named_struct('max_tokens', 700, 'temperature', 0.1)
         ) AS draft_assessment
  FROM new_accessions
),
source AS (
  SELECT
    accession_number,
    drafting_findings_raw,
    final_report,
    parsed.retention_pct,
    parsed.added_by_radiologist,
    parsed.added_by_radiologist_categories,
    parsed.removed_from_draft,
    parsed.removed_from_draft_categories,
    parsed.overall_assessment,
    parsed.formatting,
    parsed.formatting_categories,
    parsed.clinical_interpretation,
    parsed.clinical_interpretation_categories,
    parsed.additional_findings,
    parsed.additional_findings_categories,
    parsed.removed_content,
    parsed.terminology,
    'databricks-claude-sonnet-4' AS model_used,
    current_timestamp() AS effective_from,
    CAST(NULL AS TIMESTAMP) AS effective_to,
    true AS is_current
  FROM assessed
  LATERAL VIEW OUTER inline(ARRAY(
    from_json(
      regexp_replace(draft_assessment, '```json\\s*|```\\s*', ''),
      'STRUCT<retention_pct:INT, added_by_radiologist:STRING, added_by_radiologist_categories:STRING, removed_from_draft:STRING, removed_from_draft_categories:STRING, overall_assessment:STRING, formatting:STRING, formatting_categories:STRING, clinical_interpretation:STRING, clinical_interpretation_categories:STRING, additional_findings:STRING, additional_findings_categories:STRING, removed_content:STRING, terminology:STRING>'
    )
  )) parsed
)
MERGE INTO edw_prod.enterprise_analytics.tbl_mosaic_draft_insights AS tgt
USING source AS src
  ON tgt.accession_number = src.accession_number AND tgt.is_current = true
-- SCD2: if re-assessed, expire the old row
WHEN MATCHED THEN UPDATE SET
  tgt.effective_to = src.effective_from,
  tgt.is_current   = false
-- New accession: insert current row
WHEN NOT MATCHED THEN INSERT (
  accession_number, drafting_findings_raw, final_report,
  retention_pct, added_by_radiologist, added_by_radiologist_categories,
  removed_from_draft, removed_from_draft_categories, overall_assessment,
  formatting, formatting_categories,
  clinical_interpretation, clinical_interpretation_categories,
  additional_findings, additional_findings_categories,
  removed_content, terminology,
  model_used, effective_from, effective_to, is_current
) VALUES (
  src.accession_number, src.drafting_findings_raw, src.final_report,
  src.retention_pct, src.added_by_radiologist, src.added_by_radiologist_categories,
  src.removed_from_draft, src.removed_from_draft_categories, src.overall_assessment,
  src.formatting, src.formatting_categories,
  src.clinical_interpretation, src.clinical_interpretation_categories,
  src.additional_findings, src.additional_findings_categories,
  src.removed_content, src.terminology,
  src.model_used, src.effective_from, src.effective_to, src.is_current
)
