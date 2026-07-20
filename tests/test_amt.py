"""Unit tests for AMT (Alternate Minimum Tax u/s 115JC) schedule."""

from decimal import Decimal
from app.engine.schedules.amt import compute, AMT_RATE


def test_amt_no_triggers():
    result = compute(
        total_income=Decimal("1000000"),
        total_tax_before_cess=Decimal("150000"),
        deductions_triggers={},
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False
    assert result.final_tax == Decimal("150000")


def test_amt_applies_when_higher():
    """AMT = 18.5% of (TI + 80-IA) + surcharge + cess."""
    deductions = {"80-IA": Decimal("500000")}
    # TI = 10L, ATI = 15L, AMT before cess = 15L * 18.5% = 277,500
    result = compute(
        total_income=Decimal("1000000"),
        total_tax_before_cess=Decimal("100000"),  # regular tax very low
        deductions_triggers=deductions,
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is True
    assert result.adjusted_total_income == Decimal("1500000")
    assert result.amt_credit > 0


def test_amt_does_not_apply_when_regular_higher():
    deductions = {"80-IA": Decimal("200000")}
    result = compute(
        total_income=Decimal("2000000"),
        total_tax_before_cess=Decimal("500000"),
        deductions_triggers=deductions,
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False


def test_amt_not_in_new_regime():
    deductions = {"80-IA": Decimal("500000")}
    result = compute(
        total_income=Decimal("1000000"),
        total_tax_before_cess=Decimal("100000"),
        deductions_triggers=deductions,
        regime="new",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False
    assert result.final_tax == Decimal("100000")


def test_amt_rate():
    assert AMT_RATE == Decimal("0.185")
