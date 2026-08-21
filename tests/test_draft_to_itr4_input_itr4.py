"""Phase 2 tests — canonical draft_to_itr4_input mapper.

Golden vectors: canonical ``ReturnDraft`` → ``ITR4Input``. Verifies the
single canonical ITR-4 mapper produces the correct typed fields by reading
the typed draft directly (no alias guessing). The legacy
``_build_itr4_input_from_flat`` flat-blob mapper was deleted in Phase 7.

Run: pytest tests/test_draft_to_itr4_input_itr4.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.draft_to_itr4_input import DraftMappingError, draft_to_itr4_input
from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr4 import PresumptiveScheme
from app.schemas.return_draft import (
    Employer,
    HouseProperty,
    InterestIncome,
    Presumptive44AD,
    Presumptive44ADA,
    Presumptive44AE,
    ReturnDraft,
    TdsCredit,
    WinningIncome,
    create_empty_draft,
)


def _basic_itr4_draft() -> ReturnDraft:
    """An ITR-4 draft with the minimum required personal info."""
    draft = create_empty_draft("2026-27", "ITR-4", "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.age = 45
    draft.personal.firstName = "Rahul"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.fatherName = "Mohan Sharma"
    draft.personal.dateOfBirth = "1980-05-15"
    return draft


# ── 44AD ─────────────────────────────────────────────────────────────────────

def test_44ad_draft_maps_presumptive_scheme():
    """A 44AD draft produces the correct presumptive scheme + sub-model."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(
        id="b1", businessName="Acme Trading", natureCode="01101",
        digitalReceipts=Decimal("5000000"),
        nonDigitalReceipts=Decimal("1000000"),
        declaredIncome=Decimal("600000"),
    )]
    typed, breakdown = draft_to_itr4_input(draft)
    assert typed.presumptive_scheme == PresumptiveScheme.S44AD
    assert typed.business_income_44ad is not None
    assert typed.business_income_44ad.total_turnover == Decimal("6000000")
    assert typed.business_income_44ad.digital_turnover == Decimal("5000000")
    assert typed.business_income_44ad.cash_turnover == Decimal("1000000")
    assert typed.business_income_44ad.income_declared == Decimal("600000")
    assert typed.professional_income_44ada is None
    assert typed.goods_carriage_44ae is None
    assert breakdown["presumptive_scheme"] == "44AD"
    assert breakdown["business_code"] == "01101"


def test_44ad_draft_without_declared_income_keeps_none():
    """A 44AD draft with no explicit declared income leaves it None."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(
        id="b1", digitalReceipts=Decimal("2000000"),
        nonDigitalReceipts=Decimal("0"),
    )]
    typed, _ = draft_to_itr4_input(draft)
    assert typed.business_income_44ad is not None
    assert typed.business_income_44ad.income_declared is None
    assert typed.business_income_44ad.total_turnover == Decimal("2000000")


# ── 44ADA ────────────────────────────────────────────────────────────────────

def test_44ada_draft_maps_professional_income():
    """A 44ADA draft produces the correct professional sub-model."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44ADA(
        id="b1", businessName="Legal Practice", natureCode="07003",
        grossReceipts=Decimal("4000000"),
        digitalReceipts=Decimal("3000000"),
        nonDigitalReceipts=Decimal("1000000"),
        declaredIncome=Decimal("2000000"),
    )]
    typed, breakdown = draft_to_itr4_input(draft)
    assert typed.presumptive_scheme == PresumptiveScheme.S44ADA
    assert typed.professional_income_44ada is not None
    assert typed.professional_income_44ada.gross_receipts == Decimal("4000000")
    assert typed.professional_income_44ada.digital_receipts == Decimal("3000000")
    assert typed.professional_income_44ada.cash_receipts == Decimal("1000000")
    assert typed.professional_income_44ada.income_declared == Decimal("2000000")
    assert typed.business_income_44ad is None
    assert breakdown["presumptive_scheme"] == "44ADA"
    assert breakdown["business_code"] is None  # code flows to profession_code for 44ADA


def test_44ada_gross_receipts_derived_when_zero():
    """When gross receipts are 0, they are derived from digital + cash."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44ADA(
        id="b1", digitalReceipts=Decimal("2500000"),
        nonDigitalReceipts=Decimal("500000"),
    )]
    typed, _ = draft_to_itr4_input(draft)
    assert typed.professional_income_44ada.gross_receipts == Decimal("3000000")


# ── 44AE ─────────────────────────────────────────────────────────────────────

def test_44ae_draft_maps_goods_carriage_vehicles():
    """A 44AE draft with heavy + light vehicles maps each correctly."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AE(
        id="b1", businessName="Transport Co", natureCode="06051",
        vehicles=[
            {"vehicleType": "HEAVY", "tonnage": Decimal("16"), "ownedMonths": 12, "vehicleNumber": "KA01"},
            {"vehicleType": "OTHER", "ownedMonths": 6, "vehicleNumber": "KA02"},
        ],
    )]
    typed, breakdown = draft_to_itr4_input(draft)
    assert typed.presumptive_scheme == PresumptiveScheme.S44AE
    assert typed.goods_carriage_44ae is not None
    assert len(typed.goods_carriage_44ae.vehicles) == 2
    heavy = typed.goods_carriage_44ae.vehicles[0]
    assert heavy.is_heavy_goods_vehicle is True
    assert heavy.gross_vehicle_weight_tons == Decimal("16")
    assert heavy.months_owned == 12
    light = typed.goods_carriage_44ae.vehicles[1]
    assert light.is_heavy_goods_vehicle is False
    assert light.gross_vehicle_weight_tons is None
    assert light.months_owned == 6
    assert breakdown["presumptive_scheme"] == "44AE"


# ── Age bracket ──────────────────────────────────────────────────────────────

def test_age_bracket_derived_from_personal_age():
    """ITR-4 derives the age bracket from the explicit age field."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(id="b1", digitalReceipts=Decimal("1000000"))]

    draft.personal.age = 45
    typed, _ = draft_to_itr4_input(draft)
    assert typed.age_bracket == AgeBracket.BELOW_60

    draft.personal.age = 65
    typed, _ = draft_to_itr4_input(draft)
    assert typed.age_bracket == AgeBracket.SIXTY_TO_80

    draft.personal.age = 82
    typed, _ = draft_to_itr4_input(draft)
    assert typed.age_bracket == AgeBracket.ABOVE_80


# ── Combined heads ──────────────────────────────────────────────────────────

def test_combined_salary_hp_os_tds_draft():
    """A draft with salary + HP + OS + TDS populates all shared sub-models."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(
        id="b1", digitalReceipts=Decimal("2000000"),
        declaredIncome=Decimal("200000"),
    )]
    draft.employers = [Employer(
        id="e1", employerName="Acme", employerTAN="MUMA12345B",
        basic=Decimal("800000"), tdsDeducted=Decimal("40000"),
    )]
    draft.houseProperties = [HouseProperty(
        id="h1", propertyType="SELF_OCCUPIED", interestOnLoan=Decimal("150000"),
    )]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("12000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme",
        deductorTAN="MUMA12345B", taxDeducted=Decimal("40000"),
    )]
    typed, breakdown = draft_to_itr4_input(draft)
    assert typed.salary_income is not None
    assert typed.salary_income.gross_salary == Decimal("800000")
    assert typed.house_property_income is not None
    assert typed.house_property_income.home_loan_interest_paid == Decimal("150000")
    assert typed.other_sources_income is not None
    assert typed.other_sources_income.savings_bank_interest == Decimal("12000")
    assert typed.tds1_entries is not None
    assert len(typed.tds1_entries) == 1
    assert typed.tds1_entries[0].tds_deducted == Decimal("40000")
    assert breakdown["gross_salary"] == Decimal("800000")
    assert breakdown["claimed_tds"] == Decimal("40000")


# ── Regime ───────────────────────────────────────────────────────────────────

def test_regime_mapped_from_draft():
    """The draft regime maps to the TaxRegime enum."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(id="b1", digitalReceipts=Decimal("1000000"))]

    typed, _ = draft_to_itr4_input(draft)
    assert typed.tax_regime == TaxRegime.NEW

    draft.regime = "old"
    typed, _ = draft_to_itr4_input(draft)
    assert typed.tax_regime == TaxRegime.OLD


# ── Scope guard ──────────────────────────────────────────────────────────────

def test_lottery_winnings_rejected_for_itr4():
    """Lottery winnings are outside ITR-4 scope — the mapper rejects them."""
    draft = _basic_itr4_draft()
    draft.businesses = [Presumptive44AD(id="b1", digitalReceipts=Decimal("1000000"))]
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="LOTTERY", grossAmount=Decimal("1000"),
    )]
    with pytest.raises(DraftMappingError):
        draft_to_itr4_input(draft)


# ── Empty draft ─────────────────────────────────────────────────────────────

def test_empty_businesses_defaults_to_44ad_zero():
    """A draft with no businesses defaults to 44AD with zero turnover."""
    draft = _basic_itr4_draft()
    typed, _ = draft_to_itr4_input(draft)
    assert typed.presumptive_scheme == PresumptiveScheme.S44AD
    assert typed.business_income_44ad is not None
    assert typed.business_income_44ad.total_turnover == Decimal("0")
