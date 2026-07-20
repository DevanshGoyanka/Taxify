"""Progressive slab tax computation for both old and new regimes."""

from decimal import Decimal
from typing import Sequence
from app.engine.common.rounding import vba_round
from app.engine.constants import (
    OLD_REGIME_SLABS_BELOW_60,
    OLD_REGIME_SLABS_60_TO_80,
    OLD_REGIME_SLABS_ABOVE_80,
    NEW_REGIME_SLABS_AY_2026_27,
)

Slab = tuple[Decimal, Decimal | None, Decimal]  # (lower, upper | None, rate%)


def _compute(slab_defs: Sequence[Slab], taxable_income: Decimal) -> Decimal:
    if taxable_income <= 0:
        return Decimal("0")
    tax = Decimal("0")
    for lower, upper, rate in slab_defs:
        if taxable_income <= lower:
            break
        taxable = (min(taxable_income, upper) - lower if upper is not None
                   else taxable_income - lower)
        if taxable <= 0:
            continue
        tax += vba_round(taxable * rate / Decimal("100"))
    return tax


def compute_old_regime(taxable_income: Decimal, age_bracket: str) -> Decimal:
    from app.schemas.itr1 import AgeBracket
    if age_bracket == AgeBracket.ABOVE_80:
        slabs = OLD_REGIME_SLABS_ABOVE_80
    elif age_bracket == AgeBracket.SIXTY_TO_80:
        slabs = OLD_REGIME_SLABS_60_TO_80
    else:
        slabs = OLD_REGIME_SLABS_BELOW_60
    return _compute(slabs, taxable_income)


def compute_new_regime(taxable_income: Decimal) -> Decimal:
    return _compute(NEW_REGIME_SLABS_AY_2026_27, taxable_income)


def compute(taxable_income: Decimal, age_bracket: str, regime: str) -> Decimal:
    from app.schemas.itr1 import TaxRegime
    if regime == TaxRegime.NEW:
        return compute_new_regime(taxable_income)
    return compute_old_regime(taxable_income, age_bracket)
