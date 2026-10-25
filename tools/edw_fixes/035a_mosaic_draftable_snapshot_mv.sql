-- 035a: daily snapshot of the legacy PBI "Draftable" source, for the exec dashboard's
-- "Draftable, Undrafted" page.
--
-- Why a snapshot: edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw recomputes from
-- exam_fact on every read (>2 min per query). PBI imports it once a day; this MV does the same.
-- Logic is NOT changed: rows are the legacy view's rows 1:1, plus two lookup columns.
--   * team_rolled_up : tbl_team_rollups on Team (144 rows, unique on Team -> no fan-out;
--                      100% of Sept-2026 Teams map).
--   * local_region   : exact copy of PBI Draftable[Localdraf] SWITCH (first match wins, ELSE Matrix).
--                      Intentionally NOT the volume view's Local Region CASE -- they differ for a
--                      few Teams (RP Florida West, RAA, Lakefront Imaging, unmapped -> Matrix);
--                      PBI parity for this page needs Localdraf.
--   * week_start_monday : legacy column is named week_end but holds the Monday that starts the week.
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_draftable_snapshot_mv
COMMENT 'Daily snapshot of edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw (PBI Volume model Draftable table) + Team Rolled Up and PBI Localdraf Local Region. Grain: day x Team x local_practice x site x rad x exam_category x drafting_model x category. Completed weeks only.'
SCHEDULE CRON '0 0 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
SELECT
  d.calendar_date,
  d.week_end              AS week_start_monday,
  d.Team,
  r.Team_Roll_Up          AS team_rolled_up,
  CASE
      WHEN d.Team IN ('ESR', 'Lakefront Imaging', 'Jefferson', 'GLI', 'RAI', 'RP Cascade', 'RP Crossroads', 'JR', 'DRSRP', 'RP East Florida', 'RP North Florida', 'RP Palm Beach', 'PRA', 'ESRMH Garnet', 'ESRMH Hackensack', 'ESRMH Legacy', 'ESR Long Island', 'ESR Metro Hudson', 'SEAL Team', 'SEAL Legacy', 'vRad', 'Spec Ops Reserve') THEN 'Special Operations'
      WHEN d.Team IN ('ADI', 'ADR', 'CRC Central', 'CRC NW', 'CRC SW', 'Midstate', 'NEOH', 'Rad Alliance', 'RP Kentucky', 'RP Bluegrass', 'RAC', 'RACSW', 'RPKY', 'RPBG', 'RA', 'ADR Legacy', 'CRC', 'Rad Alliance Legacy', 'Rad Alliance NorthCrest', 'RP Bluegrass Legacy', 'RAA') THEN 'Apex'
      WHEN d.Team IN ('Coastal', 'Greensboro', 'MBB', 'Northside', 'Greensboro Canopy', 'RAF', 'RP Florida', 'RP Sandhills', 'RP South Carolina', 'SOAR', 'BOCA', 'GR', 'NRA', 'RASF', 'MBB Legacy', 'MBB Phoebe Putney', 'Northside Radiology', 'RAF East Coast', 'RAF Panhandle', 'RAF Sarasota', 'RAF Tampa', 'RAF Tele', 'RASF Miami', 'RASF Naples', 'RP Florida Legacy', 'RP Florida West') THEN 'Genesis'
      WHEN d.Team IN ('Advanced Radiology', 'Alaska', 'CIR', 'Desert', 'GIMA', 'RP SoCal', 'IAM', 'IAMSE', 'MIA', 'Mountain', 'NIR', 'MXC', 'Red Rock', 'RIMA', 'RP Sol', 'RP Sun City', 'RP Chicago', 'RP Forest City', 'Saline Valley', 'RP Valley Radiologists', 'SVDI', 'Western Colorado', 'WIR', 'RP IOWA', 'GSIA', 'SVL', 'MR', 'DR', 'NWIR', 'ARSC', 'DR Legacy', 'DR DRS', 'IAMSE Hurley', 'IAM Marquette', 'IAM Midlands', 'Mountain Legacy', 'Mountain Yampa', 'RP NWIR', 'RP SMIL', 'RP SoCal Lakewood', 'RP SoCal Legacy', 'RP SoCal Palmdale', 'RP Valley', 'SVDI Legacy', 'SVDI San Ramon', 'SMI', 'RIMA California') THEN 'Maverick'
      WHEN d.Team IN ('Access Alexandria', 'ARA', 'BR Academic', 'BR Community', 'CIRPA', 'Community', 'RP Eagle', 'EBI', 'GIA', 'Lake Charles', 'RP Borderlands', 'RP Brazosport', 'RP Corpus Christi', 'RP Dallas', 'RP El Paso', 'RP Gulf Coast', 'RP Houston', 'RP Laredo', 'RP Victoria', 'BR', 'Slidell', 'ACC', 'RPNM', 'EAG', 'RPEP', 'RPGC', 'RPH', 'Other', 'EXTHMC', 'RP Singleton Academic', 'RP Singleton Community', 'RP Singleton', 'Rose', 'RP North Houston', 'Synergy', 'Access Lake Charles', 'Community Laredo', 'Community Legacy', 'Community Victoria', 'Elite', 'RP Borderlands Legacy', 'RP Borderlands Lovelace', 'RP Helios') THEN 'Trailblazer'
      ELSE 'Matrix'
    END AS local_region,
  d.local_practice,
  d.site,
  d.Radiologist,
  d.npi,
  d.exam_category,
  d.drafting_model,
  d.category,
  d.category_sort_order,
  d.exam_count,
  d.tbwu
FROM edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw d
LEFT JOIN edw_test.enterprise_analytics.tbl_team_rollups r
  ON r.Team = d.Team
