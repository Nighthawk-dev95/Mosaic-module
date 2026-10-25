# Mosaic Volume Report — PBI Measure Inventory

Source TMDL: `mosaic_volume_tmdl/tables/Daily_Extract.tmdl` (223 measures) and
`mosaic_volume_tmdl/tables/Resident Utilization.tmdl` (12 measures), exported from the live
"Mosaic Volume Report" semantic model.

**IMPORTANT CAVEAT ON SCOPE** — the reference YAML this inventory was originally meant to read
from (`mv_mosaic_volume_reference.yaml`) was written to disk slightly too late for this inventory
to see it, so it was built instead from: (1) a verbal structural description of that prior
reference effort, (2) the installed `databricks-metric-views` skill's YAML spec
(`create-patterns.md`), and (3) two reachable, live reference views —
`edw_prod.enterprise_analytics.mosaic_drafting_metric_vw` (`SHOW CREATE TABLE`, full YAML read) and
`backend/app/services/mosaic_service.py` (read in full).

**CORRECTED after a first pass** — this inventory/draft SQL originally claimed Unity Catalog
metric views have no `parameters:` block, based on the installed skill's doc, which turned out to
be stale (it predates the feature). A `parameters: - name: days_back, data_type: int, default: 14`
block **is** real and supported (confirmed via live Databricks docs,
https://docs.databricks.com/aws/en/uc-semantics/metric-views/use-parameters, and this workspace's
serverless warehouse running DBSQL 2026.39, well past the documented DBR 18.2 floor) — and is now
present in both views in `015_create_mosaic_volume_metric_views_DRAFT.sql`, applied specifically to
the measures PBI itself treated as rolling-window KPIs (named `... In Window` in the SQL: exam/
RPCE/drafting counts, RVU/TBWU, US/BD capture, CA Lung Screener, Mammo, IR). Query these via
`mosaic_volume_metric_view(N)`/`mosaic_resident_utilization_metric_view(N)` as a table-valued
function (argument omitted = default 14), not a plain `WHERE days_back = N` filter. Every OTHER
PBI measure that only differed from a sibling by a hardcoded window and wasn't one of PBI's
dedicated "In Window" KPIs is still marked `duplicate-of` a single all-time, unwindowed measure,
with `Final Date`/`Final Week`/`Final Month` exposed as dimensions for any other custom date range
— that part of the original design was sound and is unchanged. The per-row "New Metric View
Measure Name" below predates this fix for the window-specific rows; cross-check those specific
names (e.g. `Exams In Window`, `US Capture Eligible In Window`) against the final `... In Window`
names in the SQL file itself, which is the source of truth.

**Second architecture note, flagged per-row below as "ROLLUP-GAP"** — roughly a dozen PBI measures
("Fully Utilizing ... (Rad)", "Count Fully Utilizing ...", "% of Rads Utilizing ...") are a
**second-order aggregation**: a per-radiologist rate (e.g. % drafted) is computed first, then
radiologists are counted against a threshold on *that* rate (>=80%, >=3 exams). A flat metric-view
measure aggregates once per query, so this can't be expressed as a single measure; it needs a
two-step query (group by NPI using this view's own measures, then threshold-filter the result) —
exactly the pattern `backend/app/services/mosaic_service.py` already uses in Python for its
roster/scorecard functions. These are listed as "business" with a ROLLUP-GAP note, not excluded,
since the underlying building-block measures are still real and portable.

**Third gap, flagged "BLOCKED (Dataverse)"** — a cluster of measures (AD Group dates, "Is On X
Drafting", "Drafting Group Filter", "In Pipeline Table", "Has Drafted But Not On Drafting") joins
to `vrarp_radpipeline`, which is sourced from the raw Dataverse `rad_pipeline`/AD-group table. Per
memory (`dataverse_connect_blocked_on_admin_consent.md`), that source is not reachable from this
app's grants. `rad_drafting_enabled_flag` on `tbl_exam_inventory` is the only available proxy
(same one-directional-soundness caveat as documented on `mosaic_drafting_metric_vw`).

Column mappings used throughout (verified live against `tbl_exam_inventory_columns_only.txt` and/or
`discover-schema`/`SELECT DISTINCT`):
`NPI`→`reading_provider_npi`, `modality_code`→`exam_Modality_Code`, `Mosaic Exam Flag`/`Mosaic_flag`→`mosaic_read_flag`
(boolean), `mosaic_draft_flag`→`mosaic_draft_flag` (boolean), `Source_System_Code`→`Source_System_Code`
(confirmed live: `rpceMidwest`/`rpceSouthwest` still present), `best_rvu`→`best_wrvu`, `RVU`/`RVU-decimal`→`estimated_wrvu`,
`TBWU`→`final_TBWU`, `Allocated_WU`→`allocated_tbwu_current`, `Clinical_Procedure_Code`/`Drafteligiblecode`→
`RPID_Procedure_Code` (RPID22 confirmed live = "CT HEAD WITHOUT IV CONTRAST"), `Calendar_Date`/`Date`/`Final_DateTime - Date`→
`final_datetime`/`CAST(final_datetime AS DATE)` (matches `mosaic_service.py`'s own convention throughout),
`Drafteligiblecode`/`drafteligibleproc` code-list membership → join to `edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw`
on `RPID_Procedure_Code` (confirmed live, exactly 7 `drafting_model` categories: CT Abd/Pel, CT Chest, CT Head, CT Spine,
DEXA Capturable, US Capturable, XR/MSK — covers every hardcoded RPID list in the TMDL), `VRAname`/`Commnotetimestamp`+
`assisted_flag`→ `VRA_Flag` (single boolean, compound condition assumed already baked in upstream — flagged per-row),
`Place_Of_Service_Name`→ no exact match; `care_setting` is the closest live column but its value set (Outpatient/ED/
Inpatient/Pre-Admit/Observation/Unknown/Recurring Patient) does not line up 1:1 with PBI's POS strings — flagged.
`Allocated_RVU` and `Adjusted_Best_RVU` have **no equivalent column** anywhere in `tbl_exam_inventory` (checked the full
280-line column list twice) — every measure built from them is marked as a genuine gap, not guessed.

Legend: **B**=business, **DS**=disconnected-slicer, **DT**=dynamic-title, **TD**=test/debug, **D**=duplicate-of.

## Daily_Extract (223 measures)

| PBI Measure Name | Source Table | Category | New Metric View Measure Name | Notes |
|---|---|---|---|---|
| Best | Daily_Extract | B | Best RVU | `best_rvu`→`best_wrvu`. Hidden helper in PBI; promoted to a first-class atomic measure. |
| WU | Daily_Extract | B | TBWU | `TBWU`→`final_TBWU` (confirmed via `mosaic_service.py`'s capacity CTE: `e.final_TBWU AS RP_TBWU`). |
| wRVU est | Daily_Extract | B | Estimated RVU | `RVU`→`estimated_wrvu` (confirmed via `mosaic_service.py`: `e.estimated_wrvu AS Estimated_RVU`). |
| Adj_Best | Daily_Extract | B | — (GAP) | `Adjusted_Best_RVU` has no column equivalent in `tbl_exam_inventory`. Needs data-engineering follow-up. |
| adj_wRVU est | Daily_Extract | B | — (GAP) | `Allocated_RVU` has no column equivalent. Needs data-engineering follow-up. |
| adj_WU | Daily_Extract | B | Allocated TBWU | `Allocated_WU`→`allocated_tbwu_current` (TBWU side does have an "allocated" variant, unlike the RVU side). Flagged assumption, not 100% certain the "_current" suffix is the intended one vs plain `allocated_tbwu`. |
| Mosaic Exam % | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams. |
| Total Exam Ct | Daily_Extract | D | Exam Count | duplicate-of Exam Count. |
| Mosaic Exam Ct | Daily_Extract | B | Mosaic Exam Count | `COUNT(*) FILTER (WHERE mosaic_read_flag)`. |
| All Exam Ct | Daily_Extract | D | Exam Count | `ALL()` override is a no-op once there's no PBI filter context; duplicate-of Exam Count. |
| % Mosaic Exams Last 7 Days | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, windowed via `Final Date` filter at query time instead of a hardcoded 7. |
| RPCE as % of Clinical | Daily_Extract | B | Pct RPCE Of All Exams | New ratio = RPCE Exam Count / Exam Count (the two switcher measures it wraps are themselves DS). |
| % of RPCE | Daily_Extract | B | Pct RPCE Reporting | Matches `mosaic_service.py`'s existing `_RPCE_PCT_ADJUSTMENT` (+0.02) convention exactly. |
| % of RPCE XR | Daily_Extract | B | — (apply Modality='CR' filter to Pct RPCE Reporting) | **Formula inconsistency to flag**: this one has NO +0.02 adjustment unlike the company-wide version. Confirm with business owner whether that's intentional before porting as a straight dimension filter. |
| # of Mosaic Rads | Daily_Extract | B | Mosaic Radiologist Count | `COUNT(DISTINCT reading_provider_npi) FILTER (mosaic_read_flag)`. |
| # of RPCE Rads | Daily_Extract | B | RPCE Radiologist Count | `COUNT(DISTINCT npi) FILTER (RPCE source)`. |
| % of Rads | Daily_Extract | B | Pct Mosaic Of RPCE Radiologists | Mosaic Radiologist Count / RPCE Radiologist Count. |
| First Mosaic Case | Daily_Extract | B | First Mosaic Exam Date | `MIN(final_date) FILTER (mosaic_read_flag)`, grouped by NPI at query time. |
| first case | Daily_Extract | D | First Mosaic Exam Date | duplicate-of First Mosaic Exam Date — alternate `ALLEXCEPT`/`REMOVEFILTERS` implementation of the same thing. |
| examslast14days | Daily_Extract | D | Exam Count | duplicate-of Exam Count, windowed. |
| mosaiceamslast14days | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count, windowed. |
| % Mosaic Exmas last 14 days | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, windowed. |
| Is mosaic exam selected | Daily_Extract | DS | — | `IF(SELECTEDVALUE('Mosaic Metric'...))`, pure slicer-state flag. |
| Total mosaic exams | Daily_Extract | D | Mosaic Exam Count | PBI's own `[selecteddays]`-parameterized version; duplicate-of Mosaic Exam Count windowed by `Final Date` filter — this is the exact pattern the new metric view replaces the parameter with. |
| % Mosaic Exams | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams. |
| examslast7days | Daily_Extract | D | Exam Count | duplicate-of Exam Count, windowed. |
| mosaicexxamslast7days | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count, windowed. |
| mosaicexams%last7days | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, windowed. |
| % Mosaic Exams Last N Days | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, windowed — PBI's own generic version, absorbed the same way. |
| Dynamic Title | Daily_Extract | DT | — | String concatenation with `SELECTEDVALUE`, becomes frontend label logic later. |
| Left Total | Daily_Extract | DS | — | `SWITCH` on Mosaic Metric/Date Selector slicer values between 3 real measures. |
| Dynamic Mosaic Title | Daily_Extract | DT | — | String concatenation. |
| Left Total Header | Daily_Extract | DT | — | String concatenation. |
| totalradslive | Daily_Extract | D | Deployed Radiologist Count | duplicate-of Deployed Radiologist Count (ROLLUP-GAP cluster — see Fully Adopted below), FullyAdoptedSlicer-interaction variant. |
| EligibleProviders | Daily_Extract | D | Deployed Radiologist Count | duplicate-of Deployed Radiologist Count, FullyAdoptedSlicer variant. |
| IsFullyAdopted | Daily_Extract | B | Fully Adopted Radiologist Count (building block) | ROLLUP-GAP — per-exam boolean that only resolves per-NPI; root logic for the Fully Adopted cluster. |
| Fullyadoptedrads | Daily_Extract | B | Fully Adopted Radiologist Count | ROLLUP-GAP — `>=14 days since go-live AND >=80% Mosaic in trailing 14d`; needs a 2-step query (group by NPI, then threshold). |
| clinicalofmosaicreporting | Daily_Extract | DS | — | `SWITCH([SelectedMeasure]...)` between Pct Mosaic Exams and a new Pct Mosaic RVU. |
| Mosaicreportingrvu | Daily_Extract | D | Estimated RVU | Exact duplicate of `rvu_mosaic` — identical DAX body (`SUM(RVU-decimal) WHERE Mosaic Exam Flag=1`). |
| % of Mosaic XR | Daily_Extract | DS | — | `SWITCH([SelectedMeasure]...)`, Modality='CR' scoped. |
| Selected measure | Daily_Extract | DS | — | `SWITCH(SELECTEDVALUE('Measureselector'...))` between Exam Ct and RVU-decimal. |
| rvu_mosaic | Daily_Extract | B | Estimated RVU (component of Pct Mosaic RVU) | Achieved via `Estimated RVU` filtered on `mosaic_read_flag` dimension at query time, not a separate stored measure. |
| selectedmeasure | Daily_Extract | DS | — | `SELECTEDVALUE('Measureselector'[Measure], "Exam Count")` — the slicer-state string itself. |
| DynamicMosaicCases | Daily_Extract | DS | — | `SWITCH` on `[SelectedMeasure]`. |
| DynamicTotalMosaicFullyadopted | Daily_Extract | DS | — | Wraps the Fully Adopted rollup + `selectedmeasure` switch. |
| RPCEEXAMS | Daily_Extract | D | RPCE Exam Count | duplicate-of RPCE Exam Count. |
| RPCERVU | Daily_Extract | B | Estimated RVU (component) | Achieved via dimension filter (RPCE source), not a separate stored measure. |
| DynamicRPCECases | Daily_Extract | DS | — | `SWITCH` on `[selectedmeasure]` between RPCEEXAMS/RPCERVU. |
| DynamicClinicalcases | Daily_Extract | DS | — | `SWITCH` on `[selectedmeasure]`. |
| Totalproviders_week | Daily_Extract | B | Distinct Radiologist Count | `COUNT(DISTINCT npi)` grouped by `Final Week` dimension at query time instead of a hand-rolled `WeekStart` var. |
| Mosaic Drafting Ct | Daily_Extract | D | Drafting Exam Count | duplicate-of Drafting Exam Count, windowed by `[selecteddays]` → query-time `Final Date` filter. |
| totalradslivedrafting | Daily_Extract | B | Drafting Radiologist Count | `COUNT(DISTINCT npi) FILTER (mosaic_draft_flag)`. |
| rvu_mosaicdrafting | Daily_Extract | B | Estimated RVU (component of Pct Drafting RVU) | Dimension-filtered (`mosaic_draft_flag`), not a separate stored measure. |
| DynamicMosaicCasesDrafting | Daily_Extract | DS | — | `SWITCH` on `[SelectedMeasure]`. |
| clinicalofmosaicdrafting | Daily_Extract | DS | — | ratio of two DS switchers. |
| % of Mosaicdrafting XR | Daily_Extract | DS | — | `SWITCH([SelectedMeasure]...)`, Modality='CR' scoped. |
| % of RPCE_drafting | Daily_Extract | B | Pct RPCE Drafting | Matches `_RPCE_PCT_ADJUSTMENT` (+0.02) convention. |
| firstdraft | Daily_Extract | B | — (BLOCKED, Dataverse) | Gates on `vrarp_radpipeline` AD-group-date presence. Proxy available: First Mosaic Drafting Exam Date (drops the AD-group gate). |
| MosaicdraftCt | Daily_Extract | B | — (BLOCKED, Dataverse) | Same AD-group gate as above. Proxy: Drafting Exam Count. |
| % Mosaic drafting Last N Days | Daily_Extract | D | Pct Drafting Exams | duplicate-of Pct Drafting Exams, windowed. |
| Dynamic Mosaic Title Drafting | Daily_Extract | DT | — | String concatenation. |
| % Mosaic drafting | Daily_Extract | D | Pct Drafting Exams | duplicate-of Pct Drafting Exams. |
| Adj_Bestrvureporting | Daily_Extract | B | — (GAP) | `Adjusted_Best_RVU` has no equivalent column. |
| Adj_Bestrvudrafting | Daily_Extract | B | — (GAP) | Same gap. |
| Adj_estrvudrafting | Daily_Extract | B | — (GAP) | `Allocated_RVU` has no equivalent column. |
| Adj_estrvureporting | Daily_Extract | B | — (GAP) | Same gap. |
| Adjwu_reporting | Daily_Extract | D | Allocated TBWU | duplicate-of Allocated TBWU, dimension-filtered (`mosaic_read_flag`). |
| Adjwu_drafting | Daily_Extract | D | Allocated TBWU | duplicate-of Allocated TBWU, dimension-filtered (`mosaic_draft_flag`). |
| Bestrvu_reporting | Daily_Extract | D | Best RVU | duplicate-of Best RVU, dimension-filtered. |
| Bestrvu_drafting | Daily_Extract | D | Best RVU | duplicate-of Best RVU, dimension-filtered. |
| TBWU_reporting | Daily_Extract | D | TBWU | duplicate-of TBWU, dimension-filtered. |
| TBWU_drafting | Daily_Extract | D | TBWU | duplicate-of TBWU, dimension-filtered. |
| wrvuest_reporting | Daily_Extract | D | Estimated RVU | duplicate-of Estimated RVU, dimension-filtered (also an exact dup of `rvu_mosaic`). |
| wrvuest_drafting | Daily_Extract | D | Estimated RVU | duplicate-of Estimated RVU, dimension-filtered (also an exact dup of `rvu_mosaicdrafting`). |
| Row Count (Dynamic) | Daily_Extract | DS | — | Filters on `Placeofserviceslicer` selection. |
| Provider Count | Daily_Extract | DS | — | Threshold driven by `Mosaic Exam Count Table` slicer. |
| SelectedMonthsText | Daily_Extract | DT | — | Formats a date-range label string. |
| Maxrows | Daily_Extract | TD | — | `CALCULATE(COUNTROWS(...), ALL(...))` — sanity-check/dev helper, not a reporting metric. |
| % drafting Exams | Daily_Extract | D | Pct Drafting Exams | duplicate-of Pct Drafting Exams. |
| Draftingexamslat14days | Daily_Extract | D | Drafting Exam Count | duplicate-of Drafting Exam Count, windowed. |
| %Draftinglast 14days | Daily_Extract | D | Pct Drafting Exams | duplicate-of Pct Drafting Exams, windowed. |
| EligibleProvidersnum | Daily_Extract | D | Fully Adopted Radiologist Count | duplicate-of Fully Adopted Radiologist Count, alt threshold-boundary variant. |
| fullyadoptednew | Daily_Extract | D | Pct Fully Adopted Radiologists | duplicate-of Pct Fully Adopted Radiologists. |
| totalradslivedep | Daily_Extract | B | Radiologists With Any Mosaic Activity Count | Distinct concept — counts "fully live" OR "partially live" (>1% and <=98% mosaic), not the 80%/14-day Fully Adopted test. ROLLUP-GAP (needs per-NPI rate first). |
| totalfullyadoptedmonthdd | Daily_Extract | D | Fully Adopted Radiologist Count | duplicate-of Fully Adopted Radiologist Count, month-aware window variant. |
| pctfullyadopredmonthaware | Daily_Extract | D | Pct Fully Adopted Radiologists | duplicate-of Pct Fully Adopted Radiologists. |
| TotalRadsLive_ByAdoption_Final2 | Daily_Extract | D | Deployed Radiologist Count | duplicate-of Deployed Radiologist Count, FullyAdoptedSlicer-interaction variant. |
| PctFullyAdopteddisclinew | Daily_Extract | D | Pct Fully Adopted Radiologists | duplicate-of Pct Fully Adopted Radiologists. |
| TotalRadsLiverespectingeverything | Daily_Extract | D | Deployed Radiologist Count | duplicate-of Deployed Radiologist Count. |
| %reportingadj | Daily_Extract | B | Pct Mosaic Reporting (Rolling Window Since Go-Live) | Composed at query time from First Mosaic Exam Date + Exam Count/Mosaic Exam Count filtered to a rolling 14-day-since-go-live window per NPI — not a single flat measure, same composition style as the capacity-baseline CTEs already in `mosaic_service.py`. |
| Total_headct | Daily_Extract | D | Exam Count | duplicate-of Exam Count filtered `RPID_Procedure_Code='RPID22'` / Drafting Model Category='CT Head'. |
| headct_reporting | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count, same CT Head filter. |
| hEADCT_Drafting | Daily_Extract | D | Drafting Exam Count | duplicate-of Drafting Exam Count, same CT Head filter. |
| Pct_HeadCT_reporting | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, same CT Head filter. |
| Pct_Headct_drafting | Daily_Extract | D | Pct Drafting Exams | duplicate-of Pct Drafting Exams, same CT Head filter. |
| rpce_Ct_head_co | Daily_Extract | D | RPCE Exam Count | duplicate-of RPCE Exam Count, filtered to RPID22. |
| Pct_ct_head_rpce | Daily_Extract | B | Pct Head CT RPCE | Distinct ratio (RPCE Head-CT / Total Head-CT, no +0.02) — kept as its own measure, parallel to Pct CT RPCE below. |
| Avg RVUs per Month (Last 12 Months) | Daily_Extract | D | Estimated RVU | duplicate-of Total RVUs (Last 12 Months); "per month" division (÷12) dropped — consumer averages across however many calendar months are in view. |
| Avg TBWU per Month (Last 12 Months) | Daily_Extract | D | TBWU | duplicate-of Total TBWU (Last 12 Months), same note. |
| Avg TBWU per Month (Last 3 Months) | Daily_Extract | D | TBWU | duplicate-of Total TBWU (Last 3 Months). |
| Avg RVUs per Month (Last 3 Months) | Daily_Extract | D | Estimated RVU | duplicate-of Total RVUs (Last 3 Months). |
| Total RVUs (Last 12 Months) | Daily_Extract | D | Estimated RVU | duplicate-of Estimated RVU, windowed + grouped by NPI at query time. |
| Total TBWU (Last 12 Months) | Daily_Extract | D | TBWU | duplicate-of TBWU, windowed. |
| Total TBWU (Last 3 Months) | Daily_Extract | D | TBWU | duplicate-of TBWU, windowed. |
| Total RVUs (Last 3 Months) | Daily_Extract | D | Estimated RVU | duplicate-of Estimated RVU, windowed. |
| EligibleExams | Daily_Extract | D | (see `mosaic_drafting_metric_vw`.`Draftable Exam Count`) | Superseded by the already-reachable `mosaic_drafting_metric_vw` — same business logic, proven there; not re-derived here to avoid two definitions of "draftable" (one-fact-source principle). |
| Mosaicexamselg | Daily_Extract | D | (see `mosaic_drafting_metric_vw`) | Superseded — approx. `Mosaic Read Exam Count` intersected with draftability there. |
| mosaicdraftexamselg | Daily_Extract | D | (see `mosaic_drafting_metric_vw`.`Drafted Exam Count`) | Superseded. |
| %Drafted of eligible exams | Daily_Extract | D | (see `mosaic_drafting_metric_vw`.`Drafting Adoption Rate`) | Superseded — identical concept, already shipped and validated there. |
| %Drafted of Mosaic Exams | Daily_Extract | D | (see `mosaic_drafting_metric_vw`, approx `Drafting Coverage`) | Superseded; formula differs slightly (denominator here is eligible-and-mosaic vs. mosaic-read there) — flag if exact parity matters. |
| VRA Prepped Exams | Daily_Extract | B | VRA Prepped Exam Count | `assisted_flag + (VRAname or Commnotetimestamp not blank)` collapsed onto the single `VRA_Flag` boolean — assumption flagged, no separate assisted/name/timestamp columns found on `tbl_exam_inventory`. |
| % VRA Prepped of Total Exams | Daily_Extract | B | Pct VRA Prepped Of Exams | ratio. |
| % VRA Prepped Mosaic Exams | Daily_Extract | B | Pct VRA Prepped Of Mosaic Exams | ratio. |
| VRA Prepped Mosaic Exams | Daily_Extract | B | VRA Prepped Mosaic Exam Count | `COUNT(*) FILTER (VRA_Flag AND mosaic_read_flag)`. |
| MosaicdraftCt XR | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered Drafting Model Category='XR/MSK' (name says "draft" but has no draft-flag condition in the DAX). |
| Total Drafted XR | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered XR/MSK + Modality='CR'; original has no eligibility filter, slightly broader population — minor discrepancy flagged. |
| MosaicdraftCt CT | Daily_Extract | D | Exam Count | duplicate-of Exam Count filtered CT Head (`Drafteligiblecode='RPID22'`) — again no draft-flag condition despite the name. |
| Total Drafted CT | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered CT Head. |
| %reportingelig | Daily_Extract | B | Pct Mosaic Reporting (Eligible Basis, Rolling Window) | Composed measure, excludes BD/MG modalities, TGHI/Tampa sites, lung-screening codes; same composition caveat as %reportingadj. |
| %XR Drafable | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered XR/MSK. |
| % CT Draftable | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered CT Head (name is misleading). |
| Provider Count RSS | Daily_Extract | DS | — | Multi-slicer-driven distinct-NPI count (Week of First Case + Drafting Group + Threshold + Utilizing>90% slicers combined). Real underlying metric is just Distinct/Deployed Radiologist Count. |
| Practice Count | Daily_Extract | DS | — | Multi-slicer-driven distinct-practice count, same pattern as above. |
| Total Mosaic Cases (All Time) | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count, no date filter applied. |
| %reportingadjagnostic | Daily_Extract | D | Pct Mosaic Reporting (Rolling Window Since Go-Live) | duplicate-of %reportingadj — NPI-agnostic (`SELECTEDVALUE` vs current-context) re-implementation of the identical measure. |
| %reportingeligagnostic | Daily_Extract | D | Pct Mosaic Reporting (Eligible Basis, Rolling Window) | duplicate-of %reportingelig, same re-implementation. |
| %mosaiceligible | Daily_Extract | D | Pct Mosaic Eligible Exams | duplicate-of Pct Mosaic Eligible Exams, company-wide/no-window variant. |
| US Capturable | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered Drafting Model Category='US Capturable' + Modality='US'. |
| Captured US | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered US Capturable + Modality='US'; original lacks the eligibility condition, slightly broader — flagged. |
| % Captured | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered US. |
| Draftable XRs per Month (Last 3m) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered XR/MSK, windowed, ÷3 dropped. |
| Draftable CTs per Month (Last 3m) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered Modality='CT' across all 4 CT drafting categories, windowed, ÷3 dropped. |
| % Draftable XRs Read in Mosaic (last 14d) | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams filtered XR/MSK-draftable, per-NPI rolling window (same composition style as %reportingadj). |
| % Draftable CTs Read in Mosaic (last 14d) | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams filtered CT-draftable, per-NPI rolling window. |
| % Eligible (Last 14d) | Daily_Extract | B | Pct Exams Eligible For Mosaic Scope | Company-wide data-quality-style measure — % of ALL exams (not just Mosaic ones) that pass the site/modality/lung-screen eligibility filter. Distinct from %mosaiceligible (that one is a Mosaic rate; this one is a coverage rate). |
| Fully Utilizing Filter | Daily_Extract | DS | — | `SELECTEDVALUE('Query (3)'[vrarp_fullyutilizingname])` status filter, joined to an external `Query (3)` table not otherwise ported. |
| Captured US (Filtered) | Daily_Extract | DS | — | Threshold-driven via `Mosaic Exam Count Table` slicer. |
| % Practice IR in Mosaic (Last 2w) | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams filtered Modality='IR', windowed. |
| Total IR Cases (Last 2w) | Daily_Extract | D | Exam Count | duplicate-of Exam Count filtered IR, windowed. |
| Total IR in Mosaic (Last 2w) | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count filtered IR, windowed. |
| % IR in Mosaic (Last 2w) | Daily_Extract | D | Pct Mosaic Exams | duplicate-of % Practice IR in Mosaic (Last 2w) — identical formula, second implementation. |
| Total US Capture Read | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered US Capturable. |
| Capture Eligible USs per Month (Last 3m) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered US Capturable, windowed, ÷3 dropped. |
| US Capture Eligible (Last 14d) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered US Capturable, windowed 14d. |
| % US Capture Read (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered US Capturable, windowed. |
| Fully Utilizing Capture (Rad) | Daily_Extract | B | — | ROLLUP-GAP — per-rad >=80% capture-read threshold, needs 2-step query. |
| Eligible Rads for Capture | Daily_Extract | B | Capture Eligible Radiologist Count | Flat `COUNT(DISTINCT npi) FILTER(...)` — NOT a rollup gap, this one is a genuine single-pass measure. |
| Rads Utilizing Capture | Daily_Extract | B | — | ROLLUP-GAP — per-rad `>=3 captured exams` threshold. |
| % of Rads Utilizing Capture | Daily_Extract | D | — | ratio of the two above; inherits ROLLUP-GAP. |
| % Capture Read Practice (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered US, grouped by practice at query time instead of a separate measure. |
| Fully Utilizing Capture (Practice) | Daily_Extract | B | — | ROLLUP-GAP, practice-level threshold. |
| Total US Capture Read Practice | Daily_Extract | D | Drafted Exam Count | duplicate-of Total US Capture Read — identical formula, grouped by practice. |
| Capture Eligible USs per Month Practice (Last 3m) | Daily_Extract | D | Draftable Exam Count | duplicate-of Capture Eligible USs per Month, grouped by practice. |
| US Capture Eligible Practice (Last 14d) | Daily_Extract | D | Draftable Exam Count | duplicate-of US Capture Eligible (Last 14d), grouped by practice. |
| Test 1 - Count Rows 4/11 | Daily_Extract | TD | — | Hardcoded one-day/one-practice debug check. |
| Test 2 - Sum Mosaic Flag 4/11 | Daily_Extract | TD | — | Same. |
| Test 3 - Distinct Accessions 4/11 | Daily_Extract | TD | — | Same. |
| MosaicCaptureCt | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered US Capturable/DEXA Capturable (Modality IN US,BD); `OnlyInvalidModalities` guard is a PBI filter-context trick, irrelevant in SQL. |
| rvu_mosaicapture | Daily_Extract | B | Estimated RVU (component of Pct Capture RVU) | Dimension-filtered, not a separate stored measure. |
| DynamicMosaicCasescapture | Daily_Extract | DS | — | `SWITCH` on `[SelectedMeasure]`. |
| clinicalofmosaiccapture | Daily_Extract | DS | — | ratio of two DS switchers. |
| % of RPCE_capture | Daily_Extract | B | Pct RPCE Capture | New measure, parallel to Pct RPCE Reporting/Drafting (+0.02), scoped to capture-eligible US/BD exams. |
| Capture Live | Daily_Extract | B | Capture Radiologist Count | `COUNT(DISTINCT npi) FILTER (mosaic_draft_flag AND Modality IN US,BD AND capture-eligible)`. |
| Count Fully Utilizing Capture | Daily_Extract | B | — | ROLLUP-GAP. |
| % Fully Utilizing Capture | Daily_Extract | D | — | ratio; inherits ROLLUP-GAP. |
| Fully Utilizing Drafting (Rad) | Daily_Extract | B | — | ROLLUP-GAP. |
| Count Fully Utilizing Drafting | Daily_Extract | B | — | ROLLUP-GAP **and** BLOCKED (Dataverse) — depends on `Mosaicdraftingeligible` which itself depends on the `vrarp_radpipeline` AD-group join. |
| % Fully Utilizing draftinmg | Daily_Extract | D | — | ratio; also references a measure named `distinctradsdraftingdynamics` that does **not exist anywhere in this table's 223 measures** — a broken/orphaned reference already present in the live PBI model. Cannot port faithfully; flagged, not guessed. |
| Total DEXA Capture Read | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered DEXA Capturable + Modality='BD'. |
| % BD Capture Read (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered BD/DEXA, windowed. |
| BD Capture Eligible (Last 14d) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered BD/DEXA, windowed. |
| BD Capture Eligible (Last 3mo) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered BD/DEXA, windowed 3mo. |
| Fully Utilizing Capture BD (Rad) | Daily_Extract | B | — | ROLLUP-GAP. |
| % BD Capture Read Practice (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of % BD Capture Read (Last 14d), grouped by practice. |
| BD Capture Eligible Practice (Last 14d) | Daily_Extract | D | Draftable Exam Count | duplicate-of BD Capture Eligible (Last 14d), grouped by practice. |
| BD Capture Eligible Practice (Last 3mo) | Daily_Extract | D | Draftable Exam Count | duplicate-of BD Capture Eligible (Last 3mo), grouped by practice. |
| Fully Utilizing BD Capture (Practice) | Daily_Extract | B | — | ROLLUP-GAP. |
| Rads Utilizing Capture BD | Daily_Extract | B | — | ROLLUP-GAP. |
| Eligible Rads for Capture BD | Daily_Extract | B | Capture Eligible Radiologist Count | duplicate-of Capture Eligible Radiologist Count, filtered Modality='BD' — flat measure, not a rollup gap. |
| % of Rads Utilizing Capture BD | Daily_Extract | D | — | ratio; inherits ROLLUP-GAP. |
| Draftable CT Abd/Pel per Month (Last 3m) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered CT Abd/Pel, windowed, ÷3 dropped. |
| Drafted CT Abd/Pel per Month (Last 3m) | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered CT Abd/Pel, windowed, ÷3 dropped. |
| Measure | Daily_Extract | TD | — | Empty/stray placeholder measure (no expression body at all) left in the live model. |
| % Drafted CT Abd/Pel read in Mosaic (last 3m) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered CT Abd/Pel. |
| % Capture Read (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered Drafting Model Category IN (US Capturable, DEXA Capturable) jointly, i.e. no single-modality restriction — the "all capture types combined" company-wide rate. |
| Drafted CT AbdPel | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered CT Abd/Pel, no window. |
| Draftable CT AbdPel | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered CT Abd/Pel, no window. |
| %Drafted Abdpel | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered CT Abd/Pel. |
| Drafting Group Filter | Daily_Extract | DS | — | Also BLOCKED (Dataverse) — depends on `Is On X Drafting` columns sourced from `vrarp_radpipeline`. |
| Total Mammo Reads by Rad (Last 14d) | Daily_Extract | D | Exam Count | duplicate-of Exam Count filtered Modality='MG', windowed. |
| Total Mammo Reads in Mosaic (Last 14d) | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count filtered MG, windowed. |
| % Mammo Reads in Mosaic (Last 14d) | Daily_Extract | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams filtered MG, windowed. |
| Total CA Lung Screener Reads by Rad (Last 14d) | Daily_Extract | D | CA Lung Screener Exam Count | duplicate-of CA Lung Screener Exam Count, windowed. |
| Total CA Lung Screener Reads in Mosaic (Last 14d) | Daily_Extract | D | CA Lung Screener Mosaic Exam Count | duplicate-of CA Lung Screener Mosaic Exam Count, windowed. |
| CA Lung Screener % Reads in Mosaic (last 14d) | Daily_Extract | D | Pct CA Lung Screener Read In Mosaic | duplicate-of Pct CA Lung Screener Read In Mosaic, windowed. |
| RefreshDate | Daily_Extract | DT | — | String concatenation of a refresh timestamp. |
| Draftable CT Chest (Last 14d) | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered CT Chest, windowed. |
| Drafted CT Chest (Last 14d) | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered CT Chest, windowed. |
| % Drafted CT Chest (Last 14d) | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered CT Chest, windowed. |
| % Mammo | Daily_Extract | D | Pct Mosaic Exams | duplicate-of % Mammo Reads in Mosaic (Last 14d), minus the window — near-identical, minor `REMOVEFILTERS(Modality)` denominator nuance flagged. |
| Threshold Filter | Daily_Extract | DS | — | `MAX('ThresholdSlicer'...)` driven row-count gate. |
| Draftable CT Chest | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable CT Chest (Last 14d), no window. |
| Drafted CTChest | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted CT Chest (Last 14d), no window. |
| % Drafted CT Chest | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of % Drafted CT Chest (Last 14d), no window. |
| Draftable CT Spine | Daily_Extract | D | Draftable Exam Count | duplicate-of Draftable Exam Count filtered CT Spine (first instance of this category — drafting_eligible_rpids_vw confirmed CT Spine is one of the 7 live categories, 13 codes). |
| Drafted CTSpine | Daily_Extract | D | Drafted Exam Count | duplicate-of Drafted Exam Count filtered CT Spine. |
| % Drafted CT Spine | Daily_Extract | D | Pct Drafted Of Draftable | duplicate-of Pct Drafted Of Draftable filtered CT Spine. |
| ct_reporting | Daily_Extract | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count filtered Modality='CT'. |
| Total_ct | Daily_Extract | D | Exam Count | duplicate-of Exam Count filtered Modality='CT'. |
| % CT | Daily_Extract | DS | — | `SWITCH([SelectedMeasure]...)` between Pct Mosaic Exams (filtered CT) and an RVU-based alternative (achievable as Estimated RVU filtered CT, not a separate stored measure). |
| CT_Drafting | Daily_Extract | D | Drafting Exam Count | duplicate-of Drafting Exam Count filtered CT. |
| % CT Drafting | Daily_Extract | DS | — | Same `SWITCH` pattern as % CT. |
| Pct_ct_rpce | Daily_Extract | B | Pct CT RPCE | New measure, parallel to Pct Head CT RPCE (RPCE CT count / Total CT count, no +0.02). |
| Test - Not On Drafting But Has Drafted Exams | Daily_Extract | TD | — | Named "Test"; also BLOCKED (Dataverse) since it reads `Is On X Drafting` columns. |
| Rads Not On Drafting With Drafted Exams | Daily_Extract | B | — | BLOCKED (Dataverse) — same `Is On X Drafting` dependency. |
| AD Group XR Date | Daily_Extract | B | — | BLOCKED (Dataverse) — reads `vrarp_radpipeline` directly. |
| AD Group CT Head Date | Daily_Extract | B | — | BLOCKED (Dataverse). |
| AD Group CT AbdPel Date | Daily_Extract | B | — | BLOCKED (Dataverse). |
| AD Group CT Chest Date | Daily_Extract | B | — | BLOCKED (Dataverse). |
| Last Drafted Exam Date | Daily_Extract | B | Last Drafted Exam Date | `MAX(final_date) FILTER (mosaic_draft_flag)` — straightforward, NOT blocked (no rad_pipeline dependency despite sitting in this cluster). |
| Has Drafted But Not On Drafting | Daily_Extract | B | — | BLOCKED (Dataverse). |
| In Pipeline Table | Daily_Extract | B | — | BLOCKED (Dataverse) — tests presence in `vrarp_radpipeline` itself. |
| NPI Check | Daily_Extract | TD | — | `MAX(Provider_NPI)` — a column-sanity debug helper. |

## Resident Utilization (12 measures)

| PBI Measure Name | Source Table | Category | New Metric View Measure Name | Notes |
|---|---|---|---|---|
| Resident Total Mosaic Exams (All Time) | Resident Utilization | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count, no date filter (`REMOVEFILTERS` on Calendar_Dt/Month is a no-op once there's no PBI filter context). |
| Resident First Mosaic Exam | Resident Utilization | B | First Mosaic Exam Date | `MIN(final_date) FILTER (mosaic_read_flag)`. |
| Resident % Mosaic Last 14d | Resident Utilization | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, windowed via `Final Date` filter instead of hardcoded `TODAY()-14`. |
| Resident % Mosaic Last 14d Eligible | Resident Utilization | D | Pct Mosaic Eligible Exams | duplicate-of Pct Mosaic Eligible Exams, windowed. |
| Fully Utilizing (Resident) | Resident Utilization | B | — | ROLLUP-GAP — per-resident >=80% threshold on Pct Mosaic Eligible Exams; needs 2-step query (group by resident NPI first, then threshold), same limitation as the practice-side Fully Adopted/Fully Utilizing clusters. |
| Count Fully Utilizing Residents | Resident Utilization | B | — | ROLLUP-GAP, same as above. |
| Exams This Period | Resident Utilization | D | Exam Count | duplicate-of Exam Count. |
| Mosaic Exams This Period | Resident Utilization | D | Mosaic Exam Count | duplicate-of Mosaic Exam Count. |
| Resident First Mosaic Draft Exam | Resident Utilization | B | First Mosaic Drafting Exam Date | `MIN(final_date) FILTER (mosaic_draft_flag)`. |
| Resident % Mosaic Exams | Resident Utilization | D | Pct Mosaic Exams | duplicate-of Pct Mosaic Exams, no window. |
| Resident % Mosaic Eligible | Resident Utilization | D | Pct Mosaic Eligible Exams | duplicate-of Pct Mosaic Eligible Exams, no window. |
| Resident FU Filter | Resident Utilization | DS | — | `SELECTEDVALUE('Resident FU Status'[Fully Utilizing])`-driven row filter. |

## Summary

- **223 + 12 = 235** PBI measures inventoried.
- **Business (ported or gap-flagged):** ~95 rows, resolving to **~41 atomic/composed measures** across
  the two new metric views (down from 235 — the consolidation the brief asked for), plus **13 rows
  marked BLOCKED (Dataverse)**, **~15 rows marked ROLLUP-GAP** (real metric, needs a 2-step query,
  not expressible as one flat measure), and **4 rows marked GAP** (no `Allocated_RVU`/`Adjusted_Best_RVU`
  column equivalent anywhere in `tbl_exam_inventory`).
- **Disconnected-slicer selectors:** ~33 rows.
- **Dynamic-title / string-concat:** 9 rows.
- **Test/debug/stray:** 9 rows.
- **Duplicate-of:** the remainder (~160 rows), absorbed into the business measures above.
