"""Section 87A rebate computation for old and new regimes.

Finance Act 2025 (AY 2026-27): Rebate cannot be set off against tax on income
chargeable at special rates (111A/112/112A/115BB/115BBH/115BBE). Rebate is
computed on slab_tax (normal-rate income tax) only, capped at the statutory
limit.

Eligibility:
  - Old regime: Total taxable_income ≤ ₹5,00,000 → rebate = min(slab_tax, ₹12,500)
  - New regime: Total taxable_income ≤ ₹12,00,000 → rebate = min(slab_tax, ₹60,000)
  - New regime marginal relief: max(0, slab_tax - (TI - ₹12,00,000))
"""

from decimal import Decimal
from app.engine.constants import (
    OLD_REBATE_TAX_LIMIT,
    OLD_REBATE_INCOME_LIMIT,
    NEW_REBATE_TAX_LIMIT,
    NEW_REBATE_INCOME_LIMIT,
)


def compute(taxable_income: Decimal, tax_before_rebate: Decimal,
            slab_tax: Decimal, regime: str) -> Decimal:
    """Compute s.87A rebate, applied ONLY to normal slab-rate tax.

    Args:
        taxable_income: Total taxable income (including special-rate income).
        tax_before_rebate: Total tax before rebate (slab + special-rate).
        slab_tax: Tax on normal-rate income only (excludes 111A/112/112A etc.).
        regime: 'old' or 'new'.

    Returns:
        Rebate amount (capped to slab_tax, not the blended tax_before_rebate).
    """
    from app.schemas.itr1 import TaxRegime

    if tax_before_rebate <= 0 or slab_tax <= 0:
        return Decimal("0")

    if regime == TaxRegime.OLD:
        if taxable_income <= OLD_REBATE_INCOME_LIMIT:
            return min(slab_tax, OLD_REBATE_TAX_LIMIT)
        return Decimal("0")
    else:
        if taxable_income <= NEW_REBATE_INCOME_LIMIT:
            return min(slab_tax, NEW_REBATE_TAX_LIMIT)
        # Marginal relief: rebate = slab_tax - (TI - ₹12,00,000), min 0
        return max(Decimal("0"), slab_tax - (taxable_income - NEW_REBATE_INCOME_LIMIT))
