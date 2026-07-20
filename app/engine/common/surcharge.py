"""Surcharge computation with marginal relief for both regimes.

CBDT marginal relief formula (Section 2(3C), Schedule I):
  Surcharge is computed on tax (after rebate). However, under marginal relief,
  the total tax + surcharge payable on income exceeding the threshold shall not
  exceed (income - threshold + tax on threshold income).

Equivalently:  surcharge payable = min(rate_surcharge, income_excess)

For post-Jul-2023 (AY 2024-25 onwards), the Finance Act simplified the
surcharge computation by applying rates to total tax after rebate and capping
at (total_income - threshold).
"""

from decimal import Decimal
from app.engine.common.rounding import vba_round
from app.engine.constants import SURCHARGE_SLABS, SURCHARGE_SLABS_NEW_REGIME


def compute(taxable_income: Decimal, tax_after_rebate: Decimal, regime: str, age_bracket: str) -> Decimal:
    from app.schemas.itr1 import TaxRegime

    if tax_after_rebate <= 0:
        return Decimal("0")

    slabs = SURCHARGE_SLABS_NEW_REGIME if regime == TaxRegime.NEW else SURCHARGE_SLABS
    rate = Decimal("0")
    base = Decimal("0")

    for low, high, r in slabs:
        if high is None:
            if taxable_income > low:
                rate = r
                base = low
        elif low < taxable_income <= high:
            rate = r
            base = low
            break

    if rate == 0:
        return Decimal("0")

    before_relief = tax_after_rebate * rate

    # Marginal relief: tax + surcharge shall not exceed
    #   (taxable_income - threshold) + tax at threshold income
    # ------------------------------------------------------------
    # tax_at_threshold: we approximate as slab tax on threshold
    # because at the threshold the assessee just enters the bracket.
    from app.engine.common.slab_tax import compute as compute_slab_tax
    threshold_tax = compute_slab_tax(base, age_bracket, regime)

    excess_income = taxable_income - base
    max_tax_plus_surcharge_at_threshold = excess_income + threshold_tax
    current_tax_plus_surcharge = tax_after_rebate + before_relief

    relief = max(Decimal("0"), current_tax_plus_surcharge - max_tax_plus_surcharge_at_threshold)
    surcharge = vba_round(before_relief - relief)

    return max(Decimal("0"), surcharge)
