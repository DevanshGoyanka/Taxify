"""
ITR-4 (Sugam) Calculator.

Composes schedule modules to produce a complete ITR-4 computation.

ITR-4 eligibility (AY 2026-27):
  - Resident individual, HUF, or partnership firm (not LLP)
  - Opted for presumptive taxation under 44AD / 44ADA / 44AE
  - Total income <= Rs 50 lakh
  - LTCG u/s 112A permitted up to Rs 1,25,000 (CBDT notification AY 2025-26 onwards)
  - No other capital gains (STCG, LTCG other than 112A, VDA)
  - No foreign assets/income
  - No brought-forward or carry-forward losses
  - Not a director in a company
  - No unlisted equity shares

Computation order:
  1. Presumptive business/professional income
  2. Salary, HP, OS income
  3. Capital Gains (112A only, capped at Rs 1.25L)
  4. GTI
  5. Chapter VI-A deductions
  6. Taxable income (rounded to nearest Rs 10)
  7. Slab tax on normal income
  8. Special rate tax on 112A (12.5% on amount exceeding Rs 1.25L)
  9. Rebate 87A
  10. Surcharge with marginal relief
  11. Cess @ 4%
  12. Interest u/s 234A/B/C + late fee 234F
  13. TDS/TCS credit
  14. Net payable / refund
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field

from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr4 import ITR4Input
from app.engine.common.rounding import round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.presumptive import compute as compute_presumptive
from app.engine.schedules.special_rates import compute_112a
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.common.interest import compute_234a, compute_234f
from app.engine.constants import LTCG_112A_EXEMPTION


@dataclass
class ITR4Result:
    presumptive_income: Decimal = Decimal("0")
    salary_income: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    capital_gains_112a: Decimal = Decimal("0")
    gross_total_income: Decimal = Decimal("0")
    deductions_total: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")

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


def compute(input_data: ITR4Input) -> ITR4Result:
    """Compute complete ITR-4 return from input schema."""
    result = ITR4Result()
    regime = input_data.tax_regime
    age = input_data.age_bracket

    # ── 1. Presumptive Business Income ────────────────────────────────────────
    # Business limit checks (only cap violations are Pydantic-level;
    # cash-ratio and vehicle-count checks are soft errors reported here.)
    if input_data.business_income_44ad:
        biz = input_data.business_income_44ad
        if biz.total_turnover > Decimal("20000000"):
            cash_ratio = biz.cash_turnover / biz.total_turnover if biz.total_turnover > 0 else Decimal("0")
            if cash_ratio > Decimal("0.05"):
                result.errors.append("Cash receipts exceed 5% limit for enhanced 3 crore threshold")

    if input_data.professional_income_44ada:
        prof = input_data.professional_income_44ada
        if prof.gross_receipts > Decimal("5000000"):
            cash_ratio = prof.cash_receipts / prof.gross_receipts if prof.gross_receipts > 0 else Decimal("0")
            if cash_ratio > Decimal("0.05"):
                result.errors.append("Cash receipts exceed 5% limit for enhanced 75 lakh threshold")

    if input_data.goods_carriage_44ae:
        vehicles = input_data.goods_carriage_44ae.vehicles
        if len(vehicles) > 10:
            result.errors.append("cannot own more than 10 vehicles under 44AE")

    pres = compute_presumptive(input_data)
    result.schedules["presumptive"] = pres
    result.presumptive_income = pres.total_presumptive_income

    # ── 2. Salary Income ─────────────────────────────────────────────────────
    sal = compute_salary(input_data.salary_income, regime)
    result.schedules["salary"] = sal
    result.salary_income = sal.income_chargeable

    # ── 3. House Property ────────────────────────────────────────────────────
    hp = compute_hp(input_data.house_property_income, regime)
    result.schedules["hp"] = hp
    result.house_property_income = hp.income_chargeable
    result.hp_loss_disallowed = hp.loss_disallowed

    # ── 4. Other Sources ─────────────────────────────────────────────────────
    os_ = compute_os(input_data.other_sources_income, regime)
    result.schedules["os"] = os_
    result.other_sources_income = os_.income_chargeable

    # ── 5. Capital Gains (112A only for ITR-4) ───────────────────────────────
    cg_112a_income = Decimal("0")
    cg_112a_tax = Decimal("0")
    if input_data.capital_gains:
        cg = input_data.capital_gains
        if cg.ltcg_112a > LTCG_112A_EXEMPTION:
            result.errors.append(
                f"Ineligible for ITR-4: LTCG u/s 112A of Rs {cg.ltcg_112a} "
                f"exceeds Rs {LTCG_112A_EXEMPTION} limit. File ITR-3."
            )
            return result
        entry = compute_112a(cg.ltcg_112a)
        cg_112a_income = entry.taxable_income
        cg_112a_tax = entry.tax_amount
        result.schedules["capital_gains_112a"] = entry

    result.capital_gains_112a = cg_112a_income

    # ── 6. Gross Total Income ────────────────────────────────────────────────
    gti = (
        result.presumptive_income
        + result.salary_income
        + result.house_property_income
        + result.other_sources_income
        + cg_112a_income
    )
    result.gross_total_income = gti

    # Eligibility check
    if gti > Decimal("5000000"):
        result.errors.append(
            f"Ineligible for ITR-4: Total income of Rs {gti} "
            f"exceeds Rs 50 lakh limit. File ITR-3."
        )
        return result

    # ── 7. Chapter VI-A Deductions ───────────────────────────────────────────
    ded = compute_deductions(
        input_data.deductions_chapter6a, gti, age, regime, input_data.other_sources_income,
        cg_112a_income=cg_112a_income,
    )
    result.schedules["deductions"] = ded
    result.deductions_total = ded.total

    # ── 8. Taxable Income (u/s 288A) ─────────────────────────────────────────
    income_before_rounding = max(Decimal("0"), gti - ded.total)
    ti = round_to_nearest_10(income_before_rounding)
    result.taxable_income = ti

    # ── 9. Normal slab tax (income excluding special-rate income) ─────────────
    normal_income = max(Decimal("0"), ti - cg_112a_income)
    slab_tax = compute_slab_tax(normal_income, age, regime)
    result.slab_tax = slab_tax

    # ── 10. Special rate tax (112A @ 12.5% on taxable portion) ────────────────
    result.special_rate_tax = cg_112a_tax
    result.tax_before_rebate = slab_tax + cg_112a_tax

    # ── 11. Rebate u/s 87A ───────────────────────────────────────────────────
    rebate = compute_rebate(ti, result.tax_before_rebate, regime)
    result.rebate_87a = rebate
    result.tax_after_rebate = max(Decimal("0"), result.tax_before_rebate - rebate)

    # ── 12. Surcharge ────────────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, result.tax_after_rebate, regime, age)
    result.surcharge = surcharge

    # ── 13. Cess ────────────────────────────────────────────────��────────────
    cess = compute_cess(result.tax_after_rebate + surcharge)
    result.health_education_cess = cess

    result.gross_tax_liability = result.tax_after_rebate + surcharge + cess

    # ── 14. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    if filing_date and due_date:
        result.interest_234a = compute_234a(result.gross_tax_liability, filing_date, due_date)
        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

    # ── 15. Tax Credits ──────────────────────────────────────────────────────
    for tds1 in (input_data.tds1_entries or []):
        result.total_tds += tds1.tds_deducted
    for tds2 in (input_data.tds2_entries or []):
        result.total_tds += tds2.tds_deducted
    for tcs in (input_data.tcs_entries or []):
        result.total_tcs += tcs.tcs_collected
    result.total_taxes_paid = (result.total_tds + result.total_tcs
                                + input_data.advance_tax_paid
                                + input_data.self_assessment_tax_paid)

    # ── 16. Final payable / refund ───────────────────────────────────────────
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

    return result
