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
    Category80D,
    CoOwner,
    DeductionLoan,
    DividendIncome,
    Donation80G,
    Employer,
    HomeLoan,
    HouseProperty,
    InterestIncome,
    Investment80C,
    OtherIncomeEntry,
    PensionContribution80CCC,
    Policy80D,
    Schedule80GGAEntry,
    Schedule80GGCEntry,
    Section80D,
    TaxChallan,
    TcsCredit,
    TenantDetail,
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
    """Resolve a dotted schema path, matching any row for ``[]`` segments."""
    parts = path.split(".")

    def resolve(cur: Any, index: int) -> Any:
        if index == len(parts):
            return cur
        part = parts[index]
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        if key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        if not is_array:
            return resolve(cur, index + 1)
        if not isinstance(cur, list):
            return None
        values = [resolve(item, index + 1) for item in cur]
        populated = [value for value in values if not _is_empty(value)]
        return populated[0] if populated else None

    return resolve(obj, 0)


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
        id="e1", employerName="Acme Corp", employerTAN="DELX12345A",
        employerAddress="1 Business Park", employerCity="Delhi",
        employerStateCode="07", employerPinCode="110001",
        basic=Decimal("600000"), hra=Decimal("120000"),
        rentPaid=Decimal("180000"), isMetroCity=True,
        natureOfEmployment="PE",
    )]
    # Maximally populated property row, including conditional co-owner,
    # tenant, rent, and Section 24(b) structures.
    draft.houseProperties = [HouseProperty(
        id="h1", propertySequenceNo=1, propertyType="LET_OUT",
        address="12A MG Road", city="Delhi", state="07", countryCode="91",
        pinCode="110001", propertyOwnerType="OT",
        propertyOwnerOther="Family trust", ownershipType="JOINT",
        ownershipShare=Decimal("70"), isCoOwned=True,
        isPropertyInJointOwnership=True,
        coOwners=[CoOwner(
            coOwnerSNo=1, name="Co Owner", pan="EFGHI1234J",
            aadhaar="234567890123", share=Decimal("30"),
        )],
        tenantDetails=[TenantDetail(
            tenantSNo=1, name="Example Tenant", pan="JKLMN1234K",
            aadhaar="345678901234", panOrTan="DELA12345B",
        )],
        annualLettingValue=Decimal("300000"),
        unrealizedRent=Decimal("10000"),
        municipalTaxesPaid=Decimal("20000"),
        arrearsOfRent=Decimal("5000"),
        interestOnLoan=Decimal("100000"),
        homeLoans=[HomeLoan(
            lenderType="B", lenderName="Example Bank",
            loanAccountNo="HOME123", dateOfLoan="2020-04-01",
            totalLoanAmount=Decimal("3000000"),
            loanOutstandingAmount=Decimal("2500000"),
            interestUs24B=Decimal("100000"),
        )],
    )]
    # Other-sources interest + deductions.
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("10000"),
    )]
    draft.otherSources.dividends = [DividendIncome(
        id="d1", section="194", grossAmount=Decimal("15000"),
        q1=Decimal("1000"), q2=Decimal("2000"), q3=Decimal("3000"),
        q4=Decimal("4000"), q5=Decimal("5000"),
    )]
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="os1", nature="OTHER", description="Consulting honorarium",
        amount=Decimal("5000"),
    )]
    # 80C investments + 80D health insurance (correct canonical shape:
    # Deductions.section80C is list[Investment80C]; section80D is a
    # Section80D object with selfFamily/parents sub-categories).
    draft.deductions.section80C = [Investment80C(
        id="c1", investmentType="PF", amount=Decimal("140000"),
        identificationNo="PF-12345", accountOrPolicyNo="EPF-001",
    )]
    draft.deductions.section80D = Section80D(
        selfSeniorCitizen="N", parentsSeniorCitizen="N",
        selfFamily=Category80D(
            policies=[Policy80D(
                id="d1", policyType="INDIVIDUAL", premiumAmount=Decimal("20000"),
                insurerName="Star Health", policyNo="SH-001",
            )],
            preventiveCheckup=Decimal("5000"), medicalExpense=Decimal("0"),
        ),
        parents=Category80D(
            policies=[Policy80D(
                id="d2", policyType="FAMILY_FLOATER", premiumAmount=Decimal("25000"),
                insurerName="HDFC Ergo", policyNo="HE-002",
            )],
            preventiveCheckup=Decimal("0"), medicalExpense=Decimal("0"),
        ),
    )
    draft.deductions.pensionContribution80CCC = [PensionContribution80CCC(
        id="ccc1", identifierType="PRAN", identifierName="PRAN123456",
        amount=Decimal("10000"),
    )]
    draft.deductions.chapterVIA.section80CCC = Decimal("10000")
    draft.deductions.chapterVIA.section80D = Decimal("45000")
    draft.deductions.section80G = [Donation80G(
        id="g1", category="50_APPROVAL_REQD", doneeName="Relief Fund",
        doneePAN="AAAAA1234A", arnNumber="ARN123",
        addrDetail="1 Main Road", city="Delhi", stateCode="07",
        pinCode="110001", donationAmtOtherMode=Decimal("10000"),
        transactionRefNum="UTR80G1", ifscCode="SBIN0001234",
    )]
    draft.deductions.chapterVIA.section80G = Decimal("4500")
    draft.deductions.loans.loans = [
        DeductionLoan(
            id="edu1", section="80E", loanTakenFrom="B", lenderName="Example Bank",
            loanAccountNo="EDU123", dateOfLoan="2022-01-01",
            totalLoanAmount=Decimal("200000"), outstandingAmount=Decimal("150000"),
            interestAmount=Decimal("10000"),
        ),
        DeductionLoan(
            id="eea1", section="80EEA", loanTakenFrom="B",
            lenderName="Example Bank", loanAccountNo="HOME123",
            dateOfLoan="2020-04-01", totalLoanAmount=Decimal("3000000"),
            outstandingAmount=Decimal("2500000"),
            interestAmount=Decimal("50000"),
        ),
    ]
    draft.deductions.chapterVIA.section80E = Decimal("10000")
    draft.deductions.chapterVIA.section80EEA = Decimal("50000")
    draft.deductions.loans.section80EEAStampDutyValue = Decimal("4000000")
    draft.deductions.schedule80GGA = [Schedule80GGAEntry(
        id="gga1", relevantClause="80GGA2a", doneeName="Research Fund",
        doneePAN="BBBBB1234B", addressLine="2 Science Road", city="Delhi",
        stateCode="07", pinCode="110001", otherModeAmount=Decimal("3000"),
    )]
    draft.deductions.chapterVIA.section80GGA = Decimal("3000")
    draft.deductions.schedule80GGC = [Schedule80GGCEntry(
        id="ggc1", otherModeAmount=Decimal("4000"),
        contributionDate="2025-06-01", transactionRef="UTR80GGC1",
        ifscCode="SBIN0001234", politicalPartyName="Example Party",
        politicalPartyPAN="CCCCC1234C",
    )]
    draft.deductions.chapterVIA.section80GGC = Decimal("4000")
    # TDS credit (salary TDS — deductor is the employer). The CBDT schema
    # enforces a city-prefix TAN pattern (DEL/BLR/MUM/...); use a valid one.
    draft.taxes.tds = [TdsCredit(
        id="t1", deductorTAN="DELX12345A", deductorName="Acme Corp",
        section="192", taxDeducted=Decimal("30000"),
        grossAmount=Decimal("600000"),
    ), TdsCredit(
        id="t2", deductorTAN="DELY12345B", deductorName="Example Bank",
        section="194A", schedule="TDS2", deductedYr=2025,
        taxDeducted=Decimal("1000"), grossAmount=Decimal("10000"),
    ), TdsCredit(
        id="t3", schedule="TDS3", section="194IB", tdsSectionCode="194IB",
        nameOfTenant="Example Tenant", panOfTenant="DDDDD1234D",
        grsRcptToTaxDeduct=Decimal("120000"), taxDeducted=Decimal("6000"),
        tdsClaimed=Decimal("6000"), deductedYr=2025,
    )]
    draft.taxes.tcs = [TcsCredit(
        id="tcs1", collectorName="Example Collector", collectorTAN="DELZ12345C",
        grossAmount=Decimal("100000"), taxCollected=Decimal("1000"),
        tcsClaimedAmtCollOwnHand=Decimal("1000"), deductedYr=2025,
    )]
    draft.taxes.challans = [
        TaxChallan(
            id="at1", kind="ADVANCE_TAX", bsrCode="1234567",
            depositDate="2025-06-15", challanSerialNo=1, amount=Decimal("5000"),
        ),
        TaxChallan(
            id="sat1", kind="SELF_ASSESSMENT", bsrCode="1234567",
            depositDate="2026-04-15", challanSerialNo=2, amount=Decimal("2000"),
        ),
    ]
    return draft


def build_full_itr4_draft() -> ReturnDraft:
    """A maximally-populated canonical ITR-4 draft (44AD)."""
    from tests.test_filing_gateway_v2_itr4 import _filing_ready_itr4
    draft = _filing_ready_itr4("44AD")
    conditional = build_full_itr1_draft()
    draft.regime = "old"
    draft.employers = conditional.employers
    draft.houseProperties = conditional.houseProperties
    draft.otherSources = conditional.otherSources
    draft.deductions = conditional.deductions
    # 80GGA is not available to a taxpayer with business income in ITR-4.
    draft.deductions.schedule80GGA = []
    draft.deductions.chapterVIA.section80GGA = Decimal("0")
    draft.taxes = conditional.taxes
    return draft


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
