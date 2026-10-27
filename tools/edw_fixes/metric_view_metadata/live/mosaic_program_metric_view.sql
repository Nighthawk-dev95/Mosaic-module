CREATE VIEW edw_test.enterprise_analytics.mosaic_program_metric_view (
  NPI COMMENT 'Radiologist\'s National Provider Identifier (10 digits). The Dynamics snapshot holds one row per NPI (about 2,600 radiologists), so every measure here is a distinct-radiologist count.',
  Radiologist Name COMMENT 'Radiologist name as recorded in Dynamics CRM. Match partial names with ILIKE \'%lastname%\' and say which radiologist(s) matched.',
  Dynamics Practice COMMENT 'Practice typed as free text in Dynamics CRM - not an MDM practice key and not the same values as Team Rolled Up (Provider Practice, the rad\'s home practice) or Managing Practice (exam site\'s practice) in the other Mosaic views. Cannot be cut by Local Region.',
  MVP Cohort COMMENT 'Full MVP cohort label, Cohort 1 to Cohort 4 with an optional track suffix, e.g. \'Cohort 2 (Mammo)\' or a \'(Ops or Self Referred)\' cohort. NULL = excluded before a cohort was assigned. Use Cohort Wave for the number only.',
  Cohort Wave COMMENT 'Cohort number only (\'Cohort 1\' to \'Cohort 4\') with the (Mammo) / (Ops or Self Referred) suffix stripped - use to compare waves across tracks. NULL when no cohort is assigned.',
  Program Track COMMENT 'MVP track: \'Core\' (cohort assigned, not Mammo, not Ops/Self Referred - the app\'s MVP Overview scope), \'Mammo\' (the app\'s Mammo scope), \'Ops or Self Referred\', or \'Not In A Cohort\'.',
  Is Actively Tracked COMMENT 'TRUE when no exclusion reason is recorded in Dynamics (radiologist is still actively tracked in MVP); FALSE = excluded - see Exclusion Reason.',
  Exclusion Reason COMMENT 'Why the radiologist was excluded from MVP tracking, as recorded in Dynamics. NULL = actively tracked (Is Actively Tracked = TRUE).',
  Optimization Support Status COMMENT 'Raw Dynamics optimization-support status, numbered in workflow order, e.g. \'1 Identified\', \'5 Scheduled\', \'7 Solutioning (Escalated - IT)\', \'9 Closed (MVP Completed)\'. Funnel Stage and Funnel Outcome group these values.',
  Funnel Stage COMMENT 'Weekly Update funnel stage: \'1 Outreached\', \'2 Scheduled\', \'3 Solutioning\', \'4 Monitoring\', \'5 Closed\' (number prefix only for sort order). NULL = not yet in the funnel (no status, 1 Identified, 2 Confirmed). Port of the app\'s mvp_dashboard_stats._stage_bucket.',
  Funnel Outcome COMMENT 'On Track / Escalated / Declined split within each funnel stage. Declined = Closed with Declined Support, Resigning, Mentor Declined or Not Progressing; Escalated = open case flagged Escalated. NULL outside the funnel. Port of mvp_dashboard_stats.compute_status_funnel.',
  Escalation Owner COMMENT 'Who owns an escalated Solutioning case: \'Mentorship\', \'IT\' or \'Development\' (Dynamics \'Program Specific\' is reported as Development). NULL when not an escalated Solutioning case. Port of mvp_dashboard_stats.compute_escalations_by_owner.',
  Impact Status COMMENT 'Post-engagement (Solutioning/Monitoring/Closed) rads only: At Or Above Baseline (L30D Full Mosaic change >= 0), Improving (L30D beats all-time drafting+capture change), Not Improving, or Insufficient Data (missing or beyond +/-100%, tiny-denominator artifacts). Inputs are manually entered in Dynamics.',
  Radiologists COMMENT 'Distinct radiologists (NPIs) in the Dynamics MVP snapshot for the slice - the headline MVP headcount; slice by Funnel Stage, Program Track or MVP Cohort. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding and the app\'s MVP page.',
  Cohort Radiologists COMMENT 'Distinct radiologists assigned to an MVP cohort (MVP Cohort not NULL). No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Actively Tracked Radiologists COMMENT 'Distinct radiologists with no exclusion reason recorded in Dynamics (Is Actively Tracked = TRUE). No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Excluded Radiologists COMMENT 'Distinct radiologists with an exclusion reason recorded in Dynamics (dropped from MVP tracking); break down by Exclusion Reason. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Funnel Radiologists COMMENT 'Radiologists in the Weekly Update funnel (Outreached through Closed) - the Weekly Update PDF\'s funnel total; excludes Identified, Confirmed and blank statuses. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Post Engagement Radiologists COMMENT 'Radiologists who reached at least Solutioning (Solutioning, Monitoring or Closed) - the population Impact Status is computed over. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Closed Completed Radiologists COMMENT 'Radiologists whose MVP case is Closed with a successful outcome (Closed, excluding Declined Support, Resigning, Mentor Declined and Not Progressing) - MVP completions. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Escalated Radiologists COMMENT 'Open (not Closed) funnel cases currently flagged Escalated - same rule as Funnel Outcome = Escalated; break down by Escalation Owner. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.',
  Median Full Mosaic L30D Change Pct COMMENT 'Median trailing-30-day Full Mosaic efficiency change vs baseline, a fraction (0.12 = 12%), over rads with a plausible (within +/-100%) value. Manually entered in Dynamics by the deployment team, not computed from EDW; no PowerBI equivalent. Always show Radiologists With L30D Change.',
  Radiologists With L30D Change COMMENT 'Building block: denominator behind Median Full Mosaic L30D Change Pct - radiologists with a plausible (within +/-100%) manually entered L30D Full Mosaic change. Always show alongside the median.',
  Latest Dynamics Activity COMMENT 'Most recent optimization_last_updated timestamp across the slice - the as-of / freshness signal for the manually refreshed Dynamics snapshot, not a snapshot load timestamp.')
COMMENT 'MOSAIC PROGRAM (MVP) SEMANTIC LAYER (draft, edw_test only). MVP efficiency-coaching program state from the Dynamics CRM snapshot tbl_mvp_rad_onboarding: cohort, exclusions, optimization-support funnel stage, and post-engagement impact. Definitions mirror backend/app/data/mvp_dashboard_stats.py. Efficiency-change inputs are manually populated by the deployment team in Dynamics, not computed from EDW.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding

comment: "MOSAIC PROGRAM (MVP) SEMANTIC LAYER (draft, edw_test only). MVP efficiency-coaching\
  \ program state from the Dynamics CRM snapshot tbl_mvp_rad_onboarding: cohort, exclusions,\
  \ optimization-support funnel stage, and post-engagement impact. Definitions mirror\
  \ backend/app/data/mvp_dashboard_stats.py. Efficiency-change inputs are manually\
  \ populated by the deployment team in Dynamics, not computed from EDW."

dimensions:
  - name: NPI
    expr: source.npi
    comment: "Radiologist's National Provider Identifier (10 digits). The Dynamics\
      \ snapshot holds one row per NPI (about 2,600 radiologists), so every measure\
      \ here is a distinct-radiologist count."
    display_name: Radiologist NPI
    synonyms:
      - provider npi
      - npi number
      - national provider identifier

  - name: Radiologist Name
    expr: source.rad_name
    comment: Radiologist name as recorded in Dynamics CRM. Match partial names with
      ILIKE '%lastname%' and say which radiologist(s) matched.
    display_name: Radiologist Name
    synonyms:
      - rad name
      - doctor
      - physician
      - provider name

  - name: Dynamics Practice
    expr: source.practice
    comment: "Practice typed as free text in Dynamics CRM - not an MDM practice key\
      \ and not the same values as Team Rolled Up (Provider Practice, the rad's home\
      \ practice) or Managing Practice (exam site's practice) in the other Mosaic\
      \ views. Cannot be cut by Local Region."
    display_name: Dynamics Practice (Free Text)
    synonyms:
      - crm practice
      - practice in dynamics
      - mvp practice

  - name: MVP Cohort
    expr: source.mvp_cohort
    comment: "Full MVP cohort label, Cohort 1 to Cohort 4 with an optional track suffix,\
      \ e.g. 'Cohort 2 (Mammo)' or a '(Ops or Self Referred)' cohort. NULL = excluded\
      \ before a cohort was assigned. Use Cohort Wave for the number only."
    display_name: MVP Cohort
    synonyms:
      - cohort
      - cohort label
      - mvp group

  - name: Cohort Wave
    expr: "REGEXP_EXTRACT(source.mvp_cohort, '^(Cohort [0-9]+)', 1)"
    comment: Cohort number only ('Cohort 1' to 'Cohort 4') with the (Mammo) / (Ops
      or Self Referred) suffix stripped - use to compare waves across tracks. NULL
      when no cohort is assigned.
    display_name: Cohort Wave
    synonyms:
      - cohort number
      - wave
      - mvp wave

  - name: Program Track
    expr: CASE WHEN source.mvp_cohort IS NULL THEN 'Not In A Cohort' WHEN source.mvp_cohort
      LIKE '%(Mammo)%' THEN 'Mammo' WHEN source.mvp_cohort LIKE '%(Ops or Self Referred)%'
      THEN 'Ops or Self Referred' ELSE 'Core' END
    comment: "MVP track: 'Core' (cohort assigned, not Mammo, not Ops/Self Referred\
      \ - the app's MVP Overview scope), 'Mammo' (the app's Mammo scope), 'Ops or\
      \ Self Referred', or 'Not In A Cohort'."
    display_name: Program Track
    synonyms:
      - mvp track
      - track
      - core vs mammo

  - name: Is Actively Tracked
    expr: source.exclusion_reason IS NULL
    comment: TRUE when no exclusion reason is recorded in Dynamics (radiologist is
      still actively tracked in MVP); FALSE = excluded - see Exclusion Reason.
    display_name: Actively Tracked Flag
    synonyms:
      - active in mvp
      - not excluded
      - still tracked

  - name: Exclusion Reason
    expr: source.exclusion_reason
    comment: "Why the radiologist was excluded from MVP tracking, as recorded in Dynamics.\
      \ NULL = actively tracked (Is Actively Tracked = TRUE)."
    display_name: Exclusion Reason
    synonyms:
      - why excluded
      - reason excluded
      - mvp exclusion

  - name: Optimization Support Status
    expr: source.optimization_support_status
    comment: "Raw Dynamics optimization-support status, numbered in workflow order,\
      \ e.g. '1 Identified', '5 Scheduled', '7 Solutioning (Escalated - IT)', '9 Closed\
      \ (MVP Completed)'. Funnel Stage and Funnel Outcome group these values."
    display_name: Optimization Support Status
    synonyms:
      - dynamics status
      - support status
      - raw mvp status

  - name: Funnel Stage
    expr: "CASE WHEN source.optimization_support_status IS NULL OR source.optimization_support_status\
      \ = '' THEN NULL WHEN source.optimization_support_status IN ('1 Identified',\
      \ '2 Confirmed') THEN NULL WHEN source.optimization_support_status LIKE '3 Outreached%'\
      \ OR source.optimization_support_status LIKE '4 Outreached%' THEN '1 Outreached'\
      \ WHEN source.optimization_support_status LIKE '5 Scheduled%' THEN '2 Scheduled'\
      \ WHEN source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status\
      \ LIKE '7 Solutioning%' THEN '3 Solutioning' WHEN source.optimization_support_status\
      \ LIKE '8 Monitoring%' THEN '4 Monitoring' WHEN source.optimization_support_status\
      \ LIKE '9 Closed%' THEN '5 Closed' ELSE NULL END"
    comment: "Weekly Update funnel stage: '1 Outreached', '2 Scheduled', '3 Solutioning',\
      \ '4 Monitoring', '5 Closed' (number prefix only for sort order). NULL = not\
      \ yet in the funnel (no status, 1 Identified, 2 Confirmed). Port of the app's\
      \ mvp_dashboard_stats._stage_bucket."
    display_name: Funnel Stage
    synonyms:
      - mvp stage
      - program stage
      - pipeline stage
      - where in the funnel

  - name: Funnel Outcome
    expr: CASE WHEN source.optimization_support_status LIKE '9 Closed%' THEN CASE
      WHEN source.optimization_support_status LIKE '%Declined Support%' OR source.optimization_support_status
      LIKE '%Resigning%' OR source.optimization_support_status LIKE '%Mentor Declined%'
      OR source.optimization_support_status LIKE '%Not Progressing%' THEN 'Declined'
      ELSE 'On Track' END WHEN source.optimization_support_status LIKE '3 Outreached%'
      OR source.optimization_support_status LIKE '4 Outreached%' OR source.optimization_support_status
      LIKE '5 Scheduled%' OR source.optimization_support_status LIKE '6 Solutioning%'
      OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status
      LIKE '8 Monitoring%' THEN CASE WHEN source.optimization_support_status LIKE
      '%Escalated%' THEN 'Escalated' ELSE 'On Track' END ELSE NULL END
    comment: "On Track / Escalated / Declined split within each funnel stage. Declined\
      \ = Closed with Declined Support, Resigning, Mentor Declined or Not Progressing;\
      \ Escalated = open case flagged Escalated. NULL outside the funnel. Port of\
      \ mvp_dashboard_stats.compute_status_funnel."
    display_name: Funnel Outcome
    synonyms:
      - on track or escalated
      - declined vs on track
      - case outcome

  - name: Escalation Owner
    expr: CASE source.optimization_support_status WHEN '7 Solutioning (Escalated -
      Mentorship)' THEN 'Mentorship' WHEN '7 Solutioning (Escalated - IT)' THEN 'IT'
      WHEN '7 Solutioning (Escalated - Program Specific)' THEN 'Development' ELSE
      NULL END
    comment: "Who owns an escalated Solutioning case: 'Mentorship', 'IT' or 'Development'\
      \ (Dynamics 'Program Specific' is reported as Development). NULL when not an\
      \ escalated Solutioning case. Port of mvp_dashboard_stats.compute_escalations_by_owner."
    display_name: Escalation Owner
    synonyms:
      - escalated to
      - escalation team
      - who owns escalation

  - name: Impact Status
    expr: CASE WHEN NOT (source.optimization_support_status LIKE '6 Solutioning%'
      OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status
      LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%')
      OR source.optimization_support_status IS NULL THEN NULL WHEN TRY_CAST(source.drafting_captured_efficiency_change_pct
      AS DOUBLE) IS NULL OR TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)
      IS NULL OR ABS(TRY_CAST(source.drafting_captured_efficiency_change_pct AS DOUBLE))
      > 100 OR ABS(TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)) > 100 THEN
      'Insufficient Data' WHEN TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE)
      >= 0 THEN 'At Or Above Baseline' WHEN TRY_CAST(source.full_mosaic_change_l30d_pct
      AS DOUBLE) > TRY_CAST(source.drafting_captured_efficiency_change_pct AS DOUBLE)
      THEN 'Improving' ELSE 'Not Improving' END
    comment: "Post-engagement (Solutioning/Monitoring/Closed) rads only: At Or Above\
      \ Baseline (L30D Full Mosaic change >= 0), Improving (L30D beats all-time drafting+capture\
      \ change), Not Improving, or Insufficient Data (missing or beyond +/-100%, tiny-denominator\
      \ artifacts). Inputs are manually entered in Dynamics."
    display_name: MVP Impact Status
    synonyms:
      - coaching impact
      - improvement status
      - mvp impact

measures:
  - name: Radiologists
    expr: COUNT(DISTINCT source.npi)
    comment: "Distinct radiologists (NPIs) in the Dynamics MVP snapshot for the slice\
      \ - the headline MVP headcount; slice by Funnel Stage, Program Track or MVP\
      \ Cohort. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding and\
      \ the app's MVP page."
    display_name: MVP Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - mvp headcount
      - number of mvp rads
      - how many radiologists in mvp
      - rads in program

  - name: Cohort Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.mvp_cohort IS NOT NULL THEN source.npi END)
    comment: Distinct radiologists assigned to an MVP cohort (MVP Cohort not NULL).
      No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.
    display_name: Radiologists In A Cohort
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - cohort rads
      - rads assigned to a cohort
      - enrolled radiologists

  - name: Actively Tracked Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.exclusion_reason IS NULL THEN source.npi
      END)
    comment: Distinct radiologists with no exclusion reason recorded in Dynamics (Is
      Actively Tracked = TRUE). No PowerBI equivalent; validated against tbl_mvp_rad_onboarding.
    display_name: Actively Tracked Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - active mvp rads
      - tracked rads
      - rads not excluded

  - name: Excluded Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.exclusion_reason IS NOT NULL THEN source.npi
      END)
    comment: Distinct radiologists with an exclusion reason recorded in Dynamics (dropped
      from MVP tracking); break down by Exclusion Reason. No PowerBI equivalent; validated
      against tbl_mvp_rad_onboarding.
    display_name: Excluded Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - excluded rads
      - rads excluded from mvp
      - mvp exclusions

  - name: Funnel Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '3 Outreached%'
      OR source.optimization_support_status LIKE '4 Outreached%' OR source.optimization_support_status
      LIKE '5 Scheduled%' OR source.optimization_support_status LIKE '6 Solutioning%'
      OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status
      LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%'
      THEN source.npi END)
    comment: "Radiologists in the Weekly Update funnel (Outreached through Closed)\
      \ - the Weekly Update PDF's funnel total; excludes Identified, Confirmed and\
      \ blank statuses. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding."
    display_name: Radiologists In Funnel
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - funnel total
      - rads in funnel
      - weekly update funnel count

  - name: Post Engagement Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '6 Solutioning%'
      OR source.optimization_support_status LIKE '7 Solutioning%' OR source.optimization_support_status
      LIKE '8 Monitoring%' OR source.optimization_support_status LIKE '9 Closed%'
      THEN source.npi END)
    comment: "Radiologists who reached at least Solutioning (Solutioning, Monitoring\
      \ or Closed) - the population Impact Status is computed over. No PowerBI equivalent;\
      \ validated against tbl_mvp_rad_onboarding."
    display_name: Post Engagement Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - post-engagement rads
      - rads past solutioning
      - coached radiologists

  - name: Closed Completed Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '9 Closed%'
      AND NOT (source.optimization_support_status LIKE '%Declined Support%' OR source.optimization_support_status
      LIKE '%Resigning%' OR source.optimization_support_status LIKE '%Mentor Declined%'
      OR source.optimization_support_status LIKE '%Not Progressing%') THEN source.npi
      END)
    comment: "Radiologists whose MVP case is Closed with a successful outcome (Closed,\
      \ excluding Declined Support, Resigning, Mentor Declined and Not Progressing)\
      \ - MVP completions. No PowerBI equivalent; validated against tbl_mvp_rad_onboarding."
    display_name: MVP Completed Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - completed mvp
      - graduated rads
      - closed on track
      - mvp completions

  - name: Escalated Radiologists
    expr: COUNT(DISTINCT CASE WHEN source.optimization_support_status LIKE '%Escalated%'
      AND (source.optimization_support_status LIKE '3 Outreached%' OR source.optimization_support_status
      LIKE '4 Outreached%' OR source.optimization_support_status LIKE '5 Scheduled%'
      OR source.optimization_support_status LIKE '6 Solutioning%' OR source.optimization_support_status
      LIKE '7 Solutioning%' OR source.optimization_support_status LIKE '8 Monitoring%')
      THEN source.npi END)
    comment: Open (not Closed) funnel cases currently flagged Escalated - same rule
      as Funnel Outcome = Escalated; break down by Escalation Owner. No PowerBI equivalent;
      validated against tbl_mvp_rad_onboarding.
    display_name: Escalated Radiologists
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - escalations
      - escalated cases
      - open escalations

  - name: Median Full Mosaic L30D Change Pct
    expr: MEDIAN(CASE WHEN ABS(TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE))
      <= 100 THEN TRY_CAST(source.full_mosaic_change_l30d_pct AS DOUBLE) / 100 END)
    comment: "Median trailing-30-day Full Mosaic efficiency change vs baseline, a\
      \ fraction (0.12 = 12%), over rads with a plausible (within +/-100%) value.\
      \ Manually entered in Dynamics by the deployment team, not computed from EDW;\
      \ no PowerBI equivalent. Always show Radiologists With L30D Change."
    display_name: Median L30D Full Mosaic Efficiency Change
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - mvp efficiency change
      - median efficiency gain
      - coaching efficiency lift
      - last 30 day efficiency change

  - name: Radiologists With L30D Change
    expr: COUNT(DISTINCT CASE WHEN ABS(TRY_CAST(source.full_mosaic_change_l30d_pct
      AS DOUBLE)) <= 100 THEN source.npi END)
    comment: "Building block: denominator behind Median Full Mosaic L30D Change Pct\
      \ - radiologists with a plausible (within +/-100%) manually entered L30D Full\
      \ Mosaic change. Always show alongside the median."
    display_name: Radiologists With L30D Change
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - rads with efficiency data
      - median sample size
      - l30d change sample

  - name: Latest Dynamics Activity
    expr: "MAX(TRY_TO_TIMESTAMP(source.optimization_last_updated, 'M/d/yyyy h:mm a'))"
    comment: "Most recent optimization_last_updated timestamp across the slice - the\
      \ as-of / freshness signal for the manually refreshed Dynamics snapshot, not\
      \ a snapshot load timestamp."
    display_name: Latest Dynamics Activity
    synonyms:
      - as of date
      - data freshness
      - last dynamics update
      - mvp last updated
$$
