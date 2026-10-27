CREATE VIEW edw_test.enterprise_analytics.mosaic_resident_utilization_metric_view (
  Exam Id COMMENT 'Unique exam identifier. The view has one row per exam read with a resident (reading_provider_resident_flag = \'Y\'). For drill-down only; do not group by it for summaries.',
  Resident NPI COMMENT 'NPI of the resident (trainee) radiologist on the exam. Group by this for per-resident utilization and first-Mosaic dates.',
  Resident Name COMMENT 'Full name of the resident (trainee) radiologist on the exam. Match partial names with ILIKE \'%lastname%\'.',
  Radiologist Name COMMENT 'Supervising / attending radiologist of record on the exam (the reading provider) - not the resident.',
  Modality COMMENT 'Exam modality code, e.g. \'CT\', \'MR\', \'US\'. Plain film is \'CR\', never \'XR\' - a filter on \'XR\' matches zero rows.',
  Source System Code COMMENT 'Source system the exam record came from, e.g. \'rpceMidwest\', \'rpceSouthwest\' (the RPCE sources).',
  Final Date COMMENT 'Date the exam report was finalized - the date dimension for this view. Apply Final Date >= CURRENT_DATE - INTERVAL N DAYS at query time in place of PowerBI\'s hardcoded Last-14d resident measures, or use the In Window measures.',
  Care Setting COMMENT 'Patient care setting: Outpatient, ED, Inpatient, Pre-Admit, Observation, Unknown, Recurring Patient. Closest equivalent to PowerBI\'s Place_Of_Service_Name but NOT a 1:1 value match - treat as a proxy.',
  Exam Count COMMENT 'Building block: denominator of Pct Mosaic Exams; also the headline resident exam volume. Exams read with a resident in the Final Date range = PowerBI [Exams This Period] (Mosaic Volume Report, Resident Utilization); unfiltered it is the all-time denominator.',
  Mosaic Exam Count COMMENT 'Building block: numerator of Pct Mosaic Exams. Resident exams read in Mosaic = PowerBI [Mosaic Exams This Period]; with no date filter = PowerBI [Resident Total Mosaic Exams (All Time)] (Mosaic Volume Report).',
  Pct Mosaic Exams COMMENT 'Resident utilization: share of resident exams read in Mosaic, a fraction (0.85 = 85%) = PowerBI [Resident % Mosaic Exams]; with a Final Date window also [Resident % Mosaic Last 14d]. Not eligibility-adjusted (PowerBI\'s \'Eligible\' variants are not in this view).',
  Exam Count In Window COMMENT 'Building block: denominator of Pct Mosaic Exams In Window. Resident exams finalized in the last days_back days (default 14) through today = PowerBI [Exams This Period] on the report\'s rolling window. Query via mosaic_resident_utilization_metric_view(N) to change N.',
  Mosaic Exam Count In Window COMMENT 'Building block: numerator of Pct Mosaic Exams In Window. Resident exams read in Mosaic in the last days_back days (default 14) through today = PowerBI [Mosaic Exams This Period].',
  Pct Mosaic Exams In Window COMMENT 'Rolling-window resident utilization: share of resident exams in the last days_back days (default 14) read in Mosaic, a fraction (0.85 = 85%) = PowerBI [Resident % Mosaic Last 14d]. Not eligibility-adjusted.',
  First Mosaic Exam Date COMMENT 'Earliest Final Date of a resident exam read in Mosaic = PowerBI [Resident First Mosaic Exam]. Group by Resident NPI for each resident\'s Mosaic start; leave Final Date unfiltered to get the true first date.',
  First Mosaic Drafting Exam Date COMMENT 'Earliest Final Date of a resident exam drafted by Mosaic AI = PowerBI [Resident First Mosaic Draft Exam]. Group by Resident NPI; leave Final Date unfiltered to get the true first date.')
COMMENT 'RESIDENT UTILIZATION SEMANTIC LAYER (draft). Governed replacement for the PBI "Mosaic Volume Report" Resident Utilization table\'s 12 measures, grain = one row per exam read by a resident (reading_provider_resident_flag = \'Y\'). (No explicit outer column list -- see mosaic_volume_metric_view\'s comment for why.)
Scope reference: edw_dev.mosaictechops.mv_mosaic_resident (NOT reachable -- reference only). Its 5 achievable measures (Exams This Period, Mosaic Exams This Period, Pct Mosaic Exams, First Mosaic Exam, First Mosaic Draft Exam) are all ported below with the same names used in this view\'s own naming convention, plus In Window variants. Confirmed with the user and excluded entirely (not a gap): the per-resident "Fully Utilizing (Resident)"/"Count Fully Utilizing Residents" threshold-on-a-rate rollup (redundant concept, same as the practice-level cluster in mosaic_volume_metric_view), and the Eligible Exam Count family (all exams in Mosaic are eligible now) -- see tools/pbi_semantic_extract/mosaic_volume_measure_inventory.md.
FORMAT CONVENTION: every percentage measure returns a RAW FRACTION between 0 and 1.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: (SELECT * FROM edw_test.enterprise_analytics.tbl_exam_inventory WHERE reading_provider_resident_flag
  = 'Y')

comment: |-
  RESIDENT UTILIZATION SEMANTIC LAYER (draft). Governed replacement for the PBI "Mosaic Volume Report" Resident Utilization table's 12 measures, grain = one row per exam read by a resident (reading_provider_resident_flag = 'Y'). (No explicit outer column list -- see mosaic_volume_metric_view's comment for why.)
  Scope reference: edw_dev.mosaictechops.mv_mosaic_resident (NOT reachable -- reference only). Its 5 achievable measures (Exams This Period, Mosaic Exams This Period, Pct Mosaic Exams, First Mosaic Exam, First Mosaic Draft Exam) are all ported below with the same names used in this view's own naming convention, plus In Window variants. Confirmed with the user and excluded entirely (not a gap): the per-resident "Fully Utilizing (Resident)"/"Count Fully Utilizing Residents" threshold-on-a-rate rollup (redundant concept, same as the practice-level cluster in mosaic_volume_metric_view), and the Eligible Exam Count family (all exams in Mosaic are eligible now) -- see tools/pbi_semantic_extract/mosaic_volume_measure_inventory.md.
  FORMAT CONVENTION: every percentage measure returns a RAW FRACTION between 0 and 1.

parameters:
  - name: days_back
    data_type: int
    default: 14

dimensions:
  - name: Exam Id
    expr: exam_id
    comment: Unique exam identifier. The view has one row per exam read with a resident
      (reading_provider_resident_flag = 'Y'). For drill-down only; do not group by
      it for summaries.
    display_name: Exam ID
    synonyms:
      - exam key
      - exam identifier

  - name: Resident NPI
    expr: resident_radiologist_npi
    comment: NPI of the resident (trainee) radiologist on the exam. Group by this
      for per-resident utilization and first-Mosaic dates.
    display_name: Resident NPI
    synonyms:
      - trainee npi
      - resident provider id

  - name: Resident Name
    expr: resident_radiologist_name_full
    comment: Full name of the resident (trainee) radiologist on the exam. Match partial
      names with ILIKE '%lastname%'.
    display_name: Resident Name
    synonyms:
      - resident
      - trainee
      - resident radiologist

  - name: Radiologist Name
    expr: reading_provider_name_full
    comment: Supervising / attending radiologist of record on the exam (the reading
      provider) - not the resident.
    display_name: Attending Radiologist
    synonyms:
      - attending
      - supervising radiologist
      - radiologist of record

  - name: Modality
    expr: exam_Modality_Code
    comment: "Exam modality code, e.g. 'CT', 'MR', 'US'. Plain film is 'CR', never\
      \ 'XR' - a filter on 'XR' matches zero rows."
    display_name: Modality
    synonyms:
      - imaging modality
      - modality code
      - exam modality

  - name: Source System Code
    expr: Source_System_Code
    comment: "Source system the exam record came from, e.g. 'rpceMidwest', 'rpceSouthwest'\
      \ (the RPCE sources)."
    display_name: Source System
    synonyms:
      - ris source
      - originating system

  - name: Final Date
    expr: CAST(final_datetime AS DATE)
    comment: "Date the exam report was finalized - the date dimension for this view.\
      \ Apply Final Date >= CURRENT_DATE - INTERVAL N DAYS at query time in place\
      \ of PowerBI's hardcoded Last-14d resident measures, or use the In Window measures."
    display_name: Final Date
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - finalized date
      - report date
      - resident exam date

  - name: Care Setting
    expr: care_setting
    comment: "Patient care setting: Outpatient, ED, Inpatient, Pre-Admit, Observation,\
      \ Unknown, Recurring Patient. Closest equivalent to PowerBI's Place_Of_Service_Name\
      \ but NOT a 1:1 value match - treat as a proxy."
    display_name: Care Setting
    synonyms:
      - patient setting
      - place of service
      - patient class

measures:
  - name: Exam Count
    expr: COUNT(*)
    comment: "Building block: denominator of Pct Mosaic Exams; also the headline resident\
      \ exam volume. Exams read with a resident in the Final Date range = PowerBI\
      \ [Exams This Period] (Mosaic Volume Report, Resident Utilization); unfiltered\
      \ it is the all-time denominator."
    display_name: Resident Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - resident exam volume
      - exams read by residents
      - exams this period

  - name: Mosaic Exam Count
    expr: COUNT(*) FILTER (WHERE mosaic_read_flag)
    comment: "Building block: numerator of Pct Mosaic Exams. Resident exams read in\
      \ Mosaic = PowerBI [Mosaic Exams This Period]; with no date filter = PowerBI\
      \ [Resident Total Mosaic Exams (All Time)] (Mosaic Volume Report)."
    display_name: Resident Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - resident mosaic volume
      - mosaic exams this period
      - resident total mosaic exams

  - name: Pct Mosaic Exams
    expr: MEASURE(`Mosaic Exam Count`) / MEASURE(`Exam Count`)
    comment: "Resident utilization: share of resident exams read in Mosaic, a fraction\
      \ (0.85 = 85%) = PowerBI [Resident % Mosaic Exams]; with a Final Date window\
      \ also [Resident % Mosaic Last 14d]. Not eligibility-adjusted (PowerBI's 'Eligible'\
      \ variants are not in this view)."
    display_name: Resident Mosaic Utilization Pct
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - resident utilization
      - resident adoption
      - '% resident exams in mosaic'
      - resident mosaic rate

  - name: Exam Count In Window
    expr: COUNT(*) FILTER (WHERE CAST(final_datetime AS DATE) >= CURRENT_DATE - days_back
      AND CAST(final_datetime AS DATE) <= CURRENT_DATE)
    comment: "Building block: denominator of Pct Mosaic Exams In Window. Resident\
      \ exams finalized in the last days_back days (default 14) through today = PowerBI\
      \ [Exams This Period] on the report's rolling window. Query via mosaic_resident_utilization_metric_view(N)\
      \ to change N."
    display_name: Resident Exams In Window
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - resident exams last 14 days
      - recent resident exams

  - name: Mosaic Exam Count In Window
    expr: COUNT(*) FILTER (WHERE mosaic_read_flag AND CAST(final_datetime AS DATE)
      >= CURRENT_DATE - days_back AND CAST(final_datetime AS DATE) <= CURRENT_DATE)
    comment: "Building block: numerator of Pct Mosaic Exams In Window. Resident exams\
      \ read in Mosaic in the last days_back days (default 14) through today = PowerBI\
      \ [Mosaic Exams This Period]."
    display_name: Resident Mosaic Exams In Window
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - resident mosaic exams last 14 days
      - recent resident mosaic exams

  - name: Pct Mosaic Exams In Window
    expr: MEASURE(`Mosaic Exam Count In Window`) / MEASURE(`Exam Count In Window`)
    comment: "Rolling-window resident utilization: share of resident exams in the\
      \ last days_back days (default 14) read in Mosaic, a fraction (0.85 = 85%) =\
      \ PowerBI [Resident % Mosaic Last 14d]. Not eligibility-adjusted."
    display_name: Resident Mosaic Utilization Pct In Window
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - resident utilization last 14 days
      - recent resident adoption
      - resident % mosaic last 14d

  - name: First Mosaic Exam Date
    expr: MIN(CAST(final_datetime AS DATE)) FILTER (WHERE mosaic_read_flag)
    comment: "Earliest Final Date of a resident exam read in Mosaic = PowerBI [Resident\
      \ First Mosaic Exam]. Group by Resident NPI for each resident's Mosaic start;\
      \ leave Final Date unfiltered to get the true first date."
    display_name: Resident First Mosaic Exam Date
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - resident mosaic start date
      - resident go live date
      - first mosaic read

  - name: First Mosaic Drafting Exam Date
    expr: MIN(CAST(final_datetime AS DATE)) FILTER (WHERE mosaic_draft_flag)
    comment: "Earliest Final Date of a resident exam drafted by Mosaic AI = PowerBI\
      \ [Resident First Mosaic Draft Exam]. Group by Resident NPI; leave Final Date\
      \ unfiltered to get the true first date."
    display_name: Resident First Mosaic Draft Date
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - resident first draft
      - resident drafting start date
      - first drafted resident exam
$$
