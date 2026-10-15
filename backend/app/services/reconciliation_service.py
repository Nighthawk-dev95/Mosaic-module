"""Reconciliation: where the counts disagree - 3 concrete, already-diagnosed divergences
surfaced as a live, queryable feed, mirroring the pattern (not the data source) of PCC's
native Mosaic Intelligence Reconciliation tab (confirmed via its own compiled bundle: it
reconciles PCC's computed numbers against a different team's published figures, rendered as a
"strip across the top... divergences first and biggest first"). We have no equivalent external
feed, but these 3 checks are just as real - each traces back to a specific prior investigation
recorded in project memory, never before surfaced as anything but a one-off notebook check.

Check 2 and 3 depend on edw_prod.enterprise_analytics.tbl_seal_roster/tbl_seal_baseline_master -
governed copies of edw_dev.bipa_analytics.stg_seal_roster/stg_seal_baseline_master, migrated so
this app's service principal (confirmed scoped to enterprise_analytics ONLY, see config.py) can
read them without a cross-catalog grant. See
tools/edw_fixes/011_migrate_seal_reference_tables_to_enterprise_analytics.sql - RUN 2026-10-14
(118/105 rows, matching source exactly). The per-check try/except in get_all_findings() below
is kept even though both tables now exist - if the migration is ever re-run and briefly fails,
the mosaic_flag_mismatch check should still return results rather than the whole feed erroring.
"""

from app.config import settings
from app.db.databricks_client import run_query
from app.models.mosaic import ReconciliationFinding


def get_mosaic_flag_divergence() -> list[ReconciliationFinding]:
    """Practices where mosaic_read_flag and report_transcription_system_name = 'Mosaic
    Reporting' disagree on the same exam. report_transcription_system_name's own column
    comment documents the two as "near-identical (99.89%)" - this surfaces the remaining
    minority where they don't match, which the 2026-09 investigation (see memory:
    mosaic-flag-edw-investigation) traced to a genuine, unresolved AWS-report-signed-events
    vs HL7 source disagreement for a minority of accessions, not a bug on our side."""
    rows = run_query(
        f"""
        SELECT
          provider_local_practice_name_curr AS practice,
          COUNT(*) AS mismatch_count
        FROM {settings.qualified}.tbl_exam_inventory
        WHERE Study_Status_Code = 'Final'
          AND mosaic_read_flag != (report_transcription_system_name = 'Mosaic Reporting')
        GROUP BY provider_local_practice_name_curr
        HAVING COUNT(*) > 0
        ORDER BY mismatch_count DESC
        """
    )
    return [
        ReconciliationFinding(
            check="mosaic_flag_mismatch",
            scope="Practice",
            entity=row["practice"] or "(unassigned)",
            expected="mosaic_read_flag matches report_transcription_system_name = 'Mosaic Reporting'",
            actual=f"{row['mismatch_count']} exam(s) where the two disagree",
            magnitude=float(row["mismatch_count"]),
            detail="Known AWS-report-signed-events vs HL7 source disagreement for a minority of accessions - see memory: mosaic-flag-edw-investigation.",
        )
        for row in rows
    ]


def get_seal_team_mislabeling() -> list[ReconciliationFinding]:
    """SEAL-roster radiologists whose live exam-level practice attribution shows their actual
    non-SEAL practice instead of "SEAL Team" - confirmed real (Krishnasetty, Hattaway and
    others) via memory: seal-current-team-mislabeling. The baseline table hardcodes
    Practice='SEAL Team' for every roster NPI, but the live reporting pipeline has no
    roster-based override, so the two disagree for any SEAL rad who works entirely under
    another practice's scheduling data."""
    rows = run_query(
        f"""
        SELECT
          e.reading_provider_npi AS npi,
          r.First_Name AS first_name,
          r.Last_Name AS last_name,
          e.provider_local_practice_name_curr AS current_practice,
          COUNT(*) AS exam_count
        FROM {settings.qualified}.tbl_exam_inventory e
        JOIN {settings.qualified}.tbl_seal_roster r
          ON e.reading_provider_npi = r.NPI
        WHERE r.Is_Active = true
          AND e.provider_local_practice_name_curr != 'SEAL Team'
          AND e.Study_Status_Code = 'Final'
        GROUP BY e.reading_provider_npi, r.First_Name, r.Last_Name, e.provider_local_practice_name_curr
        ORDER BY exam_count DESC
        """
    )
    return [
        ReconciliationFinding(
            check="seal_team_mislabeling",
            scope="Radiologist (NPI)",
            entity=f"{row['last_name']}, {row['first_name']} (NPI {row['npi']})",
            expected="SEAL Team",
            actual=f"{row['current_practice']} ({row['exam_count']} exams)",
            magnitude=float(row["exam_count"]),
            detail="Baseline table (roster-driven) and live reporting pipeline (QGenda-schedule-driven) have no shared override logic - see memory: seal-current-team-mislabeling.",
        )
        for row in rows
    ]


def get_seal_baseline_drift() -> list[ReconciliationFinding]:
    """Population drift between the SEAL baseline table and the authoritative roster -
    reconciled once (2026-09-30, see memory: seal-roster-reconciliation) but nothing has
    watched for drift since. Two directions: a baseline row for an NPI no longer active on the
    roster (a stale row that should be removed) and an active-roster NPI with no baseline row
    at all (not necessarily a bug - may just mean that radiologist hasn't crossed the 20%
    Mosaic-utilization threshold yet - labeled accordingly, not as an error)."""
    stale = run_query(
        f"""
        SELECT b.NPI AS npi, b.Radiologist AS radiologist
        FROM {settings.qualified}.tbl_seal_baseline_master b
        LEFT JOIN {settings.qualified}.tbl_seal_roster r
          ON b.NPI = r.NPI AND r.Is_Active = true
        WHERE r.NPI IS NULL
        GROUP BY b.NPI, b.Radiologist
        """
    )
    missing = run_query(
        f"""
        SELECT r.NPI AS npi, r.First_Name AS first_name, r.Last_Name AS last_name
        FROM {settings.qualified}.tbl_seal_roster r
        LEFT JOIN {settings.qualified}.tbl_seal_baseline_master b
          ON r.NPI = b.NPI
        WHERE r.Is_Active = true AND b.NPI IS NULL
        """
    )
    findings = [
        ReconciliationFinding(
            check="seal_baseline_drift",
            scope="Radiologist (NPI)",
            entity=f"{row['radiologist']} (NPI {row['npi']})",
            expected="No baseline row (not on active roster)",
            actual="Has a baseline row - stale, roster no longer lists this NPI as active",
            magnitude=1.0,
            detail="See memory: seal-roster-reconciliation for the 2026-09-30 cleanup this drift-checks against.",
        )
        for row in stale
    ]
    findings += [
        ReconciliationFinding(
            check="seal_baseline_drift",
            scope="Radiologist (NPI)",
            entity=f"{row['last_name']}, {row['first_name']} (NPI {row['npi']})",
            expected="Has a baseline row",
            actual="No baseline row yet (may be legitimate - under 20% Mosaic utilization crossed)",
            magnitude=1.0,
            detail="Not necessarily a bug - see memory: seal-roster-reconciliation, most of this population simply hasn't crossed the baseline threshold yet.",
        )
        for row in missing
    ]
    return findings


def get_all_findings() -> list[ReconciliationFinding]:
    # Each check runs independently - the 2 SEAL-based checks depend on a migration
    # (tools/edw_fixes/011_...) that may not have landed yet (table-not-found until it does),
    # and that must not take down the one check (mosaic_flag_mismatch) that already works
    # today. A failed check just contributes zero findings, not a failed refresh.
    findings: list[ReconciliationFinding] = []
    for check in (get_mosaic_flag_divergence, get_seal_team_mislabeling, get_seal_baseline_drift):
        try:
            findings.extend(check())
        except Exception as exc:  # noqa: BLE001 - one check's table not existing yet must not break the others
            print(f"[reconciliation] {check.__name__} failed (expected until its migration lands): {exc}", flush=True)
    findings.sort(key=lambda f: f.magnitude, reverse=True)
    return findings
