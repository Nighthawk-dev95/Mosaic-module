-- Capacity (PBI Mosaic Impact Report "Practice Summary" logic, TBWU 26/Shift) -- one row per shift.
-- Source: 044a mosaic_capacity_pbi_shift_vw. in_pbi_default = PBI page defaults
--   (Shift to Include = Shifts with Baselines, report Shift Length Display exclusions, Top N = All Shifts).
-- QUALIFY = PBI visual filter Has_Baseline_For_Selected_Unit: a practice is shown (and counted in totals)
--   only if it has at least one TBWU 26 baseline in the month (e.g. Matrix drops out, as in PBI).
-- Widgets aggregate per shift exactly as the PBI measures (AVERAGEX over shifts); see 044b for the governed versions.
SELECT
  ShiftDate                         AS `Shift Date`,
  shift_month                       AS `Shift Month`,
  local_region                      AS `Local Region`,
  team_rolled_up                    AS `Team Rolled Up`,
  localpractice                     AS `Local Practice`,
  Team,
  Rad_name                          AS Radiologist,
  CAST(NPI AS STRING)               AS NPI,
  Baseline_type                     AS `Baseline Type`,
  shift_baseline_RPWU,
  on_shift_capacity_RPWU,
  on_shift_efficiency_RPWU,
  on_shift_utilization_RPWU_pct,
  on_shift_cases,
  on_shift_mosaic_cases,
  on_shift_mosaic_drafting_cases
FROM edw_test.enterprise_analytics.mosaic_capacity_pbi_shift_vw
WHERE in_pbi_default
QUALIFY MAX(CASE WHEN has_tbwu26 THEN 1 ELSE 0 END) OVER (PARTITION BY localpractice, shift_month) = 1
