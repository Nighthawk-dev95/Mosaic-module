Subject: RE: Mosaic Version Flag - radpair_instance pass-through

Hi Weber, James,

Thanks for picking this up. Here's exactly where the field sits and how I'm currently extracting it, so you have a concrete reference for the pipeline change.

**Source**: `p_use1_rp_aws_dbx_workspace01.support.prod_app_logs_silver_mosaicinfohub.message`, filtered to `event = 'report.signed'` rows (same rows your pipeline already reads to populate `report_signed_events`).

**Where it sits in the payload**: `radpair_instance` is a sibling key to the ones you're already extracting (e.g. NPI, modality) in the same flat JSON object - no nesting, no transformation needed, just one more key to pass through alongside the existing extraction.

**What I'm currently running** (regex, since I don't have write access to the pipeline itself):
```sql
regexp_extract(message, 'radpair_instance":"([^"]*)', 1) as instance
```
If your pipeline already does proper JSON parsing (e.g. `get_json_object` / `from_json`) rather than regex, pulling the same key that way will obviously be cleaner and more robust than what I'm doing - the regex above is just a reference for where the field lives, not a suggestion to copy it verbatim.

**Known values** (confirmed against our own data, no edge cases found so far):
- `rp-prod` -> general/legacy instance (Mosaic 1.0)
- `rp-mg` -> mammography-built instance (Mosaic 2.0)

**Historical backfill note**: Mosaic 2.0 didn't go live until end of July 2026, so for any `report_signed_events`/`mosaicreporting` row with a `timestamp` before go-live, the value can be safely assumed `rp-prod` (Mosaic 1.0) without needing to re-process historical logs - only rows from go-live forward actually need the real extracted value. Happy to confirm the exact go-live cutover date if useful.

**Ask recap**: add `radpair_instance` as a pass-through column to `report_signed_events` and, if convenient, `mosaicreporting`, flowing through the existing AWS->Azure Delta Share as-is. Let me know what else would help - happy to hop on a call if that's faster than email.

Thanks,
Bhargav
