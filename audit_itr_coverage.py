"""End-to-end coverage audit: build a maximally-populated draft, generate the
official CBDT JSON, and report which REQUIRED schema fields are missing or
empty in the output.

This is the ground-truth compliance check: even if a field is "in the
frontend", if the builder never emits it (or emits it empty), the JSON
fails the CBDT schema gate. The schema validator already enforces this
on every generate_cbdt_json call; this script surfaces the gaps BEFORE
validation (so we can see which required fields are blank, not just that
validation failed).

Run: python audit_itr_coverage.py
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.engine.filing_gateway_v2 import generate_cbdt_json, FilingGatewayV2Error
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    HomeLoan,
    HouseProperty,
    InterestIncome,
    Investment80C,
    Policy80D,
    TdsCredit,
    ReturnDraft,
    create_empty_draft,
)


def _load_required_fields(form: str) -> list[str]:
    """Load the REQUIRED leaf field paths from the extracted inventory CSV."""
    csv_path = Path(f"audit_{form.lower().replace('-', '')}_schema_fields.csv")
    fields: list[str] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["required"] == "Y":
                fields.append(row["path"])
    return fields
    """Load the REQUIRED leaf field paths from the extracted inventory CSV."""
    csv_path = Path(f"audit_{form.lower().replace('-', '')}_schema_fields.csv")
    fields: list[str] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["required"] == "Y":
                fields.append(row["path"])
    return fields


def _get_path(obj: Any, path: str) -> Any:
    """Resolve a dotted schema path (with [] for arrays) against the JSON."""
    parts = path.replace("[]", "[0]").split(".")
    cur: Any = obj
    for part in parts:
        if part == "":
            continue
        if "[" in part and part.endswith("]"):
            name, _, idx = part.partition("[")
            idx = idx.rstrip("]")
            if name and isinstance(cur, dict):
                cur = cur.get(name, {})
            if isinstance(cur, list) and cur:
                try:
                    cur = cur[int(idx)]
                except (ValueError, IndexError):
                    cur = {}
            elif isinstance(cur, list) and not cur:
                cur = {}
            else:
                cur = {}
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def build_full_itr1_draft() -> ReturnDraft:
    """A maximally-populated canonical ITR-1 draft (every income head)."""
    draft = create_empty_draft("2026-27", "ITR-1", "old")
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Asha"
    p.middleName = "Rani"
    p.surnameOrOrgName = "Sharma"
    p.name = "Asha Rani Sharma"
    p.dateOfBirth = "1990-01-15"
    p.age = 36
    p.aadhaar = "123456789012"
    p.fatherName = "Ramesh Sharma"
    p.employerCategory = "OTH"
    p.flatNo = "12A"
    p.roadOrStreet = "MG Road"
    p.localityOrArea = "Central Colony"
    p.city = "Delhi"
    p.stateCode = "07"
    p.countryCode = "91"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "asha.sharma@example.com"
    draft.filing.filingSection = "139(1)"
    draft.verification.capacity = "SELF"
    draft.verification.place = "Delhi"
    draft.verification.declarationAccepted = True
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="State Bank of India", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]
    draft.employers = [Employer(
        id="e1", employerName="Acme Corp", basic=Decimal("600000"),
        natureOfEmployment="PE",
    )]
    # House property (self-occupied + one let-out with home loan).
    draft.houseProperties = [HouseProperty(
        id="h1", propertyType="SELF_OCCUPIED", address="12A MG Road Delhi",
        ownershipShare=100,
    )]
    # Other-sources interest + deductions.
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("10000"),
    )]
    # NOTE: deductions omitted — see audit findings. The ITR-1 mapper
    # _map_80d reads section80D.selfSeniorCitizen (flat-blob shape) but the
    # canonical Deductions.section80D is list[Policy80D] (typed shape). This
    # is a real mapper/canonical mismatch that breaks 80D mapping.
    # TDS credit (salary TDS — deductor is the employer). The CBDT schema
    # enforces a city-prefix TAN pattern (DEL/BLR/MUM/...); use a valid one.
    draft.taxes.tds = [TdsCredit(
        id="t1", deductorTAN="DELX12345A", deductorName="Acme Corp",
        section="192", taxDeducted=Decimal("30000"),
        grossAmount=Decimal("600000"),
    )]
    return draft


def build_full_itr4_draft() -> ReturnDraft:
    """A maximally-populated canonical ITR-4 draft (44AD)."""
    from app.schemas.return_draft import Presumptive44AD
    from tests.test_filing_gateway_v2_itr4 import _filing_ready_itr4
    return _filing_ready_itr4("44AD")


def audit(form: str, draft: ReturnDraft) -> None:
    """Generate the official JSON and report required-field coverage."""
    print(f"\n{'=' * 70}\n{form} end-to-end coverage audit\n{'=' * 70}")
    try:
        official, summary = generate_cbdt_json(draft)
    except FilingGatewayV2Error as exc:
        print(f"  generate_cbdt_json FAILED: {exc.message}")
        for err in exc.errors[:6]:
            print(f"    - {err[:160]}")
        return
    required = _load_required_fields(form)
    # Dedupe the required list (allOf can produce duplicate paths).
    seen: set[str] = set()
    required = [r for r in required if not (r in seen or seen.add(r))]
    print(f"  JSON generated OK. Checking {len(required)} required schema fields...")
    missing: list[str] = []
    empty: list[str] = []
    present: list[str] = []
    for path in required:
        val = _get_path(official, path)
        if val is None:
            missing.append(path)
        elif _is_empty(val):
            empty.append(path)
        else:
            present.append(path)
    print(f"  PRESENT : {len(present)}/{len(required)}")
    print(f"  MISSING : {len(missing)}")
    print(f"  EMPTY   : {len(empty)}")
    # Persist full missing/empty/present lists to CSV for the report.
    slug = form.lower().replace("-", "")
    for label, rows in (("missing", missing), ("empty", empty), ("present", present)):
        out = Path(f"audit_{slug}_{label}.csv")
        with out.open("w", encoding="utf-8") as f:
            f.write("path\n")
            for p in rows:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"  {label:8}: {len(rows):3d} -> {out}")
    Path(f"audit_{slug}_generated.json").write_text(
        json.dumps(official, indent=2, default=str), encoding="utf-8")
    print(f"  Generated JSON written to audit_{slug}_generated.json")


def main() -> None:
    audit("ITR-1", build_full_itr1_draft())
    audit("ITR-4", build_full_itr4_draft())


if __name__ == "__main__":
    main()
