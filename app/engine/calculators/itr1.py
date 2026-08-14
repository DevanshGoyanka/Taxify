"""
ITR-1 (Sahaj) Calculator.

Composes schedule modules to produce a complete ITR-1 computation.

ITR-1 eligibility:
  - Resident individual
  - Total income <= Rs 50 lakh
  - Income from: Salary, up to two House Properties, Other Sources
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
from app.engine.common.rounding import round_to_nearest_10
from app.engine.common.slab_tax import (
    compute as compute_slab_tax,
    basic_exemption_limit as get_basic_exemption_limit,
)
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234i, compute_234f
from app.engine.common.due_dates import get_due_date, get_default_filing_date
from app.engine.constants import LTCG_112A_EXEMPTION, LTCG_112A_RATE_POST_JUL24
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import HPResult, compute as compute_hp, apply_inter_head_loss_limit
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
    total_income_before_288a: Decimal = Decimal("0")
    rounding_adjustment_288a: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")
    basic_exemption_limit: Decimal = Decimal("0")
    normal_rate_income: Decimal = Decimal("0")
    income_chargeable_above_basic_exemption: Decimal = Decimal("0")
    nil_tax_reason: str | None = None

    # Per-property house-property schedule results (one per ITR-1 row).
    # Ordered to match the ITR1Input.house_properties list; the first entry
    # corresponds to HPSNo 1, the second to HPSNo 2.
    hp_results: list = field(default_factory=list)

    # Salary detail (for ITD JSON output)
    salary_gross: Decimal = Decimal("0")
    salary_perquisites: Decimal = Decimal("0")
    salary_profits_in_lieu: Decimal = Decimal("0")
    salary_net: Decimal = Decimal("0")
    salary_deduction_us16: Decimal = Decimal("0")
    salary_deduction_us16ia: Decimal = Decimal("0")
    salary_entertainment_allowance: Decimal = Decimal("0")
    salary_professional_tax: Decimal = Decimal("0")
    # Section 10 exemption breakdown (for ITD JSON / display)
    salary_gratuity_exempt: Decimal = Decimal("0")
    salary_leave_encashment_exempt: Decimal = Decimal("0")
    salary_vrs_exempt: Decimal = Decimal("0")
    salary_commutted_pension_exempt: Decimal = Decimal("0")
    salary_transport_exempt: Decimal = Decimal("0")
    salary_children_education_exempt: Decimal = Decimal("0")
    salary_hostel_exempt: Decimal = Decimal("0")
    salary_hra_exempt: Decimal = Decimal("0")
    salary_lta_exempt: Decimal = Decimal("0")

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

    # 6. Official AY 2026-27 ITR-1 schema permits at most two PropertyDetails rows.
    hp_rows = input_data.reconciled_house_properties() or [input_data.house_property_income]
    property_count = max(input_data.house_property_count, len(hp_rows))
    if property_count > 2:
        errors.append(
            f"Ineligible for ITR-1: Assessee owns {property_count} house properties. "
            "Official ITR-1 supports at most 2. File ITR-2."
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
    # Use the typed multi-property list when supplied; fall back to the legacy
    # single-property field for backward-compatible callers. The helper detects
    # staleness from model_copy(update=...) and returns the authoritative list.
    hp_inputs = input_data.reconciled_house_properties() or [input_data.house_property_income]
    # Defensive clamp — the eligibility gate already rejects >2.
    if len(hp_inputs) > 2:
        result.errors.append(
            "Ineligible for ITR-1: more than two house properties supplied. File ITR-2."
        )
        return result
    hp_results = [compute_hp(hp_input, regime) for hp_input in hp_inputs]
    # Aggregate intra-head income BEFORE applying the inter-head loss limit
    # (Section 24(b) self-occupied interest cap and Section 71B set-off).
    hp_income_before_setoff = sum((hp.income_chargeable for hp in hp_results), Decimal("0"))
    hp_setoff = apply_inter_head_loss_limit(
        HPResult(income_chargeable=hp_income_before_setoff),
        regime,
    )
    os = compute_os(input_data.other_sources_income, regime)
    result.schedules["salary"] = sal
    result.schedules["hp"] = hp_results
    result.schedules["os"] = os

    result.salary_income = sal.income_chargeable
    result.house_property_income = hp_setoff.allowed_income
    result.hp_loss_disallowed = hp_setoff.disallowed_loss
    # Retain per-property HP results so the official JSON builder can emit
    # one PropertyDetails row per property (HPSNo 1 and 2).
    result.hp_results = hp_results

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
    # Section 10 exemption breakdown from the salary schedule
    result.salary_gratuity_exempt = getattr(sal, 'gratuity_exempt', Decimal("0"))
    result.salary_leave_encashment_exempt = getattr(sal, 'leave_encashment_exempt', Decimal("0"))
    result.salary_vrs_exempt = getattr(sal, 'vrs_exempt', Decimal("0"))
    result.salary_commutted_pension_exempt = getattr(sal, 'commuted_pension_exempt', Decimal("0"))
    result.salary_transport_exempt = getattr(sal, 'transport_exempt', Decimal("0"))
    result.salary_children_education_exempt = getattr(sal, 'children_education_exempt', Decimal("0"))
    result.salary_hostel_exempt = getattr(sal, 'hostel_exempt', Decimal("0"))
    result.salary_hra_exempt = getattr(sal, 'hra_exempt', Decimal("0"))
    result.salary_lta_exempt = getattr(sal, 'lta_exempt', Decimal("0"))

    result.advance_tax_paid = input_data.advance_tax_paid
    result.self_assessment_tax_paid = input_data.self_assessment_tax_paid

    # Relief u/s 89 (pass-through from Form 10E computation)
    result.relief_89 = input_data.relief_89

    # Capital Gains (112A only for ITR-1)
    cg_112a_income = Decimal("0")
    cg_112a_tax = Decimal("0")
    if input_data.cg_transactions:
        # Standalone CG schedule runs the complete suite (112A / 111A /
        # section-112 / land-building / other) with grandfathering and the
        # ₹1.25L aggregate threshold. ITR-1 then projects the restricted-112A
        # aggregate view: only the 112A basket is reportable, losses are
        # forfeited, and exemptions/other CG are disallowed (the form
        # classifier surfaces "file ITR-2" guidance).
        from app.engine.schedules.capital_gains import (
            compute as _compute_cg_schedule,
            project_restricted_112a,
        )
        cg_result = _compute_cg_schedule(input_data.cg_transactions)
        projection = project_restricted_112a(cg_result)
        result.schedules["capital_gains_unified"] = cg_result
        result.schedules["capital_gains_projection"] = projection
        gain_112a = projection["gain_112a"]
        if gain_112a > LTCG_112A_EXEMPTION:
            result.errors.append(
                f"Ineligible for ITR-1: LTCG u/s 112A of Rs {gain_112a} "
                f"exceeds Rs {LTCG_112A_EXEMPTION} limit. File ITR-2."
            )
            return result
        if projection["other_cg_disallowed"] > 0:
            result.errors.append(
                "Ineligible for ITR-1: capital gains outside restricted "
                "Section 112A are present. File ITR-2 or ITR-3."
            )
            return result
        if projection["exemptions_disallowed"] > 0:
            result.errors.append(
                "Ineligible for ITR-1: §54/54B/54EC/54F exemption claims "
                "require Schedule CG. File ITR-2 or ITR-3."
            )
            return result
        entry = compute_112a(gain_112a)
        cg_112a_income = entry.net_income
        cg_112a_tax = entry.tax_amount
        result.schedules["capital_gains_112a"] = entry
    elif input_data.capital_gains:
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
    result.total_income_before_288a = income_before_rounding
    result.rounding_adjustment_288a = ti - income_before_rounding
    result.taxable_income = ti

    # ── 5. Normal slab tax (income excluding special-rate income) ─────────────
    normal_income = max(Decimal("0"), ti - cg_112a_income)
    exemption_limit = get_basic_exemption_limit(age, regime)
    result.basic_exemption_limit = exemption_limit
    result.normal_rate_income = normal_income
    result.income_chargeable_above_basic_exemption = max(
        Decimal("0"), normal_income - exemption_limit,
    )
    slab_tax = compute_slab_tax(normal_income, age, regime)
    result.slab_tax = slab_tax

    # ── 6. Special rate tax ──────────────────────────────────────────────────
    result.special_rate_tax = cg_112a_tax
    result.tax_before_rebate = slab_tax + cg_112a_tax
    if result.tax_before_rebate == Decimal("0") and normal_income <= exemption_limit:
        result.nil_tax_reason = "BELOW_BASIC_EXEMPTION_LIMIT"

    # ── 7. Rebate u/s 87A ────────────────────────────────────────────────────
    rebate = compute_rebate(ti, result.tax_before_rebate, slab_tax, regime)
    result.rebate_87a = rebate
    result.tax_after_rebate = max(Decimal("0"), result.tax_before_rebate - rebate)
    if result.tax_before_rebate > Decimal("0") and result.tax_after_rebate == Decimal("0"):
        result.nil_tax_reason = "REBATE_87A"

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
    # Credits are claimed in whole rupees and must not be rounded under
    # section 288B before they are netted against final liability.
    result.total_taxes_paid = (
        result.total_tds + result.total_tcs
        + input_data.advance_tax_paid
        + input_data.self_assessment_tax_paid)

    # ── 11. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date or (get_due_date("ITR-1") if filing_date else None)

    # Pure calculator callers that do not supply filing context remain neutral.
    # The API/UI supplies the statutory due date as the default filing date.
    if filing_date and due_date:
        # Assessed tax for 234B/C excludes TDS/TCS but not advance tax.
        advance_tax_assessed = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs,
        )
        assessed_tax_234a = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs - input_data.advance_tax_paid,
        )
        ay_start = date(due_date.year, 4, 1)

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
        self_assessment_payments = [
            (entry.payment_date, entry.amount)
            for entry in input_data.tax_payment_entries
            if entry.payment_type == "self_assessment" and entry.payment_date is not None
        ]
        result.interest_234b = compute_234b(
            advance_tax_assessed,
            input_data.advance_tax_paid,
            filing_date,
            ay_start,
            self_assessment_payments=self_assessment_payments,
        )
        result.interest_234a = compute_234a(assessed_tax_234a, filing_date, due_date)
        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
        result.fees_234i = compute_234i(filing_date, due_date, ti,
                                        filing_section=input_data.filing_section)

    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

    # ── 12. Final payable / refund ───────────────────────────────────────────
    # Net liability is retained before Section 288B rounding so that TDS/TCS
    # and challan credits reconcile exactly in whole rupees.
    final_liability = max(
        Decimal("0"),
        result.gross_tax_liability - result.relief_89
        + result.total_interest + result.late_fee_234f + result.fees_234i,
    )
    result.net_tax_liability = final_liability
    diff = final_liability - result.total_taxes_paid
    if diff > 0:
        result.balance_payable = round_to_nearest_10(diff)
    else:
        result.refund_due = round_to_nearest_10(abs(diff))

    return result
