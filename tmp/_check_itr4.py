"""Read-only check of an exported CBDT JSON file: format, digest, schema, and tax math."""
import json
import re
import hmac
import hashlib
import base64
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path("D:/Taxify/Taxify")
load_dotenv(ROOT / ".env", override=True)

p = Path("D:/CBDT_de585d10-95bd-4e3a-9161-745dc07258da_2026-27.json")
raw = p.read_text(encoding="utf-8")

print("=== FILE FORMAT ===")
print("bytes          :", len(raw.encode("utf-8")))
print("newlines       :", raw.count("\n"))
print("tabs           :", raw.count("\t"))
print("has BOM        :", raw.startswith("\ufeff"))
print("starts with    :", repr(raw[:12]))

in_str = False
esc = False
outside_spaces = 0
for ch in raw:
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
        outside_spaces += 1
print("spaces outside :", outside_spaces)

print()
print("=== DIGEST ===")
d = json.loads(raw)
digest = d["ITR"]["ITR4"]["CreationInfo"]["Digest"]
print("stamped digest :", digest, "len=", len(digest))

key = os.environ.get("ERI_DIGEST_SECRET_KEY_TYPE3_UAT", "")
iters = int(os.environ.get("ERI_DIGEST_ITERATIONS_TYPE3_UAT", "0") or 0)
print("secret key set :", bool(key), "iters=", iters)

minified = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"))
payload = re.sub(r'"Digest"\s*:\s*"[^"]*"', '"Digest":"-"', minified)
digest_bytes = payload.encode("utf-8")
for _ in range(iters):
    digest_bytes = hmac.new(key.encode("utf-8"), digest_bytes, hashlib.sha256).digest()
recomputed = base64.b64encode(digest_bytes).decode("utf-8")
print("recomputed     :", recomputed)
print("verifies       :", recomputed == digest)

print()
print("=== FILING STATUS ===")
fs = d["ITR"]["ITR4"]["FilingStatus"]
ci = d["ITR"]["ITR4"]["CreationInfo"]
print("ReturnFileSec      :", fs.get("ReturnFileSec"))
print("ItrFilingDueDate   :", fs.get("ItrFilingDueDate"))
print("SWCreatedBy        :", ci.get("SWCreatedBy"))
print("JSONCreatedBy      :", ci.get("JSONCreatedBy"))
print("JSONCreationDate    :", ci.get("JSONCreationDate"))

print()
print("=== TAX MATH ===")
tc = d["ITR"]["ITR4"]["TaxComputation"]
inc = d["ITR"]["ITR4"]["IncomeDeductions"]
tp = d["ITR"]["ITR4"]["TaxPaid"]
print("GrossTotIncome     :", inc.get("GrossTotIncome"))
print("TotalIncome        :", inc.get("TotalIncome"))
print("GrossTaxLiability  :", tc.get("GrossTaxLiability"))
print("Rebate87A          :", tc.get("Rebate87A"))
print("EducationCess      :", tc.get("EducationCess"))
print("NetTaxLiability    :", tc.get("NetTaxLiability"))
print("LateFilingFee234F  :", tc.get("IntrstPay", {}).get("LateFilingFee234F"))
print("IntrstPayUs234A    :", tc.get("IntrstPay", {}).get("IntrstPayUs234A"))
print("TotTaxPlusIntrstPay:", tc.get("TotTaxPlusIntrstPay"))
print("BalTaxPayable      :", tp.get("BalTaxPayable"))

print()
print("=== PRESUMPTIVE ===")
bp = d["ITR"]["ITR4"]["ScheduleBP"]
pad = bp["PersumptiveInc44AD"]
print("GrsTotalTrnOver       :", pad.get("GrsTotalTrnOver"))
print("GrsTotalTrnOverInCash :", pad.get("GrsTotalTrnOverInCash"))
print("PersumptiveInc44AD6Per :", pad.get("PersumptiveInc44AD6Per"))
print("PersumptiveInc44AD8Per :", pad.get("PersumptiveInc44AD8Per"))
print("TotPersumptiveInc44AD :", pad.get("TotPersumptiveInc44AD"))

print()
print("=== VERIFICATION ===")
v = d["ITR"]["ITR4"]["Verification"]
print("Place        :", v.get("Place"))
print("Capacity     :", v.get("Capacity"))
print("Has Date key :", "Date" in v)
