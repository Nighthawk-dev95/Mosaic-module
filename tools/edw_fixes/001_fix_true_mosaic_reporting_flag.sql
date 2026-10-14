-- STATUS (2026-10-02): REWRITTEN - the Rpt_Sys_Nm_Code/Draft_Sys_Nm_Code join itself has
-- moved down to model_mosaic_dailyvolume_vw (see 007_add_rpt_sys_nm_to_model_view.sql, per
-- request 2026-10-02: "implement that now in my base tables which are
-- model_mosaic_dailyvolume_vw and presentation_mosaicdailyvolume_vw"). This file is now a
-- pure passthrough of those two columns from the model layer - no second join here, one
-- source of truth. Deploy 007 first (or together) - this file's two new columns return NULL
-- until 007 is live.
--
-- ORIGINAL BACKGROUND (still accurate - why these columns exist, what the values mean):
-- The % RPCE denominator work from 2026-09-22: the denominator ("how many exams are
-- truly RPCE") needs Rpt_Sys_Nm_Code to correctly exclude ADI PS/ARA PS/NRA PS (other
-- practices riding the same rpceMidwest/rpceSouthwest pipeline, ~887K rows) while keeping
-- UNK in (unresolved, but still genuine RPCE volume - confirmed 62-64% of it sits under
-- both rpceMidwest and rpceSouthwest, not concentrated in one). Verified live (2026-09-22):
-- numerator = COUNT(Rpt_Sys_Nm_Code = 'ORU_MSC') = 16,484,726; denominator =
-- COUNT(Rpt_Sys_Nm_Code IS NULL OR Rpt_Sys_Nm_Code NOT IN ('ADI PS','ARA PS','NRA PS')) =
-- 48,001,900; % RPCE reporting = 34.34% (cumulative since 2025-04-01) - close to the
-- existing ~33.7%, not the 95.9% you get if UNK is wrongly excluded from the denominator too.
--
-- ORIGINAL INVESTIGATION NOTES (accurate as of when the bug was ~1.5-1.8M records, before
-- EDW's own fix; Mosaic_flag redefinition described here is NOT done anywhere - EDW fixed
-- Msc_Rpt_Ind at the source, Mosaic_flag is a plain passthrough at every layer):
--
-- ROOT CAUSE: Mosaic_flag (sourced from accum_exam_fact_vw.Msc_Rpt_Ind, passed through
-- exam_fact -> model_mosaic_dailyvolume_vw -> presentation_mosaicdailyvolume_vw unchanged)
-- does not actually mean "reported via Mosaic". Msc_Rpt_Ind = 1 for ANY exam whose
-- reporting system was successfully resolved to a known code in generic_code_dim -
-- Mosaic (ORU_MSC) AND non-Mosaic legacy systems alike (RP Midwest/Southwest Powerscribe,
-- CRC/GR Fluency, ADI/ARA Powerscribe). It is only 0 when the classification failed
-- (Rpt_Sys_Nm_ID = -2 / UNK).
--
-- On 2026-06-13, the classification/matching logic behind the new Rpt_Sys_Nm_ID/
-- Draft_Sys_Nm_ID columns (added to edw_prod.edw_gold.accum_exam_fact_vw per the EDW
-- team's additive-columns proposal) got dramatically better at resolving codes that used
-- to sit in UNK (~40-47% of rpceMidwest/rpceSouthwest volume for months, collapsing to
-- ~10-12% overnight). Because Msc_Rpt_Ind flips to 1 for ANY successful resolution, not
-- specifically ORU_MSC, this took company-wide "% RPCE reporting" from ~66% to ~90% in a
-- single day (2026-06-12 -> 2026-06-13) - confirmed against edw_prod.bipa_analytics.exam_fact
-- directly. mosaic_draft_flag (Msc_Draft_Ind/Draft_Sys_Nm_ID) does NOT have this problem -
-- for these two source systems, Draft_Sys_Nm_ID only ever resolves to ORU_MSC or UNK, never
-- a non-Mosaic drafting system (drafting is Mosaic-only; reporting spans multiple legacy
-- dictation platforms). Left untouched here.
--
-- Rpt_Sys_Nm_Code / Draft_Sys_Nm_Code values: ORU_MSC = Mosaic Reporting, PS MW/PS SW = RP
-- Midwest/Southwest Powerscribe, CRC Fluency, GR Fluency = Greensboro Fluency (all 5 are
-- "truly RPCE"); ADI PS/ARA PS/NRA PS = other practices riding the same pipeline, NOT RPCE;
-- NULL/UNK = unresolved, still real RPCE volume, just unattributed - keep in denominator,
-- exclude from numerator.
--
-- PRE-DEPLOY FIX, CONFIRMED REAL (2026-09-30, re-verified 2026-10-02 with live data): the
-- previously-live view's final SELECT had `Physician_Extender Hire_Date,` with no comma -
-- Spark SQL parses "expr alias" without requiring the AS keyword, so this is valid syntax
-- that silently ALIASES the Physician_Extender column (z.Phys_ext_flag) AS Hire_Date,
-- rather than selecting two separate columns - RankedData's own correctly-computed
-- Hire_Date (z.Roster_hire_date) was never referenced in the outer SELECT at all. Confirmed
-- with live data: joining presentation_mosaicdailyvolume_vw.Hire_Date against
-- model_mosaic_dailyvolume_vw.Phys_ext_flag/Roster_hire_date for the same NPIs shows
-- Hire_Date == Phys_ext_flag (always 0 in the sample checked) while Roster_hire_date has
-- real dates (e.g. 2022-01-24) that never reach the final output. This is a genuine,
-- already-live production bug, unrelated to this file's actual purpose - fixed here by
-- removing the stray `Physician_Extender` reference entirely (not used anywhere in this
-- app, confirmed via repo-wide grep) and letting `Hire_Date` resolve correctly to
-- RankedData's own Hire_Date column. Matches the declared outer column list, which never had
-- a separate slot for Physician_Extender in the first place (112 columns, not 113).
--
-- This file has NOT been run - the Databricks connector available to this session is
-- read-only. A human with CREATE VIEW on edw_dev.bipa_analytics needs to run it (Databricks
-- SQL editor or a notebook cell). Deploy 007_add_rpt_sys_nm_to_model_view.sql first (or
-- together) - this file's Rpt_Sys_Nm_Code/Draft_Sys_Nm_Code passthrough returns NULL until
-- that one is live. No backend code changes needed after both deploy - mosaic_service.py
-- already reads Mosaic_flag, and anything built on the % RPCE work reads Rpt_Sys_Nm_Code
-- directly from presentation_mosaicdailyvolume_vw.

CREATE OR REPLACE VIEW edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw (
  Provider_NPI,
  Provider_name_format1,
  Radiologist,
  Rad_Type,
  NPI,
  Physician_Partner_Status,
  working_subspecialty,
  Practice_Code COMMENT 'This column represents the code associated with the practice  under the old practice hierarchy associated with the imaging site',
  Sub_Practice_Code COMMENT 'This column represents the code of the  sub-practice associated with the imaging site',
  Practice_Short_Name COMMENT 'This column represents the shortened name for the practice  under the old practice hierarchy associated with the imaging site',
  Sub_Practice_Short_Name COMMENT 'This column represents the shortened name for the sub-practice  under the old practice hierarchy associated with the imaging site',
  Location_Name,
  client_name COMMENT 'This column represents the name of the local client',
  Department_Name COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  Priority_Description COMMENT 'This column represents the exams Priority name ',
  Accession_Number COMMENT 'This column stores Radiology Accession Number which is unique identifier',
  Source_Procedure_Description COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  modality_code,
  Calendar_Date,
  Final_DateTime,
  auto_next_flag,
  Available_To_MD_Date,
  Study_Status_Description,
  Place_Of_Service_Name,
  Day_Of_Week_Number,
  Day_Of_Week_Name,
  Month_Num,
  TAT_Minutes,
  Linked_Charge_Flag,
  Useage,
  RP_IOWA_Reader_Flag,
  Interventional_Flag,
  Clinical_Procedure_Short_Description,
  Clinical_Procedure_Code,
  Clinical_CPT_Code,
  Clinical_Procedure_Description,
  Drafteligiblecode,
  drafteligibleproc,
  Time_Hour,
  Case_Count,
  RVU,
  best_rvu,
  TBWU,
  Allocated_RVU,
  Adjusted_Best_RVU,
  Allocated_WU,
  billled_rvu,
  Last_Name COMMENT 'This column Represents the last name of the provider',
  Suffix COMMENT 'This column Represents the suffixes associated with the provider name, such as Jr. or Sr.',
  First_Name COMMENT 'This column Represents the first name of the provider',
  physician_type,
  Middle_Name COMMENT 'This column Represents the middle name of the provider',
  Credential COMMENT 'This column Represents the credentials of the provider',
  Associate_ID COMMENT 'This column Represents the  employee ID of the provider',
  Team,
  `FTE % (other than 100%)` COMMENT 'This column Represents the full-time equivalent percentage, providing insights into the provider work commitment.',
  Ind_Contractor COMMENT 'This column Represents whether the provider was classified as an independent contractor',
  Locum COMMENT 'This column Represents whether the provider was a locum ',
  `Resident/Fellow` COMMENT 'This column Represents if the provider was a resident or fellow',
  Hire_Date COMMENT 'This column Represents whether the provider was classified as an extender',
  Employment_Status_Change_Date,
  Termination,
  Cell_Phone COMMENT 'This column Represents the mobile telephone number of the provider',
  Home_Phone COMMENT 'This column Represents the home telephone number of the provider',
  Work_Phone COMMENT 'This column Represents the work telephone number of the provider',
  UKG_ID,
  Primary_Subspecialty,
  Secondary_Subspecialty,
  Tertiary_Subspecialty,
  Week_End_Date,
  TAT_Filter,
  `30_min_flag`,
  Missing_RAD_Flag,
  physician_day,
  hour,
  Emergency_Room,
  `7 day flag`,
  Week_Number,
  Yesterday,
  Patient_MRN,
  Source_Reason_For_Exam COMMENT 'This column represents the Description of the source system attribute providing additional details about the meaning or usage of the attribute',
  Site_Accession_Number COMMENT 'This column stores the unique accession number assigned to the exam at a specific healthcare facility',
  local_practice_short_name,
  division_short_name,
  local_practice_division,
  Refresh_Date,
  Exam_ID COMMENT 'This column represents EDW ID for each exam ',
  Wet_Read_DateTime,
  Dictation_Start_DateTime,
  Dictation_End_DateTime,
  Unread_DateTime,
  Mosaic_flag COMMENT 'This column represents the indicator, if the exam report was generated in  moasic. Unchanged passthrough of accum_exam_fact_vw.Msc_Rpt_Ind - EDW fixed this at the source 2026-09, no correction needed here anymore. For the % RPCE denominator specifically, use Rpt_Sys_Nm_Code instead (see that column''s comment) rather than this flag.',
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
  TBWU26,
  Total_Adjusted_Read_Time_Sec,
  Draft_Adjusted_Read_Time_Sec,
  NonDraft_Adjusted_Read_Time_Sec,
  Rpt_Sys_Nm_Code COMMENT 'Resolved reporting-system code from generic_code_dim via accum_exam_fact_vw.Rpt_Sys_Nm_ID, passed through unchanged from model_mosaic_dailyvolume_vw (see 007_add_rpt_sys_nm_to_model_view.sql for the actual join). Values seen under rpceMidwest/rpceSouthwest: ORU_MSC = Mosaic Reporting, PS MW/PS SW = RP Midwest/Southwest Powerscribe, CRC Fluency, GR Fluency = Greensboro Fluency - all 5 are "truly RPCE"; ADI PS/ARA PS/NRA PS = other practices riding the same pipeline, NOT RPCE; NULL/UNK = unresolved, still real RPCE volume, just unattributed - keep in denominator, exclude from numerator. Use this column, not Mosaic_flag, to build the % RPCE reporting denominator: COUNT(Rpt_Sys_Nm_Code IS NULL OR Rpt_Sys_Nm_Code NOT IN (''ADI PS'',''ARA PS'',''NRA PS'')) as the denominator, COUNT(Rpt_Sys_Nm_Code = ''ORU_MSC'') as the numerator.',
  Draft_Sys_Nm_Code COMMENT 'Resolved drafting-system code from generic_code_dim via accum_exam_fact_vw.Draft_Sys_Nm_ID, passed through unchanged from model_mosaic_dailyvolume_vw. Kept for parity/transparency - drafting only ever resolves to ORU_MSC or UNK for RPCE source systems (no non-Mosaic drafting system exists), so mosaic_draft_flag needs no equivalent denominator correction.')
WITH SCHEMA COMPENSATION
AS with TempX AS (
  select
    physician_npi,
    physician_name_format1
  from
    edw_prod.bipa_analytics.physician_dim AS PD
  where
    physician_npi is not null
    and Current_Flag = 1
  group by
    physician_npi,
    physician_name_format1
),
RankedData AS (
  select
    --Top 10000
    x.physician_npi Provider_NPI,
    x.physician_name_format1 Provider_name_format1,
    z.Radiologist,
    z.Rad_Type,
    z.NPI,
    z.Physician_Partner_Status,
    z.working_subspecialty,
    z.Practice_Code,
    z.Sub_Practice_Code,
    z.Practice_Short_Name,
    z.Sub_Practice_Short_Name,
    z.Location_Name,
    z.client_name,
    z.Department_Name,
    z.Priority_Description,
    z.Accession_Number,
    z.Source_Procedure_Description,
    z.modality_code,
    z.Calendar_Date,
    z.Final_DateTime,
    z.Available_To_MD_Date,
    z.Study_Status_Description,
    z.Place_Of_Service_Name,
    z.Day_Of_Week_Number,
    z.Day_Of_Week_Name,
    z.Month_Num,
    z.TAT_Minutes,
    z.Linked_Charge_Flag,
    z.Useage,
    z.RP_IOWA_Reader_Flag,
    z.Interventional_Flag,
    z.Clinical_Procedure_Short_Description,
    z.Clinical_Procedure_Code,
    z.Clinical_CPT_Code,
    z.Clinical_Procedure_Description,
    z.Drafteligiblecode,
    z.drafteligibleproc,
    z.Time_Hour,
    z.Case_Count,
    z.Auto_Next_Flag,
    z.RVU,
    z.best_rvu,
    z.TBWU,
    z.Allocated_RVU,
    z.Adjusted_Best_RVU,
    z.Allocated_WU,
    z.billled_rvu,
    z.Roster_last_name as Last_Name,
    z.Roster_name_suffix as Suffix,
    z.Roster_first_name as First_Name,
    z.Roster_middle_name as Middle_Name,
    z.Roster_staff_credential as `Credential`,
    z.Roster_associate_id as Associate_ID,
    z.Roster_local_sub_practice as Team,
    z.Percent_Full_Time as `FTE % (other than 100%)`,
    z.Ic_flag as Ind_Contractor,
    z.Locum_flag as Locum,
    z.Res_fellow_flag as `Resident/Fellow`,
    z.Phys_ext_flag as Physician_Extender,
    z.Physician_Type,
    z.Roster_hire_date as Hire_Date,
    z.Roster_employment_status_change as Employment_Status_Change_Date,
    z.Roster_termination as Termination,
    z.Roster_cell_phone as Cell_Phone,
    z.Roster_home_phone as Home_Phone,
    z.Roster_work_phone as Work_Phone,
    z.Roster_ukg_id as UKG_ID,
    z.Physician_SubSpecialty_Name1 as Primary_Subspecialty,
    z.Physician_SubSpecialty_Name2 as Secondary_Subspecialty,
    z.Physician_SubSpecialty_Name3 as Tertiary_Subspecialty,
    (
      date_trunc('WEEK', from_utc_timestamp(current_timestamp(), 'CST')) + INTERVAL '5 day'
    ) as Week_End_Date,
    ----Review TAT funcctionality later----
    case
      when
        z.Priority_Description = 'Stat'
        and z.tat_minutes > 1440
      then
        1
      when
        z.Priority_Description = 'Routine'
        and z.tat_minutes > 4320
      then
        1
      when z.Priority_Description = 'Unknown' then 1
      when z.tat_minutes <= 0 then 1
      when
        z.Priority_Description = 'Stat'
        and z.modality_code = 'IR'
      then
        1
      when
        z.Priority_Description = 'Stat'
        and z.modality_code = 'Fluoro'
      then
        1
      when
        z.Priority_Description = 'Stat'
        and z.modality_code = 'PET'
      then
        1
      when
        z.Priority_Description = 'Stat'
        and z.modality_code = 'BD'
      then
        1
      when
        z.Priority_Description = 'Stat'
        and z.modality_code = 'NM'
      then
        1
      else 0
    end as TAT_Filter,
    case
      when z.tat_minutes < 0 then null
      when z.tat_minutes > 30 then 1
      else 0
    end as `30_min_flag`,
    case
      when Radiologist is null then 1
      when Radiologist = 'None' then 1
      else 0
    end as Missing_RAD_Flag,
    z.Radiologist || cast(Calendar_Date as string) as physician_day,
    case
      when z.Time_Hour = 0 then '12am-1am'
      when z.Time_Hour = 1 then '1am-2am'
      when z.Time_Hour = 2 then '2am-3am'
      when z.Time_Hour = 3 then '3am-4am'
      when z.Time_Hour = 4 then '4am-5am'
      when z.Time_Hour = 5 then '5am-6am'
      when z.Time_Hour = 6 then '6am-7am'
      when z.Time_Hour = 7 then '7am-8am'
      when z.Time_Hour = 8 then '8am-9am'
      when z.Time_Hour = 9 then '9am-10am'
      when z.Time_Hour = 10 then '10am-11am'
      when z.Time_Hour = 11 then '11am-12pm'
      when z.Time_Hour = 12 then '12pm-1pm'
      when z.Time_Hour = 13 then '1pm-2pm'
      when z.Time_Hour = 14 then '2pm-3pm'
      when z.Time_Hour = 15 then '3pm-4pm'
      when z.Time_Hour = 16 then '4pm-5pm'
      when z.Time_Hour = 17 then '5pm-6pm'
      when z.Time_Hour = 18 then '6pm-7pm'
      when z.Time_Hour = 19 then '7pm-8pm'
      when z.Time_Hour = 20 then '8pm-9pm'
      when z.Time_Hour = 21 then '9pm-10pm'
      when z.Time_Hour = 22 then '10pm-11pm'
      when z.Time_Hour = 23 then '11pm-12am'
    end as `hour`,
    case
      when z.Department_Name = 'MMC - EMERGENCY' then 'ER'
      when z.Department_Name = 'Piedmont Northside - Emergency' then 'ER'
      when z.Department_Name = 'BH MAD - Emergency Room' then 'ER'
      when z.Department_Name = 'Citizens - Emergency Room' then 'ER'
      when z.Department_Name = 'COMMUNITY FIRST -  EMERGENCY DEPT' then 'ER'
      when z.Department_Name = 'Cuero - EMERGENCY ROOM' then 'ER'
      when z.Department_Name = 'Dallas Med Ctr - Emergency Room' then 'ER'
      when z.Department_Name = 'Dallas Regional - Emergency Room' then 'ER'
      when z.Department_Name = 'Emergency' then 'ER'
      when z.Department_Name = 'Emergency Room' then 'ER'
      when z.Department_Name = 'Ennis Reg Med Ctr - Emergency Room' then 'ER'
      when z.Department_Name = 'JCH Emergency Room' then 'ER'
      when z.Department_Name = 'Limestone - Emergency Room' then 'ER'
      when z.Department_Name = 'LP - Emergency Lake Pointe' then 'ER'
      when z.Department_Name = 'LP - Forney ER' then 'ER'
      when z.Department_Name = 'LP - Wylie ER' then 'ER'
      when z.Department_Name = 'Marquette -Emergency Department' then 'ER'
      when z.Department_Name = 'METROSOUTH - ER OUTPATIENT' then 'ER'
      when z.Department_Name = 'MLC - EMERGENCY DEPARTMENT' then 'ER'
      when z.Department_Name = 'MMC - EMERGENCY - INPATIENT HOLDING' then 'ER'
      when z.Department_Name = 'Monroe KY - Emergency Room' then 'ER'
      when z.Department_Name = 'Norwegian Amer. Hosp.  - Emergency Room' then 'ER'
      when z.Department_Name = 'Norwegian Amer. Hosp.  - Er Fast Track' then 'ER'
      when z.Department_Name = 'Palestine Reg Med Ctr - Emergency Room' then 'ER'
      when z.Department_Name = 'Palo Pinto - Emergency Room' then 'ER'
      when z.Department_Name = 'Thorek Mem Hosp - Emergency Room' then 'ER'
      when z.Department_Name = 'Wagoner - Emergency Department' then 'ER'
      when z.Department_Name = 'Yoakum - EMERGENCY ROOM' then 'ER'
      else 'NON ER'
    end as `Emergency_Room`,
    ----End of Review Section----
    case
      when useage = 'Z' then 1
      when
        Calendar_Date >= (from_utc_timestamp(current_timestamp(), 'CST') + INTERVAL '-7 day')
      then
        1
      else 0
    end as `7 day flag`,
    date_part('week', Calendar_Date) as Week_Number,
    from_utc_timestamp(current_timestamp(), 'CST') + INTERVAL '-1 day' as Yesterday,
    z.Patient_MRN,
    z.Source_Reason_For_Exam,
    z.Site_Accession_Number,
    z.local_practice_short_name,
    z.division_short_name,
    z.local_practice_division,
    from_utc_timestamp(current_timestamp(), 'CST') Refresh_Date,
    z.Exam_ID,
    z.Wet_Read_DateTime,
    z.Dictation_Start_DateTime,
    z.Dictation_End_DateTime,
    z.Unread_DateTime,
    z.Mosaic_flag,
    z.mosaic_draft_flag,
    z.Source_System_Code,
    z.Client_System,
    z.assisted_flag,
    z.VRAname,
    z.Commnotetimestamp,
    z.USMERPID,
    z.USMEProc,
    z.USMEEligible,
    z.Mexproc,
    z.mexname,
    z.Team_Name,
    z.teamro,
    z.Vradautocommflag,
    z.TBWU26,
    z.Total_Adjusted_Read_Time_Sec,
    z.Draft_Adjusted_Read_Time_Sec,
    z.NonDraft_Adjusted_Read_Time_Sec,
    -- NEW 2026-10-02: plain passthrough from model_mosaic_dailyvolume_vw - the join itself
    -- lives there now (007_add_rpt_sys_nm_to_model_view.sql), not here.
    z.Rpt_Sys_Nm_Code,
    z.Draft_Sys_Nm_Code,
    -- DEDUPLICATION: ROW_NUMBER to identify duplicates
    ROW_NUMBER() OVER (
        PARTITION BY z.Accession_Number, z.Calendar_Date
        ORDER BY
          z.Final_DateTime DESC NULLS LAST,
          z.Radiologist ASC NULLS LAST,
          z.modality_code ASC NULLS LAST
      ) as row_num
  from
    TempX x
      inner join edw_dev.bipa_analytics.model_mosaic_dailyvolume_vw z
        on x.physician_npi = z.npi
        and z.Calendar_date >= from_utc_timestamp('2025-04-01', 'CST')
)
select
  Provider_NPI,
  Provider_name_format1,
  Radiologist,
  Rad_Type,
  NPI,
  Physician_Partner_Status,
  working_subspecialty,
  Practice_Code,
  Sub_Practice_Code,
  Practice_Short_Name,
  Sub_Practice_Short_Name,
  Location_Name,
  client_name,
  Department_Name,
  Priority_Description,
  Accession_Number,
  Source_Procedure_Description,
  modality_code,
  Calendar_Date,
  Final_DateTime,
  auto_next_flag,
  Available_To_MD_Date,
  Study_Status_Description,
  Place_Of_Service_Name,
  Day_Of_Week_Number,
  Day_Of_Week_Name,
  Month_Num,
  TAT_Minutes,
  Linked_Charge_Flag,
  Useage,
  RP_IOWA_Reader_Flag,
  Interventional_Flag,
  Clinical_Procedure_Short_Description,
  Clinical_Procedure_Code,
  Clinical_CPT_Code,
  Clinical_Procedure_Description,
  Drafteligiblecode,
  drafteligibleproc,
  Time_Hour,
  Case_Count,
  RVU,
  best_rvu,
  TBWU,
  Allocated_RVU,
  Adjusted_Best_RVU,
  Allocated_WU,
  billled_rvu,
  Last_Name,
  Suffix,
  First_Name,
  physician_type,
  Middle_Name,
  `Credential`,
  Associate_ID,
  Team,
  `FTE % (other than 100%)`,
  Ind_Contractor,
  Locum,
  `Resident/Fellow`,
  Hire_Date,
  Employment_Status_Change_Date,
  Termination,
  Cell_Phone,
  Home_Phone,
  Work_Phone,
  UKG_ID,
  Primary_Subspecialty,
  Secondary_Subspecialty,
  Tertiary_Subspecialty,
  Week_End_Date,
  TAT_Filter,
  `30_min_flag`,
  Missing_RAD_Flag,
  physician_day,
  `hour`,
  `Emergency_Room`,
  `7 day flag`,
  Week_Number,
  Yesterday,
  Patient_MRN,
  Source_Reason_For_Exam,
  Site_Accession_Number,
  local_practice_short_name,
  division_short_name,
  local_practice_division,
  Refresh_Date,
  Exam_ID,
  Wet_Read_DateTime,
  Dictation_Start_DateTime,
  Dictation_End_DateTime,
  Unread_DateTime,
  Mosaic_flag,
  mosaic_draft_flag,
  Source_System_Code,
  Client_System,
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
  TBWU26,
  Total_Adjusted_Read_Time_Sec,
  Draft_Adjusted_Read_Time_Sec,
  NonDraft_Adjusted_Read_Time_Sec,
  Rpt_Sys_Nm_Code,
  Draft_Sys_Nm_Code
from
  RankedData
where
  row_num = 1
