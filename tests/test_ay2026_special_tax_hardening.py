"""Focused AY 2026-27 tests for special tax, rebate, surcharge, and AMT."""

from decimal import Decimal

import pytest

from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.schedules.amt import (
    AMTAddition,
    AMTAdditionSection,
    compute as compute_amt,
)
from app.engine.schedules.special_rates import (
    SpecialRateEntry,
    aggregate,
    compute_111a,
    compute_112,
    compute_112a,
    compute_112a_taxable,
    compute_115bbg,
    compute_115bbi,
    compute_lottery,
)
from app.schemas.itr1 import AgeBracket, TaxRegime

D = Decimal


def test_special_rate_losses_never_create_negative_tax() -> None:
    """Losses in every flat-rate helper must produce zero income and tax."""
    entries = [
        compute_111a(D("-1")),
        compute_112(D("-2")),
        compute_112a(D("-3")),
        compute_lottery(D("-4")),
        compute_115bbg(D("-5")),
        compute_115bbi(D("-6")),
    ]

    result = aggregate(entries)

    assert all(entry.taxable_income == 0 for entry in entries)
    assert all(entry.tax_amount == 0 for entry in entries)
    assert result.total_special_rate_income == 0
    assert result.total_special_rate_tax == 0


def test_section_112_and_111a_use_ay_2026_rates() -> None:
    """Post-amendment section 112 and 111A rates are 12.5% and 20%."""
    assert compute_112(D("100000")).tax_amount == D("12500")
    assert compute_111a(D("100000")).tax_amount == D("20000")


def test_112a_explicit_taxable_api_does_not_apply_threshold_twice() -> None:
    """A CG-schedule taxable amount remains taxable in Schedule SI."""
    gross_entry = compute_112a(D("200000"))
    taxable_entry = compute_112a_taxable(D("75000"))

    assert gross_entry.exemption_available == D("125000")
    assert gross_entry.taxable_income == D("75000")
    assert taxable_entry.exemption_available == 0
    assert taxable_entry.taxable_income == D("75000")
    assert taxable_entry.tax_amount == D("9375")


def test_112a_rejects_cost_with_pre_thresholded_amount() -> None:
    """Ambiguous threshold and cost treatment is rejected explicitly."""
    with pytest.raises(ValueError, match="cost_of_acquisition"):
        compute_112a(D("75000"), D("100"), pre_exempted=True)


def test_aggregate_sanitizes_negative_external_entries() -> None:
    """Malformed external SI entries cannot offset valid special-rate tax."""
    result = aggregate([
        compute_112(D("100000")),
        SpecialRateEntry(section="115BB", taxable_income=D("-100"), tax_amount=D("-30")),
    ])

    assert result.total_special_rate_income == D("100000")
    assert result.total_special_rate_tax == D("12500")


def test_rebate_is_limited_to_resident_individuals() -> None:
    """A non-resident or non-individual cannot receive section 87A rebate."""
    assert compute_rebate(
        D("500000"), D("12500"), D("12500"), TaxRegime.OLD,
        is_resident_individual=False,
    ) == 0
    assert compute_rebate(D("500000"), D("12500"), D("12500"), TaxRegime.OLD) == D("12500")


def test_surcharge_cap_covers_112_and_dividend_baskets() -> None:
    """Aggregate capped tax receives no surcharge above the statutory 15%."""
    surcharge = compute_surcharge(
        taxable_income=D("21000000"),
        tax_after_rebate=D("2625000"),
        regime=TaxRegime.OLD,
        age_bracket=AgeBracket.BELOW_60,
        sr_tax=D("2625000"),
        sr_income=D("21000000"),
        tax_at_threshold=D("2500000"),
    )

    assert surcharge == D("393750")


def test_marginal_relief_uses_special_rate_tax_at_threshold() -> None:
    """Threshold tax includes retained special income rather than slab tax only."""
    surcharge = compute_surcharge(
        taxable_income=D("5100000"),
        tax_after_rebate=D("1530000"),
        regime=TaxRegime.OLD,
        age_bracket=AgeBracket.BELOW_60,
        sr_surcharge_full_tax=D("1530000"),
        sr_surcharge_full_income=D("5100000"),
    )

    assert surcharge == D("70000")


def test_amt_uses_typed_additions_and_compares_cess_inclusive_totals() -> None:
    """AMT credit compares coherent cess-inclusive regular and AMT totals."""
    result = compute_amt(
        total_income=D("1600000"),
        total_tax_before_cess=D("100000"),
        deductions_triggers=[
            AMTAddition(AMTAdditionSection.SECTION_80IA, D("500000")),
        ],
        regime=TaxRegime.OLD,
        age_bracket=AgeBracket.BELOW_60,
    )

    assert result.adjusted_total_income == D("2100000")
    assert result.amt_tax_before_surcharge_and_cess == D("388500.000")
    assert result.amt_surcharge == 0
    assert result.amt_cess == D("15540")
    assert result.amt_tax == D("404040.000")
    assert result.regular_tax == D("100000")
    assert result.amt_credit == D("304040.000")


def test_amt_can_explicitly_accept_regular_tax_before_cess() -> None:
    """Legacy pre-cess regular tax has cess added once, never twice."""
    result = compute_amt(
        total_income=D("1600000"),
        total_tax_before_cess=D("100000"),
        deductions_triggers={"80-IA": D("500000")},
        regime=TaxRegime.OLD,
        age_bracket=AgeBracket.BELOW_60,
        regular_tax_includes_cess=False,
    )

    assert result.regular_tax == D("104000")
    assert result.amt_credit == D("300040.000")


def test_amt_rejects_unknown_or_negative_additions() -> None:
    """Adjusted income cannot silently include unknown or negative additions."""
    with pytest.raises(ValueError, match="Unsupported AMT"):
        compute_amt(D("1"), D("1"), {"UNKNOWN": D("1")}, "old", "BELOW_60")
    with pytest.raises(ValueError, match="non-negative"):
        compute_amt(
            D("1"), D("1"),
            [AMTAddition(AMTAdditionSection.SECTION_10AA, D("-1"))],
            "old", "BELOW_60",
        )
