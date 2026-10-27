"""Generates 044a (PBI-capacity shift view) and 044b (capacity PBI metric view, DRAFT + FLOW).

Local / Area lists are exact copies of the PBI Mosaic Impact Report '0. Cur'[Local] and '0. Cur'[Area]
calculated columns (tools/pbi_semantic_extract/mosaic_impact_tmdl/tables/0. Cur.tmdl). DAX `IN` is
case-insensitive, so the CASE matches on LOWER(Team). First match wins, as in SWITCH(TRUE(), ...).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _to_flow_style import convert  # noqa: E402

LOCAL = [
    ("Special Operations", "ESR, LFI, Jefferson, GLI, RAI, RP Cascade, JR, DRSRP, RP East Florida, RP North Florida, RP Palm Beach, PRA, ESRMH Garnet, ESRMH Hackensack, ESRMH Legacy, ESR Long Island, ESR Metro Hudson, SEAL Team, SEAL Legacy, Spec Ops Reserve, Lakefront Imaging, ESRMH NY Metro, ESRMH Westchester, vRad"),
    ("Apex", "ADI, ADR, CRC Central, CRC NW, CRC SW, Midstate, NEOH, Rad Alliance, RP Kentucky, RP Bluegrass, RAC, RACSW, RPKY, RPBG, RA, ADR Legacy, CRC, Rad Alliance Legacy, Rad Alliance NorthCrest, RP Bluegrass Legacy, ADR South Tennessee, RAA"),
    ("Genesis", "Coastal, Greensboro, MBB, Northside, Greensboro Canopy, RAF, RP Florida, RP Sandhills, RP South Carolina, SOAR, BOCA, GR, NRA, RASF, MBB Legacy, MBB Phoebe Putney, Northside Radiology, RAF East Coast, RAF Panhandle, RAF Sarasota, RAF Tampa, RAF Tele, RASF Miami, RASF Naples, RP Florida Legacy, Bethesda, RP Florida West"),
    ("Maverick", "Advanced Radiology, Alaska, CIR, Desert, GIMA, RP SoCal, IAM, IAMSE, MIA, Mountain, NIR, MXC, Red Rock, RIMA, RP Sol, RP Sun City, RP Chicago, RP Forest City, Saline Valley, RP Valley Radiologists, SVDI, Western Colorado, WIR, RP IOWA, GSIA, SVL, MR, DR, NWIR, ARSC, DR Legacy, DR DRS, IAMSE Hurley, IAM Marquette, IAM Midlands, Mountain Legacy, Mountain Yampa, RP NWIR, RP SMIL, RP SoCal Lakewood, RP SoCal Legacy, RP SoCal Palmdale, RP Valley, SVDI Legacy, SVDI San Ramon, SMI, RIMA California, RP Crossroads, RP Phoenix, RP NWIR Legacy"),
    ("Trailblazer", "Access Alexandria, ARA, BR Academic, BR Community, CIRPA, Community, RP Eagle, EBI, GIA, Lake Charles, RP Borderlands, RP Brazosport, RP Corpus Christi, RP Dallas, RP El Paso, RP Gulf Coast, RP Houston, RP Laredo, RP Victoria, BR, Slidell, ACC, RPNM, EAG, RPEP, RPGC, RPH, Other, EXTHMC, RP Singleton Academic, RP Singleton Community, RP Singleton, Rose, RP North Houston, Synergy, Access Lake Charles, Community Laredo, Community Legacy, Community Victoria, Elite, RP Borderlands Legacy, RP Borderlands Lovelace, RP Helios, Rose RIS"),
    ("Matrix", "Matrix"),
]

AREA = [
    ("East", "Bethesda, Boca, Coastal, Greensboro, MBB, MBB Legacy, MBB Phoebe Putney, Northside Radiology, RAF, RAF East Coast, RAF Panhandle, RAF Sarasota, RAF Tampa, RAF Tele, RASF, RASF Miami, RASF Naples, RP Florida, RP Florida Legacy, RP Palmetto, RP South Carolina, SOAR, RP West Georgia, RP Georgia, RP Atlantic Coast, RP Sandhills, RP Florida West"),
    ("Great Lakes", "ARSC, GIMA, IAM, IAMSE Hurley, MXC, CIR, RP Chicago, RP Crossroads, RP Iowa, RP NWIR, Saline Valley, SMI, IAM Marquette, RP Forest City, GIA, RP NWIR Legacy"),
    ("Midwest", "ADI, ADR, ADR Legacy, ADR South Tennessee, CRC, CRC Central, CRC NW, CRC SW, Midstate, NEOH, Rad Alliance, Rad Alliance Legacy, Rad Alliance NorthCrest, RAC, RACSW, RP Bluegrass, RP Bluegrass Legacy, RP Bluegrass Baptist, RP Kentucky, RAA"),
    ("Envision", "DRSRP, RP East Florida, RP North Florida, RP Palm Beach, PRA, RP RAH, Spec Ops Reserve"),
    ("Integration & SEAL", "GLI, SEAL Team, SEAL Legacy, RP Cascade, Lakefront Imaging, LFI"),
    ("Matrix", "Matrix"),
    ("Northeast", "ESR Long Island, ESR Metro Hudson, ESRMH Garnet, ESRMH Hackensack, ESRMH Legacy, Jefferson, RAI, ESRMH NY Metro, ESRMH Westchester"),
    ("Southwest", "Access Alexandria, Access Lake Charles, ARA, Community, Community Laredo, Community Legacy, Community Victoria, CIRPA, Elite, RP Borderlands, RP Borderlands Legacy, RP Borderlands Lovelace, RP Brazosport, RP Corpus Christi, RP Dallas, RP Eagle, RP El Paso, RP Gulf Coast, RP Helios, RP Houston, RP North Houston, RP Singleton, RP Singleton Academic, RP Singleton Community, Rose, Rose RIS, Synergy, Access Louisiana, Access Slidell"),
    ("West", "Alaska, DR, DR Legacy, DR DRS, MIA, Mountain, Mountain Legacy, Mountain Yampa, RP Phoenix, RP SMIL, RP Sol, RP SoCal, RP SoCal Lakewood, RP SoCal Legacy, RP SoCal Palmdale, RP Sun City, RP Valley, Red Rock, RIMA, SVDI, SVDI Legacy, SVDI San Ramon, Western Colorado, Western Colorado Yampa, Western Colorado Legacy, RIMA Maui, RIMA California, RP Tucson"),
    ("VRad", "vRad"),
]

# Report-level filter on 'Shift Length Lookup'[Shift Length Display] (ROUND(no_hours, 0)).
EXCLUDED_SHIFT_LENGTHS = (-20, -16, -13, -11, -10, -9, -7, -5, -2, 0, 1, 2, 3, 17, 18, 19, 20, 21, 22, 23, 24)


def case_expr(mapping, col, indent):
    lines = ["CASE"]
    for label, teams in mapping:
        vals = ", ".join("'" + t.strip().lower().replace("'", "''") + "'" for t in teams.split(","))
        lines.append(f"{indent}  WHEN LOWER({col}) IN ({vals}) THEN '{label}'")
    lines.append(f"{indent}  ELSE 'Blank' END")
    return f"\n{indent}".join(lines)


VIEW_044A = f"""-- 044a: Mosaic capacity at PBI shift grain. DRAFT STATUS: edw_test only - do not promote to edw_prod
-- without approval. Generated by _gen_044_capacity_pbi.py - edit that, not this.
--
-- WHY: the Executive Dashboard's Capacity page must match the PBI "Mosaic Impact Report" exactly. The
-- earlier capacity metric view (028/029) re-derives an hour-weighted RPWU/hr model; PBI instead averages
-- per-shift TBWU 26 values (AVERAGEX) over its own source view with its own filters. This view exposes
-- PBI's source 1:1 plus every column PBI derives in Power Query / calculated columns, so the metric view
-- (044b) and dashboard SQL can reproduce PBI's measures by construction.
-- SOURCE: edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw (= PBI table '0. Cur').
-- Live (no MV): a full aggregate over the source takes ~4s.
-- PBI parity of derived columns:
--   team_rolled_up   = '0. Cur'[Team Rolled up] (team_rollups[Team Roll Up (KS)] on Team, case-insensitive)
--   local_region     = '0. Cur'[Local]; area = '0. Cur'[Area] (exact SWITCH lists, first match wins)
--   shift_to_include = '0. Cur'[Shift to Include] ("Shifts with Baselines" unless both RVU and RPWU baselines blank)
--   shift_length_rounded / passes_shift_length = 'Shift Length Lookup'[Shift Length Display] + report-level filter
--   in_topn_all      = '2.Top N shift Table' Rank_TopN "All Shifts": ShiftRecencyRank <= FLOOR(MAX(ShiftNo
--                      where VRAShift_TAG = 1) / 5) * 5. PBI freezes this at refresh; here it is live.
--   in_pbi_default   = passes_shift_length AND in_topn_all AND shift_to_include = 'Shifts with Baselines'
--                      (the Practice Summary page defaults).
--
-- ADDITIVE ONLY: plain CREATE VIEW (no OR REPLACE).

CREATE VIEW edw_test.enterprise_analytics.mosaic_capacity_pbi_shift_vw
COMMENT 'MOSAIC CAPACITY (PBI Impact Report parity, draft, edw_test only). One row per radiologist shift from the PBI Mosaic Impact Report source view, plus the PBI-derived Team Rolled up / Local / Area / filter flags. Use mosaic_capacity_pbi_metric_view for governed measures.'
AS
WITH src AS (
  SELECT * FROM edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw
),
mx AS (
  SELECT FLOOR(MAX(CASE WHEN VRAShift_TAG = 1 THEN ShiftNo END) / 5) * 5 AS topn_all_max
  FROM src
),
tr AS (
  SELECT LOWER(Team) AS team_key, MAX(`Team Roll Up (KS)`) AS team_rolled_up
  FROM edw_dev.bipa_analytics.team_rollups
  GROUP BY LOWER(Team)
)
SELECT
  s.*,
  s.unit_usage AS preferred_unit,
  s.Model_type AS model,
  tr.team_rolled_up,
  {case_expr(LOCAL, 's.Team', '  ')} AS local_region,
  {case_expr(AREA, 's.Team', '  ')} AS area,
  CAST(DATE_TRUNC('MONTH', s.ShiftDate) AS DATE) AS shift_month,
  CASE WHEN s.shift_baseline_RVU IS NULL AND s.shift_baseline_RPWU IS NULL THEN 'Shifts without Baselines'
       ELSE 'Shifts with Baselines' END AS shift_to_include,
  CAST(ROUND(s.no_hours, 0) AS INT) AS shift_length_rounded,
  COALESCE(CAST(ROUND(s.no_hours, 0) AS INT) NOT IN ({', '.join(str(x) for x in EXCLUDED_SHIFT_LENGTHS)}), FALSE) AS passes_shift_length,
  COALESCE(s.ShiftRecencyRank <= mx.topn_all_max, FALSE) AS in_topn_all,
  mx.topn_all_max,
  COALESCE(s.Has_TBWU26_Baseline, FALSE) AS has_tbwu26,
  COALESCE(CAST(ROUND(s.no_hours, 0) AS INT) NOT IN ({', '.join(str(x) for x in EXCLUDED_SHIFT_LENGTHS)}), FALSE)
    AND COALESCE(s.ShiftRecencyRank <= mx.topn_all_max, FALSE)
    AND NOT (s.shift_baseline_RVU IS NULL AND s.shift_baseline_RPWU IS NULL) AS in_pbi_default
FROM src s
CROSS JOIN mx
LEFT JOIN tr ON tr.team_key = LOWER(s.Team)
"""

YAML_044B = """version: 1.1
source: edw_test.enterprise_analytics.mosaic_capacity_pbi_shift_vw
filter: in_pbi_default
comment: Mosaic capacity per shift in TBWU 26 (PBI Mosaic Impact Report, Practice Summary defaults). See CREATE VIEW comment.
dimensions:
- name: Shift Date
  expr: source.ShiftDate
  comment: Shift date. Bind the dashboard Period filter here.
- name: Month
  expr: source.shift_month
  comment: Calendar month of the shift (PBI Month slicer).
- name: Local Region
  expr: source.local_region
  comment: 6 fixed regions (+ Matrix / Blank), exact copy of PBI '0. Cur'[Local] keyed on Team.
- name: Area
  expr: source.area
  comment: Exact copy of PBI '0. Cur'[Area] keyed on Team.
- name: Team
  expr: source.Team
  comment: Radiologist's roster team (Provider Practice sub-team).
- name: Team Rolled Up
  expr: source.team_rolled_up
  comment: Provider Practice (PBI 'Team Rolled up', via team_rollups).
- name: Local Practice
  expr: source.localpractice
  comment: Practice used for the PBI Practice Summary table rows (PBI '0. Cur'[localpractice]).
- name: Radiologist
  expr: source.Rad_name
  comment: Radiologist name.
- name: NPI
  expr: CAST(source.NPI AS STRING)
  comment: Radiologist NPI.
- name: Baseline Type
  expr: source.Baseline_type
  comment: How the shift baseline was set (Exact, Proxy, Manual Review, ...).
- name: Model
  expr: source.model
  comment: PBI Model (source Model_type).
- name: Data Quality
  expr: source.Shift_Data_Quality_Status
  comment: Shift data quality status (PBI Time Series page filters to Good).
- name: Shift Length (hours)
  expr: source.shift_length_rounded
  comment: Shift length rounded to whole hours (PBI Shift Length Display).
measures:
- name: Selected Shift Count
  expr: COUNT(1)
  comment: Shifts in scope. = PBI [Selected Shift Ct].
- name: Average Baseline
  expr: AVG(source.shift_baseline_RPWU)
  comment: Average TBWU 26 baseline per shift. = PBI [Average Baseline] with unit TBWU 26/Shift.
- name: New Capacity
  expr: AVG(source.on_shift_capacity_RPWU)
  comment: Average TBWU 26 capacity per shift with Mosaic. = PBI [New Capacity].
- name: Addl Capacity Per Shift
  expr: CASE WHEN AVG(source.shift_baseline_RPWU) IS NULL THEN NULL ELSE AVG(source.on_shift_capacity_RPWU) - AVG(source.shift_baseline_RPWU) END
  comment: New Capacity - Average Baseline (TBWU 26 per shift). = PBI [Add'l Capacity/Shift]. Practices with >= 0 (rounded) are 'Successful'.
- name: Pct Addl Capacity
  expr: (AVG(source.on_shift_capacity_RPWU) - AVG(source.shift_baseline_RPWU)) / NULLIF(AVG(source.shift_baseline_RPWU), 0)
  comment: Additional capacity as % of baseline. = PBI [% Add'l Capacity].
- name: Pct Mosaic
  expr: SUM(source.on_shift_mosaic_cases) / NULLIF(SUM(source.on_shift_cases), 0)
  comment: Share of on-shift cases read in Mosaic. = PBI [% Mosaic].
- name: Pct Mosaic Drafting
  expr: SUM(source.on_shift_mosaic_drafting_cases) / NULLIF(SUM(source.on_shift_cases), 0)
  comment: Share of on-shift cases drafted in Mosaic. = PBI [% Mosaic Drafting].
- name: New Efficiency
  expr: AVG(CASE WHEN source.on_shift_efficiency_RPWU <= 1 THEN source.on_shift_efficiency_RPWU END)
  comment: Average per-shift efficiency (shifts with efficiency > 1 ignored, as PBI). = PBI [New Efficiency].
- name: New Utilization
  expr: AVG(source.on_shift_utilization_RPWU_pct / 100)
  comment: Average per-shift utilization, 0-1. = PBI [New Utilization] with unit TBWU 26/Shift.
- name: Has TBWU26 Baseline
  expr: MAX(CASE WHEN source.has_tbwu26 THEN 1 ELSE 0 END)
  comment: 1 if any shift in the group has a TBWU 26 baseline. PBI hides groups where this is 0 (e.g. Matrix) - filter on it to match PBI tables and totals.
- name: Radiologist Count
  expr: COUNT(DISTINCT source.NPI)
  comment: Distinct radiologists (NPI) with a shift in scope.
- name: Data Through Date
  expr: MAX(source.ShiftDate)
  comment: Latest shift date in the source.
"""

HEADER_044B = """-- 044b: Mosaic capacity PBI-parity metric view. DRAFT STATUS: edw_test only - do not promote to
-- edw_prod without approval. Generated by _gen_044_capacity_pbi.py - edit that, not this.
--
-- WHY: governed TBWU 26/Shift capacity measures for the Executive Dashboard Capacity page and Genie,
-- matching the PBI Mosaic Impact Report "Practice Summary" page at its defaults.
-- SOURCE: edw_test.enterprise_analytics.mosaic_capacity_pbi_shift_vw (044a), filtered to in_pbi_default
-- (Shifts with Baselines + report shift-length filter + Rank_TopN "All Shifts").
-- PBI parity: measures are PBI's AVERAGEX-per-shift definitions with Unit = TBWU 26/Shift. To match PBI
-- tables/totals also filter groups to `Has TBWU26 Baseline` = 1 (PBI visual filter Has_Baseline_For_Selected_Unit).
--
-- ADDITIVE ONLY: plain CREATE VIEW (no OR REPLACE).

CREATE VIEW edw_test.enterprise_analytics.mosaic_capacity_pbi_metric_view
COMMENT 'MOSAIC CAPACITY SEMANTIC LAYER - PBI Impact Report parity (draft, edw_test only). Per-shift TBWU 26 capacity vs baseline, utilization, efficiency and Mosaic share, averaged per shift exactly as the PBI Practice Summary page. Filter groups to Has TBWU26 Baseline = 1 to match PBI.'
WITH METRICS
LANGUAGE YAML
AS
$$
"""


def main():
    with open(os.path.join(HERE, "044a_mosaic_capacity_pbi_shift_vw.sql"), "w", newline="\n") as f:
        f.write(VIEW_044A)
    draft = os.path.join(HERE, "044b_mosaic_capacity_pbi_metric_view_DRAFT.sql")
    with open(draft, "w", newline="\n") as f:
        f.write(HEADER_044B + YAML_044B + "$$\n")
    tmp_in, tmp_out = os.path.join(HERE, "_044b_in.yaml"), os.path.join(HERE, "_044b_out.yaml")
    with open(tmp_in, "w", newline="\n") as f:
        f.write(YAML_044B)
    convert(tmp_in, tmp_out)
    with open(tmp_out) as f:
        flow = f.read()
    with open(os.path.join(HERE, "044b_mosaic_capacity_pbi_metric_view_FLOW.sql"), "w", newline="\n") as f:
        f.write(HEADER_044B + flow + "$$\n")
    os.remove(tmp_in)
    os.remove(tmp_out)


if __name__ == "__main__":
    main()
