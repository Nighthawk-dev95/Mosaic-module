import csv

SRC_CSV = "mammo_accession_detail_full.csv"

# RPID -> (CPT_Code, CPT_Description), with manual fixes for bilateral-suffix
# and no-charge placeholder codes that didn't resolve directly.
FIXES = {
    "FLNC": ("N/A", "No-charge / non-billable internal code"),
    "INTNC": ("N/A", "No-charge / non-billable internal code"),
    "MGNOBILL": ("N/A", "No-charge / non-billable internal code"),
    "RAD2549": ("76641-50", "ULTRASOUND, BREAST, UNILATERAL, REAL TIME WITH IMAGE DOCUMENTATION, INCLUDING AXILLA WHEN PERFORMED; COMPLETE (bilateral)"),
    "RPID1977": ("76641-50", "ULTRASOUND, BREAST, UNILATERAL, REAL TIME WITH IMAGE DOCUMENTATION, INCLUDING AXILLA WHEN PERFORMED; COMPLETE (bilateral)"),
    "RPID1980": ("76642-50", "ULTRASOUND, BREAST, UNILATERAL, REAL TIME WITH IMAGE DOCUMENTATION, INCLUDING AXILLA WHEN PERFORMED; LIMITED (bilateral)"),
    "RPID2653": ("73562-50", "RADIOLOGIC EXAMINATION, KNEE; 3 VIEWS (bilateral)"),
    "RPID3334": ("73110-50", "RADIOLOGIC EXAMINATION, WRIST; COMPLETE, MINIMUM OF 3 VIEWS (bilateral)"),
}

cpt_map = {}
with open("_rpid_cpt_map.tsv", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 3:
            continue
        rpid, code, desc = parts
        if rpid in FIXES:
            code, desc = FIXES[rpid]
        cpt_map[rpid] = (code, desc if desc != "None" else "")

with open(SRC_CSV, newline="", encoding="utf-8") as f:
    r = csv.reader(f)
    rows = list(r)

header = rows[0]
pr_i = header.index("ParentRpt")
lpr_i = header.index("Linked_ParentRpt")

# Insert CPT_Code/CPT_Code_Description right after ParentRpt/Parent_Procedure_name block,
# and Linked_CPT_Code/Linked_CPT_Code_Description right after Linked_ParentRpt/Linked_Procedure_Description.
new_header = header + ["CPT_Code", "CPT_Code_Description", "Linked_CPT_Code", "Linked_CPT_Code_Description"]

new_rows = [new_header]
missing = set()
for row in rows[1:]:
    pr = row[pr_i].strip()
    lpr = row[lpr_i].strip()
    code, desc = cpt_map.get(pr, ("", ""))
    if pr and pr not in cpt_map:
        missing.add(pr)
    lcode, ldesc = cpt_map.get(lpr, ("", "")) if lpr else ("", "")
    if lpr and lpr not in cpt_map:
        missing.add(lpr)
    new_rows.append(row + [code, desc, lcode, ldesc])

if missing:
    print("WARNING - ParentRpt codes with no CPT mapping found:", sorted(missing))

with open(SRC_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerows(new_rows)

print("done, rows:", len(new_rows) - 1)
