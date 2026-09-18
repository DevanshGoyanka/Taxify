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
    non_spec_net_income: Decimal = Decimal("0")          # floored at 0 for GTI
    non_spec_signed: Decimal = Decimal("0")               # signed (may be negative) for CYLA/BFLA
    # Item 36 (before the Rule 7/7A/7B/8 composite-income adjustment) --
    # distinct from non_spec_signed (item A37, item 36 + the rule-adjusted
    # composite income) only when a Rule 7/7A/7B/8 activity is declared.
    non_spec_item36_signed: Decimal = Decimal("0")
    # Item 38 -- the portion of the item-4b composite profit deemed
    # agricultural income (excluded from this head entirely): item 4b
    # minus the taxpayer's own Rule 7/7A/7B/8-adjusted taxable figure.
    rule_7_8_agricultural_balance: Decimal = Decimal("0")

    # Part E -- intra-head (Section 70) set-off of a non-speculative
    # business LOSS against speculative/specified business INCOME, before
    # any cross-head (Section 71) set-off. Matches the official Schedule
    # BP Part E table exactly: row ii (speculative) absorbs first, then
    # row iii (specified) absorbs whatever remains.
    part_e_loss_to_set_off: Decimal = Decimal("0")            # row i magnitude
    part_e_speculative_income: Decimal = Decimal("0")         # row ii col 1
    part_e_speculative_setoff: Decimal = Decimal("0")         # row ii col 2
    part_e_speculative_income_after_setoff: Decimal = Decimal("0")  # row ii col 3
    part_e_specified_income: Decimal = Decimal("0")           # row iii col 1
    part_e_specified_setoff: Decimal = Decimal("0")           # row iii col 2
    part_e_specified_income_after_setoff: Decimal = Decimal("0")    # row iii col 3
    part_e_total_setoff: Decimal = Decimal("0")                # row iv
    part_e_loss_remaining: Decimal = Decimal("0")               # row v

    # Speculative business
    speculative_net_pl: Decimal = Decimal("0")
    speculative_adjustments: Decimal = Decimal("0")
    speculative_net_income: Decimal = Decimal("0")        # floored at 0 for GTI
    speculative_signed: Decimal = Decimal("0")             # signed for CYLA/BFLA

    # Specified business (35AD)
    specified_net_pl: Decimal = Decimal("0")
    specified_adjustments: Decimal = Decimal("0")
    specified_net_income: Decimal = Decimal("0")          # floored at 0 for GTI
    specified_signed: Decimal = Decimal("0")               # signed for CYLA/BFLA

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
    # Items 3a-3g -- income credited to P&L belonging to another head (see
    # BusinessIncome's own field-level docstrings for the exact form-item
    # mapping and why each of these is a real, permanent adjustment rather
    # than a disclosure-only figure that cancels out elsewhere).
    reallocation_income_salary: Decimal = Decimal("0"),
    reallocation_income_house_property: Decimal = Decimal("0"),
    reallocation_income_capital_gains: Decimal = Decimal("0"),
    reallocation_income_other_sources: Decimal = Decimal("0"),
    reallocation_income_115bbf: Decimal = Decimal("0"),
    reallocation_income_115bbg: Decimal = Decimal("0"),
    reallocation_income_115bbh: Decimal = Decimal("0"),
    # Items 7a-7g -- expenses debited to P&L relating to another head.
    reallocation_expense_salary: Decimal = Decimal("0"),
    reallocation_expense_house_property: Decimal = Decimal("0"),
    reallocation_expense_capital_gains: Decimal = Decimal("0"),
    reallocation_expense_other_sources: Decimal = Decimal("0"),
    reallocation_expense_115bbf: Decimal = Decimal("0"),
    reallocation_expense_115bbg: Decimal = Decimal("0"),
    reallocation_expense_115bbh: Decimal = Decimal("0"),
    # Items 5a/5b/5c/5A -- exempt / not-chargeable income credited to P&L.
    exempt_income_firm_share: Decimal = Decimal("0"),
    exempt_income_aop_boi_share: Decimal = Decimal("0"),
    exempt_income_other: Decimal = Decimal("0"),
    income_not_chargeable: Decimal = Decimal("0"),
    # Items 8a/8b -- expenses relating to exempt income.
    expense_relating_to_exempt_income: Decimal = Decimal("0"),
    expense_exempt_income_disallowed_us14a: Decimal = Decimal("0"),
    # Items 19/23 -- additional disallowances.
    msme_interest_disallowance: Decimal = Decimal("0"),
    other_addition_28_to_44da: Decimal = Decimal("0"),
    # Items 28/29/30 -- additional deductions.
    section35_excess_deduction: Decimal = Decimal("0"),
    section40_now_allowable: Decimal = Decimal("0"),
    section43b_now_allowable: Decimal = Decimal("0"),
    # Item 4b -- composite Rule 7/7A/7B/8 activity profit (subtracted).
    rule7_profit: Decimal = Decimal("0"),
    rule7a_profit: Decimal = Decimal("0"),
    rule7b1_profit: Decimal = Decimal("0"),
    rule7b1a_profit: Decimal = Decimal("0"),
    rule8_profit: Decimal = Decimal("0"),
    # Items 37a-37e -- the taxpayer's own rule-adjusted taxable portion of
    # that same composite activity (added back into item A37).
    rule7_taxable_income: Decimal = Decimal("0"),
    rule7a_deemed_income: Decimal = Decimal("0"),
    rule7b1_deemed_income: Decimal = Decimal("0"),
    rule7b1a_deemed_income: Decimal = Decimal("0"),
    rule8_deemed_income: Decimal = Decimal("0"),
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
        + msme_interest_disallowance + other_addition_28_to_44da
    )
    deductions = (
        deduction_us32_1_iii + icds_decrease + other_deductions
        + section35_excess_deduction + section40_now_allowable + section43b_now_allowable
    )
    # Depreciation adjustment: add back books depreciation, deduct IT depreciation
    dep_adjustment = depreciation_books - depreciation_it

    # Items 3a-3g / 4b / 5a-5c / 5A -- subtracted at item 6 (genuine,
    # permanent removals from business income, since this engine computes
    # Salary/HP/CG/OS income independently from their own typed inputs and
    # exempt/non-chargeable income is never taxable at all).
    reallocation_income_total = (
        reallocation_income_salary + reallocation_income_house_property
        + reallocation_income_capital_gains + reallocation_income_other_sources
        + reallocation_income_115bbf + reallocation_income_115bbg + reallocation_income_115bbh
    )
    rule_7_8_profit = rule7_profit + rule7a_profit + rule7b1_profit + rule7b1a_profit + rule8_profit
    exempt_income_total = exempt_income_firm_share + exempt_income_aop_boi_share + exempt_income_other

    # Items 7a-7g / 8a / 8b -- added back at item 9 (expenses that should
    # never have reduced business income).
    reallocation_expense_total = (
        reallocation_expense_salary + reallocation_expense_house_property
        + reallocation_expense_capital_gains + reallocation_expense_other_sources
        + reallocation_expense_115bbf + reallocation_expense_115bbg + reallocation_expense_115bbh
    )
    expense_exempt_income_total = expense_relating_to_exempt_income + expense_exempt_income_disallowed_us14a

    r.non_spec_profit_before_tax = net_profit_before_tax
    r.non_spec_additions = additions
    r.non_spec_deductions = deductions
    r.non_spec_depreciation_books = depreciation_books
    r.non_spec_depreciation_it = depreciation_it
    r.non_spec_icds_adjustment = icds_increase - icds_decrease

    # Item 36 (A37 before the Rule 7/7A/7B/8 adjustment).
    item36 = (
        net_profit_before_tax
        - reallocation_income_total - rule_7_8_profit - exempt_income_total - income_not_chargeable
        + reallocation_expense_total + expense_exempt_income_total
        + additions - deductions + dep_adjustment
    )
    r.non_spec_item36_signed = item36

    # Items 37a-37e -- the taxpayer's own rule-adjusted taxable portion of
    # the item-4b composite activity, added on top of item 36 to reach
    # item A37. Item 38 (agricultural balance) is the difference.
    rule_7_8_taxable_total = (
        rule7_taxable_income + rule7a_deemed_income + rule7b1_deemed_income
        + rule7b1a_deemed_income + rule8_deemed_income
    )
    r.rule_7_8_agricultural_balance = rule_7_8_profit - rule_7_8_taxable_total

    adjusted = item36 + rule_7_8_taxable_total
    r.non_spec_signed = adjusted
    r.non_spec_net_income = max(z, adjusted)

    # --- Speculative business ---
    r.speculative_net_pl = speculative_net_pl
    r.speculative_adjustments = speculative_additions - speculative_deductions
    r.speculative_signed = speculative_net_pl + speculative_additions - speculative_deductions
    r.speculative_net_income = max(z, r.speculative_signed)

    # --- Specified business ---
    r.specified_net_pl = specified_net_pl
    r.specified_adjustments = specified_additions - specified_deductions
    r.specified_signed = specified_net_pl + specified_additions - specified_deductions
    r.specified_net_income = max(z, r.specified_signed)

    # --- Part E: intra-head (Section 70) set-off of a non-speculative
    # business LOSS (item A37, if negative) against speculative/specified
    # business INCOME, before any cross-head Section 71 set-off. Item D
    # ("IncChrgUnHdProftGain" = A37+B42+C48) is a pure signed sum and is
    # unaffected by how this intra-head absorption is booked -- but the
    # REMAINING loss after this step (not the raw A37 loss) is what the
    # calculator must feed to CYLA's own cross-head machinery, and the
    # speculative/specified income already consumed here must not also be
    # offered to CYLA as a still-available cross-head absorption target.
    loss_to_set_off = max(z, -r.non_spec_signed)
    spec_income_avail = max(z, r.speculative_signed)
    specified_income_avail = max(z, r.specified_signed)
    speculative_setoff = min(loss_to_set_off, spec_income_avail)
    remaining_after_spec = loss_to_set_off - speculative_setoff
    specified_setoff = min(remaining_after_spec, specified_income_avail)
    r.part_e_loss_to_set_off = loss_to_set_off
    r.part_e_speculative_income = spec_income_avail
    r.part_e_speculative_setoff = speculative_setoff
    r.part_e_speculative_income_after_setoff = spec_income_avail - speculative_setoff
    r.part_e_specified_income = specified_income_avail
    r.part_e_specified_setoff = specified_setoff
    r.part_e_specified_income_after_setoff = specified_income_avail - specified_setoff
    r.part_e_total_setoff = speculative_setoff + specified_setoff
    r.part_e_loss_remaining = loss_to_set_off - r.part_e_total_setoff

    # Item D: A37 + B42 + C48 -- a pure signed sum, floored at 0 only for
    # GTI purposes (a residual head-level loss flows cross-head via CYLA
    # instead, using r.part_e_loss_remaining below, not this floor).
    r.total_business_income = max(z, r.non_spec_signed + r.speculative_signed + r.specified_signed)

    return r
