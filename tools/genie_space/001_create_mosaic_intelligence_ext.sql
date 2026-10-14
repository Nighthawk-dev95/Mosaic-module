-- STATUS: ON HOLD (2026-09-30) - user said hold off on this for now.
--
-- Materializes the Practice Command Centre's SharePoint-sourced static reference data
-- (Mosaic General Survey results, real Capture enablement dates) as real Unity Catalog
-- tables, so a Genie Space can query them like everything else in edw_dev.mosaictechops.
--
-- Source of truth for every value below: backend/app/data/rad_survey.py and
-- backend/app/data/capture_enablement.py in the mosaic-module repo (snapshot as of
-- 2026-09-11/14). This script has NOT been run yet - the Databricks connector available
-- to this session is read-only, so a human with CREATE TABLE on edw_dev needs to run it
-- (Databricks SQL editor or a notebook cell). Re-run this whole script (CREATE OR REPLACE)
-- whenever those two Python files are refreshed from updated source workbooks.
--
-- Consolidated to 3 tables (not 9) per the company's Genie Space governance model, which
-- treats table count as a deliberately-scoped, frozen-at-Bronze budget - see
-- tools/genie_space/SETUP.md. Concepts sharing a grain are merged into one wide table
-- rather than kept as separate one-concept-per-table objects.
--
-- New schema (not edw_dev.mosaictechops) so this app-contributed data has clear, separate
-- provenance from the data-engineering-owned governed layer.

CREATE SCHEMA IF NOT EXISTS edw_dev.mosaic_intelligence_ext
COMMENT 'Static reference data compiled by the Practice Command Centre / Mosaic Intelligence app from RP SharePoint trackers and the Mosaic General Survey - not derivable from EDW fact tables. Source: mosaic-module repo, backend/app/data/*.py.';

-- ============================================================================
-- Table 1/3: top-line survey scalars + the raw 0-10 NPS histogram (both single-row-ish,
-- fixed-cardinality reference data - natural to keep together).
-- ============================================================================

CREATE OR REPLACE TABLE edw_dev.mosaic_intelligence_ext.rad_survey_summary
COMMENT 'Top-line Mosaic General Survey results (810 respondents, fielded 2026-08-07 to 2026-09-02, sent 2026-08-12), one row. NPS is corrected from the raw workbook (recomputed as (promoters-detractors)/responses = -54.7, not the sheet''s buggy -8.09 which divided by total sent instead). Response rate corrected to 810/5474=14.8%, not the sheet''s unreconciled 40.7%. score_0..score_10 is the raw histogram for Q1 ("0-10, how likely to recommend Mosaic to a colleague"); promoters=sum(score_9,score_10), passives=sum(score_7,score_8), detractors=sum(score_0..score_6).'
AS SELECT * FROM VALUES (
  5474, 810, CAST(810 AS DOUBLE)/5474, 4.9, -54.7, 100, 167, 543,
  126, 46, 70, 75, 40, 98, 88, 90, 77, 41, 59
) AS t(
  sent, responses, response_rate, median_completion_minutes, nps, promoters, passives, detractors,
  score_0, score_1, score_2, score_3, score_4, score_5, score_6, score_7, score_8, score_9, score_10
);

-- ============================================================================
-- Table 2/3: every Likert/theme survey item in one long/tidy table - agreement
-- statements, feature satisfaction, problem frequency, and verbatim-keyword themes all
-- share a "label + optional 1-5 distribution + optional pct" shape, so one table with a
-- `category` discriminator replaces 5 separate one-per-concept tables.
-- ============================================================================

CREATE OR REPLACE TABLE edw_dev.mosaic_intelligence_ext.rad_survey_items
COMMENT 'Every Likert-scale item and verbatim-keyword theme from the Mosaic General Survey, one row per item. `category` = agreement_statement (Q6, 1-5 agree scale, n=810 each) | feature_satisfaction (Q8, 1-5 satisfaction, na_count = "N/A/haven''t used") | problem_frequency (Q9, 1=never-5=very often, n=810) | frustration_theme (Q4 verbatim, n=717 non-blank, keyword-tagged, can hit multiple themes so pct does not sum to 100) | praised_theme (Q3 verbatim, n=633 non-blank, same caveat). score_1..score_5/mean/na_count apply only to agreement_statement/feature_satisfaction/problem_frequency rows; pct applies only to frustration_theme/praised_theme rows (all other columns NULL on those rows).'
AS SELECT * FROM VALUES
  ('agreement_statement', 'Supports high-quality patient care', 153,153,206,218,80, NULL, 2.90, NULL),
  ('agreement_statement', 'Mosaic is easy to use',              129,192,192,249,48, NULL, 2.87, NULL),
  ('agreement_statement', 'I trust Mosaic outputs',             200,216,224,146,24, NULL, 2.48, NULL),
  ('agreement_statement', 'Meets/exceeds productivity goals',   220,163,176,175,76, NULL, 2.66, NULL),
  ('agreement_statement', 'Timely/effective support',           102,114,246,260,88, NULL, 3.15, NULL),
  ('agreement_statement', 'Seen meaningful improvement',        116,134,167,270,123,NULL, 3.19, NULL),
  ('agreement_statement', 'Believe it will keep improving',     50,69,193,347,151,  NULL, 3.59, NULL),
  ('feature_satisfaction', 'Reporting (STT/editing)',     4,299,233,138,117, 19, 3.08, NULL),
  ('feature_satisfaction', 'Drafting (AI reports XR/CT)', 114,82,131,199,226, 58, 3.45, NULL),
  ('feature_satisfaction', 'Capture (US worksheets)',     156,71,85,151,263,  84, 3.40, NULL),
  ('feature_satisfaction', 'Templates',                   21,177,186,201,192, 33, 3.47, NULL),
  ('problem_frequency', 'Slowness',                  6,126,333,242,103, NULL, 3.38, NULL),
  ('problem_frequency', 'Errors/freezing/crashes',   25,249,336,155,45,  NULL, 2.93, NULL),
  ('problem_frequency', 'Hardware issues (mic etc.)',111,366,214,83,36,  NULL, 2.47, NULL),
  ('frustration_theme', 'Speech recognition',        NULL,NULL,NULL,NULL,NULL, NULL, NULL, 40.4),
  ('frustration_theme', 'Templates rigidity',        NULL,NULL,NULL,NULL,NULL, NULL, NULL, 23.0),
  ('frustration_theme', 'Editing experience',        NULL,NULL,NULL,NULL,NULL, NULL, NULL, 17.0),
  ('frustration_theme', 'Drafting quality',          NULL,NULL,NULL,NULL,NULL, NULL, NULL, 13.8),
  ('frustration_theme', 'Slowness',                  NULL,NULL,NULL,NULL,NULL, NULL, NULL, 11.2),
  ('frustration_theme', 'Hallucinations/inaccuracy',  NULL,NULL,NULL,NULL,NULL, NULL, NULL, 9.6),
  ('frustration_theme', 'Trust',                      NULL,NULL,NULL,NULL,NULL, NULL, NULL, 7.9),
  ('frustration_theme', 'Crashes',                    NULL,NULL,NULL,NULL,NULL, NULL, NULL, 6.7),
  ('praised_theme', 'Drafting',            NULL,NULL,NULL,NULL,NULL, NULL, NULL, 36.2),
  ('praised_theme', 'Capture/ultrasound',  NULL,NULL,NULL,NULL,NULL, NULL, NULL, 13.9),
  ('praised_theme', 'Speech recognition',  NULL,NULL,NULL,NULL,NULL, NULL, NULL, 13.1),
  ('praised_theme', 'Templates',           NULL,NULL,NULL,NULL,NULL, NULL, NULL, 7.0),
  ('praised_theme', 'Productivity',        NULL,NULL,NULL,NULL,NULL, NULL, NULL, 3.6)
AS t(category, label, score_1, score_2, score_3, score_4, score_5, na_count, mean, pct);

-- ============================================================================
-- Table 3/3: one row per practice, merging survey NPS (18 practices, n>=15) and real
-- Capture enablement dates (54 practices) - both are practice-grain reference data, so
-- one wide table replaces two separate by-practice tables. NULLs are expected: not every
-- practice has both a qualifying survey sample and a known Capture date.
-- ============================================================================

CREATE OR REPLACE TABLE edw_dev.mosaic_intelligence_ext.practice_reference
COMMENT 'One row per practice: Mosaic General Survey NPS (restricted to the 18 practices with n>=15 respondents - every one is net-negative, none are above water) and real US Capture enablement dates from Capture Deployment Tracker.xlsx / US Capture Phase 3 Deployment Status.xlsx (soft_launch = first champion-rad go-live, full_enablement = all-rad go-live, prefer full_enablement when both present). opted_out=true means the practice was fully enabled for Capture then explicitly reverted (CRC, RP Borderlands only). A practice missing survey_n has no qualifying survey sample; a practice missing both date columns has no known real Capture date and the app falls back to a "first captured exam" EDW proxy for it.'
AS SELECT * FROM VALUES
  ('RIMA',               32,   -25.0, 6.41, DATE'2026-03-12', DATE'2026-06-11', false),
  ('DR',                 19,   -26.3, 6.00, CAST(NULL AS DATE), CAST(NULL AS DATE), CAST(NULL AS BOOLEAN)),
  ('ESR Metro Hudson',   16,   -31.3, 5.88, DATE'2026-03-11', DATE'2026-06-02', false),
  ('Greensboro',         25,   -40.0, 5.44, DATE'2026-03-10', DATE'2026-06-02', false),
  ('DRSRP',              39,   -41.0, 5.69, CAST(NULL AS DATE), CAST(NULL AS DATE), CAST(NULL AS BOOLEAN)),
  ('CRC',                51,   -43.1, 5.24, DATE'2026-01-26', DATE'2026-05-21', true),
  ('MIA',                18,   -50.0, 5.44, CAST(NULL AS DATE), CAST(NULL AS DATE), CAST(NULL AS BOOLEAN)),
  ('Matrix',             75,   -52.0, 4.53, DATE'2026-03-10', DATE'2026-05-20', false),
  ('RAF',                39,   -53.8, 4.62, DATE'2026-03-10', DATE'2026-05-26', false),
  ('ESR Long Island',    20,   -60.0, 4.05, DATE'2026-03-19', DATE'2026-06-02', false),
  ('Jefferson',          30,   -60.0, 3.60, CAST(NULL AS DATE), DATE'2026-05-22', false),
  ('MBB',                23,   -60.9, 4.35, DATE'2026-03-12', CAST(NULL AS DATE), false),
  ('SEAL Team',          40,   -62.5, 5.15, DATE'2026-03-06', CAST(NULL AS DATE), false),
  ('RP Gulf Coast',      19,   -68.4, 4.37, DATE'2026-03-20', DATE'2026-06-01', false),
  ('RP Florida',         16,   -68.8, 4.88, DATE'2026-03-17', DATE'2026-05-20', false),
  ('Rad Alliance',       37,   -75.7, 3.24, CAST(NULL AS DATE), DATE'2026-05-19', false),
  ('RP Chicago',         17,   -88.2, 2.94, DATE'2026-03-11', DATE'2026-05-29', false),
  ('Lakefront Imaging',  15,   -93.3, 2.27, DATE'2026-03-11', CAST(NULL AS DATE), false),
  ('ADI',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-19', false),
  ('ADR',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-02', DATE'2026-06-03', false),
  ('ARA',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-05-04', CAST(NULL AS DATE), false),
  ('Access Alexandria',  CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-06', DATE'2026-05-22', false),
  ('Access Lake Charles',CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-06', DATE'2026-05-19', false),
  ('Baylor',             CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-19', CAST(NULL AS DATE), false),
  ('CIR',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-04-02', DATE'2026-06-15', false),
  ('CIRPA',              CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-01-26', CAST(NULL AS DATE), false),
  ('Coastal',            CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-16', DATE'2026-06-04', false),
  ('Community',          CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-24', CAST(NULL AS DATE), false),
  ('GLI',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-09', DATE'2026-06-04', false),
  ('IAM',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-19', CAST(NULL AS DATE), false),
  ('IAMSE Hurley',       CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-19', CAST(NULL AS DATE), false),
  ('RP Bluegrass',       CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-17', CAST(NULL AS DATE), false),
  ('RP Borderlands',     CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-23', DATE'2026-05-21', true),
  ('RP Cascade',         CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-06-04', false),
  ('RP Corpus Christi',  CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-06-01', false),
  ('RP Crossroads',      CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-09', CAST(NULL AS DATE), false),
  ('RP Dallas',          CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-22', false),
  ('RP Eagle',           CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-01-26', DATE'2026-06-02', false),
  ('RP El Paso',         CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-06-04', false),
  ('RP Houston',         CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-23', DATE'2026-06-01', false),
  ('RP Kentucky',        CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-02-27', CAST(NULL AS DATE), false),
  ('RP NWIR',            CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-23', DATE'2026-06-15', false),
  ('RP North Florida',   CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-21', false),
  ('RP SoCal',           CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-04-06', DATE'2026-06-01', false),
  ('RP Sol',             CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-04-03', DATE'2026-05-27', false),
  ('RP South Carolina',  CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-23', DATE'2026-06-11', false),
  ('RP West Florida',    CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-25', false),
  ('Red Rock',           CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-12', CAST(NULL AS DATE), false),
  ('SOAR',               CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-18', CAST(NULL AS DATE), false),
  ('SVDI',               CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-12', DATE'2026-06-01', false),
  ('Western Colorado',   CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-22', false),
  ('Mountain',           CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-22', false),
  ('NEOH',               CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-05-21', false),
  ('PRA',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DATE), DATE'2026-06-01', false),
  ('RAC',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-01-26', CAST(NULL AS DATE), false),
  ('RACSW',              CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-01-26', CAST(NULL AS DATE), false),
  ('RAI',                CAST(NULL AS INT), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), DATE'2026-03-23', DATE'2026-06-04', false)
AS t(practice, survey_n, survey_nps, survey_mean, capture_soft_launch_date, capture_full_enablement_date, capture_opted_out);
