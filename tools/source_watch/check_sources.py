"""Daily watcher for the local OneDrive-synced Radiology Partners source folders.

Not part of the running app - this is an ops/maintenance script invoked by a
scheduled Claude Code task. It never edits app code or data itself; it only
detects filesystem changes under the 4 Carlton Prickett folders and reports
them so a human (or the scheduled task's own follow-up reasoning) can decide
whether backend/app/data/*.py or the Focus Rads methodology needs updating.

Two tiers:
  - CORE_FILES: the ~16 paths (covering ~14 distinct documents, some tracked
    under two synced copies) already read and incorporated into the app this
    session. Each has a `feeds` note describing what in the app depends on it.
    A change here is flagged for deep review.
  - everything else under WATCH_ROOTS: presumed historical/frozen. A change
    here is just flagged by path - not analyzed further, since we have no
    baseline extraction to diff it against.

State is persisted in manifest.json (path -> {mtime, size}) so each run only
reports *new* changes since the previous run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = r"C:\Users\bhargav.narasimhan\Radiology Partners Inc"

WATCH_ROOTS = [
    os.path.join(ROOT, "Carlton Prickett - Data"),
    os.path.join(ROOT, "Carlton Prickett - Decks"),
    os.path.join(ROOT, "Carlton Prickett - Deployment"),
    os.path.join(ROOT, "Carlton Prickett - US"),
]

# path -> what in the app depends on this file, if anything
CORE_FILES: dict[str, str] = {
    os.path.join(ROOT, "Carlton Prickett - Decks", "Mosaic Rad Experience_MASTER.pptx"):
        "General context/ontology only - not wired into a specific data file yet.",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "260724 Mosaic Value Project.pptx"):
        "Focus Rads MVP methodology (baseline window, tier thresholds, volume floor) "
        "is hardcoded in backend/app/services/cache_service.py get_focus_radiologists() "
        "and mosaic_service.py get_mvp_efficiency_by_radiologist/get_mvp_capacity_by_radiologist. "
        "A change here may require code changes, not just data literals.",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "260724 MVP Master Data.xlsx"):
        "Corroborating source for the same Focus Rads MVP methodology as the MVP deck above.",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "260827 MVP Rad Engagement Model.xlsx"):
        "Informational only - staffing calculator, not wired into the app.",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "260901 Rads on Drafting Analysis.xlsx"):
        "Informational only - feeds the deferred Deployment blocker-taxonomy follow-up (not built).",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "Mosaic - Rads w No Drafting 8-31-2026.xlsx"):
        "Informational only - same deferred blocker-taxonomy follow-up (not built).",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "2026 Mosaic Executive Dashboard.pptx"):
        "Informational context only - not wired into a specific data file.",
    os.path.join(ROOT, "Carlton Prickett - Deployment", "MASTER.LegacyVRSunsetTracker.xlsx"):
        "Informational only - feeds the deferred Legacy VR Sunset follow-up (not built).",
    os.path.join(ROOT, "Carlton Prickett - US", "Capture Deployment Tracker.xlsx"):
        "Feeds backend/app/data/capture_enablement.py (soft launch dates).",
    os.path.join(ROOT, "Carlton Prickett - Data", "Insights Analytics", "Mosaic AI Knowledge Resources", "Capture Deployment Tracker.xlsx"):
        "Duplicate synced copy of the Capture Deployment Tracker above - same feed.",
    os.path.join(ROOT, "Carlton Prickett - US", "US Capture Phase 3 Deployment Status.xlsx"):
        "Feeds backend/app/data/capture_enablement.py (full enablement dates + opted_out flags).",
    os.path.join(ROOT, "Carlton Prickett - Data", "Insights Analytics", "Mosaic AI Knowledge Resources", "US Capture Phase 3 Deployment Status.xlsx"):
        "Duplicate synced copy of the Phase 3 Deployment Status tracker above - same feed.",
    os.path.join(ROOT, "Carlton Prickett - US", "Utilization Drive - US Capture.xlsx"):
        "Informational only - qualitative Capture context, not wired into a data file.",
    os.path.join(ROOT, "Carlton Prickett - US", "Official US Capture Efficiency Tracker.xlsx"):
        "Informational only - qualitative Capture context, not wired into a data file.",
    os.path.join(ROOT, "Carlton Prickett - Data", "Mosaic General Survey.xlsx"):
        "Feeds backend/app/data/rad_survey.py (NPS, Likert distributions, theme tagging, by-practice table).",
    os.path.join(ROOT, "Carlton Prickett - Data", "Mosaic 6 For 26 Data.xlsx"):
        "Informational only - raw KPI feed described but not ingested into a data file yet.",
}

MANIFEST_PATH = Path(__file__).parent / "manifest.json"
IGNORE_NAMES = {"desktop.ini"}


def _stat(path: str) -> tuple[float, int] | None:
    try:
        st = os.stat(path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def _scan() -> dict[str, tuple[float, int]]:
    current: dict[str, tuple[float, int]] = {}
    for root in WATCH_ROOTS:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name in IGNORE_NAMES or name.startswith("~$"):
                    continue
                full = os.path.join(dirpath, name)
                st = _stat(full)
                if st is not None:
                    current[full] = st
    return current


def _load_manifest() -> dict[str, dict]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("files", {})
    return {}


def _save_manifest(current: dict[str, tuple[float, int]]) -> None:
    payload = {
        "files": {
            path: {"mtime": mtime, "size": size}
            for path, (mtime, size) in sorted(current.items())
        }
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    previous = _load_manifest()
    current = _scan()

    core_changes: list[dict] = []
    other_changes: list[dict] = []

    for path, (mtime, size) in current.items():
        prev = previous.get(path)
        tier = "core" if path in CORE_FILES else "watch"
        if prev is None:
            change_type = "new"
        elif prev["mtime"] != mtime or prev["size"] != size:
            change_type = "modified"
        else:
            continue
        entry = {"path": path, "change_type": change_type}
        if tier == "core":
            entry["feeds"] = CORE_FILES[path]
            core_changes.append(entry)
        else:
            other_changes.append(entry)

    for path in previous:
        if path not in current:
            entry = {"path": path, "change_type": "removed"}
            if path in CORE_FILES:
                entry["feeds"] = CORE_FILES[path]
                core_changes.append(entry)
            else:
                other_changes.append(entry)

    _save_manifest(current)

    report = {
        "checked_files": len(current),
        "core_changes": core_changes,
        "other_changes": other_changes,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
