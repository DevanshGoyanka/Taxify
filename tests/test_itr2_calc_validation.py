"""
ITR-2 post-computation validation rules (CBDT Category A, AY 2026-27).

Phase 5E of Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md — rules that need a
completed ``ITR2Result`` (not just the pre-compute ``ITR2Input``), starting
with Schedule AL's total-income threshold.

Run: pytest tests/test_itr2_calc_validation.py -v
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.calculators.itr2 import compute as compute_itr2
from app.engine.validators.itr2.calc_rules import run_calc_validation
from app.schemas.itr1 import SalaryIncome, TaxRegime
from app.schemas.itr2 import AgeBracket, AssetLiabilityInput, ITR2Input


def failed(report, rule_id: str) -> bool:
    return any(r.rule_id == rule_id and not r.passed for r in report.results)


def _high_income_input(**overrides) -> ITR2Input:
    fields = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("20000000")),
    )
    fields.update(overrides)
    return ITR2Input(**fields)


def test_CALC_027_schedule_al_present_above_1cr_passes():
    inp = _high_income_input(asset_liability=AssetLiabilityInput(
        immovable_property=Decimal("50000000"),
    ))
    result = compute_itr2(inp)
    assert result.taxable_income > Decimal("10000000")
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-027")


def test_CALC_027_schedule_al_missing_above_1cr_fails():
    inp = _high_income_input(asset_liability=None)
    result = compute_itr2(inp)
    assert result.taxable_income > Decimal("10000000")
    assert failed(run_calc_validation(inp, result), "ITR2-CALC-027")


def test_CALC_027_schedule_al_missing_below_1cr_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("1500000")),
        asset_liability=None,
    )
    result = compute_itr2(inp)
    assert result.taxable_income <= Decimal("10000000")
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-027")
