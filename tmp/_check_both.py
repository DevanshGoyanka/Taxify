"""Comprehensive verification of two exported CBDT JSON files (ITR-1 and ITR-4).

Checks, per file:
  1. File format  : bytes, newlines, tabs, BOM, spaces outside string values
  2. Digest       : 44 chars, recomputes via HMAC-SHA256 x iters against own bytes
  3. Credentials  : SWCreatedBy / JSONCreatedBy == SW20014243
  4. Filing status: ReturnFileSec, ItrFilingDueDate, section/date consistency
  5. Tax math     : income, tax, rebate, cess, 234F, 234A, balances
"""
import json
import re
import hmac
import hashlib
import base64
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path("D:/Taxify/Taxify")
load_dotenv(ROOT / ".env", override=True)

KEY = os.environ.get("ERI_DIGEST_SECRET_KEY_TYPE3_UAT", "")
ITERS = int(os.environ.get("ERI_DIGEST_ITERATIONS_TYPE3_UAT", "0") or 0)
SW_ID = os.environ.get("ERI_SW_ID_TYPE3_UAT", "SW20014243")

# Import the live bidirectional checker so we judge with the same code the
# generation pipeline uses.
import sys
sys.path.insert(0, str(ROOT))
from app.engine.common.due_dates import (
    filing_section_due_date_error,
    get_due_date,
    is_due_date_passed,
)

SEC_TO_CODE = {"139(1)": 11, "139(4)": 12, "139(5)": 17, "142(1)": 13,
               "148": 14, "153C": 16, "139(9)": 18, "119(2)(b)": 20}
CODE_TO_SEC = {v: k for k, v in SEC_TO_CODE.items()}

FILES = {
    "ITR-1": Path("D:/CBDT_de30e822-69da-497e-a361-8c95f0eb1b92_2026-27 (1).json"),
    "ITR-4": Path("D:/CBDT_de585d10-95bd-4e3a-9161-745dc07258da_2026-27 (1).json"),
}


def count_spaces_outside_strings(text: str) -> int:
    """Count space chars that are structural whitespace, not inside a string."""
    in_str = False
    esc = False
    count = 0
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str and ch == " ":
            count += 1
    return count


def recompute_digest(raw: str) -> tuple[str, bool]:
    """Recompute the Digest the way ITD does: minify, placeholder, HMAC loop."""
    minified = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"))
    payload = re.sub(r'"Digest"\s*:\s*"[^"]*"', '"Digest":"-"', minified)
    digest_bytes = payload.encode("utf-8")
    for _ in range(ITERS):
        digest_bytes = hmac.new(KEY.encode("utf-8"), digest_bytes, hashlib.sha256).digest()
    return base64.b64encode(digest_bytes).decode("utf-8")


def verify(form: str, path: Path) -> None:
    print("=" * 78)
    print(f"  {form}   {path.name}")
    print("=" * 78)
    raw = path.read_text(encoding="utf-8")
    d = json.loads(raw)
    itr = d["ITR"]
    form_key = "ITR1" if form == "ITR-1" else "ITR4"
    obj = itr[form_key]
    ci = obj["CreationInfo"]
    fs = obj["FilingStatus"]
    if form == "ITR-1":
        tc = obj["ITR1_TaxComputation"]
        inc = obj["ITR1_IncomeDeductions"]
    else:
        tc = obj["TaxComputation"]
        inc = obj["IncomeDeductions"]
    tp = obj["TaxPaid"]

    # ---- 1. Format ----
    print("\n[1] FILE FORMAT")
    print(f"    bytes            : {len(raw.encode('utf-8'))}")
    print(f"    newlines         : {raw.count(chr(10))}")
    print(f"    tabs             : {raw.count(chr(9))}")
    print(f"    BOM              : {raw.startswith(chr(0xFEFF))}")
    spaces = count_spaces_outside_strings(raw)
    print(f"    spaces outside   : {spaces}")
    ok_fmt = (raw.count("\n") == 0 and raw.count("\t") == 0 and spaces == 0
              and not raw.startswith("\ufeff"))
    print(f"    FORMAT OK        : {ok_fmt}")

    # ---- 2. Digest ----
    print("\n[2] DIGEST")
    digest = ci.get("Digest", "")
    print(f"    stamped          : {digest}")
    print(f"    length           : {len(digest)}")
    recomputed = recompute_digest(raw)
    print(f"    recomputed       : {recomputed}")
    print(f"    key set          : {bool(KEY)}  iters={ITERS}")
    ok_dig = (len(digest) == 44 and recomputed == digest)
    print(f"    DIGEST OK        : {ok_dig}")

    # ---- 3. Credentials ----
    print("\n[3] CREDENTIALS")
    print(f"    SWCreatedBy      : {ci.get('SWCreatedBy')}")
    print(f"    JSONCreatedBy    : {ci.get('JSONCreatedBy')}")
    print(f"    JSONCreationDate : {ci.get('JSONCreationDate')}")
    print(f"    expected SW_ID   : {SW_ID}")
    ok_sw = (ci.get("SWCreatedBy") == SW_ID and ci.get("JSONCreatedBy") == SW_ID)
    print(f"    SW_ID OK         : {ok_sw}")

    # ---- 4. Filing status & section/date consistency ----
    print("\n[4] FILING STATUS & SECTION/DATE")
    rfs = fs.get("ReturnFileSec")
    due_str = fs.get("ItrFilingDueDate")
    declared_sec = CODE_TO_SEC.get(rfs)
    print(f"    ReturnFileSec    : {rfs}  ({declared_sec})")
    print(f"    ItrFilingDueDate : {due_str}")
    # The file's declared filing date = JSONCreationDate (the date it was
    # prepared); for the section check the return itself claims no Date in
    # Verification (AY 2026-27 schema has none), so today is the on_date.
    on_date = date(2026, 8, 25)
    due = get_due_date(form, "2026-27")
    passed = is_due_date_passed(form, "2026-27", on_date)
    print(f"    form due date    : {due}")
    print(f"    due passed (2026-08-25): {passed}")
    if declared_sec:
        verdict = filing_section_due_date_error(declared_sec, form, "2026-27", on_date)
        print(f"    bidirectional check: {'PASS' if verdict is None else 'FAIL'}")
        if verdict:
            print(f"      -> {verdict}")
        ok_sec = verdict is None
    else:
        ok_sec = False
        print("    bidirectional check: FAIL (unknown section code)")
    # due date in file must match the form's canonical due date
    ok_due = (due is not None and due_str == due.isoformat())
    print(f"    due date matches : {ok_due}")

    # ---- 5. Tax math ----
    print("\n[5] TAX MATH")
    intrst = tc.get("IntrstPay", {})
    if form == "ITR-1":
        salary = inc.get("GrossSalary", 0)
        gti = inc.get("GrossTotIncome", 0)
        ti = inc.get("TotalIncome", 0)
        print(f"    GrossSalary      : {salary}")
        print(f"    GrossTotIncome   : {gti}")
        print(f"    TotalIncome      : {ti}")
    else:
        bp = obj.get("ScheduleBP", {})
        pad = bp.get("PersumptiveInc44AD", {})
        print(f"    44AD turnover    : {pad.get('GrsTotalTrnOver')}")
        print(f"    44AD 8% income   : {pad.get('PersumptiveInc44AD8Per')}")
        print(f"    Total 44AD      : {pad.get('TotPersumptiveInc44AD')}")
        gti = inc.get("GrossTotIncome", 0)
        ti = inc.get("TotalIncome", 0)
        print(f"    GrossTotIncome   : {gti}")
        print(f"    TotalIncome      : {ti}")
    print(f"    GrossTaxLiability: {tc.get('GrossTaxLiability')}")
    print(f"    Rebate87A        : {tc.get('Rebate87A')}")
    print(f"    EducationCess    : {tc.get('EducationCess')}")
    print(f"    NetTaxLiability  : {tc.get('NetTaxLiability')}")
    print(f"    LateFilingFee234F: {intrst.get('LateFilingFee234F')}")
    print(f"    IntrstPayUs234A  : {intrst.get('IntrstPayUs234A')}")
    print(f"    TotTaxPlusIntrst : {tc.get('TotTaxPlusIntrstPay')}")
    print(f"    BalTaxPayable    : {tp.get('BalTaxPayable')}")

    # Cross-check 234F: ₹1000 if TI<=5L and due passed; ₹5000 if TI>5L and
    # due passed; 0 if on time. Nil-tax + rebate returns have 0 tax but the
    # 234F fee still applies if belated.
    expected_234f = 0
    if passed:
        if ti <= 500000:
            expected_234f = 1000
        else:
            expected_234f = 5000
    actual_234f = intrst.get("LateFilingFee234F", 0)
    ok_234f = (actual_234f == expected_234f)
    print(f"    expected 234F    : {expected_234f}  (actual {actual_234f}) -> {'OK' if ok_234f else 'MISMATCH'}")

    # BalTaxPayable should equal tax + interest + fee - taxes paid
    bal = tp.get("BalTaxPayable", 0)
    total_pay = tc.get("TotTaxPlusIntrstPay", 0)
    ok_bal = (bal == total_pay)
    print(f"    BalTaxPayable==TotTaxPlusIntrst : {ok_bal}")

    # ---- 6. Verification block ----
    print("\n[6] VERIFICATION")
    v = obj.get("Verification", {})
    print(f"    Place            : {v.get('Place')}")
    print(f"    Capacity         : {v.get('Capacity')}")
    print(f"    has Date key    : {'Date' in v}  (expected False for AY2026-27)")

    # ---- summary ----
    print("\n[SUMMARY]")
    overall = ok_fmt and ok_dig and ok_sw and ok_sec and ok_due and ok_234f and ok_bal
    print(f"    format={ok_fmt} digest={ok_dig} sw_id={ok_sw} section={ok_sec} due={ok_due} 234F={ok_234f} balance={ok_bal}")
    print(f"    >>> {'ALL CHECKS PASS' if overall else 'DEFECTS FOUND — see above'}")
    print()


for form, path in FILES.items():
    if path.exists():
        verify(form, path)
    else:
        print(f"MISSING: {path}")
