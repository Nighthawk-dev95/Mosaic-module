CREATE VIEW edw_test.enterprise_analytics.mosaic_efficiency_vs_rp_avg_metric_view (
  NPI COMMENT 'Radiologist\'s 10-digit National Provider Identifier; one per radiologist. Pair with Radiologist Name for per-radiologist breakdowns.',
  Radiologist Name COMMENT 'Reading radiologist\'s name, formatted \'Last, First M\' (e.g. \'Taha, Manuel R\').',
  Team COMMENT 'The radiologist\'s own home pool, finer than Team Rolled Up (e.g. \'SEAL Team\' is a float/cross-coverage pool, not a billing practice). NOT the same as Practice (the exam site\'s practice). For PowerBI \'Team Rolled up\' / provider practice reporting, use Team Rolled Up.',
  Team Rolled Up COMMENT 'Provider Practice: the radiologist\'s home practice, i.e. Team rolled up via the team_rollups lookup (= PowerBI \'Team Rolled up\'). One value per radiologist; differs from Practice, which is the practice owning the exam site.',
  Local Region COMMENT 'One of 6 fixed regions: Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix. Keyed on the radiologist\'s Team (matches PowerBI \'0. Cur\'[Local]).',
  Practice COMMENT 'Managing Practice: the practice owning the exam site, whose exams are being read, regardless of the reading radiologist\'s Team (= PowerBI \'Practice\'). The business-facing \'By Practice\' grouping; one radiologist (e.g. SEAL Team) can read for many Practices.',
  Subspecialty COMMENT 'Subspecialty grouping carried on each exam row (the reading specialty area). Use to compare Mosaic efficiency across specialties.',
  Modality COMMENT 'Imaging modality code of the exam (e.g. CT, CR, US, BD). Drafting mode covers CR/CT; Capture covers US/BD.',
  Parent Procedure Name COMMENT 'Standardized parent procedure (exam type) at which each radiologist\'s baseline is defined, e.g. \'Head CT\'.',
  Exam Category COMMENT 'Broad exam category assigned to the parent procedure via the canonical exam-category crosswalk.',
  Exam Month COMMENT 'Month of the exam date (first day of the month). Trend-chart grain for the Efficiency Over Time / Efficiency Change Over Time pages; use for monthly trends.',
  Reporting Own Exams COMMENT 'Building block: exam count on Reporting-period exams (read in Mosaic Reporting) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Reporting Own TBWU COMMENT 'Building block: total TBWU workload units on Reporting-period exams (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Reporting Own Efficiency.',
  Reporting Own Time Sec COMMENT 'Building block: total read time in seconds on Reporting-period exams (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Reporting Own Efficiency.',
  Reporting Own Efficiency COMMENT 'TBWU per minute on Reporting exams for the selected slice (radiologist, practice, region): the side compared to the RP average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Reporting RP Avg Efficiency COMMENT 'Company-wide RP average TBWU per minute on Reporting exams: fixed benchmark, constant regardless of query grouping, over radiologists with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview).',
  Reporting Efficiency Vs RP Avg COMMENT 'Reporting Own Efficiency / Reporting RP Avg Efficiency. A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview). Company/region here; practice or radiologist rankings: mosaic_eff_vs_avg_* functions.',
  Drafting Own Exams COMMENT 'Building block: exam count on Mosaic Drafting exams (Drafting period, CR/CT only) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Drafting Own TBWU COMMENT 'Building block: total TBWU workload units on Mosaic Drafting exams (Drafting period, CR/CT only). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Drafting Own Efficiency.',
  Drafting Own Time Sec COMMENT 'Building block: total read time in seconds on Mosaic Drafting exams (Drafting period, CR/CT only). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Drafting Own Efficiency.',
  Drafting Own Efficiency COMMENT 'TBWU per minute on Drafting (CR/CT) exams for the selected slice (radiologist, practice, region): the side compared to the RP average. CR/CT on both sides (deliberate fix vs PowerBI). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Drafting RP Avg Efficiency COMMENT 'Company-wide RP average TBWU per minute on Drafting (CR/CT) exams: fixed benchmark, constant regardless of query grouping, over radiologists with >= 1 qualifying exam (min_exams does not apply). CR/CT on both sides (deliberate fix vs PowerBI). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview).',
  Drafting Efficiency Vs RP Avg COMMENT 'Drafting Own Efficiency / Drafting RP Avg Efficiency. A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide, so quote it per slice. CR/CT both sides (fix vs PowerBI). = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview).',
  Capture Own Exams COMMENT 'Building block: exam count on Mosaic Capture exams (Drafting period, US/BD only) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Capture Own TBWU COMMENT 'Building block: total TBWU workload units on Mosaic Capture exams (Drafting period, US/BD only). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Capture Own Efficiency.',
  Capture Own Time Sec COMMENT 'Building block: total read time in seconds on Mosaic Capture exams (Drafting period, US/BD only). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Capture Own Efficiency.',
  Capture Own Efficiency COMMENT 'TBWU per minute on Capture (US/BD) exams for the selected slice (radiologist, practice, region): the side compared to the RP average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Capture RP Avg Efficiency COMMENT 'Company-wide RP average TBWU per minute on Capture (US/BD) exams: fixed benchmark, constant regardless of query grouping, over radiologists with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview).',
  Capture Efficiency Vs RP Avg COMMENT 'Capture Own Efficiency / Capture RP Avg Efficiency. A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview). Company/region here; practice or radiologist rankings: mosaic_eff_vs_avg_* functions.',
  Drafting Capture Own Exams COMMENT 'Building block: exam count on Drafting-period CR/CT/US/BD exams (Drafting + Capture) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Drafting Capture Own TBWU COMMENT 'Building block: total TBWU workload units on Drafting-period CR/CT/US/BD exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Drafting Capture Own Efficiency.',
  Drafting Capture Own Time Sec COMMENT 'Building block: total read time in seconds on Drafting-period CR/CT/US/BD exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Drafting Capture Own Efficiency.',
  Drafting Capture Own Efficiency COMMENT 'TBWU per minute on Drafting + Capture (CR/CT/US/BD) exams for the selected slice (radiologist, practice, region): the side compared to the RP average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Drafting Capture RP Avg Efficiency COMMENT 'Company-wide RP average TBWU per minute on Drafting + Capture (CR/CT/US/BD) exams: fixed benchmark, constant regardless of query grouping, over radiologists with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview).',
  Drafting Capture Efficiency Vs RP Avg COMMENT 'Drafting Capture Own Efficiency / Drafting Capture RP Avg Efficiency. A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview).',
  Full Mosaic Own Exams COMMENT 'Building block: exam count on all Mosaic exams (Reporting + Drafting) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Full Mosaic Own TBWU COMMENT 'Building block: total TBWU workload units on all Mosaic exams (Reporting + Drafting). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Full Mosaic Own Efficiency.',
  Full Mosaic Own Time Sec COMMENT 'Building block: total read time in seconds on all Mosaic exams (Reporting + Drafting). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Full Mosaic Own Efficiency.',
  Full Mosaic Own Efficiency COMMENT 'TBWU per minute on Full Mosaic (Reporting + Drafting) exams for the selected slice (radiologist, practice, region): the side compared to the RP average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Full Mosaic RP Avg Efficiency COMMENT 'Headline company-wide RP average TBWU per minute on all Mosaic exams (Reporting + Drafting): fixed benchmark, constant regardless of grouping, over radiologists with >= 1 qualifying exam. = PowerBI [RP_Avg_Efficiency] / [Benchmark_FullMosaic_Only_Overall] (Mosaic Efficiency, Readtimeview).',
  Full Mosaic Efficiency Vs RP Avg COMMENT 'Headline: Full Mosaic Own Efficiency / RP Avg Efficiency. A ratio, not a percent: 1.0 = average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide; quote per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview). Company/region here; practice/rad rankings: mosaic_eff_vs_avg_* functions.',
  Both Own Exams COMMENT 'Building block: exam count on exams in all periods (Reporting + Drafting + pre-Mosaic Baseline) used for the vs RP average comparison. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). No baseline required, so a broader population than mosaic_efficiency_metric_view.',
  Both Own TBWU COMMENT 'Building block: total TBWU workload units on exams in all periods (Reporting + Drafting + pre-Mosaic Baseline). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Numerator of Both Own Efficiency.',
  Both Own Time Sec COMMENT 'Building block: total read time in seconds on exams in all periods (Reporting + Drafting + pre-Mosaic Baseline). Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). Denominator of Both Own Efficiency.',
  Both Own Efficiency COMMENT 'TBWU per minute on all-period exams (incl. Baseline) for the selected slice (radiologist, practice, region): the side compared to the RP average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview).',
  Both RP Avg Efficiency COMMENT 'Company-wide RP average TBWU per minute on all-period exams (incl. Baseline): fixed benchmark, constant regardless of query grouping, over radiologists with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview).',
  Both Efficiency Vs RP Avg COMMENT 'Both Own Efficiency / Both RP Avg Efficiency. A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview).')
COMMENT 'MOSAIC EFFICIENCY VS RP AVERAGE (draft, edw_test only). Governed replacement for the PowerBI "Mosaic Efficiency Report"\'s Readtimeview.tmdl: each radiologist\'s (or slice\'s) own TBWU-per-minute efficiency as a ratio of the qualifying-radiologist company-wide RP average, across 6 modes; outliers excluded. A DIFFERENT semantic from mosaic_efficiency_metric_view, which compares to each radiologist\'s OWN baseline, not to peers. Use for company/region figures; per-practice and per-radiologist vs-average rankings come from the mosaic_eff_vs_avg_* functions. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_test.enterprise_analytics.tbl_efficiency_rp_avg_source_vw

comment: "MOSAIC EFFICIENCY VS RP AVERAGE (draft, edw_test only). Governed replacement\
  \ for the PowerBI \"Mosaic Efficiency Report\"'s Readtimeview.tmdl: each radiologist's\
  \ (or slice's) own TBWU-per-minute efficiency as a ratio of the qualifying-radiologist\
  \ company-wide RP average, across 6 modes; outliers excluded. A DIFFERENT semantic\
  \ from mosaic_efficiency_metric_view, which compares to each radiologist's OWN baseline,\
  \ not to peers. Use for company/region figures; per-practice and per-radiologist\
  \ vs-average rankings come from the mosaic_eff_vs_avg_* functions. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md."

parameters:
  - name: min_exams
    data_type: int
    default: 1

dimensions:
  - name: NPI
    expr: source.npi
    comment: Radiologist's 10-digit National Provider Identifier; one per radiologist.
      Pair with Radiologist Name for per-radiologist breakdowns.
    display_name: Radiologist NPI
    synonyms:
      - provider NPI
      - national provider identifier
      - rad NPI

  - name: Radiologist Name
    expr: source.radiologist_name
    comment: "Reading radiologist's name, formatted 'Last, First M' (e.g. 'Taha, Manuel\
      \ R')."
    display_name: Radiologist Name
    synonyms:
      - radiologist
      - reading radiologist
      - doctor name
      - rad name

  - name: Team
    expr: source.team
    comment: "The radiologist's own home pool, finer than Team Rolled Up (e.g. 'SEAL\
      \ Team' is a float/cross-coverage pool, not a billing practice). NOT the same\
      \ as Practice (the exam site's practice). For PowerBI 'Team Rolled up' / provider\
      \ practice reporting, use Team Rolled Up."
    display_name: Radiologist Team
    synonyms:
      - sub team
      - radiologist home pool
      - reading pool

  - name: Team Rolled Up
    expr: source.team_rolled_up
    comment: "Provider Practice: the radiologist's home practice, i.e. Team rolled\
      \ up via the team_rollups lookup (= PowerBI 'Team Rolled up'). One value per\
      \ radiologist; differs from Practice, which is the practice owning the exam\
      \ site."
    display_name: Team Rolled Up (Provider Practice)
    synonyms:
      - provider practice
      - home practice
      - rolled up team
      - radiologist home practice
      - provider group

  - name: Local Region
    expr: source.local_region
    comment: "One of 6 fixed regions: Special Operations, Apex, Genesis, Maverick,\
      \ Trailblazer, Matrix. Keyed on the radiologist's Team (matches PowerBI '0.\
      \ Cur'[Local])."
    display_name: Local Region
    synonyms:
      - region
      - local
      - regional group
      - team local

  - name: Practice
    expr: source.practice
    comment: "Managing Practice: the practice owning the exam site, whose exams are\
      \ being read, regardless of the reading radiologist's Team (= PowerBI 'Practice').\
      \ The business-facing 'By Practice' grouping; one radiologist (e.g. SEAL Team)\
      \ can read for many Practices."
    display_name: Managing Practice
    synonyms:
      - site practice
      - exam site practice
      - owning practice
      - practice reading for

  - name: Subspecialty
    expr: source.subspecialty
    comment: Subspecialty grouping carried on each exam row (the reading specialty
      area). Use to compare Mosaic efficiency across specialties.
    display_name: Subspecialty
    synonyms:
      - specialty
      - reading subspecialty
      - clinical subspecialty

  - name: Modality
    expr: source.modality_code
    comment: "Imaging modality code of the exam (e.g. CT, CR, US, BD). Drafting mode\
      \ covers CR/CT; Capture covers US/BD."
    display_name: Modality
    synonyms:
      - modality code
      - imaging modality
      - scan type

  - name: Parent Procedure Name
    expr: source.parent_procedure_name
    comment: "Standardized parent procedure (exam type) at which each radiologist's\
      \ baseline is defined, e.g. 'Head CT'."
    display_name: Parent Procedure
    synonyms:
      - parent exam
      - procedure
      - exam type
      - parent procedure name

  - name: Exam Category
    expr: source.exam_category
    comment: Broad exam category assigned to the parent procedure via the canonical
      exam-category crosswalk.
    display_name: Exam Category
    synonyms:
      - exam group
      - procedure category
      - study category

  - name: Exam Month
    expr: "DATE_TRUNC('MONTH', source.exam_date)"
    comment: Month of the exam date (first day of the month). Trend-chart grain for
      the Efficiency Over Time / Efficiency Change Over Time pages; use for monthly
      trends.
    display_name: Exam Month
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - month of exam
      - read month
      - monthly trend month

measures:
  - name: Reporting Own Exams
    expr: SUM(source.exam_count) FILTER (WHERE source.period_type = 'Reporting' AND
      source.outliers = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)
    comment: "Building block: exam count on Reporting-period exams (read in Mosaic\
      \ Reporting) used for the vs RP average comparison. Outliers excluded; min_exams\
      \ gate (default 1 all-time exam per radiologist in this mode). No baseline required,\
      \ so a broader population than mosaic_efficiency_metric_view."
    display_name: Reporting Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - reporting own exam count
      - reporting individual exams vs peers

  - name: Reporting Own TBWU
    expr: SUM(source.tbwu) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers
      = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)
    comment: "Building block: total TBWU workload units on Reporting-period exams\
      \ (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Numerator of Reporting Own Efficiency."
    display_name: Reporting Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - reporting own workload units
      - reporting individual TBWU

  - name: Reporting Own Time Sec
    expr: SUM(source.time_sec) FILTER (WHERE source.period_type = 'Reporting' AND
      source.outliers = 'Excluded' AND source.rad_total_reporting_all_excl >= min_exams)
    comment: "Building block: total read time in seconds on Reporting-period exams\
      \ (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Denominator of Reporting Own Efficiency."
    display_name: Reporting Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - reporting own read time seconds
      - reporting individual read time

  - name: Reporting Own Efficiency
    expr: MEASURE(`Reporting Own TBWU`) / (MEASURE(`Reporting Own Time Sec`) / 60)
    comment: "TBWU per minute on Reporting exams for the selected slice (radiologist,\
      \ practice, region): the side compared to the RP average. Outliers excluded;\
      \ min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI\
      \ [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Reporting Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - reporting individual efficiency
      - reporting own TBWU per minute
      - reporting radiologist own productivity

  - name: Reporting RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_reporting_tbwu) / (ANY_VALUE(source.rp_avg_reporting_time)
      / 60)
    comment: "Company-wide RP average TBWU per minute on Reporting exams: fixed benchmark,\
      \ constant regardless of query grouping, over radiologists with >= 1 qualifying\
      \ exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency,\
      \ Readtimeview)."
    display_name: Reporting RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - reporting RP average
      - reporting company average efficiency
      - reporting peer benchmark

  - name: Reporting Efficiency Vs RP Avg
    expr: MEASURE(`Reporting Own Efficiency`) / MEASURE(`Reporting RP Avg Efficiency`)
    comment: "Reporting Own Efficiency / Reporting RP Avg Efficiency. A ratio, not\
      \ a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below.\
      \ Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB]\
      \ (Mosaic Efficiency, Readtimeview). Company/region here; practice or radiologist\
      \ rankings: mosaic_eff_vs_avg_* functions."
    display_name: Reporting Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - reporting efficiency vs company average
      - reporting efficiency vs peers
      - reporting vs RP average
      - reporting efficiency index

  - name: Drafting Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND\
      \ source.rad_total_drafting_cr_ct_all_excl >= min_exams)"
    comment: "Building block: exam count on Mosaic Drafting exams (Drafting period,\
      \ CR/CT only) used for the vs RP average comparison. Outliers excluded; min_exams\
      \ gate (default 1 all-time exam per radiologist in this mode). No baseline required,\
      \ so a broader population than mosaic_efficiency_metric_view."
    display_name: Drafting Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting own exam count
      - drafting individual exams vs peers

  - name: Drafting Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.rad_total_drafting_cr_ct_all_excl\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units on Mosaic Drafting exams (Drafting\
      \ period, CR/CT only). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Numerator of Drafting Own Efficiency."
    display_name: Drafting Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting own workload units
      - drafting individual TBWU

  - name: Drafting Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND\
      \ source.rad_total_drafting_cr_ct_all_excl >= min_exams)"
    comment: "Building block: total read time in seconds on Mosaic Drafting exams\
      \ (Drafting period, CR/CT only). Outliers excluded; min_exams gate (default\
      \ 1 all-time exam per radiologist in this mode). Denominator of Drafting Own\
      \ Efficiency."
    display_name: Drafting Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting own read time seconds
      - drafting individual read time

  - name: Drafting Own Efficiency
    expr: MEASURE(`Drafting Own TBWU`) / (MEASURE(`Drafting Own Time Sec`) / 60)
    comment: "TBWU per minute on Drafting (CR/CT) exams for the selected slice (radiologist,\
      \ practice, region): the side compared to the RP average. CR/CT on both sides\
      \ (deliberate fix vs PowerBI). Outliers excluded; min_exams gate (default 1\
      \ all-time exam per radiologist in this mode). = PowerBI [Mosaic_Efficiency_NB]\
      \ (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting individual efficiency
      - drafting own TBWU per minute
      - drafting radiologist own productivity

  - name: Drafting RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_drafting_tbwu) / (ANY_VALUE(source.rp_avg_drafting_time)
      / 60)
    comment: "Company-wide RP average TBWU per minute on Drafting (CR/CT) exams: fixed\
      \ benchmark, constant regardless of query grouping, over radiologists with >=\
      \ 1 qualifying exam (min_exams does not apply). CR/CT on both sides (deliberate\
      \ fix vs PowerBI). = PowerBI [RP_Avg_Efficiency] (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting RP average
      - drafting company average efficiency
      - drafting peer benchmark

  - name: Drafting Efficiency Vs RP Avg
    expr: MEASURE(`Drafting Own Efficiency`) / MEASURE(`Drafting RP Avg Efficiency`)
    comment: "Drafting Own Efficiency / Drafting RP Avg Efficiency. A ratio, not a\
      \ percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below.\
      \ Equals 1.0 company-wide, so quote it per slice. CR/CT both sides (fix vs PowerBI).\
      \ = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting efficiency vs company average
      - drafting efficiency vs peers
      - drafting vs RP average
      - drafting efficiency index

  - name: Capture Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND\
      \ source.rad_total_capture_all_excl >= min_exams)"
    comment: "Building block: exam count on Mosaic Capture exams (Drafting period,\
      \ US/BD only) used for the vs RP average comparison. Outliers excluded; min_exams\
      \ gate (default 1 all-time exam per radiologist in this mode). No baseline required,\
      \ so a broader population than mosaic_efficiency_metric_view."
    display_name: Capture Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - capture own exam count
      - capture individual exams vs peers

  - name: Capture Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.rad_total_capture_all_excl\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units on Mosaic Capture exams (Drafting\
      \ period, US/BD only). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Numerator of Capture Own Efficiency."
    display_name: Capture Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - capture own workload units
      - capture individual TBWU

  - name: Capture Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD') AND\
      \ source.rad_total_capture_all_excl >= min_exams)"
    comment: "Building block: total read time in seconds on Mosaic Capture exams (Drafting\
      \ period, US/BD only). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Denominator of Capture Own Efficiency."
    display_name: Capture Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - capture own read time seconds
      - capture individual read time

  - name: Capture Own Efficiency
    expr: MEASURE(`Capture Own TBWU`) / (MEASURE(`Capture Own Time Sec`) / 60)
    comment: "TBWU per minute on Capture (US/BD) exams for the selected slice (radiologist,\
      \ practice, region): the side compared to the RP average. Outliers excluded;\
      \ min_exams gate (default 1 all-time exam per radiologist in this mode). = PowerBI\
      \ [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Capture Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - capture individual efficiency
      - capture own TBWU per minute
      - capture radiologist own productivity

  - name: Capture RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_capture_tbwu) / (ANY_VALUE(source.rp_avg_capture_time)
      / 60)
    comment: "Company-wide RP average TBWU per minute on Capture (US/BD) exams: fixed\
      \ benchmark, constant regardless of query grouping, over radiologists with >=\
      \ 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency]\
      \ (Mosaic Efficiency, Readtimeview)."
    display_name: Capture RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - capture RP average
      - capture company average efficiency
      - capture peer benchmark

  - name: Capture Efficiency Vs RP Avg
    expr: MEASURE(`Capture Own Efficiency`) / MEASURE(`Capture RP Avg Efficiency`)
    comment: "Capture Own Efficiency / Capture RP Avg Efficiency. A ratio, not a percent\
      \ change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0\
      \ company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic\
      \ Efficiency, Readtimeview). Company/region here; practice or radiologist rankings:\
      \ mosaic_eff_vs_avg_* functions."
    display_name: Capture Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - capture efficiency vs company average
      - capture efficiency vs peers
      - capture vs RP average
      - capture efficiency index

  - name: Drafting Capture Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US',\
      \ 'BD') AND source.rad_total_drafting_capture_all_excl >= min_exams)"
    comment: "Building block: exam count on Drafting-period CR/CT/US/BD exams (Drafting\
      \ + Capture) used for the vs RP average comparison. Outliers excluded; min_exams\
      \ gate (default 1 all-time exam per radiologist in this mode). No baseline required,\
      \ so a broader population than mosaic_efficiency_metric_view."
    display_name: Drafting + Capture Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting plus capture own exam count
      - drafting plus capture individual exams vs peers

  - name: Drafting Capture Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.rad_total_drafting_capture_all_excl\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units on Drafting-period CR/CT/US/BD\
      \ exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Numerator of Drafting Capture Own Efficiency."
    display_name: Drafting + Capture Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting plus capture own workload units
      - drafting plus capture individual TBWU

  - name: Drafting Capture Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type = 'Drafting' AND\
      \ source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US',\
      \ 'BD') AND source.rad_total_drafting_capture_all_excl >= min_exams)"
    comment: "Building block: total read time in seconds on Drafting-period CR/CT/US/BD\
      \ exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 all-time\
      \ exam per radiologist in this mode). Denominator of Drafting Capture Own Efficiency."
    display_name: Drafting + Capture Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting plus capture own read time seconds
      - drafting plus capture individual read time

  - name: Drafting Capture Own Efficiency
    expr: MEASURE(`Drafting Capture Own TBWU`) / (MEASURE(`Drafting Capture Own Time
      Sec`) / 60)
    comment: "TBWU per minute on Drafting + Capture (CR/CT/US/BD) exams for the selected\
      \ slice (radiologist, practice, region): the side compared to the RP average.\
      \ Outliers excluded; min_exams gate (default 1 all-time exam per radiologist\
      \ in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting + Capture Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting plus capture individual efficiency
      - drafting plus capture own TBWU per minute
      - drafting plus capture radiologist own productivity

  - name: Drafting Capture RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_drafting_capture_tbwu) / (ANY_VALUE(source.rp_avg_drafting_capture_time)
      / 60)
    comment: "Company-wide RP average TBWU per minute on Drafting + Capture (CR/CT/US/BD)\
      \ exams: fixed benchmark, constant regardless of query grouping, over radiologists\
      \ with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency]\
      \ (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting + Capture RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting plus capture RP average
      - drafting plus capture company average efficiency
      - drafting plus capture peer benchmark

  - name: Drafting Capture Efficiency Vs RP Avg
    expr: MEASURE(`Drafting Capture Own Efficiency`) / MEASURE(`Drafting Capture RP
      Avg Efficiency`)
    comment: "Drafting Capture Own Efficiency / Drafting Capture RP Avg Efficiency.\
      \ A ratio, not a percent change: 1.0 = exactly average, 1.10 = 10% above, 0.92\
      \ = 8% below. Equals 1.0 company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB]\
      \ (Mosaic Efficiency, Readtimeview)."
    display_name: Drafting + Capture Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting plus capture efficiency vs company average
      - drafting plus capture efficiency vs peers
      - drafting plus capture vs RP average
      - drafting plus capture efficiency index

  - name: Full Mosaic Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type IN ('Reporting',\
      \ 'Drafting') AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl\
      \ >= min_exams)"
    comment: "Building block: exam count on all Mosaic exams (Reporting + Drafting)\
      \ used for the vs RP average comparison. Outliers excluded; min_exams gate (default\
      \ 1 all-time exam per radiologist in this mode). No baseline required, so a\
      \ broader population than mosaic_efficiency_metric_view."
    display_name: Full Mosaic Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - full mosaic own exam count
      - full mosaic individual exams vs peers

  - name: Full Mosaic Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting')\
      \ AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units on all Mosaic exams (Reporting\
      \ + Drafting). Outliers excluded; min_exams gate (default 1 all-time exam per\
      \ radiologist in this mode). Numerator of Full Mosaic Own Efficiency."
    display_name: Full Mosaic Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - full mosaic own workload units
      - full mosaic individual TBWU

  - name: Full Mosaic Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type IN ('Reporting',\
      \ 'Drafting') AND source.outliers = 'Excluded' AND source.rad_total_full_mosaic_all_excl\
      \ >= min_exams)"
    comment: "Building block: total read time in seconds on all Mosaic exams (Reporting\
      \ + Drafting). Outliers excluded; min_exams gate (default 1 all-time exam per\
      \ radiologist in this mode). Denominator of Full Mosaic Own Efficiency."
    display_name: Full Mosaic Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - full mosaic own read time seconds
      - full mosaic individual read time

  - name: Full Mosaic Own Efficiency
    expr: MEASURE(`Full Mosaic Own TBWU`) / (MEASURE(`Full Mosaic Own Time Sec`) /
      60)
    comment: "TBWU per minute on Full Mosaic (Reporting + Drafting) exams for the\
      \ selected slice (radiologist, practice, region): the side compared to the RP\
      \ average. Outliers excluded; min_exams gate (default 1 all-time exam per radiologist\
      \ in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Full Mosaic Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - full mosaic individual efficiency
      - full mosaic own TBWU per minute
      - full mosaic radiologist own productivity

  - name: Full Mosaic RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_full_mosaic_tbwu) / (ANY_VALUE(source.rp_avg_full_mosaic_time)
      / 60)
    comment: "Headline company-wide RP average TBWU per minute on all Mosaic exams\
      \ (Reporting + Drafting): fixed benchmark, constant regardless of grouping,\
      \ over radiologists with >= 1 qualifying exam. = PowerBI [RP_Avg_Efficiency]\
      \ / [Benchmark_FullMosaic_Only_Overall] (Mosaic Efficiency, Readtimeview)."
    display_name: Full Mosaic RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - full mosaic RP average
      - full mosaic company average efficiency
      - full mosaic peer benchmark
      - RP benchmark
      - company-wide efficiency benchmark
      - overall RP average

  - name: Full Mosaic Efficiency Vs RP Avg
    expr: MEASURE(`Full Mosaic Own Efficiency`) / MEASURE(`Full Mosaic RP Avg Efficiency`)
    comment: "Headline: Full Mosaic Own Efficiency / RP Avg Efficiency. A ratio, not\
      \ a percent: 1.0 = average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0 company-wide;\
      \ quote per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic Efficiency, Readtimeview).\
      \ Company/region here; practice/rad rankings: mosaic_eff_vs_avg_* functions."
    display_name: Full Mosaic Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - full mosaic efficiency vs company average
      - full mosaic efficiency vs peers
      - full mosaic vs RP average
      - full mosaic efficiency index
      - efficiency vs company average
      - efficiency vs peers

  - name: Both Own Exams
    expr: "SUM(source.exam_count) FILTER (WHERE source.period_type IN ('Reporting',\
      \ 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl\
      \ >= min_exams)"
    comment: "Building block: exam count on exams in all periods (Reporting + Drafting\
      \ + pre-Mosaic Baseline) used for the vs RP average comparison. Outliers excluded;\
      \ min_exams gate (default 1 all-time exam per radiologist in this mode). No\
      \ baseline required, so a broader population than mosaic_efficiency_metric_view."
    display_name: Both (All Periods) Own Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - both modes own exam count
      - both modes individual exams vs peers

  - name: Both Own TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting',\
      \ 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units on exams in all periods (Reporting\
      \ + Drafting + pre-Mosaic Baseline). Outliers excluded; min_exams gate (default\
      \ 1 all-time exam per radiologist in this mode). Numerator of Both Own Efficiency."
    display_name: Both (All Periods) Own TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - both modes own workload units
      - both modes individual TBWU

  - name: Both Own Time Sec
    expr: "SUM(source.time_sec) FILTER (WHERE source.period_type IN ('Reporting',\
      \ 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND source.rad_total_both_all_excl\
      \ >= min_exams)"
    comment: "Building block: total read time in seconds on exams in all periods (Reporting\
      \ + Drafting + pre-Mosaic Baseline). Outliers excluded; min_exams gate (default\
      \ 1 all-time exam per radiologist in this mode). Denominator of Both Own Efficiency."
    display_name: Both (All Periods) Own Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - both modes own read time seconds
      - both modes individual read time

  - name: Both Own Efficiency
    expr: MEASURE(`Both Own TBWU`) / (MEASURE(`Both Own Time Sec`) / 60)
    comment: "TBWU per minute on all-period exams (incl. Baseline) for the selected\
      \ slice (radiologist, practice, region): the side compared to the RP average.\
      \ Outliers excluded; min_exams gate (default 1 all-time exam per radiologist\
      \ in this mode). = PowerBI [Mosaic_Efficiency_NB] (Mosaic Efficiency, Readtimeview)."
    display_name: Both (All Periods) Own Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - both modes individual efficiency
      - both modes own TBWU per minute
      - both modes radiologist own productivity

  - name: Both RP Avg Efficiency
    expr: ANY_VALUE(source.rp_avg_both_tbwu) / (ANY_VALUE(source.rp_avg_both_time)
      / 60)
    comment: "Company-wide RP average TBWU per minute on all-period exams (incl. Baseline):\
      \ fixed benchmark, constant regardless of query grouping, over radiologists\
      \ with >= 1 qualifying exam (min_exams does not apply). = PowerBI [RP_Avg_Efficiency]\
      \ (Mosaic Efficiency, Readtimeview)."
    display_name: Both (All Periods) RP Average Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - both modes RP average
      - both modes company average efficiency
      - both modes peer benchmark

  - name: Both Efficiency Vs RP Avg
    expr: MEASURE(`Both Own Efficiency`) / MEASURE(`Both RP Avg Efficiency`)
    comment: "Both Own Efficiency / Both RP Avg Efficiency. A ratio, not a percent\
      \ change: 1.0 = exactly average, 1.10 = 10% above, 0.92 = 8% below. Equals 1.0\
      \ company-wide, so quote it per slice. = PowerBI [Efficiency_vs_RP_Avg_NB] (Mosaic\
      \ Efficiency, Readtimeview)."
    display_name: Both (All Periods) Efficiency vs RP Average
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - both modes efficiency vs company average
      - both modes efficiency vs peers
      - both modes vs RP average
      - both modes efficiency index
$$
