-- Mosaic Efficiency semantic migration (tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md).
-- Governed, exam-grain view feeding the mosaic_efficiency_metric_view. Lifts
-- backend/app/services/mosaic_service.py's _MER_BASE_CTE_SQL + _MER_BASELINE_CTE_SQL (already a
-- validated, production SQL reimplementation of edw_dev.bipa_analytics.radiologist_metrics_optimized,
-- confirmed live via SHOW CREATE TABLE this session - same baseline_eff_excl <= 1.000 eligibility
-- gate, same Outliers/Period_Type classification), restructured to expose ONE ROW PER QUALIFYING
-- EXAM instead of the pre-aggregated grain mosaic_service.py's own functions use - metric views
-- re-aggregate to whatever grain a query asks for, so the row-per-exam shape is more flexible and
-- avoids needing a second near-duplicate query per report page.
--
-- Team vs Practice (confirmed explicitly 2026-10-22, see SEAL-current-team-mislabeling memory for
-- why this split exists): Team = provider_local_practice_name_curr (the radiologist's OWN home
-- pool - e.g. "SEAL Team" is a float/cross-coverage pool, not a billing practice). Practice =
-- managing_local_practice_name_curr (the practice whose exams are actually being read - what "By
-- Practice" reporting means business-wise). Confirmed live this session: SEAL Team's provider rows
-- span 90+ distinct managing practices, which is exactly the cross-coverage behavior this split is
-- for - collapsing to Team alone would make every SEAL-covered practice's numbers vanish into one
-- "SEAL Team" bucket.
--
-- team_rolled_up / local_region: team_rolled_up joins edw_prod.enterprise_analytics.tbl_team_rollups
-- (migrated from edw_dev.bipa_analytics.team_rollups, see 021). local_region ports
-- backend/app/data/local_region.py's Team -> 6-bucket mapping (itself a port of the real DAX
-- '0. Cur'[Local] calculated column) to SQL, keyed on Team (provider_local_practice_name_curr),
-- matching the DAX source exactly - not Practice.
--
-- additive-only: never CREATE OR REPLACE/DROP on enterprise_analytics (see memory:
-- never_overwrite_enterprise_analytics). First creation below; use ALTER VIEW ... AS (same body)
-- if the definition ever needs to change.

CREATE VIEW IF NOT EXISTS edw_prod.enterprise_analytics.tbl_efficiency_exam_level_vw
COMMENT 'Mosaic Efficiency semantic: one row per qualifying exam (has an eligible baseline, same gate as radiologist_metrics_optimized), carrying TBWU/read-time plus each exam''s own-NPI-and-procedure baseline efficiency rate. Source for mosaic_efficiency_metric_view. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.'
AS
WITH mosaic_live_practices AS (
  SELECT DISTINCT provider_local_practice_name_curr AS team
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory
  WHERE mosaic_read_flag = true AND provider_local_practice_name_curr IS NOT NULL
),
qualified_radiologists AS (
  SELECT e.reading_provider_npi AS npi
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.team = e.provider_local_practice_name_curr
  WHERE NOT e.mosaic_read_flag AND NOT e.mosaic_draft_flag
    AND CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND CAST(e.reading_provider_npi AS STRING) NOT IN (
      '1134233869', '1578529640', '1255305371', '1043457591', '1134169857', '1174919955',
      '1588690002', '1083662803', '1184859589', '1861695322', '1124331582', '1578728184',
      '1568705986', '1144482738', '1134395858'
    )
  GROUP BY e.reading_provider_npi
  HAVING COUNT(DISTINCT e.exam_id) >= 1000
),
raw_exams AS (
  SELECT
    e.exam_id, e.reading_provider_npi AS npi,
    e.reading_provider_name_full AS radiologist_name,
    e.provider_local_practice_name_curr AS team,
    e.managing_local_practice_name_curr AS practice,
    e.provider_primary_subspecialty_curr AS subspecialty,
    e.exam_Modality_Code AS modality_code,
    e.RPID_parent_code_description AS parent_procedure_name,
    x.Category AS exam_category,
    e.RPID_Procedure_Code,
    e.mosaic_read_flag, e.mosaic_draft_flag,
    CAST(e.final_datetime AS DATE) AS exam_date,
    e.unassisted_tbwu_current AS tbwu,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime,
    LAG(e.final_datetime) OVER (
      PARTITION BY e.reading_provider_npi, DATE(e.dictation_start_datetime)
      ORDER BY e.dictation_start_datetime, e.exam_id
    ) AS prev_final
  FROM edw_prod.enterprise_analytics.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.team = e.provider_local_practice_name_curr
  JOIN qualified_radiologists qr ON qr.npi = e.reading_provider_npi
  LEFT JOIN edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk x
    ON x.ParentRpt = e.RPID_parent_code
  WHERE CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND e.dictation_start_datetime IS NOT NULL
    AND e.dictation_end_datetime IS NOT NULL
    AND e.final_datetime IS NOT NULL
),
adjusted AS (
  SELECT *,
    LEAST(3600, GREATEST(0, TIMESTAMPDIFF(SECOND,
      CASE WHEN prev_final IS NOT NULL AND prev_final > dictation_start_datetime THEN prev_final ELSE dictation_start_datetime END,
      CASE WHEN final_datetime < dictation_end_datetime THEN final_datetime ELSE dictation_end_datetime END
    ))) AS adjusted_read_time_sec
  FROM raw_exams
),
outlier_calc AS (
  SELECT *,
    CASE WHEN adjusted_read_time_sec > (
      AVG(adjusted_read_time_sec) OVER (PARTITION BY RPID_Procedure_Code)
      + 2 * STDDEV(adjusted_read_time_sec) OVER (PARTITION BY RPID_Procedure_Code)
    ) THEN 'Included' ELSE 'Excluded' END AS outliers
  FROM adjusted
),
classified AS (
  SELECT *,
    CASE
      WHEN NOT mosaic_read_flag AND NOT mosaic_draft_flag THEN 'Baseline'
      WHEN mosaic_draft_flag THEN 'Drafting'
      WHEN mosaic_read_flag THEN 'Reporting'
      ELSE 'Unknown'
    END AS period_type
  FROM outlier_calc
),
baseline_by_procedure AS (
  SELECT
    npi, parent_procedure_name,
    SUM(CASE WHEN period_type = 'Baseline' AND outliers = 'Excluded' THEN tbwu ELSE 0 END) AS baseline_tbwu_excl,
    SUM(CASE WHEN period_type = 'Baseline' AND outliers = 'Excluded' THEN adjusted_read_time_sec ELSE 0 END) AS baseline_time_excl,
    SUM(CASE WHEN period_type = 'Baseline' AND outliers = 'Excluded' AND modality_code IN ('US', 'BD') THEN tbwu ELSE 0 END) AS baseline_usbd_tbwu_excl,
    SUM(CASE WHEN period_type = 'Baseline' AND outliers = 'Excluded' AND modality_code IN ('US', 'BD') THEN adjusted_read_time_sec ELSE 0 END) AS baseline_usbd_time_excl
  FROM classified
  GROUP BY npi, parent_procedure_name
),
baseline_eff AS (
  SELECT
    npi, parent_procedure_name,
    baseline_tbwu_excl / NULLIF(baseline_time_excl / 60.0, 0) AS baseline_eff_excl,
    baseline_usbd_tbwu_excl / NULLIF(baseline_usbd_time_excl / 60.0, 0) AS baseline_usbd_eff_excl
  FROM baseline_by_procedure
)
SELECT
  c.npi, c.radiologist_name, c.team,
  tr.Team_Roll_Up AS team_rolled_up,
  CASE
    WHEN c.team IN (
      'ESR','LFI','Jefferson','GLI','RAI','RP Cascade','RP Crossroads','JR','DRSRP',
      'RP East Florida','RP North Florida','RP Palm Beach','RP Florida West','PRA',
      'ESRMH Garnet','ESRMH Hackensack','ESRMH Legacy','ESR Long Island','ESR Metro Hudson',
      'SEAL Team','SEAL Legacy','vRad','Spec Ops Reserve'
    ) THEN 'Special Operations'
    WHEN c.team IN (
      'ADI','ADR','CRC Central','CRC NW','CRC SW','Midstate','NEOH','Rad Alliance',
      'RP Kentucky','RP Bluegrass','RAC','RACSW','RPKY','RPBG','RA','ADR Legacy','CRC',
      'Rad Alliance Legacy','Rad Alliance NorthCrest','RP Bluegrass Legacy'
    ) THEN 'Apex'
    WHEN c.team IN (
      'Coastal','Greensboro','MBB','Northside','Greensboro Canopy','RAF','RP Florida',
      'RP Sandhills','RP South Carolina','SOAR','BOCA','GR','NRA','RASF','MBB Legacy',
      'MBB Phoebe Putney','Northside Radiology','RAF East Coast','RAF Panhandle',
      'RAF Sarasota','RAF Tampa','RAF Tele','RASF Miami','RASF Naples','RP Florida Legacy'
    ) THEN 'Genesis'
    WHEN c.team IN (
      'Advanced Radiology','Alaska','CIR','Desert','GIMA','RP SoCal','IAM','IAMSE','MIA',
      'Mountain','NIR','RAA','MXC','Red Rock','RIMA','RP Sol','RP Sun City','RP Chicago',
      'RP Forest City','Saline Valley','RP Valley Radiologists','SVDI','Western Colorado',
      'WIR','RP IOWA','GSIA','SVL','MR','DR','NWIR','ARSC','DR Legacy','DR DRS',
      'IAMSE Hurley','IAM Marquette','IAM Midlands','Lakefront Imaging','Mountain Legacy',
      'Mountain Yampa','RP NWIR','RP SMIL','RP SoCal Lakewood','RP SoCal Legacy',
      'RP SoCal Palmdale','RP Valley','SVDI Legacy','SVDI San Ramon','SMI','RIMA California'
    ) THEN 'Maverick'
    WHEN c.team IN (
      'Access Alexandria','ARA','BR Academic','BR Community','CIRPA','Community','RP Eagle',
      'EBI','GIA','Lake Charles','RP Borderlands','RP Brazosport','RP Corpus Christi',
      'RP Dallas','RP El Paso','RP Gulf Coast','RP Houston','RP Laredo','RP Victoria','BR',
      'Slidell','ACC','RPNM','EAG','RPEP','RPGC','RPH','Other','EXTHMC',
      'RP Singleton Academic','RP Singleton Community','RP Singleton','Rose',
      'RP North Houston','Synergy','Access Lake Charles','Community Laredo',
      'Community Legacy','Community Victoria','Elite','RP Borderlands Legacy',
      'RP Borderlands Lovelace','RP Helios'
    ) THEN 'Trailblazer'
    ELSE 'Matrix'
  END AS local_region,
  c.practice, c.subspecialty, c.modality_code, c.parent_procedure_name, c.exam_category,
  c.exam_date, c.period_type, c.outliers, c.tbwu, c.adjusted_read_time_sec,
  be.baseline_eff_excl, be.baseline_usbd_eff_excl,
  -- Per-NPI qualification flags (Parameter.tmdl's Rad_Qualifies_Opt / Timeline.tmdl's
  -- 'HasBothMetrics Practice' pattern): "has both baseline and mosaic" reduces to "has >=1
  -- qualifying row in this mode" because every row already carries a valid per-row baseline
  -- (guaranteed by the WHERE filter below) - so there's no separate has_baseline check needed.
  -- Min-exams threshold is hardcoded to 0 (the PBI model's own default fallback everywhere it's
  -- read) - see MIGRATION_PLAYBOOK.md for the configurable-threshold follow-up.
  SUM(CASE WHEN c.period_type = 'Reporting' AND c.outliers = 'Excluded' THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS reporting_qualifies,
  SUM(CASE WHEN c.period_type = 'Drafting' AND c.outliers = 'Excluded' AND c.modality_code IN ('CR', 'CT') THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS drafting_qualifies,
  SUM(CASE WHEN c.period_type = 'Drafting' AND c.outliers = 'Excluded' AND c.modality_code IN ('US', 'BD') THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS capture_qualifies,
  SUM(CASE WHEN c.period_type = 'Drafting' AND c.outliers = 'Excluded' AND c.modality_code IN ('CR', 'CT', 'US', 'BD') THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS drafting_capture_qualifies,
  SUM(CASE WHEN c.period_type IN ('Reporting', 'Drafting') AND c.outliers = 'Excluded' THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS full_mosaic_qualifies,
  SUM(CASE WHEN c.period_type IN ('Reporting', 'Drafting', 'Baseline') AND c.outliers = 'Excluded' THEN 1 ELSE 0 END)
    OVER (PARTITION BY c.npi) > 0 AS both_qualifies
FROM classified c
JOIN baseline_eff be ON be.npi = c.npi AND be.parent_procedure_name = c.parent_procedure_name
LEFT JOIN edw_prod.enterprise_analytics.tbl_team_rollups tr ON tr.Team = c.team
WHERE be.baseline_eff_excl <= 1.000;
