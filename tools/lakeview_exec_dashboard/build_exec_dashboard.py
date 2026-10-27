"""Builds the 6-page "Mosaic Executive Dashboard" (Lakeview) on the governed Mosaic metric views.

Every number on this dashboard is a MEASURE() from one of the edw_test.enterprise_analytics metric
views that were validated against the PowerBI reports (Volume / Efficiency / Capacity) plus the
Dynamics program view (033). No measure logic lives in this file -- only layout, labels and filters.

Usage:
  python tools/lakeview_exec_dashboard/build_exec_dashboard.py                 # write JSON only
  python tools/lakeview_exec_dashboard/build_exec_dashboard.py --create  --profile mosaic-oauth
  python tools/lakeview_exec_dashboard/build_exec_dashboard.py --update <dashboard_id> --profile mosaic-oauth

Never publishes -- publishing is a separate, explicit step.

Dataset design notes:
  * KPI datasets (ds_volume, ds_efficiency, ds_efficiency_rp_avg, ds_cap_pbi) take the global
    Period filter. Trend datasets (*_trend) point at the same sources but are NOT bound to
    Period, so trend lines always show full history while counters show the selected period.
  * ds_cap_pbi / ds_cap_pbi_trend (Capacity) are SQL datasets over the 044a shift view running
    capacity_practice_summary.sql: one row per shift at the PBI Mosaic Impact Report "Practice Summary"
    defaults (TBWU 26/Shift, Shifts with Baselines, shift-length exclusions, All Shifts) plus PBI's
    Has_Baseline_For_Selected_Unit visual filter. Widgets average per shift exactly as the PBI measures.
  * ds_program (Dynamics) has no MDM practice/region keys, so it is not bound to global filters.
  * ds_pp_* (By Provider Practice -- the CEO monthly send-out numbers) are SQL datasets over the 038 MV (all 5 PBI modes) running
    provider_practice_efficiency.sql, which replicates the PBI visual-level filters exactly. The window must be
    applied INSIDE that logic (who qualifies depends on it), so Period reaches them as the :period parameter,
    not as a field filter. Local Region / Managing Practice do not apply there (the PBI page has neither).
  * ds_mp_* (By Managing Practice -> Site) are SQL datasets over the 039 MV running managing_practice_efficiency.sql,
    the same way (PBI's site-level visual filters, window applied inside). The global Managing Practice filter is a
    plain field filter there: survival is decided per site / practice, so filtering practices never changes a row.
"""

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT_JSON = HERE / "exec_dashboard.json"
ID_FILE = HERE / "dashboard_id.txt"

DISPLAY_NAME = "Mosaic Executive Dashboard"
PARENT_PATH = "/Users/bhargav.narasimhan@radpartners.com/dashboards"
WAREHOUSE_ID = "fe0ad987563c672a"

CATALOG, SCHEMA = "edw_test", "enterprise_analytics"
VOLUME_MV = f"{CATALOG}.{SCHEMA}.mosaic_volume_metric_view"
EFF_MV = f"{CATALOG}.{SCHEMA}.mosaic_efficiency_metric_view"
RP_MV = f"{CATALOG}.{SCHEMA}.mosaic_efficiency_vs_rp_avg_metric_view"
PROGRAM_MV = f"{CATALOG}.{SCHEMA}.mosaic_program_metric_view"
DRAFTABLE_MV = f"{CATALOG}.{SCHEMA}.mosaic_draftable_metric_view"
BASELINE_TBL = f"{CATALOG}.{SCHEMA}.tbl_mosaic_baseline_master"
PROVIDER_PRACTICE_SQL = HERE / "provider_practice_efficiency.sql"
MANAGING_PRACTICE_SQL = HERE / "managing_practice_efficiency.sql"
TIME_SERIES_SQL = HERE / "efficiency_change_time_series.sql"
TS_WU_SQL = HERE / "time_series_wu.sql"
VS_AVG_SQL = HERE / "mosaic_eff_vs_avg.sql"
VS_AVG_TS_SQL = HERE / "mosaic_eff_vs_avg_ts.sql"
CAP_SQL = HERE / "capacity_practice_summary.sql"
MIN_EXAMS_PARAM = "min_exams"
PERIOD_PARAM = "period"

GREEN, RED = "#1A4F27", "#C23B22"

NUM_FMT = {"type": "number", "decimalPlaces": {"type": "max", "places": 2}}
COUNT_FMT = {"type": "number", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
PCT_FMT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}

THEME = {
    "theme": {
        "canvasBackgroundColor": {"light": "#F4F2ED", "dark": "#1F1E1D"},
        "widgetBackgroundColor": {"light": "#EBE9E2", "dark": "#1B1817"},
        "widgetBorderColor": {"light": "#D5CEC3", "dark": "#2F2E2B"},
        "fontColor": {"light": "#3D3C39", "dark": "#FAFBF9"},
        "selectionColor": {"light": "#5F7E52", "dark": "#7A8F3E"},
        "visualizationColors": ["#1A4F27", "#B35900", "#3A9BDC", "#7A8F3E", "#E8B200", "#767676", "#C23B22"],
        "widgetHeaderAlignment": "LEFT",
    },
    "applyModeEnabled": False,
    # "Ask Genie" opens the curated exec space (tools/genie_exec_space) instead of an auto-generated one.
    "genieSpace": {"isEnabled": True, "enablementMode": "ENABLED",
                   "overrideId": (HERE.parent / "genie_exec_space" / "space_id.txt").read_text().strip()},
}

DATASETS = {
    "ds_volume": ("Volume (period)", VOLUME_MV),
    "ds_volume_trend": ("Volume (trend)", VOLUME_MV),
    "ds_efficiency": ("Efficiency (period)", EFF_MV),
    "ds_efficiency_trend": ("Efficiency (trend)", EFF_MV),
    "ds_efficiency_rp_avg": ("Efficiency vs RP Average (period)", RP_MV),
    "ds_program": ("Program (Dynamics MVP)", PROGRAM_MV),
    "ds_shift_baselines": ("Shift Baselines", BASELINE_TBL),
    "ds_draftable": ("Draftable / Undrafted (period)", DRAFTABLE_MV),
    "ds_draftable_trend": ("Draftable / Undrafted (trend)", DRAFTABLE_MV),
}

# SQL datasets: name -> (display name, SQL file, output-level CTE in that file)
SQL_DATASETS = {
    "ds_pp_practice": ("Efficiency by Provider Practice (PBI visual logic)", PROVIDER_PRACTICE_SQL, "practice_rows"),
    "ds_pp_rad": ("Efficiency by Radiologist (PBI visual logic)", PROVIDER_PRACTICE_SQL, "radiologist_rows"),
    "ds_pp_exam": ("Efficiency by Parent Exam (PBI visual logic)", PROVIDER_PRACTICE_SQL, "parent_exam_rows"),
    "ds_mp_practice": ("Efficiency by Managing Practice (PBI visual logic)", MANAGING_PRACTICE_SQL, "practice_rows"),
    "ds_mp_site": ("Efficiency by Site (PBI visual logic)", MANAGING_PRACTICE_SQL, "site_rows"),
}
PROVIDER_PRACTICE = ["ds_pp_practice", "ds_pp_rad", "ds_pp_exam"]
MANAGING_SITE = ["ds_mp_practice", "ds_mp_site"]
# Mosaic Efficiency vs Average: period + PBI Min Exams slicer (default 100) -> name -> (display name, output-level CTE)
VS_AVG_DATASETS = {
    "ds_va_cards": ("Efficiency vs Average benchmarks by mode (PBI visual logic)", "card_rows"),
    "ds_va_team": ("Efficiency vs Average by Provider Practice (PBI visual logic)", "team_rows"),
    "ds_va_rad": ("Efficiency vs Average by Radiologist (PBI visual logic)", "radiologist_rows"),
    "ds_va_exam": ("Efficiency vs Average by Parent Exam (PBI visual logic)", "parent_exam_rows"),
}
VS_AVG = list(VS_AVG_DATASETS)
VS_AVG_MIN_DEFAULT = "100"
# Efficiency Change time series: full history, daily rows for PBI-gated radiologists; clipped by its own window picker.
TIME_SERIES = "ds_ts_eff"
# Time Series (WU/min by month): one row per Platform x Mode x rad x parent exam x month; picked by its own slicers.
TS_WU = "ds_ts_wu"
VS_AVG_TS = "ds_va_ts"
# Capacity (PBI Practice Summary logic): period-bound copy for counters/tables, unbound copy for trends.
CAP, CAP_TREND = "ds_cap_pbi", "ds_cap_pbi_trend"
CAPACITY = [CAP, CAP_TREND]

MODES = [("Reporting", "Reporting"), ("Drafting", "Drafting"), ("Capture", "Capture"),
         ("Drafting Capture", "Drafting + Capture"), ("Full Mosaic", "Full Mosaic")]


# ---------------------------------------------------------------- widget helpers

def m(name):
    return {"name": f"measure(`{name}`)", "expression": f"MEASURE(`{name}`)"}


def mref(name):
    return f"measure(`{name}`)"


def d(name, expr=None):
    return {"name": name, "expression": expr or f"`{name}`"}


def rule(operator, value, color, background=False):
    key = "backgroundColor" if background else "foregroundColor"
    return {"condition": {"operand": {"type": "data-value", "value": str(value)}, "operator": operator}, key: color}


def sign_rules(threshold="0"):
    return [rule("<", threshold, RED), rule(">=", threshold, GREEN)]


def col(field, title, fmt=None, rules=None):
    c = {"fieldName": field, "displayName": title}
    if fmt:
        c["format"] = fmt
    if rules:
        c["style"] = {"type": "basic", "rules": rules}
    return c


def counter(name, ds, measure, title, fmt, description=None):
    frame = {"title": title, "showTitle": True}
    if description:
        frame.update({"description": description, "showDescription": True})
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": [m(measure)], "disaggregated": False}}],
        "spec": {"version": 2, "widgetType": "counter",
                 "encodings": {"value": {"fieldName": mref(measure), "displayName": title, "format": fmt}},
                 "frame": frame},
    }}


def counter_expr(name, ds, field, expr, title, fmt, description=None):
    """Counter over a custom aggregate expression (SQL datasets have no MEASURE())."""
    w = counter(name, ds, field, title, fmt, description)
    w["widget"]["queries"][0]["query"]["fields"] = [d(field, expr)]
    w["widget"]["spec"]["encodings"]["value"]["fieldName"] = field
    return w


def line_expr(name, ds, x, series, title, fmt, color_dim=None):
    """line() over custom aggregate expressions. series: list of (field, label, expr)."""
    w = line(name, ds, x, [], title, fmt, color_dim)
    w["widget"]["queries"][0]["query"]["fields"] += [d(f, e) for f, _, e in series]
    w["widget"]["spec"]["encodings"]["y"]["fields"] = [{"fieldName": f, "displayName": lbl} for f, lbl, _ in series]
    return w


def table(name, ds, fields, columns, title, order=None, disaggregated=False):
    q = {"datasetName": ds, "fields": fields, "disaggregated": disaggregated}
    if order:
        q["orders"] = [{"direction": order[1], "expression": order[0]}]
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": q}],
        "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": columns},
                 "frame": {"title": title, "showTitle": True}},
    }}


def line(name, ds, x, measures, title, fmt, color_dim=None):
    """measures: list of (measure_name, series_label)."""
    fields = [d(x)] + ([d(color_dim)] if color_dim else []) + [m(n) for n, _ in measures]
    enc = {
        "x": {"fieldName": x, "scale": {"type": "temporal"}, "displayName": x},
        "y": {"fields": [{"fieldName": mref(n), "displayName": lbl} for n, lbl in measures],
              "scale": {"type": "quantitative"}, "format": fmt},
    }
    if color_dim:
        enc["color"] = {"fieldName": color_dim, "scale": {"type": "categorical"}, "displayName": color_dim}
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {
            "datasetName": ds, "fields": fields, "disaggregated": False,
            "orders": [{"direction": "ASC", "expression": f"`{x}`"}]}}],
        "spec": {"version": 3, "widgetType": "line", "encodings": enc, "frame": {"title": title, "showTitle": True}},
    }}


def bar(name, ds, x, measure, title, fmt=COUNT_FMT, color_dim=None, x_title=None):
    fields = [d(x)] + ([d(color_dim)] if color_dim else []) + [m(measure)]
    enc = {
        "x": {"fieldName": x, "scale": {"type": "categorical"}, "displayName": x_title or x},
        "y": {"fieldName": mref(measure), "scale": {"type": "quantitative"}, "displayName": measure, "format": fmt},
    }
    if color_dim:
        enc["color"] = {"fieldName": color_dim, "scale": {"type": "categorical"}, "displayName": color_dim}
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": fields, "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "bar", "encodings": enc, "frame": {"title": title, "showTitle": True}},
    }}


def pivot(name, ds, rows, columns, cells, title):
    """rows / columns: lists of (field, display); cells: list of (name, expression, display, fmt).
    Grouping sets give PBI-style row and column totals."""
    dims = [f for f, _ in rows + columns]
    fields = [d(f) for f in dims] + [d(n, e) for n, e, _, _ in cells]
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {
            "datasetName": ds, "fields": fields, "disaggregated": False,
            "cubeGroupingSets": {"sets": [{"fieldNames": [f for f, _ in rows]},
                                          {"fieldNames": [f for f, _ in columns]}]},
            "orders": [{"direction": "ASC", "expression": f"`{f}`"} for f in dims]}}],
        "spec": {"version": 3, "widgetType": "pivot", "encodings": {
            "rows": [{"fieldName": f, "displayName": t} for f, t in rows],
            "columns": [{"fieldName": f, "displayName": t} for f, t in columns],
            "cell": {"type": "multi-cell", "fields": [
                {"fieldName": n, "cellType": "text", "format": fmt, "displayName": t} for n, _, t, fmt in cells]}},
            "frame": {"title": title, "showTitle": True}},
    }}


def text(name, lines):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}}}


def multi_filter(name, title, widget_type, bindings, default=None, param_bindings=()):
    """One filter widget bound to the same business field across several datasets.
    bindings: list of (dataset_name, field_name); param_bindings: list of (dataset_name, parameter keyword)."""
    queries, fields = [], []
    for ds, field in bindings:
        qn = f"f_{name}_{ds}"
        queries.append({"name": qn, "query": {"datasetName": ds, "fields": [d(field)], "disaggregated": False}})
        fields.append({"fieldName": field, "displayName": title, "queryName": qn})
    for ds, keyword in param_bindings:
        qn = f"p_{name}_{ds}"
        queries.append({"name": qn, "query": {"datasetName": ds, "parameters": [{"name": keyword, "keyword": keyword}],
                                              "disaggregated": False}})
        fields.append({"parameterName": keyword, "queryName": qn})
    spec = {"version": 2, "widgetType": widget_type, "encodings": {"fields": fields},
            "frame": {"showTitle": True, "title": title}}
    if default:
        spec["selection"] = {"defaultSelection": default}
    return {"widget": {"name": name, "queries": queries, "spec": spec}}


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.layout, self.y = name, display, [], 0

    def row(self, items, h):
        """items: list of (widget, width); widths must sum to 12."""
        assert sum(w for _, w in items) == 12, f"{self.name} y={self.y}: widths {[w for _, w in items]}"
        x = 0
        for widget, w in items:
            self.layout.append({**widget, "position": {"x": x, "y": self.y, "width": w, "height": h}})
            x += w
        self.y += h

    def full(self, widget, h):
        self.row([(widget, 12)], h)

    def to_json(self):
        return {"name": self.name, "displayName": self.display, "pageType": "PAGE_TYPE_CANVAS",
                "layoutVersion": "GRID_V1", "layout": self.layout}


# ---------------------------------------------------------------- global filters

KPI_AND_TREND = ["ds_volume", "ds_volume_trend", "ds_efficiency", "ds_efficiency_trend",
                 "ds_efficiency_rp_avg"]
MANAGING_PRACTICE_FIELD = {"ds_volume": "Managing Practice", "ds_volume_trend": "Managing Practice"}
# Draftable carries Local Region (PBI Localdraf) and Team Rolled Up but no Managing Practice key.
DRAFTABLE = ["ds_draftable", "ds_draftable_trend"]

# "Last complete month": relative-date default. If Lakeview ignores this, the picker simply
# opens unbounded -- see README for the one-time UI check.
LAST_COMPLETE_MONTH = {"range": {"dataType": "DATE", "min": {"value": "now-1M/M"}, "max": {"value": "now-1M/M"}}}


def global_filters_page():
    widgets = [
        multi_filter("g_period", "Period (defaults to last complete month)", "filter-date-range-picker", [
            ("ds_volume", "Final Date"), ("ds_efficiency", "Exam Month"), ("ds_efficiency_rp_avg", "Exam Month"),
            (CAP, "Shift Date"),
            ("ds_draftable", "Calendar Date")], default=LAST_COMPLETE_MONTH,
            param_bindings=[(ds, PERIOD_PARAM) for ds in PROVIDER_PRACTICE + MANAGING_SITE + VS_AVG]),
        multi_filter("g_local", "Local Region", "filter-multi-select",
                     [(ds, "Local Region") for ds in KPI_AND_TREND + DRAFTABLE + CAPACITY + [TIME_SERIES, TS_WU]]),
        multi_filter("g_practice", "Managing Practice", "filter-multi-select",
                     [(ds, MANAGING_PRACTICE_FIELD.get(ds, "Practice")) for ds in KPI_AND_TREND]
                     + [(ds, "Managing Practice") for ds in MANAGING_SITE + [TIME_SERIES, TS_WU]]
                     + [(ds, "Local Practice") for ds in CAPACITY]),
        multi_filter("g_team_rollup", "Team Rolled Up", "filter-multi-select",
                     [(ds, "Team Rolled Up") for ds in KPI_AND_TREND + DRAFTABLE + CAPACITY]
                     + [(ds, "Provider Practice") for ds in PROVIDER_PRACTICE + [TIME_SERIES, TS_WU]]),
    ]
    layout = [{**w, "position": {"x": 0, "y": i * 2, "width": 2, "height": 2}} for i, w in enumerate(widgets)]
    return {"name": "global_filters", "displayName": "Global Filters", "pageType": "PAGE_TYPE_GLOBAL_FILTERS",
            "layoutVersion": "GRID_V1", "layout": layout}


# ---------------------------------------------------------------- pages

DEFINITIONS = [
    "### Definitions & notes\n",
    "- **Baseline / legacy VR** = each radiologist's own pre-Mosaic efficiency on legacy voice recognition. "
    "Efficiency % change = Mosaic efficiency vs. that baseline (TBWU per hour). Implied read-time savings is "
    "the same comparison expressed as time per exam (negative = less time per exam).\n",
    "- **% of RPCE exams** (Reporting / Drafting / Capture) = share of RPCE-sourced exams read in Mosaic, "
    "same +0.02 adjustment as the PowerBI report.\n",
    "- **Drafting** efficiency is restricted to CR/CT exams on both the Mosaic and baseline side "
    "(intentional, documented divergence from the PowerBI page).\n",
    "- **Capacity** = the PowerBI Mosaic Impact Report *Practice Summary* at its defaults: TBWU 26 per shift, "
    "shifts with a baseline only, PowerBI's shift-length exclusions, all shifts. Each shift's Mosaic-era output "
    "(New Capacity) is compared with its legacy shift baseline and averaged per shift; practices without any "
    "TBWU 26 baseline are hidden, as in PowerBI.\n",
    "- **Utilization** = reading time / shift time per shift, averaged (PowerBI *New Utilization*, TBWU 26/Shift). "
    "New Efficiency ignores shifts with efficiency above 1, as PowerBI does.\n",
    "- Outlier exams are excluded from efficiency (PowerBI default). The current month is partial in trend lines.\n",
]


def page_summary():
    p = Page("exec_summary", "Executive Summary")
    p.full(text("es_header", [
        "# Mosaic -- Executive Summary\n",
        "Mosaic (Reporting, AI Drafting, Capture) compared with legacy voice recognition. KPIs follow the "
        "**Period** filter (defaults to the last complete month); trend lines always show full history.\n"]), 2)
    p.row([
        (counter("es_rads_live", "ds_volume", "Mosaic Radiologist Count", "Radiologists reading in Mosaic", COUNT_FMT), 3),
        (counter("es_rpce_reporting", "ds_volume", "Pct RPCE Reporting", "% RPCE exams reported in Mosaic", PCT_FMT), 3),
        (counter("es_rpce_drafting", "ds_volume", "Pct RPCE Drafting", "% RPCE exams AI-drafted", PCT_FMT), 3),
        (counter("es_rpce_capture", "ds_volume", "Pct RPCE Capture", "% RPCE exams captured", PCT_FMT), 3),
    ], 3)
    p.row([
        (counter("es_eff_change", "ds_efficiency", "Full Mosaic Pct Change Vs Baseline",
                 "Efficiency vs legacy VR (Full Mosaic)", PCT_FMT), 3),
        (counter("es_rts", "ds_efficiency", "Full Mosaic Implied Read Time Savings Pct",
                 "Implied read-time change per exam", PCT_FMT), 3),
        (counter("es_eff_drafting", "ds_efficiency", "Drafting Pct Change Vs Baseline",
                 "Efficiency vs legacy VR (AI Drafting, CR/CT)", PCT_FMT), 3),
        (counter("es_eff_exams", "ds_efficiency", "Full Mosaic Mosaic Exams", "Mosaic exams in comparison", COUNT_FMT), 3),
    ], 3)
    p.row([
        (cap_counter("es_cap_pct_addl", "Pct Addl Capacity", "% Add'l capacity vs baseline (TBWU 26/shift)"), 3),
        (cap_counter("es_cap_addl", "Addl Capacity Per Shift", "Add'l capacity per shift (TBWU 26)"), 3),
        (cap_counter("es_util", "New Utilization", "Utilization (New Utilization)"), 3),
        (cap_counter("es_cap_shifts", "Selected Shifts", "Shifts with a baseline"), 3),
    ], 3)
    p.row([
        (line("es_trend_rpce", "ds_volume_trend", "Final Month",
              [("Pct RPCE Reporting", "Reporting"), ("Pct RPCE Drafting", "Drafting"), ("Pct RPCE Capture", "Capture")],
              "% of RPCE exams by solution (monthly)", PCT_FMT), 4),
        (line("es_trend_eff", "ds_efficiency_trend", "Exam Month",
              [("Full Mosaic Pct Change Vs Baseline", "Full Mosaic"), ("Drafting Pct Change Vs Baseline", "Drafting")],
              "Efficiency vs legacy VR (monthly)", PCT_FMT), 4),
        (line_expr("es_trend_util", CAP_TREND, "Shift Month",
                   [("New Utilization", "Utilization", CAP_COLS["New Utilization"][1]),
                    ("Pct Addl Capacity", "% Add'l capacity", CAP_COLS["Pct Addl Capacity"][1])],
                   "Capacity & utilization (monthly)", PCT_FMT), 4),
    ], 6)
    p.row([
        (text("es_definitions", DEFINITIONS), 9),
        (table("es_data_through", "ds_volume_trend", [d("Exams through", "MAX(`Final Date`)")],
               [col("Exams through", "Exams through")], "Data freshness"), 3),
    ], 7)
    return p


def page_adoption():
    p = Page("adoption", "Adoption")
    p.full(text("ad_header", [
        "# Adoption -- Reporting, AI Drafting, Capture\n",
        "Who is on Mosaic and how much of the RPCE workload runs through each solution.\n"]), 2)
    p.row([
        (counter("ad_rads", "ds_volume", "Mosaic Radiologist Count", "Rads on Mosaic", COUNT_FMT), 2),
        (counter("ad_draft_rads", "ds_volume", "Drafting Radiologist Count", "Rads drafting", COUNT_FMT), 2),
        (counter("ad_capture_rads", "ds_volume", "Capture Radiologist Count", "Rads capturing", COUNT_FMT), 2),
        (counter("ad_pct_rpce_rads", "ds_volume", "Pct Mosaic Of RPCE Radiologists", "% of RPCE rads on Mosaic", PCT_FMT), 2),
        (counter("ad_pct_rpce_all", "ds_volume", "Pct RPCE Of All Exams", "% of all exams on RPCE", PCT_FMT), 2),
        (counter("ad_pct_mosaic_rvu", "ds_volume", "Pct Mosaic RVU", "% of RVU in Mosaic", PCT_FMT), 2),
    ], 3)
    p.row([
        (counter("ad_mosaic_exams", "ds_volume", "Mosaic Exam Count", "Mosaic exams", COUNT_FMT), 2),
        (counter("ad_draft_exams", "ds_volume", "Drafting Exam Count", "Drafted exams", COUNT_FMT), 2),
        (counter("ad_capture_exams", "ds_volume", "Captured Exam Count", "Captured exams", COUNT_FMT), 2),
        (counter("ad_pct_ct", "ds_volume", "Pct CT RPCE", "% CT RPCE in Mosaic", PCT_FMT), 2),
        (counter("ad_pct_head_ct", "ds_volume", "Pct Head CT RPCE", "% Head CT RPCE in Mosaic", PCT_FMT), 2),
        (counter("ad_pct_draft_rvu", "ds_volume", "Pct Drafting RVU", "% of RVU drafted", PCT_FMT), 2),
    ], 3)
    p.row([
        (line("ad_trend_rpce", "ds_volume_trend", "Final Month",
              [("Pct RPCE Reporting", "Reporting"), ("Pct RPCE Drafting", "Drafting"), ("Pct RPCE Capture", "Capture")],
              "% of RPCE exams by solution (monthly)", PCT_FMT), 6),
        (line("ad_trend_exams", "ds_volume_trend", "Final Month",
              [("Mosaic Exam Count", "Mosaic"), ("Drafting Exam Count", "Drafted"), ("Captured Exam Count", "Captured")],
              "Mosaic exam volume (monthly)", COUNT_FMT), 6),
    ], 6)
    measures = [
        ("Mosaic Radiologist Count", "Rads on Mosaic", COUNT_FMT), ("Drafting Radiologist Count", "Rads drafting", COUNT_FMT),
        ("Exam Count", "Exams", COUNT_FMT), ("Mosaic Exam Count", "Mosaic exams", COUNT_FMT),
        ("Pct RPCE Reporting", "% RPCE reported", PCT_FMT), ("Pct RPCE Drafting", "% RPCE drafted", PCT_FMT),
        ("Pct RPCE Capture", "% RPCE captured", PCT_FMT), ("Pct Mosaic RVU", "% RVU in Mosaic", PCT_FMT),
    ]
    for key, dims, title, h in [
        ("region", ["Local Region"], "By Local Region", 6),
        ("practice", ["Local Region", "Managing Practice"], "By Managing Practice", 10),
        ("team", ["Team Rolled Up", "Team"], "By Team (reading radiologist's pool)", 10),
    ]:
        fields = [d(x) for x in dims] + [m(n) for n, _, _ in measures]
        cols = [col(x, x) for x in dims] + [col(mref(n), t, f) for n, t, f in measures]
        p.full(table(f"ad_by_{key}", "ds_volume", fields, cols, title,
                     order=(f"MEASURE(`Mosaic Exam Count`)", "DESC")), h)
    return p


def page_efficiency():
    p = Page("efficiency", "Efficiency")
    p.full(text("ef_header", [
        "# Efficiency -- Mosaic vs legacy voice recognition\n",
        "Each radiologist is compared with their own legacy-VR baseline, by mode. Positive % = more work per hour.\n"]), 2)
    for key, label, suffix, fmt in [
        ("chg", "**% efficiency change vs legacy VR**", "Pct Change Vs Baseline", PCT_FMT),
        ("rts", "**Implied read-time change per exam**", "Implied Read Time Savings Pct", PCT_FMT),
        ("exams", "**Mosaic exams compared**", "Mosaic Exams", COUNT_FMT),
    ]:
        p.row([(text(f"ef_lbl_{key}", [label + "\n"]), 2)] + [
            (counter(f"ef_{key}_{mode.lower().replace(' ', '_')}", "ds_efficiency", f"{mode} {suffix}", title, fmt), 2)
            for mode, title in MODES], 3)
    p.row([
        (counter("ef_mosaic_eff", "ds_efficiency", "Full Mosaic Mosaic Efficiency", "Mosaic efficiency (Full Mosaic)", NUM_FMT), 3),
        (counter("ef_base_eff", "ds_efficiency", "Full Mosaic Baseline Efficiency", "Legacy VR baseline efficiency", NUM_FMT), 3),
        (counter("ef_own_eff", "ds_efficiency_rp_avg", "Full Mosaic Own Efficiency", "Own efficiency (vs RP avg basis)", NUM_FMT), 2),
        (counter("ef_rp_avg", "ds_efficiency_rp_avg", "Full Mosaic RP Avg Efficiency", "RP average efficiency", NUM_FMT), 2),
        (counter("ef_vs_rp", "ds_efficiency_rp_avg", "Full Mosaic Efficiency Vs RP Avg", "vs RP average (1.0 = avg)", NUM_FMT,
                 "Always 1.0 company-wide; filter to a region, practice or team to benchmark it."), 2),
    ], 3)
    time_series_section(p)
    wu_time_series_section(p)
    provider_practice_section(p)
    managing_practice_section(p)
    vs_avg_section(p)
    vs_avg_ts_section(p)
    fields = [d("Team Rolled Up"), m("Full Mosaic Own Exams"), m("Full Mosaic Own Efficiency"),
              m("Full Mosaic RP Avg Efficiency"), m("Full Mosaic Efficiency Vs RP Avg"),
              m("Drafting Efficiency Vs RP Avg")]
    cols = [col("Team Rolled Up", "Team Rolled Up"), col(mref("Full Mosaic Own Exams"), "Exams", COUNT_FMT),
            col(mref("Full Mosaic Own Efficiency"), "Own efficiency", NUM_FMT),
            col(mref("Full Mosaic RP Avg Efficiency"), "RP avg efficiency", NUM_FMT),
            col(mref("Full Mosaic Efficiency Vs RP Avg"), "Full Mosaic vs RP avg", NUM_FMT, sign_rules("1")),
            col(mref("Drafting Efficiency Vs RP Avg"), "Drafting vs RP avg", NUM_FMT, sign_rules("1"))]
    p.full(table("ef_vs_rp_by_team", "ds_efficiency_rp_avg", fields, cols, "Benchmark: efficiency vs RP average by Team",
                 order=("MEASURE(`Full Mosaic Own Exams`)", "DESC")), 8)
    return p


PP_VALUES = [("Mosaic Exams", "Mosaic exams", COUNT_FMT, None),
             ("Baseline Efficiency", "Baseline efficiency", NUM_FMT, None),
             ("Mosaic Efficiency", "Mosaic efficiency", NUM_FMT, None),
             ("Pct Change Vs Baseline", "% change vs baseline", PCT_FMT, "0")]
FULL_MOSAIC = {"values": {"dataType": "STRING", "values": [{"value": "Full Mosaic"}]}}


MP_VALUES = [("Site Total Mosaic Exams", "Site total Mosaic exams (all time)", COUNT_FMT, None),
             ("Baseline Exams", "Baseline exams (all time)", COUNT_FMT, None)] + PP_VALUES + [
             ("Implied Read Time Savings Pct", "Implied read-time savings", PCT_FMT, None)]


def pp_table(name, ds, dims, title, orders, hidden=(), values=PP_VALUES):
    fields = [d(x) for x in dims + list(hidden)] + [d(n) for n, _, _, _ in values]
    cols = [col(x, x) for x in dims] + [col(n, t, f, sign_rules(r) if r else None) for n, t, f, r in values]
    w = table(name, ds, fields, cols, title, disaggregated=True)
    w["widget"]["queries"][0]["query"]["orders"] = [{"direction": dr, "expression": f"`{e}`"} for e, dr in orders]
    return w


def provider_practice_section(p):
    """By Provider Practice -- PBI's page as sent to the CEO monthly, with its visual-level filters replicated."""
    p.full(text("ef_pp_header", [
        "## By Provider Practice -- monthly executive send-out numbers\n",
        "Same logic as the PowerBI *By Provider Practice* page, including its visual-level filters: a radiologist / "
        "parent exam is shown only when it has Mosaic exams, a legacy-VR baseline and a non-blank efficiency. "
        "Practice rows are pooled the way PowerBI pools them, so **a practice row is not the sum of its radiologist "
        "rows**. Follows the global **Period** and **Team Rolled Up** filters only (the PowerBI page has no Region / "
        "Managing Practice slicer). Provider Practice = the radiologist's home practice (Team Rolled Up).\n"]), 3)
    p.row([
        (multi_filter("ef_pp_f_mode", "Mode", "filter-single-select",
                      [(ds, "Mode") for ds in PROVIDER_PRACTICE], default=FULL_MOSAIC), 3),
        (multi_filter("ef_pp_f_practice", "Provider Practice", "filter-multi-select",
                      [("ds_pp_rad", "Provider Practice"), ("ds_pp_exam", "Provider Practice")]), 3),
        (multi_filter("ef_pp_f_rad", "Radiologist", "filter-multi-select",
                      [("ds_pp_rad", "Radiologist"), ("ds_pp_exam", "Radiologist")]), 3),
        (table("ef_pp_window", "ds_pp_practice",
               [d("Window Start", "MIN(`Window Start`)"), d("Window End", "MAX(`Window End`)")],
               [col("Window Start", "From"), col("Window End", "To")], "Period applied"), 3),
    ], 2)
    p.full(pp_table("ef_pp_practice", "ds_pp_practice", ["Provider Practice", "Radiologists"],
                    "By Provider Practice (Total row last = all radiologists, pooled)",
                    [("sort_key", "DESC"), ("Mosaic Exams", "DESC")], hidden=["sort_key"]), 12)
    p.full(pp_table("ef_pp_rad", "ds_pp_rad", ["Provider Practice", "Radiologist"], "By Radiologist",
                    [("Provider Practice", "ASC"), ("Mosaic Exams", "DESC")]), 12)
    p.full(pp_table("ef_pp_exam", "ds_pp_exam", ["Provider Practice", "Radiologist", "Parent Exam"],
                    "By Parent Exam (pick a practice or radiologist above)",
                    [("Radiologist", "ASC"), ("Mosaic Exams", "DESC")]), 10)


def managing_practice_section(p):
    """By Managing Practice -> Site -- PBI's page of the same name, with its site-level visual filters replicated."""
    p.full(text("ef_mp_header", [
        "## By Managing Practice -- practices and the sites they manage\n",
        "Same logic as the PowerBI *By Managing Practice* page. **Managing Practice** is the practice that owns the "
        "exam site (not the radiologist's home practice). A site is shown when it has Mosaic exams, read time and a "
        "non-zero baseline and Mosaic efficiency in the period. Practice and Total rows pool their sites "
        "(time-weighted). *Site total Mosaic exams* and *Baseline exams* are all-time counts, as in PowerBI. "
        "Follows the global **Period** and **Managing Practice** filters.\n"]), 3)
    p.row([
        (multi_filter("ef_mp_f_mode", "Mode", "filter-single-select",
                      [(ds, "Mode") for ds in MANAGING_SITE], default=FULL_MOSAIC), 4),
        (multi_filter("ef_mp_f_practice", "Managing Practice (sites table)", "filter-multi-select",
                      [("ds_mp_site", "Managing Practice")]), 4),
        (table("ef_mp_window", "ds_mp_practice",
               [d("Window Start", "MIN(`Window Start`)"), d("Window End", "MAX(`Window End`)")],
               [col("Window Start", "From"), col("Window End", "To")], "Period applied"), 4),
    ], 2)
    p.full(pp_table("ef_mp_practice", "ds_mp_practice", ["Managing Practice", "Sites"],
                    "By Managing Practice (Total row first = all sites, pooled)",
                    [("sort_key", "ASC"), ("Mosaic Exams", "DESC")], hidden=["sort_key"], values=MP_VALUES), 12)
    p.full(pp_table("ef_mp_site", "ds_mp_site", ["Managing Practice", "Site"], "By Site",
                    [("Managing Practice", "ASC"), ("Mosaic Exams", "DESC")], values=MP_VALUES), 12)


VA_VALUES = [("Mosaic Exams All Time", "Mosaic exams (all time)", COUNT_FMT, None),
             ("Mosaic Exams Period", "Mosaic exams (period)", COUNT_FMT, None),
             ("Mosaic Efficiency", "Mosaic efficiency", NUM_FMT, None),
             ("Vs RP Avg Overall", "vs RP avg (overall)", NUM_FMT, "1"),
             ("Vs RP Avg", "vs RP avg (shown radiologists)", NUM_FMT, "1")]


def vs_avg_section(p):
    """Mosaic Efficiency vs Average -- PBI's page of the same name: benchmark cards per mode plus the
    Team Rolled Up -> Radiologist -> Parent Exam pivot with its Rad_Qualifies_NB / Has_Data_NB visual filter."""
    p.full(text("ef_va_header", [
        "## Mosaic efficiency vs average -- who is above or below the benchmark\n",
        "Same logic as the PowerBI *Mosaic Efficiency vs Average* page. Efficiency = TBWU per minute of Mosaic read "
        "time. A radiologist is listed when their Mosaic exams in the period reach **Min exams** (PowerBI default "
        "100); each parent exam row also needs exams and read time. **vs RP avg (shown radiologists)** divides by the "
        "benchmark of the radiologists listed (the Total row, = 1.0); **vs RP avg (overall)** divides by the "
        "all-radiologist benchmark. Above 1.0 = faster than average. Benchmarks are company-wide and follow the "
        "global **Period** only. *Mosaic exams (all time)* ignores the period, as in PowerBI. Modes: Drafting Only = "
        "drafting on CR/CT; Capture Only = drafting on US/BD; Drafting + Capture = CR/CT/US/BD.\n"]), 4)
    p.row([
        (multi_filter("ef_va_f_mode", "Mode", "filter-single-select",
                      [(ds, "Mode") for ds in VS_AVG if ds != "ds_va_cards"], default=FULL_MOSAIC), 3),
        (multi_filter("ef_va_f_min", "Min exams (PBI default 100)", "filter-text-entry", [],
                      param_bindings=[(ds, MIN_EXAMS_PARAM) for ds in VS_AVG]), 3),
        (multi_filter("ef_va_f_practice", "Provider Practice", "filter-multi-select",
                      [("ds_va_rad", "Provider Practice"), ("ds_va_exam", "Provider Practice")]), 3),
        (multi_filter("ef_va_f_rad", "Radiologist", "filter-multi-select",
                      [("ds_va_rad", "Radiologist"), ("ds_va_exam", "Radiologist")]), 3),
    ], 2)
    card_vals = [("Radiologists", "Radiologists (min exams met)", COUNT_FMT, None),
                 ("Pop Avg Efficiency", "Benchmark: radiologists with read time", NUM_FMT, None),
                 ("RP Avg Efficiency Overall", "Benchmark: overall (vs RP avg overall basis)", NUM_FMT, None),
                 ("Shown Population Benchmark", "Benchmark: shown radiologists (Total row)", NUM_FMT, None)]
    p.full(pp_table("ef_va_cards", "ds_va_cards", ["Mode"], "Benchmark efficiency by mode (PowerBI cards)",
                    [("sort_key", "ASC")], hidden=["sort_key"], values=card_vals), 5)
    p.full(pp_table("ef_va_team", "ds_va_team", ["Provider Practice", "Radiologists"],
                    "By Provider Practice (Total row first = the benchmark)",
                    [("sort_key", "ASC"), ("Mosaic Exams Period", "DESC")], hidden=["sort_key"], values=VA_VALUES), 12)
    p.full(pp_table("ef_va_rad", "ds_va_rad", ["Provider Practice", "Radiologist", "Subspecialty"], "By Radiologist",
                    [("Provider Practice", "ASC"), ("Mosaic Exams Period", "DESC")], values=VA_VALUES), 12)
    p.full(pp_table("ef_va_exam", "ds_va_exam", ["Provider Practice", "Radiologist", "Parent Exam"],
                    "By Parent Exam (pick a practice or radiologist above)",
                    [("Radiologist", "ASC"), ("Mosaic Exams Period", "DESC")], values=VA_VALUES), 10)


# Efficiency change from summed sums: (60*W/T - C/T) / (C/T) = 60*W/C - 1 (T cancels).
TS_CHANGE = "60 * SUM(`w`) / SUM(`c`) - 1"
ALL_MODES = {"values": {"dataType": "STRING", "values": [{"value": v} for _, v in MODES]}}
LAST_SIX_MONTHS = {"range": {"dataType": "DATE", "min": {"value": "now-6M/M"}, "max": {"value": "now-1M/M"}}}


def ts_line(name, grain, title):
    x = f"{grain.title()} Starting"
    w = line(name, TIME_SERIES, x, [], title, PCT_FMT, color_dim="Mode")
    q = w["widget"]["queries"][0]["query"]
    q["fields"] = [d(x, f'DATE_TRUNC("{grain}", `Exam Date`)'), d("Mode"), d("Efficiency Change", TS_CHANGE),
                   d("Exams", "SUM(`x`)")]
    q["orders"] = [{"direction": "ASC", "expression": f'DATE_TRUNC("{grain}", `Exam Date`)'}]
    w["widget"]["spec"]["encodings"]["y"] = {"fieldName": "Efficiency Change", "displayName": "Efficiency change",
                                             "scale": {"type": "quantitative"}, "format": PCT_FMT}
    return w


def time_series_section(p):
    """Efficiency Change, Time Series -- PBI Mode_Lines[Efficiency_Change_By_Mode_Line] with its all-time gate."""
    p.full(text("ef_ts_header", [
        "## Efficiency change over time, by mode\n",
        "Same logic as the PowerBI *Efficiency Change, Time Series* page. A radiologist counts in a mode when, over "
        "all time, they meet *Min exams* and have read time, TBWU and a legacy-VR baseline in that mode; each point "
        "pools those radiologists' work in that week / month (time-weighted). Weeks start Monday; the first and last "
        "point are clipped to the window. Follows its own **Time-series window** plus the global **Local Region**, "
        "**Managing Practice** and **Team Rolled Up** filters.\n"]), 3)
    p.row([
        (multi_filter("ef_ts_f_window", "Time-series window", "filter-date-range-picker",
                      [(TIME_SERIES, "Exam Date")], default=LAST_SIX_MONTHS), 4),
        (multi_filter("ef_ts_f_mode", "Mode", "filter-multi-select", [(TIME_SERIES, "Mode")], default=ALL_MODES), 4),
        (multi_filter("ef_ts_f_min", "Min exams (PBI default 0)", "filter-text-entry", [],
                      param_bindings=[(TIME_SERIES, MIN_EXAMS_PARAM)]), 4),
    ], 2)
    p.row([(ts_line("ef_ts_week", "WEEK", "Efficiency change vs legacy VR -- weekly"), 6),
           (ts_line("ef_ts_month", "MONTH", "Efficiency change vs legacy VR -- monthly"), 6)], 7)
    fields = [d("Mode"), d("Radiologists", "COUNT(DISTINCT `Radiologist`)"), d("Exams", "SUM(`x`)"),
              d("Efficiency Change", TS_CHANGE)]
    cols = [col("Mode", "Mode"), col("Radiologists", "Radiologists (window)", COUNT_FMT),
            col("Exams", "Mosaic exams (window)", COUNT_FMT),
            col("Efficiency Change", "Efficiency change (window)", PCT_FMT, sign_rules("0"))]
    rad_fields = [d("Radiologist"), d("Provider Practice", "MIN(`Provider Practice`)"), d("Mode"),
                  d("Exams", "SUM(`x`)"), d("Efficiency Change", TS_CHANGE)]
    rad_cols = [col("Radiologist", "Radiologist"), col("Provider Practice", "Provider Practice"), col("Mode", "Mode"),
                col("Exams", "Mosaic exams (window)", COUNT_FMT),
                col("Efficiency Change", "Efficiency change (window)", PCT_FMT, sign_rules("0"))]
    p.row([(table("ef_ts_by_mode", TIME_SERIES, fields, cols, "Window totals by mode (PowerBI tooltip counts)",
                  order=("SUM(`x`)", "DESC")), 5),
           (table("ef_ts_rads", TIME_SERIES, rad_fields, rad_cols, "Radiologist detail (PowerBI Rad Detail Export)",
                  order=("SUM(`x`)", "DESC")), 7)], 8)


WU_FMT = {"type": "number", "decimalPlaces": {"type": "exact", "places": 3}}
WU_CELLS = [("WU per Min", "60 * SUM(`w`) / SUM(`t`)", "WU/min", WU_FMT), ("Exams", "SUM(`x`)", "Exams", COUNT_FMT)]
BOTH_PLATFORMS = {"values": {"dataType": "STRING", "values": [{"value": "Both"}]}}


def wu_time_series_section(p):
    """Time Series -- PBI Mosaic Mode[Mean Work Units per Minmode (With Vol)] / [VolumeMode] matrix by month."""
    p.full(text("ef_wu_header", [
        "## Work units per minute by month -- legacy VR, Mosaic or both\n",
        "Same logic as the PowerBI *Time Series* page: TBWU per minute of read time, pooled per cell, shown only "
        "where there are exams. **Platform** Legacy = legacy-VR (baseline) exams; Mosaic = the selected **Mode**; "
        "Both = the two together. Mode is ignored when Platform = Legacy, as in PowerBI. Drafting Only covers every "
        "modality and Capture Only is drafting on US/BD, as on the PowerBI page. Outliers excluded. Follows its own "
        "**Month window** plus the global **Local Region**, **Managing Practice** and **Team Rolled Up** filters.\n"]), 3)
    p.row([
        (multi_filter("ef_wu_f_platform", "Platform", "filter-single-select", [(TS_WU, "Platform")],
                      default=BOTH_PLATFORMS), 2),
        (multi_filter("ef_wu_f_mode", "Mode", "filter-single-select", [(TS_WU, "Mode")], default=FULL_MOSAIC), 2),
        (multi_filter("ef_wu_f_window", "Month window", "filter-date-range-picker", [(TS_WU, "Month")],
                      default=LAST_SIX_MONTHS), 3),
        (multi_filter("ef_wu_f_practice", "Provider Practice", "filter-multi-select",
                      [(TS_WU, "Provider Practice")]), 3),
        (multi_filter("ef_wu_f_rad", "Radiologist", "filter-multi-select", [(TS_WU, "Radiologist")]), 2),
    ], 2)
    month = [("Month Label", "Month")]
    p.full(pivot("ef_wu_practice", TS_WU, [("Provider Practice", "Provider Practice")], month, WU_CELLS,
                 "WU/min by Provider Practice and month"), 10)
    p.full(pivot("ef_wu_rad", TS_WU, [("Provider Practice", "Provider Practice"), ("Radiologist", "Radiologist")],
                 month, WU_CELLS, "WU/min by Radiologist and month"), 12)
    p.full(pivot("ef_wu_exam", TS_WU, [("Radiologist", "Radiologist"), ("Parent Exam", "Parent Exam")], month,
                 WU_CELLS, "WU/min by Parent Exam and month (pick a practice or radiologist above)"), 12)


LAST_TWELVE_MONTHS = {"range": {"dataType": "DATE", "min": {"value": "now-12M/M"}, "max": {"value": "now-1M/M"}}}
# Mode_Lines_NB1[ModeLine] -> Benchmark_By_Mode_Line1. Pooled over qualified radiologists; RP Avg lines are the
# company-wide monthly columns, shown only where the selection has rows in that bucket (_hasDraftingData etc.).
VA_TS_LINES = [
    ("Drafting Only", "60 * SUM(`w_d`) / NULLIF(SUM(`t_d`), 0)"),
    ("Non-Drafted", "60 * SUM(`w_r`) / NULLIF(SUM(`t_r`), 0)"),
    ("Full Mosaic", "60 * SUM(`w_f`) / NULLIF(SUM(`t_f`), 0)"),
    ("RP Avg, Drafting Only", "CASE WHEN SUM(`n_d`) > 0 THEN 60 * MAX(`rp_w_d`) / NULLIF(MAX(`rp_t_d`), 0) END"),
    ("RP Avg, Full Mosaic", "CASE WHEN SUM(`n_f`) > 0 THEN 60 * MAX(`rp_w_f`) / NULLIF(MAX(`rp_t_f`), 0) END"),
]
VA_TS_COUNTS = [
    ("Radiologists", "COUNT(DISTINCT `active_rad`)", "Radiologists (Rad_Count_By_Month)"),
    ("Mosaic Exams", "SUM(`x_f`)", "Mosaic exams (Full Mosaic)"),
    ("Drafting Exams", "SUM(`x_d`)", "Drafting exams (CR/CT)"),
    ("Reporting Exams", "SUM(`x_r`)", "Non-drafted exams"),
]


def vs_avg_ts_section(p):
    """Mosaic Efficiency, Time Series Viz -- PBI Mode_Lines_NB1[ModeLine] x Benchmark_By_Mode_Line1 by YearMonth,
    with the Rad_Count_By_Month / Exam_Count_* tooltips as a month table."""
    p.full(text("ef_vats_header", [
        "## Mosaic efficiency vs average over time\n",
        "Same logic as the PowerBI *Mosaic Efficiency, Time Series Viz* page. Each month shows the efficiency (TBWU "
        "per minute of Mosaic read time) of the selected radiologists -- Drafting Only (drafting on CR/CT), "
        "Non-Drafted (reporting) and Full Mosaic -- against the **RP Avg** lines, which are always every "
        "radiologist company-wide in that month, whatever Provider Practice or Radiologist is picked. A radiologist "
        "is included once their all-time Mosaic exams reach **Min exams** (PowerBI default 0). Outliers and "
        "interventional exams excluded. Follows its own filters only.\n"]), 3)
    p.row([
        (multi_filter("ef_vats_f_window", "Month window", "filter-date-range-picker", [(VS_AVG_TS, "Month")],
                      default=LAST_TWELVE_MONTHS), 3),
        (multi_filter("ef_vats_f_min", "Min exams (PBI default 0)", "filter-text-entry", [],
                      param_bindings=[(VS_AVG_TS, MIN_EXAMS_PARAM)]), 3),
        (multi_filter("ef_vats_f_practice", "Provider Practice", "filter-multi-select",
                      [(VS_AVG_TS, "Provider Practice")]), 3),
        (multi_filter("ef_vats_f_rad", "Radiologist", "filter-multi-select", [(VS_AVG_TS, "Radiologist")]), 3),
    ], 2)
    w = line("ef_vats_line", VS_AVG_TS, "Month", [], "Mosaic efficiency vs RP average -- monthly", NUM_FMT)
    q = w["widget"]["queries"][0]["query"]
    q["fields"] = [d("Month")] + [d(n, e) for n, e in VA_TS_LINES]
    w["widget"]["spec"]["encodings"]["y"] = {
        "fields": [{"fieldName": n, "displayName": n} for n, _ in VA_TS_LINES],
        "scale": {"type": "quantitative"}, "format": NUM_FMT}
    p.full(w, 8)
    fields = [d("Month Label")] + [d(n, e) for n, e, _ in VA_TS_COUNTS] + [d(n, e) for n, e in VA_TS_LINES]
    cols = ([col("Month Label", "Month")] + [col(n, t, COUNT_FMT) for n, _, t in VA_TS_COUNTS]
            + [col(n, n, NUM_FMT) for n, _ in VA_TS_LINES])
    p.full(table("ef_vats_table", VS_AVG_TS, fields, cols, "By month (PowerBI tooltip counts)",
                 order=("`Month Label`", "DESC")), 7)


_BL, _CAP = "AVG(`shift_baseline_RPWU`)", "AVG(`on_shift_capacity_RPWU`)"
# The PBI Practice Summary columns (Mosaic Impact Report, Unit = TBWU 26/Shift):
# field -> (PBI column title, aggregate expression = PBI measure, format, green/red on sign)
CAP_COLS = {
    "Selected Shifts": ("Selected Shift Ct", "COUNT(1)", COUNT_FMT, False),
    "Average Baseline": ("Average Baseline", _BL, NUM_FMT, False),
    "New Capacity": ("New Capacity", _CAP, NUM_FMT, False),
    "Addl Capacity Per Shift": ("Add'l Capacity/Shift", f"{_CAP} - {_BL}", NUM_FMT, True),
    "Pct Addl Capacity": ("% Add'l Capacity", f"({_CAP} - {_BL}) / NULLIF({_BL}, 0)", PCT_FMT, True),
    "Pct Mosaic": ("% Mosaic", "SUM(`on_shift_mosaic_cases`) / NULLIF(SUM(`on_shift_cases`), 0)", PCT_FMT, False),
    "Pct Mosaic Drafting": ("% Mosaic Drafting",
                            "SUM(`on_shift_mosaic_drafting_cases`) / NULLIF(SUM(`on_shift_cases`), 0)", PCT_FMT, False),
    "New Efficiency": ("New Efficiency",
                       "AVG(CASE WHEN `on_shift_efficiency_RPWU` <= 1 THEN `on_shift_efficiency_RPWU` END)", NUM_FMT, False),
    "New Utilization": ("New Utilization", "AVG(`on_shift_utilization_RPWU_pct` / 100)", PCT_FMT, False),
}


def cap_counter(name, field, title=None, ds=CAP):
    t, expr, fmt, _ = CAP_COLS[field]
    return counter_expr(name, ds, field, expr, title or t, fmt)


def cap_table(name, dims, title, order_by="Selected Shifts"):
    fields = [d(x) for x in dims] + [d(f, e) for f, (_, e, _, _) in CAP_COLS.items()]
    cols = [col(x, x) for x in dims] + [col(f, t, fmt, sign_rules() if sign else None)
                                        for f, (t, _, fmt, sign) in CAP_COLS.items()]
    return table(name, CAP, fields, cols, title, order=(CAP_COLS[order_by][1], "DESC"))


def page_capacity():
    p = Page("capacity", "Capacity & Utilization")
    p.full(text("cp_header", [
        "# Capacity & Utilization\n",
        "The PowerBI Mosaic Impact Report *Practice Summary*, same logic and defaults: TBWU 26 per shift, shifts "
        "with a baseline, all shifts. Each shift's Mosaic-era capacity is compared with its legacy baseline and "
        "averaged per shift. Practices with no TBWU 26 baseline in the month are hidden, as in PowerBI.\n"]), 2)
    p.row([
        (cap_counter("cp_shifts", "Selected Shifts"), 3),
        (cap_counter("cp_base", "Average Baseline"), 3),
        (cap_counter("cp_cap", "New Capacity"), 3),
        (cap_counter("cp_addl", "Addl Capacity Per Shift"), 3),
    ], 3)
    p.row([
        (cap_counter("cp_pct_addl", "Pct Addl Capacity"), 3),
        (cap_counter("cp_util", "New Utilization"), 3),
        (cap_counter("cp_eff", "New Efficiency"), 2),
        (cap_counter("cp_mosaic", "Pct Mosaic"), 2),
        (cap_counter("cp_drafting", "Pct Mosaic Drafting"), 2),
    ], 3)
    p.row([
        (line_expr("cp_trend_cap", CAP_TREND, "Shift Month",
                   [(f, CAP_COLS[f][0], CAP_COLS[f][1]) for f in ("Average Baseline", "New Capacity")],
                   "Average baseline vs new capacity per shift (TBWU 26, monthly)", NUM_FMT), 6),
        (line_expr("cp_trend_util", CAP_TREND, "Shift Month",
                   [(f, CAP_COLS[f][0], CAP_COLS[f][1]) for f in ("New Utilization", "Pct Addl Capacity")],
                   "Utilization and % add'l capacity (monthly)", PCT_FMT), 6),
    ], 6)
    p.full(cap_table("cp_by_practice", ["Local Region", "Local Practice"], "Practice Summary"), 10)
    return p


def page_drilldown():
    p = Page("drilldown", "Radiologist & Practice Drill-down")
    p.full(text("dd_header", [
        "# Radiologist & Practice drill-down\n",
        "Pick a radiologist (or use the global Region / Practice / Team filters) -- every table below follows.\n"]), 2)
    p.row([
        (multi_filter("dd_f_rad", "Radiologist", "filter-multi-select", [
            ("ds_volume", "Radiologist Name"), ("ds_efficiency", "Radiologist Name"),
            ("ds_efficiency_rp_avg", "Radiologist Name"), (CAP, "Radiologist"),
            ("ds_shift_baselines", "Radiologist")]), 6),
        (multi_filter("dd_f_team", "Team (radiologist's pool)", "filter-multi-select", [
            ("ds_volume", "Team"), ("ds_efficiency", "Team"), ("ds_efficiency_rp_avg", "Team"), (CAP, "Team")]), 6),
    ], 2)

    vol = [("Exam Count", "Exams", COUNT_FMT), ("Mosaic Exam Count", "Mosaic exams", COUNT_FMT),
           ("Pct Mosaic Exams", "% Mosaic", PCT_FMT), ("Drafting Exam Count", "Drafted", COUNT_FMT),
           ("Pct Drafting Exams", "% Drafted", PCT_FMT), ("Captured Exam Count", "Captured", COUNT_FMT),
           ("Pct RPCE Reporting", "% RPCE reported", PCT_FMT)]
    vol.insert(0, ("First Mosaic Exam Date", "First Mosaic exam", None))
    dims = ["Radiologist Name", "NPI", "Team"]
    p.full(table("dd_volume", "ds_volume", [d(x) for x in dims] + [m(n) for n, _, _ in vol],
                 [col(x, x) for x in dims] + [col(mref(n), t, f) for n, t, f in vol],
                 "Adoption by radiologist", order=("MEASURE(`Exam Count`)", "DESC")), 10)

    eff = [("Full Mosaic Mosaic Exams", "Mosaic exams", COUNT_FMT, None),
           ("Full Mosaic Mosaic Efficiency", "Mosaic efficiency", NUM_FMT, None),
           ("Full Mosaic Baseline Efficiency", "Baseline efficiency", NUM_FMT, None),
           ("Full Mosaic Pct Change Vs Baseline", "Full Mosaic % change", PCT_FMT, "0"),
           ("Reporting Pct Change Vs Baseline", "Reporting % change", PCT_FMT, "0"),
           ("Drafting Pct Change Vs Baseline", "Drafting % change", PCT_FMT, "0"),
           ("Full Mosaic Implied Read Time Savings Pct", "Implied read-time change", PCT_FMT, None)]
    dims = ["Radiologist Name", "NPI", "Team"]
    p.full(table("dd_efficiency", "ds_efficiency", [d(x) for x in dims] + [m(n) for n, _, _, _ in eff],
                 [col(x, x) for x in dims] + [col(mref(n), t, f, sign_rules(r) if r else None) for n, t, f, r in eff],
                 "Efficiency vs legacy VR by radiologist", order=("MEASURE(`Full Mosaic Mosaic Exams`)", "DESC")), 10)

    rp = [("Full Mosaic Own Exams", "Exams", COUNT_FMT, None), ("Full Mosaic Own Efficiency", "Own efficiency", NUM_FMT, None),
          ("Full Mosaic RP Avg Efficiency", "RP avg efficiency", NUM_FMT, None),
          ("Full Mosaic Efficiency Vs RP Avg", "vs RP avg", NUM_FMT, "1")]
    p.full(table("dd_vs_rp", "ds_efficiency_rp_avg", [d(x) for x in dims] + [m(n) for n, _, _, _ in rp],
                 [col(x, x) for x in dims] + [col(mref(n), t, f, sign_rules(r) if r else None) for n, t, f, r in rp],
                 "Efficiency vs RP average by radiologist", order=("MEASURE(`Full Mosaic Own Exams`)", "DESC")), 8)

    p.full(cap_table("dd_capacity", ["Radiologist", "NPI", "Local Practice"],
                     "Capacity & utilization by radiologist (PBI Practice Summary logic)"), 10)

    bl = [("Practice", None), ("Radiologist", None), ("NPI", None), ("Shift_Name", None), ("Baseline_Type", None),
          ("Shift_Length", NUM_FMT), ("Shift_Count", COUNT_FMT), ("Shift_Baseline", NUM_FMT), ("Matched_Shift_Name", None)]
    p.full(table("dd_baselines", "ds_shift_baselines", [d(x) for x, _ in bl],
                 [col(x, x.replace("_", " "), f) for x, f in bl], "Shift baselines (legacy-VR reference)",
                 disaggregated=True), 10)
    return p


def page_program():
    p = Page("program", "Program (MVP)")
    p.full(text("pg_header", [
        "# Program -- MVP onboarding & optimization (Dynamics)\n",
        "Source: Dynamics CRM radiologist onboarding table (manually refreshed snapshot). Not linked to the global "
        "Region / Practice / Team filters -- Dynamics practice is free text. Efficiency-change figures here are "
        "entered by hand in Dynamics and can differ from the governed Efficiency page.\n"]), 2)
    p.row([
        (multi_filter("pg_f_track", "Program Track", "filter-multi-select", [("ds_program", "Program Track")]), 4),
        (multi_filter("pg_f_cohort", "MVP Cohort", "filter-multi-select", [("ds_program", "MVP Cohort")]), 4),
        (multi_filter("pg_f_active", "Actively tracked", "filter-multi-select", [("ds_program", "Is Actively Tracked")]), 4),
    ], 2)
    p.row([
        (counter("pg_rads", "ds_program", "Radiologists", "Radiologists in Dynamics", COUNT_FMT), 2),
        (counter("pg_cohort", "ds_program", "Cohort Radiologists", "In an MVP cohort", COUNT_FMT), 2),
        (counter("pg_active", "ds_program", "Actively Tracked Radiologists", "Actively tracked", COUNT_FMT), 2),
        (counter("pg_funnel", "ds_program", "Funnel Radiologists", "In optimization funnel", COUNT_FMT), 2),
        (counter("pg_post", "ds_program", "Post Engagement Radiologists", "Post engagement", COUNT_FMT), 2),
        (counter("pg_escalated", "ds_program", "Escalated Radiologists", "Escalated", COUNT_FMT), 2),
    ], 3)
    p.row([
        (counter("pg_closed", "ds_program", "Closed Completed Radiologists", "Closed -- completed", COUNT_FMT), 3),
        (counter("pg_median", "ds_program", "Median Full Mosaic L30D Change Pct",
                 "Median Full Mosaic change, last 30 days (Dynamics)", PCT_FMT), 3),
        (counter("pg_with_l30d", "ds_program", "Radiologists With L30D Change", "Rads with a L30D figure", COUNT_FMT), 3),
        (table("pg_asof", "ds_program", [m("Latest Dynamics Activity")],
               [col(mref("Latest Dynamics Activity"), "Latest Dynamics activity")], "Program data as of"), 3),
    ], 3)
    p.row([
        (bar("pg_funnel_bar", "ds_program", "Funnel Stage", "Radiologists", "Optimization funnel by stage and outcome",
             color_dim="Funnel Outcome"), 8),
        (bar("pg_impact_bar", "ds_program", "Impact Status", "Radiologists", "Post-engagement impact"), 4),
    ], 7)
    p.row([
        (bar("pg_escalation_bar", "ds_program", "Escalation Owner", "Radiologists", "Escalations by owner"), 6),
        (bar("pg_exclusion_bar", "ds_program", "Exclusion Reason", "Radiologists", "Not tracked: exclusion reasons"), 6),
    ], 6)
    dims = ["Radiologist Name", "NPI", "Dynamics Practice", "MVP Cohort", "Program Track", "Optimization Support Status",
            "Funnel Stage", "Funnel Outcome", "Impact Status"]
    p.full(table("pg_roster", "ds_program", [d(x) for x in dims], [col(x, x) for x in dims], "Program roster",
                 order=("`Optimization Support Status`", "DESC")), 10)
    return p


DRAFT_CATS = [  # (measure suffix, column label) in PBI waterfall order
    ("Rad Declined", "Rad declined"), ("Ops Declined", "Ops declined"),
    ("Incomplete Process", "Incomplete process"), ("Practice Not Enabled", "Practice not enabled"),
    ("Opened Under 5 Min", "Opened <5 min"), ("Opened Over 5 Min", "Opened >5 min"),
    ("Never Opened", "Never opened"),
]

DRAFTABLE_INSIGHTS = [
    "### What is holding drafting back\n",
    "- **Radiologist not enabled** (consent declined, ops declined, or *incomplete process* -- the radiologist "
    "drafted under 10% of that model's exams that week) is the largest bucket. *Incomplete process* alone is "
    "the single biggest lever: these radiologists have drafting but are not using it consistently.\n",
    "- **Enabled, draft not used** (radiologist and practice both live, exam opened without a draft) is the "
    "workflow / product bucket. *Opened >5 min* means the draft had time to arrive but was not used; "
    "*opened <5 min* points to draft latency.\n",
    "- **Practice not enabled** is small: it only covers CT Chest / CT Spine exams at practices not yet "
    "live on those models.\n",
    "- Use the tables below to find where each bucket concentrates (region, team, model, radiologist).\n",
]

DRAFTABLE_NOTES = [
    "### Definitions & notes\n",
    "- **Draftable** = Mosaic exams on drafting-eligible procedure codes. Each exam is classified once, first "
    "match wins: Drafted > Rad declined > Ops declined > Incomplete process > Practice not enabled > Never "
    "opened > Opened <5 min > Opened >5 min. % = share of all draftable exams (Drafted included), as in "
    "PowerBI's *Category % of Draftable*.\n",
    "- Same source as the PowerBI Volume report's Draftable page (daily snapshot, refreshed 7am CT). Completed "
    "Mon-Sun weeks only, so the current week is not shown. XR/MSK and the CT models switch on per radiologist "
    "per week; Do-Not-Launch radiologists are excluded.\n",
    "- **Local Region** here is PowerBI's Draftable mapping, which places a few teams (RP Florida West, RAA, "
    "Lakefront Imaging) in a different region than the other pages. **Managing Practice** does not apply to "
    "this page.\n",
]


def draft_fields_cols(dims):
    meas = [("Draftable Exam Count", "Draftable exams", COUNT_FMT), ("Undrafted Exam Count", "Undrafted", COUNT_FMT),
            ("Pct Drafted", "% Drafted", PCT_FMT)] + [(f"Pct {s}", lbl, PCT_FMT) for s, lbl in DRAFT_CATS]
    fields = [d(x) for x in dims] + [m(n) for n, _, _ in meas]
    cols = [col(x, x) for x in dims] + [col(mref(n), t, f) for n, t, f in meas]
    return fields, cols


def page_draftable():
    p = Page("draftable", "Draftable, Undrafted")
    p.full(text("dr_header", [
        "# Draftable, Undrafted -- why exams are not AI-drafted\n",
        "Every Mosaic exam that *could* have been drafted, classified by why it was or was not. Follows the "
        "global **Period**, **Local Region** and **Team Rolled Up** filters; the weekly trend shows full history.\n"]), 2)
    p.row([
        (counter("dr_draftable", "ds_draftable", "Draftable Exam Count", "Draftable exams", COUNT_FMT), 2),
        (counter("dr_pct_drafted", "ds_draftable", "Pct Drafted", "% drafted", PCT_FMT), 2),
        (counter("dr_undrafted", "ds_draftable", "Undrafted Exam Count", "Undrafted exams", COUNT_FMT), 2),
        (counter("dr_pct_rad", "ds_draftable", "Pct Rad Not Enabled", "% lost: radiologist not enabled", PCT_FMT,
                 "Rad declined + ops declined + incomplete process"), 2),
        (counter("dr_pct_practice", "ds_draftable", "Pct Practice Not Enabled", "% lost: practice not enabled", PCT_FMT), 2),
        (counter("dr_pct_unused", "ds_draftable", "Pct Draft Not Used", "% lost: enabled, draft not used", PCT_FMT,
                 "Opened <5 min + opened >5 min + never opened"), 2),
    ], 3)
    # Category shares as one row of measures: grouping a table by Category would also filter the
    # denominator, so per-row "% of draftable" is not expressible there.
    shares = [("Pct Drafted", "Drafted")] + [(f"Pct {s}", lbl) for s, lbl in DRAFT_CATS]
    p.full(table("dr_shares", "ds_draftable", [m(n) for n, _ in shares],
                 [col(mref(n), t, PCT_FMT) for n, t in shares],
                 "Share of draftable exams by category (= PowerBI Category % of Draftable)"), 3)
    p.row([
        (table("dr_by_category", "ds_draftable",
               [d("Category Sort Order"), d("Category Group"), d("Category"),
                m("Draftable Exam Count"), m("Draftable TBWU"), m("Radiologist Count")],
               [col("Category Group", "Group"), col("Category", "Category"),
                col(mref("Draftable Exam Count"), "Exams", COUNT_FMT), col(mref("Draftable TBWU"), "TBWU", COUNT_FMT),
                col(mref("Radiologist Count"), "Radiologists", COUNT_FMT)],
               "Draftable exams by category (PowerBI waterfall order)", order=("`Category Sort Order`", "ASC")), 7),
        (bar("dr_group_bar", "ds_draftable", "Category Group", "Draftable Exam Count",
             "Where draftable exams go", x_title="Category group"), 5),
    ], 7)
    p.full(line("dr_trend", "ds_draftable_trend", "Week Start",
                [("Pct Drafted", "Drafted"), ("Pct Rad Not Enabled", "Rad not enabled"),
                 ("Pct Practice Not Enabled", "Practice not enabled"), ("Pct Draft Not Used", "Enabled, draft not used")],
                "Weekly share of draftable exams (completed weeks, full history)", PCT_FMT), 6)
    p.row([(text("dr_insights", DRAFTABLE_INSIGHTS), 7), (text("dr_notes", DRAFTABLE_NOTES), 5)], 8)
    for key, dims, title, h in [
        ("region", ["Local Region"], "By Local Region", 6),
        ("team", ["Local Region", "Team Rolled Up"], "By Team Rolled Up (Provider Practice)", 10),
        ("model", ["Drafting Model"], "By drafting model", 6),
        ("exam_cat", ["Drafting Model", "Exam Category"], "By exam category", 10),
    ]:
        fields, cols = draft_fields_cols(dims)
        p.full(table(f"dr_by_{key}", "ds_draftable", fields, cols, title,
                     order=("MEASURE(`Undrafted Exam Count`)", "DESC")), h)
    fields, cols = draft_fields_cols(["Radiologist Name", "NPI", "Team Rolled Up"])
    p.full(table("dr_by_rad", "ds_draftable", fields, cols, "Radiologists with the most undrafted draftable exams",
                 order=("MEASURE(`Undrafted Exam Count`)", "DESC")), 10)
    return p


# ---------------------------------------------------------------- assemble / deploy

def min_exams_param(default):
    return {"displayName": "Min exams", "keyword": MIN_EXAMS_PARAM, "dataType": "INTEGER",
            "defaultSelection": {"values": {"dataType": "INTEGER", "values": [{"value": default}]}}}


def sql_dataset(name, display, path, level, min_exams_default=None):
    """A PBI-visual-logic SQL file with its window bound to the :period range parameter
    (and, when min_exams_default is given, PBI's Min Exams slicer bound to :min_exams)."""
    sql = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                    if not l.lstrip().startswith("--"))
    sql = (sql.replace("{START}", f":{PERIOD_PARAM}.min").replace("{END}", f":{PERIOD_PARAM}.max")
           .replace("{FINAL}", level).replace("{MIN_EXAMS}", f":{MIN_EXAMS_PARAM}"))
    params = [{"displayName": "Period", "keyword": PERIOD_PARAM, "dataType": "DATE",
               "complexType": "RANGE", "defaultSelection": LAST_COMPLETE_MONTH}]
    if min_exams_default is not None:
        params.append(min_exams_param(min_exams_default))
    return {"name": name, "displayName": display, "queryLines": [l + "\n" for l in sql.splitlines()],
            "parameters": params}


def ts_dataset(name, display, path):
    """Full-history SQL dataset (no period binding) with PBI's Min Exams slicer as an integer parameter."""
    sql = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                    if not l.lstrip().startswith("--")).replace("{MIN_EXAMS}", f":{MIN_EXAMS_PARAM}")
    return {"name": name, "displayName": display, "queryLines": [l + "\n" for l in sql.splitlines()],
            "parameters": [min_exams_param("0")]}


def plain_dataset(name, display, path):
    """Parameter-free SQL dataset; widget filters do all the slicing."""
    sql = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("--"))
    return {"name": name, "displayName": display, "queryLines": [l + "\n" for l in sql.splitlines()]}


def build():
    pages = [page_summary(), page_adoption(), page_efficiency(), page_capacity(), page_drilldown(), page_program(),
             page_draftable()]
    datasets = [{"name": n, "displayName": disp, "asset_name": asset, "catalog": CATALOG, "schema": SCHEMA}
                for n, (disp, asset) in DATASETS.items()]
    datasets += [sql_dataset(n, disp, path, level) for n, (disp, path, level) in SQL_DATASETS.items()]
    datasets += [sql_dataset(n, disp, VS_AVG_SQL, level, VS_AVG_MIN_DEFAULT)
                 for n, (disp, level) in VS_AVG_DATASETS.items()]
    datasets.append(ts_dataset(TIME_SERIES, "Efficiency change time series (PBI visual logic)", TIME_SERIES_SQL))
    datasets.append(ts_dataset(VS_AVG_TS, "Efficiency vs Average time series (PBI visual logic)", VS_AVG_TS_SQL))
    datasets.append(plain_dataset(TS_WU, "WU per minute time series (PBI visual logic)", TS_WU_SQL))
    datasets.append(plain_dataset(CAP, "Capacity per shift (PBI Practice Summary logic, period)", CAP_SQL))
    cap_trend = plain_dataset(CAP_TREND, "Capacity per shift (PBI Practice Summary logic, trend)", CAP_SQL)
    # Dec 2023 is a handful of pre-launch stub shifts (capacity ~half of baseline) that would wreck the trend axis.
    cap_trend["queryLines"] = (["SELECT * FROM (\n"] + cap_trend["queryLines"]
                               + [") WHERE `Shift Month` >= DATE'2024-01-01'\n"])
    datasets.append(cap_trend)
    return {"datasets": datasets, "pages": [p.to_json() for p in pages] + [global_filters_page()], "uiSettings": THEME}


def cli(args, profile):
    out = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", shell=(sys.platform == "win32"))
    if out.returncode:
        sys.exit(f"databricks {' '.join(args[:2])} failed:\n{out.stderr}")
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--create", action="store_true", help="create a new draft dashboard")
    g.add_argument("--update", metavar="DASHBOARD_ID", help="overwrite an existing draft's definition")
    ap.add_argument("--profile", help="Databricks CLI profile (required with --create/--update)")
    a = ap.parse_args()

    sd = build()
    OUT_JSON.write_text(json.dumps(sd, indent=1), encoding="utf-8")
    print(f"wrote {OUT_JSON} ({len(sd['pages'])} pages, {sum(len(p['layout']) for p in sd['pages'])} widgets)")
    if not (a.create or a.update):
        return
    if not a.profile:
        sys.exit("--profile is required to create/update")
    body = HERE / "_request_body.json"
    payload = {"serialized_dashboard": json.dumps(sd)}
    if a.create:
        payload.update({"display_name": DISPLAY_NAME, "parent_path": PARENT_PATH, "warehouse_id": WAREHOUSE_ID})
        body.write_text(json.dumps(payload), encoding="utf-8")
        res = cli(["lakeview", "create", "--json", f"@{body}"], a.profile)
        ID_FILE.write_text(res["dashboard_id"], encoding="utf-8")
        print(f"created draft {res['dashboard_id']} at {res.get('path')}")
    else:
        body.write_text(json.dumps(payload), encoding="utf-8")
        res = cli(["lakeview", "update", a.update, "--json", f"@{body}"], a.profile)
        print(f"updated draft {res['dashboard_id']}")
    body.unlink()


if __name__ == "__main__":
    main()
