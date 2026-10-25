"""Mosaic Volume EDW queries - kept in its own module (not mosaic_service.py) so the boundary
between this governed, dashboard-reconciled domain and the app's older, independently-evolved
domains stays obvious at a glance. See tools/mosaic_validation/VALIDATION_REPORT_VOLUME.md for the
reconciliation this was built to match: every measure here is deliberately the same SQL shape as
edw_test.enterprise_analytics.mosaic_volume_metric_view, run against the same edw_prod base table,
so the numbers are identical by construction, not by coincidence.

Deliberately NOT included (same scope boundary as the governed metric view): Team Rolled Up
grouping (needs tbl_team_rollups, which only exists in edw_test - this app's service principal
cannot reach it) and the AD-group/drafting-enablement measures (same edw_test-only reachability
gap). Local Region IS included - it's a flat CASE expression with no join dependency, copied
verbatim from the deployed metric view's own YAML (confirmed identical 2026-10-23)."""

from app.config import settings
from app.db.databricks_client import run_query, run_query_one
from app.services.mosaic_service import _RPCE_PCT_ADJUSTMENT, _RPCE_SOURCE_SYSTEMS_SQL

# Copied verbatim from edw_test.enterprise_analytics.mosaic_volume_metric_view's own "Local
# Region" dimension YAML (confirmed identical via SHOW CREATE TABLE, 2026-10-23) - one of 6 fixed
# regions (Special Operations/Apex/Genesis/Maverick/Trailblazer/Matrix), keyed on the radiologist's
# own home Team. Do not hand-edit this list without also updating the metric view, or the two
# surfaces will silently diverge on Local Region groupings.
_LOCAL_REGION_CASE_SQL = """
    CASE
      WHEN provider_local_practice_name_curr IN (
        'ESR','LFI','Jefferson','GLI','RAI','RP Cascade','RP Crossroads','JR','DRSRP',
        'RP East Florida','RP North Florida','RP Palm Beach','RP Florida West','PRA',
        'ESRMH Garnet','ESRMH Hackensack','ESRMH Legacy','ESR Long Island','ESR Metro Hudson',
        'SEAL Team','SEAL Legacy','vRad','Spec Ops Reserve'
      ) THEN 'Special Operations'
      WHEN provider_local_practice_name_curr IN (
        'ADI','ADR','CRC Central','CRC NW','CRC SW','Midstate','NEOH','Rad Alliance',
        'RP Kentucky','RP Bluegrass','RAC','RACSW','RPKY','RPBG','RA','ADR Legacy','CRC',
        'Rad Alliance Legacy','Rad Alliance NorthCrest','RP Bluegrass Legacy'
      ) THEN 'Apex'
      WHEN provider_local_practice_name_curr IN (
        'Coastal','Greensboro','MBB','Northside','Greensboro Canopy','RAF','RP Florida',
        'RP Sandhills','RP South Carolina','SOAR','BOCA','GR','NRA','RASF','MBB Legacy',
        'MBB Phoebe Putney','Northside Radiology','RAF East Coast','RAF Panhandle',
        'RAF Sarasota','RAF Tampa','RAF Tele','RASF Miami','RASF Naples','RP Florida Legacy'
      ) THEN 'Genesis'
      WHEN provider_local_practice_name_curr IN (
        'Advanced Radiology','Alaska','CIR','Desert','GIMA','RP SoCal','IAM','IAMSE','MIA',
        'Mountain','NIR','RAA','MXC','Red Rock','RIMA','RP Sol','RP Sun City','RP Chicago',
        'RP Forest City','Saline Valley','RP Valley Radiologists','SVDI','Western Colorado',
        'WIR','RP IOWA','GSIA','SVL','MR','DR','NWIR','ARSC','DR Legacy','DR DRS',
        'IAMSE Hurley','IAM Marquette','IAM Midlands','Lakefront Imaging','Mountain Legacy',
        'Mountain Yampa','RP NWIR','RP SMIL','RP SoCal Lakewood','RP SoCal Legacy',
        'RP SoCal Palmdale','RP Valley','SVDI Legacy','SVDI San Ramon','SMI','RIMA California'
      ) THEN 'Maverick'
      WHEN provider_local_practice_name_curr IN (
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
    END
"""

# Core measure set shared by every query below - exact SQL shape as the governed metric view's
# Exam Count / Mosaic Exam Count / Pct Mosaic Exams / Drafting Exam Count / Pct Drafting Exams /
# Pct RPCE Reporting / Pct RPCE Drafting, so a company-wide total computed here matches the
# dashboard's company-wide total exactly (confirmed live, see VALIDATION_REPORT_VOLUME.md).
_VOLUME_MEASURES_SQL = f"""
    COUNT(*)                                                                        AS total_exams,
    SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END)                               AS mosaic_exams,
    SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)         AS pct_mosaic,
    SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END)                              AS drafting_exams,
    SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)        AS pct_drafting,
    (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
      / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
      + {_RPCE_PCT_ADJUSTMENT}                                                      AS pct_rpce_reporting,
    (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
      / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
      + {_RPCE_PCT_ADJUSTMENT}                                                      AS pct_rpce_drafting
"""


def get_volume_summary() -> dict:
    """Company-wide (no grouping) volume snapshot."""
    return run_query_one(
        f"""
        SELECT {_VOLUME_MEASURES_SQL}
        FROM {settings.qualified}.tbl_exam_inventory
        """
    ) or {}


def get_volume_by_practice() -> list[dict]:
    """By Managing Practice - whose exams are actually being read, regardless of which Team/pool
    the reading radiologist belongs to (the business-facing "By Practice" cut, same convention as
    the Efficiency/Capacity migration's own Team-vs-Practice fix)."""
    return run_query(
        f"""
        SELECT
          managing_local_practice_name_curr AS `group`,
          {_VOLUME_MEASURES_SQL}
        FROM {settings.qualified}.tbl_exam_inventory
        GROUP BY managing_local_practice_name_curr
        ORDER BY total_exams DESC
        """
    )


def get_volume_by_team() -> list[dict]:
    """By Team - the reading radiologist's own home/float-pool practice (e.g. "SEAL Team" is a
    cross-coverage pool, not a billing practice) - not the same cut as By Practice above."""
    return run_query(
        f"""
        SELECT
          provider_local_practice_name_curr AS `group`,
          {_VOLUME_MEASURES_SQL}
        FROM {settings.qualified}.tbl_exam_inventory
        GROUP BY provider_local_practice_name_curr
        ORDER BY total_exams DESC
        """
    )


def get_volume_by_local_region() -> list[dict]:
    """By Local Region - one of 6 fixed regions, keyed on Team. See _LOCAL_REGION_CASE_SQL's own
    comment for the reconciliation guarantee with the governed metric view."""
    return run_query(
        f"""
        SELECT
          {_LOCAL_REGION_CASE_SQL} AS `group`,
          {_VOLUME_MEASURES_SQL}
        FROM {settings.qualified}.tbl_exam_inventory
        GROUP BY {_LOCAL_REGION_CASE_SQL}
        ORDER BY total_exams DESC
        """
    )


def get_volume_trend() -> list[dict]:
    """Monthly volume trend, company-wide (no Practice/Team grouping - matches the dashboard's
    Volume Trend Visual page's own always-visible-measures convention).

    Excludes the NULL-final_datetime bucket (~22.6M exams, confirmed identical on the Lakeview
    dashboard's own Final Month dimension - not something introduced here) via the WHERE clause,
    not just a client-side chart filter: a null `period` isn't a real calendar month, and leaving
    it in the query let it reach VolumeTrendPoint's `period: str` field as a Python None, which
    raised a validation error that 500'd the whole endpoint - confirmed live 2026-10-24. Filtering
    here only drops one unplottable trend-chart row, it does not change any company-wide total
    (VolumeSummary queries the full unfiltered table separately)."""
    return run_query(
        f"""
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', final_datetime) AS DATE) AS STRING) AS period,
          COUNT(*)                                                          AS total_exams,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END)                 AS mosaic_exams,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS pct_mosaic,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END)                AS drafting_exams,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS pct_drafting
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE final_datetime IS NOT NULL
        GROUP BY DATE_TRUNC('MONTH', final_datetime)
        ORDER BY period
        """
    )


def get_volume_filter_options() -> dict:
    rows = run_query(
        f"""
        SELECT DISTINCT managing_local_practice_name_curr AS practice, provider_local_practice_name_curr AS team
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE managing_local_practice_name_curr IS NOT NULL OR provider_local_practice_name_curr IS NOT NULL
        """
    )
    practices = sorted({r["practice"] for r in rows if r.get("practice")})
    teams = sorted({r["team"] for r in rows if r.get("team")})
    local_regions = ["Special Operations", "Apex", "Genesis", "Maverick", "Trailblazer", "Matrix"]
    return {"practices": practices, "teams": teams, "local_regions": local_regions}
