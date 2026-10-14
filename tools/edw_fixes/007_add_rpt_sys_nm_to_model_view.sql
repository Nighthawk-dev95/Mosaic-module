-- Adds the Rpt_Sys_Nm_Code/Draft_Sys_Nm_Code resolution to model_mosaic_dailyvolume_vw -
-- the model/base layer, one level below presentation_mosaicdailyvolume_vw in the view
-- chain (model_mosaic_dailyvolume_vw -> presentation_mosaicdailyvolume_vw). Request
-- 2026-10-02: "implement that now in my base tables which are
-- edw_dev.bipa_analytics.model_mosaic_dailyvolume_vw and
-- edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw" - both views get the new
-- columns, but the join itself lives ONCE here; see 001_fix_true_mosaic_reporting_flag.sql
-- (rewritten alongside this file) for presentation_mosaicdailyvolume_vw's half, which is now
-- just a passthrough of z.Rpt_Sys_Nm_Code/z.Draft_Sys_Nm_Code from this view - no second
-- join at that layer, one source of truth.
--
-- Same join as the original % RPCE denominator work (see 001's header for the full
-- Rpt_Sys_Nm_Code/Draft_Sys_Nm_Code background/values): exam_fact (aliased e here, same as
-- model_mosaic_dailyvolume_vw's own existing alias) -> accum_exam_fact_vw on
-- Accum_Exam_ID = e.Exam_ID -> generic_code_dim, twice (once for Rpt_Sys_Nm_ID, once for
-- Draft_Sys_Nm_ID). Verified live 2026-10-02 against the current exam_fact (not a stale
-- check): 2,867,827 rows since 2026-09-01, 0 unmatched Rpt_Sys_Nm_ID joins.
--
-- Grain-safety check: this view's final SELECT already includes e.Exam_ID as a bare
-- (non-aggregated) column alongside `group by all` - since Exam_ID is unique per exam and
-- Rpt_Sys_Nm_Code/Draft_Sys_Nm_Code are a deterministic function of Exam_ID (via
-- accum_exam_fact_vw), adding them as two more bare columns cannot change the number of
-- groups/rows this view produces - no fan-out risk, confirmed by inspection of the join
-- cardinality (accum_exam_fact_vw is 1 row per Accum_Exam_ID, generic_code_dim is 1 row per
-- Generic_Cd_ID).
--
-- Mosaic_flag/mosaic_draft_flag themselves are NOT touched here - still plain passthrough
-- from e.Mosaic_flag/e.mosaic_draft_flag (EDW already fixed Msc_Rpt_Ind at the source,
-- confirmed earlier this session - no correction needed). Only the two new resolved-code
-- columns are added.
--
-- This file has NOT been run - the Databricks connector available to this session is
-- read-only. A human with CREATE VIEW on edw_dev.bipa_analytics needs to run it.
-- Deploy this file BEFORE (or together with) the rewritten 001 - presentation's passthrough
-- will return NULL for both new columns until this one is live.

CREATE OR REPLACE VIEW edw_dev.bipa_analytics.model_mosaic_dailyvolume_vw (
  Radiologist,
  Rad_Type,
  NPI,
  Physician_Partner_Status,
  working_subspecialty,
  practice_code COMMENT 'This column represents the code associated with the practice  under the old practice hierarchy associated with the imaging site',
  sub_practice_code COMMENT 'This column represents the code of the  sub-practice associated with the imaging site',
  Practice_Short_Name COMMENT 'This column represents the shortened name for the practice  under the old practice hierarchy associated with the imaging site',
  sub_practice_short_name COMMENT 'This column represents the shortened name for the sub-practice  under the old practice hierarchy associated with the imaging site',
  Location_Name,
  client_name COMMENT 'This column represents the name of the local client',
  Department_Name COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  Priority_Description COMMENT 'This column represents the exams Priority name ',
  Accession_Number COMMENT 'This column stores Radiology Accession Number which is unique identifier',
  Source_Procedure_Description COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  modality_code,
  Calendar_Date,
  Final_DateTime,
  Available_To_MD_Date,
  Auto_Next_Flag,
  study_status_description,
  Place_Of_Service_Name,
  Day_Of_Week_Number,
  Day_Of_Week_Name,
  month_num,
  tat_minutes,
  Linked_Charge_Flag,
  useage,
  rp_iowa_reader_flag,
  Interventional_Flag,
  Clinical_Procedure_Short_Description,
  Clinical_Procedure_Code,
  Clinical_CPT_Code,
  Clinical_Procedure_Description,
  Drafteligiblecode,
  drafteligibleproc,
  Time_Hour,
  case_count,
  RVU,
  billled_rvu,
  best_rvu,
  TBWU,
  TBWU26,
  Allocated_RVU,
  Allocated_WU,
  Adjusted_Best_RVU,
  Roster_last_name COMMENT 'This column Represents the last name of the provider',
  Roster_name_suffix COMMENT 'This column Represents the suffixes associated with the provider name, such as Jr. or Sr.',
  Roster_first_name COMMENT 'This column Represents the first name of the provider',
  Roster_middle_name COMMENT 'This column Represents the middle name of the provider',
  Roster_staff_credential COMMENT 'This column Represents the credentials of the provider',
  Roster_associate_id COMMENT 'This column Represents the  employee ID of the provider',
  Roster_local_sub_practice,
  Percent_Full_Time COMMENT 'This column Represents the full-time equivalent percentage, providing insights into the provider work commitment.',
  Ic_flag COMMENT 'This column Represents whether the provider was classified as an independent contractor',
  Locum_flag COMMENT 'This column Represents whether the provider was a locum ',
  Res_fellow_flag COMMENT 'This column Represents if the provider was a resident or fellow',
  Phys_ext_flag COMMENT 'This column Represents whether the provider was classified as an extender',
  Roster_hire_date COMMENT 'This column Represents the hire date of the provider, important for employment history tracking.',
  Roster_employment_status_change,
  Roster_termination,
  Roster_cell_phone COMMENT 'This column Represents the mobile telephone number of the provider',
  Roster_home_phone COMMENT 'This column Represents the home telephone number of the provider',
  Roster_work_phone COMMENT 'This column Represents the work telephone number of the provider',
  Roster_ukg_id,
  Physician_SubSpecialty_Name1,
  Physician_SubSpecialty_Name2,
  Physician_SubSpecialty_Name3,
  Physician_Type,
  Patient_MRN,
  Source_Reason_For_Exam COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  Site_Accession_Number COMMENT 'This column stores the unique accession number assigned to the exam at a specific healthcare facility',
  local_practice_short_name,
  division_short_name,
  Wet_Read_DateTime,
  Exam_ID COMMENT 'This column represents EDW ID for each exam ',
  Unread_DateTime,
  Dictation_Start_DateTime,
  Dictation_End_DateTime,
  local_practice_division,
  Mosaic_flag COMMENT 'This column represents the indicator, if the exam report was generated in  moasic',
  mosaic_draft_flag COMMENT 'This column represents the indicator, if the exam was drafted on moasic',
  Source_System_Code COMMENT 'This column stores the source system name associated with the exams',
  Client_System COMMENT 'This column represents the location client system',
  assisted_flag,
  VRAname,
  Commnotetimestamp,
  USMERPID,
  USMEProc,
  USMEEligible,
  Mexproc,
  mexname,
  Team_Name,
  teamro,
  Vradautocommflag,
  Total_Adjusted_Read_Time_Sec,
  Draft_Adjusted_Read_Time_Sec,
  NonDraft_Adjusted_Read_Time_Sec,
  Rpt_Sys_Nm_Code COMMENT 'NEW 2026-10-02: resolved reporting-system code from generic_code_dim via accum_exam_fact_vw.Rpt_Sys_Nm_ID (values seen under rpceMidwest/rpceSouthwest: ORU_MSC = Mosaic Reporting, PS MW/PS SW = RP Midwest/Southwest Powerscribe, CRC Fluency, GR Fluency = Greensboro Fluency - all 5 are "truly RPCE"; ADI PS/ARA PS/NRA PS = other practices riding the same pipeline, NOT RPCE; NULL/UNK = unresolved, still real RPCE volume, just unattributed - keep in denominator, exclude from numerator). Use this column, not Mosaic_flag, to build the % RPCE reporting denominator: COUNT(Rpt_Sys_Nm_Code IS NULL OR Rpt_Sys_Nm_Code NOT IN (''ADI PS'',''ARA PS'',''NRA PS'')) as the denominator, COUNT(Rpt_Sys_Nm_Code = ''ORU_MSC'') as the numerator.',
  Draft_Sys_Nm_Code COMMENT 'NEW 2026-10-02: resolved drafting-system code from generic_code_dim via accum_exam_fact_vw.Draft_Sys_Nm_ID. Kept for parity/transparency - drafting only ever resolves to ORU_MSC or UNK for RPCE source systems (no non-Mosaic drafting system exists), so mosaic_draft_flag needs no equivalent denominator correction.')
WITH SCHEMA COMPENSATION
AS with exam_timestamps AS (
  SELECT
    e.Exam_ID,
    e.Dictation_Start_DateTime,
    e.Dictation_End_DateTime,
    e.final_datetime,
    p.Physician_NPI,
    DATE(e.Dictation_Start_DateTime) AS Exam_Date,
    LAG(e.final_datetime) OVER (
        PARTITION BY p.Physician_NPI, DATE(e.Dictation_Start_DateTime)
        ORDER BY e.Dictation_Start_DateTime, e.Exam_ID
      ) AS Prev_Final_Signed_Time
  FROM
    edw_prod.bipa_analytics.exam_fact e
      INNER JOIN edw_prod.bipa_analytics.physician_dim p
        ON e.signing_radiologist_key = p.physician_key
  WHERE
    e.Dictation_Start_DateTime IS NOT NULL
    AND e.Dictation_End_DateTime IS NOT NULL
    AND e.final_datetime IS NOT NULL
    AND p.Physician_NPI IS NOT NULL
),
adjusted_read_time AS (
  SELECT
    Exam_ID,
    Physician_NPI,
    Dictation_Start_DateTime,
    Dictation_End_DateTime,
    final_datetime,
    Prev_Final_Signed_Time,
    GREATEST(
      0,
      TIMESTAMPDIFF(
        SECOND,
        CASE
          WHEN
            Prev_Final_Signed_Time IS NOT NULL
            AND Prev_Final_Signed_Time > Dictation_Start_DateTime
          THEN
            Prev_Final_Signed_Time
          ELSE Dictation_Start_DateTime
        END,
        CASE
          WHEN final_datetime < Dictation_End_DateTime THEN final_datetime
          ELSE Dictation_End_DateTime
        END
      )
    ) AS Adjusted_Read_Time_Sec
  FROM
    exam_timestamps
)
select
  p1.physician_name_format1 as Radiologist,
  case
    when p1.employee_flag = 1 then 'RP Rad'
    when p1.Radiologist_IC_Flag = 1 then 'IC Rad'
    when p1.Radiologist_Locum_Flag = 1 then 'Locum Rad'
  end as Rad_Type,
  p1.Physician_NPI as NPI,
  p1.Physician_Partner_Status,
  p2.SubSpecialty as working_subspecialty,
  l.practice_code,
  l.sub_practice_code,
  l.Practice_Short_Name,
  l.sub_practice_short_name,
  case
    when l.location_name like 'STAT XRay%' then 'STAT XRay Locations'
    when
      l.location_name = 'Belterra Health and Rehabilitation Center West'
    then
      'STAT XRay Locations'
    when l.client_name = 'Westerville Medical Campus' then 'Westerville Medical Campus'
    else l.location_name
  end as Location_Name,
  l.client_name,
  e.Department_Name,
  e.Priority_Description,
  e.Accession_Number,
  e.Source_Procedure_Description,
  case
    when M.Interventional_Flag = 1 then 'IR'
    else M.Modality_Code
  end modality_code,
  d1.Calendar_Date,
  e.Final_DateTime,
  e.Available_To_MD_Date,
  e.Auto_Next_Flag,
  ss.study_status_description,
  ps.Place_Of_Service_Name,
  d1.Day_Of_Week_Number,
  d1.Day_Of_Week_Name,
  d1.beginning_Of_Month as month_num,
  e.tat_minutes,
  e.Linked_Charge_Flag,
  'x' as useage,
  case
    when l.practice_code = 'RPI' then 1
    else 0
  end as rp_iowa_reader_flag,
  cd.Interventional_Flag,
  cd.Clinical_Procedure_Short_Description,
  cd.Clinical_Procedure_Code,
  cd.Clinical_CPT_Code,
  cd.Clinical_Procedure_Description,
  dp.`Procedure Code` as Drafteligiblecode,
  dp.`Procedure Name` as drafteligibleproc,
  t1.Time_Hour,
  count(1) as case_count,
  sum(coalesce(rrt.Estimated_RVU, coalesce(e.Exam_Pro_RVU, 0))) as RVU,
  sum(coalesce(rrt.Billed_RVUs, 0)) as billled_rvu,
  sum(coalesce(rrt.Best_RVU, 0)) as best_rvu,
  sum(rrt.RP_TBWU) as TBWU,
  sum(E.System_Work_Units) as TBWU26,
  sum(coalesce(rrt.Allocated_RVUs, 0)) as Allocated_RVU,
  sum(coalesce(rrt.Allocated_TBWU, 0)) as Allocated_WU,
  sum(
    coalesce(rrt.Allocated_RVUs, coalesce(rrt.Best_RVU, coalesce(e.Exam_Pro_RVU, 0)))
  ) as Adjusted_Best_RVU,
  rt.Roster_last_name,
  rt.Roster_name_suffix,
  rt.Roster_first_name,
  rt.Roster_middle_name,
  rt.Roster_staff_credential,
  rt.Roster_associate_id,
  case
    when
      rt.Roster_engagement_notes like '%Baylor College of Medicine%'
    then
      'Baylor College of Medicine'
    else rt.local_practice_division
  end as Roster_local_sub_practice,
  rt.Percent_Full_Time,
  rt.Ic_flag,
  rt.Locum_flag,
  rt.Res_fellow_flag,
  rt.Phys_ext_flag,
  rt.Roster_hire_date,
  case
    when rt.Roster_employment_status_change = '1900-01-01' then null
    else rt.Roster_employment_status_change
  end as Roster_employment_status_change,
  case
    when rt.Roster_termination = '1900-01-01' then null
    else rt.roster_termination
  end as Roster_termination,
  rt.Roster_cell_phone,
  rt.Roster_home_phone,
  rt.Roster_work_phone,
  rt.Roster_ukg_id,
  p1.Physician_SubSpecialty_Name1,
  p1.Physician_SubSpecialty_Name2,
  p1.Physician_SubSpecialty_Name3,
  p1.Physician_Type,
  pd.Patient_MRN,
  e.Source_Reason_For_Exam,
  e.Site_Accession_Number,
  lp.local_practice_short_name,
  dv.division_short_name,
  e.Wet_Read_DateTime,
  e.Exam_ID,
  e.Unread_DateTime,
  e.Dictation_Start_DateTime,
  e.Dictation_End_DateTime,
  case
    when dv.division_key < 0 then lp.local_practice_short_name
    else dv.division_short_name
  end as local_practice_division,
  e.Mosaic_flag,
  e.mosaic_draft_flag,
  e.Source_System_Code,
  l.Client_System,
  iff(va.exam_id is null, 0, 1) assisted_flag,
  pool.Comm_Note_Creator as VRAname,
  pool.comm_note_datetime as Commnotetimestamp,
  usme.`Procedure Code` as USMERPID,
  usme.`Procedure Name` as USMEProc,
  usme.`USME Eligible` as USMEEligible,
  mex.`Procedure Code` as Mexproc,
  mex.`Procedure Name` as mexname,
  e.Team_Name,
  p2.Team as teamro,
  case
    when vrad.communication_type is not null then 1
    else 0
  end as Vradautocommflag,
  -- ── Adjusted Read Time columns ──────────────────────────────────────────
  sum(coalesce(art.Adjusted_Read_Time_Sec, 0)) as Total_Adjusted_Read_Time_Sec,
  sum(
    case
      when e.mosaic_draft_flag = 1 then coalesce(art.Adjusted_Read_Time_Sec, 0)
      else 0
    end
  ) as Draft_Adjusted_Read_Time_Sec,
  sum(
    case
      when e.mosaic_draft_flag = 0 then coalesce(art.Adjusted_Read_Time_Sec, 0)
      else 0
    end
  ) as NonDraft_Adjusted_Read_Time_Sec,
  -- NEW 2026-10-02: resolved codes backing the % RPCE denominator work (see column comments
  -- above). aef/rgc/dgc joined on the surrogate key already used for Exam_ID elsewhere in
  -- this query - no fan-out, see header note.
  rgc.Generic_Cd as Rpt_Sys_Nm_Code,
  dgc.Generic_Cd as Draft_Sys_Nm_Code
from
  edw_prod.bipa_analytics.exam_fact e
    left join edw_prod.bipa_analytics.location_dim l
      on e.location_key = l.location_key
    inner join edw_prod.bipa_analytics.physician_dim p1
      on e.signing_radiologist_key = p1.physician_key
    left join edw_prod.bipa_analytics.modality_dim m
      on e.modality_key = m.modality_key
    inner join edw_prod.bipa_analytics.date_dim d1
      on e.final_date_key = d1.date_key
    left join edw_prod.bipa_analytics.clinical_procedure_dim cd
      on e.clinical_procedure_key = cd.clinical_procedure_key
    left join edw_prod.bipa_analytics.study_status_dim ss
      on e.study_status_key = ss.Study_Status_ID
    left join edw_prod.bipa_analytics.place_of_service_dim ps
      on e.Place_Of_Service_Key = ps.Place_Of_Service_Key
    inner join edw_prod.bipa_analytics.time_dim t1
      on e.final_time_key = t1.Time_key
    left join edw_prod.bipa_analytics.stg_cvt_radtracker_test RT
      on p1.physician_npi = rt.NPI
      and rt.effective_start_date <= d1.calendar_date
      and d1.calendar_date <= rt.effective_end_date
    left join edw_prod.bipa_analytics.model_ref_rvusandtbwu rrt
      on e.Exam_ID = rrt.Exam_ID
    left join edw_prod.bipa_analytics.patient_dim pd
      on e.patient_key = pd.patient_key
    left join edw_prod.bipa_analytics.division_dim dv
      on e.division_key = dv.division_key
    left join edw_prod.bipa_analytics.local_practice_dim lp
      on e.local_practice_key = lp.local_practice_key
    left join edw_prod.bipa_analytics.model_ref_vra_assisted_exams_vw va
      on e.Exam_ID = va.Exam_ID
    left join edw_prod.bipa_analytics.presentation_physiciansubspecialty_vw p2
      on p2.physician_npi = rt.npi
    left join edw_dev.bipa_analytics.251212_xr_drafting_procedure_codes dp
      on cd.Clinical_Procedure_Code = dp.`Procedure Code`
    left join edw_dev.bipa_analytics.vra_colorcommnotes pool
      on e.Accession_Number = pool.acc_no
    left join edw_dev.bipa_analytics.usme_eligible_exams usme
      on cd.Clinical_Procedure_Code = usme.`Procedure Code`
    left join edw_dev.bipa_analytics.me_x_procedure_codes_for_requirements mex
      on cd.Clinical_Procedure_Code = mex.`Procedure Code`
    left join edw_dev.bipa_analytics.vra_vradcommnotes vrad
      on e.Accession_Number = vrad.acc_no
    -- ── Join adjusted read time ──────────────────────────────────────────
    left join adjusted_read_time art
      on e.Exam_ID = art.Exam_ID
    -- ── NEW 2026-10-02: resolve the true reporting/drafting system ────────
    left join edw_prod.edw_gold.accum_exam_fact_vw aef
      on aef.Accum_Exam_ID = e.Exam_ID
    left join edw_prod.edw_gold.generic_code_dim rgc
      on rgc.Generic_Cd_ID = aef.Rpt_Sys_Nm_ID
    left join edw_prod.edw_gold.generic_code_dim dgc
      on dgc.Generic_Cd_ID = aef.Draft_Sys_Nm_ID
where
  d1.Calendar_Date < from_utc_timestamp(NOW(), 'America/Chicago')
group by
  all
