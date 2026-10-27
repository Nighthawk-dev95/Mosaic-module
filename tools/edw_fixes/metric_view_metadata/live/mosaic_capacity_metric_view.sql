CREATE VIEW edw_test.enterprise_analytics.mosaic_capacity_metric_view (
  NPI COMMENT 'Radiologist\'s National Provider Identifier (10-digit ID, text). Use to identify a radiologist unambiguously.',
  Radiologist Name COMMENT 'Radiologist name, \'Last, First M\'. Match partial names with ILIKE \'%name%\'.',
  Team COMMENT 'Radiologist\'s roster team, a sub-team finer than Team Rolled Up (Provider Practice), e.g. \'RAF Tampa\'. For the radiologist\'s home practice use Team Rolled Up.',
  Team Rolled Up COMMENT 'Provider Practice = the radiologist\'s home practice (PowerBI \'Team Rolled up\'): Team mapped to its parent grouping via the team_rollups lookup, same join as the Volume metric view. Not the exam site\'s practice - that is Practice.',
  Local Region COMMENT 'One of 6 fixed regions keyed on Team: Special Operations, Apex, Genesis, Maverick, Trailblazer, Matrix (unmapped teams fall into Matrix here). Matches PowerBI \'0. Cur\'[Local], same mapping as the Volume and Efficiency views.',
  Practice COMMENT 'Managing Practice = the practice owning the exam SITE (PowerBI \'Practice\'), one per shift (if a shift spans several sites the alphabetically highest is kept). Same Team-vs-Practice convention as the efficiency exam-level view; the home practice is Team Rolled Up.',
  Shift Name COMMENT 'Name of the scheduled shift the radiologist worked (from the shift schedule); one row per radiologist, date, shift name and task.',
  Shift Date COMMENT 'Date of the radiologist\'s shift (shifts from 2024-10-01 onward). Bind date-range filters here.',
  Shift Month COMMENT 'Calendar month of the shift, as the first day of the month (e.g. 2026-09-01). Use for monthly trends; the current month is partial.',
  Baseline Type COMMENT 'How the shift\'s TBWU 26 baseline was matched: Exact, Proxy or Manual Review; NULL = no baseline matched (from tbl_mosaic_baseline_master). Filter to NOT NULL for like-for-like capacity-vs-baseline comparisons.',
  Is RPCE Source COMMENT 'TRUE if the shift has RPCE-sourced exams (rpceMidwest / rpceSouthwest). Usually means reliable dictation timestamps but NOT always (2026-10-22: RP Valley ~100% RPCE yet 88.7% missing timestamps). Use Pct Exams With Valid Read Time as the trust signal, not this flag.',
  On Shift Cases COMMENT 'Total exams read during scheduled shifts (all shifts, with or without a baseline). Denominator for every \'Pct ... Of Shift\' case-mix measure. = PowerBI [On-Shift Cases] (Mosaic Impact).',
  Total Hours COMMENT 'Building block: total scheduled shift hours. Feeds the Per Hour / Per 9Hour capacity and baseline measures and On Shift Utilization Pct.',
  On Shift Capacity RPWU COMMENT 'Total workload read on shift, in TBWU (RPWU), summed over all shifts in scope with or without a baseline. = PowerBI [On-Shift Capacity] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view [New Capacity] (average per shift).',
  On Shift Capacity RVU COMMENT 'Total workload read on shift in RVU (billing units), summed over all shifts in scope. RVU counterpart of On Shift Capacity RPWU. = PowerBI [On-Shift Capacity] (Mosaic Impact, RVU unit).',
  On Shift Capacity RPWU Per Hour COMMENT 'On-shift TBWU per scheduled shift hour (total TBWU / total hours, hour-weighted). All shifts in scope, with or without a baseline.',
  On Shift Capacity RPWU Per 9Hour COMMENT 'On-shift TBWU per hour scaled to a standard 9-hour shift. = PowerBI [New Capacity RPWU 9h(Top N)] (Mosaic Impact). For exec capacity per shift use mosaic_capacity_pbi_metric_view [New Capacity].',
  On Shift Capacity RVU Per Hour COMMENT 'On-shift RVU per scheduled shift hour (total RVU / total hours, hour-weighted).',
  On Shift Capacity RVU Per 9Hour COMMENT 'On-shift RVU per hour scaled to a standard 9-hour shift.',
  Shift Baseline RPWU COMMENT 'Total pre-Mosaic baseline (TBWU 26, rescaled to shift hours), summed only over shifts with a matched baseline (Baseline Type not null; NULL-safe). = PowerBI [Shift Baseline] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view [Average Baseline].',
  Shift Baseline RPWU Per Hour COMMENT 'Baseline TBWU per scheduled hour. Caveat: divides baselined-shift baseline by the hours of ALL shifts, so it is understated unless filtered to Baseline Type not null.',
  Shift Baseline RPWU Per 9Hour COMMENT 'Baseline TBWU per hour scaled to a standard 9-hour shift. Same caveat as the per-hour baseline: filter to Baseline Type not null for a like-for-like figure.',
  Shifts With Baseline COMMENT 'Building block: number of shifts with a matched TBWU 26 baseline (Baseline Type not null). Feeds Pct Shifts With Baseline.',
  Pct Shifts With Baseline COMMENT 'Share of shifts that have a matched baseline, a fraction 0-1. Low coverage means capacity-vs-baseline measures describe only part of the work.',
  On Shift Capacity Vs Baseline RPWU COMMENT 'Total on-shift TBWU minus total baseline TBWU (positive = above baseline). Caveat: capacity includes all shifts, baseline only baselined ones - filter Baseline Type not null. = PowerBI [On-Shift Capacity v. BL] (Mosaic Impact). Exec: mosaic_capacity_pbi_metric_view [Pct Addl Capacity].',
  On Shift Capacity Vs Baseline RPWU Per Hour COMMENT 'On-shift TBWU per hour minus baseline TBWU per hour (positive = above baseline). Filter Baseline Type not null for like-for-like. For exec added capacity use mosaic_capacity_pbi_metric_view [Addl Capacity Per Shift].',
  On Shift Above Baseline RPWU COMMENT 'Portion of on-shift TBWU above each shift\'s baseline, summed (0 for shifts at/under baseline or with no baseline). Stacks with On Shift Up To Baseline RPWU to total capacity. = PowerBI [On-Shift Capacity Above BL(Unit)] (Mosaic Impact).',
  On Shift Up To Baseline RPWU COMMENT 'Portion of on-shift TBWU at/under each shift\'s baseline, summed; shifts with no baseline count fully here. Pairs with On Shift Above Baseline RPWU for a stacked view (together = total capacity). = PowerBI [On-Shift Capacity Up to BL(Unit)] (Mosaic Impact).',
  Read Minutes COMMENT 'Building block: total reading (dictation) minutes on shift, from exams with valid timestamps only, each exam capped at 60 minutes. Feeds On Shift Utilization Pct and On Shift Efficiency.',
  Exams With Valid Read Time COMMENT 'Building block: exams with usable dictation timestamps (start, end and final all present) - the population Read Minutes, efficiency and utilization are actually computed over. Feeds Pct Exams With Valid Read Time.',
  Pct Exams With Valid Read Time COMMENT 'ALWAYS CHECK before trusting efficiency or utilization for a slice: share of on-shift exams with usable dictation timestamps, a fraction 0-1. Coverage varies enormously by practice (live: 0.03% to 66%+), independent of Is RPCE Source.',
  On Shift Utilization Pct COMMENT 'Hour-weighted utilization: total reading minutes / total shift minutes, a fraction 0-1, capped at 1 (100%). Check Pct Exams With Valid Read Time alongside it. = PowerBI [On-Shift Utilization]. Exec: mosaic_capacity_pbi_metric_view [New Utilization].',
  On Shift Efficiency RPWU COMMENT 'TBWU read per reading minute (total TBWU / total read minutes). Capacity counts all cases but read minutes only exams with valid timestamps - check Pct Exams With Valid Read Time. = PowerBI [On-Shift Efficiency] (Mosaic Impact). Exec: mosaic_capacity_pbi_metric_view [New Efficiency].',
  On Shift Efficiency RVU COMMENT 'RVU read per reading minute (total RVU / total read minutes); same read-time coverage caveat as the TBWU version. = PowerBI [On-Shift Efficiency] (Mosaic Impact, RVU unit).',
  CT Cases COMMENT 'Building block: number of CT exams read during shifts. Feeds Pct CT Of Shift (share of On Shift Cases).',
  Pct CT Of Shift COMMENT 'Share of on-shift exams that are CT exams, a fraction 0-1 (= CT Cases / On Shift Cases). = PowerBI [% CT] (Mosaic Impact).',
  XR Cases COMMENT 'Building block: number of X-ray exams (source modality code CR) read during shifts. Feeds Pct XR Of Shift (share of On Shift Cases).',
  Pct XR Of Shift COMMENT 'Share of on-shift exams that are X-ray exams (source modality code CR), a fraction 0-1 (= XR Cases / On Shift Cases). = PowerBI [% XR] (Mosaic Impact).',
  US Cases COMMENT 'Building block: number of ultrasound exams read during shifts. Feeds Pct US Of Shift (share of On Shift Cases).',
  Pct US Of Shift COMMENT 'Share of on-shift exams that are ultrasound exams, a fraction 0-1 (= US Cases / On Shift Cases). = PowerBI [% US] (Mosaic Impact).',
  MR Cases COMMENT 'Building block: number of MRI exams read during shifts. Feeds Pct MR Of Shift (share of On Shift Cases).',
  Pct MR Of Shift COMMENT 'Share of on-shift exams that are MRI exams, a fraction 0-1 (= MR Cases / On Shift Cases). = PowerBI [% MR] (Mosaic Impact).',
  NM Cases COMMENT 'Building block: number of nuclear medicine exams read during shifts. Feeds Pct NM Of Shift (share of On Shift Cases).',
  Pct NM Of Shift COMMENT 'Share of on-shift exams that are nuclear medicine exams, a fraction 0-1 (= NM Cases / On Shift Cases). = PowerBI [% NM] (Mosaic Impact).',
  PT Cases COMMENT 'Building block: number of PET exams read during shifts. Feeds Pct PT Of Shift (share of On Shift Cases).',
  Pct PT Of Shift COMMENT 'Share of on-shift exams that are PET exams, a fraction 0-1 (= PT Cases / On Shift Cases). = PowerBI [% PT] (Mosaic Impact).',
  MG Cases COMMENT 'Building block: number of mammography exams read during shifts. Feeds Pct MG Of Shift (share of On Shift Cases).',
  Pct MG Of Shift COMMENT 'Share of on-shift exams that are mammography exams, a fraction 0-1 (= MG Cases / On Shift Cases). = PowerBI [% MG] (Mosaic Impact).',
  IR Cases COMMENT 'Building block: number of interventional radiology exams read during shifts. Feeds Pct IR Of Shift (share of On Shift Cases).',
  Pct IR Of Shift COMMENT 'Share of on-shift exams that are interventional radiology exams, a fraction 0-1 (= IR Cases / On Shift Cases). = PowerBI [% IR] (Mosaic Impact).',
  Other Modality Cases COMMENT 'Building block: number of exams in modalities other than CT/XR/US/MR/NM/PT/MG/IR read during shifts. Feeds Pct Other Modality Of Shift (share of On Shift Cases).',
  Pct Other Modality Of Shift COMMENT 'Share of on-shift exams that are exams in modalities other than CT/XR/US/MR/NM/PT/MG/IR, a fraction 0-1 (= Other Modality Cases / On Shift Cases). = PowerBI [% Other Modality] (Mosaic Impact).',
  Routine Cases COMMENT 'Building block: number of Routine-priority exams read during shifts. Feeds Pct Routine Of Shift (share of On Shift Cases).',
  Pct Routine Of Shift COMMENT 'Share of on-shift exams that are Routine-priority exams, a fraction 0-1 (= Routine Cases / On Shift Cases). = PowerBI [% Routine] (Mosaic Impact).',
  Stat Cases COMMENT 'Building block: number of Stat-priority exams read during shifts. Feeds Pct Stat Of Shift (share of On Shift Cases).',
  Pct Stat Of Shift COMMENT 'Share of on-shift exams that are Stat-priority exams, a fraction 0-1 (= Stat Cases / On Shift Cases). = PowerBI [% Stat] (Mosaic Impact).',
  Stroke Cases COMMENT 'Building block: number of Stroke-priority exams read during shifts. Feeds Pct Stroke Of Shift (share of On Shift Cases).',
  Pct Stroke Of Shift COMMENT 'Share of on-shift exams that are Stroke-priority exams, a fraction 0-1 (= Stroke Cases / On Shift Cases). = PowerBI [% Stroke] (Mosaic Impact).',
  Trauma Cases COMMENT 'Building block: number of Trauma-priority exams read during shifts. Feeds Pct Trauma Of Shift (share of On Shift Cases).',
  Pct Trauma Of Shift COMMENT 'Share of on-shift exams that are Trauma-priority exams, a fraction 0-1 (= Trauma Cases / On Shift Cases). = PowerBI [% Trauma] (Mosaic Impact).',
  OtherP Cases COMMENT 'Building block: number of exams with a priority outside Routine/Stat/Stroke/Trauma read during shifts. Feeds Pct OtherP Of Shift (share of On Shift Cases).',
  Pct OtherP Of Shift COMMENT 'Share of on-shift exams that are exams with a priority outside Routine/Stat/Stroke/Trauma, a fraction 0-1 (= OtherP Cases / On Shift Cases). = PowerBI [% OtherP] (Mosaic Impact).',
  ER Cases COMMENT 'Building block: number of emergency (ED care setting) exams read during shifts. Feeds Pct ER Of Shift (share of On Shift Cases).',
  Pct ER Of Shift COMMENT 'Share of on-shift exams that are emergency (ED care setting) exams, a fraction 0-1 (= ER Cases / On Shift Cases). = PowerBI [% ER] (Mosaic Impact).',
  Inpatient Cases COMMENT 'Building block: number of inpatient exams read during shifts. Feeds Pct Inpatient Of Shift (share of On Shift Cases).',
  Pct Inpatient Of Shift COMMENT 'Share of on-shift exams that are inpatient exams, a fraction 0-1 (= Inpatient Cases / On Shift Cases). = PowerBI [% Inpatient] (Mosaic Impact).',
  Outpatient Cases COMMENT 'Building block: number of outpatient exams read during shifts. Feeds Pct Outpatient Of Shift (share of On Shift Cases).',
  Pct Outpatient Of Shift COMMENT 'Share of on-shift exams that are outpatient exams, a fraction 0-1 (= Outpatient Cases / On Shift Cases). = PowerBI [% Outpatient] (Mosaic Impact).',
  Mosaic Cases COMMENT 'Building block: number of exams read in Mosaic read during shifts. Feeds Pct Mosaic Of Shift (share of On Shift Cases).',
  Pct Mosaic Of Shift COMMENT 'Share of on-shift exams that are exams read in Mosaic, a fraction 0-1 (= Mosaic Cases / On Shift Cases). = PowerBI [% Mosaic] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view [Pct Mosaic].',
  Mosaic Drafting Cases COMMENT 'Building block: number of exams drafted in Mosaic (AI Drafting) read during shifts. Feeds Pct Mosaic Drafting Of Shift (share of On Shift Cases).',
  Pct Mosaic Drafting Of Shift COMMENT 'Share of on-shift exams that are exams drafted in Mosaic (AI Drafting), a fraction 0-1 (= Mosaic Drafting Cases / On Shift Cases). = PowerBI [% Mosaic Drafting] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view [Pct Mosaic Drafting].',
  Captured US In Mosaic Cases COMMENT 'Building block: number of ultrasound exams captured in Mosaic (Mosaic draft flag) read during shifts. Feeds Pct Captured US In Mosaic Of Shift (share of On Shift Cases).',
  Pct Captured US In Mosaic Of Shift COMMENT 'Share of on-shift exams that are ultrasound exams captured in Mosaic (Mosaic draft flag), a fraction 0-1 (= Captured US In Mosaic Cases / On Shift Cases). = PowerBI [% Mosaic Capture] (Mosaic Impact).',
  Assigned Cases COMMENT 'Building block: number of exams self-assigned by the radiologist read during shifts. Feeds Pct Assigned Of Shift (share of On Shift Cases). Assigned + Pool + Autonext = On Shift Cases.',
  Pct Assigned Of Shift COMMENT 'Share of on-shift exams that are exams self-assigned by the radiologist, a fraction 0-1 (= Assigned Cases / On Shift Cases). = PowerBI [% Assigned] (Mosaic Impact).',
  Pool Cases COMMENT 'Building block: number of exams taken from the shared worklist pool (neither self-assigned nor Autonext) read during shifts. Feeds Pct Pool Of Shift (share of On Shift Cases). Assigned + Pool + Autonext = On Shift Cases.',
  Pct Pool Of Shift COMMENT 'Share of on-shift exams that are exams taken from the shared worklist pool (neither self-assigned nor Autonext), a fraction 0-1 (= Pool Cases / On Shift Cases). = PowerBI [% Pool] (Mosaic Impact).',
  Autonext Cases COMMENT 'Building block: number of exams served by Autonext read during shifts. Feeds Pct Autonext Of Shift (share of On Shift Cases). Assigned + Pool + Autonext = On Shift Cases.',
  Pct Autonext Of Shift COMMENT 'Share of on-shift exams that are exams served by Autonext, a fraction 0-1 (= Autonext Cases / On Shift Cases). = PowerBI [% Autonext] (Mosaic Impact).',
  VRA Assisted Cases COMMENT 'Building block: on-shift exams assisted by VRA (VRA flag). Feeds Pct VRA Assisted. = PowerBI [On-Shift Assisted Cases] (Mosaic Impact).',
  Non IR Stroke Trauma Cases COMMENT 'Building block: on-shift exams excluding IR and Stroke/Trauma priority - the denominator for Pct VRA Assisted, matching the PowerBI DAX exactly (not On Shift Cases).',
  Pct VRA Assisted COMMENT 'Share of VRA-eligible on-shift exams (excluding IR, Stroke and Trauma) that were VRA-assisted, a fraction 0-1. = PowerBI [% VRA Assisted] / [% Assisted] (Mosaic Impact).')
COMMENT 'MOSAIC CAPACITY DETAIL (draft, edw_test only). One row per radiologist shift (shifts from 2024-10-01): summed on-shift TBWU (RPWU) and RVU capacity vs each radiologist\'s own POS-adjusted TBWU 26 baseline (tbl_mosaic_baseline_master), hour-weighted utilization (reading time / shift time), efficiency per read-minute, and the full on-shift case mix (modality, priority, place of service, Mosaic use, assignment method, VRA). No PowerBI default filters are applied here (all shift lengths, shifts with and without a baseline). For exec added-capacity, capacity-per-shift and utilization numbers use the PowerBI-parity view mosaic_capacity_pbi_metric_view; use this view for case mix, per-hour normalisation and diagnostics. PowerBI mappings below are not yet parity-verified.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_test.enterprise_analytics.tbl_capacity_shift_level_vw

joins:
  - name: dim_team_rollup
    source: edw_test.enterprise_analytics.tbl_team_rollups
    "on": source.team = dim_team_rollup.Team

comment: "MOSAIC CAPACITY DETAIL (draft, edw_test only). One row per radiologist shift\
  \ (shifts from 2024-10-01): summed on-shift TBWU (RPWU) and RVU capacity vs each\
  \ radiologist's own POS-adjusted TBWU 26 baseline (tbl_mosaic_baseline_master),\
  \ hour-weighted utilization (reading time / shift time), efficiency per read-minute,\
  \ and the full on-shift case mix (modality, priority, place of service, Mosaic use,\
  \ assignment method, VRA). No PowerBI default filters are applied here (all shift\
  \ lengths, shifts with and without a baseline). For exec added-capacity, capacity-per-shift\
  \ and utilization numbers use the PowerBI-parity view mosaic_capacity_pbi_metric_view;\
  \ use this view for case mix, per-hour normalisation and diagnostics. PowerBI mappings\
  \ below are not yet parity-verified."

dimensions:
  - name: NPI
    expr: source.npi
    comment: "Radiologist's National Provider Identifier (10-digit ID, text). Use\
      \ to identify a radiologist unambiguously."
    display_name: Radiologist NPI
    synonyms:
      - NPI number
      - provider ID
      - national provider identifier

  - name: Radiologist Name
    expr: source.radiologist_name
    comment: "Radiologist name, 'Last, First M'. Match partial names with ILIKE '%name%'."
    display_name: Radiologist Name
    synonyms:
      - radiologist
      - rad
      - doctor
      - physician

  - name: Team
    expr: source.team
    comment: "Radiologist's roster team, a sub-team finer than Team Rolled Up (Provider\
      \ Practice), e.g. 'RAF Tampa'. For the radiologist's home practice use Team\
      \ Rolled Up."
    display_name: Team
    synonyms:
      - sub team
      - roster team

  - name: Team Rolled Up
    expr: dim_team_rollup.Team_Roll_Up
    comment: "Provider Practice = the radiologist's home practice (PowerBI 'Team Rolled\
      \ up'): Team mapped to its parent grouping via the team_rollups lookup, same\
      \ join as the Volume metric view. Not the exam site's practice - that is Practice."
    display_name: Provider Practice (Team Rolled Up)
    synonyms:
      - provider practice
      - home practice
      - rolled up team
      - group

  - name: Local Region
    expr: "CASE WHEN source.team IN ('ESR','LFI','Jefferson','GLI','RAI','RP Cascade','RP\
      \ Crossroads','JR','DRSRP','RP East Florida','RP North Florida','RP Palm Beach','RP\
      \ Florida West','PRA','ESRMH Garnet','ESRMH Hackensack','ESRMH Legacy','ESR\
      \ Long Island','ESR Metro Hudson','SEAL Team','SEAL Legacy','vRad','Spec Ops\
      \ Reserve') THEN 'Special Operations' WHEN source.team IN ('ADI','ADR','CRC\
      \ Central','CRC NW','CRC SW','Midstate','NEOH','Rad Alliance','RP Kentucky','RP\
      \ Bluegrass','RAC','RACSW','RPKY','RPBG','RA','ADR Legacy','CRC','Rad Alliance\
      \ Legacy','Rad Alliance NorthCrest','RP Bluegrass Legacy') THEN 'Apex' WHEN\
      \ source.team IN ('Coastal','Greensboro','MBB','Northside','Greensboro Canopy','RAF','RP\
      \ Florida','RP Sandhills','RP South Carolina','SOAR','BOCA','GR','NRA','RASF','MBB\
      \ Legacy','MBB Phoebe Putney','Northside Radiology','RAF East Coast','RAF Panhandle','RAF\
      \ Sarasota','RAF Tampa','RAF Tele','RASF Miami','RASF Naples','RP Florida Legacy')\
      \ THEN 'Genesis' WHEN source.team IN ('Advanced Radiology','Alaska','CIR','Desert','GIMA','RP\
      \ SoCal','IAM','IAMSE','MIA','Mountain','NIR','RAA','MXC','Red Rock','RIMA','RP\
      \ Sol','RP Sun City','RP Chicago','RP Forest City','Saline Valley','RP Valley\
      \ Radiologists','SVDI','Western Colorado','WIR','RP IOWA','GSIA','SVL','MR','DR','NWIR','ARSC','DR\
      \ Legacy','DR DRS','IAMSE Hurley','IAM Marquette','IAM Midlands','Lakefront\
      \ Imaging','Mountain Legacy','Mountain Yampa','RP NWIR','RP SMIL','RP SoCal\
      \ Lakewood','RP SoCal Legacy','RP SoCal Palmdale','RP Valley','SVDI Legacy','SVDI\
      \ San Ramon','SMI','RIMA California') THEN 'Maverick' WHEN source.team IN ('Access\
      \ Alexandria','ARA','BR Academic','BR Community','CIRPA','Community','RP Eagle','EBI','GIA','Lake\
      \ Charles','RP Borderlands','RP Brazosport','RP Corpus Christi','RP Dallas','RP\
      \ El Paso','RP Gulf Coast','RP Houston','RP Laredo','RP Victoria','BR','Slidell','ACC','RPNM','EAG','RPEP','RPGC','RPH','Other','EXTHMC','RP\
      \ Singleton Academic','RP Singleton Community','RP Singleton','Rose','RP North\
      \ Houston','Synergy','Access Lake Charles','Community Laredo','Community Legacy','Community\
      \ Victoria','Elite','RP Borderlands Legacy','RP Borderlands Lovelace','RP Helios')\
      \ THEN 'Trailblazer' ELSE 'Matrix' END"
    comment: "One of 6 fixed regions keyed on Team: Special Operations, Apex, Genesis,\
      \ Maverick, Trailblazer, Matrix (unmapped teams fall into Matrix here). Matches\
      \ PowerBI '0. Cur'[Local], same mapping as the Volume and Efficiency views."
    display_name: Local Region
    synonyms:
      - region
      - local
      - operating region

  - name: Practice
    expr: source.practice
    comment: "Managing Practice = the practice owning the exam SITE (PowerBI 'Practice'),\
      \ one per shift (if a shift spans several sites the alphabetically highest is\
      \ kept). Same Team-vs-Practice convention as the efficiency exam-level view;\
      \ the home practice is Team Rolled Up."
    display_name: Managing Practice
    synonyms:
      - site practice
      - exam site practice
      - practice of the shift

  - name: Shift Name
    expr: source.shift_name
    comment: "Name of the scheduled shift the radiologist worked (from the shift schedule);\
      \ one row per radiologist, date, shift name and task."
    display_name: Shift Name
    synonyms:
      - schedule shift
      - shift label
      - shift schedule name

  - name: Shift Date
    expr: source.shift_date
    comment: Date of the radiologist's shift (shifts from 2024-10-01 onward). Bind
      date-range filters here.
    display_name: Shift Date
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - date of shift
      - shift day
      - date worked

  - name: Shift Month
    expr: "DATE_TRUNC('MONTH', source.shift_date)"
    comment: "Calendar month of the shift, as the first day of the month (e.g. 2026-09-01).\
      \ Use for monthly trends; the current month is partial."
    display_name: Shift Month
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - month
      - shift calendar month
      - month of shift

  - name: Baseline Type
    expr: source.baseline_type
    comment: "How the shift's TBWU 26 baseline was matched: Exact, Proxy or Manual\
      \ Review; NULL = no baseline matched (from tbl_mosaic_baseline_master). Filter\
      \ to NOT NULL for like-for-like capacity-vs-baseline comparisons."
    display_name: Baseline Type
    synonyms:
      - baseline method
      - baseline match type
      - how baseline was matched

  - name: Is RPCE Source
    expr: source.is_rpce_source
    comment: "TRUE if the shift has RPCE-sourced exams (rpceMidwest / rpceSouthwest).\
      \ Usually means reliable dictation timestamps but NOT always (2026-10-22: RP\
      \ Valley ~100% RPCE yet 88.7% missing timestamps). Use Pct Exams With Valid\
      \ Read Time as the trust signal, not this flag."
    display_name: Is RPCE Source
    synonyms:
      - RPCE flag
      - RPCE sourced shift
      - RPCE system

measures:
  - name: On Shift Cases
    expr: SUM(source.on_shift_cases)
    comment: "Total exams read during scheduled shifts (all shifts, with or without\
      \ a baseline). Denominator for every 'Pct ... Of Shift' case-mix measure. =\
      \ PowerBI [On-Shift Cases] (Mosaic Impact)."
    display_name: On-Shift Cases
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - exams read on shift
      - shift case volume
      - cases read during shifts

  - name: Total Hours
    expr: SUM(source.no_hours)
    comment: "Building block: total scheduled shift hours. Feeds the Per Hour / Per\
      \ 9Hour capacity and baseline measures and On Shift Utilization Pct."
    display_name: Total Shift Hours
    format:
      type: number
      decimal_places:
        type: max
        places: 1
    synonyms:
      - scheduled hours
      - hours worked on shift
      - shift hours total

  - name: On Shift Capacity RPWU
    expr: SUM(source.on_shift_capacity_rpwu)
    comment: "Total workload read on shift, in TBWU (RPWU), summed over all shifts\
      \ in scope with or without a baseline. = PowerBI [On-Shift Capacity] (Mosaic\
      \ Impact). For exec reporting use mosaic_capacity_pbi_metric_view [New Capacity]\
      \ (average per shift)."
    display_name: On-Shift Capacity (Total TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - summed TBWU capacity
      - total TBWU read on shift
      - total RPWU on shift

  - name: On Shift Capacity RVU
    expr: SUM(source.on_shift_capacity_rvu)
    comment: "Total workload read on shift in RVU (billing units), summed over all\
      \ shifts in scope. RVU counterpart of On Shift Capacity RPWU. = PowerBI [On-Shift\
      \ Capacity] (Mosaic Impact, RVU unit)."
    display_name: On-Shift Capacity (Total RVU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - summed RVU capacity
      - total RVU read on shift
      - RVUs on shift

  - name: On Shift Capacity RPWU Per Hour
    expr: MEASURE(`On Shift Capacity RPWU`) / MEASURE(`Total Hours`)
    comment: "On-shift TBWU per scheduled shift hour (total TBWU / total hours, hour-weighted).\
      \ All shifts in scope, with or without a baseline."
    display_name: On-Shift Capacity per Hour (TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - TBWU per shift hour
      - hourly TBWU capacity
      - RPWU per hour

  - name: On Shift Capacity RPWU Per 9Hour
    expr: MEASURE(`On Shift Capacity RPWU Per Hour`) * 9
    comment: "On-shift TBWU per hour scaled to a standard 9-hour shift. = PowerBI\
      \ [New Capacity RPWU 9h(Top N)] (Mosaic Impact). For exec capacity per shift\
      \ use mosaic_capacity_pbi_metric_view [New Capacity]."
    display_name: On-Shift Capacity per 9-Hour Shift (TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - TBWU per 9 hour shift
      - 9-hour normalised TBWU capacity
      - RPWU per 9 hours

  - name: On Shift Capacity RVU Per Hour
    expr: MEASURE(`On Shift Capacity RVU`) / MEASURE(`Total Hours`)
    comment: "On-shift RVU per scheduled shift hour (total RVU / total hours, hour-weighted)."
    display_name: On-Shift Capacity per Hour (RVU)
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - RVU per shift hour
      - hourly RVU capacity

  - name: On Shift Capacity RVU Per 9Hour
    expr: MEASURE(`On Shift Capacity RVU Per Hour`) * 9
    comment: On-shift RVU per hour scaled to a standard 9-hour shift.
    display_name: On-Shift Capacity per 9-Hour Shift (RVU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - RVU per 9 hour shift
      - 9-hour normalised RVU capacity

  - name: Shift Baseline RPWU
    expr: SUM(source.shift_baseline_rpwu)
    comment: "Total pre-Mosaic baseline (TBWU 26, rescaled to shift hours), summed\
      \ only over shifts with a matched baseline (Baseline Type not null; NULL-safe).\
      \ = PowerBI [Shift Baseline] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view\
      \ [Average Baseline]."
    display_name: Shift Baseline (Total TBWU 26)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - summed baseline TBWU
      - total baseline TBWU
      - baseline RPWU total

  - name: Shift Baseline RPWU Per Hour
    expr: MEASURE(`Shift Baseline RPWU`) / MEASURE(`Total Hours`)
    comment: "Baseline TBWU per scheduled hour. Caveat: divides baselined-shift baseline\
      \ by the hours of ALL shifts, so it is understated unless filtered to Baseline\
      \ Type not null."
    display_name: Shift Baseline per Hour (TBWU 26)
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - baseline TBWU per hour
      - hourly baseline

  - name: Shift Baseline RPWU Per 9Hour
    expr: MEASURE(`Shift Baseline RPWU Per Hour`) * 9
    comment: "Baseline TBWU per hour scaled to a standard 9-hour shift. Same caveat\
      \ as the per-hour baseline: filter to Baseline Type not null for a like-for-like\
      \ figure."
    display_name: Shift Baseline per 9-Hour Shift (TBWU 26)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - baseline TBWU per 9 hour shift
      - 9-hour normalised baseline

  - name: Shifts With Baseline
    expr: SUM(CASE WHEN source.baseline_type IS NOT NULL THEN 1 ELSE 0 END)
    comment: "Building block: number of shifts with a matched TBWU 26 baseline (Baseline\
      \ Type not null). Feeds Pct Shifts With Baseline."
    display_name: Shifts With a Baseline
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - baselined shifts
      - shifts with matched baseline

  - name: Pct Shifts With Baseline
    expr: MEASURE(`Shifts With Baseline`) / COUNT(1)
    comment: "Share of shifts that have a matched baseline, a fraction 0-1. Low coverage\
      \ means capacity-vs-baseline measures describe only part of the work."
    display_name: '% Shifts With a Baseline'
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - baseline coverage
      - share of shifts baselined
      - baseline match rate

  - name: On Shift Capacity Vs Baseline RPWU
    expr: MEASURE(`On Shift Capacity RPWU`) - MEASURE(`Shift Baseline RPWU`)
    comment: "Total on-shift TBWU minus total baseline TBWU (positive = above baseline).\
      \ Caveat: capacity includes all shifts, baseline only baselined ones - filter\
      \ Baseline Type not null. = PowerBI [On-Shift Capacity v. BL] (Mosaic Impact).\
      \ Exec: mosaic_capacity_pbi_metric_view [Pct Addl Capacity]."
    display_name: On-Shift Capacity vs Baseline (Total TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - summed TBWU above baseline
      - total capacity gain vs baseline
      - net TBWU vs baseline

  - name: On Shift Capacity Vs Baseline RPWU Per Hour
    expr: MEASURE(`On Shift Capacity RPWU Per Hour`) - MEASURE(`Shift Baseline RPWU
      Per Hour`)
    comment: "On-shift TBWU per hour minus baseline TBWU per hour (positive = above\
      \ baseline). Filter Baseline Type not null for like-for-like. For exec added\
      \ capacity use mosaic_capacity_pbi_metric_view [Addl Capacity Per Shift]."
    display_name: On-Shift Capacity vs Baseline per Hour (TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 3
    synonyms:
      - hourly TBWU gain vs baseline
      - TBWU per hour above baseline

  - name: On Shift Above Baseline RPWU
    expr: "SUM(GREATEST(source.on_shift_capacity_rpwu - COALESCE(source.shift_baseline_rpwu,\
      \ source.on_shift_capacity_rpwu), 0))"
    comment: "Portion of on-shift TBWU above each shift's baseline, summed (0 for\
      \ shifts at/under baseline or with no baseline). Stacks with On Shift Up To\
      \ Baseline RPWU to total capacity. = PowerBI [On-Shift Capacity Above BL(Unit)]\
      \ (Mosaic Impact)."
    display_name: On-Shift Capacity Above Baseline (TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - TBWU above baseline
      - capacity exceeding baseline
      - above-baseline workload

  - name: On Shift Up To Baseline RPWU
    expr: "SUM(LEAST(source.on_shift_capacity_rpwu, COALESCE(source.shift_baseline_rpwu,\
      \ source.on_shift_capacity_rpwu)))"
    comment: "Portion of on-shift TBWU at/under each shift's baseline, summed; shifts\
      \ with no baseline count fully here. Pairs with On Shift Above Baseline RPWU\
      \ for a stacked view (together = total capacity). = PowerBI [On-Shift Capacity\
      \ Up to BL(Unit)] (Mosaic Impact)."
    display_name: On-Shift Capacity Up to Baseline (TBWU)
    format:
      type: number
      decimal_places:
        type: max
        places: 2
    synonyms:
      - TBWU up to baseline
      - capacity within baseline
      - at-or-below-baseline workload

  - name: Read Minutes
    expr: SUM(source.shift_read_minutes)
    comment: "Building block: total reading (dictation) minutes on shift, from exams\
      \ with valid timestamps only, each exam capped at 60 minutes. Feeds On Shift\
      \ Utilization Pct and On Shift Efficiency."
    display_name: Reading Minutes on Shift
    format:
      type: number
      decimal_places:
        type: max
        places: 1
    synonyms:
      - dictation minutes
      - reading time minutes
      - read time on shift

  - name: Exams With Valid Read Time
    expr: SUM(source.exams_with_valid_read_time)
    comment: "Building block: exams with usable dictation timestamps (start, end and\
      \ final all present) - the population Read Minutes, efficiency and utilization\
      \ are actually computed over. Feeds Pct Exams With Valid Read Time."
    display_name: Exams With Valid Read Time
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - exams with dictation timestamps
      - timed exams
      - exams with usable read time

  - name: Pct Exams With Valid Read Time
    expr: MEASURE(`Exams With Valid Read Time`) / MEASURE(`On Shift Cases`)
    comment: "ALWAYS CHECK before trusting efficiency or utilization for a slice:\
      \ share of on-shift exams with usable dictation timestamps, a fraction 0-1.\
      \ Coverage varies enormously by practice (live: 0.03% to 66%+), independent\
      \ of Is RPCE Source."
    display_name: '% Exams With Valid Read Time'
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - read time coverage
      - timestamp coverage
      - dictation timestamp coverage

  - name: On Shift Utilization Pct
    expr: "LEAST(MEASURE(`Read Minutes`) / (MEASURE(`Total Hours`) * 60), 1.0)"
    comment: "Hour-weighted utilization: total reading minutes / total shift minutes,\
      \ a fraction 0-1, capped at 1 (100%). Check Pct Exams With Valid Read Time alongside\
      \ it. = PowerBI [On-Shift Utilization]. Exec: mosaic_capacity_pbi_metric_view\
      \ [New Utilization]."
    display_name: On-Shift Utilization (Hour-Weighted)
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - hour-weighted utilization
      - pooled reading time share
      - read minutes over shift minutes

  - name: On Shift Efficiency RPWU
    expr: MEASURE(`On Shift Capacity RPWU`) / MEASURE(`Read Minutes`)
    comment: "TBWU read per reading minute (total TBWU / total read minutes). Capacity\
      \ counts all cases but read minutes only exams with valid timestamps - check\
      \ Pct Exams With Valid Read Time. = PowerBI [On-Shift Efficiency] (Mosaic Impact).\
      \ Exec: mosaic_capacity_pbi_metric_view [New Efficiency]."
    display_name: On-Shift Efficiency (TBWU per Read Minute)
    format:
      type: number
      decimal_places:
        type: max
        places: 4
    synonyms:
      - TBWU per read minute
      - pooled shift efficiency
      - RPWU per reading minute

  - name: On Shift Efficiency RVU
    expr: MEASURE(`On Shift Capacity RVU`) / MEASURE(`Read Minutes`)
    comment: "RVU read per reading minute (total RVU / total read minutes); same read-time\
      \ coverage caveat as the TBWU version. = PowerBI [On-Shift Efficiency] (Mosaic\
      \ Impact, RVU unit)."
    display_name: On-Shift Efficiency (RVU per Read Minute)
    format:
      type: number
      decimal_places:
        type: max
        places: 4
    synonyms:
      - RVU per read minute
      - RVU efficiency on shift

  - name: CT Cases
    expr: SUM(source.ct_cases)
    comment: "Building block: number of CT exams read during shifts. Feeds Pct CT\
      \ Of Shift (share of On Shift Cases)."
    display_name: CT Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - CT exams on shift
      - CT volume on shift

  - name: Pct CT Of Shift
    expr: MEASURE(`CT Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are CT exams, a fraction 0-1 (= CT Cases\
      \ / On Shift Cases). = PowerBI [% CT] (Mosaic Impact)."
    display_name: "% of Shift Cases: CT"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - CT share of shift cases
      - '% CT on shift'
      - CT mix on shift

  - name: XR Cases
    expr: SUM(source.xr_cases)
    comment: "Building block: number of X-ray exams (source modality code CR) read\
      \ during shifts. Feeds Pct XR Of Shift (share of On Shift Cases)."
    display_name: XR Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - X-ray exams on shift
      - XR volume on shift

  - name: Pct XR Of Shift
    expr: MEASURE(`XR Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are X-ray exams (source modality code CR),\
      \ a fraction 0-1 (= XR Cases / On Shift Cases). = PowerBI [% XR] (Mosaic Impact)."
    display_name: "% of Shift Cases: XR"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - X-ray share of shift cases
      - '% XR on shift'
      - XR mix on shift

  - name: US Cases
    expr: SUM(source.us_cases)
    comment: "Building block: number of ultrasound exams read during shifts. Feeds\
      \ Pct US Of Shift (share of On Shift Cases)."
    display_name: US Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - ultrasound exams on shift
      - US volume on shift

  - name: Pct US Of Shift
    expr: MEASURE(`US Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are ultrasound exams, a fraction 0-1 (=\
      \ US Cases / On Shift Cases). = PowerBI [% US] (Mosaic Impact)."
    display_name: "% of Shift Cases: US"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - ultrasound share of shift cases
      - '% US on shift'
      - US mix on shift

  - name: MR Cases
    expr: SUM(source.mr_cases)
    comment: "Building block: number of MRI exams read during shifts. Feeds Pct MR\
      \ Of Shift (share of On Shift Cases)."
    display_name: MR Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - MRI exams on shift
      - MR volume on shift

  - name: Pct MR Of Shift
    expr: MEASURE(`MR Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are MRI exams, a fraction 0-1 (= MR Cases\
      \ / On Shift Cases). = PowerBI [% MR] (Mosaic Impact)."
    display_name: "% of Shift Cases: MR"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - MRI share of shift cases
      - '% MR on shift'
      - MR mix on shift

  - name: NM Cases
    expr: SUM(source.nm_cases)
    comment: "Building block: number of nuclear medicine exams read during shifts.\
      \ Feeds Pct NM Of Shift (share of On Shift Cases)."
    display_name: NM Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - nuclear medicine exams on shift
      - NM volume on shift

  - name: Pct NM Of Shift
    expr: MEASURE(`NM Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are nuclear medicine exams, a fraction\
      \ 0-1 (= NM Cases / On Shift Cases). = PowerBI [% NM] (Mosaic Impact)."
    display_name: "% of Shift Cases: NM"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - nuclear medicine share of shift cases
      - '% NM on shift'

  - name: PT Cases
    expr: SUM(source.pt_cases)
    comment: "Building block: number of PET exams read during shifts. Feeds Pct PT\
      \ Of Shift (share of On Shift Cases)."
    display_name: PT Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - PET exams on shift
      - PT volume on shift

  - name: Pct PT Of Shift
    expr: MEASURE(`PT Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are PET exams, a fraction 0-1 (= PT Cases\
      \ / On Shift Cases). = PowerBI [% PT] (Mosaic Impact)."
    display_name: "% of Shift Cases: PT"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - PET share of shift cases
      - '% PT on shift'

  - name: MG Cases
    expr: SUM(source.mg_cases)
    comment: "Building block: number of mammography exams read during shifts. Feeds\
      \ Pct MG Of Shift (share of On Shift Cases)."
    display_name: MG Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - mammography exams on shift
      - MG volume on shift

  - name: Pct MG Of Shift
    expr: MEASURE(`MG Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are mammography exams, a fraction 0-1 (=\
      \ MG Cases / On Shift Cases). = PowerBI [% MG] (Mosaic Impact)."
    display_name: "% of Shift Cases: MG"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - mammography share of shift cases
      - '% MG on shift'

  - name: IR Cases
    expr: SUM(source.ir_cases)
    comment: "Building block: number of interventional radiology exams read during\
      \ shifts. Feeds Pct IR Of Shift (share of On Shift Cases)."
    display_name: IR Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - IR exams on shift
      - IR volume on shift

  - name: Pct IR Of Shift
    expr: MEASURE(`IR Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are interventional radiology exams, a fraction\
      \ 0-1 (= IR Cases / On Shift Cases). = PowerBI [% IR] (Mosaic Impact)."
    display_name: "% of Shift Cases: IR"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - IR share of shift cases
      - '% IR on shift'

  - name: Other Modality Cases
    expr: SUM(source.other_modality_cases)
    comment: "Building block: number of exams in modalities other than CT/XR/US/MR/NM/PT/MG/IR\
      \ read during shifts. Feeds Pct Other Modality Of Shift (share of On Shift Cases)."
    display_name: Other Modality Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - other modality exams on shift
      - other modality volume on shift

  - name: Pct Other Modality Of Shift
    expr: MEASURE(`Other Modality Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams in modalities other than CT/XR/US/MR/NM/PT/MG/IR,\
      \ a fraction 0-1 (= Other Modality Cases / On Shift Cases). = PowerBI [% Other\
      \ Modality] (Mosaic Impact)."
    display_name: "% of Shift Cases: Other Modality"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - other modality share of shift cases
      - '% other modality on shift'

  - name: Routine Cases
    expr: SUM(source.routine_cases)
    comment: "Building block: number of Routine-priority exams read during shifts.\
      \ Feeds Pct Routine Of Shift (share of On Shift Cases)."
    display_name: Routine Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - routine exams on shift
      - routine priority volume on shift

  - name: Pct Routine Of Shift
    expr: MEASURE(`Routine Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are Routine-priority exams, a fraction\
      \ 0-1 (= Routine Cases / On Shift Cases). = PowerBI [% Routine] (Mosaic Impact)."
    display_name: "% of Shift Cases: Routine"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - routine share of shift cases
      - '% routine on shift'

  - name: Stat Cases
    expr: SUM(source.stat_cases)
    comment: "Building block: number of Stat-priority exams read during shifts. Feeds\
      \ Pct Stat Of Shift (share of On Shift Cases)."
    display_name: Stat Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - stat exams on shift
      - stat priority volume on shift

  - name: Pct Stat Of Shift
    expr: MEASURE(`Stat Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are Stat-priority exams, a fraction 0-1\
      \ (= Stat Cases / On Shift Cases). = PowerBI [% Stat] (Mosaic Impact)."
    display_name: "% of Shift Cases: Stat"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - stat share of shift cases
      - '% stat on shift'

  - name: Stroke Cases
    expr: SUM(source.stroke_cases)
    comment: "Building block: number of Stroke-priority exams read during shifts.\
      \ Feeds Pct Stroke Of Shift (share of On Shift Cases)."
    display_name: Stroke Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - stroke exams on shift
      - stroke priority volume on shift

  - name: Pct Stroke Of Shift
    expr: MEASURE(`Stroke Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are Stroke-priority exams, a fraction 0-1\
      \ (= Stroke Cases / On Shift Cases). = PowerBI [% Stroke] (Mosaic Impact)."
    display_name: "% of Shift Cases: Stroke"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - stroke share of shift cases
      - '% stroke on shift'

  - name: Trauma Cases
    expr: SUM(source.trauma_cases)
    comment: "Building block: number of Trauma-priority exams read during shifts.\
      \ Feeds Pct Trauma Of Shift (share of On Shift Cases)."
    display_name: Trauma Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - trauma exams on shift
      - trauma priority volume on shift

  - name: Pct Trauma Of Shift
    expr: MEASURE(`Trauma Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are Trauma-priority exams, a fraction 0-1\
      \ (= Trauma Cases / On Shift Cases). = PowerBI [% Trauma] (Mosaic Impact)."
    display_name: "% of Shift Cases: Trauma"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - trauma share of shift cases
      - '% trauma on shift'

  - name: OtherP Cases
    expr: SUM(source.otherp_cases)
    comment: "Building block: number of exams with a priority outside Routine/Stat/Stroke/Trauma\
      \ read during shifts. Feeds Pct OtherP Of Shift (share of On Shift Cases)."
    display_name: Other Priority Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - other priority exams on shift
      - other priority volume on shift

  - name: Pct OtherP Of Shift
    expr: MEASURE(`OtherP Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams with a priority outside Routine/Stat/Stroke/Trauma,\
      \ a fraction 0-1 (= OtherP Cases / On Shift Cases). = PowerBI [% OtherP] (Mosaic\
      \ Impact)."
    display_name: "% of Shift Cases: Other Priority"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - other priority share of shift cases
      - '% other priority on shift'

  - name: ER Cases
    expr: SUM(source.er_cases)
    comment: "Building block: number of emergency (ED care setting) exams read during\
      \ shifts. Feeds Pct ER Of Shift (share of On Shift Cases)."
    display_name: ER Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - ER exams on shift
      - emergency volume on shift

  - name: Pct ER Of Shift
    expr: MEASURE(`ER Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are emergency (ED care setting) exams,\
      \ a fraction 0-1 (= ER Cases / On Shift Cases). = PowerBI [% ER] (Mosaic Impact)."
    display_name: "% of Shift Cases: ER"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - ER share of shift cases
      - '% ER on shift'
      - emergency share on shift

  - name: Inpatient Cases
    expr: SUM(source.inpatient_cases)
    comment: "Building block: number of inpatient exams read during shifts. Feeds\
      \ Pct Inpatient Of Shift (share of On Shift Cases)."
    display_name: Inpatient Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - inpatient exams on shift
      - inpatient volume on shift

  - name: Pct Inpatient Of Shift
    expr: MEASURE(`Inpatient Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are inpatient exams, a fraction 0-1 (=\
      \ Inpatient Cases / On Shift Cases). = PowerBI [% Inpatient] (Mosaic Impact)."
    display_name: "% of Shift Cases: Inpatient"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - inpatient share of shift cases
      - '% inpatient on shift'

  - name: Outpatient Cases
    expr: SUM(source.outpatient_cases)
    comment: "Building block: number of outpatient exams read during shifts. Feeds\
      \ Pct Outpatient Of Shift (share of On Shift Cases)."
    display_name: Outpatient Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - outpatient exams on shift
      - outpatient volume on shift

  - name: Pct Outpatient Of Shift
    expr: MEASURE(`Outpatient Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are outpatient exams, a fraction 0-1 (=\
      \ Outpatient Cases / On Shift Cases). = PowerBI [% Outpatient] (Mosaic Impact)."
    display_name: "% of Shift Cases: Outpatient"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - outpatient share of shift cases
      - '% outpatient on shift'

  - name: Mosaic Cases
    expr: SUM(source.mosaic_cases)
    comment: "Building block: number of exams read in Mosaic read during shifts. Feeds\
      \ Pct Mosaic Of Shift (share of On Shift Cases)."
    display_name: Mosaic Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - Mosaic exams on shift
      - shift exams read in Mosaic

  - name: Pct Mosaic Of Shift
    expr: MEASURE(`Mosaic Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams read in Mosaic, a fraction 0-1\
      \ (= Mosaic Cases / On Shift Cases). = PowerBI [% Mosaic] (Mosaic Impact). For\
      \ exec reporting use mosaic_capacity_pbi_metric_view [Pct Mosaic]."
    display_name: "% of Shift Cases: Mosaic"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - Mosaic share of shift case mix
      - '% of shift cases in Mosaic (case mix)'

  - name: Mosaic Drafting Cases
    expr: SUM(source.drafting_cases)
    comment: "Building block: number of exams drafted in Mosaic (AI Drafting) read\
      \ during shifts. Feeds Pct Mosaic Drafting Of Shift (share of On Shift Cases)."
    display_name: Mosaic Drafting Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - drafted exams on shift
      - shift exams drafted in Mosaic

  - name: Pct Mosaic Drafting Of Shift
    expr: MEASURE(`Mosaic Drafting Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams drafted in Mosaic (AI Drafting),\
      \ a fraction 0-1 (= Mosaic Drafting Cases / On Shift Cases). = PowerBI [% Mosaic\
      \ Drafting] (Mosaic Impact). For exec reporting use mosaic_capacity_pbi_metric_view\
      \ [Pct Mosaic Drafting]."
    display_name: "% of Shift Cases: Mosaic Drafting"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - drafting share of shift case mix
      - '% of shift cases drafted (case mix)'

  - name: Captured US In Mosaic Cases
    expr: SUM(source.captured_us_in_mosaic_cases)
    comment: "Building block: number of ultrasound exams captured in Mosaic (Mosaic\
      \ draft flag) read during shifts. Feeds Pct Captured US In Mosaic Of Shift (share\
      \ of On Shift Cases)."
    display_name: Captured US in Mosaic Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - Mosaic-captured ultrasound on shift
      - captured US exams on shift

  - name: Pct Captured US In Mosaic Of Shift
    expr: MEASURE(`Captured US In Mosaic Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are ultrasound exams captured in Mosaic\
      \ (Mosaic draft flag), a fraction 0-1 (= Captured US In Mosaic Cases / On Shift\
      \ Cases). = PowerBI [% Mosaic Capture] (Mosaic Impact)."
    display_name: "% of Shift Cases: Captured US in Mosaic"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - '% Mosaic capture'
      - ultrasound capture share on shift
      - Mosaic US capture rate

  - name: Assigned Cases
    expr: SUM(source.assigned_cases)
    comment: "Building block: number of exams self-assigned by the radiologist read\
      \ during shifts. Feeds Pct Assigned Of Shift (share of On Shift Cases). Assigned\
      \ + Pool + Autonext = On Shift Cases."
    display_name: Assigned Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - self-assigned exams on shift
      - assigned volume on shift

  - name: Pct Assigned Of Shift
    expr: MEASURE(`Assigned Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams self-assigned by the radiologist,\
      \ a fraction 0-1 (= Assigned Cases / On Shift Cases). = PowerBI [% Assigned]\
      \ (Mosaic Impact)."
    display_name: "% of Shift Cases: Assigned"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - self-assigned share of shift cases
      - '% assigned on shift'

  - name: Pool Cases
    expr: SUM(source.pool_cases)
    comment: "Building block: number of exams taken from the shared worklist pool\
      \ (neither self-assigned nor Autonext) read during shifts. Feeds Pct Pool Of\
      \ Shift (share of On Shift Cases). Assigned + Pool + Autonext = On Shift Cases."
    display_name: Pool Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - pool exams on shift
      - worklist pool volume on shift

  - name: Pct Pool Of Shift
    expr: MEASURE(`Pool Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams taken from the shared worklist\
      \ pool (neither self-assigned nor Autonext), a fraction 0-1 (= Pool Cases /\
      \ On Shift Cases). = PowerBI [% Pool] (Mosaic Impact)."
    display_name: "% of Shift Cases: Pool"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - pool share of shift cases
      - '% pool on shift'

  - name: Autonext Cases
    expr: SUM(source.autonext_cases)
    comment: "Building block: number of exams served by Autonext read during shifts.\
      \ Feeds Pct Autonext Of Shift (share of On Shift Cases). Assigned + Pool + Autonext\
      \ = On Shift Cases."
    display_name: Autonext Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - Autonext exams on shift
      - Autonext volume on shift

  - name: Pct Autonext Of Shift
    expr: MEASURE(`Autonext Cases`) / MEASURE(`On Shift Cases`)
    comment: "Share of on-shift exams that are exams served by Autonext, a fraction\
      \ 0-1 (= Autonext Cases / On Shift Cases). = PowerBI [% Autonext] (Mosaic Impact)."
    display_name: "% of Shift Cases: Autonext"
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - Autonext share of shift cases
      - '% Autonext on shift'

  - name: VRA Assisted Cases
    expr: SUM(source.assisted_cases)
    comment: "Building block: on-shift exams assisted by VRA (VRA flag). Feeds Pct\
      \ VRA Assisted. = PowerBI [On-Shift Assisted Cases] (Mosaic Impact)."
    display_name: VRA-Assisted Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - VRA assisted exams
      - assisted exams on shift

  - name: Non IR Stroke Trauma Cases
    expr: SUM(source.non_ir_stroke_trauma_cases)
    comment: "Building block: on-shift exams excluding IR and Stroke/Trauma priority\
      \ - the denominator for Pct VRA Assisted, matching the PowerBI DAX exactly (not\
      \ On Shift Cases)."
    display_name: VRA-Eligible Cases on Shift
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
    synonyms:
      - VRA eligible exams
      - non-IR non-stroke non-trauma exams

  - name: Pct VRA Assisted
    expr: MEASURE(`VRA Assisted Cases`) / MEASURE(`Non IR Stroke Trauma Cases`)
    comment: "Share of VRA-eligible on-shift exams (excluding IR, Stroke and Trauma)\
      \ that were VRA-assisted, a fraction 0-1. = PowerBI [% VRA Assisted] / [% Assisted]\
      \ (Mosaic Impact)."
    display_name: '% VRA-Assisted Cases'
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
    synonyms:
      - VRA assist rate
      - '% assisted by VRA'
      - VRA usage on shift
$$
