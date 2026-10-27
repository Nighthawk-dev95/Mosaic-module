CREATE VIEW edw_test.enterprise_analytics.mosaic_efficiency_metric_view (
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
  Exam Week COMMENT 'Week of the exam date (week starting Monday). Weekly grain for the Efficiency Change Time Series page (= PowerBI Week_Date); finer-grained sibling of Exam Month.',
  Reporting Mosaic Exams COMMENT 'Count of Reporting-period exams (read in Mosaic Reporting) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on Reporting-period exams (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Reporting Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on Reporting exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Reporting Mosaic Efficiency and Reporting Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. All modalities, not limited to this mode\'s modalities. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = each radiologist\'s own baseline rate (TBWU/min) x each exam\'s own read time, over Reporting-period exams (read in Mosaic Reporting). Divide by Reporting Mosaic Time Sec to get Reporting Baseline Efficiency.',
  Reporting Mosaic Efficiency COMMENT 'TBWU per minute on Reporting-period exams (read in Mosaic Reporting). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Reporting Only). Company/region trends here; practice, radiologist or site splits: mosaic_eff_* functions.',
  Reporting Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using each radiologist\'s own baseline rate, time-weighted by the read time of the same Reporting exams: the like-for-like comparison point for Reporting Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Pct Change Vs Baseline COMMENT 'Efficiency change vs baseline, Reporting exams: (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Reporting Only).',
  Reporting Implied Read Time Savings Pct COMMENT 'Implied read-time savings, Reporting exams: baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work than baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Reporting Only).',
  Drafting Mosaic Exams COMMENT 'Count of Mosaic Drafting exams (Drafting period, CR/CT only) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on Mosaic Drafting exams (Drafting period, CR/CT only). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Drafting Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on Drafting (CR/CT) exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Drafting Mosaic Efficiency and Drafting Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. All modalities, not limited to this mode\'s modalities. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = each radiologist\'s own baseline rate (TBWU/min) x each exam\'s own read time, over Mosaic Drafting exams (Drafting period, CR/CT only). Divide by Drafting Mosaic Time Sec to get Drafting Baseline Efficiency.',
  Drafting Mosaic Efficiency COMMENT 'TBWU per minute on Mosaic Drafting exams (Drafting period, CR/CT only). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Drafting Only). Company/region trends here; practice, radiologist or site splits: mosaic_eff_* functions.',
  Drafting Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using each radiologist\'s own baseline rate, time-weighted by the read time of the same Drafting (CR/CT) exams: the like-for-like comparison point for Drafting Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Pct Change Vs Baseline COMMENT 'Efficiency change vs baseline, Drafting (CR/CT) exams: (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Drafting Only).',
  Drafting Implied Read Time Savings Pct COMMENT 'Implied read-time savings, Drafting (CR/CT) exams: baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work than baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Drafting Only).',
  Capture Mosaic Exams COMMENT 'Count of Mosaic Capture exams (Drafting period, US/BD only) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Capture Only).',
  Capture Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on Mosaic Capture exams (Drafting period, US/BD only). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Capture Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Capture Only).',
  Capture Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on Capture (US/BD) exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Capture Mosaic Efficiency and Capture Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Capture Only).',
  Capture Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. Limited to US/BD. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Capture Only).',
  Capture Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = the US/BD-specific baseline rate (TBWU/min) x each exam\'s own read time, over Mosaic Capture exams (Drafting period, US/BD only). Divide by Capture Mosaic Time Sec to get Capture Baseline Efficiency.',
  Capture Mosaic Efficiency COMMENT 'TBWU per minute on Mosaic Capture exams (Drafting period, US/BD only). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Capture Only). Company/region trends here; practice, radiologist or site splits: mosaic_eff_* functions.',
  Capture Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using the US/BD-specific baseline rate, time-weighted by the read time of the same Capture (US/BD) exams: the like-for-like comparison point for Capture Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Capture Only).',
  Capture Pct Change Vs Baseline COMMENT 'Efficiency change vs baseline, Capture (US/BD) exams: (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Capture Only).',
  Capture Implied Read Time Savings Pct COMMENT 'Implied read-time savings, Capture (US/BD) exams: baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work than baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Capture Only).',
  Drafting Capture Mosaic Exams COMMENT 'Count of Drafting-period CR/CT/US/BD exams (Drafting + Capture) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on Drafting-period CR/CT/US/BD exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Drafting Capture Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on Drafting + Capture (CR/CT/US/BD) exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Drafting Capture Mosaic Efficiency and Drafting Capture Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. All modalities, not limited to this mode\'s modalities. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = the standard all-modality blended baseline (TBWU/min) x each exam\'s own read time, over Drafting-period CR/CT/US/BD exams (Drafting + Capture). Divide by Drafting Capture Mosaic Time Sec to get Drafting Capture Baseline Efficiency.',
  Drafting Capture Mosaic Efficiency COMMENT 'TBWU per minute on Drafting-period CR/CT/US/BD exams (Drafting + Capture). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using the standard all-modality blended baseline, time-weighted by the read time of the same Drafting + Capture (CR/CT/US/BD) exams: the like-for-like comparison point for Drafting Capture Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Pct Change Vs Baseline COMMENT 'Efficiency change vs baseline, Drafting + Capture (CR/CT/US/BD) exams: (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Drafting + Capture).',
  Drafting Capture Implied Read Time Savings Pct COMMENT 'Implied read-time savings, Drafting + Capture (CR/CT/US/BD) exams: baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work than baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Drafting + Capture).',
  Full Mosaic Mosaic Exams COMMENT 'Count of all Mosaic exams (Reporting + Drafting) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Full Mosaic).',
  Full Mosaic Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on all Mosaic exams (Reporting + Drafting). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Full Mosaic Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Full Mosaic).',
  Full Mosaic Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on Full Mosaic (Reporting + Drafting) exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Full Mosaic Mosaic Efficiency and Full Mosaic Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Full Mosaic).',
  Full Mosaic Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. All modalities, not limited to this mode\'s modalities. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Full Mosaic).',
  Full Mosaic Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = each radiologist\'s own baseline rate (TBWU/min) x each exam\'s own read time, over all Mosaic exams (Reporting + Drafting). Divide by Full Mosaic Mosaic Time Sec to get Full Mosaic Baseline Efficiency.',
  Full Mosaic Mosaic Efficiency COMMENT 'Headline \'overall\' Mosaic efficiency: TBWU per minute on all Mosaic exams (Reporting + Drafting); ungrouped = the app\'s \'RP Benchmark\' tile. Outliers excluded; min_exams gate (default 1). = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Full Mosaic). Company/region here; practice/rad/site splits: mosaic_eff_* functions.',
  Full Mosaic Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using each radiologist\'s own baseline rate, time-weighted by the read time of the same Full Mosaic (Reporting + Drafting) exams: the like-for-like comparison point for Full Mosaic Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Full Mosaic).',
  Full Mosaic Pct Change Vs Baseline COMMENT 'Headline efficiency change vs baseline, all Mosaic exams (Reporting + Drafting): (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU/min than pre-Mosaic. Outliers excluded; min_exams gate. = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Full Mosaic). Company/region here; practice/rad/site splits: mosaic_eff_* functions.',
  Full Mosaic Implied Read Time Savings Pct COMMENT 'Headline implied read-time savings, all Mosaic exams: baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work). Outliers excluded; min_exams gate. = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Full Mosaic). Company/region here; practice/rad/site splits: mosaic_eff_* functions.',
  Both Mosaic Exams COMMENT 'Count of exams in all periods (Reporting + Drafting + pre-Mosaic Baseline) for radiologists with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt] (Mosaic Efficiency, Both).',
  Both Mosaic TBWU COMMENT 'Building block: total TBWU workload units (same unit as RPWU) on exams in all periods (Reporting + Drafting + pre-Mosaic Baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Numerator of Both Mosaic Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Both).',
  Both Mosaic Time Sec COMMENT 'Building block: total adjusted read time in seconds on all-period exams (incl. Baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator of Both Mosaic Efficiency and Both Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Both).',
  Both Baseline Exams COMMENT 'Count of the same qualifying radiologists\' pre-Mosaic Baseline-period exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded. All modalities, not limited to this mode\'s modalities. Context only; not used in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency, Both).',
  Both Baseline Contrib COMMENT 'Building block: time-weighted baseline contribution = each radiologist\'s own baseline rate (TBWU/min) x each exam\'s own read time, over exams in all periods (Reporting + Drafting + pre-Mosaic Baseline). Divide by Both Mosaic Time Sec to get Both Baseline Efficiency.',
  Both Mosaic Efficiency COMMENT 'TBWU per minute on exams in all periods (Reporting + Drafting + pre-Mosaic Baseline). Includes Baseline-period exams, so it is an all-period figure, not Mosaic-only. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency, Both).',
  Both Baseline Efficiency COMMENT 'Pre-Mosaic baseline TBWU per minute, using each radiologist\'s own baseline rate, time-weighted by the read time of the same all-period exams (incl. Baseline): the like-for-like comparison point for Both Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Both).',
  Both Pct Change Vs Baseline COMMENT 'Efficiency change vs baseline, all-period exams (incl. Baseline): (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Both).',
  Both Implied Read Time Savings Pct COMMENT 'Implied read-time savings, all-period exams (incl. Baseline): baseline / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of work than baseline). Outliers excluded; min_exams gate (default 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Both).')
COMMENT 'MOSAIC EFFICIENCY SEMANTIC LAYER (draft, edw_test only). Governed replacement for the PowerBI "Mosaic Efficiency Report"\'s Parameter/Timeline/Mode_Lines tables: TBWU-per-minute efficiency vs. each radiologist\'s own pre-Mosaic PowerScribe baseline, plus implied read-time savings, across 6 modes (Reporting/Drafting/Capture/Drafting+Capture/Full Mosaic/Both), with a qualification gate (min_exams threshold + has-both-baseline-and-mosaic) baked into every measure; outliers excluded. Source is mosaic_efficiency_exam_level_mv, a daily (7:30 AM CT) snapshot of tbl_efficiency_exam_level_vw used for speed, so figures reflect data as of the morning refresh. Use for company/region totals and trends; per-practice, per-radiologist and per-site breakdowns come from the mosaic_eff_* functions. Readtimeview\'s separate "efficiency vs RP average" semantic is NOT part of this view - see mosaic_efficiency_vs_rp_avg_metric_view and tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_test.enterprise_analytics.mosaic_efficiency_exam_level_mv

comment: "MOSAIC EFFICIENCY SEMANTIC LAYER (draft, edw_test only). Governed replacement\
  \ for the PowerBI \"Mosaic Efficiency Report\"'s Parameter/Timeline/Mode_Lines tables:\
  \ TBWU-per-minute efficiency vs. each radiologist's own pre-Mosaic PowerScribe baseline,\
  \ plus implied read-time savings, across 6 modes (Reporting/Drafting/Capture/Drafting+Capture/Full\
  \ Mosaic/Both), with a qualification gate (min_exams threshold + has-both-baseline-and-mosaic)\
  \ baked into every measure; outliers excluded. Source is mosaic_efficiency_exam_level_mv,\
  \ a daily (7:30 AM CT) snapshot of tbl_efficiency_exam_level_vw used for speed,\
  \ so figures reflect data as of the morning refresh. Use for company/region totals\
  \ and trends; per-practice, per-radiologist and per-site breakdowns come from the\
  \ mosaic_eff_* functions. Readtimeview's separate \"efficiency vs RP average\" semantic\
  \ is NOT part of this view - see mosaic_efficiency_vs_rp_avg_metric_view and tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md."

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
      - Managing Practice
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

  - name: Exam Week
    expr: "DATE_TRUNC('WEEK', source.exam_date)"
    comment: Week of the exam date (week starting Monday). Weekly grain for the Efficiency
      Change Time Series page (= PowerBI Week_Date); finer-grained sibling of Exam
      Month.
    display_name: Exam Week
    synonyms:
      - week of exam
      - read week
      - weekly trend week
      - week date

measures:
  - name: Reporting Mosaic Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers
      = 'Excluded' AND source.reporting_exam_count >= min_exams)
    comment: "Count of Reporting-period exams (read in Mosaic Reporting) for radiologists\
      \ with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam\
      \ per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt]\
      \ (Mosaic Efficiency, Reporting Only)."
    display_name: Reporting Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - reporting exam volume
      - reporting exams read
      - number of reporting exams

  - name: Reporting Mosaic TBWU
    expr: SUM(source.tbwu) FILTER (WHERE source.period_type = 'Reporting' AND source.outliers
      = 'Excluded' AND source.reporting_exam_count >= min_exams)
    comment: "Building block: total TBWU workload units (same unit as RPWU) on Reporting-period\
      \ exams (read in Mosaic Reporting). Outliers excluded; min_exams gate (default\
      \ 1 exam per rad in this mode). Numerator of Reporting Mosaic Efficiency. =\
      \ PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Reporting Only)."
    display_name: Reporting Mosaic TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - reporting workload units
      - reporting RPWU
      - reporting total TBWU

  - name: Reporting Mosaic Time Sec
    expr: SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Reporting'
      AND source.outliers = 'Excluded' AND source.reporting_exam_count >= min_exams)
    comment: "Building block: total adjusted read time in seconds on Reporting exams.\
      \ Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Denominator\
      \ of Reporting Mosaic Efficiency and Reporting Baseline Efficiency. = PowerBI\
      \ [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Reporting Only)."
    display_name: Reporting Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - reporting read time seconds
      - reporting total read time
      - reporting reading time

  - name: Reporting Baseline Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers
      = 'Excluded' AND source.reporting_exam_count >= min_exams)
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ All modalities, not limited to this mode's modalities. Context only; not used\
      \ in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency,\
      \ Reporting Only)."
    display_name: Reporting Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - reporting pre-Mosaic exams
      - reporting legacy VR exams
      - reporting PowerScribe baseline exams

  - name: Reporting Baseline Contrib
    expr: SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE
      source.period_type = 'Reporting' AND source.outliers = 'Excluded' AND source.reporting_exam_count
      >= min_exams)
    comment: "Building block: time-weighted baseline contribution = each radiologist's\
      \ own baseline rate (TBWU/min) x each exam's own read time, over Reporting-period\
      \ exams (read in Mosaic Reporting). Divide by Reporting Mosaic Time Sec to get\
      \ Reporting Baseline Efficiency."
    display_name: Reporting Baseline Contribution (Helper)
    synonyms:
      - reporting baseline numerator
      - reporting time weighted baseline contribution

  - name: Reporting Mosaic Efficiency
    expr: MEASURE(`Reporting Mosaic TBWU`) / (MEASURE(`Reporting Mosaic Time Sec`)
      / 60)
    comment: "TBWU per minute on Reporting-period exams (read in Mosaic Reporting).\
      \ Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice\
      \ by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency,\
      \ Reporting Only). Company/region trends here; practice, radiologist or site\
      \ splits: mosaic_eff_* functions."
    display_name: Reporting Mosaic Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - reporting TBWU per minute
      - reporting productivity on Mosaic
      - reporting efficiency on Mosaic

  - name: Reporting Baseline Efficiency
    expr: MEASURE(`Reporting Baseline Contrib`) / MEASURE(`Reporting Mosaic Time Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using each radiologist's own baseline\
      \ rate, time-weighted by the read time of the same Reporting exams: the like-for-like\
      \ comparison point for Reporting Mosaic Efficiency. Outliers excluded. = PowerBI\
      \ [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Reporting Only)."
    display_name: Reporting Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - reporting baseline TBWU per minute
      - reporting pre-Mosaic efficiency
      - reporting legacy VR efficiency

  - name: Reporting Pct Change Vs Baseline
    expr: (MEASURE(`Reporting Mosaic Efficiency`) - MEASURE(`Reporting Baseline Efficiency`))
      / MEASURE(`Reporting Baseline Efficiency`)
    comment: "Efficiency change vs baseline, Reporting exams: (Mosaic - baseline)\
      \ / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative\
      \ = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this\
      \ mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Reporting Only)."
    display_name: Reporting Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - reporting efficiency gain vs baseline
      - reporting % change vs baseline
      - reporting productivity lift vs baseline

  - name: Reporting Implied Read Time Savings Pct
    expr: MEASURE(`Reporting Baseline Efficiency`) / MEASURE(`Reporting Mosaic Efficiency`)
      - 1
    comment: "Implied read-time savings, Reporting exams: baseline / Mosaic efficiency\
      \ - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per unit of\
      \ work than baseline). Outliers excluded; min_exams gate (default 1 exam per\
      \ rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency, Reporting\
      \ Only)."
    display_name: Reporting Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - reporting read time savings
      - reporting time saved vs baseline
      - reporting read time reduction

  - name: Drafting Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count\
      \ >= min_exams)"
    comment: "Count of Mosaic Drafting exams (Drafting period, CR/CT only) for radiologists\
      \ with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam\
      \ per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt]\
      \ (Mosaic Efficiency, Drafting Only)."
    display_name: Drafting Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting exam volume
      - drafting exams read
      - number of drafting exams

  - name: Drafting Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT') AND source.drafting_exam_count\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units (same unit as RPWU) on Mosaic\
      \ Drafting exams (Drafting period, CR/CT only). Outliers excluded; min_exams\
      \ gate (default 1 exam per rad in this mode). Numerator of Drafting Mosaic Efficiency.\
      \ = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Drafting Only)."
    display_name: Drafting Mosaic TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting workload units
      - drafting RPWU
      - drafting total TBWU

  - name: Drafting Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting'\
      \ AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT')\
      \ AND source.drafting_exam_count >= min_exams)"
    comment: "Building block: total adjusted read time in seconds on Drafting (CR/CT)\
      \ exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode).\
      \ Denominator of Drafting Mosaic Efficiency and Drafting Baseline Efficiency.\
      \ = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Drafting Only)."
    display_name: Drafting Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting read time seconds
      - drafting total read time
      - drafting reading time

  - name: Drafting Baseline Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers
      = 'Excluded' AND source.drafting_exam_count >= min_exams)
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ All modalities, not limited to this mode's modalities. Context only; not used\
      \ in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency,\
      \ Drafting Only)."
    display_name: Drafting Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting pre-Mosaic exams
      - drafting legacy VR exams
      - drafting PowerScribe baseline exams

  - name: Drafting Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE\
      \ source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code\
      \ IN ('CR', 'CT') AND source.drafting_exam_count >= min_exams)"
    comment: "Building block: time-weighted baseline contribution = each radiologist's\
      \ own baseline rate (TBWU/min) x each exam's own read time, over Mosaic Drafting\
      \ exams (Drafting period, CR/CT only). Divide by Drafting Mosaic Time Sec to\
      \ get Drafting Baseline Efficiency."
    display_name: Drafting Baseline Contribution (Helper)
    synonyms:
      - drafting baseline numerator
      - drafting time weighted baseline contribution

  - name: Drafting Mosaic Efficiency
    expr: MEASURE(`Drafting Mosaic TBWU`) / (MEASURE(`Drafting Mosaic Time Sec`) /
      60)
    comment: "TBWU per minute on Mosaic Drafting exams (Drafting period, CR/CT only).\
      \ Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice\
      \ by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency,\
      \ Drafting Only). Company/region trends here; practice, radiologist or site\
      \ splits: mosaic_eff_* functions."
    display_name: Drafting Mosaic Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting TBWU per minute
      - drafting productivity on Mosaic
      - drafting efficiency on Mosaic

  - name: Drafting Baseline Efficiency
    expr: MEASURE(`Drafting Baseline Contrib`) / MEASURE(`Drafting Mosaic Time Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using each radiologist's own baseline\
      \ rate, time-weighted by the read time of the same Drafting (CR/CT) exams: the\
      \ like-for-like comparison point for Drafting Mosaic Efficiency. Outliers excluded.\
      \ = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Drafting Only)."
    display_name: Drafting Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting baseline TBWU per minute
      - drafting pre-Mosaic efficiency
      - drafting legacy VR efficiency

  - name: Drafting Pct Change Vs Baseline
    expr: (MEASURE(`Drafting Mosaic Efficiency`) - MEASURE(`Drafting Baseline Efficiency`))
      / MEASURE(`Drafting Baseline Efficiency`)
    comment: "Efficiency change vs baseline, Drafting (CR/CT) exams: (Mosaic - baseline)\
      \ / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative\
      \ = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this\
      \ mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Drafting Only)."
    display_name: Drafting Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting efficiency gain vs baseline
      - drafting % change vs baseline
      - drafting productivity lift vs baseline

  - name: Drafting Implied Read Time Savings Pct
    expr: MEASURE(`Drafting Baseline Efficiency`) / MEASURE(`Drafting Mosaic Efficiency`)
      - 1
    comment: "Implied read-time savings, Drafting (CR/CT) exams: baseline / Mosaic\
      \ efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per\
      \ unit of work than baseline). Outliers excluded; min_exams gate (default 1\
      \ exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency,\
      \ Drafting Only)."
    display_name: Drafting Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting read time savings
      - drafting time saved vs baseline
      - drafting read time reduction

  - name: Capture Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count\
      \ >= min_exams)"
    comment: "Count of Mosaic Capture exams (Drafting period, US/BD only) for radiologists\
      \ with an eligible baseline. Outliers excluded; min_exams gate (default 1 exam\
      \ per rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt]\
      \ (Mosaic Efficiency, Capture Only)."
    display_name: Capture Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - capture exam volume
      - capture exams read
      - number of capture exams

  - name: Capture Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units (same unit as RPWU) on Mosaic\
      \ Capture exams (Drafting period, US/BD only). Outliers excluded; min_exams\
      \ gate (default 1 exam per rad in this mode). Numerator of Capture Mosaic Efficiency.\
      \ = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Capture Only)."
    display_name: Capture Mosaic TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - capture workload units
      - capture RPWU
      - capture total TBWU

  - name: Capture Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting'\
      \ AND source.outliers = 'Excluded' AND source.modality_code IN ('US', 'BD')\
      \ AND source.capture_exam_count >= min_exams)"
    comment: "Building block: total adjusted read time in seconds on Capture (US/BD)\
      \ exams. Outliers excluded; min_exams gate (default 1 exam per rad in this mode).\
      \ Denominator of Capture Mosaic Efficiency and Capture Baseline Efficiency.\
      \ = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Capture Only)."
    display_name: Capture Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - capture read time seconds
      - capture total read time
      - capture reading time

  - name: Capture Baseline Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('US', 'BD') AND source.capture_exam_count\
      \ >= min_exams)"
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ Limited to US/BD. Context only; not used in the efficiency ratios. = PowerBI\
      \ [baselineexams_opt] (Mosaic Efficiency, Capture Only)."
    display_name: Capture Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - capture pre-Mosaic exams
      - capture legacy VR exams
      - capture PowerScribe baseline exams

  - name: Capture Baseline Contrib
    expr: "SUM(source.baseline_usbd_eff_excl * source.adjusted_read_time_sec) FILTER\
      \ (WHERE source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND\
      \ source.modality_code IN ('US', 'BD') AND source.capture_exam_count >= min_exams)"
    comment: "Building block: time-weighted baseline contribution = the US/BD-specific\
      \ baseline rate (TBWU/min) x each exam's own read time, over Mosaic Capture\
      \ exams (Drafting period, US/BD only). Divide by Capture Mosaic Time Sec to\
      \ get Capture Baseline Efficiency."
    display_name: Capture Baseline Contribution (Helper)
    synonyms:
      - capture baseline numerator
      - capture time weighted baseline contribution

  - name: Capture Mosaic Efficiency
    expr: MEASURE(`Capture Mosaic TBWU`) / (MEASURE(`Capture Mosaic Time Sec`) / 60)
    comment: "TBWU per minute on Mosaic Capture exams (Drafting period, US/BD only).\
      \ Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice\
      \ by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency,\
      \ Capture Only). Company/region trends here; practice, radiologist or site splits:\
      \ mosaic_eff_* functions."
    display_name: Capture Mosaic Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - capture TBWU per minute
      - capture productivity on Mosaic
      - capture efficiency on Mosaic

  - name: Capture Baseline Efficiency
    expr: MEASURE(`Capture Baseline Contrib`) / MEASURE(`Capture Mosaic Time Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using the US/BD-specific baseline\
      \ rate, time-weighted by the read time of the same Capture (US/BD) exams: the\
      \ like-for-like comparison point for Capture Mosaic Efficiency. Outliers excluded.\
      \ = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Capture Only)."
    display_name: Capture Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - capture baseline TBWU per minute
      - capture pre-Mosaic efficiency
      - capture legacy VR efficiency

  - name: Capture Pct Change Vs Baseline
    expr: (MEASURE(`Capture Mosaic Efficiency`) - MEASURE(`Capture Baseline Efficiency`))
      / MEASURE(`Capture Baseline Efficiency`)
    comment: "Efficiency change vs baseline, Capture (US/BD) exams: (Mosaic - baseline)\
      \ / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic; negative\
      \ = slower. Outliers excluded; min_exams gate (default 1 exam per rad in this\
      \ mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Capture Only)."
    display_name: Capture Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - capture efficiency gain vs baseline
      - capture % change vs baseline
      - capture productivity lift vs baseline

  - name: Capture Implied Read Time Savings Pct
    expr: MEASURE(`Capture Baseline Efficiency`) / MEASURE(`Capture Mosaic Efficiency`)
      - 1
    comment: "Implied read-time savings, Capture (US/BD) exams: baseline / Mosaic\
      \ efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per\
      \ unit of work than baseline). Outliers excluded; min_exams gate (default 1\
      \ exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency,\
      \ Capture Only)."
    display_name: Capture Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - capture read time savings
      - capture time saved vs baseline
      - capture read time reduction

  - name: Drafting Capture Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count\
      \ >= min_exams)"
    comment: "Count of Drafting-period CR/CT/US/BD exams (Drafting + Capture) for\
      \ radiologists with an eligible baseline. Outliers excluded; min_exams gate\
      \ (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. =\
      \ PowerBI [mosaicexams_opt] (Mosaic Efficiency, Drafting + Capture)."
    display_name: Drafting + Capture Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting plus capture exam volume
      - drafting plus capture exams read
      - number of drafting plus capture exams

  - name: Drafting Capture Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type = 'Drafting' AND source.outliers\
      \ = 'Excluded' AND source.modality_code IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count\
      \ >= min_exams)"
    comment: "Building block: total TBWU workload units (same unit as RPWU) on Drafting-period\
      \ CR/CT/US/BD exams (Drafting + Capture). Outliers excluded; min_exams gate\
      \ (default 1 exam per rad in this mode). Numerator of Drafting Capture Mosaic\
      \ Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Drafting + Capture)."
    display_name: Drafting + Capture Mosaic TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting plus capture workload units
      - drafting plus capture RPWU
      - drafting plus capture total TBWU

  - name: Drafting Capture Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type = 'Drafting'\
      \ AND source.outliers = 'Excluded' AND source.modality_code IN ('CR', 'CT',\
      \ 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    comment: "Building block: total adjusted read time in seconds on Drafting + Capture\
      \ (CR/CT/US/BD) exams. Outliers excluded; min_exams gate (default 1 exam per\
      \ rad in this mode). Denominator of Drafting Capture Mosaic Efficiency and Drafting\
      \ Capture Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency,\
      \ Drafting + Capture)."
    display_name: Drafting + Capture Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting plus capture read time seconds
      - drafting plus capture total read time
      - drafting plus capture reading time

  - name: Drafting Capture Baseline Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers
      = 'Excluded' AND source.drafting_capture_exam_count >= min_exams)
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ All modalities, not limited to this mode's modalities. Context only; not used\
      \ in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency,\
      \ Drafting + Capture)."
    display_name: Drafting + Capture Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafting plus capture pre-Mosaic exams
      - drafting plus capture legacy VR exams
      - drafting plus capture PowerScribe baseline exams

  - name: Drafting Capture Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE\
      \ source.period_type = 'Drafting' AND source.outliers = 'Excluded' AND source.modality_code\
      \ IN ('CR', 'CT', 'US', 'BD') AND source.drafting_capture_exam_count >= min_exams)"
    comment: "Building block: time-weighted baseline contribution = the standard all-modality\
      \ blended baseline (TBWU/min) x each exam's own read time, over Drafting-period\
      \ CR/CT/US/BD exams (Drafting + Capture). Divide by Drafting Capture Mosaic\
      \ Time Sec to get Drafting Capture Baseline Efficiency."
    display_name: Drafting + Capture Baseline Contribution (Helper)
    synonyms:
      - drafting plus capture baseline numerator
      - drafting plus capture time weighted baseline contribution

  - name: Drafting Capture Mosaic Efficiency
    expr: MEASURE(`Drafting Capture Mosaic TBWU`) / (MEASURE(`Drafting Capture Mosaic
      Time Sec`) / 60)
    comment: "TBWU per minute on Drafting-period CR/CT/US/BD exams (Drafting + Capture).\
      \ Outliers excluded; min_exams gate (default 1 exam per rad in this mode). Slice\
      \ by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic Efficiency,\
      \ Drafting + Capture)."
    display_name: Drafting + Capture Mosaic Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting plus capture TBWU per minute
      - drafting plus capture productivity on Mosaic
      - drafting plus capture efficiency on Mosaic

  - name: Drafting Capture Baseline Efficiency
    expr: MEASURE(`Drafting Capture Baseline Contrib`) / MEASURE(`Drafting Capture
      Mosaic Time Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using the standard all-modality\
      \ blended baseline, time-weighted by the read time of the same Drafting + Capture\
      \ (CR/CT/US/BD) exams: the like-for-like comparison point for Drafting Capture\
      \ Mosaic Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic\
      \ Efficiency, Drafting + Capture)."
    display_name: Drafting + Capture Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - drafting plus capture baseline TBWU per minute
      - drafting plus capture pre-Mosaic efficiency
      - drafting plus capture legacy VR efficiency

  - name: Drafting Capture Pct Change Vs Baseline
    expr: (MEASURE(`Drafting Capture Mosaic Efficiency`) - MEASURE(`Drafting Capture
      Baseline Efficiency`)) / MEASURE(`Drafting Capture Baseline Efficiency`)
    comment: "Efficiency change vs baseline, Drafting + Capture (CR/CT/US/BD) exams:\
      \ (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute\
      \ than pre-Mosaic; negative = slower. Outliers excluded; min_exams gate (default\
      \ 1 exam per rad in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency,\
      \ Drafting + Capture)."
    display_name: Drafting + Capture Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting plus capture efficiency gain vs baseline
      - drafting plus capture % change vs baseline
      - drafting plus capture productivity lift vs baseline

  - name: Drafting Capture Implied Read Time Savings Pct
    expr: MEASURE(`Drafting Capture Baseline Efficiency`) / MEASURE(`Drafting Capture
      Mosaic Efficiency`) - 1
    comment: "Implied read-time savings, Drafting + Capture (CR/CT/US/BD) exams: baseline\
      \ / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read\
      \ time per unit of work than baseline). Outliers excluded; min_exams gate (default\
      \ 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency,\
      \ Drafting + Capture)."
    display_name: Drafting + Capture Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - drafting plus capture read time savings
      - drafting plus capture time saved vs baseline
      - drafting plus capture read time reduction

  - name: Full Mosaic Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting')\
      \ AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    comment: "Count of all Mosaic exams (Reporting + Drafting) for radiologists with\
      \ an eligible baseline. Outliers excluded; min_exams gate (default 1 exam per\
      \ rad in this mode). Slice by Exam Month or Exam Week. = PowerBI [mosaicexams_opt]\
      \ (Mosaic Efficiency, Full Mosaic)."
    display_name: Full Mosaic Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - full mosaic exam volume
      - full mosaic exams read
      - number of full mosaic exams
      - Mosaic exam volume
      - overall Mosaic exams

  - name: Full Mosaic Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting')\
      \ AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)"
    comment: "Building block: total TBWU workload units (same unit as RPWU) on all\
      \ Mosaic exams (Reporting + Drafting). Outliers excluded; min_exams gate (default\
      \ 1 exam per rad in this mode). Numerator of Full Mosaic Mosaic Efficiency.\
      \ = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Full Mosaic)."
    display_name: Full Mosaic TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - full mosaic workload units
      - full mosaic RPWU
      - full mosaic total TBWU

  - name: Full Mosaic Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN\
      \ ('Reporting', 'Drafting') AND source.outliers = 'Excluded' AND source.full_mosaic_exam_count\
      \ >= min_exams)"
    comment: "Building block: total adjusted read time in seconds on Full Mosaic (Reporting\
      \ + Drafting) exams. Outliers excluded; min_exams gate (default 1 exam per rad\
      \ in this mode). Denominator of Full Mosaic Mosaic Efficiency and Full Mosaic\
      \ Baseline Efficiency. = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency,\
      \ Full Mosaic)."
    display_name: Full Mosaic Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - full mosaic read time seconds
      - full mosaic total read time
      - full mosaic reading time

  - name: Full Mosaic Baseline Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers
      = 'Excluded' AND source.full_mosaic_exam_count >= min_exams)
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ All modalities, not limited to this mode's modalities. Context only; not used\
      \ in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency,\
      \ Full Mosaic)."
    display_name: Full Mosaic Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - full mosaic pre-Mosaic exams
      - full mosaic legacy VR exams
      - full mosaic PowerScribe baseline exams

  - name: Full Mosaic Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE\
      \ source.period_type IN ('Reporting', 'Drafting') AND source.outliers = 'Excluded'\
      \ AND source.full_mosaic_exam_count >= min_exams)"
    comment: "Building block: time-weighted baseline contribution = each radiologist's\
      \ own baseline rate (TBWU/min) x each exam's own read time, over all Mosaic\
      \ exams (Reporting + Drafting). Divide by Full Mosaic Mosaic Time Sec to get\
      \ Full Mosaic Baseline Efficiency."
    display_name: Full Mosaic Baseline Contribution (Helper)
    synonyms:
      - full mosaic baseline numerator
      - full mosaic time weighted baseline contribution

  - name: Full Mosaic Mosaic Efficiency
    expr: MEASURE(`Full Mosaic Mosaic TBWU`) / (MEASURE(`Full Mosaic Mosaic Time Sec`)
      / 60)
    comment: "Headline 'overall' Mosaic efficiency: TBWU per minute on all Mosaic\
      \ exams (Reporting + Drafting); ungrouped = the app's 'RP Benchmark' tile. Outliers\
      \ excluded; min_exams gate (default 1). = PowerBI [Base_Mosaic_Eff_Opt] (Mosaic\
      \ Efficiency, Full Mosaic). Company/region here; practice/rad/site splits: mosaic_eff_*\
      \ functions."
    display_name: Full Mosaic Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - full mosaic TBWU per minute
      - full mosaic productivity on Mosaic
      - full mosaic efficiency on Mosaic
      - overall Mosaic efficiency
      - Mosaic productivity
      - Mosaic efficiency

  - name: Full Mosaic Baseline Efficiency
    expr: MEASURE(`Full Mosaic Baseline Contrib`) / MEASURE(`Full Mosaic Mosaic Time
      Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using each radiologist's own baseline\
      \ rate, time-weighted by the read time of the same Full Mosaic (Reporting +\
      \ Drafting) exams: the like-for-like comparison point for Full Mosaic Mosaic\
      \ Efficiency. Outliers excluded. = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency,\
      \ Full Mosaic)."
    display_name: Full Mosaic Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - full mosaic baseline TBWU per minute
      - full mosaic pre-Mosaic efficiency
      - full mosaic legacy VR efficiency
      - overall baseline efficiency
      - PowerScribe baseline efficiency

  - name: Full Mosaic Pct Change Vs Baseline
    expr: (MEASURE(`Full Mosaic Mosaic Efficiency`) - MEASURE(`Full Mosaic Baseline
      Efficiency`)) / MEASURE(`Full Mosaic Baseline Efficiency`)
    comment: "Headline efficiency change vs baseline, all Mosaic exams (Reporting\
      \ + Drafting): (Mosaic - baseline) / baseline. Fraction: 0.12 = 12% more TBWU/min\
      \ than pre-Mosaic. Outliers excluded; min_exams gate. = PowerBI [Pct_Change_Metric_Opt]\
      \ (Mosaic Efficiency, Full Mosaic). Company/region here; practice/rad/site splits:\
      \ mosaic_eff_* functions."
    display_name: Full Mosaic Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - full mosaic efficiency gain vs baseline
      - full mosaic % change vs baseline
      - full mosaic productivity lift vs baseline
      - Mosaic efficiency gain
      - overall efficiency change vs baseline
      - Mosaic productivity improvement

  - name: Full Mosaic Implied Read Time Savings Pct
    expr: MEASURE(`Full Mosaic Baseline Efficiency`) / MEASURE(`Full Mosaic Mosaic
      Efficiency`) - 1
    comment: "Headline implied read-time savings, all Mosaic exams: baseline / Mosaic\
      \ efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read time per\
      \ unit of work). Outliers excluded; min_exams gate. = PowerBI [Implied_RTS_Opt]\
      \ (Mosaic Efficiency, Full Mosaic). Company/region here; practice/rad/site splits:\
      \ mosaic_eff_* functions."
    display_name: Full Mosaic Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - full mosaic read time savings
      - full mosaic time saved vs baseline
      - full mosaic read time reduction
      - Mosaic read time savings
      - overall read time savings

  - name: Both Mosaic Exams
    expr: "COUNT(*) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting',\
      \ 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >=\
      \ min_exams)"
    comment: "Count of exams in all periods (Reporting + Drafting + pre-Mosaic Baseline)\
      \ for radiologists with an eligible baseline. Outliers excluded; min_exams gate\
      \ (default 1 exam per rad in this mode). Slice by Exam Month or Exam Week. =\
      \ PowerBI [mosaicexams_opt] (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - both modes exam volume
      - both modes exams read
      - number of both modes exams

  - name: Both Mosaic TBWU
    expr: "SUM(source.tbwu) FILTER (WHERE source.period_type IN ('Reporting', 'Drafting',\
      \ 'Baseline') AND source.outliers = 'Excluded' AND source.both_exam_count >=\
      \ min_exams)"
    comment: "Building block: total TBWU workload units (same unit as RPWU) on exams\
      \ in all periods (Reporting + Drafting + pre-Mosaic Baseline). Outliers excluded;\
      \ min_exams gate (default 1 exam per rad in this mode). Numerator of Both Mosaic\
      \ Efficiency. = PowerBI [mosaictbwu_opt] (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) TBWU
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - both modes workload units
      - both modes RPWU
      - both modes total TBWU

  - name: Both Mosaic Time Sec
    expr: "SUM(source.adjusted_read_time_sec) FILTER (WHERE source.period_type IN\
      \ ('Reporting', 'Drafting', 'Baseline') AND source.outliers = 'Excluded' AND\
      \ source.both_exam_count >= min_exams)"
    comment: "Building block: total adjusted read time in seconds on all-period exams\
      \ (incl. Baseline). Outliers excluded; min_exams gate (default 1 exam per rad\
      \ in this mode). Denominator of Both Mosaic Efficiency and Both Baseline Efficiency.\
      \ = PowerBI [Base_Time_Mosaic_Opt] (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) Read Time (Seconds)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - both modes read time seconds
      - both modes total read time
      - both modes reading time

  - name: Both Baseline Exams
    expr: COUNT(*) FILTER (WHERE source.period_type = 'Baseline' AND source.outliers
      = 'Excluded' AND source.both_exam_count >= min_exams)
    comment: "Count of the same qualifying radiologists' pre-Mosaic Baseline-period\
      \ exams (legacy VR/PowerScribe, not Mosaic-read or drafted), outliers excluded.\
      \ All modalities, not limited to this mode's modalities. Context only; not used\
      \ in the efficiency ratios. = PowerBI [baselineexams_opt] (Mosaic Efficiency,\
      \ Both)."
    display_name: Both (All Periods) Baseline Exams
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - both modes pre-Mosaic exams
      - both modes legacy VR exams
      - both modes PowerScribe baseline exams

  - name: Both Baseline Contrib
    expr: "SUM(source.baseline_eff_excl * source.adjusted_read_time_sec) FILTER (WHERE\
      \ source.period_type IN ('Reporting', 'Drafting', 'Baseline') AND source.outliers\
      \ = 'Excluded' AND source.both_exam_count >= min_exams)"
    comment: "Building block: time-weighted baseline contribution = each radiologist's\
      \ own baseline rate (TBWU/min) x each exam's own read time, over exams in all\
      \ periods (Reporting + Drafting + pre-Mosaic Baseline). Divide by Both Mosaic\
      \ Time Sec to get Both Baseline Efficiency."
    display_name: Both (All Periods) Baseline Contribution (Helper)
    synonyms:
      - both modes baseline numerator
      - both modes time weighted baseline contribution

  - name: Both Mosaic Efficiency
    expr: MEASURE(`Both Mosaic TBWU`) / (MEASURE(`Both Mosaic Time Sec`) / 60)
    comment: "TBWU per minute on exams in all periods (Reporting + Drafting + pre-Mosaic\
      \ Baseline). Includes Baseline-period exams, so it is an all-period figure,\
      \ not Mosaic-only. Outliers excluded; min_exams gate (default 1 exam per rad\
      \ in this mode). Slice by Exam Month or Exam Week. = PowerBI [Base_Mosaic_Eff_Opt]\
      \ (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - both modes TBWU per minute
      - both modes productivity on Mosaic
      - both modes efficiency on Mosaic

  - name: Both Baseline Efficiency
    expr: MEASURE(`Both Baseline Contrib`) / MEASURE(`Both Mosaic Time Sec`)
    comment: "Pre-Mosaic baseline TBWU per minute, using each radiologist's own baseline\
      \ rate, time-weighted by the read time of the same all-period exams (incl. Baseline):\
      \ the like-for-like comparison point for Both Mosaic Efficiency. Outliers excluded.\
      \ = PowerBI [Base_Baseline_Eff_Opt] (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) Baseline Efficiency
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - both modes baseline TBWU per minute
      - both modes pre-Mosaic efficiency
      - both modes legacy VR efficiency

  - name: Both Pct Change Vs Baseline
    expr: (MEASURE(`Both Mosaic Efficiency`) - MEASURE(`Both Baseline Efficiency`))
      / MEASURE(`Both Baseline Efficiency`)
    comment: "Efficiency change vs baseline, all-period exams (incl. Baseline): (Mosaic\
      \ - baseline) / baseline. Fraction: 0.12 = 12% more TBWU per minute than pre-Mosaic;\
      \ negative = slower. Outliers excluded; min_exams gate (default 1 exam per rad\
      \ in this mode). = PowerBI [Pct_Change_Metric_Opt] (Mosaic Efficiency, Both)."
    display_name: Both (All Periods) Efficiency Change vs Baseline
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - both modes efficiency gain vs baseline
      - both modes % change vs baseline
      - both modes productivity lift vs baseline

  - name: Both Implied Read Time Savings Pct
    expr: MEASURE(`Both Baseline Efficiency`) / MEASURE(`Both Mosaic Efficiency`)
      - 1
    comment: "Implied read-time savings, all-period exams (incl. Baseline): baseline\
      \ / Mosaic efficiency - 1. Fraction; NEGATIVE = savings (-0.10 = 10% less read\
      \ time per unit of work than baseline). Outliers excluded; min_exams gate (default\
      \ 1 exam per rad in this mode). = PowerBI [Implied_RTS_Opt] (Mosaic Efficiency,\
      \ Both)."
    display_name: Both (All Periods) Implied Read Time Savings
    format:
      type: percentage
      decimal_places:
        type: max
        places: 2
    synonyms:
      - both modes read time savings
      - both modes time saved vs baseline
      - both modes read time reduction
$$
