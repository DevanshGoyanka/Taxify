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
    BankAccount,
    Employer,
    DividendIncome,
    Investment80C,
    InterestIncome,
    ReturnDraft,
    TdsCredit,
    TaxChallan,
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
