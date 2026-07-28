"""Surcharge computation with marginal relief for both regimes.

Surcharge is applied on tax (after rebate) at slab-determined rates.
For dividend income and capital gains u/s 111A/112/112A/115AD, the surcharge
rate is capped at 15% regardless of the taxpayer's total-income slab — only the
surcharge on the "other" (normal-rate) component of income can go up to the
full slab rate (25%/37% old regime, 25% new regime).

CBDT marginal relief formula (Section 2(3C), Schedule I):
  Surcharge is computed on tax (after rebate). However, under marginal relief,
  the total tax + surcharge payable on income exceeding the threshold shall not
  exceed (income - threshold + tax on threshold income).

Equivalently:  surcharge payable = min(rate_surcharge, income_excess)
"""

from decimal import Decimal
from app.engine.common.rounding import vba_round
from app.engine.constants import SURCHARGE_SLABS, SURCHARGE_SLABS_NEW_REGIME


def compute(taxable_income: Decimal, tax_after_rebate: Decimal, regime: str,
            age_bracket: str, sr_tax: Decimal = Decimal("0"),
            sr_surcharge_full_tax: Decimal = Decimal("0")) -> Decimal:
    """Compute surcharge, capping special-rate income component at 15%.

    Args:
        taxable_income: Total taxable income for slab determination.
        tax_after_rebate: Tax after rebate (normal + special-rate).
        regime: 'old' or 'new'.
        age_bracket: Age bracket for threshold tax computation.
        sr_tax: Tax on qualifying special-rate income eligible for 15% cap
                (111A/112/112A). For backward compatibility, if
                sr_surcharge_full_tax is 0, all sr_tax is treated as capped.
        sr_surcharge_full_tax: Tax on non-qualifying special-rate income
                (115BB lottery, 115BBH VDA, 115BBE unexplained, 115BBF patent)
                that gets the full slab-determined surcharge rate.

    Returns:
        Surcharge amount.
    """
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

    # Split into three buckets:
    #   capped_sr: 111A/112/112A -> capped at 15%
    #   full_sr:   115BB/BBE/BBH/BBF -> full slab rate
    #   normal:    everything else -> full slab rate
    capped_sr = sr_tax or Decimal("0")
    full_sr = sr_surcharge_full_tax or Decimal("0")
    normal_tax = tax_after_rebate - capped_sr - full_sr
    capped_sr_surcharge = capped_sr * min(rate, Decimal("0.15"))
    full_sr_surcharge = full_sr * rate
    normal_surcharge = normal_tax * rate
    before_relief = capped_sr_surcharge + full_sr_surcharge + normal_surcharge

    # Marginal relief: tax + surcharge shall not exceed
    #   (taxable_income - threshold) + tax at threshold income
    # ------------------------------------------------------------
    from app.engine.common.slab_tax import compute as compute_slab_tax
    threshold_tax = compute_slab_tax(base, age_bracket, regime)

    excess_income = taxable_income - base
    max_tax_plus_surcharge_at_threshold = excess_income + threshold_tax
    current_tax_plus_surcharge = tax_after_rebate + before_relief

    relief = max(Decimal("0"), current_tax_plus_surcharge - max_tax_plus_surcharge_at_threshold)
    surcharge = vba_round(before_relief - relief)

    return max(Decimal("0"), surcharge)
