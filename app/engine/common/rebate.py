"""Section 87A rebate computation for old and new regimes."""

from decimal import Decimal
from app.engine.constants import (
    OLD_REBATE_TAX_LIMIT,
    OLD_REBATE_INCOME_LIMIT,
    NEW_REBATE_TAX_LIMIT,
    NEW_REBATE_INCOME_LIMIT,
)


def compute(taxable_income: Decimal, tax_before_rebate: Decimal, regime: str) -> Decimal:
    from app.schemas.itr1 import TaxRegime

    if tax_before_rebate <= 0:
        return Decimal("0")

    if regime == TaxRegime.OLD:
        if taxable_income <= OLD_REBATE_INCOME_LIMIT:
            return min(tax_before_rebate, OLD_REBATE_TAX_LIMIT)
        return Decimal("0")
    else:
        if taxable_income <= NEW_REBATE_INCOME_LIMIT:
            return min(tax_before_rebate, NEW_REBATE_TAX_LIMIT)
        return max(Decimal("0"), tax_before_rebate - (taxable_income - NEW_REBATE_INCOME_LIMIT))
