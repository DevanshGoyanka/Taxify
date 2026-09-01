"""
Phase 1 tests — canonical ReturnDraft schema round-trip + /v2 router.

These tests verify the guarantees the new typed contract must hold:
  1. Empty draft → JSON → draft (exact round-trip).
  2. Rich draft (employers, TDS, challans, banks) round-trips.
  3. extra="forbid" rejects unknown keys at top-level AND nested.
  4. Money is Decimal (no float precision loss).
  5. draft_from_client_seed seeds personal info from a Client master.

Run: pytest tests/test_return_draft_schema.py -v
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.schemas.return_draft import (
    AlternateAddress,
    BankAccount,
    CapitalGainsSchedule,
    Employer,
    DividendIncome,
    ImmovableAssetGain,
    Investment80C,
    InterestIncome,
    ReturnDraft,
    Scrip112A,
    SeventhProviso,
    TdsCredit,
    TaxChallan,
    VdaEntry,
    create_empty_draft,
    draft_from_client_seed,
)


class _FakeClient:
    """Minimal stand-in for app.db.models.Client for seed tests."""

    def __init__(self, name, pan, email, mobile, dob):
        self.name = name
        self.pan = pan
        self.email = email
        self.mobile = mobile
        self.dob = dob


# ── Round-trip ──────────────────────────────────────────────────────────────

def test_empty_draft_round_trip():
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    payload = draft.model_dump_json()
    restored = ReturnDraft.model_validate(json.loads(payload))
    assert restored.assessmentYear == "2026-27"
    assert restored.form == "ITR-1"
    assert restored.regime == "new"
    assert restored.employers == []
    assert restored.taxes.tds == []
    assert restored.deductions.section80C == []


def test_rich_draft_round_trip():
    draft = create_empty_draft("2026-27", "ITR-1", "old")
    draft.employers = [Employer(
        id="e1", employerName="Acme", employerTAN="MUMA12345B",
        basic=Decimal("1200000"), da=Decimal("12000"), hra=Decimal("60000"),
        perquisites=Decimal("5000"), professionalTax=Decimal("2400"),
        tdsDeducted=Decimal("80000"),
    )]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("15000"),
    )]
    draft.otherSources.dividends = [DividendIncome(
        id="d1", section="194", grossAmount=Decimal("10000"),
        tdsDeducted=Decimal("1000"),
    )]
    draft.deductions.section80C = [Investment80C(
        id="c1", investmentType="EPF", amount=Decimal("50000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme",
        deductorTAN="MUMA12345B", taxDeducted=Decimal("80000"),
    )]
    draft.taxes.challans = [TaxChallan(
        id="ch1", kind="SELF_ASSESSMENT", bsrCode="1234567",
        depositDate="2026-04-10", challanSerialNo=1, amount=Decimal("5000"),
    )]
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="SBI", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]

    payload = json.loads(draft.model_dump_json())
    restored = ReturnDraft.model_validate(payload)

    assert len(restored.employers) == 1
    assert restored.employers[0].basic == Decimal("1200000")
    assert restored.employers[0].tdsDeducted == Decimal("80000")
    assert len(restored.otherSources.interest) == 1
    assert restored.otherSources.interest[0].grossAmount == Decimal("15000")
    assert len(restored.otherSources.dividends) == 1
    assert restored.otherSources.dividends[0].tdsDeducted == Decimal("1000")
    assert len(restored.deductions.section80C) == 1
    assert restored.deductions.section80C[0].amount == Decimal("50000")
    assert len(restored.taxes.tds) == 1
    assert restored.taxes.tds[0].taxDeducted == Decimal("80000")
    assert len(restored.taxes.challans) == 1
    assert restored.taxes.challans[0].amount == Decimal("5000")
    assert len(restored.bankAccounts) == 1
    assert restored.bankAccounts[0].accountType == "SB"


def test_official_personal_fields_are_additive_and_round_trip():
    draft = create_empty_draft("2026-27")
    draft.personal.firstName = "Rahul"
    draft.personal.middleName = "Kumar"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.fatherName = "Mohan Sharma"
    draft.personal.aadhaar = "123412341234"
    draft.personal.flatNo = "12A"
    draft.personal.residenceName = "Taxify Heights"
    draft.personal.roadOrStreet = "MG Road"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    restored = ReturnDraft.model_validate_json(draft.model_dump_json())
    assert restored.personal.firstName == "Rahul"
    assert restored.personal.surnameOrOrgName == "Sharma"
    assert restored.personal.fatherName == "Mohan Sharma"
    assert restored.personal.pinCode == "110001"


def test_official_personal_fields_default_without_breaking_old_drafts():
    draft = ReturnDraft.model_validate({"assessmentYear": "2026-27", "personal": {"name": "Rahul"}})
    assert draft.personal.name == "Rahul"
    assert draft.personal.firstName == ""
    assert draft.personal.fatherName == ""
    assert draft.personal.countryCode == "91"


# ── extra="forbid" ───────────────────────────────────────────────────────────

def test_rejects_unknown_top_level_key():
    with pytest.raises(Exception):
        ReturnDraft.model_validate({
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "bogusLegacyScalar": 123,  # must be rejected
        })


def test_rejects_unknown_nested_key():
    with pytest.raises(Exception):
        ReturnDraft.model_validate({
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "employers": [{"id": "e1", "hraReceived": 5000}],  # alias, must be rejected
        })


def test_rejects_unknown_interest_key():
    with pytest.raises(Exception):
        ReturnDraft.model_validate({
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "otherSources": {
                "interest": [{"id": "i1", "itdTag": "SAVINGS_BANK"}],  # alias, rejected
            },
        })


# ── Decimal precision ─────────────────────────────────────────────────────────

def test_money_is_decimal_not_float():
    draft = create_empty_draft("2026-27")
    draft.employers = [Employer(id="e1", basic=Decimal("123456.78"))]
    payload = json.loads(draft.model_dump_json())
    # JSON serializes Decimal as string "123456.78" — no float rounding.
    assert payload["employers"][0]["basic"] == "123456.78"
    restored = ReturnDraft.model_validate(payload)
    assert restored.employers[0].basic == Decimal("123456.78")


# ── Client seed ───────────────────────────────────────────────────────────────

def test_draft_from_client_seed():
    client = _FakeClient(
        name="Rahul", pan="ABCDE1234F", email="r@example.com",
        mobile="9876543210", dob="1990-01-15",
    )
    draft = draft_from_client_seed(client, "2026-27")
    assert draft.assessmentYear == "2026-27"
    assert draft.form == "ITR-1"
    assert draft.personal.name == "Rahul"
    assert draft.personal.pan == "ABCDE1234F"
    assert draft.personal.email == "r@example.com"
    assert draft.personal.mobile == "9876543210"
    assert draft.personal.dateOfBirth == "1990-01-15"
    assert draft.employers == []
    assert draft.taxes.tds == []


# ── Phase 1: additive ITR-4 fields (must not break ITR-1) ────────────────────

def test_empty_itr4_draft_validates():
    """An empty ITR-4 draft validates with default additive fields."""
    draft = create_empty_draft("2026-27", "ITR-4", "new")
    payload = draft.model_dump_json()
    restored = ReturnDraft.model_validate_json(payload)
    assert restored.form == "ITR-4"
    assert restored.personal.age == 30
    assert restored.personal.assesseeStatus == "I"
    assert restored.personal.employerCategory == ""
    assert restored.personal.landlineStdCode == "0"
    assert restored.personal.landlinePhoneNo == "0"
    assert restored.personal.secondaryAddressDifferent is False
    assert restored.personal.alternateAddress is None
    assert restored.filing.form10IEAAcknowledgement == ""
    assert restored.filing.form10IEADate is None
    assert restored.filing.seventhProviso.foreignTravel is False


def test_additive_itr4_fields_round_trip():
    """Populated ITR-4 additive fields survive a JSON round-trip exactly."""
    draft = create_empty_draft("2026-27", "ITR-4", "old")
    draft.personal.age = 65
    draft.personal.assesseeStatus = "H"
    draft.personal.employerCategory = "PSU"
    draft.personal.landlineStdCode = "011"
    draft.personal.landlinePhoneNo = "2345678"
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="5B", cityOrTownOrDistrict="Mumbai",
        stateCode="27", pinCode="400001",
    )
    draft.filing.form10IEAAcknowledgement = "123456789012345"
    draft.filing.form10IEADate = "2026-04-15"
    draft.filing.seventhProviso = SeventhProviso(
        foreignTravel=True, foreignTravelAmount=Decimal("250000"),
        electricityExpenditure=False,
    )
    restored = ReturnDraft.model_validate_json(draft.model_dump_json())
    assert restored.personal.age == 65
    assert restored.personal.assesseeStatus == "H"
    assert restored.personal.employerCategory == "PSU"
    assert restored.personal.landlineStdCode == "011"
    assert restored.personal.landlinePhoneNo == "2345678"
    assert restored.personal.secondaryAddressDifferent is True
    assert restored.personal.alternateAddress is not None
    assert restored.personal.alternateAddress.cityOrTownOrDistrict == "Mumbai"
    assert restored.personal.alternateAddress.pinCode == "400001"
    assert restored.filing.form10IEAAcknowledgement == "123456789012345"
    assert restored.filing.form10IEADate == "2026-04-15"
    assert restored.filing.seventhProviso.foreignTravel is True
    assert restored.filing.seventhProviso.foreignTravelAmount == Decimal("250000")


def test_itr1_draft_without_additive_fields_still_validates():
    """Regression: an ITR-1 draft with only ITR-1 personal fields still works."""
    draft = ReturnDraft.model_validate({
        "assessmentYear": "2026-27", "form": "ITR-1",
        "personal": {"name": "Rahul", "pan": "ABCDE1234F", "age": 30},
    })
    assert draft.personal.assesseeStatus == "I"
    assert draft.personal.employerCategory == ""
    assert draft.filing.seventhProviso.foreignTravel is False


# ── ITR-2/3 plan Phase 1: typed capitalGainsSchedule ─────────────────────────
# Mirrors frontend/src/domain/returns/types.ts::CapitalGainsSchedule exactly
# (Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md Phase 1).

def test_empty_draft_has_typed_empty_capital_gains_schedule():
    """The default CapitalGainsSchedule is a real typed instance, not a dict."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    assert isinstance(draft.capitalGainsSchedule, CapitalGainsSchedule)
    assert draft.capitalGainsSchedule.simplified112A.totalSaleConsideration == Decimal("0")
    assert draft.capitalGainsSchedule.schedule112A == []
    assert draft.capitalGainsSchedule.stEquity == []
    assert draft.capitalGainsSchedule.stUnutilizedFlag == "N"


def test_capital_gains_schedule_round_trips_typed_and_generic_rows():
    """Typed sub-arrays (112A, VDA, immovable) and generic JsonRow[] fields
    both survive a full JSON round-trip losslessly."""
    draft = create_empty_draft("2026-27", "ITR-2", "new")
    draft.capitalGainsSchedule = CapitalGainsSchedule(
        simplified112A={"totalSaleConsideration": Decimal("500000"), "totalCostAcquisition": Decimal("300000")},
        schedule112A=[Scrip112A(
            id="s1", isin="INE001A01036", name="Reliance", quantity=Decimal("100"),
            salePricePerUnit=Decimal("2500"), totalSaleValue=Decimal("250000"),
            costWithoutIndexation=Decimal("200000"), acquisitionCost=Decimal("200000"),
        )],
        vda=[VdaEntry(
            id="v1", dateOfAcquisition="2025-01-01", dateOfTransfer="2025-06-01",
            head="CG", acquisitionCost=Decimal("10000"), consideration=Decimal("15000"),
        )],
        ltImmovable=[ImmovableAssetGain(
            id="p1", dateOfSale="2025-12-01", fullConsideration=Decimal("8000000"),
            acquisitionCost=Decimal("3000000"), transferExpenses=Decimal("50000"),
        )],
        # Generic JsonRow[]-equivalent field — arbitrary keys must pass through
        # untouched (matches the frontend's deliberately-untyped scope).
        stEquity=[{"isin": "INE002A01018", "grossGain": 5000, "customField": "x"}],
    )
    restored = ReturnDraft.model_validate_json(draft.model_dump_json())
    cg = restored.capitalGainsSchedule
    assert cg.simplified112A.totalSaleConsideration == Decimal("500000")
    assert len(cg.schedule112A) == 1
    assert cg.schedule112A[0].isin == "INE001A01036"
    assert len(cg.vda) == 1
    assert cg.vda[0].head == "CG"
    assert len(cg.ltImmovable) == 1
    assert cg.ltImmovable[0].fullConsideration == Decimal("8000000")
    assert cg.stEquity == [{"isin": "INE002A01018", "grossGain": 5000, "customField": "x"}]


def test_capital_gains_schedule_rejects_unknown_key():
    """extra='forbid' still holds on the typed CG schedule itself."""
    with pytest.raises(Exception):
        ReturnDraft.model_validate({
            "assessmentYear": "2026-27", "form": "ITR-2",
            "capitalGainsSchedule": {"bogusField": 123},
        })


def test_capital_gains_schedule_rejects_unknown_key_in_typed_subarray():
    """extra='forbid' also holds on typed sub-array elements like Scrip112A."""
    with pytest.raises(Exception):
        ReturnDraft.model_validate({
            "assessmentYear": "2026-27", "form": "ITR-2",
            "capitalGainsSchedule": {
                "schedule112A": [{"id": "s1", "legacyAliasField": "x"}],
            },
        })


def test_old_simplified_112a_only_shape_still_validates():
    """Backward compatibility: a draft with only the old simplified112A block
    (the shape every ITR-1/4 client currently has saved) still loads."""
    draft = ReturnDraft.model_validate({
        "assessmentYear": "2026-27", "form": "ITR-1",
        "capitalGainsSchedule": {
            "simplified112A": {
                "totalSaleConsideration": "180000",
                "totalCostAcquisition": "100000",
            },
        },
    })
    assert draft.capitalGainsSchedule.simplified112A.totalSaleConsideration == Decimal("180000")
    assert draft.capitalGainsSchedule.schedule112A == []
