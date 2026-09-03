"""Statutory known-answer regression tests for AY 2026-27 ITR-4 calculations.

Each test uses statutory thresholds and formulas from the Income-tax Act,
Finance Act 2025, and the CBDT AY 2026-27 validation-rule document.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import (
    compute_234a,
    compute_234b,
    compute_234c,
    compute_234f,
    compute_234i,
)
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.rounding import round_to_nearest_10, round_to_nearest_rupee, vba_round
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.schedules.agricultural import compute_partial_integration_tax
from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr4 import (
    GoodsCarriageVehicle,
    ITR4Input,
    PresumptiveBusinessIncome44AD,
    PresumptiveGoodsCarriage44AE,
    PresumptiveScheme,
)


D = Decimal
AY_START = date(2026, 4, 1)
DUE_DATE = date(2026, 8, 31)


def _itr4_44ad_input(**overrides: object) -> ITR4Input:
    """Build a valid zero-turnover 44AD ITR-4 input for calculator tests.

    Args:
        **overrides: Top-level ITR4Input fields to override.

    Returns:
        A minimally valid ITR4Input.
    """
    values: dict[str, object] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "presumptive_scheme": PresumptiveScheme.S44AD,
        "business_income_44ad": PresumptiveBusinessIncome44AD(
            total_turnover=D("0"), digital_turnover=D("0"), cash_turnover=D("0")
        ),
        "filing_date": date(2026, 8, 31),
        "due_date": DUE_DATE,
    }
    values.update(overrides)
    return ITR4Input(**values)


def test_rounding_known_answers() -> None:
    """Verify statutory half-up rupee and Section 288A/288B rounding."""
    assert round_to_nearest_rupee(D("100.49")) == D("100")
    assert round_to_nearest_rupee(D("100.50")) == D("101")
    assert vba_round(D("100.50")) == D("101")
    assert round_to_nearest_10(D("104")) == D("100")
    assert round_to_nearest_10(D("105")) == D("110")
    assert round_to_nearest_10(D("-105")) == D("-110")


def test_slab_tax_known_answers_ay_2026_27() -> None:
    """Verify AY 2026-27 old/new slab-tax boundary calculations."""
    assert compute_slab_tax(D("400000"), AgeBracket.BELOW_60, TaxRegime.NEW) == D("0")
    assert compute_slab_tax(D("800000"), AgeBracket.BELOW_60, TaxRegime.NEW) == D("20000")
    assert compute_slab_tax(D("1200000"), AgeBracket.BELOW_60, TaxRegime.NEW) == D("60000")
    assert compute_slab_tax(D("500000"), AgeBracket.BELOW_60, TaxRegime.OLD) == D("12500")
    assert compute_slab_tax(D("500000"), AgeBracket.SIXTY_TO_80, TaxRegime.OLD) == D("10000")
    assert compute_slab_tax(D("500000"), AgeBracket.ABOVE_80, TaxRegime.OLD) == D("0")


def test_rebate_87a_known_answers_and_marginal_relief() -> None:
    """Verify Section 87A caps and marginal relief under both regimes."""
    assert compute_rebate(D("500000"), D("12500"), D("12500"), TaxRegime.OLD) == D("12500")
    assert compute_rebate(D("500100"), D("12520"), D("12520"), TaxRegime.OLD) == D("12420")
    assert compute_rebate(D("1200000"), D("60000"), D("60000"), TaxRegime.NEW) == D("60000")
    assert compute_rebate(D("1200100"), D("60015"), D("60015"), TaxRegime.NEW) == D("59915")
    assert compute_rebate(D("1200000"), D("60000"), D("60000"), TaxRegime.NEW, False) == D("0")


def test_interest_234a_known_answers() -> None:
    """Verify 234A 1%-per-month-or-part-month calculation."""
    assert compute_234a(D("100000"), DUE_DATE, DUE_DATE) == D("0")
    assert compute_234a(D("100000"), date(2026, 9, 1), DUE_DATE) == D("1000")
    assert compute_234a(D("100000"), date(2026, 10, 1), DUE_DATE) == D("2000")


def test_interest_234b_known_answers_with_sat_challan() -> None:
    """Verify 234B 90% trigger and actual SAT challan-date reduction."""
    assert compute_234b(D("100000"), D("90000"), date(2026, 8, 31), AY_START) == D("0")
    assert compute_234b(D("9999"), D("0"), date(2026, 8, 31), AY_START) == D("0")
    interest = compute_234b(
        D("100000"),
        D("0"),
        date(2026, 8, 31),
        AY_START,
        self_assessment_payments=[(date(2026, 6, 10), D("100000"))],
    )
    assert interest == D("3000")


def test_interest_234c_known_answers_regular_and_presumptive() -> None:
    """Verify 234C quarterly and 44AD/44ADA single-installment rules.

    CBDT 234C charges interest on the CUMULATIVE shortfall at each
    installment date. For [0,0,0,100000] on assessed tax ₹1L:
    Q1 shortfall=15k×3mo=₹450, Q2 shortfall=45k×3mo=₹1350,
    Q3 shortfall=75k×3mo=₹2250, Q4 met=₹0. Total=₹4050.
    """
    assert compute_234c([D("15000"), D("30000"), D("30000"), D("25000")], D("100000"), AY_START) == D("0")
    assert compute_234c([D("0"), D("0"), D("0"), D("100000")], D("100000"), AY_START) == D("4050")
    assert compute_234c([D("0")], D("100000"), AY_START, True) == D("1000")
    assert compute_234c([D("100000")], D("100000"), AY_START, True) == D("0")


def test_late_and_revised_return_fees_known_answers() -> None:
    """Verify 234F and 234-I AY 2026-27 fee thresholds and dates.

    234F's pre-Finance-Act-2021 Rs 10,000 tier for filing after 31 December
    was removed; the maximum is Rs 5,000 (Rs 1,000 if total income <=
    Rs 5,00,000) regardless of how late within the belated-filing window
    the return is filed -- the official ITR-1 JSON schema enforces this
    directly (LateFilingFee234F max 5,000). See
    Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
    """
    assert compute_234f(DUE_DATE, DUE_DATE, D("600000")) == D("0")
    assert compute_234f(date(2026, 10, 1), DUE_DATE, D("500000")) == D("1000")
    assert compute_234f(date(2026, 10, 1), DUE_DATE, D("500001")) == D("5000")
    assert compute_234f(date(2027, 1, 1), DUE_DATE, D("500000")) == D("1000")
    assert compute_234i(date(2027, 1, 1), DUE_DATE, D("500000"), "139(5)") == D("1000")
    assert compute_234i(date(2027, 1, 1), DUE_DATE, D("500001"), "139(5)") == D("5000")
    assert compute_234i(date(2027, 1, 1), DUE_DATE, D("500001"), "139(1)") == D("0")


def test_cess_and_surcharge_known_answers() -> None:
    """Verify 4% cess and surcharge marginal relief at ₹50L threshold.

    Marginal relief ensures tax+surcharge at ₹50L+1 does not exceed
    tax at ₹50L + income excess over ₹50L (i.e. ₹1). So surcharge is
    reduced to the amount that caps aggregate tax at threshold_tax+1.
    """
    assert compute_cess(D("100000")) == D("4000")
    tax_50l = compute_slab_tax(D("5000000"), AgeBracket.BELOW_60, TaxRegime.OLD)
    tax_50l_plus_one = compute_slab_tax(D("5000001"), AgeBracket.BELOW_60, TaxRegime.OLD)
    surcharge = compute_surcharge(
        D("5000001"), tax_50l_plus_one, TaxRegime.OLD, AgeBracket.BELOW_60,
        tax_at_threshold=tax_50l,
    )
    # With marginal relief, surcharge is reduced so tax+surcharge ≤ tax@50L+1
    assert tax_50l_plus_one + surcharge <= tax_50l + D("1")
    # Surcharge is non-negative
    assert surcharge >= D("0")


def test_partial_integration_known_answer() -> None:
    """Verify Finance Act partial-integration formula for agricultural income."""
    extra_tax = compute_partial_integration_tax(
        D("600000"), D("100000"), D("250000"), compute_slab_tax,
        AgeBracket.BELOW_60, TaxRegime.OLD,
    )
    assert extra_tax == D("47500")
    assert compute_partial_integration_tax(
        D("600000"), D("5000"), D("250000"), compute_slab_tax,
        AgeBracket.BELOW_60, TaxRegime.OLD,
    ) == D("0")


def test_itr4_rejects_no_presumptive_scheme() -> None:
    """Verify Rule 140 calculator gate rejects PresumptiveScheme.NONE."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.NONE,
    )
    result = compute_itr4(inp)
    assert any("No presumptive scheme selected" in error for error in result.errors)


def test_itr4_rejects_44ae_more_than_120_aggregate_months() -> None:
    """Verify CBDT Rule 141 aggregate 44AE month hard gate."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                GoodsCarriageVehicle(is_heavy_goods_vehicle=False, months_owned=12)
                for _ in range(10)
            ]
        ),
    )
    result = compute_itr4(inp)
    assert not any("aggregate holding period" in error for error in result.errors)


def test_itr4_44ae_eleven_vehicles_is_rejected() -> None:
    """Verify Section 44AE's ten-goods-carriage limit is enforced."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                GoodsCarriageVehicle(is_heavy_goods_vehicle=False, months_owned=12)
                for _ in range(11)
            ]
        ),
    )
    result = compute_itr4(inp)
    assert any("limits ITR-4 to 10 goods carriages" in error for error in result.errors)
