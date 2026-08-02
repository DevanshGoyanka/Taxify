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
from datetime import date

from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome,
    AgeBracket, AssesseeType, TaxRegime,
)
from app.engine.common.rounding import vba_round, round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234f, compute_234i
from app.engine.constants import LTCG_112A_EXEMPTION, LTCG_112A_RATE_POST_JUL24
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp, apply_inter_head_loss_limit
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.agricultural import (
    compute as compute_agri,
    compute_partial_integration_tax,
)
from app.engine.schedules.agricultural import (
    compute as compute_agri,
    compute_partial_integration_tax,
)
from app.engine.schedules.special_rates import compute_112a
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.schedules.tds_tcs import compute_all as compute_tds_tcs


@dataclass
class ITR1Result:
    """Complete ITR-1 computation result."""
    salary_income: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    capital_gains_112a: Decimal = Decimal("0")
    gross_total_income: Decimal = Decimal("0")
    net_agricultural_income: Decimal = Decimal("0")
    aggregate_income: Decimal = Decimal("0")
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
    fees_234i: Decimal = Decimal("0")
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



def _check_itr1_eligibility(input_data: ITR1Input) -> list[str]:
    """Check all ITR-1 statutory eligibility conditions.

    Returns list of error messages if any condition fails; empty list if eligible.
    """
    errors: list[str] = []

    # 1. Must be an individual (not HUF)
    if input_data.assessee_type != AssesseeType.INDIVIDUAL:
        errors.append(
            f"Ineligible for ITR-1: Assessee type is '{input_data.assessee_type.value}'. "
            "ITR-1 is only for individuals. File ITR-2 or ITR-3."
        )
        return errors

    # 2. Must be a resident
    if not input_data.is_resident:
        errors.append(
            "Ineligible for ITR-1: Assessee is not a resident individual. "
            "ITR-1 is only for residents. File ITR-2."
        )
        return errors

    # 3. Not a director in any company
    if input_data.is_director:
        errors.append(
            "Ineligible for ITR-1: Assessee is a director in a company. "
            "File ITR-2."
        )

    # 4. No foreign assets / income
    if input_data.has_foreign_assets:
        errors.append(
            "Ineligible for ITR-1: Assessee holds foreign assets or has foreign "
            "income. File ITR-2."
        )

    # 5. No unlisted equity shares
    if input_data.has_unlisted_equity:
        errors.append(
            "Ineligible for ITR-1: Assessee holds unlisted equity shares. "
            "File ITR-2."
        )

    # 6. At most 1 house property
    if input_data.house_property_count > 1:
        errors.append(
            f"Ineligible for ITR-1: Assessee owns {input_data.house_property_count} "
            "house properties. ITR-1 allows at most 1. File ITR-2."
        )

    # 7. Agricultural income must NOT exceed ₹5,000 for ITR-1
    agri = getattr(input_data, "agriculture_income", Decimal("0")) or Decimal("0")
    if agri > Decimal("5000"):
        errors.append(
            f"Ineligible for ITR-1: Agricultural income of Rs {agri} "
            "exceeds Rs 5,000 limit. File ITR-2."
        )

    return errors


def compute(input_data: ITR1Input) -> ITR1Result:
    """Compute complete ITR-1 return from input schema."""
    result = ITR1Result()

    # ── 0. ITR-1 Eligibility Gates ───────────────────────────────────────────
    eligibility = _check_itr1_eligibility(input_data)
    if eligibility:
        result.errors = eligibility
        return result

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

    hp_setoff = apply_inter_head_loss_limit(hp, regime)
    result.house_property_income = hp_setoff.allowed_income
    result.hp_loss_disallowed = hp_setoff.disallowed_loss

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

    # Relief u/s 89 (pass-through from Form 10E computation)
    result.relief_89 = input_data.relief_89

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
        cg_112a_income = entry.net_income
        cg_112a_tax = entry.tax_amount
        result.schedules["capital_gains_112a"] = entry

    result.capital_gains_112a = cg_112a_income

    # ── 2. Gross Total Income ────────────────────────────────────────────────
    gti = result.salary_income + result.house_property_income + result.other_sources_income + cg_112a_income
    result.gross_total_income = gti
    result.net_agricultural_income = input_data.agriculture_income
    result.aggregate_income = gti + result.net_agricultural_income

    # Eligibility: GTI cannot exceed Rs 50 lakh for ITR-1
    if gti > Decimal("5000000"):
        result.errors.append(
            f"Ineligible for ITR-1: Gross Total Income of Rs {gti} "
            f"exceeds Rs 50 lakh limit. File ITR-2."
        )
        return result

    # ── 3. Chapter VI-A Deductions ───────────────────────────────────────────
    # Derive senior/severe flags from rich schedule inputs
    is_parents_senior = False
    is_80dd_severe = False
    is_80u_severe = False
    if ded_input := input_data.deductions_chapter6a:
        is_parents_senior = ded_input.has_parents_senior
        try:
            schedule_80dd = input_data.disability_schedule_80dd()
            schedule_80u = input_data.disability_schedule_80u()
        except ValueError as exc:
            result.errors.append(str(exc))
            return result
        if schedule_80dd is not None:
            is_80dd_severe = schedule_80dd.disability_type.value == "severe"
            if ded_input.amount_80dd > 0:
                ded_input = ded_input.model_copy(deep=True)
                ded_input.amount_80dd = (
                    Decimal("125000") if is_80dd_severe else Decimal("75000")
                )
        if schedule_80u is not None:
            is_80u_severe = schedule_80u.disability_type.value == "severe"
            if ded_input.amount_80u > 0:
                if ded_input is input_data.deductions_chapter6a:
                    ded_input = ded_input.model_copy(deep=True)
                ded_input.amount_80u = (
                    Decimal("125000") if is_80u_severe else Decimal("75000")
                )

    # ── Statutory validation warnings ──
    if ded_input:
        # 80TTB only for senior citizens (age >= 60)
        if ded_input.amount_80ttb > 0 and age not in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80):
            result.warnings.append(
                "80TTB is only available for senior citizens (age >= 60). "
                "Deduction set to Rs 0."
            )
        # 80TTA and 80TTB are mutually exclusive
        if ded_input.amount_80tta > 0 and ded_input.amount_80ttb > 0:
            result.warnings.append(
                "80TTA and 80TTB are mutually exclusive. "
                "80TTA applies to non-seniors; 80TTB applies to seniors."
            )
        # 80GG not available if HRA is claimed
        if ded_input.amount_80gg > 0:
            sal_inp = input_data.salary_income
            if sal_inp and getattr(sal_inp, 'hra_exempt_amount', Decimal("0")) > 0:
                result.warnings.append(
                    "80GG deduction is not available when HRA exemption is claimed. "
                    "Deduction may be disallowed."
                )

    ded = compute_deductions(
        ded_input, gti, age, regime, input_data.other_sources_income,
        cg_112a_income=cg_112a_income,
        is_parents_senior=is_parents_senior,
        is_80dd_severe=is_80dd_severe,
        is_80u_severe=is_80u_severe,
        use_structured_80ddb=True,
        hra_exempt_amount=getattr(input_data.salary_income, 'hra_exempt_amount', Decimal("0")) if input_data.salary_income else Decimal("0"),
        schedule_80gga=input_data.schedule_80gga,
        schedule_80ggc=input_data.schedule_80ggc,
        assessee_pan=input_data.assessee_pan,
        schedule_80c_entries=input_data.schedule_80c_entries,
        schedule_80e_entries=input_data.schedule_80e_entries,
        loan_rows_80ee=input_data.loan_schedule_rows("80EE") if input_data else None,
        loan_rows_80eea=input_data.loan_schedule_rows("80EEA") if input_data else None,
        loan_rows_80eeb=input_data.loan_schedule_rows("80EEB") if input_data else None,
        property_stamp_duty_value_80eea=input_data.property_stamp_duty_value_80eea if input_data else None,
        schedule_80dd=schedule_80dd,
        schedule_80u=schedule_80u,
        schedule_80d=input_data.schedule_80d,
        salary=input_data.salary_income.gross_salary if input_data.salary_income else Decimal("0"),
        is_government_employee=bool(
            input_data.salary_income and input_data.salary_income.is_government_employee
        ),
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
    rebate = compute_rebate(ti, result.tax_before_rebate, slab_tax, regime)
    result.rebate_87a = rebate
    result.tax_after_rebate = max(Decimal("0"), result.tax_before_rebate - rebate)

    # ── 8. Surcharge ─────────────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, result.tax_after_rebate, regime, age,
                                   sr_tax=result.special_rate_tax)
    result.surcharge = surcharge

    # ── 9. Cess (4% on tax + surcharge) ──────────────────────────────────────
    cess = compute_cess(result.tax_after_rebate + surcharge)
    result.health_education_cess = cess

    result.gross_tax_liability = result.tax_after_rebate + surcharge + cess

    # ── 10. Tax Credits (compute BEFORE interest — 234A base uses net assessed tax) ──
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

    # ── 11. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    if filing_date and due_date:
        # 234A: 1% on net assessed tax (gross liability minus prepaid taxes)
        assessed_tax = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs - input_data.advance_tax_paid,
        )
        result.interest_234a = compute_234a(assessed_tax, filing_date, due_date)

        # 234B: assessed tax excludes TDS/TCS but not advance tax, whose
        # sufficiency is evaluated separately by compute_234b.
        advance_tax_assessed = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs,
        )
        ay_start = date(due_date.year, 4, 1)
        result.interest_234b = compute_234b(advance_tax_assessed,
            input_data.advance_tax_paid, filing_date, ay_start)

        # 234C: deferred installment interest
        # Build quarterly advance-tax list.
        # If per-quarter fields are filled, use them; otherwise fall back
        # to treating the scalar advance_tax_paid as a single Q1 lump sum.
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
        result.interest_234c = compute_234c(quarterly, advance_tax_assessed, ay_start)

        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
        result.fees_234i = compute_234i(filing_date, due_date, ti)
    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

    # ── 12. Final payable / refund ───────────────────────────────────────────
    final_liability = round_to_nearest_10(
        max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            + result.total_interest + result.late_fee_234f + result.fees_234i,
        )
    )
    diff = final_liability - result.total_taxes_paid
    if diff > 0:
        result.balance_payable = diff
        result.net_tax_liability = final_liability
    else:
        result.refund_due = abs(diff)
        result.net_tax_liability = final_liability

    return result
