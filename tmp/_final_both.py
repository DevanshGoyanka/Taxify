"""Final unified verification of both CBDT JSON files."""
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

FILES = {
    "ITR-1": Path("D:/CBDT_de30e822-69da-497e-a361-8c95f0eb1b92_2026-27 (2).json"),
    "ITR-4": Path("D:/CBDT_de585d10-95bd-4e3a-9161-745dc07258da_2026-27 (1).json"),
}


def spaces_outside(t):
    in_s = esc = n = 0
    for ch in t:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_s = not in_s
            continue
        if not in_s and ch == " ":
            n += 1
    return n


def verify(form, path):
    raw = path.read_text(encoding="utf-8")
    d = json.loads(raw)
    fk = "ITR1" if form == "ITR-1" else "ITR4"
    obj = d["ITR"][fk]
    ci, fs = obj["CreationInfo"], obj["FilingStatus"]
    if form == "ITR-1":
        tc, inc, tp = obj["ITR1_TaxComputation"], obj["ITR1_IncomeDeductions"], obj["TaxPaid"]
    else:
        tc, inc, tp = obj["TaxComputation"], obj["IncomeDeductions"], obj["TaxPaid"]
    intrst = tc.get("IntrstPay", {})
    v = obj.get("Verification", {})

    print("=" * 72)
    print(f"  {form}   {path.name}")
    print("=" * 72)

    # 1. Format
    ok_fmt = (raw.count("\n") == 0 and raw.count("\t") == 0
              and spaces_outside(raw) == 0 and not raw.startswith("\ufeff"))
    print(f"[1] FORMAT        bytes={len(raw.encode('utf-8'))} newlines={raw.count(chr(10))} "
          f"tabs={raw.count(chr(9))} spaces_outside={spaces_outside(raw)} BOM={raw.startswith(chr(0xFEFF))}  -> {'OK' if ok_fmt else 'FAIL'}")

    # 2. Digest
    stamped = re.search(r'"Digest"\s*:\s*"([^"]*)"', raw).group(1)
    verifies = verify_delivered_text(raw)
    ok_dig = verifies and len(stamped) == 44
    print(f"[2] DIGEST        stamped={stamped[:40]}... len={len(stamped)}")
    print(f"                  recomputed={digest_of_delivered_text(raw)[:40]}... verifies={verifies}  -> {'OK' if ok_dig else 'FAIL'}")

    # 3. Credentials
    ok_sw = ci.get("SWCreatedBy") == "SW20014243" and ci.get("JSONCreatedBy") == "SW20014243"
    print(f"[3] SW_ID         SWCreatedBy={ci.get('SWCreatedBy')} JSONCreatedBy={ci.get('JSONCreatedBy')} date={ci.get('JSONCreationDate')}  -> {'OK' if ok_sw else 'FAIL'}")

    # 4. Section / date
    rfs = fs.get("ReturnFileSec")
    sec = SEC.get(rfs)
    due_str = fs.get("ItrFilingDueDate")
    on = date(2026, 8, 25)
    due = get_due_date(form, "2026-27")
    passed = is_due_date_passed(form, "2026-27", on)
    verdict = filing_section_due_date_error(sec, form, "2026-27", on) if sec else "unknown"
    ok_sec = verdict is None
    ok_due = due is not None and due_str == due.isoformat()
    print(f"[4] SECTION       ReturnFileSec={rfs}({sec}) ItrFilingDueDate={due_str}")
    print(f"                  form_due={due} passed={passed} bidirectional={'PASS' if ok_sec else 'FAIL'} due_matches={ok_due}  -> {'OK' if (ok_sec and ok_due) else 'FAIL'}")
    if verdict:
        print(f"                  -> {verdict}")

    # 5. Tax math
    ti = inc.get("TotalIncome", 0)
    gti = inc.get("GrossTotIncome", 0)
    exp_234f = 1000 if (passed and ti <= 500000) else (5000 if passed else 0)
    ok_234f = intrst.get("LateFilingFee234F") == exp_234f
    ok_bal = tp.get("BalTaxPayable") == tc.get("TotTaxPlusIntrstPay")
    print(f"[5] TAX MATH      GTI={gti} TI={ti} GrossTax={tc.get('GrossTaxLiability')} "
          f"Rebate87A={tc.get('Rebate87A')} Cess={tc.get('EducationCess')} NetTax={tc.get('NetTaxLiability')}")
    print(f"                  234F={intrst.get('LateFilingFee234F')}(exp {exp_234f}) 234A={intrst.get('IntrstPayUs234A')} "
          f"TotTaxPlusIntrst={tc.get('TotTaxPlusIntrstPay')} BalTaxPayable={tp.get('BalTaxPayable')}")
    print(f"                  234F_ok={ok_234f} balance_ok={ok_bal}  -> {'OK' if (ok_234f and ok_bal) else 'FAIL'}")

    # 6. Verification
    ok_v = "Date" not in v
    print(f"[6] VERIFICATION  Place={v.get('Place')} Capacity={v.get('Capacity')} has_Date={'Date' in v}  -> {'OK' if ok_v else 'FAIL'}")

    overall = ok_fmt and ok_dig and ok_sw and ok_sec and ok_due and ok_234f and ok_bal and ok_v
    print(f"\n>>> {'ALL CHECKS PASS' if overall else 'DEFECTS REMAIN'}")
    print()
    return overall


all_ok = True
for form, path in FILES.items():
    if not path.exists():
        print(f"MISSING: {path}")
        all_ok = False
        continue
    if not verify(form, path):
        all_ok = False

print("=" * 72)
print(f"  FINAL: {'BOTH FILES PASS — ready to send to erihelp@incometax.gov.in' if all_ok else 'DEFECTS FOUND'}")
print("=" * 72)
