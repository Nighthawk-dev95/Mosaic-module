# Mosaic Executive — sharing readiness (pilot / Genie Governance kickoff)

Status as of 2026-10-26. Everything is in **edw_test.enterprise_analytics** (reads live edw_prod data). Nothing is in PROD.

| Asset | ID / object | State |
|---|---|---|
| Lakeview dashboard "Mosaic Executive Dashboard" | `01f1d0089f5410359e87575975cb5dea` | Published, embedded credentials, 8 pages, PBI-parity |
| Genie space "Mosaic Executive (Sandbox)" | `01f1d02c5dad1f359b76e45dc3920549` | Sandbox tier, linked to the dashboard |
| Metric views in Genie (6) | volume, efficiency, efficiency_vs_rp_avg, capacity_pbi, program, draftable | Every dimension + measure has a business comment, display name and synonyms (050) |
| UC functions in Genie (8) | `mosaic_eff_*` | Per practice / rad / site efficiency, PBI-parity |
| Efficiency speed fix | `mosaic_efficiency_exam_level_mv` (048) + repoint (049) | Daily 7:30 AM CT refresh; queries went from 7–10 min to ~5–10 s, values identical |

## Who needs what

**Dashboard viewers** only need `CAN VIEW` on the dashboard. It is published with embedded credentials, so they do
not need data grants to see the pages.

**Genie users** (including the dashboard's "Ask Genie" button) run queries **as themselves**. They need the
following (to be run by a catalog/schema owner — not run automatically):

```sql
-- replace <group> with the pilot group, e.g. a SEC-AZ-DBX-... AD group
GRANT USE CATALOG ON CATALOG edw_test TO `<group>`;
GRANT USE SCHEMA  ON SCHEMA  edw_test.enterprise_analytics TO `<group>`;

GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_volume_metric_view               TO `<group>`;
GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_efficiency_metric_view           TO `<group>`;
GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_efficiency_vs_rp_avg_metric_view TO `<group>`;
GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_capacity_pbi_metric_view         TO `<group>`;
GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_program_metric_view              TO `<group>`;
GRANT SELECT ON TABLE edw_test.enterprise_analytics.mosaic_draftable_metric_view            TO `<group>`;

GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_by_provider_practice  TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_by_radiologist        TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_by_parent_exam        TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_by_managing_practice  TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_by_managing_site      TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_vs_avg_benchmarks     TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_vs_avg_by_practice    TO `<group>`;
GRANT EXECUTE ON FUNCTION edw_test.enterprise_analytics.mosaic_eff_vs_avg_by_radiologist TO `<group>`;
```

Views, metric views and SQL functions resolve their underlying tables with the **owner's** rights, so the
group should not need SELECT on the MVs or source views behind them. **Verify this with one pilot user before the
wide rollout.** If a function errors with a permission message, also grant SELECT on the
`mosaic_eff_*_mv` materialized views (037–043).

Plus, in the workspace UI:
- SQL warehouse `fe0ad987563c672a`: **CAN USE** for `<group>`.
- Genie space: **CAN RUN** for `<group>`. Reviewers who curate it get **CAN EDIT**.
- Dashboard: **CAN VIEW** for `<group>`.

`SEC-AZ-DBX-T-BIPA-RW` already holds SELECT on catalog `edw_test`, so its members can use Genie today once they have
CAN RUN on the space and CAN USE on the warehouse.

## Governance (Sandbox → Candidate)
- **Tier:** Sandbox, since it lives in the creator's `/Genie-Sandbox` folder.
- **Candidate criteria met:**
  - Curated, governed data only: 6 metric views + 8 functions, and no raw tables.
  - Benchmarks are in the space.
  - Business glossary and routing instructions are in the space.
  - Every field is documented.
- **Promotion to Candidate** requires the committee's sign-off, plus a pilot group outside the creator.
- **Change control:** the space is edited only through `tools/genie_exec_space/build_genie_space.py`, which is source
  controlled. Field metadata lives in `tools/edw_fixes/metric_view_metadata/*.json` and is applied with
  `_enrich_metric_view_metadata.py`, which asserts that metric logic is unchanged.
