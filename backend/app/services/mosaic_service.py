from app.config import settings
from app.data.rpce_audit import rpce_status_counts
from app.db.databricks_client import run_query, run_query_one
from app.models.mosaic import (
    BlockerByPractice,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    DeploymentFunnel,
    DeploymentFunnelStage,
    DeploymentPracticeRollup,
    DeploymentRadiologistItem,
    MosaicIntelligenceSnapshot,
    RadiologistRosterItem,
    RadSummaryStat,
    RpceTrendPoint,
    UtilizationPracticeRollup,
)

CT_ABDPEL_DRAFT_CODES = (
    "CT3PHLIV", "RPID152-3D", "RPID1060-3D", "RPID1449", "RPID279", "RPID140", "RAD2508", "RPID152", "RPID1060",
    "RPID1459", "CTAPRENALMA", "RPID1643D", "RPID164", "RAD2260", "RAD2262", "RAD2261", "RPID145", "RPID145-RC",
    "RPID144", "RPID144RC", "RPID144-RC", "RPID198", "RPID198-IVP3D", "RPID198-RC", "RPID5", "RPID3", "RPID4",
    "RAD2345", "RAD2346", "RAD2011", "RPID48-B", "RPID46-B", "RAD2266", "RAD2012", "RAD2013", "RAD2014", "RPID64",
    "RPID48", "RPID48MR", "RPID68-MIP", "RPID48-RC", "RPID46", "RPID47", "RPID47MR", "RPID47-RC", "CT4PHLIV",
    "RAD2852", "RAD2853", "RPID46-RC", "RAD2854", "RAD2986", "RAD2987",
)
_CT_ABDPEL_CODES_SQL = ", ".join(f"'{code}'" for code in CT_ABDPEL_DRAFT_CODES)

CT_CHEST_DRAFT_CODES = (
    "RPID249", "RPID249T", "RPID357", "RPID357T", "RPID250", "RPID251", "RPID356", "RPID252",
    "RPID250-CAPWWO", "RPID252-CAWWO", "RPID250-CAPWOW", "RPID18", "RPID18I-BP", "RPID18-SD",
    "RPID16", "RPID16-IBP", "RPID16-LD", "RPID16-PNHR", "RPID16-PNLR", "RPID16-SP", "RPID16-SD",
    "RPID16T", "RPID16-ZP", "RPID17", "RPID16-QRS", "RAD2942",
)
_CT_CHEST_CODES_SQL = ", ".join(f"'{code}'" for code in CT_CHEST_DRAFT_CODES)

# RPCE Exam Flag isn't a physical column here; RPCE-sourced rows are identified the same way
# as elsewhere in this schema (mv_mosaic_volume's "Is RPCE" field).
_RPCE_SOURCE_SYSTEMS_SQL = "'rpceMidwest', 'rpceSouthwest'"

# Both % RPCE measures in the source DAX model add a flat 0.02 (2 percentage points) to the
# ratio, with no comment explaining why - confirmed with the business owner this is an
# intentional, known adjustment to retain, not a leftover hack.
_RPCE_PCT_ADJUSTMENT = 0.02


# presentation_mosaicdailyvolume_vw and radiologist_metrics_optimized are heavy semantic
# views with dozens of joins baked in (confirmed via EXPLAIN); referencing either ALONE is
# fast, but joining two of them together row-by-row in one query compounds that cost to the
# point of not returning within 15+ minutes. Every function below therefore touches at most
# one such heavy view per query and combines results in Python instead of in SQL.


def get_radiologist_roster(
    practice: str | None = None,
    subspecialty: str | None = None,
    deployment_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RadiologistRosterItem]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))

    where_clauses = []
    params: dict[str, object] = {}
    if practice:
        where_clauses.append("home_practice = %(practice)s")
        params["practice"] = practice
    if subspecialty:
        where_clauses.append("working_subspecialty = %(subspecialty)s")
        params["subspecialty"] = subspecialty
    if deployment_status:
        where_clauses.append("deployment_status = %(deployment_status)s")
        params["deployment_status"] = deployment_status

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    rows = run_query(
        f"""
        SELECT NPI AS npi, radiologist_name, home_practice, working_subspecialty,
               deployment_status, deployment_launch_group, current_team,
               TRY_CAST(REPLACE(CAST(reporting_cases_read AS STRING), ',', '') AS DOUBLE) AS reporting_cases_read,
               TRY_CAST(REPLACE(CAST(total_drafting_cases AS STRING), ',', '') AS DOUBLE) AS total_drafting_cases
        FROM {settings.qualified}.dim_mosaic_radiologist
        {where_sql}
        ORDER BY radiologist_name
        LIMIT {safe_limit} OFFSET {safe_offset}
        """,
        params,
    )
    return [RadiologistRosterItem(**row) for row in rows]


def get_utilization_by_practice(days_back: int = 30) -> list[UtilizationPracticeRollup]:
    safe_days = max(1, min(int(days_back), 365))
    rows = run_query(
        f"""
        SELECT
          COALESCE(dp.practice_rollup, v.Team)                                          AS practice,
          SUM(v.Case_Count)                                                             AS total_exams,
          SUM(v.Mosaic_flag)                                                            AS mosaic_exams,
          SUM(v.Mosaic_flag) / NULLIF(SUM(v.Case_Count), 0)                             AS pct_mosaic,
          SUM(v.mosaic_draft_flag)                                                      AS drafting_exams,
          SUM(v.mosaic_draft_flag) / NULLIF(SUM(v.Case_Count), 0)                       AS pct_drafting,
          SUM(CASE WHEN v.modality_code = 'US' THEN v.mosaic_draft_flag ELSE 0 END)     AS capture_exams,
          SUM(CASE WHEN v.modality_code = 'MG' THEN 1 ELSE 0 END)                       AS mammo_exams,
          SUM(CASE WHEN v.modality_code = 'MG' THEN v.Mosaic_flag ELSE 0 END)           AS mammo_mosaic_exams,
          SUM(CASE WHEN v.modality_code = 'MG' THEN v.Mosaic_flag ELSE 0 END)
            / NULLIF(SUM(CASE WHEN v.modality_code = 'MG' THEN 1 ELSE 0 END), 0)        AS pct_mammo_mosaic,
          COUNT(DISTINCT CASE WHEN v.Mosaic_flag = 1 THEN v.NPI END)                     AS rads_live,
          COUNT(DISTINCT CASE WHEN v.mosaic_draft_flag = 1 THEN v.NPI END)               AS rads_drafting
        FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw v
        LEFT JOIN {settings.qualified}.dim_mosaic_practice dp ON dp.team_code = v.Team
        WHERE v.Calendar_Date >= CURRENT_DATE - {safe_days} AND v.Calendar_Date <= CURRENT_DATE
        GROUP BY COALESCE(dp.practice_rollup, v.Team)
        ORDER BY total_exams DESC
        """
    )
    return [UtilizationPracticeRollup(**row) for row in rows]


def get_deployment_by_radiologist(limit: int = 500, offset: int = 0) -> list[DeploymentRadiologistItem]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    rows = run_query(
        f"""
        WITH last14 AS (
          SELECT
            NPI,
            SUM(CASE WHEN modality_code = 'CT' AND Clinical_Procedure_Code = 'RPID22' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_head_drafts_14d,
            SUM(CASE WHEN modality_code = 'CR' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS xr_drafts_14d,
            SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_ABDPEL_CODES_SQL}) AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_abdpel_drafts_14d
          FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
          WHERE Calendar_Date >= CURRENT_DATE - 14 AND Calendar_Date <= CURRENT_DATE
          GROUP BY NPI
        )
        SELECT
          dr.NPI AS npi, dr.radiologist_name, dr.home_practice, dr.working_subspecialty,
          drft.DraftingStatus AS xr_ct_head_status,
          ctap.StatusLabel AS ct_abdpel_status,
          COALESCE(l.ct_head_drafts_14d, 0) AS ct_head_drafts_last_14d,
          COALESCE(l.xr_drafts_14d, 0) AS xr_drafts_last_14d,
          COALESCE(l.ct_abdpel_drafts_14d, 0) AS ct_abdpel_drafts_last_14d
        FROM {settings.qualified}.dim_mosaic_radiologist dr
        LEFT JOIN {settings.qualified}.vw_drafting_npi_bridge drft ON drft.NPI = dr.NPI
        LEFT JOIN {settings.qualified}.vw_ct_abdpel_npi_bridge ctap ON ctap.NPI = dr.NPI
        LEFT JOIN last14 l ON l.NPI = dr.NPI
        ORDER BY dr.radiologist_name
        LIMIT {safe_limit} OFFSET {safe_offset}
        """
    )
    return [DeploymentRadiologistItem(**row) for row in rows]


def get_deployment_by_practice() -> list[DeploymentPracticeRollup]:
    rows = run_query(
        f"""
        WITH last14 AS (
          SELECT
            NPI,
            SUM(CASE WHEN modality_code = 'CT' AND Clinical_Procedure_Code = 'RPID22' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_head_drafts_14d,
            SUM(CASE WHEN modality_code = 'CR' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS xr_drafts_14d,
            SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_ABDPEL_CODES_SQL}) AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_abdpel_drafts_14d
          FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
          WHERE Calendar_Date >= CURRENT_DATE - 14 AND Calendar_Date <= CURRENT_DATE
          GROUP BY NPI
        )
        SELECT
          dr.home_practice AS practice,
          COUNT(DISTINCT dr.NPI) AS total_rads,
          COUNT(DISTINCT CASE WHEN drft.DraftingStatus IN ('Fully Enabled, 1+ Drafts', 'Fully Enabled, No Drafts') THEN dr.NPI END) AS xr_ct_head_enabled_rads,
          COUNT(DISTINCT CASE WHEN ctap.StatusLabel IN ('Enabled, 1+ Drafts', 'Enabled, No Drafts') THEN dr.NPI END) AS ct_abdpel_enabled_rads,
          SUM(COALESCE(l.ct_head_drafts_14d, 0)) AS ct_head_cases_last_14d,
          SUM(COALESCE(l.xr_drafts_14d, 0)) AS xr_cases_last_14d,
          SUM(COALESCE(l.ct_abdpel_drafts_14d, 0)) AS ct_abdpel_cases_last_14d
        FROM {settings.qualified}.dim_mosaic_radiologist dr
        LEFT JOIN {settings.qualified}.vw_drafting_npi_bridge drft ON drft.NPI = dr.NPI
        LEFT JOIN {settings.qualified}.vw_ct_abdpel_npi_bridge ctap ON ctap.NPI = dr.NPI
        LEFT JOIN last14 l ON l.NPI = dr.NPI
        WHERE dr.home_practice IS NOT NULL
        GROUP BY dr.home_practice
        ORDER BY total_rads DESC
        """
    )
    return [DeploymentPracticeRollup(**row) for row in rows]


def get_deployment_funnel_reporting() -> DeploymentFunnel:
    """The Reporting waterfall is a direct pass-through of the pre-computed 11-stage
    StatusLabel/StatusRank progression on vw_deployment_npi_bridge - "Do Not Launch" rads
    are already excluded structurally (StatusLabel is NULL for them, filtered by the WHERE).
    """
    rows = run_query(
        f"""
        SELECT StatusLabel AS stage, StatusRank AS rank, COUNT(DISTINCT NPI) AS count
        FROM {settings.qualified}.vw_deployment_npi_bridge
        WHERE StatusLabel IS NOT NULL
        GROUP BY StatusLabel, StatusRank
        ORDER BY StatusRank
        """
    )
    return DeploymentFunnel(domain="Reporting", stages=[DeploymentFunnelStage(**row) for row in rows])


# vw_drafting_npi_bridge's own DraftingStatus/BlockerLabel columns turned out to have no
# rads categorized past "Eligible, Not Fully Enabled" and a BlockerLabel dominated (~37%) by
# "Other" - confirmed stale/incomplete against live EDW data, so the Drafting funnel and its
# blocker breakdown are rebuilt here directly from rad_onboarding/contacts instead of the
# bridge view. Both source tables carry duplicate rows per NPI (live Dataverse sync artifact,
# confirmed via COUNT(*) vs COUNT(DISTINCT NPI)); rn = 1 keeps only the most-recently-modified
# row per NPI. A blank launch_group/consent is treated as "no exclusion on file" -> eligible,
# per business confirmation. contacts.total_reporting_case_read (was reporting_cases_read,
# briefly total_reporting_case_read mid-migration too) - EDW confirmed a live pipeline refresh
# on the Dynamics sync renamed this column; re-verify here if it errors again.
_DRAFTING_FUNNEL_BASE_SQL = """
WITH ro_dedup AS (
  SELECT * FROM (
    SELECT ro.*, ROW_NUMBER() OVER (PARTITION BY CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) ORDER BY modified_on DESC) AS rn
    FROM `edw_prod`.`dataverse_m365-vra-dynamics-prod`.rad_onboarding ro
    WHERE npi IS NOT NULL AND npi <> '0000000000'
  ) WHERE rn = 1
),
contacts_dedup AS (
  SELECT * FROM (
    SELECT c.*, ROW_NUMBER() OVER (PARTITION BY CAST(REPLACE(npi, ',', '') AS DECIMAL(10,0)) ORDER BY modified_on DESC) AS rn
    FROM `edw_prod`.`dataverse_m365-vra-dynamics-prod`.contacts c
    WHERE npi IS NOT NULL AND npi <> '0000000000'
  ) WHERE rn = 1
),
base AS (
  SELECT
    CAST(REPLACE(ro.npi, ',', '') AS DECIMAL(10,0)) AS NPI,
    ro.practice AS Practice,
    COALESCE(UPPER(TRIM(NULLIF(ro.launch_group, 'None'))), '') AS launch_upper,
    COALESCE(UPPER(TRIM(NULLIF(ro.mosaic_drafting_consent, 'None'))), '') AS consent_upper,
    (NULLIF(ro.added_to_ad_group_cxr_abd_msk, 'None') IS NOT NULL AND TO_DATE(ro.added_to_ad_group_cxr_abd_msk, 'M/d/yyyy') > DATE'1900-01-01') AS ad_xr_valid,
    (ro.added_to_ad_group_ct_head IS NOT NULL AND CAST(ro.added_to_ad_group_ct_head AS DATE) > DATE'1900-01-01') AS ad_cthead_valid,
    (NULLIF(ro.drafting_training_completed_cxr_abd_msk, 'None') IS NOT NULL) AS xr_trained,
    (NULLIF(ro.drafting_training_completed_ct_head, 'None') IS NOT NULL) AS cthead_trained,
    TRY_CAST(REPLACE(NULLIF(cd.total_reporting_case_read, 'None'), ',', '') AS DOUBLE) AS cases_read_raw
  FROM ro_dedup ro
  LEFT JOIN contacts_dedup cd ON cd.npi = CAST(REPLACE(ro.npi, ',', '') AS DECIMAL(10,0))
),
scoped AS (
  SELECT *,
    (consent_upper NOT IN ('NO DRAFTING','DISABLED') AND launch_upper NOT IN ('DO NOT LAUNCH','DO NOT REVISIT')) AS eligible,
    (ad_xr_valid OR ad_cthead_valid) AS enabled,
    ((ad_xr_valid OR ad_cthead_valid) AND COALESCE(cases_read_raw,0) >= 1) AS live
  FROM base
  WHERE launch_upper <> 'DO NOT LAUNCH'
)
"""

_BLOCKER_LABEL_CASE_SQL = """
    CASE
      WHEN NOT eligible OR live THEN 'Not Applicable'
      WHEN COALESCE(cases_read_raw,0) < 1 THEN 'No Reporting Cases Read'
      WHEN NOT ad_xr_valid AND NOT ad_cthead_valid THEN 'No AD Group'
      WHEN NOT xr_trained AND NOT cthead_trained THEN 'No XR & CT Head Training'
      WHEN NOT xr_trained THEN 'No XR Training'
      WHEN NOT cthead_trained THEN 'No CT Head Training'
      ELSE 'Other'
    END
"""


def get_deployment_funnel_drafting() -> DeploymentFunnel:
    row = run_query_one(
        f"""
        {_DRAFTING_FUNNEL_BASE_SQL}
        SELECT
          COUNT(DISTINCT CASE WHEN eligible THEN NPI END) AS eligible,
          COUNT(DISTINCT CASE WHEN eligible AND enabled THEN NPI END) AS enabled,
          COUNT(DISTINCT CASE WHEN eligible AND live THEN NPI END) AS live
        FROM scoped
        """
    )
    row = row or {"eligible": 0, "enabled": 0, "live": 0}
    return DeploymentFunnel(
        domain="Drafting",
        stages=[
            DeploymentFunnelStage(stage="Eligible", rank=1, count=row["eligible"]),
            DeploymentFunnelStage(stage="Enabled", rank=2, count=row["enabled"]),
            DeploymentFunnelStage(stage="Live", rank=3, count=row["live"]),
        ],
    )


def get_drafting_blockers_by_practice() -> list[BlockerByPractice]:
    rows = run_query(
        f"""
        {_DRAFTING_FUNNEL_BASE_SQL}
        SELECT Practice AS practice, {_BLOCKER_LABEL_CASE_SQL} AS blocker, COUNT(DISTINCT NPI) AS count
        FROM scoped
        WHERE eligible AND NOT live
        GROUP BY Practice, {_BLOCKER_LABEL_CASE_SQL}
        ORDER BY Practice
        """
    )
    return [BlockerByPractice(**row) for row in rows]


def get_efficiency_matrix() -> list[dict]:
    """Fine-grained Efficiency source rows - one per (radiologist, practice, subspecialty,
    modality, parent procedure) - written to the dedicated SQLite efficiency_matrix table
    (see app/db/efficiency_store.py) rather than the generic JSON cache, since it's ~780K
    rows at full grain. Every downstream Efficiency view (by-radiologist, by-practice, and
    "population efficiency" for whatever slice the user has filtered to) is derived from
    this one table via real indexed SQL instead of separate EDW queries.

    Eligibility (>=1000 baseline/PowerScribe exams since 2024-11-01) is already enforced
    upstream - every NPI in radiologist_metrics_optimized has already passed it. The
    "same parent procedure in both baseline and Mosaic periods" matching requirement is
    also automatic: Weighted_Baseline_Contrib_Excl is NULL wherever a procedure has no
    matching baseline, and SUM() silently skips NULLs.
    """
    return run_query(
        """
        SELECT
          Physician_NPI AS npi, MAX(Radiologist) AS radiologist_name, Practice AS practice,
          working_subspecialty AS subspecialty, Modality_Code AS modality_code,
          Parent_Procedure_name AS parent_procedure_name,
          MAX(mpcat) AS exam_category,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTime ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN Weighted_Baseline_Contrib_Excl ELSE 0 END) AS reporting_baseline_contrib,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTime ELSE 0 END) AS drafting_time,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN Weighted_Baseline_Contrib_Excl ELSE 0 END) AS drafting_baseline_contrib,
          SUM(CASE WHEN Is_Capture_Row = 1 THEN TotalTBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN Is_Capture_Row = 1 THEN TotalTime ELSE 0 END) AS capture_time,
          SUM(CASE WHEN Is_Capture_Row = 1 THEN Weighted_Baseline_USBD_Contrib_Excl ELSE 0 END) AS capture_baseline_contrib
        FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
        WHERE Exam_Date >= '2024-11-01'
        GROUP BY Physician_NPI, Practice, working_subspecialty, Modality_Code, Parent_Procedure_name
        """
    )


def get_efficiency_trend_by_category() -> list[dict]:
    """Monthly efficiency trend, split by exam category - feeds both the "Mosaic Efficiency
    Over Time" chart (absolute TBWU/min) and the "Efficiency Change" chart (same data,
    rendered as % vs baseline instead) so no second EDW query is needed for the latter.
    Grouped by (month, exam category) rather than the full (practice/subspecialty/modality/
    procedure) dimension set the aggregate matrix uses, since adding a month axis to that
    780K-row matrix would explode cardinality into the tens of millions.
    """
    return run_query(
        """
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', Exam_Date) AS DATE) AS STRING) AS period,
          MAX(mpcat) AS exam_category,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTime ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN Weighted_Baseline_Contrib_Excl ELSE 0 END) AS reporting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN Is_Reporting_Row = 1 THEN Physician_NPI END) AS reporting_rad_count,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN ExamCount ELSE 0 END) AS reporting_exam_count,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTime ELSE 0 END) AS drafting_time,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN Weighted_Baseline_Contrib_Excl ELSE 0 END) AS drafting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN Is_Drafting_Row = 1 THEN Physician_NPI END) AS drafting_rad_count,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN ExamCount ELSE 0 END) AS drafting_exam_count
        FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
        WHERE Exam_Date >= '2024-11-01'
        GROUP BY DATE_TRUNC('MONTH', Exam_Date), mpcat
        ORDER BY period
        """
    )


def get_efficiency_trend_rp_avg() -> list[dict]:
    """Company-wide (ignores every filter) monthly efficiency, for the two "RP Avg" reference
    lines - Drafting Only and Full Mosaic (no RP Avg for Reporting/Non-Drafted, per spec)."""
    return run_query(
        """
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', Exam_Date) AS DATE) AS STRING) AS period,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN Is_Reporting_Row = 1 THEN TotalTime ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN Is_Drafting_Row = 1 THEN TotalTime ELSE 0 END) AS drafting_time
        FROM edw_dev.bipa_analytics.radiologist_metrics_optimized
        WHERE Exam_Date >= '2024-11-01'
        GROUP BY DATE_TRUNC('MONTH', Exam_Date)
        ORDER BY period
        """
    )


# utilization_*_pct is "% of scheduled shift time spent actively reading" (read-time minutes
# / scheduled minutes, capped at 100%) - verified against the source view's own
# on_shift_utilization_*_pct columns, which algebraically reduce to this same ratio
# regardless of RVU/RPWU/RPWU25 (the unit cancels out), so all three variants are
# identical; not a bug, just redundant naming upstream. This is a genuinely different
# metric from capacity_rvu/baseline_rvu (which measure output volume, not time spent).
_CAPACITY_MEASURES_SQL = """
  COUNT(1)                                                                AS total_shifts,
  SUM(no_hours)                                                           AS total_hours,
  SUM(on_shift_capacity_RVU)                                             AS capacity_rvu,
  SUM(on_shift_capacity_RPWU)                                            AS capacity_rpwu,
  SUM(shift_baseline_RVU)                                                AS baseline_rvu,
  SUM(shift_baseline_RPWU)                                               AS baseline_rpwu,
  LEAST(SUM(on_shift_efficiency_denominator_minutes) / NULLIF(SUM(no_hours) * 60.0, 0), 1.0) AS utilization_rvu_pct,
  LEAST(SUM(on_shift_efficiency_denominator_minutes) / NULLIF(SUM(no_hours) * 60.0, 0), 1.0) AS utilization_rpwu_pct,
  SUM(on_shift_efficiency_numerator_RVU) / NULLIF(SUM(on_shift_efficiency_denominator_minutes), 0) AS efficiency_rvu_per_min,
  SUM(on_shift_efficiency_numerator_RPWU) / NULLIF(SUM(on_shift_efficiency_denominator_minutes), 0) AS efficiency_rpwu_per_min,
  SUM(on_shift_capacity_RVU) / NULLIF(SUM(no_hours), 0)                  AS capacity_rvu_per_hour,
  SUM(shift_baseline_RVU) / NULLIF(SUM(no_hours), 0)                     AS baseline_rvu_per_hour,
  SUM(on_shift_cases)                                                    AS on_shift_cases,
  SUM(on_shift_mosaic_cases)                                             AS mosaic_cases,
  SUM(on_shift_mosaic_drafting_cases)                                    AS drafting_cases,
  SUM(on_shift_mosaic_cases) / NULLIF(SUM(on_shift_cases), 0)            AS pct_mosaic,
  SUM(on_shift_mosaic_drafting_cases) / NULLIF(SUM(on_shift_cases), 0)   AS pct_drafting,
  SUM(on_shift_capacity_RVU) / NULLIF(SUM(on_shift_cases), 0)            AS avg_rvu_per_case,
  SUM(on_shift_CT_cases)                                                 AS ct_cases,
  SUM(on_shift_XR_cases)                                                 AS xr_cases,
  SUM(on_shift_US_cases)                                                 AS us_cases,
  SUM(on_shift_MR_cases)                                                 AS mr_cases,
  SUM(on_shift_IR_cases)                                                 AS ir_cases,
  SUM(adjustment_RVU)                                                    AS adjustment_rvu,
  SUM(adjustment_TBWU)                                                   AS adjustment_tbwu
"""


def get_capacity_by_radiologist(limit: int = 500, offset: int = 0) -> list[CapacityRadiologistItem]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    rows = run_query(
        f"""
        SELECT
          NPI AS npi, Rad_name AS radiologist_name, Team AS team, localpractice AS practice,
          {_CAPACITY_MEASURES_SQL}
        FROM edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw
        GROUP BY NPI, Rad_name, Team, localpractice
        ORDER BY radiologist_name
        LIMIT {safe_limit} OFFSET {safe_offset}
        """
    )
    return [CapacityRadiologistItem(**row) for row in rows]


def get_capacity_by_practice() -> list[CapacityPracticeRollup]:
    rows = run_query(
        f"""
        SELECT
          localpractice AS practice,
          {_CAPACITY_MEASURES_SQL}
        FROM edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw
        WHERE localpractice IS NOT NULL
        GROUP BY localpractice
        ORDER BY practice
        """
    )
    return [CapacityPracticeRollup(**row) for row in rows]


def get_mosaic_intelligence_snapshot() -> MosaicIntelligenceSnapshot:
    volume_row = run_query_one(
        f"""
        SELECT
          COUNT(DISTINCT CASE WHEN Mosaic_flag = 1 THEN NPI END) AS rads_live_on_mosaic,
          COUNT(DISTINCT CASE WHEN modality_code IN ('US', 'BD') AND mosaic_draft_flag = 1
                              AND Mexproc IS NOT NULL THEN NPI END) AS rads_live_on_capture,
          (SUM(CASE WHEN Mosaic_flag = 1 THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN mosaic_draft_flag = 1 THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
        WHERE Calendar_Date >= '2025-04-01'
        """
    )

    drafting_row = run_query_one(
        f"""
        WITH drafting_activity AS (
          SELECT NPI, SUM(mosaic_draft_flag) AS total_drafts
          FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
          WHERE Calendar_Date >= '2025-04-01'
          GROUP BY NPI
        )
        SELECT COUNT(DISTINCT da.NPI) AS rads_live_on_ai_drafting
        FROM drafting_activity da
        JOIN `edw_prod`.`dataverse_m365-vra-dynamics-prod`.rad_onboarding ro
          ON CAST(REPLACE(ro.npi, ',', '') AS DECIMAL(10,0)) = da.NPI
        WHERE da.total_drafts >= 1
          AND (
            (NULLIF(ro.added_to_ad_group_cxr_abd_msk, 'None') IS NOT NULL
              AND TO_DATE(ro.added_to_ad_group_cxr_abd_msk, 'M/d/yyyy') <> DATE'1900-01-01')
            OR (ro.added_to_ad_group_ct_head IS NOT NULL
              AND CAST(ro.added_to_ad_group_ct_head AS DATE) <> DATE'1900-01-01')
            OR (ro.added_to_ad_group_ct_abd_pelvis IS NOT NULL
              AND CAST(ro.added_to_ad_group_ct_abd_pelvis AS DATE) <> DATE'1900-01-01')
          )
        """
    )

    rpce_counts = rpce_status_counts()
    return MosaicIntelligenceSnapshot(
        rads_live_on_mosaic=volume_row["rads_live_on_mosaic"] if volume_row else 0,
        rads_live_on_ai_drafting=drafting_row["rads_live_on_ai_drafting"] if drafting_row else 0,
        pct_rpce_reporting=volume_row["pct_rpce_reporting"] if volume_row else None,
        pct_rpce_drafting=volume_row["pct_rpce_drafting"] if volume_row else None,
        rads_live_on_capture=volume_row["rads_live_on_capture"] if volume_row else 0,
        practices_fully_on_rpce=rpce_counts["Fully on RPCE"],
        practices_split_integration=rpce_counts["Split Integration"],
        practices_not_on_rpce=rpce_counts["Not on RPCE"],
    )


def get_rpce_trend() -> list[RpceTrendPoint]:
    rows = run_query(
        f"""
        SELECT
          CAST(Calendar_Date AS STRING) AS period,
          SUM(CASE WHEN Mosaic_flag = 1 THEN 1 ELSE 0 END) AS mosaic_exam_ct,
          SUM(CASE WHEN mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS drafting_exam_ct,
          (SUM(CASE WHEN Mosaic_flag = 1 THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN mosaic_draft_flag = 1 THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
        WHERE Calendar_Date >= '2025-04-01'
        GROUP BY Calendar_Date
        ORDER BY Calendar_Date
        """
    )
    return [RpceTrendPoint(**row) for row in rows]


def get_rad_summary_stats() -> list[RadSummaryStat]:
    agg_rows = run_query(
        f"""
        SELECT
          NPI AS npi,
          MIN(CASE WHEN Mosaic_flag = 1 THEN Calendar_Date END) AS mosaic_go_live_date,
          SUM(CASE WHEN Mosaic_flag = 1 THEN 1 ELSE 0 END) AS total_mosaic_exams,
          COUNT(*) AS total_exams,
          SUM(CASE WHEN modality_code = 'MG' THEN 1 ELSE 0 END) AS mammo_total,
          SUM(CASE WHEN modality_code = 'MG' AND Mosaic_flag = 1 THEN 1 ELSE 0 END) AS mammo_mosaic,
          SUM(CASE WHEN modality_code = 'CR' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS total_xr_drafted,
          SUM(CASE WHEN modality_code = 'CR' AND drafteligibleproc IS NOT NULL THEN 1 ELSE 0 END) AS draftable_xr,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode = 'RPID22' AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_head_drafted,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode = 'RPID22' THEN 1 ELSE 0 END) AS draftable_ct_head,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_ABDPEL_CODES_SQL}) AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_abdpel_drafted,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_ABDPEL_CODES_SQL}) THEN 1 ELSE 0 END) AS draftable_ct_abdpel,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_CHEST_CODES_SQL}) AND mosaic_draft_flag = 1 THEN 1 ELSE 0 END) AS ct_chest_drafted,
          SUM(CASE WHEN modality_code = 'CT' AND Drafteligiblecode IN ({_CT_CHEST_CODES_SQL}) THEN 1 ELSE 0 END) AS draftable_ct_chest,
          SUM(CASE WHEN modality_code = 'US' AND mosaic_draft_flag = 1 AND Mexproc IS NOT NULL THEN 1 ELSE 0 END) AS captured_us,
          SUM(CASE WHEN modality_code = 'US' AND Mexproc IS NOT NULL THEN 1 ELSE 0 END) AS us_capturable
        FROM edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw
        WHERE Calendar_Date >= '2025-04-01'
        GROUP BY NPI
        """
    )

    dim_rows = run_query(
        f"""
        SELECT NPI AS npi, radiologist_name, home_practice
        FROM {settings.qualified}.dim_mosaic_radiologist
        """
    )
    dim_by_npi = {row["npi"]: row for row in dim_rows}

    group_rows = run_query(
        """
        SELECT
          CAST(REPLACE(ro.npi, ',', '') AS DECIMAL(10,0)) AS npi,
          (NULLIF(ro.added_to_ad_group_cxr_abd_msk, 'None') IS NOT NULL
            AND TO_DATE(ro.added_to_ad_group_cxr_abd_msk, 'M/d/yyyy') <> DATE'1900-01-01') AS on_xr,
          (ro.added_to_ad_group_ct_head IS NOT NULL
            AND CAST(ro.added_to_ad_group_ct_head AS DATE) <> DATE'1900-01-01') AS on_ct_head,
          (ro.added_to_ad_group_ct_abd_pelvis IS NOT NULL
            AND CAST(ro.added_to_ad_group_ct_abd_pelvis AS DATE) <> DATE'1900-01-01') AS on_ct_abdpel
        FROM `edw_prod`.`dataverse_m365-vra-dynamics-prod`.rad_onboarding ro
        """
    )
    groups_by_npi: dict[int, list[str]] = {}
    for row in group_rows:
        groups = []
        if row["on_xr"]:
            groups.append("XR/CXR-ABD-MSK")
        if row["on_ct_head"]:
            groups.append("CT Head")
        if row["on_ct_abdpel"]:
            groups.append("CT Abd/Pel")
        if not groups:
            groups.append("Not on Drafting")
        groups_by_npi[row["npi"]] = groups

    def pct(numerator: float, denominator: float) -> float | None:
        if not denominator:
            return None
        return numerator / denominator

    results = []
    for row in agg_rows:
        npi = row["npi"]
        dim_row = dim_by_npi.get(npi, {})
        results.append(
            RadSummaryStat(
                npi=npi,
                radiologist_name=dim_row.get("radiologist_name"),
                home_practice=dim_row.get("home_practice"),
                mosaic_go_live_date=row["mosaic_go_live_date"],
                total_mosaic_exams=row["total_mosaic_exams"],
                pct_mosaic=pct(row["total_mosaic_exams"], row["total_exams"]),
                pct_mammo=pct(row["mammo_mosaic"], row["mammo_total"]),
                total_xr_drafted=row["total_xr_drafted"],
                pct_xr_drafted=pct(row["total_xr_drafted"], row["draftable_xr"]),
                ct_head_drafted=row["ct_head_drafted"],
                pct_ct_head_drafted=pct(row["ct_head_drafted"], row["draftable_ct_head"]),
                ct_abdpel_drafted=row["ct_abdpel_drafted"],
                pct_ct_abdpel_drafted=pct(row["ct_abdpel_drafted"], row["draftable_ct_abdpel"]),
                ct_chest_drafted=row["ct_chest_drafted"],
                pct_ct_chest_drafted=pct(row["ct_chest_drafted"], row["draftable_ct_chest"]),
                captured_us=row["captured_us"],
                pct_captured=pct(row["captured_us"], row["us_capturable"]),
                drafting_groups=groups_by_npi.get(npi, ["Not on Drafting"]),
            )
        )
    return results
