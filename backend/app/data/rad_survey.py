"""Compiled results from the Mosaic General Survey - not derivable from EDW, sourced from
"Mosaic General Survey.xlsx" (Survey Data sheet, 810 respondents, fielded 2026-08-07 to
2026-09-02, sent 2026-08-12). Snapshot as of 2026-09-11. Refresh by re-running the same
compilation against an updated copy of that workbook and replacing the values below.

Two corrections applied vs. the raw workbook (both confirmed by recomputing from the 810 raw
response rows, not trusting the sheet's own pre-built summary):
  - NPS = -54.7, not the -8.09 shown on the "General Survey 1" sheet (that figure divides
    (promoters-detractors) by total Sent=5,474 instead of total Responses=810 - a bug).
  - Response rate = 810/5,474 sent = 14.8%, not the unreconciled 40.7% figure on the
    "Summary Results" sheet (which uses an unexplained smaller base of 1,991).
"""

SENT = 5474
RESPONSES = 810
RESPONSE_RATE = RESPONSES / SENT
MEDIAN_COMPLETION_MINUTES = 4.9

# Q1: "On a scale of 0-10, how likely are you to recommend Mosaic to a colleague?"
NPS_DISTRIBUTION: dict[str, int] = {
    "0": 126, "1": 46, "2": 70, "3": 75, "4": 40, "5": 98,
    "6": 88, "7": 90, "8": 77, "9": 41, "10": 59,
}
PROMOTERS = 100   # score 9-10
PASSIVES = 167    # score 7-8
DETRACTORS = 543  # score 0-6
NPS = -54.7

# Q6: agreement statements, 1 (strongly disagree) - 5 (strongly agree), n=810 each.
AGREEMENT_STATEMENTS: list[dict] = [
    {"label": "Supports high-quality patient care", "distribution": {"1": 153, "2": 153, "3": 206, "4": 218, "5": 80}, "mean": 2.90, "top2box_pct": 36.8},
    {"label": "Mosaic is easy to use", "distribution": {"1": 129, "2": 192, "3": 192, "4": 249, "5": 48}, "mean": 2.87, "top2box_pct": 36.7},
    {"label": "I trust Mosaic outputs", "distribution": {"1": 200, "2": 216, "3": 224, "4": 146, "5": 24}, "mean": 2.48, "top2box_pct": 21.0},
    {"label": "Meets/exceeds productivity goals", "distribution": {"1": 220, "2": 163, "3": 176, "4": 175, "5": 76}, "mean": 2.66, "top2box_pct": 31.0},
    {"label": "Timely/effective support", "distribution": {"1": 102, "2": 114, "3": 246, "4": 260, "5": 88}, "mean": 3.15, "top2box_pct": 43.0},
    {"label": "Seen meaningful improvement", "distribution": {"1": 116, "2": 134, "3": 167, "4": 270, "5": 123}, "mean": 3.19, "top2box_pct": 48.5},
    {"label": "Believe it will keep improving", "distribution": {"1": 50, "2": 69, "3": 193, "4": 347, "5": 151}, "mean": 3.59, "top2box_pct": 61.5},
]

# Q8: feature satisfaction, 1-5 (option 6 = N/A/haven't used, excluded from mean/distribution).
FEATURE_SATISFACTION: list[dict] = [
    {"label": "Reporting (STT/editing)", "distribution": {"1": 4, "2": 299, "3": 233, "4": 138, "5": 117}, "mean": 3.08, "na_count": 19},
    {"label": "Drafting (AI reports XR/CT)", "distribution": {"1": 114, "2": 82, "3": 131, "4": 199, "5": 226}, "mean": 3.45, "na_count": 58},
    {"label": "Capture (US worksheets)", "distribution": {"1": 156, "2": 71, "3": 85, "4": 151, "5": 263}, "mean": 3.40, "na_count": 84},
    {"label": "Templates", "distribution": {"1": 21, "2": 177, "3": 186, "4": 201, "5": 192}, "mean": 3.47, "na_count": 33},
]

# Q9: frequency of problems, 1 (never) - 5 (very often), n=810, no N/A option.
PROBLEM_FREQUENCY: list[dict] = [
    {"label": "Slowness", "distribution": {"1": 6, "2": 126, "3": 333, "4": 242, "5": 103}, "mean": 3.38},
    {"label": "Errors/freezing/crashes", "distribution": {"1": 25, "2": 249, "3": 336, "4": 155, "5": 45}, "mean": 2.93},
    {"label": "Hardware issues (mic etc.)", "distribution": {"1": 111, "2": 366, "3": 214, "4": 83, "5": 36}, "mean": 2.47},
]

# Q4 verbatim ("greatest frustration"), n=717 non-blank, keyword-tagged (can hit multiple themes).
TOP_FRUSTRATION_THEMES: list[dict] = [
    {"theme": "Speech recognition", "pct": 40.4},
    {"theme": "Templates rigidity", "pct": 23.0},
    {"theme": "Editing experience", "pct": 17.0},
    {"theme": "Drafting quality", "pct": 13.8},
    {"theme": "Slowness", "pct": 11.2},
    {"theme": "Hallucinations/inaccuracy", "pct": 9.6},
    {"theme": "Trust", "pct": 7.9},
    {"theme": "Crashes", "pct": 6.7},
]

# Q3 verbatim ("features appreciated most"), n=633 non-blank.
TOP_PRAISED_THEMES: list[dict] = [
    {"theme": "Drafting", "pct": 36.2},
    {"theme": "Capture/ultrasound", "pct": 13.9},
    {"theme": "Speech recognition", "pct": 13.1},
    {"theme": "Templates", "pct": 7.0},
    {"theme": "Productivity", "pct": 3.6},
]

# All 18 practices with n>=15 respondents, proper NPS (%promoter[9-10] - %detractor[0-6]).
# Every single one is net-negative - there is no practice above water on this metric.
BY_PRACTICE: list[dict] = [
    {"practice": "RIMA", "n": 32, "nps": -25.0, "mean": 6.41},
    {"practice": "DR", "n": 19, "nps": -26.3, "mean": 6.00},
    {"practice": "ESR Metro Hudson", "n": 16, "nps": -31.3, "mean": 5.88},
    {"practice": "Greensboro", "n": 25, "nps": -40.0, "mean": 5.44},
    {"practice": "DRSRP", "n": 39, "nps": -41.0, "mean": 5.69},
    {"practice": "CRC", "n": 51, "nps": -43.1, "mean": 5.24},
    {"practice": "MIA", "n": 18, "nps": -50.0, "mean": 5.44},
    {"practice": "Matrix", "n": 75, "nps": -52.0, "mean": 4.53},
    {"practice": "RAF", "n": 39, "nps": -53.8, "mean": 4.62},
    {"practice": "ESR Long Island", "n": 20, "nps": -60.0, "mean": 4.05},
    {"practice": "Jefferson", "n": 30, "nps": -60.0, "mean": 3.60},
    {"practice": "MBB", "n": 23, "nps": -60.9, "mean": 4.35},
    {"practice": "SEAL Team", "n": 40, "nps": -62.5, "mean": 5.15},
    {"practice": "RP Gulf Coast", "n": 19, "nps": -68.4, "mean": 4.37},
    {"practice": "RP Florida", "n": 16, "nps": -68.8, "mean": 4.88},
    {"practice": "Rad Alliance", "n": 37, "nps": -75.7, "mean": 3.24},
    {"practice": "RP Chicago", "n": 17, "nps": -88.2, "mean": 2.94},
    {"practice": "Lakefront Imaging", "n": 15, "nps": -93.3, "mean": 2.27},
]
