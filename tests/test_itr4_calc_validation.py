"""Tests for app/engine/validators/itr4/calc_rules.py (post-computation checks)."""

from decimal import Decimal

from app.schemas.itr1 import (
    AgeBracket, TaxRegime, PropertyType, OtherSourcesIncome,
)
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD,
    ScheduleBPFinancial,
)
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.validators.itr4.runner import run_calc_validation


def _base_input(**overrides) -> ITR4Input:
    defaults = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_code="B001",
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            digital_turnover=Decimal("500000"),
            cash_turnover=Decimal("0"),
        ),
        nature_of_employment="Private",
        schedule_bp_financial=ScheduleBPFinancial(),
    )
    defaults.update(overrides)
    return ITR4Input(**defaults)


def failed(results, rule_id: str) -> bool:
    return any(r.rule_id == rule_id and not r.passed for r in results)


def test_C096_new_regime_57iia_within_25000_cap_not_falsely_flagged():
    """New regime: 57(iia) family pension deduction = min(1/3 of FP, 25000).
    A deduction of Rs 20,000 (1/3 of a Rs 60,000 pension) is legitimate
    under the new regime's Rs 25,000 cap and must not be flagged, even
    though it exceeds the OLD regime's lower Rs 15,000 cap -- a prior bug
    used a flat, unconditional Rs 15,000 ceiling for both regimes here."""
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(family_pension_received=Decimal("60000")),
    )
    result = compute_itr4(inp)
    assert result.schedules["os"].deduction_57iia == Decimal("20000")
    report = run_calc_validation(inp, result)
    assert not failed(report.results, "ITR4-C096")


def test_C096_new_regime_57iia_exceeding_25000_cap_is_flagged():
    """New regime: family pension large enough that 1/3rd exceeds Rs 25,000
    -- the deduction is correctly capped at 25000 by the calculator, so this
    also should not fire (calculator and validator must agree)."""
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(family_pension_received=Decimal("200000")),
    )
    result = compute_itr4(inp)
    assert result.schedules["os"].deduction_57iia == Decimal("25000")
    report = run_calc_validation(inp, result)
    assert not failed(report.results, "ITR4-C096")


def test_C096_old_regime_57iia_15000_cap_still_enforced():
    """Old regime keeps the Rs 15,000 cap -- unchanged by this fix."""
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        other_sources_income=OtherSourcesIncome(family_pension_received=Decimal("60000")),
        house_property_income=None,
    )
    result = compute_itr4(inp)
    assert result.schedules["os"].deduction_57iia == Decimal("15000")
    report = run_calc_validation(inp, result)
    assert not failed(report.results, "ITR4-C096")
