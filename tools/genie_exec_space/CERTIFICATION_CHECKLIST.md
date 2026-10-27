# [DEV] Mosaic Executive: Genie certification checklist

Source: **Genie Space Best Practices & Certification Guide** (Data Warehouse + Data Strategy, Oct 2026). The deck is
`Genie_Space_Best_Practices_Certification_Guide.pptx` in the repo root.

Process: complete this checklist, submit it to the **Genie Governance group**, and address their feedback. **EDW Dev**
then applies the Certified tag. Nothing is certified without documented approval. The committee meets monthly, and the
deadline is **Jan 31, 2027**.

| | |
|---|---|
| Space | `01f1d02c5dad1f359b76e45dc3920549`, "[DEV] Mosaic Executive" |
| Folder | `/Users/bhargav.narasimhan@radpartners.com/Genie-Sandbox` |
| Linked dashboard | Lakeview `01f1d0089f5410359e87575975cb5dea` (Mosaic Executive Dashboard, 8 pages) |
| Source of truth | `tools/genie_exec_space/build_genie_space.py`. The space is never edited in the UI. |
| Author | bhargav.narasimhan@radpartners.com |
| Lifecycle stage | **Development** (author-only, CAN MANAGE) |
| Target audience | CEO, President, executive leadership (CAN RUN through an AD group after certification) |

Status as of 2026-10-27. ✅ means met. 🟡 means met with a note, or a user or committee decision is needed. ⛔ means
blocked by a dependency outside this repo.

## The 16 checklist items

| # | Item | Status | Evidence / notes | Owner |
|---|---|---|---|---|
| 1 | Not in the Prod workspace | 🟡 | There is only one workspace (`adb-7306149455716415`). The space is in the author's personal `/Genie-Sandbox` folder, not a shared or prod folder. **Ask Governance** whether a dev folder in this workspace satisfies the rule. | Governance |
| 2 | Naming convention: `[DEV]` / `[TEST]` prefix | ✅ | Titled `[DEV] Mosaic Executive`. It becomes `[TEST]` when reviewers are added, and drops the prefix once certified. | Author |
| 3 | Purpose and scope in the instructions | ✅ | The first paragraph of `INSTRUCTIONS` states the audience, solutions, metrics, and TABLE→DOMAIN routing. | Author |
| 4 | All tables from `edw_gold` or downstream | ⛔ | Every asset is in **`edw_test.enterprise_analytics`**, and several upstream sources are in **`edw_dev.bipa_analytics`**. See *Blocker A*. | Author + BIPA/EDW |
| 5 | All visible columns described | ✅ | 311 of 311 metric-view columns have a comment (verified 2026-10-27). All have a display name and synonyms (migration 050). `Exam Id` and `Allocated TBWU` are hidden in the space. | Author |
| 6 | SQL expressions for key metrics and filters | ✅ | Key **metrics** are governed `MEASURE()`s inside the 6 metric views. Re-declaring them as snippets would fork the definitions, which the Databricks guidance advises against. Reusable **filters** (last complete month per domain, YTD, not-drafted, MVP cohort) and **expressions** (quarter) are `sql_snippets`. All are executed by `--check`. | Author |
| 7 | Join relationships configured | ✅ (N/A) | By design there are no joins: each metric view is pre-joined, and rule 2 forbids joining metric views together. The deck itself recommends pre-joining into views or metric views. | Author |
| 8 | ≥10 example SQL queries | ✅ | 30 example question/SQL pairs. | Author |
| 9 | Specific plain-text instructions | ✅ | 10 numbered rules, terminology, synonyms, and per-domain notes. Reusable filters are now also SQL Expressions (item 6), which take precedence over text. | Author |
| 10 | Benchmark suite ≥20 questions | ✅ | 35 benchmarks, all with SQL answers. They cover all 6 views and 8 functions and include edge cases: a misspelling, no period given, a synonym ("capacity lift"), a date range (Q3), a region filter, the Matrix region/practice ambiguity, and top-N. | Author |
| 11 | Benchmark accuracy ≥80% | ✅ | Latest eval: see *Eval history*. Target 100%. Re-run after every change. | Author |
| 12 | Author tested 20+ questions | ✅ | 30 examples plus 35 benchmarks are executed against live data by `--check` before every push. Edge-case log below. | Author |
| 13 | Peer review completed | 🟡 | Not started. Reviewers are Karin Sanders, Naomi Hoppel, and Calli (login to be confirmed), each asking 10+ questions. See *Peer review plan*. | Author + reviewers |
| 14 | Permissions set correctly | ✅ (for the stage) | Development means author-only CAN MANAGE (verified with `databricks permissions get genie`). Testing will give reviewers **CAN EDIT** only. Production will give the audience group CAN RUN. | Author |
| 15 | SQL warehouse assigned and tagged | 🟡 | Warehouse `fe0ad987563c672a` (EDW-PROD) is assigned but has **no tags**. The warehouse owner (s.madala.priv) must add a tag. | Warehouse owner |
| 16 | No PII exposed without access controls | 🟡 | There is no patient PHI: no MRN, patient name, DOB, or accession. **Provider-level** data is exposed: radiologist name, NPI, and per-radiologist efficiency. **Governance** must confirm that the audience may see radiologist-level performance. | Governance |

### Data rules from the deck

| Rule | Status | Notes |
|---|---|---|
| ≤5 tables (50 max) | 🟡 | 6 metric views and 8 UC functions. Each metric view is one domain on the dashboard: volume, efficiency, efficiency vs RP average, capacity, drafting coverage, and MVP program. Merging them would mix different grains. **Decision:** keep 6 and justify it to the committee, or drop the program and/or draftable view to reach 5. |
| No staging / bronze / silver tables | ✅ | The space only sees metric views and functions. |
| Valid exams = `Exclusion_Reason_ID < 0` | ✅ | The volume view filters `Exclusion_Reason_Cd = 'N/A'` on `edw_prod.enterprise_analytics.tbl_exam_inventory`. For Sept 2026 this matches `Exclusion_Reason_ID < 0` row for row: 3,505,431 included, 528,094 excluded, 0 disagreements. Efficiency and capacity reproduce the PowerBI pipeline's own exam population (outliers excluded), which was proven in the PBI parity pack. |
| Exam questions start from `tbl_exam_inventory` / `accum_exam_fact` | ✅ | The volume view is built on `tbl_exam_inventory`. |
| `COMMENT ON TABLE` states grain, filters, and join path | ✅ | All 6 metric-view comments state the grain, source filters, and joins. They will need rewording from "draft / edw_test" on promotion. |

## Blockers

**A. Sources must be `edw_gold` or downstream (item 4).**
Everything the space reads must be in `edw_prod.enterprise_analytics` (or `edw_gold`).

| Asset in the space | Current chain | Needed |
|---|---|---|
| `mosaic_volume_metric_view` | edw_test view → `edw_test.dynamics_rad_drafting_enablement_by_npi_vw` + `edw_test.tbl_team_rollups` (← `edw_dev.bipa_analytics.team_rollups`) | Promote to `edw_prod`. The `team_rollups` copy in edw_prod is stale (2026-05-27, versus dev 2026-10-05). |
| `mosaic_efficiency_metric_view` + 8 `mosaic_eff_*` functions | `mosaic_efficiency_exam_level_mv` ← `tbl_efficiency_exam_level_vw` ← `tbl_exam_category_lookup_xwalk` + `tbl_team_rollups` | Promote to `edw_prod` |
| `mosaic_efficiency_vs_rp_avg_metric_view` | `tbl_efficiency_rp_avg_source_vw` ← `tbl_readtime_radiologist_metrics_shadow` ← **`edw_dev.bipa_analytics.radiologist_metrics_minexams_rtupdatedshadow`** | BIPA promotes the shadow view to prod |
| `mosaic_capacity_pbi_metric_view` | `mosaic_capacity_pbi_shift_vw` ← **`edw_dev.bipa_analytics.presentation_rpt_vra_capacity_enhancetest_vw`** + team_rollups | BIPA promotes to prod |
| `mosaic_draftable_metric_view` | `mosaic_draftable_snapshot_mv` ← **`edw_dev.bipa_analytics.examsnotdraftedbutdraftable_vw`** | BIPA promotes to prod |
| `mosaic_program_metric_view` | `edw_prod.enterprise_analytics.tbl_mvp_rad_onboarding` | Promote the view only (the source is already prod) |

Promotion plan:
1. BIPA/EDW promotes the 4 `edw_dev` sources.
2. The `edw_test` objects are re-created in `edw_prod.enterprise_analytics` as **new** objects. This is additive only,
   with no CREATE OR REPLACE, INSERT OVERWRITE, or DROP on any existing object.
3. The parity gate is re-run.
4. `S` in `build_genie_space.py` is repointed.
5. `--check`, then the eval.

This is a PROD deployment and needs explicit approval from the project owner.

**B. Warehouse tag (item 15).** The warehouse owner adds a tag to `fe0ad987563c672a`.

**C. Governance decisions:**
- Workspace / folder question (item 1)
- Radiologist-level visibility (item 16)
- Table count of 6 versus the target of 5

**D. Peer review (item 13).** Reviewers need CAN EDIT on the space, plus UC grants on the 6 views and 8 functions (see
[SHARING_READINESS.md](SHARING_READINESS.md)).

## Known limitations (to give reviewers and the committee)

- **Data freshness:**
  - Volume and efficiency are refreshed daily. The efficiency MV refreshes at 7:30 AM CT.
  - The current month is partial. With no period given, answers use the last complete month and say so.
  - The draftable view is a snapshot MV, and the MVP program data is a Dynamics CRM snapshot. Its as-of date is
    `Latest Dynamics Activity`.
- **MVP efficiency-change figures** are entered by hand in Dynamics. The answer says so.
- **Capacity:**
  - Answers follow the PowerBI Practice Summary defaults (TBWU 26 per shift, shifts with baselines only).
  - About half of shifts have no baseline and are out of scope.
  - Practices without a TBWU 26 baseline in a month are excluded, as in PowerBI.
- **Drafting efficiency** is restricted to CR/CT exams on both sides.
- **The "% of RPCE" measures** include PowerBI's +0.02 adjustment, for parity. "% of RPCE XR" does not.
- **"Matrix"** is both a Local Region and a Provider Practice. The answer states which one it used.
- **No forecasting or what-if questions.** Exam- or patient-level detail is out of scope.
- **Efficiency per practice, radiologist, or site** comes from UC functions and needs a whole-month window.

## Author testing log (edge cases)

All of these run through `--check` (the SQL executes against live data). They are also benchmarks, so the eval scores
Genie on them.

| Category | Question | Expected behaviour |
|---|---|---|
| Misspelling | "whats mosiac adoption for sept 2026" | Pct RPCE Reporting, Sept 2026 |
| No period | "How many radiologists used Mosaic?" | Last complete month, stated in the answer |
| Synonym | "How much capacity lift did Mosaic give us in September 2026?" | Pct Addl Capacity with the TBWU26 practice filter |
| Date range | "Mosaic adoption by month for Q3 2026" | 3 monthly rows, Jul–Sep |
| Region | "…drafted in Mosaic in the Maverick region in Sept 2026?" | `Local Region` = 'Maverick', Pct RPCE Drafting |
| Ambiguity | "Show the Matrix provider practice's efficiency…" | Provider Practice, with the region alternative noted |
| Top-N / threshold | "Top 5 radiologists … at least 500 Mosaic exams" | Function plus filter, ordered, LIMIT 5 |
| Named entity | "What was Taha, Manuel R's Full Mosaic efficiency change…" | Radiologist function |
| Trend | "change from August to September 2026" | 2 monthly rows |

## Peer review plan (item 13)

1. Rename the space to `[TEST] Mosaic Executive` (`TITLE`, then `--update`).
2. Give each reviewer **CAN EDIT** on the space, CAN VIEW on the dashboard, the UC grants, and warehouse CAN USE (see
   SHARING_READINESS.md).
3. Each reviewer asks **10+ questions in their own words**, ideally without reading the instructions first. They mark
   each answer 👍 or 👎 in Genie and note anything wrong.
4. The author reviews the thumbs-down answers and the `system.access.audit` log (query below). Fixes go into
   `build_genie_space.py`, and the eval is re-run.
5. Record the reviewers, dates, question counts, and outcome in the sign-off table below.

| Reviewer | Date | Questions asked | 👍 / 👎 | Issues raised → fix |
|---|---|---|---|---|
| | | | | |

## Eval history

| Date | Eval run | Benchmarks | Score |
|---|---|---|---|
| 2026-10-27 | `01f1d2229e701637b695af1bfccf6e53` | 30 | 30/30 (100%) |
| 2026-10-27 | `01f1d2300bbd10c19bc8ac3be7cd264e` | 35 (incl. 5 edge cases), with SQL Expressions | 35/35 (100%) |

## Maintenance plan (after certification)

- **Change control:**
  - Every change goes through `build_genie_space.py`, then `--check`, then `--update`, then the eval.
  - Accuracy must stay ≥80% (target 100%).
  - Metric-view metadata changes go through `tools/edw_fixes/metric_view_metadata/*.json` and
    `_enrich_metric_view_metadata.py`.
- **Monthly review** of feedback and usage:
  ```sql
  SELECT event_date, user_identity.email, action_name, request_params
  FROM system.access.audit
  WHERE service_name = 'aibiGenie'
    AND request_params['space_id'] = '01f1d02c5dad1f359b76e45dc3920549'
    AND event_date >= current_date() - INTERVAL 30 DAYS
  ORDER BY event_time DESC
  ```
- **Benchmarks** are re-run after any change to the space, the metric views, or the upstream sources, and at least
  monthly. The benchmark dates are anchored to Sept 2026 so the expected answers do not drift.

## Deprecation steps (when retired)

1. Set the status to **Deprecated**; the Retiring stage is read-only for existing users.
2. Add an instruction pointing to the replacement space.
3. Revoke access, then delete the space (Decommissioned stage).
