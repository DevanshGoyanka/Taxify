"""Regression tests for flat-draft to canonical ITR-1 filing-profile mapping."""

from decimal import Decimal

import pytest

from app.engine.calculators.itr1 import compute
from app.engine.filing_gateway import _build_itr1_input_from_flat, _validate_itr1_cross_fields
from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr1_schema import validate_itr1_json


def _payload() -> dict[str, object]:
    """Create a minimal complete flat ITR-1 draft for official generation."""
    return {
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "assessmentYear": "2026-27",
        "regime": "OLD",
        "taxRegime": "OLD",
        "pan": "ABCDE1234F",
        "firstName": "Asha",
        "middleName": "Rani",
        "surnameOrOrgName": "Sharma",
        "name": "Asha Rani Sharma",
        "dob": "1990-01-15",
        "age": 36,
        "aadhaar": "123456789012",
        "fatherName": "Ramesh Sharma",
        "employerCategory": "OTH",
        "flatNo": "12A",
        "premises": "",
        "road": "MG Road",
        "area": "Central Colony",
        "city": "Delhi",
        "state": "07",
        "country": "91",
        "pincode": "110001",
        "zipCode": "",
        "mobileCountryCode": "91",
        "mobile": "9876543210",
        "email": "asha.sharma@example.com",
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
                "bankName": "State Bank of India",
                "accountNumber": "1234567890",
                "ifscCode": "SBIN0001234",
                "accountType": "SB",
                "useForRefund": True,
            }]
        },
        "employerEntries": [{"basic": "600000"}],
        "housePropertyEntries": [],
    }


def test_flat_mapper_builds_real_filing_profile_and_schema_valid_json() -> None:
    """Official generation must use draft identity, never placeholder identity."""
    typed = _build_itr1_input_from_flat(_payload())

    assert typed.filing_profile is not None
    assert typed.filing_profile.pan == "ABCDE1234F"
    assert typed.filing_profile.surname == "Sharma"
    assert typed.filing_profile.primary_address.city_or_town_or_district == "Delhi"
    assert typed.filing_profile.verification_place == "Delhi"
    assert typed.filing_profile.return_file_section == 11
    assert len(typed.bank_accounts) == 1
    assert typed.bank_accounts[0].is_primary is True

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert itr1["PersonalInfo"]["PAN"] == "ABCDE1234F"
    assert itr1["Verification"]["Place"] == "Delhi"
    assert "AAAAA0000A" not in str(document)


def test_flat_mapper_rejects_missing_verification_declaration() -> None:
    """Official JSON mapping must reject an unaccepted declaration."""
    payload = _payload()
    payload["verification"] = {"capacity": "SELF", "place": "Delhi", "declarationAccepted": False}

    with pytest.raises(ValueError, match="Verification declaration"):
        _build_itr1_input_from_flat(payload)


def test_flat_mapper_rejects_unsupported_itr1_representative_verification() -> None:
    """Representative ITR-1 generation must block rather than fabricate Capacity."""
    payload = _payload()
    payload["verification"] = {"capacity": "REPRESENTATIVE", "place": "Delhi", "declarationAccepted": True}

    with pytest.raises(ValueError, match="Representative verification"):
        _build_itr1_input_from_flat(payload)


def test_flat_mapper_rejects_unsupported_filing_section() -> None:
    """Unsupported official filing sections must fail explicitly until implemented."""
    payload = _payload()
    payload["filingSection"] = "139(5)"

    with pytest.raises(ValueError, match=r"139\(1\) and 139\(4\)"):
        _build_itr1_input_from_flat(payload)


def test_flat_mapper_rejects_mismatched_filing_label_and_official_code() -> None:
    """The presentation label and official numeric filing code must agree."""
    payload = _payload()
    payload["filingSection"] = "139(1)"
    payload["returnFileSectionCode"] = 12

    with pytest.raises(ValueError, match="must describe the same return section"):
        _build_itr1_input_from_flat(payload)


def test_new_regime_excludes_stale_old_regime_deduction_values() -> None:
    """Saved old-regime values stay auditable but cannot affect new-regime input."""
    payload = _payload()
    payload.update({
        "regime": "new",
        "taxRegime": "new",
        "optOutNewTaxRegime": "N",
        "section80C": {"investments": [{"amount": "150000"}]},
        "section80D": {"selfFamily": {"policies": [{"premiumAmount": "25000"}]}},
        "s80CCD1B": "50000",
        "s80CCD2": "40000",
        "s80E": "30000",
        "s80TTA": "10000",
        "s80G": "5000",
    })

    typed = _build_itr1_input_from_flat(payload)
    deductions = typed.deductions_chapter6a

    assert typed.tax_regime.value == "new"
    assert deductions.amount_80c == Decimal("0")
    assert deductions.amount_80ccd1b == Decimal("0")
    assert deductions.amount_80d_self_family == Decimal("0")
    assert deductions.amount_80e == Decimal("0")
    assert deductions.amount_80tta == Decimal("0")
    assert deductions.amount_80g == Decimal("0")
    assert deductions.amount_80ccd2 == Decimal("40000")


def test_flat_mapper_maps_schedule_80gga_rows_to_official_json() -> None:
    """Schedule 80GGA evidence rows must flow into typed input and official JSON."""
    payload = _payload()
    payload["schedule80GGAEntries"] = [{
        "relevantClause": "80GGA2a",
        "doneeName": "Indian Institute of Science",
        "doneePAN": "AAATI1234F",
        "addressLine": "C V Raman Road",
        "city": "Bengaluru",
        "stateCode": "29",
        "pinCode": "560012",
        "cashAmount": "0",
        "otherModeAmount": "25000",
    }]

    typed = _build_itr1_input_from_flat(payload)

    assert typed.schedule_80gga is not None
    assert len(typed.schedule_80gga.donations) == 1
    donation = typed.schedule_80gga.donations[0]
    assert donation.donee_pan == "AAATI1234F"
    assert donation.other_mode_amount == Decimal("25000")
    assert typed.deductions_chapter6a.amount_80gga == Decimal("25000")

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert "Schedule80GGA" in itr1


def test_flat_mapper_maps_schedule_80ggc_rows_to_official_json() -> None:
    """Schedule 80GGC political contribution rows must flow into official JSON."""
    payload = _payload()
    payload["schedule80GGCEntries"] = [{
        "cashAmount": "0",
        "otherModeAmount": "10000",
        "contributionDate": "2025-11-15",
        "transactionRef": "UTR123456789",
        "ifscCode": "HDFC0001234",
        "politicalPartyName": "Example Party",
        "politicalPartyPAN": "AAACP1234D",
    }]

    typed = _build_itr1_input_from_flat(payload)

    assert typed.schedule_80ggc is not None
    assert len(typed.schedule_80ggc.contributions) == 1
    contribution = typed.schedule_80ggc.contributions[0]
    assert contribution.political_party_pan == "AAACP1234D"
    assert contribution.other_mode_amount == Decimal("10000")
    assert typed.deductions_chapter6a.amount_80ggc == Decimal("10000")

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert "Schedule80GGC" in itr1


def test_flat_mapper_maps_tax_return_preparer_to_official_json() -> None:
    """TRP details must appear in the official JSON when used is true."""
    payload = _payload()
    payload["taxReturnPreparer"] = {
        "used": True,
        "identificationNumber": "T123456789",
        "name": "Ravi Kumar",
        "reimbursementFromGovernment": "500",
    }

    typed = _build_itr1_input_from_flat(payload)

    assert typed.tax_return_preparer is not None
    assert typed.tax_return_preparer.identification_number == "T123456789"
    assert typed.tax_return_preparer.name == "Ravi Kumar"
    assert typed.tax_return_preparer.reimbursement_from_government == Decimal("500")

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert itr1["TaxReturnPreparer"]["IdentificationNoOfTRP"] == "T123456789"
    assert itr1["TaxReturnPreparer"]["NameOfTRP"] == "Ravi Kumar"
    assert itr1["TaxReturnPreparer"]["ReImbFrmGov"] == 500


def test_flat_mapper_omits_tax_return_preparer_when_not_used() -> None:
    """The TaxReturnPreparer node must be absent when no TRP is involved."""
    payload = _payload()

    typed = _build_itr1_input_from_flat(payload)
    assert typed.tax_return_preparer is None

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert "TaxReturnPreparer" not in itr1


def test_flat_mapper_maps_tds3_rows_to_schedule_tds3_dtls() -> None:
    """TDS3 tenant rows must flow into ScheduleTDS3Dtls in the official JSON."""
    payload = _payload()
    payload["tdsEntries"] = [{
        "schedule": "TDS3",
        "section": "195",
        "panOfTenant": "ABCDE1234F",
        "nameOfTenant": "Ravi Kumar",
        "grsRcptToTaxDeduct": "120000",
        "taxDeducted": "3000",
        "tdsClaimed": "3000",
        "deductedYr": "2025",
        "claimedInReturn": True,
    }]

    typed = _build_itr1_input_from_flat(payload)

    assert typed.tds3_entries is not None
    assert len(typed.tds3_entries) == 1
    entry = typed.tds3_entries[0]
    assert entry.tenant_pan == "ABCDE1234F"
    assert entry.tenant_name == "Ravi Kumar"
    assert entry.tds_deducted == Decimal("3000")
    assert entry.tds_claimed == Decimal("3000")
    assert entry.tds_section == "195"

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert "ScheduleTDS3Dtls" in itr1
    tds3 = itr1["ScheduleTDS3Dtls"]
    assert tds3["TotalTDS3Details"] == 3000
    assert tds3["TDS3Details"][0]["PANofTenant"] == "ABCDE1234F"
    assert tds3["TDS3Details"][0]["NameOfTenant"] == "Ravi Kumar"


def test_flat_mapper_maps_multiple_bank_accounts_with_refund_selection() -> None:
    """All bank accounts must reach the official JSON; exactly one is refund-selected."""
    payload = _payload()
    payload["bankAccountData"] = {
        "accounts": [
            {
                "bankName": "State Bank of India",
                "accountNumber": "1234567890",
                "ifscCode": "SBIN0001234",
                "accountType": "SB",
                "useForRefund": True,
            },
            {
                "bankName": "HDFC Bank",
                "accountNumber": "9876543210",
                "ifscCode": "HDFC0001234",
                "accountType": "CA",
                "useForRefund": False,
            },
        ]
    }

    typed = _build_itr1_input_from_flat(payload)
    assert len(typed.bank_accounts) == 2
    primary_accounts = [a for a in typed.bank_accounts if a.is_primary]
    assert len(primary_accounts) == 1
    assert primary_accounts[0].account_number == "1234567890"

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    refund = document["ITR"]["ITR1"]["Refund"]
    bank_details = refund["BankAccountDtls"]["AddtnlBankDetails"]
    assert len(bank_details) == 2
    refund_accounts = [b for b in bank_details if b["UseForRefund"] == "true"]
    assert len(refund_accounts) == 1


def test_flat_mapper_rejects_missing_refund_bank_selection() -> None:
    """Filing JSON generation must block when no bank account is marked for refund."""
    payload = _payload()
    payload["bankAccountData"] = {
        "accounts": [{
            "bankName": "State Bank of India",
            "accountNumber": "1234567890",
            "ifscCode": "SBIN0001234",
            "accountType": "SB",
            "useForRefund": False,
        }]
    }

    typed = _build_itr1_input_from_flat(payload)
    result = compute(typed)
    with pytest.raises(ValueError, match="Exactly one bank account"):
        build_itr1_json(result, typed)


def test_flat_mapper_maps_hra_details_to_schedule_ea10_13a() -> None:
    """HRA evidence must flow into ScheduleEA10_13A in the official JSON."""
    payload = _payload()
    payload["employerEntries"] = [{
        "basic": "600000",
        "da": "50000",
        "hra": "100000",
        "hraExempt": "55000",
        "rentPaid": "120000",
        "isMetroCity": True,
    }]

    typed = _build_itr1_input_from_flat(payload)

    assert typed.hra_details is not None
    assert typed.hra_details.actual_hra_received == Decimal("100000")
    assert typed.hra_details.rent_paid == Decimal("120000")
    assert typed.hra_details.salary_for_hra == Decimal("600000")
    assert typed.hra_details.dearness_allowance == Decimal("50000")
    assert typed.hra_details.is_metro_city is True

    result = compute(typed)
    assert result.errors == []
    document = build_itr1_json(result, typed)
    validate_itr1_json(document)

    itr1 = document["ITR"]["ITR1"]
    assert "ScheduleEA10_13A" in itr1
    hra = itr1["ScheduleEA10_13A"]
    assert hra["Placeofwork"] == "1"
    assert hra["ActlHRARecv"] == 100000
    assert hra["ActlRentPaid"] == 120000
    assert hra["BasicSalary"] == 600000
    assert hra["DearnessAllwnc"] == 50000


def test_cross_field_rejects_donee_pan_equal_to_taxpayer_pan() -> None:
    """A donee PAN matching the taxpayer PAN must be blocked."""
    payload = _payload()
    payload["donationEntries"] = [{
        "category": "50_APPROVAL_REQD",
        "doneeName": "Self Trust",
        "doneePAN": "ABCDE1234F",  # Same as taxpayer PAN.
        "donationAmtOtherMode": "5000",
    }]

    typed = _build_itr1_input_from_flat(payload)
    errors = _validate_itr1_cross_fields(typed)
    assert any("must not equal the taxpayer PAN" in e for e in errors)


def test_cross_field_rejects_80ccd1b_without_pran() -> None:
    """A positive 80CCD(1B) claim without a PRAN must be blocked."""
    payload = _payload()
    payload["s80CCD1B"] = "50000"

    typed = _build_itr1_input_from_flat(payload)
    errors = _validate_itr1_cross_fields(typed)
    assert any("PRAN" in e for e in errors)


def test_cross_field_accepts_80ccd1b_with_pran() -> None:
    """A positive 80CCD(1B) claim with a PRAN must pass."""
    payload = _payload()
    payload["s80CCD1B"] = "50000"
    payload["s80CCD1B_PRAN"] = "123456789012"

    typed = _build_itr1_input_from_flat(payload)
    errors = _validate_itr1_cross_fields(typed)
    assert not any("PRAN" in e for e in errors)


def test_cross_field_rejects_tds_claimed_exceeding_deducted() -> None:
    """TDS2 claimed credit exceeding the deducted amount must be blocked by the cross-field validator."""
    from app.schemas.itr1 import TDS2Entry
    from decimal import Decimal as D

    payload = _payload()
    typed = _build_itr1_input_from_flat(payload)

    # Inject a TDS2 entry directly with claimed > deducted to test the rule.
    bad_entry = TDS2Entry(
        deductor_tan="DELA00001A",
        tds_section="94A",
        gross_amount=D("100000"),
        tds_deducted=D("5000"),
        tds_claimed_this_year=D("8000"),
    )
    typed = typed.model_copy(update={"tds2_entries": [bad_entry]})
    errors = _validate_itr1_cross_fields(typed)
    assert any("exceeds the deducted amount" in e for e in errors)
