"""
Schedule EI: Exempt Income and Agricultural Income.

Exempt incomes u/s 10 that are not taxable but must be reported for
rate-determination purposes (partial integration u/s 10(1) read with
Finance Act).

Categories:
  - Agricultural income (total, deductions, net) — used for slab rate
    computation on non-agricultural income (partial integration).
  - Other exempt incomes: PPF interest, tax-free bonds, etc.
  - Share of agricultural income from firm/AOP/BOI.

Partial integration of agricultural income (Finance Act):
  If non-agricultural income > basic exemption limit AND
  net agricultural income > ₹5,000:
    Tax = Tax on (NAI + AI) - Tax on (AI + basic exemption)

ITR-1: Simplified EI (agricultural income only for slab computation).
ITR-2/3: Full Schedule EI with all exempt income categories.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass


@dataclass
class AgriculturalIncomeResult:
    gross_agricultural_income: Decimal = Decimal("0")
    agricultural_income_deductions: Decimal = Decimal("0")
    net_agricultural_income: Decimal = Decimal("0")
    share_from_firm: Decimal = Decimal("0")
    total_net_agricultural_income: Decimal = Decimal("0")


def compute_partial_integration_tax(
    non_agri_income: Decimal,
    net_agri_income: Decimal,
    basic_exemption: Decimal,
    slab_tax_fn,
    age_bracket: str,
    regime: str,
) -> Decimal:
    """
    Compute the additional tax due to partial integration of agricultural income.

    Only applies under OLD regime when:
      - non_agri_income > basic_exemption AND
      - net_agri_income > ₹5,000

    Formula (Finance Act, Part I, First Schedule):
      Tax = Tax on (NAI + AI) - Tax on (AI + basic exemption)
    """
    from app.engine.constants import NEW_REGIME_SLABS_AY_2026_27
    from app.schemas.itr1 import TaxRegime

    if regime == TaxRegime.NEW:
        return Decimal("0")

    if net_agri_income <= Decimal("5000") or non_agri_income <= basic_exemption:
        return Decimal("0")

    a = non_agri_income + net_agri_income
    b = net_agri_income + basic_exemption

    tax_a = slab_tax_fn(a, age_bracket, regime)
    tax_b = slab_tax_fn(b, age_bracket, regime)

    return max(Decimal("0"), tax_a - tax_b)


def compute(
    gross_agri: Optional[Decimal] = None,
    agri_deductions: Optional[Decimal] = None,
    share_from_firm: Optional[Decimal] = None,
) -> AgriculturalIncomeResult:
    gross = gross_agri or Decimal("0")
    ded = agri_deductions or Decimal("0")
    net = max(Decimal("0"), gross - ded)
    share = share_from_firm or Decimal("0")

    return AgriculturalIncomeResult(
        gross_agricultural_income=gross,
        agricultural_income_deductions=ded,
        net_agricultural_income=net,
        share_from_firm=share,
        total_net_agricultural_income=net + share,
    )
