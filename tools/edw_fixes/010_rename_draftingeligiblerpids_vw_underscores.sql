-- STATUS (2026-10-06): READY TO DEPLOY - pure rename for readability, no logic change.
-- Request: keep "_" as the word delimiter in object names.
--
-- Confirmed this is a VIEW (system.information_schema.tables.table_type = 'VIEW') in
-- edw_prod.enterprise_analytics_ref - NOT the same object as edw_prod.bipa_analytics.
-- draftingeligiblerpids_vw that tools/edw_fixes/004_*.sql and 005_*.sql reference (different
-- schema entirely; grepped this repo, zero references to the enterprise_analytics_ref copy,
-- so this rename has no knock-on effect on anything checked in here).

ALTER VIEW edw_prod.enterprise_analytics_ref.draftingeligiblerpids_vw
RENAME TO drafting_eligible_rpids_vw;
