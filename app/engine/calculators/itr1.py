"""
ITR-1 (Sahaj) Calculator.

Composes schedule modules to produce a complete ITR-1 computation.

ITR-1 eligibility:
  - Resident individual
  - Total income <= Rs 50 lakh
  - Income from: Salary, One House Property, Other Sources
  - LTCG u/s 112A only (capped at Rs 1.25 lakh), no other capital gains
  - No business/professional income
  - No foreign assets/income
  - Not a director in a company
  - No unlisted equity shares

Computation order:
  1. Heads of income (Salary, HP, Other Sources, CG-112A)
  2. GTI = sum of income heads
  3. Chapter VI-A deductions
  4. Taxable income = GTI - deductions (rounded to nearest Rs 10)
  5. Slab tax on TI (excluding special-rate income)
  6. Special rate tax (112A @ 12.5%)
  7. Rebate u/s 87A
  8. Surcharge with marginal relief
  9. Health & Education Cess @ 4%
  10. Relief u/s 89 (if applicable)
  11. Interest u/s 234A/B/C + late fee 234F
  12. Total tax liability
  13. TDS/TCS credit
  14. Net payable / refund
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field

from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome,
    AgeBracket, TaxRegime,
)
from app.engine.common.rounding import vba_round, round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234f
from app.engine.constants import LTCG_112A_EXEMPTION, LTCG_112A_RATE_POST_JUL23
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.special_rates import compute_112a
from app.engine.schedules.deductions import compute_all as compute_deductions


@dataclass
class ITR1Result:
    """Complete ITR-1 computation result."""
    salary_income: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    capital_gains_112a: Decimal = Decimal("0")
    gross_total_income: Decimal = Decimal("0")
    deductions_total: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")

    # Salary detail (for ITD JSON output)
    salary_gross: Decimal = Decimal("0")
    salary_perquisites: Decimal = Decimal("0")
    salary_profits_in_lieu: Decimal = Decimal("0")
    salary_net: Decimal = Decimal("0")
    salary_deduction_us16: Decimal = Decimal("0")
    salary_deduction_us16ia: Decimal = Decimal("0")
    salary_entertainment_allowance: Decimal = Decimal("0")
    salary_professional_tax: Decimal = Decimal("0")

    # Tax payment detail (for ITD JSON output)
    advance_tax_paid: Decimal = Decimal("0")
    self_assessment_tax_paid: Decimal = Decimal("0")

    slab_tax: Decimal = Decimal("0")
    special_rate_tax: Decimal = Decimal("0")
    tax_before_rebate: Decimal = Decimal("0")
    rebate_87a: Decimal = Decimal("0")
    tax_after_rebate: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    health_education_cess: Decimal = Decimal("0")
    gross_tax_liability: Decimal = Decimal("0")

    relief_89: Decimal = Decimal("0")
    interest_234a: Decimal = Decimal("0")
    interest_234b: Decimal = Decimal("0")
    interest_234c: Decimal = Decimal("0")
    late_fee_234f: Decimal = Decimal("0")
    total_interest: Decimal = Decimal("0")

    net_tax_liability: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")
    total_tcs: Decimal = Decimal("0")
    total_taxes_paid: Decimal = Decimal("0")
    balance_payable: Decimal = Decimal("0")
    refund_due: Decimal = Decimal("0")

    hp_loss_disallowed: Decimal = Decimal("0")
    schedules: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def compute(input_data: ITR1Input) -> ITR1Result:
    """Compute complete ITR-1 return from input schema."""
    result = ITR1Result()
    regime = input_data.tax_regime
    age = input_data.age_bracket

    # ── 1. Heads of Income ───────────────────────────────────────────────────
    sal = compute_salary(input_data.salary_income, regime)
    hp = compute_hp(input_data.house_property_income, regime)
    os = compute_os(input_data.other_sources_income, regime)
    result.schedules["salary"] = sal
    result.schedules["hp"] = hp
    result.schedules["os"] = os

    result.salary_income = sal.income_chargeable
    result.house_property_income = hp.income_chargeable
    result.other_sources_income = os.income_chargeable

    # Salary detail fields for ITD JSON output
    result.salary_gross = sal.gross_salary
    result.salary_perquisites = getattr(input_data.salary_income, 'perquisites_value', Decimal("0"))
    result.salary_profits_in_lieu = getattr(input_data.salary_income, 'profits_in_lieu_of_salary', Decimal("0"))
    result.salary_net = sal.net_salary
    result.salary_deduction_us16 = sal.deductions_u16
    result.salary_deduction_us16ia = sal.standard_deduction
    result.salary_entertainment_allowance = sal.entertainment_allowance
    result.salary_professional_tax = sal.professional_tax

    result.advance_tax_paid = input_data.advance_tax_paid
    result.self_assessment_tax_paid = input_data.self_assessment_tax_paid

    # Capital Gains (112A only for ITR-1)
    cg_112a_income = Decimal("0")
    cg_112a_tax = Decimal("0")
    if input_data.capital_gains:
        cg = input_data.capital_gains
        # Eligibility check: LTCG 112A cannot exceed Rs 1.25 lakh for ITR-1
        if cg.ltcg_112a > LTCG_112A_EXEMPTION:
            result.errors.append(
                f"Ineligible for ITR-1: LTCG u/s 112A of Rs {cg.ltcg_112a} "
                f"exceeds Rs {LTCG_112A_EXEMPTION} limit. File ITR-2."
            )
            return result
        entry = compute_112a(cg.ltcg_112a)
        cg_112a_income = entry.taxable_income
        cg_112a_tax = entry.tax_amount
        result.schedules["capital_gains_112a"] = entry

    result.capital_gains_112a = cg_112a_income

    # ── 2. Gross Total Income ────────────────────────────────────────────────
    gti = result.salary_income + result.house_property_income + result.other_sources_income + cg_112a_income
    result.gross_total_income = gti

    # Eligibility: GTI cannot exceed Rs 50 lakh for ITR-1
    if gti > Decimal("5000000"):
        result.errors.append(
            f"Ineligible for ITR-1: Gross Total Income of Rs {gti} "
            f"exceeds Rs 50 lakh limit. File ITR-2."
        )
        return result

    # ── 3. Chapter VI-A Deductions ───────────────────────────────────────────
    ded = compute_deductions(
        input_data.deductions_chapter6a, gti, age, regime, input_data.other_sources_income,
        cg_112a_income=cg_112a_income,
    )
    result.schedules["deductions"] = ded
    result.deductions_total = ded.total

    # ── 4. Taxable Income (u/s 288A, rounded to nearest Rs 10) ───────────────
    income_before_rounding = max(Decimal("0"), gti - ded.total)
    ti = round_to_nearest_10(income_before_rounding)
    result.taxable_income = ti

    # ── 5. Normal slab tax (income excluding special-rate income) ─────────────
    normal_income = max(Decimal("0"), ti - cg_112a_income)
    slab_tax = compute_slab_tax(normal_income, age, regime)
    result.slab_tax = slab_tax

    # ── 6. Special rate tax ──────────────────────────────────────────────────
    result.special_rate_tax = cg_112a_tax
    result.tax_before_rebate = slab_tax + cg_112a_tax

    # ── 7. Rebate u/s 87A ────────────────────────────────────────────────────
    rebate = compute_rebate(ti, result.tax_before_rebate, regime)
    result.rebate_87a = rebate
    result.tax_after_rebate = max(Decimal("0"), result.tax_before_rebate - rebate)

    # ── 8. Surcharge ─────────────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, result.tax_after_rebate, regime, age)
    result.surcharge = surcharge

    # ── 9. Cess (4% on tax + surcharge) ──────────────────────────────────────
    cess = compute_cess(result.tax_after_rebate + surcharge)
    result.health_education_cess = cess

    result.gross_tax_liability = result.tax_after_rebate + surcharge + cess

    # ── 10. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    tax_payable_for_interest = result.gross_tax_liability
    if filing_date and due_date:
        result.interest_234a = compute_234a(tax_payable_for_interest, filing_date, due_date)
        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

    # ── 11. Tax Credits ──────────────────────────────────────────────────────
    for tds1 in (input_data.tds1_entries or []):
        result.total_tds += tds1.tds_deducted
    for tds2 in (input_data.tds2_entries or []):
        result.total_tds += tds2.tds_deducted
    for tcs in (input_data.tcs_entries or []):
        result.total_tcs += tcs.tcs_collected
    result.total_taxes_paid = (result.total_tds + result.total_tcs
                                + input_data.advance_tax_paid
                                + input_data.self_assessment_tax_paid)

    # ── 12. Final payable / refund ───────────────────────────────────────────
    final_liability = round_to_nearest_10(
        result.gross_tax_liability + result.total_interest + result.late_fee_234f
    )
    diff = final_liability - result.total_taxes_paid
    if diff > 0:
        result.balance_payable = diff
        result.net_tax_liability = final_liability
    else:
        result.refund_due = abs(diff)
        result.net_tax_liability = final_liability

    result.hp_loss_disallowed = hp.loss_disallowed

    return result
