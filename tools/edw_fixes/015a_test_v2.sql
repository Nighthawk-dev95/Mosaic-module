CREATE VIEW edw_test.enterprise_analytics.mosaic_volume_metric_view
COMMENT 'MOSAIC VOLUME SEMANTIC LAYER. Governed replacement for the PBI "Mosaic Volume Report" Daily_Extract table''s 223 measures, built on edw_prod.enterprise_analytics.tbl_exam_inventory (exam grain), the confirmed enterprise_analytics equivalent of edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw. (No explicit outer column list -- every dimension/measure carries its own `comment` inside the YAML below instead, which avoids the position-dependent column-list/YAML mismatch risk that an outer list would introduce as this view evolves.)
DRAFT STATUS: not yet executed, not yet reviewed. See tools/pbi_semantic_extract/mosaic_volume_measure_inventory.md for the full PBI-measure-to-SQL-measure mapping, including every duplicate/gap/blocked item this consolidation resolved.
GRAIN: one row per exam-reading, unchanged from tbl_exam_inventory. Three LEFT JOINs (drafting_eligible_rpids_vw on rpid_procedure_code, tbl_exam_category_lookup_xwalk on RPID_parent_code=ParentRpt, dynamics_rad_drafting_enablement_vw on npi+drafting_model), all verified many-to-one on their respective key columns at authoring time (drafting_eligible_rpids_vw: 627 rows across 7 categories; dynamics_rad_drafting_enablement_vw: confirmed unique on (npi, drafting_model) this session) -- RECOMMEND RE-VERIFYING ROW COUNT IS UNCHANGED AFTER THIS VIEW IS ACTUALLY CREATED, same fan-out check mosaic_drafting_metric_vw documents doing for its own join.
WHAT THIS REPLACES: 223 PBI measures on the Daily_Extract TMDL table. ~160 were exact or near-exact duplicates of each other (same business logic at a different hardcoded window, modality, or practice grouping) and collapse onto the measures below via dimension filtering at query time or the days_back parameter. ~33 were disconnected-slicer selectors (SELECTEDVALUE-driven measure switches with no SQL equivalent). ~9 were dynamic-title string concatenations (frontend label logic now). ~9 were test/debug/stray measures. The ~13 that depend on the Dataverse AD-group/rad-pipeline data are NOT blocked -- that data is already reachable via edw_prod.enterprise_analytics.dynamics_rad_drafting_enablement_vw, joined in below as dim_enablement. Confirmed with the user and excluded entirely (not a gap, not pursued further): the "Fully Utilizing (Rad/Practice)" per-radiologist threshold-on-a-rate cluster (redundant concept), the "Eligible Exam Count"/"Mosaic Eligible Exam Count" family (all exams in Mosaic are eligible now, the PBI-era carve-out no longer applies), and Adjusted_Best_RVU/Allocated_RVU (no column equivalent exists and they are not needed).
WHAT THIS DOES NOT RE-DERIVE: drafting-eligibility/drafting-adoption business logic (Draftable/Drafted/Drafting Coverage/Drafting Adoption Rate at the fleet level) already lives in the proven, reachable edw_prod.enterprise_analytics.mosaic_drafting_metric_vw. This view''s Draftable Exam Count/Drafted Exam Count measures are SCOPED TO VOLUME REPORTING (category/modality/practice cuts PBI''s Daily_Extract needed) and are a SEPARATE, simpler definition (drafting_model IS NOT NULL, no consent/enrollment decomposition) -- do not expect them to reconcile line-for-line with mosaic_drafting_metric_vw''s exam_draftable_flag-based figures, which layer on two more ladder levels (practice-in-program, rad-enrolled) this view does not carry. For an enrollment/consent-aware drafting adoption number, query mosaic_drafting_metric_vw directly.
KEY RELATIONSHIPS: base table edw_prod.enterprise_analytics.tbl_exam_inventory. Joined dimension-only views edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw and edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk. Sibling semantic objects edw_prod.enterprise_analytics.mosaic_drafting_metric_vw (drafting/enrollment) and edw_prod.enterprise_analytics.tbl_exam_inventory_metric_view (SLA/TAT/TBWU/backlog).
FORMAT CONVENTION: every percentage measure returns a RAW FRACTION between 0 and 1; the 100x and % sign are a display-layer concern. NEVER multiply by 100 in a measure or in ad-hoc SQL against this view.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_test.enterprise_analytics.tbl_exam_inventory

joins:
  - name: dim_drafting
    source: edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw
    'on': source.RPID_Procedure_Code = dim_drafting.rpid_procedure_code
    joins:
      - name: dim_enablement
        source: edw_prod.enterprise_analytics.dynamics_rad_drafting_enablement_vw
        'on': "source.reading_provider_npi = dim_enablement.npi AND dim_drafting.drafting_model = dim_enablement.drafting_model"
  - name: dim_category
    source: edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk
    'on': source.RPID_parent_code = dim_category.ParentRpt

parameters:
  - name: days_back
    data_type: int
    default: 14

comment: |-
  MOSAIC VOLUME SEMANTIC LAYER (draft). See the CREATE VIEW table comment above for the full
  rationale, scope, and what this intentionally does NOT re-derive (drafting enrollment/consent,
  which stays in mosaic_drafting_metric_vw).
  Query with a `days_back` argument for the rolling-window measures below, e.g.
  `SELECT Modality, MEASURE(\`Mosaic Exam Count In Window\`) FROM mosaic_volume_metric_view(7)
  GROUP BY ALL` -- omit the argument to get the default (14). All-time measures (Exam Count,
  Mosaic Exam Count, etc.) ignore the parameter entirely; filter the Final Date/Week/Month
  dimensions directly at query time for any other custom range instead.

dimensions:
  - name: Exam Id
    expr: source.exam_id
    comment: Primary key of the base table. One row per exam-reading.

  - name: NPI
    expr: source.reading_provider_npi
    comment: NPI of the reading radiologist. Always a 10-digit value.
    display_name: Radiologist NPI

  - name: Radiologist Name
    expr: source.reading_provider_name_full
    display_name: Radiologist Name

  - name: Practice
    expr: source.provider_local_practice_name_curr
    comment: "Local Practice the READING RADIOLOGIST is attached to, current. THE adoption-question\
      \ practice column -- see Managing Practice for the program-membership cut, which is a\
      \ different column on purpose."
    synonyms:
      - Home Practice
      - Reading Practice

  - name: Managing Practice
    expr: source.managing_local_practice_name_curr
    comment: "Local Practice that MANAGES the site/PSA the exam was performed under, current. The\
      \ program-membership practice column that drafting_eligible_rpids_vw-style eligibility\
      \ actually keys on."

  - name: Modality
    expr: source.exam_Modality_Code
    comment: "Plain film is 'CR', never 'XR' -- a filter written against 'XR' matches zero rows."

  - name: RPID Procedure Code
    expr: source.RPID_Procedure_Code
    comment: "RPID procedure code. RPID22 confirmed live = CT HEAD WITHOUT IV CONTRAST."

  - name: RPID Parent Procedure Name
    expr: source.RPID_parent_code_description
    display_name: Parent Procedure Name

  - name: Drafting Model Category
    expr: dim_drafting.drafting_model
    comment: "One of the 7 live categories confirmed via SELECT DISTINCT this session: CT Abd/Pel,\
      \ CT Chest, CT Head, CT Spine, DEXA Capturable, US Capturable, XR/MSK. NULL = this exam's\
      \ procedure is not covered by any current Mosaic drafting model -- NOT the same as\
      \ not-drafted."
    synonyms:
      - Drafting Eligibility Category
      - Draftable Category

  - name: Exam Category
    expr: dim_category.Category
    comment: "Broader clinical exam-category taxonomy (26 categories, 969 procedure codes),\
      \ joined on RPID_parent_code = ParentRpt. A DIFFERENT, wider vocabulary from Drafting Model\
      \ Category -- do not conflate the two."

  - name: Source System Code
    expr: source.Source_System_Code

  - name: Is RPCE Source
    expr: "source.Source_System_Code IN ('rpceMidwest', 'rpceSouthwest')"
    comment: "TRUE for the two rpce-prefixed Clario values, matching backend/app/services/mosaic_service.py's\
      \ existing _RPCE_SOURCE_SYSTEMS_SQL constant exactly."

  - name: Reporting Status
    expr: |-
      CASE
        WHEN source.mosaic_draft_flag THEN 'Drafting'
        WHEN source.mosaic_read_flag  THEN 'Reporting'
        ELSE 'Baseline'
      END
    comment: "Same Drafting > Reporting > Baseline vocabulary as the MER Current Method pipeline's\
      \ Period_Type column (backend/app/services/mosaic_service.py _MER_BASE_CTE_SQL)."
    display_name: Reporting Status
    synonyms:
      - Period Type
      - Exam Stage

  - name: Final Date
    expr: CAST(source.final_datetime AS DATE)
    comment: "THE period anchor for every 'in window' measure in this view. Apply\
      \ `WHERE \\`Final Date\\` >= CURRENT_DATE - INTERVAL N DAYS` at query time instead of a\
      \ hardcoded PBI measure variant."
    format:
      type: date
      date_format: year_month_day

  - name: Final Week
    expr: "DATE_TRUNC('WEEK', source.final_datetime)"
    format:
      type: date
      date_format: year_month_day

  - name: Final Month
    expr: "DATE_TRUNC('MONTH', source.final_datetime)"
    format:
      type: date
      date_format: year_month_day

  - name: Care Setting
    expr: source.care_setting
    comment: "Closest live equivalent to PBI's Place_Of_Service_Name. NOT a 1:1 value match --\
      \ this column's values (Outpatient/ED/Inpatient/Pre-Admit/Observation/Unknown/Recurring\
      \ Patient) do not line up with PBI's POS strings. Treat as a proxy pending confirmation."

  - name: VRA Flag
    expr: source.VRA_Flag
    comment: "Maps PBI's compound condition (assisted_flag=1 AND (VRAname or Commnotetimestamp\
      \ not blank)) onto this single native boolean. Assumption flagged: no separate\
      \ assisted_flag/name/timestamp columns exist on tbl_exam_inventory."

  - name: AD Group Added Date
    expr: dim_drafting.dim_enablement.ad_group_added_date
    comment: "Replaces PBI's 4 separate 'AD Group XR/CT Head/CT AbdPel/CT Chest Date' columns with\
      \ ONE date, automatically scoped to whichever Drafting Model Category this exam belongs to\
      \ (the join keys on NPI + drafting_model together) -- no need for 4 near-duplicate\
      \ dimensions. From edw_prod.enterprise_analytics.dynamics_rad_drafting_enablement_vw,\
      \ confirmed unique on (npi, drafting_model)."
    format: { type: date, date_format: year_month_day }

  - name: Training Sent Date
    expr: dim_drafting.dim_enablement.training_sent_date

  - name: Training Completed Date
    expr: dim_drafting.dim_enablement.training_completed_date

  - name: Rad Drafting Consent
    expr: dim_drafting.dim_enablement.mosaic_drafting_consent

  - name: Rad Drafting Enabled Flag
    expr: dim_drafting.dim_enablement.drafting_enabled_flag

measures:
  - name: Exam Count
    expr: COUNT(*)
    comment: "Count of all exam-readings in scope. Denominator of Pct Mosaic Exams and Pct Drafting\
      \ Exams. Absorbs PBI's Total Exam Ct, All Exam Ct, examslast7days/examslast14days and every\
      \ other hardcoded-window exam-count variant -- filter Final Date at query time instead."
    display_name: Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }
    synonyms: [Total Exams, Finalized Exams]

  - name: Mosaic Exam Count
    expr: COUNT(*) FILTER (WHERE source.mosaic_read_flag)
    comment: "Count of exams read on the Mosaic platform. Absorbs Mosaic Exam Ct,\
      \ mosaiceamslast14days, mosaicexxamslast7days, Total Mosaic Cases (All Time) and every other\
      \ hardcoded-window variant."
    display_name: Mosaic Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }
    synonyms: [Exams On Mosaic, Mosaic Volume]

  - name: Pct Mosaic Exams
    expr: "MEASURE(`Mosaic Exam Count`) / MEASURE(`Exam Count`)"
    comment: "Raw fraction, 0 to 1. Absorbs Mosaic Exam %, % Mosaic Exams, every Last-7/14/N-Days\
      \ variant, and every modality-filtered variant (% CT, % Mammo, % Practice IR in Mosaic,\
      \ etc. -- filter the Modality dimension at query time instead of using a separate measure)."
    display_name: Pct Mosaic Exams
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Drafting Exam Count
    expr: COUNT(*) FILTER (WHERE source.mosaic_draft_flag)
    comment: "Count of exams a Mosaic AI model pre-populated (drafted OR captured -- see\
      \ mosaic_drafting_metric_vw's ai_assistance_type dimension if the Drafted/Captured split\
      \ itself is needed). Absorbs Mosaic Drafting Ct and every hardcoded-window variant."
    display_name: Drafting Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Drafting Exams
    expr: "MEASURE(`Drafting Exam Count`) / MEASURE(`Exam Count`)"
    display_name: Pct Drafting Exams
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "Rolling `days_back`-day version of Exam Count (default 14). Query via\
      \ `mosaic_volume_metric_view(N)` -- see the view-level comment. PBI's examslast7days/\
      \ examslast14days/mosaiceamslast14days family, collapsed onto one parameterized measure\
      \ instead of one measure per hardcoded window."
    display_name: Exam Count In Window
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Mosaic Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.mosaic_read_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    display_name: Mosaic Exam Count In Window
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Mosaic Exams In Window
    expr: "MEASURE(`Mosaic Exam Count In Window`) / MEASURE(`Exam Count In Window`)"
    comment: "PBI's '% Mosaic Exams Last N Days'/mosaicexams%last7days."
    display_name: Pct Mosaic Exams In Window
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Drafting Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.mosaic_draft_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's Draftingexamslat14days family."
    display_name: Drafting Exam Count In Window
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Drafting In Window
    expr: "MEASURE(`Drafting Exam Count In Window`) / MEASURE(`Exam Count In Window`)"
    comment: "PBI's '%Draftinglast 14days'."
    display_name: Pct Drafting In Window
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Estimated RVU
    expr: SUM(source.estimated_wrvu)
    comment: "wRVU est in PBI. Maps to estimated_wrvu (confirmed via backend/app/services/mosaic_service.py's\
      \ capacity CTE: `e.estimated_wrvu AS Estimated_RVU`)."
    display_name: Estimated RVU
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: Mosaic RVU
    expr: SUM(source.estimated_wrvu) FILTER (WHERE source.mosaic_read_flag)
    comment: "Building block for Pct Mosaic RVU. Exact duplicate of PBI's rvu_mosaic/Mosaicreportingrvu."

  - name: Pct Mosaic RVU
    expr: "MEASURE(`Mosaic RVU`) / MEASURE(`Estimated RVU`)"
    comment: "RVU-weighted alternative to Pct Mosaic Exams. The real measure behind PBI's\
      \ clinicalofmosaicreporting/'% of Mosaic XR' disconnected-slicer switchers."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Drafting RVU
    expr: SUM(source.estimated_wrvu) FILTER (WHERE source.mosaic_draft_flag)
    comment: "Building block for Pct Drafting RVU. Duplicate of PBI's rvu_mosaicdrafting."

  - name: Pct Drafting RVU
    expr: "MEASURE(`Drafting RVU`) / MEASURE(`Estimated RVU`)"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Best RVU
    expr: SUM(source.best_wrvu)
    comment: "best_rvu in PBI. Maps to best_wrvu."
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: TBWU
    expr: SUM(source.final_TBWU)
    comment: "TBWU/WU in PBI. Maps to final_TBWU -- the volume/exam-count TBWU, distinct from\
      \ base_tbwu/unassisted_tbwu/empirical_tbwu/allocated_tbwu which are for efficiency/capacity\
      \ (see backend/app/services/mosaic_service.py's own usage: `e.final_TBWU AS RP_TBWU`)."
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: Allocated TBWU
    expr: SUM(source.allocated_tbwu_current)
    comment: "Allocated_WU in PBI. FLAGGED ASSUMPTION: mapped to allocated_tbwu_current (the\
      \ current-recompute variant) rather than plain allocated_tbwu -- confirm which is intended\
      \ before relying on this for a trend that crosses a TBWU-version boundary (same\
      \ _current-suffix trap documented on mosaic_drafting_metric_vw's Credited Capacity TBWU)."
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: Estimated RVU In Window
    expr: "SUM(CASE WHEN CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE THEN source.estimated_wrvu ELSE 0 END)"
    comment: "PBI's 'Total RVUs In Window' (mosaictechops reference pattern), default 14 days via\
      \ `mosaic_volume_metric_view(N)`."
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: TBWU In Window
    expr: "SUM(CASE WHEN CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE THEN source.final_TBWU ELSE 0 END)"
    comment: "PBI's 'Total TBWU In Window'."
    format: { type: number, decimal_places: { type: max, places: 2 } }

  - name: RPCE Exam Count
    expr: "COUNT(*) FILTER (WHERE source.Source_System_Code IN ('rpceMidwest', 'rpceSouthwest'))"
    comment: "Absorbs RPCEEXAMS and every hardcoded-window variant."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct RPCE Reporting
    expr: "MEASURE(`Mosaic Exam Count`) / MEASURE(`RPCE Exam Count`) + 0.02"
    comment: "Matches the existing +0.02 adjustment in backend/app/services/mosaic_service.py's\
      \ _RPCE_PCT_ADJUSTMENT exactly -- confirmed with the business owner as an intentional,\
      \ known adjustment to retain, not a leftover hack."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Pct RPCE Drafting
    expr: "MEASURE(`Drafting Exam Count`) / MEASURE(`RPCE Exam Count`) + 0.02"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Pct RPCE Of All Exams
    expr: "MEASURE(`RPCE Exam Count`) / MEASURE(`Exam Count`)"
    comment: "No +0.02 adjustment -- this is a different ratio (RPCE share of ALL exams) from\
      \ Pct RPCE Reporting/Drafting (Mosaic or Drafting share of RPCE exams). Do not confuse the\
      \ two; PBI's 'RPCE as % of Clinical' is this one."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Distinct Radiologist Count
    expr: COUNT(DISTINCT source.reading_provider_npi)
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Mosaic Radiologist Count
    expr: COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE source.mosaic_read_flag)
    comment: "PBI's '# of Mosaic Rads'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Drafting Radiologist Count
    expr: COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE source.mosaic_draft_flag)
    comment: "PBI's totalradslivedrafting."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: RPCE Radiologist Count
    expr: "COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE source.Source_System_Code IN ('rpceMidwest', 'rpceSouthwest'))"
    comment: "PBI's '# of RPCE Rads'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Mosaic Of RPCE Radiologists
    expr: "MEASURE(`Mosaic Radiologist Count`) / MEASURE(`RPCE Radiologist Count`)"
    comment: "PBI's '% of Rads' -- an unusual ratio (Mosaic rads as a % of RPCE rads, not of all\
      \ rads), kept faithful to the original."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: First Mosaic Exam Date
    expr: MIN(CAST(source.final_datetime AS DATE)) FILTER (WHERE source.mosaic_read_flag)
    comment: "Per-radiologist go-live date. Group by NPI at query time -- this is PBI's 'First\
      \ Mosaic Case'/'first case'."
    format: { type: date, date_format: year_month_day }

  - name: First Mosaic Drafting Exam Date
    expr: MIN(CAST(source.final_datetime AS DATE)) FILTER (WHERE source.mosaic_draft_flag)
    comment: "PBI's firstdraft, unconditional on AD-group status (unlike PBI's original gate).\
      \ Filter on Rad Drafting Enabled Flag at query time for the AD-group-gated version."
    format: { type: date, date_format: year_month_day }

  - name: Last Drafted Exam Date
    expr: MAX(CAST(source.final_datetime AS DATE)) FILTER (WHERE source.mosaic_draft_flag)
    format: { type: date, date_format: year_month_day }

  - name: VRA Prepped Exam Count
    expr: COUNT(*) FILTER (WHERE source.VRA_Flag)
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: VRA Prepped Mosaic Exam Count
    expr: COUNT(*) FILTER (WHERE source.VRA_Flag AND source.mosaic_read_flag)
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct VRA Prepped Of Exams
    expr: "MEASURE(`VRA Prepped Exam Count`) / MEASURE(`Exam Count`)"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Pct VRA Prepped Of Mosaic Exams
    expr: "MEASURE(`VRA Prepped Mosaic Exam Count`) / MEASURE(`Mosaic Exam Count`)"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Draftable Exam Count
    expr: COUNT(*) FILTER (WHERE dim_drafting.drafting_model IS NOT NULL)
    comment: "SCOPED TO VOLUME REPORTING, a simpler definition than mosaic_drafting_metric_vw's\
      \ exam_draftable_flag (no practice-in-program or rad-enrolled gate layered on). Filter the\
      \ Drafting Model Category dimension at query time to scope to one of the 7 categories --\
      \ absorbs every one of PBI's ~20 hardcoded-RPID-list Draftable measures (US Capturable,\
      \ Draftable CT Abd/Pel/Chest/Spine/Head, Draftable XRs, BD/DEXA Capture Eligible, all their\
      \ (Last 14d)/(Last 3m)/(Practice) variants)."
    display_name: Draftable Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Drafted Exam Count
    expr: "COUNT(*) FILTER (WHERE dim_drafting.drafting_model IS NOT NULL AND source.mosaic_draft_flag)"
    comment: "Absorbs Captured US, Total Drafted XR/CT/Chest/Spine/AbdPel, MosaicCaptureCt, Total\
      \ US/BD/DEXA Capture Read and all their window/practice variants."
    display_name: Drafted Exam Count
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Drafted Of Draftable
    expr: "MEASURE(`Drafted Exam Count`) / MEASURE(`Draftable Exam Count`)"
    comment: "Absorbs every '% Drafted CT X'/'% Captured'/'% X Capture Read' measure in the TMDL."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Capture Eligible Exam Count
    expr: "COUNT(*) FILTER (WHERE dim_drafting.drafting_model IN ('US Capturable', 'DEXA Capturable'))"
    comment: "Draftable Exam Count scoped to the two capture categories (US + BD/DEXA combined --\
      \ PBI's 'US Capturable'/BD-capture-eligible measures scope one modality at a time by also\
      \ filtering Modality at query time)."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Captured Exam Count
    expr: "COUNT(*) FILTER (WHERE dim_drafting.drafting_model IN ('US Capturable', 'DEXA Capturable') AND source.mosaic_draft_flag)"
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Capture Read
    expr: "MEASURE(`Captured Exam Count`) / MEASURE(`Capture Eligible Exam Count`)"
    comment: "PBI's '% Capture Read (Last 14d)' -- the all-capture-types-combined rate, no\
      \ single-modality restriction. Filter Modality='US' or 'BD' at query time to scope to one."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Pct RPCE Capture
    expr: "MEASURE(`Captured Exam Count`) / MEASURE(`RPCE Exam Count`) + 0.02"
    comment: "PBI's '% of RPCE_capture', same +0.02 adjustment convention as Pct RPCE\
      \ Reporting/Drafting."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: US Capture Eligible In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'US' AND dim_drafting.drafting_model = 'US Capturable' AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'US Capture Eligible (Last 14d)', default 14 days via\
      \ `mosaic_volume_metric_view(N)`. Draftable Exam Count/Capture Eligible Exam Count above\
      \ scope all-time; this is the rolling-window, US-only equivalent."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: US Capture Read In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'US' AND dim_drafting.drafting_model = 'US Capturable' AND source.mosaic_draft_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Total US Capture Read'/'US Capture Read (Last 14d)'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct US Capture Read In Window
    expr: "MEASURE(`US Capture Read In Window`) / MEASURE(`US Capture Eligible In Window`)"
    comment: "PBI's '% US Capture Read (Last 14d)'."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: BD Capture Eligible In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'BD' AND dim_drafting.drafting_model = 'DEXA Capturable' AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'BD Capture Eligible (Last 14d)'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: BD Capture Read In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'BD' AND dim_drafting.drafting_model = 'DEXA Capturable' AND source.mosaic_draft_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's '% BD Capture Read (Last 14d)' numerator."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct BD Capture Read In Window
    expr: "MEASURE(`BD Capture Read In Window`) / MEASURE(`BD Capture Eligible In Window`)"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: CA Lung Screener Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT' AND source.RPID_Procedure_Code IN ('RPID6891', 'RPID6891-FU', 'RAD2282', 'RPID6891-WC') AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'CA Lung Screener Reads By Rad In Window' -- the dedicated rolling-window\
      \ variant; CA Lung Screener Exam Count above is the all-time total."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: CA Lung Screener Mosaic Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT' AND source.RPID_Procedure_Code IN ('RPID6891', 'RPID6891-FU', 'RAD2282', 'RPID6891-WC') AND source.mosaic_read_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'CA Lung Screener Reads In Mosaic In Window'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct CA Lung Screener Read In Mosaic In Window
    expr: "MEASURE(`CA Lung Screener Mosaic Exam Count In Window`) / MEASURE(`CA Lung Screener Exam Count In Window`)"
    comment: "PBI's 'CA Lung Screener % Reads in Mosaic (last 14d)'."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Mammo Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'MG' AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Total Mammo Reads by Rad (Last 14d)'. Modality='MG' is filterable at query\
      \ time against the all-time Exam Count too, but PBI's mammo/lung-screener/IR KPI tiles were\
      \ always window-scoped by design, so a dedicated In Window measure matches that usage."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Mammo Mosaic Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'MG' AND source.mosaic_read_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Total Mammo Reads in Mosaic (Last 14d)'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct Mammo Read In Mosaic In Window
    expr: "MEASURE(`Mammo Mosaic Exam Count In Window`) / MEASURE(`Mammo Exam Count In Window`)"
    comment: "PBI's '% Mammo Reads in Mosaic (Last 14d)'."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: IR Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'IR' AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Total IR Cases (Last 2w)' -- PBI hardcoded 2 weeks specifically for this one;\
      \ default days_back=14 reproduces that, any other value is a deliberate generalization."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: IR Mosaic Exam Count In Window
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'IR' AND source.mosaic_read_flag AND CAST(source.final_datetime AS DATE) >= CURRENT_DATE - days_back AND CAST(source.final_datetime AS DATE) <= CURRENT_DATE)"
    comment: "PBI's 'Total IR in Mosaic (Last 2w)'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct IR In Mosaic In Window
    expr: "MEASURE(`IR Mosaic Exam Count In Window`) / MEASURE(`IR Exam Count In Window`)"
    comment: "PBI's '% IR in Mosaic (Last 2w)'/'% Practice IR in Mosaic (Last 2w)'."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: Capture Eligible Radiologist Count
    expr: "COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE dim_drafting.drafting_model IN ('US Capturable', 'DEXA Capturable'))"
    comment: "PBI's 'Eligible Rads for Capture'/'Eligible Rads for Capture BD'. A flat distinct\
      \ count -- unrelated to the excluded Fully-Utilizing cluster (that was specifically about\
      \ threshold-on-a-rate measures, not plain distinct counts)."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Capture Radiologist Count
    expr: "COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE source.mosaic_draft_flag AND dim_drafting.drafting_model IN ('US Capturable', 'DEXA Capturable'))"
    comment: "PBI's 'Capture Live'."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Head CT Exam Count
    expr: "COUNT(*) FILTER (WHERE source.RPID_Procedure_Code = 'RPID22')"
    comment: "Building block for Pct Head CT RPCE. Equivalent to Exam Count filtered to Drafting\
      \ Model Category = 'CT Head' at query time, kept as its own measure only because the RPCE\
      \ ratio below needs a fixed (non-dimension-filterable) denominator."

  - name: Head CT RPCE Exam Count
    expr: "COUNT(*) FILTER (WHERE source.RPID_Procedure_Code = 'RPID22' AND source.Source_System_Code IN ('rpceMidwest', 'rpceSouthwest'))"

  - name: Pct Head CT RPCE
    expr: "MEASURE(`Head CT RPCE Exam Count`) / MEASURE(`Head CT Exam Count`)"
    comment: "PBI's Pct_ct_head_rpce. No +0.02 adjustment (unlike Pct RPCE Reporting/Drafting --\
      \ this is a different ratio: RPCE share of Head CT volume specifically)."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: CT Exam Count
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT')"
    comment: "Building block for Pct CT RPCE, same reasoning as Head CT Exam Count above."

  - name: CT RPCE Exam Count
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT' AND source.Source_System_Code IN ('rpceMidwest', 'rpceSouthwest'))"

  - name: Pct CT RPCE
    expr: "MEASURE(`CT RPCE Exam Count`) / MEASURE(`CT Exam Count`)"
    comment: "PBI's Pct_ct_rpce."
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: CA Lung Screener Exam Count
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT' AND source.RPID_Procedure_Code IN ('RPID6891', 'RPID6891-FU', 'RAD2282', 'RPID6891-WC'))"
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: CA Lung Screener Mosaic Exam Count
    expr: "COUNT(*) FILTER (WHERE source.exam_Modality_Code = 'CT' AND source.RPID_Procedure_Code IN ('RPID6891', 'RPID6891-FU', 'RAD2282', 'RPID6891-WC') AND source.mosaic_read_flag)"
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Pct CA Lung Screener Read In Mosaic
    expr: "MEASURE(`CA Lung Screener Mosaic Exam Count`) / MEASURE(`CA Lung Screener Exam Count`)"
    format: { type: percentage, decimal_places: { type: max, places: 2 } }

  - name: In Drafting Pipeline Exam Count
    expr: "COUNT(*) FILTER (WHERE dim_drafting.dim_enablement.ad_group_added_date IS NOT NULL)"
    comment: "PBI's 'In Pipeline Table' -- exam's radiologist+drafting-model combination has been\
      \ added to the AD group at all (regardless of consent/training/enablement status)."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Drafted But Not Enabled Exam Count
    expr: "COUNT(*) FILTER (WHERE source.mosaic_draft_flag AND NOT COALESCE(dim_drafting.dim_enablement.drafting_enabled_flag, FALSE))"
    comment: "PBI's 'Has Drafted But Not On Drafting' -- exam was AI-drafted but the\
      \ radiologist+model combination doing the drafting isn't (or is no longer) formally enabled.\
      \ Group by Modality/Drafting Model Category at query time for the modality breakdown PBI\
      \ showed."
    format: { type: number, decimal_places: { type: exact, places: 0 } }

  - name: Drafted But Not Enabled Radiologist Count
    expr: "COUNT(DISTINCT source.reading_provider_npi) FILTER (WHERE source.mosaic_draft_flag AND NOT COALESCE(dim_drafting.dim_enablement.drafting_enabled_flag, FALSE))"
    comment: "PBI's 'Rads Not On Drafting With Drafted Exams' -- distinct-radiologist version of\
      \ Drafted But Not Enabled Exam Count above."
    format: { type: number, decimal_places: { type: exact, places: 0 } }
$$;
