"""Section 87A rebate computation for AY 2026-27."""

from decimal import Decimal

from app.engine.constants import (
    NEW_REBATE_INCOME_LIMIT,
    NEW_REBATE_TAX_LIMIT,
    OLD_REBATE_INCOME_LIMIT,
    OLD_REBATE_TAX_LIMIT,
)


def compute(
    taxable_income: Decimal,
    tax_before_rebate: Decimal,
    slab_tax: Decimal,
    regime: str,
    is_resident_individual: bool = True,
) -> Decimal:
    """Compute section 87A rebate against normal-rate tax only.

    Args:
        taxable_income: Total taxable income including special-rate income.
        tax_before_rebate: Total tax before rebate.
        slab_tax: Tax on normal-rate income only.
        regime: Selected tax regime.
        is_resident_individual: Whether the assessee is both resident and an
            individual. Defaults to true for compatibility with existing ITR
            individual calculators.

    Returns:
        Rebate amount, or zero for an ineligible assessee.
    """
    from app.schemas.itr1 import TaxRegime

    if not is_resident_individual or taxable_income < 0:
        return Decimal("0")
    available_slab_tax = max(Decimal("0"), min(slab_tax, tax_before_rebate))
    if available_slab_tax == 0:
        return Decimal("0")

    if regime == TaxRegime.OLD:
        if taxable_income <= OLD_REBATE_INCOME_LIMIT:
            return min(available_slab_tax, OLD_REBATE_TAX_LIMIT)
        return Decimal("0")

    if taxable_income <= NEW_REBATE_INCOME_LIMIT:
        return min(available_slab_tax, NEW_REBATE_TAX_LIMIT)
    income_excess = taxable_income - NEW_REBATE_INCOME_LIMIT
    return min(available_slab_tax, max(Decimal("0"), available_slab_tax - income_excess))
