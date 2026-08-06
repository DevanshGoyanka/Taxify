"""Surcharge and marginal-relief computation for AY 2026-27."""

from decimal import Decimal

from app.engine.common.rounding import vba_round
from app.engine.constants import SURCHARGE_SLABS, SURCHARGE_SLABS_NEW_REGIME

_ZERO = Decimal("0")
_CAP_RATE = Decimal("0.15")


def _tax_at_threshold(
    threshold: Decimal,
    taxable_income: Decimal,
    regime: str,
    age_bracket: str,
    capped_tax: Decimal,
    full_special_tax: Decimal,
    capped_income: Decimal,
    full_special_income: Decimal,
) -> Decimal:
    """Recompute tax at a surcharge threshold across all income baskets."""
    from app.engine.common.slab_tax import compute as compute_slab_tax

    excess = max(_ZERO, taxable_income - threshold)
    normal_income = max(_ZERO, taxable_income - capped_income - full_special_income)
    normal_at_threshold = max(_ZERO, normal_income - excess)
    remaining_excess = max(_ZERO, excess - normal_income)

    full_retained = max(_ZERO, full_special_income - remaining_excess)
    remaining_excess = max(_ZERO, remaining_excess - full_special_income)
    capped_retained = max(_ZERO, capped_income - remaining_excess)

    full_tax_at_threshold = (
        full_special_tax * full_retained / full_special_income
        if full_special_income > 0 else _ZERO
    )
    capped_tax_at_threshold = (
        capped_tax * capped_retained / capped_income
        if capped_income > 0 else _ZERO
    )
    return (
        compute_slab_tax(normal_at_threshold, age_bracket, regime)
        + full_tax_at_threshold
        + capped_tax_at_threshold
    )


def compute(
    taxable_income: Decimal,
    tax_after_rebate: Decimal,
    regime: str,
    age_bracket: str,
    sr_tax: Decimal = _ZERO,
    sr_surcharge_full_tax: Decimal = _ZERO,
    sr_income: Decimal = _ZERO,
    sr_surcharge_full_income: Decimal = _ZERO,
    tax_at_threshold: Decimal | None = None,
) -> Decimal:
    """Compute surcharge, its 15% basket cap, and marginal relief.

    Args:
        taxable_income: Total income used to select the surcharge slab.
        tax_after_rebate: Aggregate normal and special-rate tax after rebate.
        regime: Selected tax regime.
        age_bracket: Taxpayer age bracket.
        sr_tax: Tax on section 111A/112/112A and dividend income, whose
            surcharge is capped at 15%.
        sr_surcharge_full_tax: Tax on special income without the 15% cap.
        sr_income: Income corresponding to ``sr_tax``. Supplying it enables a
            basket-aware marginal-relief threshold computation.
        sr_surcharge_full_income: Income corresponding to the uncapped special
            tax basket.
        tax_at_threshold: Explicit aggregate tax (before surcharge) at the
            applicable threshold. This overrides internal recomputation.

    Returns:
        Non-negative surcharge after marginal relief.
    """
    from app.schemas.itr1 import TaxRegime

    income = max(_ZERO, taxable_income)
    aggregate_tax = max(_ZERO, tax_after_rebate)
    if aggregate_tax == 0:
        return _ZERO

    slabs = SURCHARGE_SLABS_NEW_REGIME if regime == TaxRegime.NEW else SURCHARGE_SLABS
    rate = _ZERO
    threshold = _ZERO
    for low, high, slab_rate in slabs:
        if income > low and (high is None or income <= high):
            rate = slab_rate
            threshold = low
            break
    if rate == 0:
        return _ZERO

    capped_tax = min(max(_ZERO, sr_tax), aggregate_tax)
    full_special_tax = min(
        max(_ZERO, sr_surcharge_full_tax),
        aggregate_tax - capped_tax,
    )
    normal_tax = max(_ZERO, aggregate_tax - capped_tax - full_special_tax)
    surcharge_before_relief = (
        capped_tax * min(rate, _CAP_RATE)
        + full_special_tax * rate
        + normal_tax * rate
    )

    if tax_at_threshold is None:
        if sr_income > 0 or sr_surcharge_full_income > 0:
            threshold_tax = _tax_at_threshold(
                threshold,
                income,
                regime,
                age_bracket,
                capped_tax,
                full_special_tax,
                max(_ZERO, sr_income),
                max(_ZERO, sr_surcharge_full_income),
            )
        else:
            from app.engine.common.slab_tax import compute as compute_slab_tax
            threshold_tax = compute_slab_tax(threshold, age_bracket, regime)
    else:
        threshold_tax = max(_ZERO, tax_at_threshold)

    maximum_tax_and_surcharge = threshold_tax + (income - threshold)
    relief = max(
        _ZERO,
        aggregate_tax + surcharge_before_relief - maximum_tax_and_surcharge,
    )
    return max(_ZERO, vba_round(surcharge_before_relief - relief))
