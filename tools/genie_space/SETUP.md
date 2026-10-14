# Genie Space setup — Mosaic Intelligence

Scoped against the company's 3-tier Genie Space governance model (Sandbox → Candidate →
Certified, with Bronze/Silver/Gold maturity tags). That model puts a deliberate budget on
table count ("5 core tables" at Bronze, "no out-of-scope table added" by Gold), so this
plan is trimmed to **8 core tables** — down from an earlier, uncut draft of 21+9 — by
dropping redundant assets and merging tables that share a grain.

## 0. Prerequisite — materialize the two app-only data sources

Two things the app knows about live nowhere in Unity Catalog: the compiled Mosaic
General Survey results and the real Capture enablement dates (both are just Python
literals in `backend/app/data/`). Run
[`001_create_mosaic_intelligence_ext.sql`](001_create_mosaic_intelligence_ext.sql) once
(Databricks SQL editor or a notebook cell — needs `CREATE TABLE` on `edw_dev`) to turn
them into **3** real tables under a new `edw_dev.mosaic_intelligence_ext` schema. Re-run
it (it's all `CREATE OR REPLACE`) whenever those two Python files get refreshed from
updated source workbooks.

`edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw` needs no such step — it already
exists, it just has no `mosaictechops` equivalent, so it's added to the Genie Space
directly as its own asset.

## 1. Core table scope (8 tables)

| # | Table | Schema | Domain |
|---|---|---|---|
| 1 | `mv_mosaic_deployment` | `mosaictechops` | Deployment status, funnel, blockers |
| 2 | `mv_mosaic_efficiency` | `mosaictechops` | Efficiency (RVU/TBWU per minute) vs. baseline |
| 3 | `mv_mosaic_capacity` | `mosaictechops` | Capacity (on-shift vs. baseline) |
| 4 | `mv_mosaic_volume` | `mosaictechops` | RPCE / Capture / CT-XR drafting volume |
| 5 | `examsnotdraftedbutdraftable_vw` | `bipa_analytics` | Undrafted-but-draftable exam analysis (the one true gap — no mosaictechops equivalent exists) |
| 6 | `rad_survey_summary` | `mosaic_intelligence_ext` | Survey NPS/response-rate headline + raw 0-10 histogram |
| 7 | `rad_survey_items` | `mosaic_intelligence_ext` | Every Likert/theme survey item (agreement, feature satisfaction, problems, frustration/praised themes) — one long table, `category` column discriminates |
| 8 | `practice_reference` | `mosaic_intelligence_ext` | One row per practice: survey NPS **and** real Capture enablement dates merged (same grain, natural fit) |

### What got cut, and why

Dropped entirely rather than force into the 8 above — none are required by anything
asked for, and adding them risks the Gold "no out-of-scope table added" rule later. Can
be revisited as a deliberate re-scope conversation, not a casual addition:

- **`dim_mosaic_practice`, `dim_mosaic_radiologist`** — redundant. The metric views
  already carry `Practice`/`Radiologist` as plain text columns, denormalized; a separate
  dimension join buys nothing for Genie's NL Q&A.
- **`vw_deployment_npi_bridge`, `vw_drafting_npi_bridge`, `vw_ct_abdpel_npi_bridge`** —
  redundant. `mv_mosaic_deployment` already carries `Drafting Blocker`/`CT Abd Pel
  Blocker`/status-label columns at the same NPI grain; the bridges only add `StatusRank`/
  `BlockerRank` sort helpers, not new facts.
- **`vw_mosaic_radiologist_rollup`, `vw_mosaic_enterprise_snapshot`,
  `vw_mosaic_adoption_stage_distribution`, `vw_mosaic_recently_active`,
  `vw_mosaic_active_alerts`, `mv_mosaic_readtimes`, `mv_mosaic_practice_command_center`**
  — all genuinely useful, none currently surfaced by the app and none needed to answer
  anything in scope today. Good Silver/Gold-stage candidates if a real question for them
  comes up, not Bronze-stage defaults.

Consolidated instead of added one-per-concept (see `001_create_mosaic_intelligence_ext.sql`
for exact shapes): the original 8 separate survey tables collapsed into 2
(`rad_survey_summary` + `rad_survey_items`), and the by-practice survey table merged with
`capture_enablement` into 1 (`practice_reference`), since both are practice-grain — net
9 tables down to 3.

## 2. Permissions

Genie queries as either the asker's own identity or a fixed service principal, depending
on the space's "Run as" setting. Whichever it is, it needs `USE CATALOG` on `edw_dev` and
`USE SCHEMA` + `SELECT` on `mosaictechops`, `bipa_analytics` (just for the one view above),
and the new `mosaic_intelligence_ext`. If the space is already reading `mosaictechops`
today, only the `bipa_analytics` view and the new schema need a fresh grant. Per the
governance model, this per-user/per-principal enforcement applies identically at every
tier (Sandbox through Certified) — promotion tags never substitute for real UC grants.

## 3. Promotion checklist against the 3-tier model

**Tier 1 — Sandbox:** build this space in `/Genie-Sandbox` (or your personal workspace
folder) first. Wire up the 8 tables, draft instructions/example SQL/synonyms/join hints
below, iterate freely — folder ACL is creator-only, not visible in Genie One yet.

**Tier 2 — Candidate**, in order:
- **Bronze:** set the owner tag, agree the name ("Mosaic Intelligence") and spec (this
  doc), confirm all 8 core tables exist. Move to the Candidate folder, share to REVIEWERS
  + agreed pilot users (CAN RUN).
- **Silver:** add the test instructions (§4 below), agree the metric-view references
  (the 4 `mv_mosaic_*` views), run it against reviewer test questions (§5 is a starting
  bank), get data-owner sign-off pending.
- **Gold:** add trusted SQL assets (§6), make join relationships explicit (`NPI` and
  `practice`/`Practice`/`localpractice` as the shared keys — call out that naming varies
  by table), get owner + data-owner sign-off, pass the benchmark, and confirm **no table
  beyond the 8 above got added**.

**Promotion gate:** domain expert + data owner jointly confirm, then tag Certified and
widen the ACL to the consumer group.

**Tier 3 — Certified:** shared to the consumer group, discoverable via Genie One.

## 4. General instructions (paste into the Genie Space's "Instructions" field)

> This space answers questions about Mosaic Intelligence — Radiology Partners' AI
> reporting/drafting/capture rollout — covering Deployment, Efficiency, Capacity,
> Capture/Utilization, undrafted-exam analysis, and radiologist sentiment (survey).
>
> - The `mv_mosaic_*` tables are Databricks **Metric Views** — their measure columns
>   (RVU, TBWU, counts, percentages, anything under "measure" in the schema) can only be
>   referenced inside `MEASURE(...)` or an aggregate, never selected raw. Genie generates
>   this correctly on its own; keep it in mind only if writing/checking a trusted SQL asset.
> - The grain of most tables is either **per radiologist (NPI)** or **per practice**.
>   Join on `NPI` or `Practice`/`practice`/`localpractice` (naming varies by table — treat
>   them as the same key) when a question spans two tables.
> - In `mv_mosaic_efficiency`, `Period Type` is **not** a time window — it's `Baseline`
>   (pre-Mosaic activity for that rad, `Pct Change Vs Baseline` is null on these rows),
>   `Reporting`, or `Drafting` (current Mosaic-era activity, split by mode; compare these
>   against `Baseline` rows for the same radiologist to get a real before/after). A positive
>   "vs. baseline" change is good (more efficient/higher capacity); negative is worse.
> - `mv_mosaic_efficiency`'s `Outliers` column ('Included'/'Excluded') flags rows with
>   anomalous read times — filter to `Outliers = 'Excluded'` unless the user explicitly
>   asks about outliers.
> - `rad_survey_summary` and `rad_survey_items` are a single fixed snapshot from one
>   survey wave (810 respondents, Aug-Sep 2026), not a time series — don't try to trend
>   them. `rad_survey_items.category` distinguishes agreement_statement /
>   feature_satisfaction / problem_frequency (all Likert, 1-5, use score_1..score_5/mean)
>   from frustration_theme / praised_theme (verbatim keyword tags, use `pct` only —
>   these don't sum to 100 since one response can match multiple themes).
> - `practice_reference.capture_opted_out = true` means that practice was fully enabled
>   for Capture and then explicitly reverted — treat it as a real, current state, not an
>   error. A practice with `survey_n` null had too few survey respondents (<15) to trust
>   its NPS; a practice with both capture date columns null has no known real enablement
>   date.
> - `examsnotdraftedbutdraftable_vw`'s `category` column is the reason an eligible exam
>   wasn't drafted (e.g. rad declined, ops declined, incomplete process, never opened);
>   `category_sort_order = 0` is "Drafted" itself — exclude it when asked specifically
>   about *undrafted* reasons.
> - When a question is ambiguous between "by radiologist" and "by practice", prefer
>   practice-level unless a specific NPI or radiologist name is given.

## 5. Example questions to seed

**Deployment**
- Which practices have the lowest % of radiologists live on Mosaic reporting?
- What's the most common drafting blocker across all radiologists right now?
- How many radiologists are fully enabled for CT Abd/Pel drafting?

**Efficiency / Capacity**
- Which radiologists have the biggest efficiency decline vs. their baseline this month?
- What's the average on-shift capacity (RPWU) by practice?
- Show me radiologists with high baseline capacity but negative capacity change.

**Capture / Volume**
- What percent of eligible US exams are actually being captured, by practice?
- Which practices have the biggest gap between capturable and captured exams?
- How has Mosaic drafting adoption changed over the last 90 days?

**Undrafted analysis**
- What are the top reasons eligible exams aren't getting drafted?
- How many exams were undrafted because the radiologist declined, by practice, last quarter?
- Which practices have the highest share of "never opened" undrafted exams?

**Rad sentiment (survey)**
- What's our overall Mosaic NPS, and how many promoters vs. detractors do we have?
- Which practice has the worst survey NPS?
- What are radiologists' top frustrations with Mosaic?
- How satisfied are radiologists with the Capture feature specifically?
- Is trust in Mosaic outputs higher or lower than the average agreement statement?

**Capture enablement**
- Which practices have been fully enabled for Capture the longest?
- Which practices opted out of Capture after enabling it?
- Do practices with a real Capture enablement date have better survey NPS than ones without?

## 6. Trusted assets — example SQL to seed (grounds Genie on tricky joins/terms)

```sql
-- Overall NPS + tier breakdown
SELECT nps, promoters, passives, detractors, responses, sent, response_rate
FROM edw_dev.mosaic_intelligence_ext.rad_survey_summary;

-- Worst-sentiment practices
SELECT practice, survey_n, survey_nps, survey_mean
FROM edw_dev.mosaic_intelligence_ext.practice_reference
WHERE survey_n IS NOT NULL
ORDER BY survey_nps ASC
LIMIT 5;

-- Top reasons eligible exams go undrafted (excluding "Drafted" itself)
SELECT category, SUM(exam_count) AS exams, SUM(tbwu) AS tbwu
FROM edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw
WHERE category_sort_order > 0
GROUP BY category
ORDER BY exams DESC;

-- Practices that opted out of Capture after enabling it
SELECT practice, capture_soft_launch_date, capture_full_enablement_date
FROM edw_dev.mosaic_intelligence_ext.practice_reference
WHERE capture_opted_out = true;

-- Radiologists with declining efficiency vs. baseline (Metric View - measures need MEASURE())
SELECT `Physician NPI`, Radiologist, Practice,
       MEASURE(`Pct Change Vs Baseline`) AS pct_change_vs_baseline
FROM edw_dev.mosaictechops.mv_mosaic_efficiency
WHERE `Period Type` IN ('Reporting', 'Drafting') AND Outliers = 'Excluded'
GROUP BY `Physician NPI`, Radiologist, Practice
HAVING MEASURE(`Pct Change Vs Baseline`) < 0
ORDER BY pct_change_vs_baseline ASC;

-- Top survey frustration themes
SELECT label, pct
FROM edw_dev.mosaic_intelligence_ext.rad_survey_items
WHERE category = 'frustration_theme'
ORDER BY pct DESC;
```

## 7. Suggested Genie Space name/description

- **Name:** Mosaic Intelligence
- **Description:** Ask questions about Mosaic AI reporting/drafting/capture adoption,
  efficiency, capacity, undrafted exams, and radiologist sentiment across Radiology
  Partners practices.
