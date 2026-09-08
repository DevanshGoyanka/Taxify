"""Verify the regenerated ITR-1 file: format, digest, credentials, section, tax math."""
import json
import re
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path("D:/Taxify/Taxify")
load_dotenv(ROOT / ".env", override=True)
os.environ["ERI_MODE"] = "type3"
os.environ["ERI_ENV"] = "uat"

import sys
sys.path.insert(0, str(ROOT))
from app.eri.digest import verify_delivered_text, digest_of_delivered_text
from app.engine.common.due_dates import (
    filing_section_due_date_error, get_due_date, is_due_date_passed,
)

SEC = {11: "139(1)", 12: "139(4)", 13: "142(1)", 14: "148",
       16: "153C", 17: "139(5)", 18: "139(9)", 20: "119(2)(b)"}

path = Path("D:/CBDT_de30e822-69da-497e-a361-8c95f0eb1b92_2026-27 (2).json")
raw = path.read_text(encoding="utf-8")
d = json.loads(raw)
obj = d["ITR"]["ITR1"]
ci, fs = obj["CreationInfo"], obj["FilingStatus"]
tc, inc, tp = obj["ITR1_TaxComputation"], obj["ITR1_IncomeDeductions"], obj["TaxPaid"]
intrst = tc["IntrstPay"]

# 1. Format
def spaces_outside(t):
    in_s = esc = n = 0
    for ch in t:
        if esc: esc = False; continue
        if ch == "\\": esc = True; continue
        if ch == '"': in_s = not in_s; continue
        if not in_s and ch == " ": n += 1
    return n

print("=" * 70)
print("  ITR-1 (regenerated)  ", path.name)
print("=" * 70)
print("\n[1] FORMAT")
print("  bytes          :", len(raw.encode("utf-8")))
print("  newlines       :", raw.count("\n"))
print("  tabs           :", raw.count("\t"))
print("  BOM            :", raw.startswith("\ufeff"))
print("  spaces outside :", spaces_outside(raw))
ok_fmt = raw.count("\n")==0 and raw.count("\t")==0 and spaces_outside(raw)==0 and not raw.startswith("\ufeff")
print("  FORMAT OK      :", ok_fmt)

# 2. Digest
print("\n[2] DIGEST")
stamped = re.search(r'"Digest"\s*:\s*"([^"]*)"', raw).group(1)
recomputed = digest_of_delivered_text(raw)
verifies = verify_delivered_text(raw)
print("  stamped        :", stamped, "len=", len(stamped))
print("  recomputed     :", recomputed)
print("  verifies       :", verifies)
ok_dig = verifies and len(stamped) == 44
print("  DIGEST OK      :", ok_dig)

# 3. Credentials
print("\n[3] CREDENTIALS")
print("  SWCreatedBy      :", ci.get("SWCreatedBy"))
print("  JSONCreatedBy    :", ci.get("JSONCreatedBy"))
print("  JSONCreationDate :", ci.get("JSONCreationDate"))
ok_sw = ci.get("SWCreatedBy")=="SW20014243" and ci.get("JSONCreatedBy")=="SW20014243"
print("  SW_ID OK         :", ok_sw)

# 4. Section / date
print("\n[4] FILING STATUS")
rfs = fs.get("ReturnFileSec")
sec = SEC.get(rfs)
due_str = fs.get("ItrFilingDueDate")
on = date(2026, 8, 25)
due = get_due_date("ITR-1", "2026-27")
passed = is_due_date_passed("ITR-1", "2026-27", on)
print("  ReturnFileSec    :", rfs, f"({sec})")
print("  ItrFilingDueDate :", due_str)
print("  form due date    :", due, " passed:", passed)
verdict = filing_section_due_date_error(sec, "ITR-1", "2026-27", on) if sec else "unknown code"
ok_sec = verdict is None
ok_due = due is not None and due_str == due.isoformat()
print("  bidirectional    :", "PASS" if verdict is None else "FAIL")
if verdict: print("    ->", verdict)
print("  due matches      :", ok_due)

# 5. Tax math
print("\n[5] TAX MATH")
ti = inc.get("TotalIncome", 0)
print("  GrossSalary      :", inc.get("GrossSalary"))
print("  GrossTotIncome   :", inc.get("GrossTotIncome"))
print("  TotalIncome      :", ti)
print("  GrossTaxLiability:", tc.get("GrossTaxLiability"))
print("  Rebate87A        :", tc.get("Rebate87A"))
print("  EducationCess    :", tc.get("EducationCess"))
print("  NetTaxLiability  :", tc.get("NetTaxLiability"))
print("  LateFilingFee234F:", intrst.get("LateFilingFee234F"))
print("  IntrstPayUs234A  :", intrst.get("IntrstPayUs234A"))
print("  TotTaxPlusIntrst :", tc.get("TotTaxPlusIntrstPay"))
print("  BalTaxPayable    :", tp.get("BalTaxPayable"))
exp_234f = 1000 if (passed and ti <= 500000) else (5000 if passed else 0)
ok_234f = intrst.get("LateFilingFee234F") == exp_234f
ok_bal = tp.get("BalTaxPayable") == tc.get("TotTaxPlusIntrstPay")
print("  expected 234F    :", exp_234f, "->", "OK" if ok_234f else "MISMATCH")
print("  Bal==TotTaxPlus  :", ok_bal)

# 6. Verification
print("\n[6] VERIFICATION")
v = obj.get("Verification", {})
print("  Place  :", v.get("Place"))
print("  Capacity:", v.get("Capacity"))
print("  has Date key:", "Date" in v, "(expected False)")

# Summary
print("\n" + "=" * 70)
overall = ok_fmt and ok_dig and ok_sw and ok_sec and ok_due and ok_234f and ok_bal
print(f"  format={ok_fmt} digest={ok_dig} sw_id={ok_sw} section={ok_sec} "
      f"due={ok_due} 234F={ok_234f} balance={ok_bal}")
print(f"  >>> {'ALL CHECKS PASS — file is good to send' if overall else 'DEFECTS REMAIN — see above'}")
