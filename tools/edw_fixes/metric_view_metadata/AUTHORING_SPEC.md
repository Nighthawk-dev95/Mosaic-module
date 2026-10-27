# Metric-view metadata authoring spec (050)

Goal: every dimension and measure in the 8 exec metric views gets a business-grade `comment`,
`display_name` and `synonyms`, so Genie and a broad test audience understand each field without asking us.
LOGIC IS NOT CHANGED - only these three keys (plus the view-level comment) are added.

## Output: `tools/edw_fixes/metric_view_metadata/<view>.json`
```json
{
  "view_comment": "optional - replaces the view-level comment; omit to keep live",
  "dimensions": {"<exact field name>": {"comment": "...", "display_name": "...", "synonyms": ["..."]}},
  "measures":   {"<exact field name>": {"comment": "...", "display_name": "...", "synonyms": ["..."]}}
}
```
Field names must match the live YAML exactly (case, spaces). EVERY dimension and measure must have an entry.

## Inputs (read these, do not guess)
- Live definition (authoritative names/exprs/existing comments): `tools/edw_fixes/metric_view_metadata/live/<view>.sql`
  (YAML between the `$$` markers).
- PBI mapping per measure: `tools/mosaic_validation/parity/MEASURE_COVERAGE.md` (grep the view / measure name).
- PBI DAX source: `tools/pbi_semantic_extract/{mosaic_volume,mosaic_efficiency,mosaic_impact}_tmdl/`.
- Business glossary + routing rules: `INSTRUCTIONS` and `COLUMN_CONFIGS` in `tools/genie_exec_space/build_genie_space.py`.

## Rules
- **comment** (1-3 sentences, <= 350 chars, plain business language a VP understands):
  what it measures; unit (percentages are FRACTIONS 0-1, e.g. 0.12 = 12%); key gates/filters (e.g. Outliers
  excluded, min exams, +0.02 RPCE adjustment, only shifts with a baseline); which date dimension to slice by;
  the PowerBI equivalent as "= PowerBI [Measure Name] (<report>)" when MEASURE_COVERAGE.md maps one.
  Helper/building-block measures (numerators, denominators, sums used inside ratios) start with
  "Building block:" and say which headline measure they feed - so Genie prefers the headline one.
  KEEP every accurate caveat already in the live comment (rewrite for clarity, never drop a caveat).
  If a field's live comment is already excellent, you may reuse it verbatim.
  Dimensions: say what values look like (give 2-3 example values when known from the live comment/glossary),
  and the Team vs Practice rule: Team Rolled Up = Provider Practice = the radiologist's home practice
  (PowerBI 'Team Rolled up'); Managing Practice / Practice = the practice owning the exam SITE (PowerBI 'Practice').
- **display_name**: business label, <= 60 chars, unique within the view, Title Case, no underscores
  (e.g. "Full Mosaic Efficiency Change vs Baseline"). If the name is already a perfect label, reuse it.
- **synonyms**: 2-6 phrasings an exec would type ("adoption rate", "read time savings", "% drafted").
  Must NOT equal any other field's name or display_name in the same view, and must not be shared by two fields
  in the same view. Prefer specific over generic (no bare "count", "percent", "rate").
- No SQL needs to be run. Do NOT run any DDL. Do not touch any file other than your JSON(s).

## Validate
`backend/.venv/Scripts/python.exe tools/edw_fixes/_enrich_metric_view_metadata.py build --views <view> [<view>...]`
must report `0 problems` for each of your views (it writes local SQL only - nothing is deployed).
