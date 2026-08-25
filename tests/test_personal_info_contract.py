"""Contract tests for the Personal Info field pipeline.

Verifies that every entered Personal Info field survives the full flow:
  flat payload → filing gateway → ITR1FilingProfile → ITD JSON builder → CBDT JSON

This is the production-readiness gate: no entered statutory field may be
silently replaced with a default or dropped during JSON generation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.engine.filing_gateway import generate_filing_artifact
from app.schemas.itr1 import FilingAddress, ITR1FilingProfile, SeventhProvisoDetails


# ---------------------------------------------------------------------------
# Minimal valid flat payload — extended per test.
# ---------------------------------------------------------------------------

BASE_PAYLOAD: dict[str, Any] = {
    "assessmentYear": "2026-27",
    "form": "ITR-1",
    "pan": "ABCDE1234F",
    "firstName": "RAHUL",
    "middleName": "KUMAR",
    "surnameOrOrgName": "SHARMA",
    "dob": "1990-05-15",
    "employerCategory": "OTH",
    "fatherName": "SURESH SHARMA",
    "flatNo": "12A",
    "premises": "Rose Apartments",
    "road": "MG Road",
    "area": "Bandra West",
    "city": "Mumbai",
    "state": "27",
    "country": "91",
    "pincode": "400050",
    "mobileCountryCode": "91",
    "mobile": "9876543210",
    "email": "rahul@example.com",
    "filingSection": "139(1)",
    # A return filed under 139(1) declares a filing date on or before the due
    # date; without one the fixture is judged against the day the suite runs.
    "verification": {"place": "Mumbai", "date": "2026-07-31", "declarationAccepted": True, "capacity": "SELF"},
    "employerEntries": [{"basic": 800000, "da": 0, "hra": 0, "bonus": 0, "perquisites": 0, "profitsInLieu": 0, "allowances": 0, "tdsS192": 50000}],
    "bankAccountData": {"accounts": [
        {
            "accountNumber": "12345678901",
            "ifscCode": "HDFC0001234",
            "bankName": "HDFC Bank",
            "accountType": "SAVINGS",
            "useForRefund": True,
        }
    ]},
}


def _generate(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the full filing gateway and return the official CBDT JSON."""
    # filing_gateway reads user/db but they're only used for persistence;
    # the compute path works with None when include_official_json=True.
    result = generate_filing_artifact(
        flat_draft=payload,
        user=None,
        db=None,
        include_official_json=True,
    )
    assert result.has_official_json, f"Gateway did not produce JSON: {result.validation_errors}"
    return result.official_json


def _personal_info(json_doc: dict[str, Any]) -> dict[str, Any]:
    return json_doc["ITR"]["ITR1"]["PersonalInfo"]


def _address(json_doc: dict[str, Any]) -> dict[str, Any]:
    return _personal_info(json_doc)["Address"]


def _filing_status(json_doc: dict[str, Any]) -> dict[str, Any]:
    return json_doc["ITR"]["ITR1"]["FilingStatus"]


# ---------------------------------------------------------------------------
# Secondary mobile
# ---------------------------------------------------------------------------

class TestSecondaryMobile:
    """Secondary mobile must flow from flat payload through to CBDT JSON."""

    def test_secondary_mobile_with_explicit_country_code(self) -> None:
        """When both secondary country code and number are provided, both survive."""
        payload = {
            **BASE_PAYLOAD,
            "secondaryMobileCountryCode": "91",
            "secondaryMobile": "9403556603",
        }
        json_doc = _generate(payload)
        addr = _address(json_doc)
        assert addr["CountryCodeMobileNoSec"] == 91
        assert addr["MobileNoSec"] == 9403556603

    def test_secondary_mobile_inherits_primary_country_code(self) -> None:
        """When secondary number is given but country code is blank, inherit primary."""
        payload = {
            **BASE_PAYLOAD,
            "secondaryMobile": "9403556603",
            # secondaryMobileCountryCode intentionally omitted
        }
        json_doc = _generate(payload)
        addr = _address(json_doc)
        assert addr["CountryCodeMobileNoSec"] == 91, (
            "Secondary country code must inherit primary (91) when blank"
        )
        assert addr["MobileNoSec"] == 9403556603

    def test_no_secondary_mobile_emits_zero(self) -> None:
        """When no secondary mobile is entered, CBDT keys are present and 0."""
        payload = {**BASE_PAYLOAD}
        json_doc = _generate(payload)
        addr = _address(json_doc)
        assert addr["CountryCodeMobileNoSec"] == 0
        assert addr["MobileNoSec"] == 0
        # EmailAddressSec must be absent when no secondary email entered
        assert "EmailAddressSec" not in addr

    def test_secondary_mobile_country_code_without_number_fails(self) -> None:
        """A secondary country code without a number should not produce a stale value."""
        payload = {
            **BASE_PAYLOAD,
            "secondaryMobileCountryCode": "91",
            # secondaryMobile intentionally omitted
        }
        json_doc = _generate(payload)
        addr = _address(json_doc)
        # No number → no secondary mobile emitted (country code defaults to 0)
        assert addr["CountryCodeMobileNoSec"] == 0
        assert addr["MobileNoSec"] == 0


# ---------------------------------------------------------------------------
# Secondary email
# ---------------------------------------------------------------------------

class TestSecondaryEmail:
    """Secondary email must flow through and be omitted when blank."""

    def test_secondary_email_present(self) -> None:
        payload = {**BASE_PAYLOAD, "secondaryEmail": "secondary@example.com"}
        json_doc = _generate(payload)
        addr = _address(json_doc)
        assert addr["EmailAddressSec"] == "secondary@example.com"

    def test_secondary_email_absent(self) -> None:
        payload = {**BASE_PAYLOAD}
        json_doc = _generate(payload)
        addr = _address(json_doc)
        assert "EmailAddressSec" not in addr


# ---------------------------------------------------------------------------
# FilingStatus: seventh-proviso and opt-out
# ---------------------------------------------------------------------------

class TestFilingStatusDeclarations:
    """FilingStatus must emit entered declarations, not hardcoded defaults."""

    def test_no_seventh_proviso_emits_N_flag_only(self) -> None:
        payload = {**BASE_PAYLOAD}
        json_doc = _generate(payload)
        fs = _filing_status(json_doc)
        assert fs["SeventhProvisio139"] == "N"
        # Amount keys must be absent when flag is N (schema minimum 200000)
        assert "AmtSeventhProvisio139ii" not in fs
        assert "AmtSeventhProvisio139iii" not in fs

    def test_foreign_travel_declaration_emits_amount(self) -> None:
        payload = {
            **BASE_PAYLOAD,
            "seventhProviso": {
                "foreignTravel": True,
                "foreignTravelAmount": 350000,
            },
        }
        json_doc = _generate(payload)
        fs = _filing_status(json_doc)
        assert fs["SeventhProvisio139"] == "Y"
        assert fs["IncrExpAggAmt2LkTrvFrgnCntryFlg"] == "Y"
        assert fs["AmtSeventhProvisio139ii"] == 350000

    def test_electricity_expenditure_declaration_emits_amount(self) -> None:
        payload = {
            **BASE_PAYLOAD,
            "seventhProviso": {
                "electricityExpenditure": True,
                "electricityExpenditureAmount": 150000,
            },
        }
        json_doc = _generate(payload)
        fs = _filing_status(json_doc)
        assert fs["IncrExpAggAmt1LkElctrctyPrYrFlg"] == "Y"
        assert fs["AmtSeventhProvisio139iii"] == 150000

    def test_new_regime_emits_N_opt_out(self) -> None:
        payload = {**BASE_PAYLOAD, "taxRegime": "NEW"}
        json_doc = _generate(payload)
        fs = _filing_status(json_doc)
        assert fs["OptOutNewTaxRegime"] == "N"

    def test_old_regime_emits_Y_opt_out(self) -> None:
        payload = {**BASE_PAYLOAD, "taxRegime": "OLD"}
        json_doc = _generate(payload)
        fs = _filing_status(json_doc)
        assert fs["OptOutNewTaxRegime"] == "Y"


# ---------------------------------------------------------------------------
# Aadhaar
# ---------------------------------------------------------------------------

class TestAadhaar:
    """Aadhaar must be emitted when provided and omitted when absent."""

    def test_aadhaar_present(self) -> None:
        payload = {**BASE_PAYLOAD, "aadhaar": "123456789012"}
        json_doc = _generate(payload)
        pi = _personal_info(json_doc)
        assert pi["AadhaarCardNo"] == "123456789012"

    def test_aadhaar_absent(self) -> None:
        payload = {**BASE_PAYLOAD}
        json_doc = _generate(payload)
        pi = _personal_info(json_doc)
        assert "AadhaarCardNo" not in pi
