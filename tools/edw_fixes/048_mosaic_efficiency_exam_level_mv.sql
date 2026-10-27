-- 048: daily snapshot of edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw (022), the exam-grain source
-- of mosaic_efficiency_metric_view (023).
--
-- Why a snapshot: the view recomputes outlier windows, per-procedure baselines and per-radiologist qualification
-- counts over full exam history on every read, so nothing is pushed down. Every metric-view query (and every Genie
-- company / region efficiency question) rescanned ~250M rows and took 7-40 minutes. The view's logic is NOT
-- changed: this MV is SELECT * of it, refreshed daily after the EDW loads (same cadence as MVs 037-043).
-- 023 is then re-pointed at this MV (049); measures, dimensions and comments are unchanged.
-- No inline comments below: the deploy command strips '--' lines and flattens the statement.
-- Target: edw_test only. New object (additive). Never edw_prod.
CREATE MATERIALIZED VIEW IF NOT EXISTS edw_test.enterprise_analytics.mosaic_efficiency_exam_level_mv
COMMENT 'Daily snapshot (SELECT *) of edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw - one row per qualifying exam with period_type, outliers, baseline rates and per-mode qualification counts. Source of mosaic_efficiency_metric_view; materialized because the view recomputes full-history windows on every read.'
SCHEDULE CRON '0 30 7 * * ?' AT TIME ZONE 'America/Chicago'
AS
SELECT * FROM edw_test.enterprise_analytics.tbl_efficiency_exam_level_vw
