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


def _slabs_for(age_bracket: str, regime: str) -> Sequence[Slab]:
    """Return the authoritative slab table for a taxpayer."""
    from app.schemas.itr1 import AgeBracket, TaxRegime

    if regime == TaxRegime.NEW:
        return NEW_REGIME_SLABS_AY_2026_27
    if age_bracket == AgeBracket.ABOVE_80:
        return OLD_REGIME_SLABS_ABOVE_80
    if age_bracket == AgeBracket.SIXTY_TO_80:
        return OLD_REGIME_SLABS_60_TO_80
    return OLD_REGIME_SLABS_BELOW_60


def compute_old_regime(taxable_income: Decimal, age_bracket: str) -> Decimal:
    from app.schemas.itr1 import TaxRegime

    return _compute(_slabs_for(age_bracket, TaxRegime.OLD), taxable_income)


def compute_new_regime(taxable_income: Decimal) -> Decimal:
    return _compute(NEW_REGIME_SLABS_AY_2026_27, taxable_income)


def basic_exemption_limit(age_bracket: str, regime: str) -> Decimal:
    """Return the applicable zero-rate slab ceiling for AY 2026-27.

    Args:
        age_bracket: Taxpayer age bracket.
        regime: Selected tax regime.

    Returns:
        The upper limit of the first zero-rate slab.
    """
    slabs = _slabs_for(age_bracket, regime)
    return slabs[0][1] or Decimal("0")


def compute(taxable_income: Decimal, age_bracket: str, regime: str) -> Decimal:
    """Compute normal-rate slab tax for the selected regime and age bracket."""
    from app.schemas.itr1 import TaxRegime
    if regime == TaxRegime.NEW:
        return compute_new_regime(taxable_income)
    return compute_old_regime(taxable_income, age_bracket)
