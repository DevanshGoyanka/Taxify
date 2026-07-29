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

from app.schemas.itr1 import AgeBracket, AssesseeType, TaxRegime
from app.schemas.itr4 import ITR4Input, PresumptiveScheme
from app.engine.common.rounding import round_to_nearest_10

from datetime import date

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
from app.engine.schedules.tds_tcs import compute_all as compute_tds_tcs
from app.engine.schedules.agricultural import (
    compute as compute_agri,
    compute_partial_integration_tax,
)
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234f
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
    net_agricultural_income: Decimal = Decimal("0")
    partial_integration_tax: Decimal = Decimal("0")
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


def _check_itr4_eligibility(input_data: ITR4Input) -> list[str]:
    """Check all ITR-4 statutory eligibility conditions."""
    errors: list[str] = []

    if not getattr(input_data, "is_resident", True):
        errors.append("Ineligible for ITR-4: Assessee is not a resident. File ITR-3.")
        return errors

    if getattr(input_data, "is_director", False):
        errors.append("Ineligible for ITR-4: Assessee is a director in a company. File ITR-3.")

    if getattr(input_data, "has_foreign_assets", False):
        errors.append("Ineligible for ITR-4: Assessee holds foreign assets or has foreign income. File ITR-3.")

    if getattr(input_data, "has_unlisted_equity", False):
        errors.append("Ineligible for ITR-4: Assessee holds unlisted equity shares. File ITR-3.")

    if getattr(input_data, "house_property_count", 1) > 1:
        errors.append(
            f"Ineligible for ITR-4: Owns {input_data.house_property_count} "
            "house properties. ITR-4 allows at most 1. File ITR-3."
        )

    return errors


def compute(input_data: ITR4Input) -> ITR4Result:
    """Compute complete ITR-4 return from input schema."""
    result = ITR4Result()

    # ---- 0. ITR-4 Eligibility Gates ----
    eligibility = _check_itr4_eligibility(input_data)
    if eligibility:
        result.errors = eligibility
        return result

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

    # Salary detail fields for ITD JSON output
    result.salary_gross = sal.gross_salary
    if input_data.salary_income:
        result.salary_perquisites = input_data.salary_income.perquisites_value
        result.salary_profits_in_lieu = input_data.salary_income.profits_in_lieu_of_salary
    result.salary_net = sal.net_salary
    result.salary_deduction_us16 = sal.deductions_u16
    result.salary_deduction_us16ia = sal.standard_deduction
    result.salary_entertainment_allowance = sal.entertainment_allowance
    result.salary_professional_tax = sal.professional_tax

    result.advance_tax_paid = input_data.advance_tax_paid
    result.self_assessment_tax_paid = input_data.self_assessment_tax_paid

    # ── 3. House Property ────────────────────────────────────────────────────
    hp = compute_hp(input_data.house_property_income, regime)
    result.schedules["hp"] = hp
    result.house_property_income = hp.income_chargeable
    result.hp_loss_disallowed = hp.loss_disallowed

    # ── 4. Other Sources ─────────────────────────────────────────────────────
    os_ = compute_os(input_data.other_sources_income, regime)
    result.schedules["os"] = os_
    result.other_sources_income = os_.income_chargeable

    # ---- 4a. Agricultural Income (for partial integration rate) ----
    agri_val = getattr(input_data, "agriculture_income", Decimal("0"))
    agri_result = compute_agri(
        gross_agri=agri_val if agri_val else None,
    )
    result.net_agricultural_income = agri_result.total_net_agricultural_income

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
    is_parents_senior = False
    is_80dd_severe = False
    is_80u_severe = False
    if ded_input := input_data.deductions_chapter6a:
        is_parents_senior = ded_input.has_parents_senior
        if ded_input.schedule_80dd and "severe" in ded_input.schedule_80dd.disability_type.lower():
            is_80dd_severe = True
        if ded_input.schedule_80u and "severe" in ded_input.schedule_80u.disability_type.lower():
            is_80u_severe = True

    # ── Statutory validation warnings ──
    if ded_input:
        if ded_input.amount_80ttb > 0 and age not in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80):
            result.warnings.append(
                "80TTB is only available for senior citizens (age >= 60). "
                "Deduction set to Rs 0."
            )
        if ded_input.amount_80tta > 0 and ded_input.amount_80ttb > 0:
            result.warnings.append(
                "80TTA and 80TTB are mutually exclusive. "
                "80TTA applies to non-seniors; 80TTB applies to seniors."
            )
        if ded_input.amount_80gg > 0:
            sal_inp = input_data.salary_income
            if sal_inp and getattr(sal_inp, 'hra_exempt_amount', Decimal("0")) > 0:
                result.warnings.append(
                    "80GG deduction is not available when HRA exemption is claimed. "
                    "Deduction may be disallowed."
                )

    ded = compute_deductions(
        input_data.deductions_chapter6a, gti, age, regime, input_data.other_sources_income,
        cg_112a_income=cg_112a_income,
        is_parents_senior=is_parents_senior,
        is_80dd_severe=is_80dd_severe,
        is_80u_severe=is_80u_severe,
        hra_exempt_amount=getattr(input_data.salary_income, 'hra_exempt_amount', Decimal("0")) if input_data.salary_income else Decimal("0"),
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

    # Partial integration of agricultural income (old regime only, net agri > Rs 5,000)
    pi_tax = Decimal("0")
    if (regime == TaxRegime.OLD and result.net_agricultural_income > Decimal("5000")
            and normal_income > 0):
        from app.engine.constants import BASIC_EXEMPTION_LIMITS
        basic_exemption = BASIC_EXEMPTION_LIMITS.get(age.value, Decimal("250000"))
        pi_tax = compute_partial_integration_tax(
            normal_income, result.net_agricultural_income,
            basic_exemption, compute_slab_tax,
            age, regime,
        )
    result.partial_integration_tax = pi_tax
    slab_tax += pi_tax
    result.slab_tax = slab_tax


    # ── 10. Special rate tax (112A @ 12.5% on taxable portion) ────────────────
    result.special_rate_tax = cg_112a_tax
    result.tax_before_rebate = slab_tax + cg_112a_tax

    # ── 11. Rebate u/s 87A ───────────────────────────────────────────────────
    rebate = compute_rebate(ti, result.tax_before_rebate, slab_tax, regime)
    result.rebate_87a = rebate
    result.tax_after_rebate = max(Decimal("0"), result.tax_before_rebate - rebate)

    # ── 12. Surcharge ────────────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, result.tax_after_rebate, regime, age,
                                   sr_tax=result.special_rate_tax)
    result.surcharge = surcharge

    # ── 13. Cess ────────────────────────────────────────────────��────────────
    cess = compute_cess(result.tax_after_rebate + surcharge)
    result.health_education_cess = cess

    result.gross_tax_liability = result.tax_after_rebate + surcharge + cess

    # ── 14. Tax Credits (must compute BEFORE interest — 234A base uses net assessed tax) ──
    tds_tcs = compute_tds_tcs(
        tds1_entries=input_data.tds1_entries,
        tds2_entries=input_data.tds2_entries,
        tcs_entries=input_data.tcs_entries,
    )
    result.total_tds = tds_tcs.total_tds
    result.total_tcs = tds_tcs.total_tcs
    result.total_taxes_paid = round_to_nearest_10(
        result.total_tds + result.total_tcs
        + input_data.advance_tax_paid
        + input_data.self_assessment_tax_paid)

    # ── 15. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    if filing_date and due_date:
        # 234A: 1% on net assessed tax (gross liability minus prepaid taxes)
        assessed_tax = max(Decimal("0"),
            result.gross_tax_liability - result.total_tds - result.total_tcs)
        result.interest_234a = compute_234a(assessed_tax, filing_date, due_date)

        # 234B: 1% on shortfall in advance tax (< 90% of assessed tax)
        ay_start = date(due_date.year, 4, 1)
        result.interest_234b = compute_234b(assessed_tax,
            input_data.advance_tax_paid, filing_date, ay_start)

        # 234C: deferred installment interest
        is_presumptive = input_data.presumptive_scheme in (
            PresumptiveScheme.S44AD, PresumptiveScheme.S44ADA)
        if (input_data.advance_tax_q1 is not None or input_data.advance_tax_q2 is not None
                or input_data.advance_tax_q3 is not None or input_data.advance_tax_q4 is not None):
            quarterly = [
                input_data.advance_tax_q1 or Decimal("0"),
                input_data.advance_tax_q2 or Decimal("0"),
                input_data.advance_tax_q3 or Decimal("0"),
                input_data.advance_tax_q4 or Decimal("0"),
            ]
        else:
            quarterly = [input_data.advance_tax_paid] if input_data.advance_tax_paid > 0 else [Decimal("0")]
        result.interest_234c = compute_234c(
            quarterly, assessed_tax, ay_start,
            is_presumptive_44ad_44ada=is_presumptive)

        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

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
