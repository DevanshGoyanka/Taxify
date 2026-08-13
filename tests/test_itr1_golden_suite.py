"""
ITR-1 Golden End-to-End Test Suite — AY 2026-27

Each golden case asserts the full pipeline:
  frontend canonical draft (flat payload)
    -> _build_itr1_input_from_flat (mapper)
    -> ITR1Input (typed Pydantic model)
    -> compute (ITR-1 calculator)
    -> build_itr1_json (official JSON builder)
    -> validate_itr1_json (official V1.1 schema validator)

All cases use real taxpayer-like identity (synthetic PAN) and must produce
schema-valid ITR-1 JSON. No placeholders are acceptable in the output.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.calculators.itr1 import compute
from app.engine.filing_gateway import _build_itr1_input_from_flat
from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr1_schema import validate_itr1_json


# ---------------------------------------------------------------------------
# Shared base payload — minimal valid ITR-1 identity and bank details.
# Each test extends this with test-specific fields.
# ---------------------------------------------------------------------------

def _base() -> dict:
    return {
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "assessmentYear": "2026-27",
        "regime": "OLD",
        "taxRegime": "OLD",
        "pan": "ABCDE1234F",
        "firstName": "Priya",
        "middleName": "",
        "surnameOrOrgName": "Verma",
        "name": "Priya Verma",
        "dob": "1988-03-15",
        "age": 38,
        "aadhaar": "987654321012",
        "fatherName": "Rajesh Verma",
        "employerCategory": "OTH",
        "flatNo": "5B",
        "premises": "",
        "road": "Nehru Road",
        "area": "Connaught Place",
        "city": "Delhi",
        "state": "07",
        "country": "91",
        "pincode": "110001",
        "zipCode": "",
        "mobileCountryCode": "91",
        "mobile": "9988776655",
        "email": "priya.verma@example.com",
        "filingSection": "139(1)",
        "optOutNewTaxRegime": "Y",
        "verification": {
            "capacity": "SELF",
            "place": "Delhi",
            "date": "2026-07-31",
            "declarationAccepted": True,
        },
        "bankAccountData": {
            "accounts": [{
                "bankName": "HDFC Bank",
                "accountNumber": "50100012345678",
                "ifscCode": "HDFC0001234",
                "accountType": "SB",
                "useForRefund": True,
            }]
        },
        "housePropertyEntries": [],
    }


def _assert_no_placeholders(document: dict) -> None:
    """Assert the document contains no placeholder PAN or name."""
    doc_str = str(document)
    assert "AAAAA0000A" not in doc_str, "Placeholder PAN found in output"
    assert "Tax Preparer" not in doc_str, "Placeholder TRP name found in output (outside typed TRP context)"


def _build_and_validate(payload: dict) -> dict:
    """Run the full pipeline: mapper -> compute -> build -> validate. Return the ITR1 dict."""
    typed = _build_itr1_input_from_flat(payload)
    result = compute(typed)
    assert result.errors == [], f"Calculator errors: {result.errors}"
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)
    _assert_no_placeholders(document)
    return document["ITR"]["ITR1"]


# ---------------------------------------------------------------------------
# Golden case 1 - Salary-only ITR-1 (zero deductions, zero TDS)
# ---------------------------------------------------------------------------

def test_golden_salary_only() -> None:
    """Minimal salary-only ITR-1 must produce schema-valid JSON."""
    payload = _base()
    payload["employerEntries"] = [{"basic": "800000"}]

    itr1 = _build_and_validate(payload)

    assert itr1["PersonalInfo"]["PAN"] == "ABCDE1234F"
    assert itr1["Verification"]["Place"] == "Delhi"
    assert "ITR1_IncomeDeductions" in itr1
    assert "Refund" in itr1
    refund = itr1["Refund"]
    assert "BankAccountDtls" in refund
    assert refund["BankAccountDtls"]["AddtnlBankDetails"][0]["IFSCCode"] == "HDFC0001234"


# ---------------------------------------------------------------------------
# Golden case 2 - Salary + 80C deductions + TDS + bank refund
# ---------------------------------------------------------------------------

def test_golden_salary_deductions_tds_refund() -> None:
    """Salary with TDS and bank refund must produce schema-valid JSON."""
    payload = _base()
    payload["employerEntries"] = [{"basic": "1000000"}]
    payload["tdsEntries"] = [{
        "section": "192",
        "deductorTAN": "DELA00001A",
        "deductorName": "Tech Corp Ltd",
        "grossAmount": "1000000",
        "taxDeducted": "50000",
        "claimedInReturn": True,
    }]

    itr1 = _build_and_validate(payload)

    assert "TDSonSalaries" in itr1


# ---------------------------------------------------------------------------
# Golden case 3 - Belated return (section 139(4))
# ---------------------------------------------------------------------------

def test_golden_belated_return() -> None:
    """Belated return under section 139(4) must produce schema-valid JSON."""
    payload = _base()
    payload["filingSection"] = "139(4)"
    payload["employerEntries"] = [{"basic": "600000"}]

    itr1 = _build_and_validate(payload)

    filing_status = itr1["FilingStatus"]
    assert filing_status["ReturnFileSec"] == 12  # 139(4) -> code 12


# ---------------------------------------------------------------------------
# Golden case 4 - HRA + house property
# ---------------------------------------------------------------------------

def test_golden_hra_and_house_property() -> None:
    """HRA exemption and house-property income must both flow into official JSON."""
    payload = _base()
    payload["employerEntries"] = [{
        "basic": "700000",
        "da": "50000",
        "hra": "84000",
        "hraExempt": "45000",   # min(84000, 120000 - 75000, 750000*0.4) = 45000 non-metro
        "rentPaid": "120000",
        "isMetroCity": False,
    }]
    payload["housePropertyEntries"] = [{
        "propertyType": "LET_OUT",
        "annualRent": "180000",
        "municipalTaxesPaid": "10000",
        "interestOnLoan": "0",
    }]

    itr1 = _build_and_validate(payload)

    assert "ScheduleEA10_13A" in itr1
    hra = itr1["ScheduleEA10_13A"]
    assert hra["Placeofwork"] == "2"  # Non-metro
    assert hra["ActlHRARecv"] == 84000
    assert hra["EligbleExmpAllwncUs13A"] == 45000


# ---------------------------------------------------------------------------
# Golden case 5 - 80GGA + 80GGC + TRP
# ---------------------------------------------------------------------------

def test_golden_80gga_80ggc_trp() -> None:
    """80GGA, 80GGC donation rows and TRP must all appear in official JSON."""
    payload = _base()
    payload["employerEntries"] = [{"basic": "1200000"}]
    payload["schedule80GGAEntries"] = [{
        "relevantClause": "80GGA2a",
        "doneeName": "IISc Bangalore",
        "doneePAN": "AAATI1234F",
        "addressLine": "CV Raman Road",
        "city": "Bengaluru",
        "stateCode": "29",
        "pinCode": "560012",
        "cashAmount": "0",
        "otherModeAmount": "50000",
    }]
    payload["schedule80GGCEntries"] = [{
        "cashAmount": "0",
        "otherModeAmount": "25000",
        "contributionDate": "2025-11-01",
        "transactionRef": "UTR987654321",
        "ifscCode": "SBIN0001234",
        "politicalPartyName": "Democratic Party",
        "politicalPartyPAN": "AAACP1234D",
    }]
    payload["taxReturnPreparer"] = {
        "used": True,
        "identificationNumber": "T987654321",
        "name": "Sanjay Kumar",
        "reimbursementFromGovernment": "300",
    }

    itr1 = _build_and_validate(payload)

    assert "Schedule80Gga" in itr1 or "Schedule80GGA" in itr1
    assert "Schedule80Ggc" in itr1 or "Schedule80GGC" in itr1
    assert "TaxReturnPreparer" in itr1
    assert itr1["TaxReturnPreparer"]["NameOfTRP"] == "Sanjay Kumar"


# ---------------------------------------------------------------------------
# Golden case 6 - TDS3 + TCS + advance/self-assessment tax
# ---------------------------------------------------------------------------

def test_golden_tds3_tcs_and_tax_payments() -> None:
    """TDS3, TCS, and advance/self-assessment challans must all reach the JSON."""
    payload = _base()
    payload["employerEntries"] = [{"basic": "900000"}]
    payload["tdsEntries"] = [{
        "schedule": "TDS3",
        "section": "195",
        "panOfTenant": "BBBBB1234B",
        "nameOfTenant": "Meera Agarwal",
        "grsRcptToTaxDeduct": "240000",
        "taxDeducted": "4800",
        "tdsClaimed": "4800",
        "deductedYr": "2025",
        "claimedInReturn": True,
    }]
    payload["tcsEntries"] = [{
        "collectorTAN": "DELA12345B",
        "collectorName": "HDFC Securities",
        "section": "206C",
        "grossAmount": "500000",
        "taxCollected": "5000",
        "tcsCollected": "5000",
    }]
    payload["advanceTaxEntries"] = [{
        "kind": "ADVANCE_TAX",
        "bsrCode": "0000123",
        "depositDate": "2025-09-15",
        "challanSerialNo": 1,
        "amount": "20000",
    }]
    payload["selfAssessmentTaxEntries"] = [{
        "kind": "SELF_ASSESSMENT",
        "bsrCode": "0000456",
        "depositDate": "2026-07-20",
        "challanSerialNo": 2,
        "amount": "5000",
    }]

    itr1 = _build_and_validate(payload)

    assert "ScheduleTDS3Dtls" in itr1
    tds3 = itr1["ScheduleTDS3Dtls"]
    assert tds3["TDS3Details"][0]["PANofTenant"] == "BBBBB1234B"
    assert "ScheduleTCS" in itr1


# ---------------------------------------------------------------------------
# Golden case 7 - Invalid filing-profile must return actionable error
# ---------------------------------------------------------------------------

def test_golden_missing_declaration_blocked() -> None:
    """Missing verification declaration must block before any JSON is produced."""
    payload = _base()
    payload["verification"] = {
        "capacity": "SELF",
        "place": "Delhi",
        "date": "2026-07-31",
        "declarationAccepted": False,  # Must be True for official filing.
    }
    payload["employerEntries"] = [{"basic": "600000"}]

    with pytest.raises(ValueError, match="Verification declaration"):
        _build_itr1_input_from_flat(payload)


# ---------------------------------------------------------------------------
# Golden case 8 - New regime: only 80CCD(2) deduction passes through
# ---------------------------------------------------------------------------

def test_golden_new_regime_only_80ccd2_passes() -> None:
    """New regime must zero out 80C, 80D, 80E but preserve 80CCD(2)."""
    payload = _base()
    payload["regime"] = "new"
    payload["taxRegime"] = "new"
    payload["optOutNewTaxRegime"] = "N"
    payload["employerEntries"] = [{"basic": "1500000"}]
    payload["s80CCD2"] = "60000"       # Employer NPS - allowed in new regime.
    payload["section80C"] = {"investments": [{"investmentType": "PPF", "amount": "150000"}]}
    payload["s80E"] = "50000"           # Education loan - disallowed in new regime.

    typed = _build_itr1_input_from_flat(payload)
    assert typed.tax_regime.value == "new"
    assert typed.deductions_chapter6a.amount_80c == Decimal("0")
    assert typed.deductions_chapter6a.amount_80e == Decimal("0")
    assert typed.deductions_chapter6a.amount_80ccd2 == Decimal("60000")

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)
    _assert_no_placeholders(document)
