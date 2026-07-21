"""
PGBP (Profits and Gains of Business or Profession) computation.

Handles the core business income computation for ITR-3:
  - Non-speculative business income
  - Speculative business income (separate basket)
  - Specified business income (u/s 35AD)
  - Additions / disallowances (u/s 28 to 44DA)
  - Depreciation adjustment
  - ICDS adjustments
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.engine.common.rounding import round_to_nearest_10


@dataclass
class PGBPResult:
    """Complete PGBP computation result."""
    # Non-speculative business
    non_spec_profit_before_tax: Decimal = Decimal("0")
    non_spec_additions: Decimal = Decimal("0")
    non_spec_deductions: Decimal = Decimal("0")
    non_spec_depreciation_books: Decimal = Decimal("0")
    non_spec_depreciation_it: Decimal = Decimal("0")
    non_spec_icds_adjustment: Decimal = Decimal("0")
    non_spec_net_income: Decimal = Decimal("0")

    # Speculative business
    speculative_net_pl: Decimal = Decimal("0")
    speculative_adjustments: Decimal = Decimal("0")
    speculative_net_income: Decimal = Decimal("0")

    # Specified business (35AD)
    specified_net_pl: Decimal = Decimal("0")
    specified_adjustments: Decimal = Decimal("0")
    specified_net_income: Decimal = Decimal("0")

    # Totals
    total_business_income: Decimal = Decimal("0")

    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def compute(
    net_profit_before_tax: Decimal = Decimal("0"),
    disallowance_us36: Decimal = Decimal("0"),
    disallowance_us37: Decimal = Decimal("0"),
    disallowance_us40: Decimal = Decimal("0"),
    disallowance_us40a: Decimal = Decimal("0"),
    disallowance_us43b: Decimal = Decimal("0"),
    deemed_income_us41: Decimal = Decimal("0"),
    deemed_income_us33ab: Decimal = Decimal("0"),
    deemed_income_us33aba: Decimal = Decimal("0"),
    deemed_income_us35aba: Decimal = Decimal("0"),
    deemed_income_us35abb: Decimal = Decimal("0"),
    deemed_income_us32ad: Decimal = Decimal("0"),
    deemed_income_us40a3a: Decimal = Decimal("0"),
    deemed_income_us43ca: Decimal = Decimal("0"),
    deemed_income_us72a: Decimal = Decimal("0"),
    deemed_income_us80hhd: Decimal = Decimal("0"),
    deemed_income_us80ia: Decimal = Decimal("0"),
    deduction_us32_1_iii: Decimal = Decimal("0"),
    depreciation_books: Decimal = Decimal("0"),
    depreciation_it: Decimal = Decimal("0"),
    icds_increase: Decimal = Decimal("0"),
    icds_decrease: Decimal = Decimal("0"),
    other_additions: Decimal = Decimal("0"),
    other_deductions: Decimal = Decimal("0"),
    speculative_net_pl: Decimal = Decimal("0"),
    speculative_additions: Decimal = Decimal("0"),
    speculative_deductions: Decimal = Decimal("0"),
    specified_net_pl: Decimal = Decimal("0"),
    specified_additions: Decimal = Decimal("0"),
    specified_deductions: Decimal = Decimal("0"),
) -> PGBPResult:
    """Compute PGBP income from input figures."""

    r = PGBPResult()
    z = Decimal("0")

    # --- Non-speculative business ---
    additions = (
        disallowance_us36 + disallowance_us37 + disallowance_us40
        + disallowance_us40a + disallowance_us43b
        + deemed_income_us41 + deemed_income_us33ab + deemed_income_us33aba
        + deemed_income_us35aba + deemed_income_us35abb + deemed_income_us32ad
        + deemed_income_us40a3a + deemed_income_us43ca + deemed_income_us72a
        + deemed_income_us80hhd + deemed_income_us80ia
        + icds_increase + other_additions
    )
    deductions = (
        deduction_us32_1_iii + icds_decrease + other_deductions
    )
    # Depreciation adjustment: add back books depreciation, deduct IT depreciation
    dep_adjustment = depreciation_books - depreciation_it

    r.non_spec_profit_before_tax = net_profit_before_tax
    r.non_spec_additions = additions
    r.non_spec_deductions = deductions
    r.non_spec_depreciation_books = depreciation_books
    r.non_spec_depreciation_it = depreciation_it
    r.non_spec_icds_adjustment = icds_increase - icds_decrease

    adjusted = net_profit_before_tax + additions - deductions + dep_adjustment
    r.non_spec_net_income = max(z, adjusted)

    # --- Speculative business ---
    r.speculative_net_pl = speculative_net_pl
    r.speculative_adjustments = speculative_additions - speculative_deductions
    r.speculative_net_income = max(z, speculative_net_pl + speculative_additions - speculative_deductions)

    # --- Specified business ---
    r.specified_net_pl = specified_net_pl
    r.specified_adjustments = specified_additions - specified_deductions
    r.specified_net_income = max(z, specified_net_pl + specified_additions - specified_deductions)

    r.total_business_income = r.non_spec_net_income + r.speculative_net_income + r.specified_net_income

    return r
