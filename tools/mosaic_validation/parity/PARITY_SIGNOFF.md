# Mosaic Executive Dashboard — PBI parity sign-off (Tier A: Volume)

Generated 2026-10-25 by `run_parity.py`. Closed months 2026-07-01 to 2026-10-01 (exclusive).

- **Reference:** PBI's own import query `edw_dev.bipa_analytics.presentation_mosaicdailyvolume_vw` with each DAX measure replicated in SQL (see `kpi_registry.yaml`). PBI Local is regenerated from the `column Local` SWITCH in `Daily_Extract.tmdl`.
- **Databricks:** `edw_test.enterprise_analytics.mosaic_volume_metric_view` governed measures (what the dashboard and Genie read).
- **Tolerance:** counts MATCH = exact, NEAR = within 0.05% (source refresh timing); percentages NEAR = within 0.05pp. KNOWN DIVERGENCE = outside tolerance but fully explained by a documented rule below (re-checked with the rule's adjustment applied). BUG = outside tolerance and unexplained.

## Known divergences (documented)

- **`imagine_non_rpce`** (32 rows) — Imagine-* source systems (Imagine-SAPA, Imagine-MIAB, Imagine-MBBAC, ...) are in tbl_exam_inventory but not in PBI's exam_fact. They are non-RPCE, so every RPCE KPI and % is unaffected; only the all-source Clinical exams count is higher (RP RAH exists only because of them).
- **`case_count_weighting`** (37 rows) — PBI sums [Exam Ct] (exam_fact.Case_Count), so a multi-case exam counts 2+; the metric view counts exams. PBI's % of RPCE (Drafting) also divides that case-weighted numerator by an exam-count denominator. Not replicated: it needs exam_fact joined into the view, and the exam count is the consistent definition. Visible only in small practices (RP Chicago, DR).
- **`rp_houston_exam_fact_gap_2026_08`** (1 rows) — ~27 rpceSouthwest exams (21 of them Mosaic; Aug 2026, valid NPI/team/site) are in tbl_exam_inventory but absent from PBI's exam_fact entirely -- a source-load gap on the PBI side, not a logic difference.

## Company-wide

| Month | Member | KPI | PBI | Databricks | Diff | Status |
|---|---|---|---:|---:|---:|---|
| 2026-07 | ALL | Clinical exams | 3,539,389 | 3,540,422 | +1,033 | NEAR |
| 2026-07 | ALL | RPCE exams | 3,048,121 | 3,048,127 | +6 | NEAR |
| 2026-07 | ALL | Mosaic exams (reporting) | 2,237,229 | 2,237,235 | +6 | NEAR |
| 2026-07 | ALL | % of RPCE (Reporting) | 75.40% | 75.40% | +0.000pp | NEAR |
| 2026-07 | ALL | Mosaic drafting exams | 1,012,826 | 1,012,805 | -21 | NEAR |
| 2026-07 | ALL | % of RPCE (Drafting) | 35.23% | 35.23% | -0.001pp | NEAR |
| 2026-07 | ALL | Mosaic capture exams | 121,354 | 121,354 | +0 | MATCH |
| 2026-07 | ALL | % of RPCE (Capture) | 5.98% | 5.98% | -0.000pp | MATCH |
| 2026-07 | ALL | # of Mosaic Rads | 2,046 | 2,046 | +0 | MATCH |
| 2026-07 | ALL | # of RPCE Rads | 2,882 | 2,882 | +0 | MATCH |
| 2026-07 | ALL | % of Rads | 70.99% | 70.99% | +0.000pp | MATCH |
| 2026-07 | ALL | Radiologists live on drafting | 1,640 | 1,640 | +0 | MATCH |
| 2026-07 | ALL | % Head CT RPCE | 86.89% | 86.89% | +0.000pp | NEAR |
| 2026-08 | ALL | Clinical exams | 3,533,586 | 3,534,144 | +558 | NEAR |
| 2026-08 | ALL | RPCE exams | 3,037,330 | 3,037,352 | +22 | NEAR |
| 2026-08 | ALL | Mosaic exams (reporting) | 2,298,434 | 2,298,456 | +22 | NEAR |
| 2026-08 | ALL | % of RPCE (Reporting) | 77.67% | 77.67% | +0.000pp | NEAR |
| 2026-08 | ALL | Mosaic drafting exams | 1,131,199 | 1,131,141 | -58 | NEAR |
| 2026-08 | ALL | % of RPCE (Drafting) | 39.24% | 39.24% | -0.002pp | NEAR |
| 2026-08 | ALL | Mosaic capture exams | 131,544 | 131,547 | +3 | NEAR |
| 2026-08 | ALL | % of RPCE (Capture) | 6.33% | 6.33% | +0.000pp | NEAR |
| 2026-08 | ALL | # of Mosaic Rads | 2,092 | 2,092 | +0 | MATCH |
| 2026-08 | ALL | # of RPCE Rads | 2,898 | 2,898 | +0 | MATCH |
| 2026-08 | ALL | % of Rads | 72.19% | 72.19% | +0.000pp | MATCH |
| 2026-08 | ALL | Radiologists live on drafting | 1,693 | 1,693 | +0 | MATCH |
| 2026-08 | ALL | % Head CT RPCE | 86.73% | 86.73% | +0.000pp | NEAR |
| 2026-09 | ALL | Clinical exams | 3,505,017 | 3,505,336 | +319 | NEAR |
| 2026-09 | ALL | RPCE exams | 3,013,521 | 3,013,541 | +20 | NEAR |
| 2026-09 | ALL | Mosaic exams (reporting) | 2,328,154 | 2,328,174 | +20 | NEAR |
| 2026-09 | ALL | % of RPCE (Reporting) | 79.26% | 79.26% | +0.000pp | NEAR |
| 2026-09 | ALL | Mosaic drafting exams | 1,252,539 | 1,252,477 | -62 | NEAR |
| 2026-09 | ALL | % of RPCE (Drafting) | 43.56% | 43.56% | -0.002pp | NEAR |
| 2026-09 | ALL | Mosaic capture exams | 138,357 | 138,357 | +0 | MATCH |
| 2026-09 | ALL | % of RPCE (Capture) | 6.59% | 6.59% | -0.000pp | MATCH |
| 2026-09 | ALL | # of Mosaic Rads | 2,080 | 2,080 | +0 | MATCH |
| 2026-09 | ALL | # of RPCE Rads | 2,837 | 2,837 | +0 | MATCH |
| 2026-09 | ALL | % of Rads | 73.32% | 73.32% | +0.000pp | MATCH |
| 2026-09 | ALL | Radiologists live on drafting | 1,698 | 1,698 | +0 | MATCH |
| 2026-09 | ALL | % Head CT RPCE | 86.55% | 86.55% | +0.000pp | MATCH |

## By Local Region

| Month | Member | KPI | PBI | Databricks | Diff | Status |
|---|---|---|---:|---:|---:|---|
| 2026-07 | Apex | Clinical exams | 446,960 | 446,991 | +31 | NEAR |
| 2026-07 | Apex | RPCE exams | 442,034 | 442,034 | +0 | MATCH |
| 2026-07 | Apex | Mosaic exams (reporting) | 377,011 | 377,011 | +0 | MATCH |
| 2026-07 | Apex | % of RPCE (Reporting) | 87.29% | 87.29% | +0.000pp | MATCH |
| 2026-07 | Apex | Mosaic drafting exams | 160,302 | 160,302 | +0 | MATCH |
| 2026-07 | Apex | % of RPCE (Drafting) | 38.26% | 38.26% | +0.000pp | MATCH |
| 2026-07 | Apex | Mosaic capture exams | 9,994 | 9,994 | +0 | MATCH |
| 2026-07 | Apex | % of RPCE (Capture) | 4.26% | 4.26% | +0.000pp | MATCH |
| 2026-07 | Apex | # of Mosaic Rads | 312 | 312 | +0 | MATCH |
| 2026-07 | Apex | # of RPCE Rads | 337 | 337 | +0 | MATCH |
| 2026-07 | Apex | % of Rads | 92.58% | 92.58% | +0.000pp | MATCH |
| 2026-07 | Apex | Radiologists live on drafting | 244 | 244 | +0 | MATCH |
| 2026-07 | Apex | % Head CT RPCE | 100.00% | 100.00% | +0.000pp | MATCH |
| 2026-07 | Genesis | Clinical exams | 679,292 | 679,446 | +154 | NEAR |
| 2026-07 | Genesis | RPCE exams | 517,664 | 517,664 | +0 | MATCH |
| 2026-07 | Genesis | Mosaic exams (reporting) | 326,929 | 326,929 | +0 | MATCH |
| 2026-07 | Genesis | % of RPCE (Reporting) | 65.15% | 65.15% | +0.000pp | MATCH |
| 2026-07 | Genesis | Mosaic drafting exams | 155,070 | 155,070 | +0 | MATCH |
| 2026-07 | Genesis | % of RPCE (Drafting) | 31.96% | 31.96% | +0.000pp | MATCH |
| 2026-07 | Genesis | Mosaic capture exams | 14,483 | 14,483 | +0 | MATCH |
| 2026-07 | Genesis | % of RPCE (Capture) | 4.80% | 4.80% | +0.000pp | MATCH |
| 2026-07 | Genesis | # of Mosaic Rads | 303 | 303 | +0 | MATCH |
| 2026-07 | Genesis | # of RPCE Rads | 430 | 430 | +0 | MATCH |
| 2026-07 | Genesis | % of Rads | 70.47% | 70.47% | +0.000pp | MATCH |
| 2026-07 | Genesis | Radiologists live on drafting | 249 | 249 | +0 | MATCH |
| 2026-07 | Genesis | % Head CT RPCE | 78.35% | 78.35% | +0.002pp | NEAR |
| 2026-07 | Matrix | Clinical exams | 523,774 | 523,811 | +37 | NEAR |
| 2026-07 | Matrix | RPCE exams | 452,014 | 452,014 | +0 | MATCH |
| 2026-07 | Matrix | Mosaic exams (reporting) | 323,121 | 323,121 | +0 | MATCH |
| 2026-07 | Matrix | % of RPCE (Reporting) | 73.48% | 73.48% | +0.000pp | MATCH |
| 2026-07 | Matrix | Mosaic drafting exams | 141,612 | 141,612 | +0 | MATCH |
| 2026-07 | Matrix | % of RPCE (Drafting) | 33.33% | 33.33% | +0.000pp | MATCH |
| 2026-07 | Matrix | Mosaic capture exams | 16,586 | 16,586 | +0 | MATCH |
| 2026-07 | Matrix | % of RPCE (Capture) | 5.67% | 5.67% | +0.000pp | MATCH |
| 2026-07 | Matrix | # of Mosaic Rads | 355 | 355 | +0 | MATCH |
| 2026-07 | Matrix | # of RPCE Rads | 740 | 740 | +0 | MATCH |
| 2026-07 | Matrix | % of Rads | 47.97% | 47.97% | +0.000pp | MATCH |
| 2026-07 | Matrix | Radiologists live on drafting | 260 | 260 | +0 | MATCH |
| 2026-07 | Matrix | % Head CT RPCE | 91.44% | 91.44% | +0.000pp | MATCH |
| 2026-07 | Maverick | Clinical exams | 644,373 | 644,518 | +145 | NEAR |
| 2026-07 | Maverick | RPCE exams | 538,885 | 538,885 | +0 | MATCH |
| 2026-07 | Maverick | Mosaic exams (reporting) | 421,915 | 421,915 | +0 | MATCH |
| 2026-07 | Maverick | % of RPCE (Reporting) | 80.29% | 80.29% | +0.000pp | MATCH |
| 2026-07 | Maverick | Mosaic drafting exams | 188,507 | 188,504 | -3 | NEAR |
| 2026-07 | Maverick | % of RPCE (Drafting) | 36.98% | 36.98% | -0.001pp | NEAR |
| 2026-07 | Maverick | Mosaic capture exams | 31,702 | 31,702 | +0 | MATCH |
| 2026-07 | Maverick | % of RPCE (Capture) | 7.88% | 7.88% | +0.000pp | MATCH |
| 2026-07 | Maverick | # of Mosaic Rads | 359 | 359 | +0 | MATCH |
| 2026-07 | Maverick | # of RPCE Rads | 440 | 440 | +0 | MATCH |
| 2026-07 | Maverick | % of Rads | 81.59% | 81.59% | +0.000pp | MATCH |
| 2026-07 | Maverick | Radiologists live on drafting | 300 | 300 | +0 | MATCH |
| 2026-07 | Maverick | % Head CT RPCE | 82.43% | 82.43% | +0.000pp | MATCH |
| 2026-07 | Special Operations | Clinical exams | 593,668 | 593,642 | -26 | NEAR |
| 2026-07 | Special Operations | RPCE exams | 586,406 | 586,406 | +0 | MATCH |
| 2026-07 | Special Operations | Mosaic exams (reporting) | 516,768 | 516,768 | +0 | MATCH |
| 2026-07 | Special Operations | % of RPCE (Reporting) | 90.12% | 90.12% | +0.000pp | MATCH |
| 2026-07 | Special Operations | Mosaic drafting exams | 240,499 | 240,480 | -19 | NEAR |
| 2026-07 | Special Operations | % of RPCE (Drafting) | 43.01% | 43.01% | -0.003pp | NEAR |
| 2026-07 | Special Operations | Mosaic capture exams | 26,802 | 26,802 | +0 | MATCH |
| 2026-07 | Special Operations | % of RPCE (Capture) | 6.57% | 6.57% | +0.000pp | MATCH |
| 2026-07 | Special Operations | # of Mosaic Rads | 485 | 485 | +0 | MATCH |
| 2026-07 | Special Operations | # of RPCE Rads | 533 | 533 | +0 | MATCH |
| 2026-07 | Special Operations | % of Rads | 90.99% | 90.99% | +0.000pp | MATCH |
| 2026-07 | Special Operations | Radiologists live on drafting | 385 | 385 | +0 | MATCH |
| 2026-07 | Special Operations | % Head CT RPCE | 98.54% | 98.54% | +0.000pp | MATCH |
| 2026-07 | Trailblazer | Clinical exams | 651,322 | 652,014 | +692 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | Trailblazer | RPCE exams | 511,118 | 511,124 | +6 | NEAR |
| 2026-07 | Trailblazer | Mosaic exams (reporting) | 271,485 | 271,491 | +6 | NEAR |
| 2026-07 | Trailblazer | % of RPCE (Reporting) | 55.12% | 55.12% | +0.001pp | NEAR |
| 2026-07 | Trailblazer | Mosaic drafting exams | 126,836 | 126,837 | +1 | NEAR |
| 2026-07 | Trailblazer | % of RPCE (Drafting) | 26.82% | 26.82% | -0.000pp | NEAR |
| 2026-07 | Trailblazer | Mosaic capture exams | 21,787 | 21,787 | +0 | MATCH |
| 2026-07 | Trailblazer | % of RPCE (Capture) | 6.26% | 6.26% | -0.000pp | NEAR |
| 2026-07 | Trailblazer | # of Mosaic Rads | 232 | 232 | +0 | MATCH |
| 2026-07 | Trailblazer | # of RPCE Rads | 402 | 402 | +0 | MATCH |
| 2026-07 | Trailblazer | % of Rads | 57.71% | 57.71% | +0.000pp | MATCH |
| 2026-07 | Trailblazer | Radiologists live on drafting | 202 | 202 | +0 | MATCH |
| 2026-07 | Trailblazer | % Head CT RPCE | 74.65% | 74.65% | +0.000pp | MATCH |
| 2026-08 | Apex | Clinical exams | 446,490 | 446,524 | +34 | NEAR |
| 2026-08 | Apex | RPCE exams | 441,045 | 441,045 | +0 | MATCH |
| 2026-08 | Apex | Mosaic exams (reporting) | 387,405 | 387,405 | +0 | MATCH |
| 2026-08 | Apex | % of RPCE (Reporting) | 89.84% | 89.84% | +0.000pp | MATCH |
| 2026-08 | Apex | Mosaic drafting exams | 175,861 | 175,859 | -2 | NEAR |
| 2026-08 | Apex | % of RPCE (Drafting) | 41.87% | 41.87% | -0.000pp | NEAR |
| 2026-08 | Apex | Mosaic capture exams | 9,813 | 9,813 | +0 | MATCH |
| 2026-08 | Apex | % of RPCE (Capture) | 4.22% | 4.22% | +0.000pp | MATCH |
| 2026-08 | Apex | # of Mosaic Rads | 316 | 316 | +0 | MATCH |
| 2026-08 | Apex | # of RPCE Rads | 343 | 343 | +0 | MATCH |
| 2026-08 | Apex | % of Rads | 92.13% | 92.13% | +0.000pp | MATCH |
| 2026-08 | Apex | Radiologists live on drafting | 246 | 246 | +0 | MATCH |
| 2026-08 | Apex | % Head CT RPCE | 100.00% | 100.00% | +0.000pp | MATCH |
| 2026-08 | Genesis | Clinical exams | 679,129 | 679,230 | +101 | NEAR |
| 2026-08 | Genesis | RPCE exams | 517,003 | 517,003 | +0 | MATCH |
| 2026-08 | Genesis | Mosaic exams (reporting) | 338,328 | 338,328 | +0 | MATCH |
| 2026-08 | Genesis | % of RPCE (Reporting) | 67.44% | 67.44% | +0.000pp | MATCH |
| 2026-08 | Genesis | Mosaic drafting exams | 169,526 | 169,526 | +0 | MATCH |
| 2026-08 | Genesis | % of RPCE (Drafting) | 34.79% | 34.79% | +0.000pp | MATCH |
| 2026-08 | Genesis | Mosaic capture exams | 17,889 | 17,889 | +0 | MATCH |
| 2026-08 | Genesis | % of RPCE (Capture) | 5.46% | 5.46% | +0.000pp | MATCH |
| 2026-08 | Genesis | # of Mosaic Rads | 319 | 319 | +0 | MATCH |
| 2026-08 | Genesis | # of RPCE Rads | 438 | 438 | +0 | MATCH |
| 2026-08 | Genesis | % of Rads | 72.83% | 72.83% | +0.000pp | MATCH |
| 2026-08 | Genesis | Radiologists live on drafting | 260 | 260 | +0 | MATCH |
| 2026-08 | Genesis | % Head CT RPCE | 77.95% | 77.95% | +0.002pp | NEAR |
| 2026-08 | Matrix | Clinical exams | 520,962 | 520,970 | +8 | NEAR |
| 2026-08 | Matrix | RPCE exams | 449,883 | 449,883 | +0 | MATCH |
| 2026-08 | Matrix | Mosaic exams (reporting) | 325,490 | 325,490 | +0 | MATCH |
| 2026-08 | Matrix | % of RPCE (Reporting) | 74.35% | 74.35% | +0.000pp | MATCH |
| 2026-08 | Matrix | Mosaic drafting exams | 167,703 | 167,703 | +0 | MATCH |
| 2026-08 | Matrix | % of RPCE (Drafting) | 39.28% | 39.28% | +0.000pp | MATCH |
| 2026-08 | Matrix | Mosaic capture exams | 17,769 | 17,769 | +0 | MATCH |
| 2026-08 | Matrix | % of RPCE (Capture) | 5.95% | 5.95% | +0.000pp | MATCH |
| 2026-08 | Matrix | # of Mosaic Rads | 363 | 363 | +0 | MATCH |
| 2026-08 | Matrix | # of RPCE Rads | 746 | 746 | +0 | MATCH |
| 2026-08 | Matrix | % of Rads | 48.66% | 48.66% | +0.000pp | MATCH |
| 2026-08 | Matrix | Radiologists live on drafting | 280 | 280 | +0 | MATCH |
| 2026-08 | Matrix | % Head CT RPCE | 90.66% | 90.66% | +0.000pp | MATCH |
| 2026-08 | Maverick | Clinical exams | 642,759 | 642,882 | +123 | NEAR |
| 2026-08 | Maverick | RPCE exams | 536,697 | 536,697 | +0 | MATCH |
| 2026-08 | Maverick | Mosaic exams (reporting) | 444,658 | 444,658 | +0 | MATCH |
| 2026-08 | Maverick | % of RPCE (Reporting) | 84.85% | 84.85% | +0.000pp | MATCH |
| 2026-08 | Maverick | Mosaic drafting exams | 206,858 | 206,820 | -38 | NEAR |
| 2026-08 | Maverick | % of RPCE (Drafting) | 40.54% | 40.54% | -0.007pp | NEAR |
| 2026-08 | Maverick | Mosaic capture exams | 33,507 | 33,507 | +0 | MATCH |
| 2026-08 | Maverick | % of RPCE (Capture) | 8.24% | 8.24% | +0.000pp | MATCH |
| 2026-08 | Maverick | # of Mosaic Rads | 367 | 367 | +0 | MATCH |
| 2026-08 | Maverick | # of RPCE Rads | 448 | 448 | +0 | MATCH |
| 2026-08 | Maverick | % of Rads | 81.92% | 81.92% | +0.000pp | MATCH |
| 2026-08 | Maverick | Radiologists live on drafting | 313 | 313 | +0 | MATCH |
| 2026-08 | Maverick | % Head CT RPCE | 83.76% | 83.76% | +0.000pp | MATCH |
| 2026-08 | Special Operations | Clinical exams | 588,146 | 588,112 | -34 | NEAR |
| 2026-08 | Special Operations | RPCE exams | 583,340 | 583,340 | +0 | MATCH |
| 2026-08 | Special Operations | Mosaic exams (reporting) | 526,405 | 526,405 | +0 | MATCH |
| 2026-08 | Special Operations | % of RPCE (Reporting) | 92.24% | 92.24% | +0.000pp | MATCH |
| 2026-08 | Special Operations | Mosaic drafting exams | 271,230 | 271,205 | -25 | NEAR |
| 2026-08 | Special Operations | % of RPCE (Drafting) | 48.50% | 48.49% | -0.004pp | NEAR |
| 2026-08 | Special Operations | Mosaic capture exams | 30,127 | 30,127 | +0 | MATCH |
| 2026-08 | Special Operations | % of RPCE (Capture) | 7.16% | 7.16% | +0.000pp | MATCH |
| 2026-08 | Special Operations | # of Mosaic Rads | 484 | 484 | +0 | MATCH |
| 2026-08 | Special Operations | # of RPCE Rads | 531 | 531 | +0 | MATCH |
| 2026-08 | Special Operations | % of Rads | 91.15% | 91.15% | +0.000pp | MATCH |
| 2026-08 | Special Operations | Radiologists live on drafting | 383 | 383 | +0 | MATCH |
| 2026-08 | Special Operations | % Head CT RPCE | 99.43% | 99.43% | +0.000pp | MATCH |
| 2026-08 | Trailblazer | Clinical exams | 656,100 | 656,426 | +326 | NEAR |
| 2026-08 | Trailblazer | RPCE exams | 509,362 | 509,384 | +22 | NEAR |
| 2026-08 | Trailblazer | Mosaic exams (reporting) | 276,148 | 276,170 | +22 | NEAR |
| 2026-08 | Trailblazer | % of RPCE (Reporting) | 56.21% | 56.22% | +0.002pp | NEAR |
| 2026-08 | Trailblazer | Mosaic drafting exams | 140,021 | 140,028 | +7 | NEAR |
| 2026-08 | Trailblazer | % of RPCE (Drafting) | 29.49% | 29.49% | +0.000pp | NEAR |
| 2026-08 | Trailblazer | Mosaic capture exams | 22,439 | 22,442 | +3 | NEAR |
| 2026-08 | Trailblazer | % of RPCE (Capture) | 6.41% | 6.41% | +0.000pp | NEAR |
| 2026-08 | Trailblazer | # of Mosaic Rads | 243 | 243 | +0 | MATCH |
| 2026-08 | Trailblazer | # of RPCE Rads | 392 | 392 | +0 | MATCH |
| 2026-08 | Trailblazer | % of Rads | 61.99% | 61.99% | +0.000pp | MATCH |
| 2026-08 | Trailblazer | Radiologists live on drafting | 211 | 211 | +0 | MATCH |
| 2026-08 | Trailblazer | % Head CT RPCE | 72.86% | 72.86% | +0.000pp | MATCH |
| 2026-09 | Apex | Clinical exams | 445,764 | 445,793 | +29 | NEAR |
| 2026-09 | Apex | RPCE exams | 440,591 | 440,591 | +0 | MATCH |
| 2026-09 | Apex | Mosaic exams (reporting) | 395,601 | 395,601 | +0 | MATCH |
| 2026-09 | Apex | % of RPCE (Reporting) | 91.79% | 91.79% | +0.000pp | MATCH |
| 2026-09 | Apex | Mosaic drafting exams | 193,814 | 193,813 | -1 | NEAR |
| 2026-09 | Apex | % of RPCE (Drafting) | 45.99% | 45.99% | -0.000pp | NEAR |
| 2026-09 | Apex | Mosaic capture exams | 10,067 | 10,067 | +0 | MATCH |
| 2026-09 | Apex | % of RPCE (Capture) | 4.28% | 4.28% | +0.000pp | MATCH |
| 2026-09 | Apex | # of Mosaic Rads | 320 | 320 | +0 | MATCH |
| 2026-09 | Apex | # of RPCE Rads | 344 | 344 | +0 | MATCH |
| 2026-09 | Apex | % of Rads | 93.02% | 93.02% | +0.000pp | MATCH |
| 2026-09 | Apex | Radiologists live on drafting | 248 | 248 | +0 | MATCH |
| 2026-09 | Apex | % Head CT RPCE | 100.00% | 100.00% | +0.000pp | MATCH |
| 2026-09 | Genesis | Clinical exams | 676,410 | 676,507 | +97 | NEAR |
| 2026-09 | Genesis | RPCE exams | 521,668 | 521,668 | +0 | MATCH |
| 2026-09 | Genesis | Mosaic exams (reporting) | 344,055 | 344,055 | +0 | MATCH |
| 2026-09 | Genesis | % of RPCE (Reporting) | 67.95% | 67.95% | +0.000pp | MATCH |
| 2026-09 | Genesis | Mosaic drafting exams | 185,182 | 185,182 | +0 | MATCH |
| 2026-09 | Genesis | % of RPCE (Drafting) | 37.50% | 37.50% | +0.000pp | MATCH |
| 2026-09 | Genesis | Mosaic capture exams | 18,019 | 18,019 | +0 | MATCH |
| 2026-09 | Genesis | % of RPCE (Capture) | 5.45% | 5.45% | +0.000pp | MATCH |
| 2026-09 | Genesis | # of Mosaic Rads | 319 | 319 | +0 | MATCH |
| 2026-09 | Genesis | # of RPCE Rads | 439 | 439 | +0 | MATCH |
| 2026-09 | Genesis | % of Rads | 72.67% | 72.67% | +0.000pp | MATCH |
| 2026-09 | Genesis | Radiologists live on drafting | 260 | 260 | +0 | MATCH |
| 2026-09 | Genesis | % Head CT RPCE | 77.99% | 77.99% | +0.000pp | MATCH |
| 2026-09 | Matrix | Clinical exams | 497,230 | 497,217 | -13 | NEAR |
| 2026-09 | Matrix | RPCE exams | 428,980 | 428,981 | +1 | NEAR |
| 2026-09 | Matrix | Mosaic exams (reporting) | 316,862 | 316,863 | +1 | NEAR |
| 2026-09 | Matrix | % of RPCE (Reporting) | 75.86% | 75.86% | +0.000pp | NEAR |
| 2026-09 | Matrix | Mosaic drafting exams | 184,667 | 184,665 | -2 | NEAR |
| 2026-09 | Matrix | % of RPCE (Drafting) | 45.05% | 45.05% | -0.001pp | NEAR |
| 2026-09 | Matrix | Mosaic capture exams | 18,008 | 18,008 | +0 | MATCH |
| 2026-09 | Matrix | % of RPCE (Capture) | 6.20% | 6.20% | -0.000pp | MATCH |
| 2026-09 | Matrix | # of Mosaic Rads | 344 | 344 | +0 | MATCH |
| 2026-09 | Matrix | # of RPCE Rads | 726 | 726 | +0 | MATCH |
| 2026-09 | Matrix | % of Rads | 47.38% | 47.38% | +0.000pp | MATCH |
| 2026-09 | Matrix | Radiologists live on drafting | 278 | 278 | +0 | MATCH |
| 2026-09 | Matrix | % Head CT RPCE | 91.83% | 91.83% | +0.000pp | MATCH |
| 2026-09 | Maverick | Clinical exams | 641,658 | 641,750 | +92 | NEAR |
| 2026-09 | Maverick | RPCE exams | 533,836 | 533,836 | +0 | MATCH |
| 2026-09 | Maverick | Mosaic exams (reporting) | 452,099 | 452,099 | +0 | MATCH |
| 2026-09 | Maverick | % of RPCE (Reporting) | 86.69% | 86.69% | +0.000pp | MATCH |
| 2026-09 | Maverick | Mosaic drafting exams | 223,324 | 223,295 | -29 | NEAR |
| 2026-09 | Maverick | % of RPCE (Drafting) | 43.83% | 43.83% | -0.005pp | NEAR |
| 2026-09 | Maverick | Mosaic capture exams | 36,796 | 36,796 | +0 | MATCH |
| 2026-09 | Maverick | % of RPCE (Capture) | 8.89% | 8.89% | +0.000pp | MATCH |
| 2026-09 | Maverick | # of Mosaic Rads | 374 | 374 | +0 | MATCH |
| 2026-09 | Maverick | # of RPCE Rads | 438 | 438 | +0 | MATCH |
| 2026-09 | Maverick | % of Rads | 85.39% | 85.39% | +0.000pp | MATCH |
| 2026-09 | Maverick | Radiologists live on drafting | 318 | 318 | +0 | MATCH |
| 2026-09 | Maverick | % Head CT RPCE | 82.62% | 82.62% | +0.000pp | MATCH |
| 2026-09 | Special Operations | Clinical exams | 595,650 | 595,613 | -37 | NEAR |
| 2026-09 | Special Operations | RPCE exams | 589,004 | 589,004 | +0 | MATCH |
| 2026-09 | Special Operations | Mosaic exams (reporting) | 533,307 | 533,307 | +0 | MATCH |
| 2026-09 | Special Operations | % of RPCE (Reporting) | 92.54% | 92.54% | +0.000pp | MATCH |
| 2026-09 | Special Operations | Mosaic drafting exams | 302,169 | 302,137 | -32 | NEAR |
| 2026-09 | Special Operations | % of RPCE (Drafting) | 53.30% | 53.30% | -0.005pp | NEAR |
| 2026-09 | Special Operations | Mosaic capture exams | 31,424 | 31,424 | +0 | MATCH |
| 2026-09 | Special Operations | % of RPCE (Capture) | 7.34% | 7.34% | +0.000pp | MATCH |
| 2026-09 | Special Operations | # of Mosaic Rads | 468 | 468 | +0 | MATCH |
| 2026-09 | Special Operations | # of RPCE Rads | 515 | 515 | +0 | MATCH |
| 2026-09 | Special Operations | % of Rads | 90.87% | 90.87% | +0.000pp | MATCH |
| 2026-09 | Special Operations | Radiologists live on drafting | 380 | 380 | +0 | MATCH |
| 2026-09 | Special Operations | % Head CT RPCE | 99.37% | 99.37% | +0.000pp | MATCH |
| 2026-09 | Trailblazer | Clinical exams | 648,305 | 648,456 | +151 | NEAR |
| 2026-09 | Trailblazer | RPCE exams | 499,442 | 499,461 | +19 | NEAR |
| 2026-09 | Trailblazer | Mosaic exams (reporting) | 286,230 | 286,249 | +19 | NEAR |
| 2026-09 | Trailblazer | % of RPCE (Reporting) | 59.31% | 59.31% | +0.002pp | NEAR |
| 2026-09 | Trailblazer | Mosaic drafting exams | 163,383 | 163,385 | +2 | NEAR |
| 2026-09 | Trailblazer | % of RPCE (Drafting) | 34.71% | 34.71% | -0.001pp | NEAR |
| 2026-09 | Trailblazer | Mosaic capture exams | 24,043 | 24,043 | +0 | MATCH |
| 2026-09 | Trailblazer | % of RPCE (Capture) | 6.81% | 6.81% | -0.000pp | NEAR |
| 2026-09 | Trailblazer | # of Mosaic Rads | 255 | 255 | +0 | MATCH |
| 2026-09 | Trailblazer | # of RPCE Rads | 375 | 375 | +0 | MATCH |
| 2026-09 | Trailblazer | % of Rads | 68.00% | 68.00% | +0.000pp | MATCH |
| 2026-09 | Trailblazer | Radiologists live on drafting | 214 | 214 | +0 | MATCH |
| 2026-09 | Trailblazer | % Head CT RPCE | 72.25% | 72.25% | +0.000pp | MATCH |

## By Managing Practice (summary)

70 practices × 13 KPIs × months: KNOWN DIVERGENCE 37, MATCH 2556, NEAR 124

| Month | Practice | KPI | PBI | Databricks | Diff | Status |
|---|---|---|---:|---:|---:|---|
| 2026-07 | ARA | Clinical exams | 179,699 | 179,899 | +200 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | ARA | Clinical exams | 184,829 | 185,005 | +176 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | Boca | Clinical exams | 30,216 | 30,263 | +47 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | Boca | Clinical exams | 30,041 | 30,066 | +25 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | Coastal | Clinical exams | 19,105 | 19,122 | +17 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | DR | Clinical exams | 15,741 | 15,731 | -10 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | DR | Mosaic drafting exams | 5,562 | 5,555 | -7 | KNOWN DIVERGENCE (`case_count_weighting`) |
| 2026-07 | MBB | Clinical exams | 123,921 | 123,991 | +70 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | MIA | Clinical exams | 47,850 | 47,974 | +124 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | MIA | Clinical exams | 46,006 | 46,164 | +158 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | MIA | Clinical exams | 46,274 | 46,400 | +126 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | RAC | Clinical exams | 34,776 | 34,809 | +33 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RAC | Clinical exams | 33,444 | 33,482 | +38 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | RAC | Clinical exams | 34,522 | 34,555 | +33 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | RP Chicago | Clinical exams | 24,769 | 24,790 | +21 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP Chicago | Clinical exams | 23,832 | 23,797 | -35 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP Chicago | Mosaic drafting exams | 8,854 | 8,818 | -36 | KNOWN DIVERGENCE (`case_count_weighting`) |
| 2026-08 | RP Chicago | % of RPCE (Drafting) | 39.22% | 39.07% | -0.151pp | KNOWN DIVERGENCE (`case_count_weighting`) |
| 2026-09 | RP Chicago | Clinical exams | 24,663 | 24,642 | -21 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | RP Chicago | Mosaic drafting exams | 10,492 | 10,471 | -21 | KNOWN DIVERGENCE (`case_count_weighting`) |
| 2026-09 | RP Chicago | % of RPCE (Drafting) | 44.58% | 44.49% | -0.085pp | KNOWN DIVERGENCE (`case_count_weighting`) |
| 2026-07 | RP Houston | Clinical exams | 51,743 | 51,844 | +101 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP Houston | Clinical exams | 53,204 | 53,242 | +38 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP Houston | Mosaic capture exams | 3,461 | 3,464 | +3 | KNOWN DIVERGENCE (`rp_houston_exam_fact_gap_2026_08`) |
| 2026-07 | RP North Houston | Clinical exams | 28,621 | 28,664 | +43 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP North Houston | Clinical exams | 29,700 | 29,725 | +25 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | RP North Houston | Clinical exams | 29,204 | 29,245 | +41 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | RP RAH | Clinical exams | 0 | 2 | +2 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP RAH | Clinical exams | 0 | 6 | +6 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | RP Singleton | Clinical exams | 40,553 | 40,806 | +253 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | RP Singleton | Clinical exams | 40,119 | 40,155 | +36 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | SMI | Clinical exams | 17,476 | 17,489 | +13 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | SMI | Clinical exams | 15,159 | 15,172 | +13 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | SOAR | Clinical exams | 32,941 | 32,970 | +29 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-08 | SOAR | Clinical exams | 34,697 | 34,730 | +33 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-09 | SOAR | Clinical exams | 34,012 | 34,071 | +59 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
| 2026-07 | Synergy | Clinical exams | 121,676 | 121,798 | +122 | KNOWN DIVERGENCE (`imagine_non_rpce`, `case_count_weighting`) |
