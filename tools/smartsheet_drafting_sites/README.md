# Smartsheet -> EDW: Managing Practice sites enabled per drafting model

Goal: a live copy, in `edw_dev.enterprise_analytics`, of the Smartsheet that tracks which
Managing Practice sites are enabled for each Mosaic drafting model. This is a separate,
new table - **not** related to `edw_dev.bipa_analytics.drafting_model_practice_enablement`
(the existing hand-maintained VALUES list fed from Dynamics/IAM enablement activity - see
`tools/edw_fixes/011_date_effective_practice_enablement.sql`). Confirmed with the user
2026-10-27 that these are two different lists; don't conflate them.

Two parallel tracks, because the native connector is Beta (not production-supported per
Databricks' own docs):

- **Primary: Lakeflow Connect** (`pipeline_create.json`) - zero-code managed connector,
  full refresh each run, no code to own. Blocked today on two one-time admin actions (see
  below) neither of which `bhargav.narasimhan@radpartners.com` can do solo.
- **Backup: scheduled Python script** (`sync_drafting_model_practice_sites.py`) calling the
  Smartsheet REST API directly, staged + MERGEd into EDW the same way
  `tools/mosaic_version_pipeline/sync_exam_lookup.py` already does for the AWS log pull.
  Lower setup friction (no Databricks-admin step, no Smartsheet Developer Tools approval -
  just a personal Smartsheet API token), GA-stable, more code to maintain. Can likely stand
  this up *today*.

Both tracks need the sheet's **16-digit numeric Sheet ID** (NOT the share-link URL token -
find it in Smartsheet via the sheet tab's right-click menu -> Properties, or File ->
Properties; view access is enough to see it) and, for the backup track, a personal
Smartsheet API token (Account -> Apps & Integrations -> API Access -> Generate new access
token - no admin approval needed, unlike the OAuth app below).

## Track 1: Lakeflow Connect (primary)

One-time setup, in order - **steps 1-2 need a human in a browser; neither can be scripted**:

1. **Smartsheet side** - register for Developer Tools with a Smartsheet account, create a
   Developer Profile, then register an App to get a Client ID/Secret. Any Smartsheet
   account can do this (doesn't have to be an org admin), but Smartsheet itself has to
   approve the Developer Tools registration first. See
   https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/smartsheet-source-setup
2. **Databricks side** - a `rp-usce-dbx-metastore-01` metastore admin (owner group
   `Metastore_Admins_Temp` - confirmed via `SHOW GRANTS ON METASTORE` 2026-10-27 that
   `bhargav.narasimhan` has no explicit `CREATE CONNECTION` grant, and neither does the
   BIPA-ADM/EA-ADM groups he's in) goes to **Catalog > Create > Create a connection**,
   type **Smartsheet**, pastes the Client ID/Secret from step 1, and signs in with a
   Smartsheet account that has at least view access to the target sheet - connector
   visibility is scoped to whichever Smartsheet account completes that OAuth login.
   See https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/smartsheet-connection
3. Once the connection exists, the admin grants `USE CONNECTION` on it to
   `bhargav.narasimhan@radpartners.com` (or the BIPA-RW/EA-ADM group), so pipeline
   creation doesn't need repeated admin involvement.
4. Fill in `pipeline_create.json`'s `connection_name` and `source_table` (the 16-digit
   sheet ID), then:
   ```bash
   databricks pipelines create --profile mosaic-app --json @tools/smartsheet_drafting_sites/pipeline_create.json
   databricks pipelines start-update <pipeline-id> --profile mosaic-app
   databricks pipelines get-update <pipeline-id> <update-id> --profile mosaic-app
   ```
5. Schedule it with a Jobs `pipeline_task` (triggered-only, no continuous mode) - daily is
   plenty for a config/reference list like this.

**Known limitation to design around:** no incremental sync - every run is a full refresh of
the destination table. Fine for a small reference list; just means no row-level history is
kept automatically (if that's ever needed, snapshot the table on a cadence separately).

## Track 2: Smartsheet REST API script (backup, can run now)

`sync_drafting_model_practice_sites.py` follows the same shape as
`tools/mosaic_version_pipeline/sync_exam_lookup.py`: pull from the external source, stage
a CSV in a Databricks Volume, `MERGE INTO` the target table via
`databricks experimental aitools tools query` (profile `mosaic-oauth` - PATs lack the
`files` scope for volume uploads, confirmed on that script). Unlike that script, this one
also does `WHEN NOT MATCHED BY SOURCE THEN DELETE` so the table stays a faithful mirror of
"currently enabled sites" (Smartsheet has no concept of incremental sync either, so a true
mirror is the right semantic here, same as the native connector's own full-refresh
behavior) - still implemented as a safe MERGE, never a DROP/CREATE OR REPLACE, so it's
consistent with this repo's additive-only rule for pre-existing objects in
`enterprise_analytics` (this table itself is new and solely owned by this job - nothing
hand-authored ever writes to it).

Setup:
1. Generate a personal Smartsheet API token (no admin approval needed) and store it the
   same way `TEAMS_WEBHOOK_URL` is stored for `post_to_teams.py` - a per-user Windows
   environment variable, read via the registry (handles the case where a long-running
   parent process hasn't picked up a `setx`'d variable yet):
   ```bash
   setx SMARTSHEET_API_TOKEN "<token>"
   ```
   Open a fresh shell afterwards so the new value is visible.
2. Fill in `SHEET_ID` at the top of `sync_drafting_model_practice_sites.py`.
3. Dry run, then apply:
   ```bash
   python tools/smartsheet_drafting_sites/sync_drafting_model_practice_sites.py
   python tools/smartsheet_drafting_sites/sync_drafting_model_practice_sites.py --apply
   ```
4. Schedule via Windows Task Scheduler running `run_sync.bat`, same pattern as
   `tools/mosaic_version_pipeline/run_sync.bat` (chosen there over a Databricks Job
   because the Databricks Jobs path hit a scheduled-task permission-prompt rejection on
   2026-10-24 for the AWS pull - documented in that script's header).

## Status (2026-10-27)

- Destination: `edw_dev.enterprise_analytics.smartsheet_drafting_model_practice_sites` -
  dev first, matching this project's established pattern of landing new external sources
  in `edw_dev` and promoting to `edw_prod.bipa_analytics` only after a parity check (see
  `036_mosaic_volume_metric_view_pbi_local_FLOW.sql` / PBI volume parity gate for that
  precedent). Promote once this is verified.
- BLOCKED on: (a) the sheet's 16-digit ID, (b) its column headers (needed to write the
  per-column `COMMENT`ed `CREATE TABLE`, matching this repo's documentation convention -
  every governed table here has one), (c) who will do the two Track 1 admin steps.
- Not blocked: nothing yet, once (a)/(b) land both tracks can be finished same-day.
