@echo off
REM Windows Task Scheduler entry point for sync_drafting_model_practice_sites.py - same
REM pattern as tools\mosaic_version_pipeline\run_sync.bat (Databricks Jobs hit a scheduled-
REM task permission-prompt rejection for that pipeline on 2026-10-24, so this repo schedules
REM these pulls via Task Scheduler instead of a Databricks Job).
cd /d "C:\Users\bhargav.narasimhan\mosaic-module"
echo ---- %date% %time% ---- >> tools\smartsheet_drafting_sites\sync_log.txt
python tools\smartsheet_drafting_sites\sync_drafting_model_practice_sites.py --apply >> tools\smartsheet_drafting_sites\sync_log.txt 2>&1
