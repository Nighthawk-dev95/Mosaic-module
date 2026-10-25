-- Migrates edw_dev.bipa_analytics.team_rollups (144 rows, Team -> "Team Roll Up (KS)") into
-- enterprise_analytics, same CTAS pattern as 011/012/013/014. Needed by the Mosaic Efficiency
-- metric view (tools/pbi_semantic_extract/MIGRATION_PLAYBOOK.md): Timeline.tmdl's
-- 'team_rolled_up' calculated column looks this up per-Team, and the Efficiency exam-level view
-- (tbl_efficiency_exam_level_vw) needs the same rollup available in SQL, not just DAX.
--
-- edw_dev.bipa_analytics is unreachable under the deployed app's service principal (confirmed
-- via prior SHOW GRANTS, see backend/app/config.py's header comment and 011's rationale) - this
-- materializes a governed copy under the running user's own privileges (mosaic-app profile,
-- SEC-AZ-DBX-P-EA-ADM group membership, ALL PRIVILEGES on edw_prod.enterprise_analytics).

CREATE TABLE IF NOT EXISTS edw_prod.enterprise_analytics.tbl_team_rollups
COMMENT 'Governed copy of edw_dev.bipa_analytics.team_rollups: maps each QGenda Team name to its "Team Roll Up (KS)" label, used to roll individual teams up before further Local-region grouping. 144 rows as of 2026-10-22. Re-run the INSERT OVERWRITE below if the source table changes.'
AS SELECT
  Team,
  `Team Roll Up (KS)` AS Team_Roll_Up
FROM edw_dev.bipa_analytics.team_rollups;

-- To re-sync after the first run:
--   INSERT OVERWRITE edw_prod.enterprise_analytics.tbl_team_rollups
--   SELECT Team, `Team Roll Up (KS)` AS Team_Roll_Up FROM edw_dev.bipa_analytics.team_rollups;
