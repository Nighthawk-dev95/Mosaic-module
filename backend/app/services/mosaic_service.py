from app.config import settings
from app.data.rpce_audit import rpce_status_counts
from app.db.databricks_client import run_query, run_query_one
from app.models.mosaic import (
    BlockerByPractice,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    CaptureOverview,
    CapturePracticeRollup,
    CaptureRadiologistItem,
    MosaicIntelligenceSnapshot,
    RadiologistRosterItem,
    RadSummaryStat,
    RpceTrendPoint,
    UtilizationPracticeRollup,
)

# Migrated 2026-10 onto edw_prod.enterprise_analytics/enterprise_analytics_ref (app-25js08's
# only granted schemas - edw_dev.bipa_analytics/mosaictechops and the raw Dataverse schema are
# unreachable under the deployed app's service principal, confirmed live via SHOW GRANTS ON
# SCHEMA). tbl_exam_inventory is the single exam-grain source of truth for volume/deployment/
# efficiency/capacity alike now; every function below still touches at most one heavy view per
# query and combines results in Python, same discipline as before.

# enterprise_analytics_ref.drafting_eligible_rpids_vw replaces the old hand-maintained
# CT_ABDPEL_DRAFT_CODES/CT_CHEST_DRAFT_CODES tuples - confirmed live: RPID152-3D/RAD2508 ->
# 'CT Abd/Pel', RPID249 -> 'CT Chest', RPID22 -> 'CT Head', matching the old lists exactly -
# and also carries 'US Capturable' as its own drafting_model value, replacing the old Mexproc
# capture-eligibility marker. This is a narrow, 7-category DRAFTING-ELIGIBILITY vocabulary
# (969 procedure codes) - correct for deployment/capture-eligibility joins (keyed on
# RPID_Procedure_Code), but NOT a substitute for the real clinical exam-category taxonomy -
# see _EXAM_CATEGORY_XWALK_VW below for that.
_DRAFTING_ELIGIBLE_VW = f"{settings.qualified}_ref.drafting_eligible_rpids_vw"

# Governed copy of edw_dev.bipa_analytics.exam_category_lookup_xwalk (see memory:
# exam_category_lookup_xwalk_reference.md) - migrated into enterprise_analytics 2026-10-15
# (tools/edw_fixes/012_migrate_exam_category_lookup_xwalk_to_enterprise_analytics.sql) after
# confirming the Efficiency pipeline's `mpcat` column was wrongly sourced from
# _DRAFTING_ELIGIBLE_VW above - that view's 7 narrow drafting-eligibility buckets don't cover
# real clinical categories like 'Mammo Diagnostic' at all (confirmed live: zero matching rows),
# silently dropping most exams out of every category-scoped Efficiency query. This is the real,
# 26-category taxonomy (969 procedure codes) the original MER Current Method notebook's cell-0
# actually joins - on ParentRpt = RPID_parent_code, NOT RPID_Procedure_Code (confirmed live:
# joining on RPID_parent_code covers 79.2M of 88.1M exams since 2024-11-01, vs. near-zero
# coverage for categories like Mammo Diagnostic via the old drafting-eligibility source).
_EXAM_CATEGORY_XWALK_VW = f"{settings.qualified}.tbl_exam_category_lookup_xwalk"

# RPCE-sourced rows are identified the same way as before (Source_System_Code is still the
# raw column name on tbl_exam_inventory).
_RPCE_SOURCE_SYSTEMS_SQL = "'rpceMidwest', 'rpceSouthwest'"

# Both % RPCE measures in the source DAX model add a flat 0.02 (2 percentage points) to the
# ratio, with no comment explaining why - confirmed with the business owner this is an
# intentional, known adjustment to retain, not a leftover hack.
_RPCE_PCT_ADJUSTMENT = 0.02


def get_radiologist_roster(
    practice: str | None = None,
    subspecialty: str | None = None,
    deployment_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RadiologistRosterItem]:
    """Rebuilt directly from tbl_exam_inventory - dim_mosaic_radiologist no longer exists under
    this app's grants. One row per NPI that has ever read a Mosaic exam, aggregated from the
    exam fact itself rather than joined from a separate roster dimension - this also sidesteps
    a coverage gap in workday_workers_dsa_vw (NPI populated for only ~81% of employed
    physicians and ~5% of contingent physicians), which would silently drop real reading
    radiologists from a roster built as an INNER JOIN against it.

    The two practice columns are a HOME and a SITE, per the standing domain rule:
      - provider_local_practice_name_curr = the radiologist's HOME PRACTICE. This is also what
        PBI calls the TEAM - the two names are synonyms for one column, not two concepts.
        Single-valued per NPI (max 1 distinct across all 2,875 Mosaic-reading NPIs, measured
        2026-10-24), so MAX() over it is exact. It is what home_practice and current_team both
        carry, and Local Region buckets it - utils/localRegion.ts is keyed on the Team.
      - managing_local_practice_name_curr = the SITE the rad travelled to and read at. This is
        what PBI calls the PRACTICE. It is an attribute of the EXAM, so it is multi-valued by
        design: 1,231 NPIs (43%) read at more than one site and some at as many as 70.

    That asymmetry is why they are computed differently. There is no single managing value to
    return for a rad, so MAX() over it would hand back whichever site name happens to sort last
    out of 70 - a real string, wrong, and unfalsifiable by eye. primary_site is instead the site
    the rad reads at MOST by exam count, with site_count alongside it so the other sites are
    visible rather than silently collapsed. Read it as "where this rad mostly works", never as
    an identity: for the long tail the primary site is only 12-25% of their volume, and the
    cube's parent_practice (plan SSB) is the structural fix, not this field.

    The `practice` argument filters on the managing column to match what PBI names it, i.e.
    "rads who read at this site", which is deliberately a different question from "rads whose
    home practice is this".

    deployment_status/deployment_launch_group stay None. The literal rollout-cohort fields lived
    only in the raw Dataverse rad_onboarding table and have no column-for-column equivalent
    here, though a real drafting deployment lifecycle (consent -> training -> AD group ->
    enabled) IS reachable via dynamics_rad_drafting_enablement_vw; wiring it up is the
    Deployment domain's job, not this roster's. capture_enabled is an empirical proxy (has this
    NPI ever captured a US/BD exam), mirroring the same proxy pattern EDW's own
    rad_drafting_enabled_flag uses for drafting enablement - sound in one direction only."""
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))

    # Split deliberately: `base_clauses` scopes which exams count toward a radiologist's
    # primary site, `row_clauses` scopes which radiologists come back. Folding the practice
    # filter into both would make primary_site echo whatever was filtered on, so every rad
    # would appear to mainly work at the filtered site even where it is 2% of their volume.
    base_clauses = ["mosaic_read_flag = true"]
    row_clauses: list[str] = []
    params: dict[str, object] = {}
    if practice:
        row_clauses.append("managing_local_practice_name_curr = %(practice)s")
        params["practice"] = practice
    if subspecialty:
        base_clauses.append("provider_primary_subspecialty_curr = %(subspecialty)s")
        params["subspecialty"] = subspecialty
    if deployment_status:
        # No source column exists for this any more - any filter value can never match.
        row_clauses.append("1 = 0")

    base_where = f"WHERE {' AND '.join(base_clauses)}"
    row_where = f"WHERE {' AND '.join(base_clauses + row_clauses)}"

    rows = run_query(
        f"""
        WITH rad AS (
          SELECT
            reading_provider_npi AS npi,
            MAX(reading_provider_name_full) AS radiologist_name,
            MAX(provider_primary_subspecialty_curr) AS working_subspecialty,
            -- The rad's home practice. Safe as MAX: provider_local_practice_name_curr is
            -- single-valued per NPI (verified live 2026-10-24 - max 1 distinct value across
            -- all 2,875 reading NPIs), so this is exact, not a guess.
            MAX(provider_local_practice_name_curr) AS current_team,
            SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) AS reporting_cases_read,
            SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) AS total_drafting_cases,
            MAX(CASE WHEN exam_Modality_Code IN ('US', 'BD') AND mosaic_draft_flag THEN 1 ELSE 0 END) = 1 AS capture_enabled
          FROM {settings.qualified}.tbl_exam_inventory
          {row_where}
          GROUP BY reading_provider_npi
        ),
        -- managing_local_practice_name_curr is the exam SITE, so it is per-exam and multi-valued
        -- per rad by design: 43% read at more than one site and some at as many as 70. Pick the
        -- site they read at most, not MAX() - which returns whichever name sorts last.
        site_volume AS (
          SELECT
            reading_provider_npi AS npi,
            managing_local_practice_name_curr AS site_name,
            COUNT(*) AS exams
          FROM {settings.qualified}.tbl_exam_inventory
          {base_where}
            AND managing_local_practice_name_curr IS NOT NULL
          GROUP BY reading_provider_npi, managing_local_practice_name_curr
        ),
        primary_site AS (
          SELECT npi, site_name, n_sites
          FROM (
            SELECT
              npi,
              site_name,
              -- site_name ASC only breaks exact volume ties, so the roster is stable between
              -- refreshes instead of flickering between two equally-read sites.
              ROW_NUMBER() OVER (PARTITION BY npi ORDER BY exams DESC, site_name ASC) AS rn,
              -- Carried through so the UI can show "+N more" rather than implying the primary
              -- site is the whole story - it is as little as 12% of volume in the long tail.
              COUNT(*) OVER (PARTITION BY npi) AS n_sites
            FROM site_volume
          )
          WHERE rn = 1
        )
        SELECT
          r.npi,
          r.radiologist_name,
          -- home_practice and current_team are the same column on purpose: the rad's home
          -- practice IS what PBI labels Team. Kept as two fields only because downstream
          -- consumers (Radiologist Lookup, Local Region bucketing) read them under both names.
          r.current_team AS home_practice,
          r.working_subspecialty,
          CAST(NULL AS STRING) AS deployment_status,
          CAST(NULL AS STRING) AS deployment_launch_group,
          r.current_team,
          s.site_name AS primary_site,
          s.n_sites AS site_count,
          r.reporting_cases_read,
          r.total_drafting_cases,
          r.capture_enabled
        FROM rad r
        LEFT JOIN primary_site s ON r.npi = s.npi
        ORDER BY r.radiologist_name
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
          provider_local_practice_name_curr                                              AS practice,
          COUNT(*)                                                                       AS total_exams,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END)                              AS mosaic_exams,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)        AS pct_mosaic,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END)                             AS drafting_exams,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)       AS pct_drafting,
          SUM(CASE WHEN exam_Modality_Code = 'US' AND mosaic_draft_flag THEN 1 ELSE 0 END) AS capture_exams,
          SUM(CASE WHEN exam_Modality_Code = 'MG' THEN 1 ELSE 0 END)                     AS mammo_exams,
          SUM(CASE WHEN exam_Modality_Code = 'MG' AND mosaic_read_flag THEN 1 ELSE 0 END) AS mammo_mosaic_exams,
          SUM(CASE WHEN exam_Modality_Code = 'MG' AND mosaic_read_flag THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN exam_Modality_Code = 'MG' THEN 1 ELSE 0 END), 0)       AS pct_mammo_mosaic,
          COUNT(DISTINCT CASE WHEN mosaic_read_flag THEN reading_provider_npi END)        AS rads_live,
          COUNT(DISTINCT CASE WHEN mosaic_draft_flag THEN reading_provider_npi END)       AS rads_drafting
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE CAST(final_datetime AS DATE) BETWEEN CURRENT_DATE - {safe_days} AND CURRENT_DATE
        GROUP BY provider_local_practice_name_curr
        ORDER BY total_exams DESC
        """
    )
    return [UtilizationPracticeRollup(**row) for row in rows]


# tbl_mosaic_shift_utilization is a governed snapshot in enterprise_analytics (NOT a live view) -
# migrated from edw_dev.bipa_analytics.presentation_deneb_vw (joined to tbl_exam_inventory for
# mosaic_read_flag/mosaic_draft_flag) because the deployed app's service principal cannot be
# granted edw_dev access (same wall _MVP_RAD_ONBOARDING_VW already hit - see
# tools/edw_fixes/014_migrate_shift_utilization_to_enterprise_analytics.sql for the full
# rationale and the exact CTAS/refresh SQL). Point-in-time snapshot of a rolling 90-day window as
# of the last migration run, not live - re-run that script's INSERT OVERWRITE block to refresh.
# utilization_pct/pct_mosaic_read/pct_ai_drafted are already fractions (0-1) in this table.
_SHIFT_UTILIZATION_TBL = f"{settings.qualified}.tbl_mosaic_shift_utilization"


def get_shift_utilization_by_radiologist() -> list[dict]:
    return run_query(f"SELECT * FROM {_SHIFT_UTILIZATION_TBL}")


# mosaic_drafting_metric_vw is a governed Databricks Metric View (confirmed live) - its
# measure-typed columns require MEASURE(col) in SELECT, bare column references raise
# METRIC_VIEW_MISSING_MEASURE_FUNCTION.
_DRAFTING_METRIC_VW = f"{settings.qualified}.mosaic_drafting_metric_vw"


# (blocker label, measure name) - mosaic_drafting_metric_vw's own binding documentation (Aura
# C2) requires "Drafting Opportunity (Workflow)" to always be shown beside "...(Enrollment)"'s
# 5-way split, never one without the other - this list carries both.
_DRAFTING_BLOCKER_MEASURES = [
    ("Workflow (drafted it could have)", "Drafting Opportunity (Workflow)"),
    ("Rad Declined", "Rad not enabled - Rad declined"),
    ("Ops Declined", "Rad not enabled - Ops declined"),
    ("Consent Sent, Not Signed", "Rad not enabled - Consent sent, not signed"),
    ("Consented, Awaiting Enablement", "Rad not enabled - Consented, awaiting enablement"),
    ("No Enrollment Record", "Rad not enabled - No enrollment record"),
]


def get_drafting_blockers_by_practice() -> list[BlockerByPractice]:
    """Replaces vw_drafting_npi_bridge's per-NPI BlockerLabel (no longer reachable) with
    mosaic_drafting_metric_vw's governed opportunity decomposition, grouped by practice.
    "Practice not enabled for model" is deliberately excluded here (it sits outside the
    draftable denominator by construction, a rollout question not an engagement one - see
    get_rollout_blockers_by_practice-equivalent note in the metric view's own column comment)
    and reported as its own blocker below instead of mixed into this list."""
    measures_sql = ",\n          ".join(f"MEASURE(`{measure}`) AS m{i}" for i, (_, measure) in enumerate(_DRAFTING_BLOCKER_MEASURES))
    rows = run_query(
        f"""
        SELECT
          provider_local_practice_name AS practice,
          {measures_sql},
          MEASURE(`Practice not enabled for model`) AS practice_not_enabled
        FROM {_DRAFTING_METRIC_VW}
        GROUP BY provider_local_practice_name
        """
    )
    result: list[BlockerByPractice] = []
    for row in rows:
        for i, (label, _) in enumerate(_DRAFTING_BLOCKER_MEASURES):
            count = row.get(f"m{i}") or 0
            if count:
                result.append(BlockerByPractice(practice=row["practice"], blocker=label, count=int(count)))
        practice_not_enabled = row.get("practice_not_enabled") or 0
        if practice_not_enabled:
            result.append(
                BlockerByPractice(practice=row["practice"], blocker="Practice Not Enabled for Model", count=int(practice_not_enabled))
            )
    result.sort(key=lambda r: r.practice or "")
    return result


def get_ct_abdpel_blockers_by_practice() -> list[BlockerByPractice]:
    """vw_ct_abdpel_npi_bridge's BlockerLabel no longer exists - rebuilt from
    dynamics_rad_drafting_enablement_vw's per-NPI drafting_enabled_flag for the CT Abd Pelvis
    model, attributed to practice via tbl_exam_inventory's own provider_local_practice_name_curr
    (the enablement view itself carries no practice column)."""
    rows = run_query(
        f"""
        WITH roster AS (
          SELECT reading_provider_npi AS npi, MAX(provider_local_practice_name_curr) AS practice
          FROM {settings.qualified}.tbl_exam_inventory
          WHERE mosaic_read_flag = true
          GROUP BY reading_provider_npi
        )
        SELECT r.practice AS practice, COUNT(DISTINCT r.npi) AS count
        FROM roster r
        JOIN {settings.qualified}.dynamics_rad_drafting_enablement_vw en
          ON en.npi = CAST(r.npi AS STRING) AND en.drafting_model = 'CT Abd Pelvis'
        WHERE NOT en.drafting_enabled_flag AND r.practice IS NOT NULL
        GROUP BY r.practice
        ORDER BY r.practice
        """
    )
    return [BlockerByPractice(practice=row["practice"], blocker="Not Enabled", count=row["count"]) for row in rows]


# ===========================================================================================
# MER Current Method notebook, migrated onto tbl_exam_inventory (edw_gold/bipa_analytics are
# unreachable under this app's grants). Reimplements the notebook's 3-cell pipeline exactly:
# cell 0 (presentation_rpt_readtimeswith_draftingadjustedrt_tbl - LAG-based Adjusted_Read_Time_Sec),
# cell 1 (radiologist_metrics_minexams_rtupdated - 2-stdev-per-procedure Outliers flag,
# Baseline/Drafting/Reporting Period_Type), cell 2 (radiologist_metrics_optimized - per-
# procedure baseline efficiency and the Weighted_Baseline_Contrib_Excl join, including the
# `baseline_eff_excl <= 1.000` filter that scopes the whole pipeline).
#
# Two confirmed drops from the original notebook (both decided after live verification this
# session, see the migration plan): the linked-encounter proportional-split fix (depended on
# edw_gold.linked_exam_fact_vw; verified tbl_exam_inventory.Combined_Exam_Src_Id/
# exam_encounter_id do NOT capture the same linkage) - Adjusted_Read_Time_Sec here is the plain
# LAG formula only, which reintroduces the zero-floor bug on linked exam pairs the fix
# corrected. draft_finding_category (depended on aws_prod_report_signed_events, not in any
# granted schema) is dropped entirely - nothing downstream used it.
#
# RP_TBWU_25_adj (ref_tbwu_2025_tbl x model_ref_pos_vw ER/IP/OP adjustment) -> tbl_exam_inventory's
# own unassisted_tbwu_current (base_tbwu_current x setting_multiplier_value_current) - the same
# flat-rate-card x care-setting-adjustment concept, already computed upstream.
# exam_category_lookup_xwalk + us_capturable_eligible_rpids (mpcat, incl. 'US Capturable') ->
# enterprise_analytics_ref.drafting_eligible_rpids_vw.drafting_model (confirmed identical
# category values live).
#
# No CREATE privilege exists under this app's grants, so this CTE chain is recomputed inline
# by every function below rather than materialized once - the same per-function-independent-
# query cost the original 7 functions already paid against the (separately materialized)
# radiologist_metrics_optimized view.
_MER_EXCLUDED_TEST_NPIS_SQL = ", ".join(
    f"'{npi}'"
    for npi in (
        "1134233869", "1578529640", "1255305371", "1043457591", "1134169857", "1174919955",
        "1588690002", "1083662803", "1184859589", "1861695322", "1124331582", "1578728184",
        "1568705986", "1144482738", "1134395858",
    )
)

_MER_BASE_CTE_SQL = f"""
WITH mosaic_live_practices AS (
  SELECT DISTINCT provider_local_practice_name_curr AS practice
  FROM {settings.qualified}.tbl_exam_inventory
  WHERE mosaic_read_flag = true AND provider_local_practice_name_curr IS NOT NULL
),
qualified_radiologists AS (
  SELECT e.reading_provider_npi AS npi
  FROM {settings.qualified}.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.practice = e.provider_local_practice_name_curr
  WHERE NOT e.mosaic_read_flag AND NOT e.mosaic_draft_flag
    AND CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND CAST(e.reading_provider_npi AS STRING) NOT IN ({_MER_EXCLUDED_TEST_NPIS_SQL})
  GROUP BY e.reading_provider_npi
  HAVING COUNT(DISTINCT e.exam_id) >= 1000
),
raw_exams AS (
  SELECT
    e.exam_id, e.reading_provider_npi AS Physician_NPI,
    e.reading_provider_name_full AS radiologist_name,
    -- Fix 2 (Team vs Practice conflation) - provider_local_practice_name_curr is the
    -- radiologist's own home/float-pool TEAM (e.g. "SEAL Team" is cross-coverage, not a billing
    -- practice); managing_local_practice_name_curr is the real PRACTICE whose exams are being
    -- read, which is what "By Practice" reporting means business-wise. Confirmed live against
    -- edw_prod: 'SEAL Team' alone spans 66 distinct managing practices. See
    -- tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md. Team stays the join key for
    -- mosaic_live_practices/qualified_radiologists below (unchanged - "is this radiologist's own
    -- team live on Mosaic" is genuinely a Team question), only the exposed "Practice" field changes.
    e.provider_local_practice_name_curr AS Team,
    e.managing_local_practice_name_curr AS Practice,
    e.provider_primary_subspecialty_curr AS working_subspecialty,
    e.exam_Modality_Code AS Modality_Code,
    e.RPID_parent_code_description AS Parent_Procedure_name,
    x.Category AS mpcat,
    e.RPID_Procedure_Code,
    e.mosaic_read_flag, e.mosaic_draft_flag,
    CAST(e.final_datetime AS DATE) AS Exam_Date,
    e.unassisted_tbwu_current AS TBWU,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime,
    LAG(e.final_datetime) OVER (
      PARTITION BY e.reading_provider_npi, DATE(e.dictation_start_datetime)
      ORDER BY e.dictation_start_datetime, e.exam_id
    ) AS prev_final
  FROM {settings.qualified}.tbl_exam_inventory e
  JOIN mosaic_live_practices mlp ON mlp.practice = e.provider_local_practice_name_curr
  JOIN qualified_radiologists qr ON qr.npi = e.reading_provider_npi
  LEFT JOIN {_EXAM_CATEGORY_XWALK_VW} x ON x.ParentRpt = e.RPID_parent_code
  WHERE CAST(e.final_datetime AS DATE) >= DATE'2024-11-01'
    AND e.dictation_start_datetime IS NOT NULL
    AND e.dictation_end_datetime IS NOT NULL
    AND e.final_datetime IS NOT NULL
),
adjusted AS (
  SELECT *,
    -- Capped at 3600s (1h) - confirmed live (2026-10-15) that tbl_exam_inventory's
    -- dictation_end_datetime carries a meaningful tail of corrupted values (max raw
    -- duration observed: 48.5M seconds, ~18 months; ~9.6% of Mammo Diagnostic rows alone
    -- exceed 4 hours). Uncapped, these "stuck session" rows don't just inflate their own
    -- row - they poison the per-RPID_Procedure_Code AVG/STDDEV used below to classify
    -- Outliers, inflating the threshold so much that genuinely bad rows stop being flagged
    -- at all (same feedback-loop failure mode as the old ref_readtime_stats_by_procedure_code
    -- - see memory: upstream_readtime_island_bug.md). Capping here, before the outlier calc,
    -- fixes both problems at once.
    LEAST(3600, GREATEST(0, TIMESTAMPDIFF(SECOND,
      CASE WHEN prev_final IS NOT NULL AND prev_final > dictation_start_datetime THEN prev_final ELSE dictation_start_datetime END,
      CASE WHEN final_datetime < dictation_end_datetime THEN final_datetime ELSE dictation_end_datetime END
    ))) AS Adjusted_Read_Time_Sec
  FROM raw_exams
),
outlier_calc AS (
  SELECT *,
    CASE WHEN Adjusted_Read_Time_Sec > (
      AVG(Adjusted_Read_Time_Sec) OVER (PARTITION BY RPID_Procedure_Code)
      + 2 * STDDEV(Adjusted_Read_Time_Sec) OVER (PARTITION BY RPID_Procedure_Code)
    ) THEN 'Included' ELSE 'Excluded' END AS Outliers
  FROM adjusted
),
classified AS (
  SELECT *,
    CASE
      WHEN NOT mosaic_read_flag AND NOT mosaic_draft_flag THEN 'Baseline'
      WHEN mosaic_draft_flag THEN 'Drafting'
      WHEN mosaic_read_flag THEN 'Reporting'
      ELSE 'Unknown'
    END AS Period_Type
  FROM outlier_calc
)
"""

# cell 2's baseline-by-procedure join, as its own CTE suffix appended where needed - computes
# baseline_eff_excl/baseline_usbd_eff_excl (TBWU per MINUTE) per (NPI, Parent_Procedure_name)
# from Baseline-period, Outliers='Excluded' rows only, exactly as the notebook does.
_MER_BASELINE_CTE_SQL = """
, baseline_by_procedure AS (
  SELECT
    Physician_NPI, Parent_Procedure_name,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' THEN TBWU ELSE 0 END) AS baseline_tbwu_excl,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' THEN Adjusted_Read_Time_Sec ELSE 0 END) AS baseline_time_excl,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' AND Modality_Code IN ('US', 'BD') THEN TBWU ELSE 0 END) AS baseline_usbd_tbwu_excl,
    SUM(CASE WHEN Period_Type = 'Baseline' AND Outliers = 'Excluded' AND Modality_Code IN ('US', 'BD') THEN Adjusted_Read_Time_Sec ELSE 0 END) AS baseline_usbd_time_excl
  FROM classified
  GROUP BY Physician_NPI, Parent_Procedure_name
),
baseline_eff AS (
  SELECT
    Physician_NPI, Parent_Procedure_name,
    baseline_tbwu_excl / NULLIF(baseline_time_excl / 60.0, 0) AS baseline_eff_excl,
    baseline_usbd_tbwu_excl / NULLIF(baseline_usbd_time_excl / 60.0, 0) AS baseline_usbd_eff_excl
  FROM baseline_by_procedure
)
"""


def get_efficiency_matrix() -> list[dict]:
    """Fine-grained Efficiency source rows - one per (radiologist, practice, subspecialty,
    modality, parent procedure) - written to the dedicated SQLite efficiency_matrix table
    (see app/db/efficiency_store.py) rather than the generic JSON cache, since it's a large
    table at full grain. Every downstream Efficiency view (by-radiologist, by-practice, and
    "population efficiency" for whatever slice the user has filtered to) is derived from
    this one table via real indexed SQL instead of separate EDW queries.

    Eligibility (>=1000 baseline exams since 2024-11-01) and the `baseline_eff_excl <= 1.000`
    procedure filter are enforced inline here (see _MER_BASE_CTE_SQL/_MER_BASELINE_CTE_SQL) -
    the same two gates the original radiologist_metrics_optimized view enforced upstream."""
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + """
        SELECT
          c.Physician_NPI AS npi, MAX(c.radiologist_name) AS radiologist_name, c.Practice AS practice,
          c.working_subspecialty AS subspecialty, c.Modality_Code AS modality_code,
          c.Parent_Procedure_name AS parent_procedure_name,
          MAX(c.mpcat) AS exam_category,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_baseline_contrib,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_baseline_contrib,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.TBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN be.baseline_usbd_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        WHERE be.baseline_eff_excl <= 1.000
        GROUP BY c.Physician_NPI, c.Practice, c.working_subspecialty, c.Modality_Code, c.Parent_Procedure_name
        """
    )


def get_efficiency_trend_by_category() -> list[dict]:
    """Monthly efficiency trend, split by exam category - feeds both the "Mosaic Efficiency
    Over Time" chart (absolute TBWU/min) and the "Efficiency Change" chart (same data,
    rendered as % vs baseline instead) so no second EDW query is needed for the latter."""
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + """
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', c.Exam_Date) AS DATE) AS STRING) AS period,
          MAX(c.mpcat) AS exam_category,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.Physician_NPI END) AS reporting_rad_count,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS reporting_exam_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.Physician_NPI END) AS drafting_rad_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS drafting_exam_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.TBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN be.baseline_usbd_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        WHERE be.baseline_eff_excl <= 1.000
        GROUP BY DATE_TRUNC('MONTH', c.Exam_Date), c.mpcat
        ORDER BY period
        """
    )


# MVP (Mosaic Value Project) data, read from a governed copy of the Clinical Transformation
# team's own Dynamics-synced CRM table rather than approximated from EDW. Confirmed live via
# query_edw this session: rad_onboarding's own mvp_cohort/exclusion_reason/
# mvp_tbwus_9h_shift_may_jul_26/*_efficiency_change_* columns ARE the program's real tiering,
# exclusion taxonomy, and fixed-baseline + rolling efficiency-change figures - a strict upgrade
# over re-deriving a worse approximation of them in SQL (the old approach's own docstring
# admitted it couldn't see "Q3 go-live practice"/"Do Not Revisit" exclusions at all, since those
# only ever lived here). Reads tbl_mvp_rad_onboarding (enterprise_analytics), NOT the raw
# Dataverse table directly - confirmed live via SHOW GRANTS that this app's service principal
# can't reach the Dataverse schema (same access gap as the SEAL tables); see
# tools/edw_fixes/013_migrate_mvp_rad_onboarding_to_enterprise_analytics.sql for the migration
# that materializes a periodically-refreshed copy here. NPI/column renaming/the `500_dx_cases`
# quoting are already baked into that copy, so this read is a plain passthrough select.
_MVP_RAD_ONBOARDING_VW = f"{settings.qualified}.tbl_mvp_rad_onboarding"


def get_mvp_rad_onboarding() -> list[dict]:
    """Every radiologist the real MVP program has either actively tiered (mvp_cohort populated)
    or explicitly excluded (exclusion_reason populated) - the full program universe, so the UI
    can show both without a second query."""
    return run_query(f"SELECT * FROM {_MVP_RAD_ONBOARDING_VW}")


# ===========================================================================================
# MIR rebaseline notebook (mosaic_rebaseline_notebook (1) (1).py, the actual baseline-computer
# per tools/capacity_model/README.md - MIR New Updated Baselines.ipynb is a downstream
# consumer, not the source) migrated onto tbl_exam_inventory's QGenda shift-match fields,
# which collapse the old 18-join transform_rpt_vra_capacity_base_exam_leveltest_vw (edw_gold/
# bipa_analytics, unreachable under this app's grants) onto one governed table:
# scheduled_shift_id (Shift_No/Task_ID), scheduled_shift_start/end_datetime_utc (Schedule_Start/
# End_DateTime), scheduled_shift_location (replaces the old schedule_task_dim join + hand-rolled
# Onsite/Remote string-matching entirely), final_TBWU (RP_TBWU), unassisted_tbwu_current
# (adjusted_TBWU - replaces the ER/IP/OP-adjustment CASE/JOIN to procedure_metrics_hist_dim_vw +
# model_ref_place_of_service_classification_vw). Rad_Go_Live_date (legacy VRA view, unreachable)
# is replaced by Mosaic_go_live_date (ref_dsa_mosaic_rad_go_live_curr) per decision - the two
# concepts collapse into one column everywhere below.
#
# Deliberately does NOT collapse overlapping shift instances to one "winner" - confirmed
# business rule (see overlapping_shift_dedup_fix.md): each shift independently shows every
# exam in its own start/end window, including the portion that overlaps another shift. An
# earlier version of this rebuild picked the longest-duration shift per overlap and discarded
# the other's exams entirely - confirmed live to silently drop 1.1M+ exams across 1,235 NPIs,
# reintroducing exactly the "pick one winner" behavior already rejected and fixed in the old
# pipeline. Same 20%-utilization crossing-date baseline/current split, same excluded-practices
# list (whole NPI dropped if ANY shift ties to an excluded practice).
_CAPACITY_EXCLUDED_PRACTICES_SQL = ", ".join(
    f"'{p}'"
    for p in (
        "Matrix", "RP East Florida", "SEAL Team", "RP North Florida", "DRSRP",
        "Spec Ops Reserve", "RP Palm Beach", "PRA", "RP RAH",
    )
)

# Baselines Proxies.sql's own subspecialty list, used for the "% Specialized" similarity score.
_PROXY_SPECIALIZED_SUBSPECIALTIES_SQL = ", ".join(
    f"'{s}'"
    for s in (
        "ARAPROC", "BREAST", "BREASTIR", "MR Breast", "BREASTUS", "CARDIAC",
        "DEXA", "FLUORO", "GENERALNEURO", "Interventional", "MAMMODX",
        "MAMMOSCR", "MSKCT", "MSKMR", "NEURO", "NUCMED", "Pediatrics",
        "PET", "SPINE", "SPINEIR", "VASCULAR",
    )
)

# Fix 1 (read-time) + Fix 2 (Team vs Practice) - see
# tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md and tbl_capacity_shift_level_vw (edw_test) for
# the validated reference this was ported from. Both confirmed live against edw_prod before this
# change: tat_unread_to_final_minutes averages ~921 min (~15h, includes queue-wait) with a max of
# ~24M minutes (~45 years) - not read time; 'SEAL Team' (provider_local_practice_name_curr) spans
# 66 distinct managing_local_practice_name_curr values - Team and Practice are different things.
_CAPACITY_SHIFT_CTE_SQL = f"""
WITH shift_exams AS (
  SELECT
    e.exam_id,
    e.reading_provider_npi AS NPI,
    e.reading_provider_name_full AS Rad_name,
    e.provider_local_practice_name_curr AS team,
    e.managing_local_practice_name_curr AS localpractice,
    e.scheduled_shift_id AS Shift_No,
    e.scheduled_shift_task_name AS ShiftName,
    CAST(e.scheduled_shift_start_datetime_utc AS DATE) AS ShiftDate,
    e.scheduled_shift_start_datetime_utc AS Schedule_Start_DateTime,
    e.scheduled_shift_end_datetime_utc AS Schedule_End_DateTime,
    e.scheduled_shift_location AS shift_location,
    e.final_TBWU AS RP_TBWU,
    e.unassisted_tbwu_current AS adjusted_TBWU,
    e.estimated_wrvu AS Estimated_RVU,
    e.dictation_start_datetime, e.dictation_end_datetime, e.final_datetime,
    e.mosaic_read_flag, e.mosaic_draft_flag,
    e.exam_Modality_Code AS Modality_Code,
    e.exam_interventional_Ind,
    e.exam_subspecialty_code,
    e.Priority_Name,
    e.Source_System_Code AS source_system_code
  FROM {settings.qualified}.tbl_exam_inventory e
  WHERE e.scheduled_shift_id IS NOT NULL
    AND e.scheduled_shift_start_datetime_utc IS NOT NULL
    AND e.scheduled_shift_end_datetime_utc IS NOT NULL
    AND CAST(e.scheduled_shift_start_datetime_utc AS DATE) >= DATE'2024-10-01'
),
with_lag AS (
  SELECT *,
    LAG(final_datetime) OVER (
      PARTITION BY NPI, DATE(dictation_start_datetime)
      ORDER BY dictation_start_datetime, exam_id
    ) AS prev_final
  FROM shift_exams
),
with_read_time AS (
  -- Nullable, not filtered - a shift-attributed exam with no usable dictation timestamps still
  -- counts toward on_shift_cases/TBWU/case-mix, it just can't contribute to read time. Same LAG-
  -- based, 3600s-capped derivation _MER_BASE_CTE_SQL already uses correctly for Efficiency.
  SELECT *,
    CASE WHEN dictation_start_datetime IS NOT NULL AND dictation_end_datetime IS NOT NULL AND final_datetime IS NOT NULL
      THEN LEAST(3600, GREATEST(0, TIMESTAMPDIFF(SECOND,
        CASE WHEN prev_final IS NOT NULL AND prev_final > dictation_start_datetime THEN prev_final ELSE dictation_start_datetime END,
        CASE WHEN final_datetime < dictation_end_datetime THEN final_datetime ELSE dictation_end_datetime END
      )))
      ELSE NULL
    END AS adjusted_read_time_sec
  FROM with_lag
),
raw_shifts AS (
  SELECT
    e.NPI, MAX(e.Rad_name) AS Rad_name, MAX(e.team) AS team, MAX(e.localpractice) AS localpractice,
    e.ShiftDate, e.ShiftName, e.Shift_No AS Task_ID,
    ANY_VALUE(e.shift_location) AS shift_location,
    ANY_VALUE(e.Schedule_Start_DateTime) AS Schedule_Start_DateTime,
    ANY_VALUE(e.Schedule_End_DateTime) AS Schedule_End_DateTime,
    MAX(TIMESTAMPDIFF(MINUTE, e.Schedule_Start_DateTime, e.Schedule_End_DateTime)) / 60.0 AS no_hours,
    CAST(SUM(e.RP_TBWU) AS DECIMAL(10,2)) AS shift_TBWU,
    CAST(SUM(e.Estimated_RVU) AS DECIMAL(10,2)) AS shift_RVU,
    COUNT(*) AS shift_cases,
    CAST(SUM(e.adjusted_TBWU) AS DECIMAL(10,2)) AS shift_adj_TBWU,
    SUM(e.adjusted_read_time_sec) / 60.0 AS shift_read_minutes,
    -- Fix 4 (population match): the TBWU produced by *only* the exams that also contributed to
    -- shift_read_minutes. shift_TBWU above covers every exam on the shift, but SUM() skips NULLs
    -- so shift_read_minutes covers only exams with usable dictation timestamps. Dividing the
    -- former by the latter mixes two populations and inflates efficiency by ~1/coverage. Measured
    -- live 2026-10-24 over 2,213 radiologists since 2026-07-01, bucketed by coverage: the mixed
    -- ratio runs 39.079 -> 0.199 TBWU/min (196x) as coverage goes 0.6% -> 98%, while
    -- mixed_ratio * coverage stays flat at 0.16-0.23 - the signature of a pure 1/coverage
    -- artifact. This column keeps numerator and denominator on the same exams, which holds the
    -- rate at 0.149-0.233 (1.6x) across the same buckets. Use it for every TBWU-per-minute rate;
    -- shift_TBWU remains correct for totals and for per-exam rates like tbwu_per_exam.
    CAST(SUM(CASE WHEN e.adjusted_read_time_sec IS NOT NULL THEN e.RP_TBWU END) AS DECIMAL(10,2)) AS shift_TBWU_with_read_time,
    SUM(CASE WHEN e.adjusted_read_time_sec IS NOT NULL THEN 1 ELSE 0 END) AS exams_with_valid_read_time,
    MAX(CASE WHEN e.source_system_code IN ('rpceMidwest', 'rpceSouthwest') THEN 1 ELSE 0 END) AS is_rpce_source,
    try_divide(SUM(CASE WHEN e.mosaic_read_flag THEN 1 ELSE 0 END), COUNT(*)) AS mosaic_utilization_pct,
    SUM(CASE WHEN e.mosaic_read_flag THEN 1 ELSE 0 END) AS mosaic_cases,
    SUM(CASE WHEN e.mosaic_draft_flag THEN 1 ELSE 0 END) AS drafting_cases,
    SUM(CASE WHEN e.exam_interventional_Ind = 1 THEN 1 ELSE 0 END) AS interventional_cases,
    SUM(CASE WHEN e.exam_subspecialty_code IN ({_PROXY_SPECIALIZED_SUBSPECIALTIES_SQL}) THEN 1 ELSE 0 END) AS specialized_cases,
    SUM(CASE WHEN e.Modality_Code = 'CT' THEN 1 ELSE 0 END) AS ct_cases,
    SUM(CASE WHEN e.Modality_Code = 'CR' THEN 1 ELSE 0 END) AS xr_cases,
    SUM(CASE WHEN e.Modality_Code = 'US' THEN 1 ELSE 0 END) AS us_cases,
    SUM(CASE WHEN e.Modality_Code = 'MR' THEN 1 ELSE 0 END) AS mr_cases,
    SUM(CASE WHEN e.Modality_Code = 'NM' THEN 1 ELSE 0 END) AS nm_cases,
    SUM(CASE WHEN e.Modality_Code = 'PT' THEN 1 ELSE 0 END) AS pt_cases,
    SUM(CASE WHEN e.Modality_Code = 'MG' THEN 1 ELSE 0 END) AS mg_cases,
    SUM(CASE WHEN e.Modality_Code = 'IR' THEN 1 ELSE 0 END) AS ir_cases,
    SUM(CASE WHEN e.Modality_Code NOT IN ('CT', 'CR', 'US', 'MR', 'NM', 'PT', 'MG', 'IR') THEN 1 ELSE 0 END) AS other_modality_cases,
    SUM(CASE WHEN e.Priority_Name = 'ROUTINE' THEN 1 ELSE 0 END) AS routine_cases,
    SUM(CASE WHEN e.Priority_Name = 'STAT' THEN 1 ELSE 0 END) AS stat_cases,
    SUM(CASE WHEN e.Priority_Name = 'STROKE' THEN 1 ELSE 0 END) AS stroke_cases,
    SUM(CASE WHEN e.Priority_Name = 'TRAUMA' THEN 1 ELSE 0 END) AS trauma_cases,
    SUM(CASE WHEN e.Priority_Name NOT IN ('ROUTINE', 'STAT', 'STROKE', 'TRAUMA') THEN 1 ELSE 0 END) AS otherp_cases
  FROM with_read_time e
  GROUP BY e.NPI, e.ShiftDate, e.ShiftName, e.Shift_No
)
"""

# Crossing-date + Baseline/Current classification, appended where the Exact-baseline tier
# needs it (get_capacity_with_baseline/get_baseline_proxy_detail) - MVP/live-capacity functions
# below don't need this, they use raw_shifts directly.
_CAPACITY_CLASSIFIED_CTE_SQL = """
, crossing_dates AS (
  SELECT NPI, MIN(ShiftDate) AS mosaic_20pct_crossing_date
  FROM raw_shifts
  WHERE mosaic_utilization_pct >= 0.20
  GROUP BY NPI
),
classified_shifts AS (
  SELECT r.*, c.mosaic_20pct_crossing_date,
    CASE
      WHEN c.mosaic_20pct_crossing_date IS NULL THEN 'No Mosaic Crossing (Excluded)'
      WHEN r.ShiftDate < ADD_MONTHS(c.mosaic_20pct_crossing_date, -6) THEN 'Pre-Baseline (Excluded)'
      WHEN r.ShiftDate >= ADD_MONTHS(c.mosaic_20pct_crossing_date, -6) AND r.ShiftDate < c.mosaic_20pct_crossing_date THEN 'Baseline'
      ELSE 'Current'
    END AS period_label
  FROM raw_shifts r
  LEFT JOIN crossing_dates c ON r.NPI = c.NPI
)
"""


def get_efficiency_trend_by_practice_category() -> list[dict]:
    """Same as get_efficiency_trend_by_category but also grouped by Practice."""
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + """
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', c.Exam_Date) AS DATE) AS STRING) AS period,
          c.Practice AS practice,
          MAX(c.mpcat) AS exam_category,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN c.Physician_NPI END) AS reporting_rad_count,
          SUM(CASE WHEN c.Period_Type = 'Reporting' AND c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS reporting_exam_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_baseline_contrib,
          COUNT(DISTINCT CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN c.Physician_NPI END) AS drafting_rad_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS drafting_exam_count,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.TBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN be.baseline_usbd_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        WHERE be.baseline_eff_excl <= 1.000
        GROUP BY DATE_TRUNC('MONTH', c.Exam_Date), c.Practice, c.mpcat
        ORDER BY period
        """
    )


def get_mammo_screening_trend() -> list[dict]:
    """Monthly Mammo-Screening volume + efficiency-change, RP-wide and MVP-mammo-cohort-only in
    one query - feeds the Mammo Screening dashboard's two combo charts (bars=volume, line=
    efficiency change). Confirmed live (2026-10-20): RPID_parent_code_description carries
    SCREENING vs DIAGNOSTIC wording directly (e.g. "MAMMO BREAST SCREENING TOMOSYNTHESIS
    BILATERAL" vs "MAMMO BREAST DIAGNOSTIC..."), so this is the existing MER CTE chain filtered
    to Modality_Code='MG' AND Parent_Procedure_name LIKE '%SCREENING%' - no new raw column
    needed. Combines Reporting+Drafting Period_Types into one "Full Mosaic"-style efficiency
    figure (mammo screening isn't itself split by reporting-vs-drafting anywhere else in this
    app, matching the PDF's own un-split framing). The MVP-mammo cohort is joined straight from
    tbl_mvp_rad_onboarding (mvp_cohort LIKE '%(Mammo)%') rather than a hardcoded NPI list, so it
    stays current as that table is re-synced."""
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + f"""
        , mvp_mammo_npis AS (
          SELECT npi FROM {settings.qualified}.tbl_mvp_rad_onboarding WHERE mvp_cohort LIKE '%(Mammo)%'
        )
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', c.Exam_Date) AS DATE) AS STRING) AS period,
          SUM(CASE WHEN c.Outliers = 'Excluded' THEN 1 ELSE 0 END) AS screening_volume,
          SUM(CASE WHEN c.Outliers = 'Excluded' THEN c.TBWU ELSE 0 END) AS screening_tbwu,
          SUM(CASE WHEN c.Outliers = 'Excluded' THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS screening_time,
          SUM(CASE WHEN c.Outliers = 'Excluded' THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS screening_baseline_contrib,
          SUM(CASE WHEN c.Outliers = 'Excluded' AND mn.npi IS NOT NULL THEN 1 ELSE 0 END) AS mvp_mammo_screening_volume,
          SUM(CASE WHEN c.Outliers = 'Excluded' AND mn.npi IS NOT NULL THEN c.TBWU ELSE 0 END) AS mvp_mammo_screening_tbwu,
          SUM(CASE WHEN c.Outliers = 'Excluded' AND mn.npi IS NOT NULL THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS mvp_mammo_screening_time,
          SUM(CASE WHEN c.Outliers = 'Excluded' AND mn.npi IS NOT NULL THEN be.baseline_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS mvp_mammo_screening_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        LEFT JOIN mvp_mammo_npis mn ON mn.npi = c.Physician_NPI
        WHERE be.baseline_eff_excl <= 1.000
          AND c.Modality_Code = 'MG' AND c.Parent_Procedure_name LIKE '%SCREENING%'
        GROUP BY DATE_TRUNC('MONTH', c.Exam_Date)
        ORDER BY period
        """
    )


def get_efficiency_trend_rp_avg() -> list[dict]:
    """Company-wide (ignores every filter) monthly efficiency, for the two "RP Avg" reference
    lines - Drafting Only and Full Mosaic (no RP Avg for Reporting/Non-Drafted, per spec).
    No baseline-contrib needed here, so this skips the cell-2 join entirely."""
    return run_query(
        _MER_BASE_CTE_SQL
        + """
        SELECT
          CAST(CAST(DATE_TRUNC('MONTH', Exam_Date) AS DATE) AS STRING) AS period,
          SUM(CASE WHEN Period_Type = 'Reporting' AND Outliers = 'Excluded' THEN TBWU ELSE 0 END) AS reporting_tbwu,
          SUM(CASE WHEN Period_Type = 'Reporting' AND Outliers = 'Excluded' THEN Adjusted_Read_Time_Sec ELSE 0 END) AS reporting_time,
          SUM(CASE WHEN Period_Type = 'Drafting' AND Outliers = 'Excluded' THEN TBWU ELSE 0 END) AS drafting_tbwu,
          SUM(CASE WHEN Period_Type = 'Drafting' AND Outliers = 'Excluded' THEN Adjusted_Read_Time_Sec ELSE 0 END) AS drafting_time
        FROM classified
        GROUP BY DATE_TRUNC('MONTH', Exam_Date)
        ORDER BY period
        """
    )


def get_capture_efficiency_trend_by_practice(granularity: str) -> list[dict]:
    """Same shape as get_efficiency_trend_by_practice_category but scoped to Drafting-period
    US/BD rows (the "Capture" concept) with no exam_category dimension - capture efficiency
    isn't broken out by category anywhere else in this app."""
    trunc = "WEEK" if granularity == "week" else "MONTH"
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + f"""
        SELECT
          CAST(CAST(DATE_TRUNC('{trunc}', c.Exam_Date) AS DATE) AS STRING) AS period,
          c.Practice AS practice,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.TBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN be.baseline_usbd_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        WHERE be.baseline_eff_excl <= 1.000
        GROUP BY DATE_TRUNC('{trunc}', c.Exam_Date), c.Practice
        ORDER BY period
        """
    )


def get_capture_efficiency_trend_by_radiologist(granularity: str) -> list[dict]:
    trunc = "WEEK" if granularity == "week" else "MONTH"
    return run_query(
        _MER_BASE_CTE_SQL
        + _MER_BASELINE_CTE_SQL
        + f"""
        SELECT
          CAST(CAST(DATE_TRUNC('{trunc}', c.Exam_Date) AS DATE) AS STRING) AS period,
          c.Physician_NPI AS npi,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.TBWU ELSE 0 END) AS capture_tbwu,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_time,
          SUM(CASE WHEN c.Period_Type = 'Drafting' AND c.Outliers = 'Excluded' AND c.Modality_Code IN ('US', 'BD') THEN be.baseline_usbd_eff_excl * c.Adjusted_Read_Time_Sec ELSE 0 END) AS capture_baseline_contrib
        FROM classified c
        JOIN baseline_eff be ON be.Physician_NPI = c.Physician_NPI AND be.Parent_Procedure_name = c.Parent_Procedure_name
        WHERE be.baseline_eff_excl <= 1.000
        GROUP BY DATE_TRUNC('{trunc}', c.Exam_Date), c.Physician_NPI
        ORDER BY period
        """
    )


# Below this read-time coverage, utilization is not a weak signal - it is a wrong one, and in a
# knowable direction. Its numerator (shift_read_minutes) only counts exams with usable dictation
# timestamps; its denominator (scheduled hours) counts the whole shift, and unlike efficiency
# there is no "covered subset" of a schedule to match it against. So reported utilization is
# understated by roughly the coverage fraction: at 50% coverage it reads half the truth, and the
# LEAST(..., 1.0) cap this used to carry did worse than hide it. Spark's LEAST *skips* NULLs, so
# when a slice has zero exams with read time - shift_read_minutes NULL - LEAST(NULL / hours, 1.0)
# collapsed to 1.0 and the slice rendered as a perfect 100% utilization. Measured live 2026-10-24
# against the then-deployed build: Boca (5,783 shifts / 341,068 exams) and Bethesda (4,597 /
# 299,725) both have exams_with_valid_read_time = 0 and both reported 100.00%. At the other end
# RASF, at 0.055% coverage, reported 0.02%.
# Neither number means anything. 0.75 is the measured bucket boundary (live 2026-10-24): 2,022 of
# 2,213 radiologists sit above it at ~98% coverage, so this suppresses ~8.6% of radiologists - the
# ones whose number is wrong by a third or more - and leaves the enterprise figure untouched. At
# practice grain the bite is larger: 20 of 84 practices, 22.5M of 72.3M exams. That is the point -
# those are the practices whose utilization is currently fiction. Null it out rather than ship a
# distorted number the UI would have to explain; every consumer (tables, AI hover cards, exports) then
# inherits the suppression, and the raw coverage % is still rendered beside it so the user sees
# why. Same discipline as _MIN_RELIABLE_BASELINE_TBWU_PER_HOUR in cache_service.py.
_MIN_READ_TIME_COVERAGE = 0.75


def _gated_utilization_sql(read_minutes: str, hours: str, covered: str, cases: str) -> str:
    """"% of scheduled shift time spent actively reading" - suppressed below
    _MIN_READ_TIME_COVERAGE and capped at 100%, without LEAST().

    LEAST() is the wrong cap here, and was the bug: Spark's LEAST *skips* NULL arguments
    instead of propagating them, so LEAST(NULL, 1.0) is 1.0 and a slice with no read time at
    all capped to a flawless 100%. The nested CASE propagates - a NULL ratio is not > 1.0, so
    it falls through to ELSE and stays NULL. That makes the cap correct on its own terms
    rather than only correct because the coverage gate in front of it happens to exclude the
    NULL cases; the gate is a reporting decision, and a reporting decision must not be the
    only thing standing between a NULL and a fabricated 100%.

    Every utilization this module emits goes through here, so the two cannot drift apart.
    """
    ratio = f"try_divide({read_minutes}, {hours} * 60.0)"
    return (
        f"CASE WHEN try_divide({covered}, {cases}) >= {_MIN_READ_TIME_COVERAGE}"
        f" THEN CASE WHEN {ratio} > 1.0 THEN 1.0 ELSE {ratio} END END"
    )


# utilization_*_pct is "% of scheduled shift time spent actively reading" (read-time minutes
# / scheduled minutes, capped at 100%); efficiency_*_per_min is TBWU per read-minute. Both old
# RVU/RPWU variants collapse onto the same one real rate here (same redundancy the old view's
# own columns had, confirmed identical per that function's original comment) since
# tbl_exam_inventory gives one TBWU-based numerator, not two. baseline_rvu/baseline_rpwu/
# baseline_rvu_per_hour are None here - the live/actual-capacity view this used to read also
# had these mostly NULL (8.6% coverage, per prior research); the real baseline lives in
# get_capacity_with_baseline below, which recomputes it properly rather than trusting this
# column. adjustment_rvu/adjustment_tbwu (a QGenda shift-credit-adjustment concept) has no
# reachable source under this app's grants - always 0.
_CAPACITY_MEASURES_SQL = f"""
  COUNT(1)                                                                AS total_shifts,
  SUM(no_hours)                                                           AS total_hours,
  SUM(shift_RVU)                                                         AS capacity_rvu,
  SUM(shift_TBWU)                                                        AS capacity_rpwu,
  CAST(NULL AS DOUBLE)                                                    AS baseline_rvu,
  CAST(NULL AS DOUBLE)                                                    AS baseline_rpwu,
  -- Suppressed below _MIN_READ_TIME_COVERAGE - see the constant for why a low-coverage
  -- utilization is wrong rather than merely uncertain. NULL renders as "-" in the UI.
  {_gated_utilization_sql("SUM(shift_read_minutes)", "SUM(no_hours)", "SUM(exams_with_valid_read_time)", "SUM(shift_cases)")} AS utilization_rvu_pct,
  {_gated_utilization_sql("SUM(shift_read_minutes)", "SUM(no_hours)", "SUM(exams_with_valid_read_time)", "SUM(shift_cases)")} AS utilization_rpwu_pct,
  -- Numerator is the coverage-matched TBWU (see raw_shifts), NOT shift_TBWU - dividing
  -- full-population TBWU by covered-only read minutes inflates this by ~1/coverage.
  SUM(shift_TBWU_with_read_time) / NULLIF(SUM(shift_read_minutes), 0)    AS efficiency_rvu_per_min,
  SUM(shift_TBWU_with_read_time) / NULLIF(SUM(shift_read_minutes), 0)    AS efficiency_rpwu_per_min,
  SUM(shift_RVU) / NULLIF(SUM(no_hours), 0)                              AS capacity_rvu_per_hour,
  CAST(NULL AS DOUBLE)                                                    AS baseline_rvu_per_hour,
  SUM(shift_cases)                                                       AS on_shift_cases,
  SUM(mosaic_cases)                                                      AS mosaic_cases,
  SUM(drafting_cases)                                                    AS drafting_cases,
  SUM(mosaic_cases) / NULLIF(SUM(shift_cases), 0)                        AS pct_mosaic,
  SUM(drafting_cases) / NULLIF(SUM(shift_cases), 0)                      AS pct_drafting,
  SUM(shift_RVU) / NULLIF(SUM(shift_cases), 0)                           AS avg_rvu_per_case,
  SUM(ct_cases)                                                          AS ct_cases,
  SUM(xr_cases)                                                          AS xr_cases,
  SUM(us_cases)                                                          AS us_cases,
  SUM(mr_cases)                                                          AS mr_cases,
  SUM(ir_cases)                                                          AS ir_cases,
  CAST(0 AS DOUBLE)                                                       AS adjustment_rvu,
  CAST(0 AS DOUBLE)                                                       AS adjustment_tbwu,
  -- Coverage varies enormously by practice/radiologist (confirmed live: as low as ~0% to 66%+)
  -- independent of Is RPCE Source alone - always check this before trusting Efficiency/
  -- Utilization above for a given slice. See tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md.
  SUM(exams_with_valid_read_time) / NULLIF(SUM(shift_cases), 0)          AS pct_exams_with_valid_read_time,
  SUM(CASE WHEN is_rpce_source = 1 THEN shift_cases ELSE 0 END) / NULLIF(SUM(shift_cases), 0) AS pct_shifts_rpce_source
"""


def get_capacity_by_radiologist(limit: int = 500, offset: int = 0) -> list[CapacityRadiologistItem]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    rows = run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + f"""
        SELECT
          NPI AS npi, MAX(Rad_name) AS radiologist_name, MAX(team) AS team, MAX(localpractice) AS practice,
          ARRAY_JOIN(SORT_ARRAY(COLLECT_SET(ShiftName)), ', ') AS shift_names,
          {_CAPACITY_MEASURES_SQL}
        FROM raw_shifts
        GROUP BY NPI
        ORDER BY radiologist_name
        LIMIT {safe_limit} OFFSET {safe_offset}
        """
    )
    return [CapacityRadiologistItem(**row) for row in rows]


def get_capacity_by_practice() -> list[CapacityPracticeRollup]:
    rows = run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + f"""
        SELECT
          localpractice AS practice,
          {_CAPACITY_MEASURES_SQL}
        FROM raw_shifts
        WHERE localpractice IS NOT NULL
        GROUP BY localpractice
        ORDER BY practice
        """
    )
    return [CapacityPracticeRollup(**row) for row in rows]


# (output_name, agg_func, source_column) - source_column ignored for COUNT. Used to build
# get_radiologist_scorecard's SELECT below programmatically: 19 metrics x 7 Top-N windows
# would be ~140 near-identical hand-written expressions otherwise (every other query in this
# file is deliberately literal SQL, but that convention stops paying off at this repetition
# factor). Plain counts/sums only - the 3 RATE metrics (efficiency/utilization/avg-units-per-
# shift) are built separately below as SUM(numerator)/SUM(denominator), not AVG here, see
# _scorecard_window_sql's own comment for why.
_SCORECARD_METRICS: list[tuple[str, str, str]] = [
    ("shifts_worked", "COUNT", "1"),
    ("case_count", "SUM", "cases"),
    ("ct_cases", "SUM", "ct_cases"),
    ("xr_cases", "SUM", "xr_cases"),
    ("us_cases", "SUM", "us_cases"),
    ("mr_cases", "SUM", "mr_cases"),
    ("nm_cases", "SUM", "nm_cases"),
    ("pt_cases", "SUM", "pt_cases"),
    ("mg_cases", "SUM", "mg_cases"),
    ("ir_cases", "SUM", "ir_cases"),
    ("other_modality_cases", "SUM", "other_modality_cases"),
    ("routine_cases", "SUM", "routine_cases"),
    ("stat_cases", "SUM", "stat_cases"),
    ("stroke_cases", "SUM", "stroke_cases"),
    ("trauma_cases", "SUM", "trauma_cases"),
    ("otherp_cases", "SUM", "otherp_cases"),
]


def _scorecard_window_sql(window: int | None) -> str:
    suffix = f"top{window}" if window is not None else "all"
    cond = f"shift_rank <= {window}" if window is not None else None

    def when(col: str) -> str:
        return f"CASE WHEN {cond} THEN {col} END" if cond else col

    parts = []
    for name, agg, col in _SCORECARD_METRICS:
        if agg == "COUNT":
            expr = f"COUNT(CASE WHEN {cond} THEN 1 END)" if cond else "COUNT(1)"
        else:
            expr = f"{agg}({when(col)})"
        parts.append(f"{expr} AS {name}_{suffix}")

    # Fix 3 - rate rollup: SUM(numerator)/SUM(denominator) across the window's shifts, never
    # AVG(per-shift-already-divided-rate) - averaging a pre-divided rate across shifts of
    # different lengths/volumes silently mis-weights them. See
    # tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md's "Rate rollup" finding; same discipline
    # _CAPACITY_MEASURES_SQL already uses for the by-radiologist/by-practice views.
    parts.append(f"CAST(NULL AS DOUBLE) AS addl_capacity_per_shift_{suffix}")
    # Fix 4 - population match: the numerator is shift_TBWU_with_read_time, not shift_TBWU, so
    # it covers the same exams the denominator does. And utilization is suppressed below
    # _MIN_READ_TIME_COVERAGE. See raw_shifts and that constant for the measured evidence.
    parts.append(
        f"try_divide(SUM({when('shift_TBWU_with_read_time')}), SUM({when('shift_read_minutes')})) AS efficiency_{suffix}"
    )
    parts.append(
        _gated_utilization_sql(
            f"SUM({when('shift_read_minutes')})",
            f"SUM({when('no_hours')})",
            f"SUM({when('exams_with_valid_read_time')})",
            f"SUM({when('cases')})",
        )
        + f" AS shift_utilization_{suffix}"
    )
    parts.append(f"try_divide(SUM({when('shift_TBWU')}), SUM({when('no_hours')})) * 9 AS avg_units_per_shift_{suffix}")
    return ",\n          ".join(parts)


def get_radiologist_scorecard() -> list[dict]:
    """Case count, capacity/shift, and modality/priority mix (all Top-N variants) for every
    radiologist live on Mosaic, computed over their N most recent shifts since go-live
    (ref_dsa_mosaic_rad_go_live_curr.mosaic_drafting_go_live_date - replaces the old view's own
    Mosaic_go_live_date column). N is precomputed for every offered dropdown value
    (5/10/15/20/25/30/all) in one pass so the frontend never has to refetch when the user
    changes the N selector. Still returns the wide (one row per NPI, `_top5`/`_top10`/.../`_all`-
    suffixed columns) shape - cache_service.py unpivots this into the nested per-Top-N `metrics`
    list the API actually returns.

    addl_capacity_per_shift (capacity vs. a per-shift-type baseline) and efficiency/utilization
    "new" (vs. baseline) framing have no reachable baseline join at this grain without
    duplicating get_capacity_with_baseline's full Exact/Proxy pipeline here too - left as None/
    the raw (non-baseline-relative) rate respectively rather than fabricating a comparison."""
    window_sql = ",\n          ".join(_scorecard_window_sql(w) for w in (5, 10, 15, 20, 25, 30, None))
    return run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + f"""
        , go_live AS (
          SELECT reading_provider_npi AS npi, mosaic_drafting_go_live_date
          FROM {settings.qualified}.ref_dsa_mosaic_rad_go_live_curr
        ),
        ranked AS (
          SELECT
            r.NPI, r.Rad_name, r.team, r.localpractice AS practice,
            gl.mosaic_drafting_go_live_date AS Mosaic_go_live_date,
            r.shift_TBWU, r.shift_TBWU_with_read_time, r.shift_read_minutes, r.no_hours,
            r.exams_with_valid_read_time,
            r.shift_cases AS cases,
            r.ct_cases, r.xr_cases, r.us_cases, r.mr_cases, r.nm_cases, r.pt_cases, r.mg_cases, r.ir_cases,
            r.other_modality_cases, r.routine_cases, r.stat_cases, r.stroke_cases, r.trauma_cases, r.otherp_cases,
            ROW_NUMBER() OVER (PARTITION BY r.NPI ORDER BY r.ShiftDate DESC) AS shift_rank
          FROM raw_shifts r
          JOIN go_live gl ON gl.npi = CAST(r.NPI AS STRING)
          WHERE gl.mosaic_drafting_go_live_date IS NOT NULL AND r.ShiftDate >= gl.mosaic_drafting_go_live_date
        )
        SELECT
          -- Fix 2 (Team vs Practice) at this grain: team is provider_local_practice_name_curr,
          -- practice is managing_local_practice_name_curr. These differ for cross-staffed rads
          -- (e.g. SEAL Team), and this SELECT used to report MAX(practice) under both labels -
          -- silently undoing the fix at the one grain a drill-down lands on.
          NPI AS npi, MAX(Rad_name) AS radiologist_name, MAX(team) AS team,
          MAX(practice) AS practice, CAST(MAX(Mosaic_go_live_date) AS STRING) AS mosaic_go_live_date,
          {window_sql}
        FROM ranked
        GROUP BY NPI
        """
    )


def get_mosaic_intelligence_snapshot() -> MosaicIntelligenceSnapshot:
    """rads_live_on_ai_drafting was previously corroborated against Dataverse AD-group dates
    (rad_onboarding) as a safeguard against counting pilot/test drafts - that raw Dataverse
    table is unreachable under this app's grants (confirmed via SHOW GRANTS), so this is
    simplified to "has drafted at least once in the window", same population tbl_exam_inventory
    itself would report. rads_capture_enabled uses the same empirical proxy as the roster's
    capture_enabled (has ever captured a US/BD exam), replacing rad_onboarding.capture_enabled."""
    volume_row = run_query_one(
        f"""
        SELECT
          COUNT(DISTINCT CASE WHEN mosaic_read_flag THEN reading_provider_npi END) AS rads_live_on_mosaic,
          COUNT(DISTINCT CASE WHEN exam_Modality_Code IN ('US', 'BD') AND mosaic_draft_flag
                              AND d.drafting_model IS NOT NULL THEN reading_provider_npi END) AS rads_live_on_capture,
          COUNT(DISTINCT CASE WHEN mosaic_draft_flag THEN reading_provider_npi END) AS rads_live_on_ai_drafting,
          COUNT(DISTINCT CASE WHEN exam_Modality_Code IN ('US', 'BD') AND mosaic_draft_flag
                              AND d.drafting_model IS NOT NULL THEN reading_provider_npi END) AS rads_capture_enabled,
          (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d
          ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE CAST(final_datetime AS DATE) >= '2025-04-01'
        """
    )

    rpce_counts = rpce_status_counts()
    return MosaicIntelligenceSnapshot(
        rads_live_on_mosaic=volume_row["rads_live_on_mosaic"] if volume_row else 0,
        rads_live_on_ai_drafting=volume_row["rads_live_on_ai_drafting"] if volume_row else 0,
        pct_rpce_reporting=volume_row["pct_rpce_reporting"] if volume_row else None,
        pct_rpce_drafting=volume_row["pct_rpce_drafting"] if volume_row else None,
        rads_live_on_capture=volume_row["rads_live_on_capture"] if volume_row else 0,
        rads_capture_enabled=volume_row["rads_capture_enabled"] if volume_row else 0,
        practices_fully_on_rpce=rpce_counts["Fully on RPCE"],
        practices_split_integration=rpce_counts["Split Integration"],
        practices_not_on_rpce=rpce_counts["Not on RPCE"],
    )


def get_mosaic_intelligence_by_practice() -> list[MosaicIntelligenceSnapshot]:
    """Same metrics as get_mosaic_intelligence_snapshot, widened by practice. rpce_status_counts()
    stays company-wide on every row (it's a hardcoded practice-status audit list, not an EDW
    aggregate, so there's nothing to widen)."""
    volume_rows = run_query(
        f"""
        SELECT
          e.provider_local_practice_name_curr AS practice,
          COUNT(DISTINCT CASE WHEN e.mosaic_read_flag THEN e.reading_provider_npi END) AS rads_live_on_mosaic,
          COUNT(DISTINCT CASE WHEN e.exam_Modality_Code IN ('US', 'BD') AND e.mosaic_draft_flag
                              AND d.drafting_model IS NOT NULL THEN e.reading_provider_npi END) AS rads_live_on_capture,
          COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN e.reading_provider_npi END) AS rads_live_on_ai_drafting,
          COUNT(DISTINCT CASE WHEN e.exam_Modality_Code IN ('US', 'BD') AND e.mosaic_draft_flag
                              AND d.drafting_model IS NOT NULL THEN e.reading_provider_npi END) AS rads_capture_enabled,
          (SUM(CASE WHEN e.mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN e.Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN e.mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN e.Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d
          ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY e.provider_local_practice_name_curr
        """
    )

    rpce_counts = rpce_status_counts()
    return [
        MosaicIntelligenceSnapshot(
            practice=row["practice"],
            rads_live_on_mosaic=row["rads_live_on_mosaic"],
            rads_live_on_ai_drafting=row["rads_live_on_ai_drafting"],
            pct_rpce_reporting=row["pct_rpce_reporting"],
            pct_rpce_drafting=row["pct_rpce_drafting"],
            rads_live_on_capture=row["rads_live_on_capture"],
            rads_capture_enabled=row["rads_capture_enabled"],
            practices_fully_on_rpce=rpce_counts["Fully on RPCE"],
            practices_split_integration=rpce_counts["Split Integration"],
            practices_not_on_rpce=rpce_counts["Not on RPCE"],
        )
        for row in volume_rows
        if row["practice"] is not None
    ]


def get_rpce_trend() -> list[RpceTrendPoint]:
    rows = run_query(
        f"""
        SELECT
          CAST(CAST(final_datetime AS DATE) AS STRING) AS period,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) AS mosaic_exam_ct,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) AS drafting_exam_ct,
          (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE CAST(final_datetime AS DATE) >= '2025-04-01'
        GROUP BY CAST(final_datetime AS DATE)
        ORDER BY period
        """
    )
    return [RpceTrendPoint(**row) for row in rows]


def get_rpce_trend_by_practice() -> list[RpceTrendPoint]:
    rows = run_query(
        f"""
        SELECT
          CAST(CAST(final_datetime AS DATE) AS STRING) AS period,
          provider_local_practice_name_curr AS practice,
          SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) AS mosaic_exam_ct,
          SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) AS drafting_exam_ct,
          (SUM(CASE WHEN mosaic_read_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_reporting,
          (SUM(CASE WHEN mosaic_draft_flag THEN 1 ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN Source_System_Code IN ({_RPCE_SOURCE_SYSTEMS_SQL}) THEN 1 ELSE 0 END), 0))
            + {_RPCE_PCT_ADJUSTMENT} AS pct_rpce_drafting
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE CAST(final_datetime AS DATE) >= '2025-04-01'
        GROUP BY CAST(final_datetime AS DATE), provider_local_practice_name_curr
        ORDER BY period
        """
    )
    return [RpceTrendPoint(**row) for row in rows]


def _get_capture_enabled_npis() -> list[int]:
    """Empirical proxy (has this NPI ever captured a US/BD exam), replacing
    rad_onboarding.capture_enabled='Yes' - that raw Dataverse table is unreachable under this
    app's grants. Sound in one direction only (having captured proves enablement; never having
    captured does not prove the reverse), same caveat as EDW's own rad_drafting_enabled_flag."""
    rows = run_query(
        f"""
        SELECT DISTINCT reading_provider_npi AS npi
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE exam_Modality_Code IN ('US', 'BD') AND mosaic_draft_flag
        """
    )
    return [int(row["npi"]) for row in rows]


def _npi_sql_list(npis: list[int]) -> str:
    return ", ".join(str(n) for n in npis) if npis else "-1"


def get_capture_overview() -> CaptureOverview:
    """Overall US+BD capture utilization (captured / capturable exams), both for all rads
    and for capture-enabled rads only. Efficiency fields are left None here - cache_service
    fills them in live from efficiency_store.aggregate(mode="capture"), the same machinery
    that already powers the existing "Capture Only" Efficiency mode, so this function has
    no reason to touch the efficiency pipeline at all."""
    enabled_sql = _npi_sql_list(_get_capture_enabled_npis())
    row = run_query_one(
        f"""
        SELECT
          SUM(CASE WHEN d.drafting_model IS NOT NULL THEN 1 ELSE 0 END) AS capturable_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS capturable_exams_enabled,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS captured_exams_enabled,
          COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN e.reading_provider_npi END) AS rads_live_on_capture
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE e.exam_Modality_Code IN ('US', 'BD') AND CAST(e.final_datetime AS DATE) >= '2025-04-01'
        """
    )
    capturable_all = (row["capturable_exams_all"] if row else 0) or 0
    captured_all = (row["captured_exams_all"] if row else 0) or 0
    capturable_enabled = (row["capturable_exams_enabled"] if row else 0) or 0
    captured_enabled = (row["captured_exams_enabled"] if row else 0) or 0
    return CaptureOverview(
        capturable_exams_all=capturable_all,
        captured_exams_all=captured_all,
        pct_captured_all=(captured_all / capturable_all) if capturable_all else None,
        capturable_exams_enabled=capturable_enabled,
        captured_exams_enabled=captured_enabled,
        pct_captured_enabled=(captured_enabled / capturable_enabled) if capturable_enabled else None,
        rads_live_on_capture=(row["rads_live_on_capture"] if row else 0) or 0,
        rads_capture_enabled=enabled_sql.count(",") + 1 if enabled_sql != "-1" else 0,
        capture_mosaic_tbwu_per_min=None,
        capture_baseline_tbwu_per_min=None,
        capture_pct_change_vs_baseline=None,
    )


def get_capture_by_practice() -> list[CapturePracticeRollup]:
    enabled_npis = _get_capture_enabled_npis()
    enabled_sql = _npi_sql_list(enabled_npis)
    rows = run_query(
        f"""
        SELECT
          e.provider_local_practice_name_curr AS practice,
          SUM(CASE WHEN d.drafting_model IS NOT NULL THEN 1 ELSE 0 END) AS capturable_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS capturable_exams_enabled,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS captured_exams_enabled,
          MIN(CASE WHEN e.mosaic_draft_flag THEN CAST(e.final_datetime AS DATE) END) AS enablement_date,
          COUNT(DISTINCT CASE WHEN e.mosaic_draft_flag THEN e.reading_provider_npi END) AS rads_live_on_capture
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE e.exam_Modality_Code IN ('US', 'BD') AND CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY e.provider_local_practice_name_curr
        """
    )
    roster_rows = run_query(
        f"""
        SELECT reading_provider_npi AS npi, MAX(provider_local_practice_name_curr) AS home_practice
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE mosaic_read_flag = true
        GROUP BY reading_provider_npi
        """
    )
    practice_by_npi = {row["npi"]: row["home_practice"] for row in roster_rows}
    enabled_counts: dict[str, int] = {}
    for npi in enabled_npis:
        practice = practice_by_npi.get(npi)
        if practice:
            enabled_counts[practice] = enabled_counts.get(practice, 0) + 1

    result = []
    for row in rows:
        if row["practice"] is None:
            continue
        capturable_all = row["capturable_exams_all"] or 0
        captured_all = row["captured_exams_all"] or 0
        capturable_enabled = row["capturable_exams_enabled"] or 0
        captured_enabled = row["captured_exams_enabled"] or 0
        result.append(
            CapturePracticeRollup(
                practice=row["practice"],
                capturable_exams_all=capturable_all,
                captured_exams_all=captured_all,
                pct_captured_all=(captured_all / capturable_all) if capturable_all else None,
                capturable_exams_enabled=capturable_enabled,
                captured_exams_enabled=captured_enabled,
                pct_captured_enabled=(captured_enabled / capturable_enabled) if capturable_enabled else None,
                rads_live_on_capture=row["rads_live_on_capture"] or 0,
                rads_capture_enabled=enabled_counts.get(row["practice"], 0),
                enablement_date=row["enablement_date"],
                # pct_change_since_enablement is filled in by cache_service, which cross-
                # references the monthly utilization trend cache for the baseline period.
                pct_change_since_enablement=None,
            )
        )
    return result


def get_capture_by_radiologist() -> list[CaptureRadiologistItem]:
    rows = run_query(
        f"""
        SELECT
          e.reading_provider_npi AS npi,
          MAX(e.reading_provider_name_full) AS radiologist_name,
          MAX(e.provider_local_practice_name_curr) AS practice,
          SUM(CASE WHEN d.drafting_model IS NOT NULL THEN 1 ELSE 0 END) AS capturable_exams,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_exams
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE e.exam_Modality_Code IN ('US', 'BD') AND CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY e.reading_provider_npi
        """
    )
    enabled_npis = set(_get_capture_enabled_npis())

    result = []
    for row in rows:
        npi = row["npi"]
        capturable = row["capturable_exams"] or 0
        captured = row["captured_exams"] or 0
        result.append(
            CaptureRadiologistItem(
                npi=npi,
                radiologist_name=row["radiologist_name"],
                practice=row["practice"],
                capture_enabled=npi in enabled_npis,
                capturable_exams=capturable,
                captured_exams=captured,
                pct_captured=(captured / capturable) if capturable else None,
            )
        )
    return result


def get_capture_utilization_trend_by_practice(granularity: str) -> list[dict]:
    trunc = "WEEK" if granularity == "week" else "MONTH"
    enabled_sql = _npi_sql_list(_get_capture_enabled_npis())
    return run_query(
        f"""
        SELECT
          CAST(CAST(DATE_TRUNC('{trunc}', e.final_datetime) AS DATE) AS STRING) AS period,
          e.provider_local_practice_name_curr AS practice,
          SUM(CASE WHEN d.drafting_model IS NOT NULL THEN 1 ELSE 0 END) AS capturable_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_exams_all,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS capturable_exams_enabled,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag AND e.reading_provider_npi IN ({enabled_sql}) THEN 1 ELSE 0 END) AS captured_exams_enabled
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE e.exam_Modality_Code IN ('US', 'BD') AND CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY DATE_TRUNC('{trunc}', e.final_datetime), e.provider_local_practice_name_curr
        ORDER BY period
        """
    )


def get_capture_utilization_trend_by_radiologist(granularity: str) -> list[dict]:
    trunc = "WEEK" if granularity == "week" else "MONTH"
    return run_query(
        f"""
        SELECT
          CAST(CAST(DATE_TRUNC('{trunc}', e.final_datetime) AS DATE) AS STRING) AS period,
          e.reading_provider_npi AS npi,
          SUM(CASE WHEN d.drafting_model IS NOT NULL THEN 1 ELSE 0 END) AS capturable_exams,
          SUM(CASE WHEN d.drafting_model IS NOT NULL AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS captured_exams
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code AND d.drafting_model = 'US Capturable'
        WHERE e.exam_Modality_Code IN ('US', 'BD') AND CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY DATE_TRUNC('{trunc}', e.final_datetime), e.reading_provider_npi
        ORDER BY period
        """
    )


def get_undrafted_analysis() -> list[dict]:
    """Draftable-but-not-drafted exam breakdown by reason - rebuilt from tbl_exam_inventory's
    own exam_draftable_flag/exam_not_draftable_reason ladder; examsnotdraftedbutdraftable_vw
    (built jointly with the Clinical Transformation team) no longer exists under this app's
    grants. team/site/exam_category ARE kept at this raw/cached
    grain (unlike before) so cache_service can filter by them - but this is at (week,
    practice, team, site, exam_category, category) grain, which is ~845K rows / 120MB+ for
    the full history. That's fine to cache server-side (SQLite, never re-queried live) but
    FAR too large to ever return whole over HTTP - cache_service.get_undrafted_analysis()
    filters by exam_category/site first, then collapses those two high-cardinality
    dimensions back down to the small (week, practice, team, category) shape the frontend
    chart actually needs before returning `list[UndraftedCategoryPoint]`. Returns raw dicts,
    not the Pydantic model, since the model no longer carries site/exam_category at all -
    those exist only as filter criteria, never as response fields.

    REBUILT (not a swap): examsnotdraftedbutdraftable_vw no longer exists under this app's
    grants. Rebuilt here from tbl_exam_inventory's own exam_draftable_flag/exam_not_draftable_reason
    ladder (confirmed finalized-exam, Mosaic-read-gated scope, same spirit as the old view) -
    the exact 8-category taxonomy the old view used was never fully documented in this app's own
    history, so this is a new, clearly-labeled category set built on the ladder's 5 precedence
    values (exam_not_read_on_mosaic/rpid_not_draftable/practice_rpid_not_in_program/
    rad_not_in_drafting/draftable) plus a Drafted/Not-Drafted split within "draftable", not a
    literal port.

    "Drafted" (category_sort_order 0) is included, not filtered out, so the frontend can
    compute each week's "% Undrafted" total as 1 - (Drafted / week total) - see
    UndraftedStackedChart, which hides the Drafted segment itself but needs it in the
    denominator.
    """
    rows = run_query(
        f"""
        SELECT
          CAST(DATE_TRUNC('WEEK', final_datetime) AS DATE) AS week_start,
          provider_local_practice_name_curr AS local_practice,
          provider_local_practice_name_curr AS team,
          Site_Name AS site,
          exam_subspecialty_code AS exam_category,
          CASE
            WHEN exam_draftable_flag AND mosaic_draft_flag THEN 'Drafted'
            WHEN exam_not_draftable_reason = 'rad_not_in_drafting' THEN 'Draftable - Rad Not Enrolled'
            WHEN exam_draftable_flag THEN 'Draftable - Not Drafted (Workflow)'
            WHEN exam_not_draftable_reason = 'practice_rpid_not_in_program' THEN 'Practice Not Enabled for Model'
            WHEN exam_not_draftable_reason = 'rpid_not_draftable' THEN 'Procedure Not Covered'
            ELSE 'Not Read on Mosaic'
          END AS category,
          CASE
            WHEN exam_draftable_flag AND mosaic_draft_flag THEN 0
            WHEN exam_not_draftable_reason = 'rad_not_in_drafting' THEN 1
            WHEN exam_draftable_flag THEN 2
            WHEN exam_not_draftable_reason = 'practice_rpid_not_in_program' THEN 3
            WHEN exam_not_draftable_reason = 'rpid_not_draftable' THEN 4
            ELSE 5
          END AS category_sort_order,
          COUNT(*) AS exam_count,
          SUM(final_TBWU) AS tbwu
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE Study_Status_Code = 'Final'
        GROUP BY
          DATE_TRUNC('WEEK', final_datetime), provider_local_practice_name_curr, Site_Name, exam_subspecialty_code,
          CASE
            WHEN exam_draftable_flag AND mosaic_draft_flag THEN 'Drafted'
            WHEN exam_not_draftable_reason = 'rad_not_in_drafting' THEN 'Draftable - Rad Not Enrolled'
            WHEN exam_draftable_flag THEN 'Draftable - Not Drafted (Workflow)'
            WHEN exam_not_draftable_reason = 'practice_rpid_not_in_program' THEN 'Practice Not Enabled for Model'
            WHEN exam_not_draftable_reason = 'rpid_not_draftable' THEN 'Procedure Not Covered'
            ELSE 'Not Read on Mosaic'
          END,
          CASE
            WHEN exam_draftable_flag AND mosaic_draft_flag THEN 0
            WHEN exam_not_draftable_reason = 'rad_not_in_drafting' THEN 1
            WHEN exam_draftable_flag THEN 2
            WHEN exam_not_draftable_reason = 'practice_rpid_not_in_program' THEN 3
            WHEN exam_not_draftable_reason = 'rpid_not_draftable' THEN 4
            ELSE 5
          END
        ORDER BY week_start, category_sort_order
        """
    )
    for row in rows:
        row["week_start"] = str(row["week_start"])
    return rows


def get_rad_summary_stats() -> list[RadSummaryStat]:
    """Drafteligiblecode-based CT Abd/Pel and CT Chest matching is now
    enterprise_analytics_ref.drafting_eligible_rpids_vw joined on RPID_Procedure_Code (same
    confirmed mapping used throughout this file); Mexproc is replaced by drafting_model =
    'US Capturable' on the same view."""
    agg_rows = run_query(
        f"""
        SELECT
          e.reading_provider_npi AS npi,
          MIN(CASE WHEN e.mosaic_read_flag THEN CAST(e.final_datetime AS DATE) END) AS mosaic_go_live_date,
          SUM(CASE WHEN e.mosaic_read_flag THEN 1 ELSE 0 END) AS total_mosaic_exams,
          COUNT(*) AS total_exams,
          SUM(CASE WHEN e.exam_Modality_Code = 'MG' THEN 1 ELSE 0 END) AS mammo_total,
          SUM(CASE WHEN e.exam_Modality_Code = 'MG' AND e.mosaic_read_flag THEN 1 ELSE 0 END) AS mammo_mosaic,
          SUM(CASE WHEN e.exam_Modality_Code = 'CR' AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS total_xr_drafted,
          SUM(CASE WHEN e.exam_Modality_Code = 'CR' AND d.drafting_model = 'XR/MSK' THEN 1 ELSE 0 END) AS draftable_xr,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND e.RPID_Procedure_Code = 'RPID22' AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS ct_head_drafted,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND e.RPID_Procedure_Code = 'RPID22' THEN 1 ELSE 0 END) AS draftable_ct_head,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND d.drafting_model = 'CT Abd/Pel' AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS ct_abdpel_drafted,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND d.drafting_model = 'CT Abd/Pel' THEN 1 ELSE 0 END) AS draftable_ct_abdpel,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND d.drafting_model = 'CT Chest' AND e.mosaic_draft_flag THEN 1 ELSE 0 END) AS ct_chest_drafted,
          SUM(CASE WHEN e.exam_Modality_Code = 'CT' AND d.drafting_model = 'CT Chest' THEN 1 ELSE 0 END) AS draftable_ct_chest,
          SUM(CASE WHEN e.exam_Modality_Code = 'US' AND e.mosaic_draft_flag AND d.drafting_model = 'US Capturable' THEN 1 ELSE 0 END) AS captured_us,
          SUM(CASE WHEN e.exam_Modality_Code = 'US' AND d.drafting_model = 'US Capturable' THEN 1 ELSE 0 END) AS us_capturable
        FROM {settings.qualified}.tbl_exam_inventory e
        LEFT JOIN {_DRAFTING_ELIGIBLE_VW} d ON d.rpid_procedure_code = e.RPID_Procedure_Code
        WHERE CAST(e.final_datetime AS DATE) >= '2025-04-01'
        GROUP BY e.reading_provider_npi
        """
    )

    dim_rows = run_query(
        f"""
        SELECT reading_provider_npi AS npi, MAX(reading_provider_name_full) AS radiologist_name,
               MAX(provider_local_practice_name_curr) AS home_practice
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE mosaic_read_flag = true
        GROUP BY reading_provider_npi
        """
    )
    dim_by_npi = {row["npi"]: row for row in dim_rows}

    # Replaces rad_onboarding's raw AD-group-date parsing (unreachable now) with
    # dynamics_rad_drafting_enablement_vw's own governed per-model drafting_enabled_flag.
    group_rows = run_query(
        f"""
        SELECT
          CAST(npi AS DECIMAL(10,0)) AS npi,
          MAX(CASE WHEN drafting_model = 'XR (CXR/ABD/MSK)' AND drafting_enabled_flag THEN 1 ELSE 0 END) = 1 AS on_xr,
          MAX(CASE WHEN drafting_model = 'CT Head' AND drafting_enabled_flag THEN 1 ELSE 0 END) = 1 AS on_ct_head,
          MAX(CASE WHEN drafting_model = 'CT Abd Pelvis' AND drafting_enabled_flag THEN 1 ELSE 0 END) = 1 AS on_ct_abdpel
        FROM {settings.qualified}.dynamics_rad_drafting_enablement_vw
        GROUP BY npi
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


def get_draft_insights_raw() -> list[dict]:
    """Every current-version row from the AI-assessed draft-vs-final sample
    (edw_prod.enterprise_analytics.tbl_mosaic_draft_insights - built out-of-band by
    tools/draft_insights/001_build_draft_insights_sample.sql, a bounded recent sample, NOT
    the full drafted population, and not written by this app), joined back to
    tbl_exam_inventory for modality/practice since the insights table itself only stores the
    assessment fields plus accession_number.

    Hardcodes edw_prod.enterprise_analytics for both tables rather than using
    settings.qualified - this predates the rest of the file's migration onto the same schema,
    kept as literal SQL since tbl_mosaic_draft_insights only ever existed there."""
    return run_query(
        """
        SELECT
          t.accession_number, t.retention_pct, t.overall_assessment,
          t.added_by_radiologist, t.added_by_radiologist_categories,
          t.removed_from_draft, t.removed_from_draft_categories,
          t.formatting_categories,
          t.clinical_interpretation_categories,
          t.additional_findings_categories,
          ei.exam_Modality_Code AS modality,
          ei.provider_local_practice_name_curr AS practice
        FROM edw_prod.enterprise_analytics.tbl_mosaic_draft_insights t
        JOIN edw_prod.enterprise_analytics.tbl_exam_inventory ei
          ON ei.accession_number = t.accession_number
        WHERE t.is_current = true
        """
    )


# Exact tier: mosaic_rebaseline_notebook's own algorithm (20%-Mosaic-utilization crossing date,
# 6-months-prior Baseline window, per-(NPI, ShiftName) average POS-adjusted TBWU/hour,
# excluded-practices list - whole NPI dropped if ANY shift ties to an excluded practice).
_CAPACITY_EXACT_CTE_SQL = f"""
, excluded_npis AS (
  SELECT DISTINCT NPI FROM raw_shifts WHERE localpractice IN ({_CAPACITY_EXCLUDED_PRACTICES_SQL})
),
exact_baseline AS (
  SELECT
    cs.NPI, cs.ShiftName,
    ANY_VALUE(cs.Task_ID) AS Task_ID,
    MAX(cs.localpractice) AS Practice,
    MAX(cs.Rad_name) AS Rad_name,
    AVG(cs.no_hours) AS Shift_Length,
    COUNT(DISTINCT cs.ShiftDate) AS Shift_Count,
    AVG(try_divide(cs.shift_adj_TBWU, cs.no_hours)) AS baseline_tbwu_per_hour
  FROM classified_shifts cs
  WHERE cs.period_label = 'Baseline'
    AND cs.NPI NOT IN (SELECT NPI FROM excluded_npis)
  GROUP BY cs.NPI, cs.ShiftName
)
"""

# Proxy/Manual Review tier: Baselines Proxies.sql's 8-component similarity scoring, rebuilt
# against tbl_exam_inventory - scheduled_shift_location replaces the old schedule_task_dim
# join + Onsite/Remote string-matching entirely. Matching is same-NPI-only (a rad's OWN other
# shift types donate the baseline), exactly as the original notebook does (source_shifts JOINs
# target_shifts on NPI alone). Simplified from the original: the "High Capacity Impact" review
# flag (top-10%-of-capacity-at-stake) is dropped - it only affected an Excel export label this
# app never surfaced - so Manual Review here is decided by the "No Good Proxy" (score < 40) and
# "Outlier vs. Peers" (< 70% of peer median) flags only.
_CAPACITY_PROXY_RANKED_CTE_SQL = """
, donor_npis AS (
  SELECT DISTINCT NPI FROM exact_baseline
),
feature_shifts AS (
  SELECT
    cs.NPI, cs.ShiftName, cs.period_label,
    ANY_VALUE(cs.localpractice) AS localpractice,
    ANY_VALUE(cs.Rad_name) AS Rad_name,
    ANY_VALUE(cs.Task_ID) AS Task_ID,
    AVG(cs.no_hours) AS avg_hours,
    try_divide(SUM(cs.shift_TBWU), NULLIF(SUM(cs.shift_cases), 0)) AS tbwu_per_exam,
    ANY_VALUE(cs.shift_location) AS shift_location,
    AVG(TIMESTAMPDIFF(MINUTE, DATE(cs.Schedule_Start_DateTime), cs.Schedule_Start_DateTime)) AS start_minute,
    AVG(TIMESTAMPDIFF(MINUTE, DATE(cs.Schedule_Start_DateTime), cs.Schedule_End_DateTime)) AS end_minute,
    MAX(CASE WHEN DAYOFWEEK(cs.ShiftDate) IN (1, 7) THEN 1 ELSE 0 END) AS is_weekend,
    try_divide(SUM(cs.specialized_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_specialized,
    try_divide(SUM(cs.interventional_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_interventional,
    try_divide(SUM(cs.ct_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_CT,
    try_divide(SUM(cs.xr_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_XR,
    try_divide(SUM(cs.us_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_US,
    try_divide(SUM(cs.mr_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_MR,
    try_divide(SUM(cs.mg_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_MG,
    try_divide(SUM(cs.nm_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_NM,
    try_divide(SUM(cs.other_modality_cases) + SUM(cs.pt_cases) + SUM(cs.ir_cases), NULLIF(SUM(cs.shift_cases), 0)) AS pct_Other
  FROM classified_shifts cs
  WHERE cs.NPI IN (SELECT NPI FROM donor_npis)
  GROUP BY cs.NPI, cs.ShiftName, cs.period_label
),
target_shifts AS (
  SELECT f.*
  FROM feature_shifts f
  LEFT JOIN exact_baseline eb ON eb.NPI = f.NPI AND eb.ShiftName = f.ShiftName
  WHERE f.period_label = 'Current' AND eb.NPI IS NULL
),
source_shifts AS (
  SELECT f.*, eb.baseline_tbwu_per_hour, eb.Shift_Length AS baseline_shift_length
  FROM feature_shifts f
  JOIN exact_baseline eb ON eb.NPI = f.NPI AND eb.ShiftName = f.ShiftName
  WHERE f.period_label = 'Baseline'
),
scored AS (
  SELECT
    t.NPI, t.Rad_name, t.localpractice,
    t.ShiftName AS target_shift, t.Task_ID AS target_task_id, t.avg_hours AS target_hours,
    s.ShiftName AS proxy_shift, s.baseline_tbwu_per_hour, s.baseline_shift_length,
    CASE WHEN UPPER(TRIM(t.ShiftName)) = UPPER(TRIM(s.ShiftName)) THEN 1 ELSE 0 END AS exact_name_match,
    ROUND(
      CASE WHEN t.pct_specialized IS NULL AND s.pct_specialized IS NULL THEN 10
           WHEN t.pct_specialized IS NULL OR s.pct_specialized IS NULL THEN 0
           ELSE (1.0 - ABS(COALESCE(t.pct_specialized, 0) - COALESCE(s.pct_specialized, 0))) * 10 END
    ) AS score_subspecialty,
    ROUND(
      CASE WHEN t.pct_interventional IS NULL AND s.pct_interventional IS NULL THEN 20
           WHEN t.pct_interventional IS NULL OR s.pct_interventional IS NULL THEN 0
           ELSE (1.0 - ABS(COALESCE(t.pct_interventional, 0) - COALESCE(s.pct_interventional, 0))) * 20 END
    ) AS score_interventional,
    ROUND(
      CASE WHEN SQRT(COALESCE(t.pct_CT,0)*COALESCE(t.pct_CT,0)+COALESCE(t.pct_XR,0)*COALESCE(t.pct_XR,0)+COALESCE(t.pct_US,0)*COALESCE(t.pct_US,0)+COALESCE(t.pct_MR,0)*COALESCE(t.pct_MR,0)+COALESCE(t.pct_MG,0)*COALESCE(t.pct_MG,0)+COALESCE(t.pct_NM,0)*COALESCE(t.pct_NM,0)+COALESCE(t.pct_Other,0)*COALESCE(t.pct_Other,0))
                * SQRT(COALESCE(s.pct_CT,0)*COALESCE(s.pct_CT,0)+COALESCE(s.pct_XR,0)*COALESCE(s.pct_XR,0)+COALESCE(s.pct_US,0)*COALESCE(s.pct_US,0)+COALESCE(s.pct_MR,0)*COALESCE(s.pct_MR,0)+COALESCE(s.pct_MG,0)*COALESCE(s.pct_MG,0)+COALESCE(s.pct_NM,0)*COALESCE(s.pct_NM,0)+COALESCE(s.pct_Other,0)*COALESCE(s.pct_Other,0)) = 0 THEN 0
           ELSE (COALESCE(t.pct_CT,0)*COALESCE(s.pct_CT,0)+COALESCE(t.pct_XR,0)*COALESCE(s.pct_XR,0)+COALESCE(t.pct_US,0)*COALESCE(s.pct_US,0)+COALESCE(t.pct_MR,0)*COALESCE(s.pct_MR,0)+COALESCE(t.pct_MG,0)*COALESCE(s.pct_MG,0)+COALESCE(t.pct_NM,0)*COALESCE(s.pct_NM,0)+COALESCE(t.pct_Other,0)*COALESCE(s.pct_Other,0))
                / (SQRT(COALESCE(t.pct_CT,0)*COALESCE(t.pct_CT,0)+COALESCE(t.pct_XR,0)*COALESCE(t.pct_XR,0)+COALESCE(t.pct_US,0)*COALESCE(t.pct_US,0)+COALESCE(t.pct_MR,0)*COALESCE(t.pct_MR,0)+COALESCE(t.pct_MG,0)*COALESCE(t.pct_MG,0)+COALESCE(t.pct_NM,0)*COALESCE(t.pct_NM,0)+COALESCE(t.pct_Other,0)*COALESCE(t.pct_Other,0))
                   * SQRT(COALESCE(s.pct_CT,0)*COALESCE(s.pct_CT,0)+COALESCE(s.pct_XR,0)*COALESCE(s.pct_XR,0)+COALESCE(s.pct_US,0)*COALESCE(s.pct_US,0)+COALESCE(s.pct_MR,0)*COALESCE(s.pct_MR,0)+COALESCE(s.pct_MG,0)*COALESCE(s.pct_MG,0)+COALESCE(s.pct_NM,0)*COALESCE(s.pct_NM,0)+COALESCE(s.pct_Other,0)*COALESCE(s.pct_Other,0))) * 5
      END
    ) AS score_modality,
    ROUND(
      CASE WHEN t.tbwu_per_exam IS NULL OR s.tbwu_per_exam IS NULL OR GREATEST(t.tbwu_per_exam, s.tbwu_per_exam) = 0 THEN 0
           ELSE (1.0 - ABS(t.tbwu_per_exam - s.tbwu_per_exam) / GREATEST(ABS(t.tbwu_per_exam), ABS(s.tbwu_per_exam), 0.0001)) * 5 END
    ) AS score_tbwu,
    ROUND(
      CASE WHEN t.avg_hours IS NULL OR s.avg_hours IS NULL OR GREATEST(t.avg_hours, s.avg_hours) = 0 THEN 0
           ELSE (1.0 - ABS(t.avg_hours - s.avg_hours) / GREATEST(t.avg_hours, s.avg_hours)) * 10 END
    ) AS score_shift_duration,
    ROUND(
      CASE WHEN t.shift_location = 'Unknown' OR s.shift_location = 'Unknown' THEN 0
           WHEN t.shift_location = s.shift_location THEN 10 ELSE 0 END
    ) AS score_location,
    ROUND(CASE WHEN t.is_weekend = s.is_weekend THEN 5 ELSE 0 END) AS score_weekday_weekend,
    ROUND(
      CASE WHEN t.start_minute IS NULL OR t.end_minute IS NULL OR s.start_minute IS NULL OR s.end_minute IS NULL THEN 0
           WHEN GREATEST(t.end_minute, s.end_minute) - LEAST(t.start_minute, s.start_minute) = 0 THEN 0
           ELSE GREATEST(0, LEAST(t.end_minute, s.end_minute) - GREATEST(t.start_minute, s.start_minute)) * 1.0
                / (GREATEST(t.end_minute, s.end_minute) - LEAST(t.start_minute, s.start_minute)) * 5 END
    ) AS score_time_of_day
  FROM target_shifts t
  JOIN source_shifts s ON s.NPI = t.NPI
),
final_scored AS (
  SELECT *,
    score_subspecialty + score_interventional + score_modality + score_tbwu AS score_work_type,
    score_subspecialty + score_interventional + score_modality + score_tbwu
      + score_shift_duration + score_location + score_weekday_weekend + score_time_of_day AS total_match_score
  FROM scored
),
ranked_proxy AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY NPI, target_shift
      ORDER BY exact_name_match DESC, total_match_score DESC, score_work_type DESC
    ) AS rank
  FROM final_scored
)
"""

# Reused as-is by get_capacity_with_baseline/get_baseline_proxy_detail (rank=1 winner only) -
# get_baseline_proxy_candidates below shares _CAPACITY_PROXY_RANKED_CTE_SQL but keeps rank<=5
# instead, so don't fold this suffix back into the ranked CTE above.
_CAPACITY_PROXY_CTE_SQL = _CAPACITY_PROXY_RANKED_CTE_SQL + """
, peer_stats AS (
  SELECT ShiftName, PERCENTILE(baseline_tbwu_per_hour * baseline_shift_length, 0.5) AS peer_median
  FROM source_shifts
  GROUP BY ShiftName
),
proxy_baseline AS (
  SELECT
    r.NPI, r.Rad_name, r.localpractice AS Practice, r.target_shift AS ShiftName, r.target_task_id AS Task_ID,
    r.target_hours AS Shift_Length, r.baseline_tbwu_per_hour, r.proxy_shift, r.total_match_score,
    r.score_subspecialty, r.score_interventional, r.score_modality, r.score_tbwu,
    r.score_shift_duration, r.score_location, r.score_weekday_weekend, r.score_time_of_day, r.score_work_type,
    CASE
      WHEN r.total_match_score < 40 THEN 'Manual Review'
      WHEN ps.peer_median IS NOT NULL AND (r.baseline_tbwu_per_hour * r.target_hours) < ps.peer_median * 0.70 THEN 'Manual Review'
      ELSE 'Proxy'
    END AS Baseline_Type
  FROM ranked_proxy r
  LEFT JOIN peer_stats ps ON ps.ShiftName = r.proxy_shift
  WHERE r.rank = 1
)
"""


def get_capacity_with_baseline() -> list[dict]:
    """Rebuilt from tbl_exam_inventory - stg_mosaic_baseline_master/
    stg_mosaic_proxy_all_candidates_2026 (edw_dev.bipa_analytics) are unreachable under this
    app's grants. Computes the Exact tier live (_CAPACITY_EXACT_CTE_SQL) and the Proxy/Manual
    Review tier live (_CAPACITY_PROXY_CTE_SQL), then attaches whichever tier matches to every
    live shift instance via the same two-tier join this function already used: exact
    (NPI, Task_ID) first, falling back to (NPI, normalized ShiftName).

    baseline_tbwu_per_hour here is already a rate (not a per-canonical-shift-length total like
    the old Shift_Baseline_TBWU_2026), so it's rescaled directly by this shift instance's own
    no_hours - same rationale as before (a rad's canonical "12-hour weekend shift" baseline
    still needs rescaling if they actually worked a 10-hour version of it that day).

    SEAL Team is deliberately NOT covered here - matches the original's own exclusion (it ran
    an entirely separate baseline pipeline, stg_seal_baseline_master, never wired into
    reporting). SEAL Team shifts simply show up with baseline_type = NULL here."""
    return run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + _CAPACITY_CLASSIFIED_CTE_SQL
        + _CAPACITY_EXACT_CTE_SQL
        + _CAPACITY_PROXY_CTE_SQL
        + """
        , baseline_merged AS (
          SELECT NPI, ShiftName, Task_ID, baseline_tbwu_per_hour, 'Exact' AS Baseline_Type FROM exact_baseline
          UNION ALL
          SELECT NPI, ShiftName, Task_ID, baseline_tbwu_per_hour, Baseline_Type FROM proxy_baseline
        ),
        baseline_ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY NPI, UPPER(TRIM(ShiftName))
            ORDER BY CASE Baseline_Type WHEN 'Exact' THEN 1 WHEN 'Proxy' THEN 2 ELSE 3 END
          ) AS rn
          FROM baseline_merged
        )
        SELECT
          v.NPI AS npi, v.localpractice AS practice, v.ShiftName AS target_shift, v.no_hours,
          v.shift_TBWU AS on_shift_capacity_rpwu,
          COALESCE(m_exact.baseline_tbwu_per_hour, m_fallback.baseline_tbwu_per_hour) * v.no_hours AS shift_baseline_rpwu_fixed,
          COALESCE(m_exact.Baseline_Type, m_fallback.Baseline_Type) AS baseline_type
        FROM raw_shifts v
        LEFT JOIN baseline_merged m_exact ON v.NPI = m_exact.NPI AND v.Task_ID = m_exact.Task_ID
        LEFT JOIN baseline_ranked m_fallback
          ON v.NPI = m_fallback.NPI AND UPPER(TRIM(v.ShiftName)) = UPPER(TRIM(m_fallback.ShiftName)) AND m_fallback.rn = 1
        WHERE v.localpractice IS NOT NULL
        """
    )


def get_baseline_proxy_detail() -> list[dict]:
    """The chosen (rank=1) proxy match per (NPI, target shift) that lacked its own baseline
    history - see _CAPACITY_PROXY_CTE_SQL for the full rebuilt scoring algorithm."""
    return run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + _CAPACITY_CLASSIFIED_CTE_SQL
        + _CAPACITY_EXACT_CTE_SQL
        + _CAPACITY_PROXY_CTE_SQL
        + """
        SELECT
          NPI AS npi, Rad_name AS radiologist_name, Practice AS practice,
          ShiftName AS target_shift, proxy_shift, total_match_score,
          score_subspecialty, score_interventional, score_modality, score_tbwu,
          score_shift_duration, score_location, score_weekday_weekend,
          score_time_of_day, score_work_type, Baseline_Type AS baseline_type
        FROM proxy_baseline
        """
    )


def get_baseline_proxy_candidates() -> list[dict]:
    """Every candidate shift-type (not just the rank=1 winner) considered for each (NPI,
    target shift) that lacks its own baseline - top 5 by total_match_score, same scoring as
    get_baseline_proxy_detail. Powers the Baseline Review Queue's ranked-candidate view, so a
    reviewer can see (and override) the alternatives the algorithm didn't pick, not just its
    final answer."""
    return run_query(
        _CAPACITY_SHIFT_CTE_SQL
        + _CAPACITY_CLASSIFIED_CTE_SQL
        + _CAPACITY_EXACT_CTE_SQL
        + _CAPACITY_PROXY_RANKED_CTE_SQL
        + """
        SELECT
          NPI AS npi, Rad_name AS radiologist_name, localpractice AS practice,
          target_shift, rank, proxy_shift, total_match_score,
          score_subspecialty, score_interventional, score_modality, score_tbwu,
          score_shift_duration, score_location, score_weekday_weekend, score_time_of_day,
          score_work_type, baseline_tbwu_per_hour
        FROM ranked_proxy
        WHERE rank <= 5
        """
    )
