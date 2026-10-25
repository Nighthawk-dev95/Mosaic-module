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
  * KPI datasets (ds_volume, ds_efficiency, ds_efficiency_rp_avg, ds_capacity) take the global
    Period filter. Trend datasets (*_trend) point at the same metric views but are NOT bound to
    Period, so trend lines always show full history while counters show the selected period.
  * ds_capacity / ds_capacity_trend take the "Capacity shifts" filter, defaulting to shifts with a
    matched baseline (PBI's "Shifts with Baselines" default). Without it, baseline RPWU/hour is
    diluted by un-baselined hours. ds_capacity_coverage is deliberately NOT bound to that filter so
    the "% shifts with a baseline" trust badge stays meaningful.
  * ds_program (Dynamics) has no MDM practice/region keys, so it is not bound to global filters.
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
DETAIL_DASHBOARD_ID = "01f1ce304a0c128f913f243dc8ad0ad1"  # 15-page "Mosaic Daily View"

CATALOG, SCHEMA = "edw_test", "enterprise_analytics"
VOLUME_MV = f"{CATALOG}.{SCHEMA}.mosaic_volume_metric_view"
EFF_MV = f"{CATALOG}.{SCHEMA}.mosaic_efficiency_metric_view"
RP_MV = f"{CATALOG}.{SCHEMA}.mosaic_efficiency_vs_rp_avg_metric_view"
CAP_MV = f"{CATALOG}.{SCHEMA}.mosaic_capacity_metric_view"
PROGRAM_MV = f"{CATALOG}.{SCHEMA}.mosaic_program_metric_view"
DRAFTABLE_MV = f"{CATALOG}.{SCHEMA}.mosaic_draftable_metric_view"
BASELINE_TBL = f"{CATALOG}.{SCHEMA}.tbl_mosaic_baseline_master"

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
}

DATASETS = {
    "ds_volume": ("Volume (period)", VOLUME_MV),
    "ds_volume_trend": ("Volume (trend)", VOLUME_MV),
    "ds_efficiency": ("Efficiency (period)", EFF_MV),
    "ds_efficiency_trend": ("Efficiency (trend)", EFF_MV),
    "ds_efficiency_rp_avg": ("Efficiency vs RP Average (period)", RP_MV),
    "ds_capacity": ("Capacity (period)", CAP_MV),
    "ds_capacity_trend": ("Capacity (trend)", CAP_MV),
    "ds_capacity_coverage": ("Capacity baseline coverage", CAP_MV),
    "ds_program": ("Program (Dynamics MVP)", PROGRAM_MV),
    "ds_shift_baselines": ("Shift Baselines", BASELINE_TBL),
    "ds_draftable": ("Draftable / Undrafted (period)", DRAFTABLE_MV),
    "ds_draftable_trend": ("Draftable / Undrafted (trend)", DRAFTABLE_MV),
}

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


def text(name, lines):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}}}


def multi_filter(name, title, widget_type, bindings, default=None):
    """One filter widget bound to the same business field across several datasets.
    bindings: list of (dataset_name, field_name)."""
    queries, fields = [], []
    for ds, field in bindings:
        qn = f"f_{name}_{ds}"
        queries.append({"name": qn, "query": {"datasetName": ds, "fields": [d(field)], "disaggregated": False}})
        fields.append({"fieldName": field, "displayName": title, "queryName": qn})
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
                 "ds_efficiency_rp_avg", "ds_capacity", "ds_capacity_trend", "ds_capacity_coverage"]
MANAGING_PRACTICE_FIELD = {"ds_volume": "Managing Practice", "ds_volume_trend": "Managing Practice"}
# Draftable carries Local Region (PBI Localdraf) and Team Rolled Up but no Managing Practice key.
DRAFTABLE = ["ds_draftable", "ds_draftable_trend"]

# "Last complete month": relative-date default. If Lakeview ignores this, the picker simply
# opens unbounded -- see README for the one-time UI check.
LAST_COMPLETE_MONTH = {"range": {"dataType": "DATE", "min": {"value": "now-1M/M"}, "max": {"value": "now-1M/M"}}}
BASELINED_SHIFTS = {"values": {"dataType": "STRING",
                               "values": [{"value": "Exact"}, {"value": "Proxy"}, {"value": "Manual Review"}]}}


def global_filters_page():
    widgets = [
        multi_filter("g_period", "Period (defaults to last complete month)", "filter-date-range-picker", [
            ("ds_volume", "Final Date"), ("ds_efficiency", "Exam Month"), ("ds_efficiency_rp_avg", "Exam Month"),
            ("ds_capacity", "Shift Date"), ("ds_capacity_coverage", "Shift Date"),
            ("ds_draftable", "Calendar Date")], default=LAST_COMPLETE_MONTH),
        multi_filter("g_local", "Local Region", "filter-multi-select",
                     [(ds, "Local Region") for ds in KPI_AND_TREND + DRAFTABLE]),
        multi_filter("g_practice", "Managing Practice", "filter-multi-select",
                     [(ds, MANAGING_PRACTICE_FIELD.get(ds, "Practice")) for ds in KPI_AND_TREND]),
        multi_filter("g_team_rollup", "Team Rolled Up", "filter-multi-select",
                     [(ds, "Team Rolled Up") for ds in KPI_AND_TREND + DRAFTABLE]),
        multi_filter("g_baseline_type", "Capacity shifts (baseline match)", "filter-multi-select",
                     [("ds_capacity", "Baseline Type"), ("ds_capacity_trend", "Baseline Type")],
                     default=BASELINED_SHIFTS),
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
    "- **Capacity** compares RPWU produced per on-shift hour with the radiologist's shift baseline. By default "
    "only shifts with a matched baseline are included, as in PowerBI; a large share of shifts have no "
    "matched baseline -- see the coverage badge.\n",
    "- **Utilization** = reading time / shift time, capped at 100%. Check *exams with valid read time* "
    "before trusting a slice: dictation timestamps are missing for some practices.\n",
    "- Outlier exams are excluded from efficiency (PowerBI default). The current month is partial in trend lines.\n",
]


def page_summary():
    p = Page("exec_summary", "Executive Summary")
    p.full(text("es_header", [
        "# Mosaic -- Executive Summary\n",
        "Mosaic (Reporting, AI Drafting, Capture) compared with legacy voice recognition. KPIs follow the "
        "**Period** filter (defaults to the last complete month); trend lines always show full history. "
        f"Detailed views: [Mosaic Daily View](/dashboardsv3/{DETAIL_DASHBOARD_ID}).\n"]), 2)
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
        (counter("es_cap_vs_base", "ds_capacity", "On Shift Capacity Vs Baseline RPWU Per Hour",
                 "Added capacity (RPWU / hour vs baseline)", NUM_FMT), 3),
        (counter("es_util", "ds_capacity", "On Shift Utilization Pct", "On-shift utilization", PCT_FMT), 3),
        (counter("es_cov_baseline", "ds_capacity_coverage", "Pct Shifts With Baseline",
                 "Trust: % shifts with a matched baseline", PCT_FMT), 3),
        (counter("es_cov_readtime", "ds_capacity", "Pct Exams With Valid Read Time",
                 "Trust: % exams with valid read time", PCT_FMT), 3),
    ], 3)
    p.row([
        (line("es_trend_rpce", "ds_volume_trend", "Final Month",
              [("Pct RPCE Reporting", "Reporting"), ("Pct RPCE Drafting", "Drafting"), ("Pct RPCE Capture", "Capture")],
              "% of RPCE exams by solution (monthly)", PCT_FMT), 4),
        (line("es_trend_eff", "ds_efficiency_trend", "Exam Month",
              [("Full Mosaic Pct Change Vs Baseline", "Full Mosaic"), ("Drafting Pct Change Vs Baseline", "Drafting")],
              "Efficiency vs legacy VR (monthly)", PCT_FMT), 4),
        (line("es_trend_util", "ds_capacity_trend", "Shift Month",
              [("On Shift Utilization Pct", "Utilization")], "On-shift utilization (monthly)", PCT_FMT), 4),
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
    p.full(line("ef_trend", "ds_efficiency_trend", "Exam Month",
                [(f"{mode} Pct Change Vs Baseline", title) for mode, title in MODES if mode != "Drafting Capture"],
                "Efficiency change vs legacy VR by mode (monthly)", PCT_FMT), 6)
    fields = [d("Local Region"), d("Practice"), m("Full Mosaic Mosaic Exams"), m("Full Mosaic Mosaic Efficiency"),
              m("Full Mosaic Baseline Efficiency"), m("Full Mosaic Pct Change Vs Baseline"),
              m("Full Mosaic Implied Read Time Savings Pct"), m("Reporting Pct Change Vs Baseline"),
              m("Drafting Pct Change Vs Baseline"), m("Capture Pct Change Vs Baseline")]
    cols = [col("Local Region", "Local Region"), col("Practice", "Managing Practice"),
            col(mref("Full Mosaic Mosaic Exams"), "Mosaic exams", COUNT_FMT),
            col(mref("Full Mosaic Mosaic Efficiency"), "Mosaic efficiency", NUM_FMT),
            col(mref("Full Mosaic Baseline Efficiency"), "Baseline efficiency", NUM_FMT),
            col(mref("Full Mosaic Pct Change Vs Baseline"), "Full Mosaic % change", PCT_FMT, sign_rules()),
            col(mref("Full Mosaic Implied Read Time Savings Pct"), "Implied read-time change", PCT_FMT),
            col(mref("Reporting Pct Change Vs Baseline"), "Reporting % change", PCT_FMT, sign_rules()),
            col(mref("Drafting Pct Change Vs Baseline"), "Drafting % change", PCT_FMT, sign_rules()),
            col(mref("Capture Pct Change Vs Baseline"), "Capture % change", PCT_FMT, sign_rules())]
    p.full(table("ef_by_practice", "ds_efficiency", fields, cols, "By Managing Practice",
                 order=("MEASURE(`Full Mosaic Mosaic Exams`)", "DESC")), 10)
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


CAP_SUMMARY = [
    ("Total Hours", "Hours", COUNT_FMT, None),
    ("Shift Baseline RPWU Per Hour", "Baseline RPWU/hr", NUM_FMT, None),
    ("On Shift Capacity RPWU Per Hour", "Mosaic RPWU/hr", NUM_FMT, None),
    ("On Shift Capacity Vs Baseline RPWU Per Hour", "Added RPWU/hr", NUM_FMT, "sign"),
    ("On Shift Utilization Pct", "Utilization", PCT_FMT, None),
    ("Pct Mosaic Of Shift", "% Mosaic", PCT_FMT, None),
    ("Pct Mosaic Drafting Of Shift", "% Drafted", PCT_FMT, None),
    ("Pct Exams With Valid Read Time", "Trust: valid read time", PCT_FMT, None),
]


def cap_fields_cols(dims):
    fields = [d(x) for x in dims] + [m(n) for n, _, _, _ in CAP_SUMMARY]
    cols = [col(x, x) for x in dims] + [col(mref(n), t, f, sign_rules() if r else None) for n, t, f, r in CAP_SUMMARY]
    return fields, cols


def page_capacity():
    p = Page("capacity", "Capacity & Utilization")
    p.full(text("cp_header", [
        "# Capacity & Utilization\n",
        "RPWU produced per on-shift hour vs each radiologist's shift baseline. Default = shifts with a matched "
        "baseline (as in PowerBI) -- change it in **Capacity shifts** in the global filters. "
        "The trust badges show how much of the workload the numbers rest on.\n"]), 2)
    p.row([
        (counter("cp_base", "ds_capacity", "Shift Baseline RPWU Per Hour", "Baseline RPWU / hour (legacy)", NUM_FMT), 3),
        (counter("cp_cap", "ds_capacity", "On Shift Capacity RPWU Per Hour", "Mosaic-era RPWU / hour", NUM_FMT), 3),
        (counter("cp_added", "ds_capacity", "On Shift Capacity Vs Baseline RPWU Per Hour", "Added RPWU / hour vs baseline", NUM_FMT), 3),
        (counter("cp_util", "ds_capacity", "On Shift Utilization Pct", "On-shift utilization", PCT_FMT), 3),
    ], 3)
    p.row([
        (counter("cp_cov_baseline", "ds_capacity_coverage", "Pct Shifts With Baseline", "Trust: % shifts with a matched baseline", PCT_FMT), 3),
        (counter("cp_cov_readtime", "ds_capacity", "Pct Exams With Valid Read Time", "Trust: % exams with valid read time", PCT_FMT), 3),
        (counter("cp_hours", "ds_capacity", "Total Hours", "On-shift hours", COUNT_FMT), 3),
        (counter("cp_cases", "ds_capacity", "On Shift Cases", "On-shift cases", COUNT_FMT), 3),
    ], 3)
    p.row([
        (line("cp_trend_util", "ds_capacity_trend", "Shift Month", [("On Shift Utilization Pct", "Utilization")],
              "Utilization by Local Region (monthly)", PCT_FMT, color_dim="Local Region"), 6),
        (line("cp_trend_added", "ds_capacity_trend", "Shift Month",
              [("Shift Baseline RPWU Per Hour", "Baseline"), ("On Shift Capacity RPWU Per Hour", "Mosaic era")],
              "RPWU per hour: baseline vs Mosaic era (monthly)", NUM_FMT), 6),
    ], 6)
    fields, cols = cap_fields_cols(["Local Region", "Practice"])
    p.full(table("cp_by_practice", "ds_capacity", fields, cols, "By Managing Practice",
                 order=("MEASURE(`Total Hours`)", "DESC")), 10)
    return p


def page_drilldown():
    p = Page("drilldown", "Radiologist & Practice Drill-down")
    p.full(text("dd_header", [
        "# Radiologist & Practice drill-down\n",
        "Pick a radiologist (or use the global Region / Practice / Team filters) -- every table below follows.\n"]), 2)
    p.row([
        (multi_filter("dd_f_rad", "Radiologist", "filter-multi-select", [
            ("ds_volume", "Radiologist Name"), ("ds_efficiency", "Radiologist Name"),
            ("ds_efficiency_rp_avg", "Radiologist Name"), ("ds_capacity", "Radiologist Name"),
            ("ds_shift_baselines", "Radiologist")]), 6),
        (multi_filter("dd_f_team", "Team (radiologist's pool)", "filter-multi-select", [
            ("ds_volume", "Team"), ("ds_efficiency", "Team"), ("ds_efficiency_rp_avg", "Team"), ("ds_capacity", "Team")]), 6),
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

    fields, cols = cap_fields_cols(["Radiologist Name", "NPI", "Practice"])
    p.full(table("dd_capacity", "ds_capacity", fields, cols, "Capacity & utilization by radiologist",
                 order=("MEASURE(`Total Hours`)", "DESC")), 10)

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

def build():
    pages = [page_summary(), page_adoption(), page_efficiency(), page_capacity(), page_drilldown(), page_program(),
             page_draftable()]
    datasets = [{"name": n, "displayName": disp, "asset_name": asset, "catalog": CATALOG, "schema": SCHEMA}
                for n, (disp, asset) in DATASETS.items()]
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
