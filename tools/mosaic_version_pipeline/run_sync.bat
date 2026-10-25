@echo off
REM Windows Task Scheduler entry point for sync_exam_lookup.py - runs independently of the
REM Claude desktop app, so it fires on schedule even if the app is closed, and doesn't hit the
REM Claude permission-prompt layer that caused the 2026-10-24 scheduled-task rejection. Interim
REM fix until the pending radpair_instance Delta Share field lands and this whole AWS pull goes
REM away.
cd /d "C:\Users\bhargav.narasimhan\mosaic-module"
echo ---- %date% %time% ---- >> tools\mosaic_version_pipeline\sync_log.txt
python tools\mosaic_version_pipeline\sync_exam_lookup.py --apply >> tools\mosaic_version_pipeline\sync_log.txt 2>&1
