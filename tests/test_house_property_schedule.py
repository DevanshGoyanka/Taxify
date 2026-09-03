"""
Unit tests for app/engine/schedules/house_property.py's Section 24(b)
self-occupied interest cap -- added closing
Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §14.1/§19's
documented-but-deferred gap: a loan sanctioned before 1 April 1999 is capped
at Rs 30,000, not the usual Rs 2,00,000.

Run: pytest tests/test_house_property_schedule.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.engine.schedules.house_property import compute
from app.schemas.itr1 import HousePropertyIncome, PropertyType, TaxRegime


def _self_occupied(interest: Decimal) -> HousePropertyIncome:
    return HousePropertyIncome(
        property_type=PropertyType.SELF_OCCUPIED,
        home_loan_interest_paid=interest,
    )


def test_self_occupied_interest_capped_at_2l_by_default():
    result = compute(_self_occupied(Decimal("250000")), TaxRegime.OLD)
    assert result.income_chargeable == Decimal("-200000")


def test_self_occupied_interest_capped_at_2l_when_loan_sanctioned_after_1999():
    result = compute(
        _self_occupied(Decimal("250000")), TaxRegime.OLD,
        loan_sanction_dates=[date(2019, 6, 1)],
    )
    assert result.income_chargeable == Decimal("-200000")


def test_self_occupied_interest_capped_at_30000_when_loan_sanctioned_before_1999():
    result = compute(
        _self_occupied(Decimal("50000")), TaxRegime.OLD,
        loan_sanction_dates=[date(1997, 3, 15)],
    )
    assert result.income_chargeable == Decimal("-30000")


def test_self_occupied_interest_below_30000_cap_unaffected_by_pre_1999_loan():
    result = compute(
        _self_occupied(Decimal("20000")), TaxRegime.OLD,
        loan_sanction_dates=[date(1998, 1, 1)],
    )
    assert result.income_chargeable == Decimal("-20000")


def test_self_occupied_pre_1999_cap_applies_if_any_loan_predates_cutoff():
    """A conservative choice for the rare multi-loan case: if any loan for
    the property was sanctioned before the cutoff, the stricter cap applies
    to the property's total interest rather than trying to split it."""
    result = compute(
        _self_occupied(Decimal("80000")), TaxRegime.OLD,
        loan_sanction_dates=[date(2020, 1, 1), date(1996, 6, 1)],
    )
    assert result.income_chargeable == Decimal("-30000")


def test_self_occupied_new_regime_disallows_interest_regardless_of_sanction_date():
    result = compute(
        _self_occupied(Decimal("50000")), TaxRegime.NEW,
        loan_sanction_dates=[date(1997, 3, 15)],
    )
    assert result.income_chargeable == Decimal("0")
    assert result.loss_disallowed == Decimal("-50000")
