-- Removes the 40 Procedure Codes that have no match in either of the 2 reference Excel
-- files ("XR - Proecdure List.xlsx" / "CT - Proecdure List.xlsx") from the underlying
-- source table edw_dev.bipa_analytics.251212_xr_drafting_procedure_codes (a real managed
-- Delta table, 484 rows, DESCRIBE TABLE EXTENDED confirms Type=MANAGED - DELETE works
-- directly, this is not a view). Request 2026-09-23: "Give me a delete statement in this
-- view to remove them from here edw_dev.bipa_analytics.251212_xr_drafting_procedure_codes."
--
-- 31 are the CT Neck / Head-Neck-combo family (CTPRTHDW, RAD2323/2324/2325, RAD2980-2982,
-- RPID11/37/38/39/379/416-418 and their variants, CTHWOCTA*) that isn't its own category in
-- either Excel file. The other 9 (CT4PHLIV, CTHFCSPWO, RAD2852-2854, RAD2986/2987,
-- RPID21-PD, RPID46-RC) are also absent from both files.
--
-- After this runs, the table drops from 484 to 444 rows (usual duplicate-name rows for
-- RAD2311/RAD2526/RPID2590 stay - those ARE in the crosswalk, untouched by this delete).
--
-- CONFIRMED DEPLOYED (2026-09-30): verified live - the table now has 444 rows (484 - 40),
-- zero of the 40 target codes remain, and spot-checked codes NOT in this delete list
-- (RPID6, RAD2008, RPID22, and the RAD2311/RAD2526/RPID2590 duplicates) are all still
-- present untouched.

DELETE FROM edw_dev.bipa_analytics.`251212_xr_drafting_procedure_codes`
WHERE `Procedure Code` IN (
  'CTPRTHDW','RAD2323','RAD2324','RAD2325','RAD2980','RAD2981','RAD2982',
  'RPID11','RPID37','RPID379','RPID3793D','RPID379S','RPID37ST','RPID38','RPID38-4D',
  'RPID38ST','RPID39','RPID39ST','RPID416','RPID417','RPID418',
  'RPID1004','RPID1004PERF','RPID1004S','RPID1005','RPID1005-3D','RPID1005PERF','RPID1005S',
  'CTHWOCTAHDNKW','CTHWOCTAHDNKWWO','CTHWOCTANKW',
  'CT4PHLIV','CTHFCSPWO','RAD2852','RAD2853','RAD2854','RAD2986','RAD2987',
  'RPID21-PD','RPID46-RC'
)
