"""Diagnose the ITR-1 digest mismatch: try candidate key/iteration sets."""
import json
import re
import hmac
import hashlib
import base64
from pathlib import Path

raw = Path("D:/CBDT_de30e822-69da-497e-a361-8c95f0eb1b92_2026-27 (1).json").read_text(encoding="utf-8")
d = json.loads(raw)
stamped = d["ITR"]["ITR1"]["CreationInfo"]["Digest"]
print("stamped digest:", stamped)
print()

minified = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"))
payload = re.sub(r'"Digest"\s*:\s*"[^"]*"', '"Digest":"-"', minified)


def loop(key: str, iters: int) -> str:
    b = payload.encode("utf-8")
    for _ in range(iters):
        b = hmac.new(key.encode("utf-8"), b, hashlib.sha256).digest()
    return base64.b64encode(b).decode("utf-8")


candidates = [
    ("939069c7620b4c8f", 1646, "new Type-3 UAT key / new iters"),
    ("4448ffc0cec1a25d", 1344, "Type-2 UAT key / iters"),
    ("939069c7620b4c8f", 1, "new key, 1 iter"),
    ("939069c7620b4c8f", 1038, "new key, OLD Type-3 iters"),
    ("4448ffc0cec1a25d", 1038, "Type-2 key, old Type-3 iters"),
    ("0123456789abcdef", 7, "test fake"),
]
for key, iters, label in candidates:
    out = loop(key, iters)
    match = "<<< MATCH" if out == stamped else ""
    print(f"  {label:40s} -> {out}  {match}")

# Also: does the digest verify if we pretend LateFilingFee234F was 0 (pre-fix)?
print()
print("=== Hypothesis: stamped digest was computed over the PRE-234F-fix text ===")
d2 = json.loads(raw)
d2["ITR"]["ITR1"]["ITR1_TaxComputation"]["IntrstPay"]["LateFilingFee234F"] = 0
d2["ITR"]["ITR1"]["ITR1_TaxComputation"]["NetTaxLiability"] = 0
d2["ITR"]["ITR1"]["ITR1_TaxComputation"]["TotTaxPlusIntrstPay"] = 0
d2["ITR"]["ITR1"]["TaxPaid"]["BalTaxPayable"] = 0
pre = json.dumps(d2, ensure_ascii=False, separators=(",", ":"))
pre_payload = re.sub(r'"Digest"\s*:\s*"[^"]*"', '"Digest":"-"', pre)
b = pre_payload.encode("utf-8")
for _ in range(1646):
    b = hmac.new("939069c7620b4c8f".encode("utf-8"), b, hashlib.sha256).digest()
pre_digest = base64.b64encode(b).decode("utf-8")
print("stamped                              :", stamped)
print("recomputed over 234F=0/NetTax=0 text :", pre_digest)
print("match (pre-fix hypothesis)           :", pre_digest == stamped)
