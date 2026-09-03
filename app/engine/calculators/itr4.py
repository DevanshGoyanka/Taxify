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
from app.engine.schedules.house_property import compute as compute_hp, apply_inter_head_loss_limit
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.presumptive import compute as compute_presumptive
from app.engine.schedules.special_rates import compute_112a
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.schedules.tds_tcs import compute_all as compute_tds_tcs
from app.engine.schedules.agricultural import (
    compute as compute_agri,
    compute_partial_integration_tax,
)
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234i, compute_234f
from app.engine.common.due_dates import get_due_date, get_default_filing_date
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
    salary_uniform_allowance_exempt: Decimal = Decimal("0")

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


def _check_itr4_eligibility(input_data: ITR4Input) -> list[str]:
    """Check all ITR-4 statutory eligibility conditions.

    ITR-4 (Sugam) is specifically for presumptive taxation under 44AD/44ADA/44AE.
    Per CBDT Rule 140: "The Return of Income is filed using ITR 4, however,
    income from business or profession under section 44AD or 44AE or 44ADA
    is not disclosed." — filing ITR-4 without a presumptive scheme is a
    Category A defect that blocks upload.

    Args:
        input_data: The ITR-4 input model to validate.

    Returns:
        A list of error strings. Empty list means eligibility passed.
    """
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

    # ITR-4 requires at least one presumptive income block (CBDT Rule 140).
    # CBDT Rule 140: filing ITR-4 without 44AD/44ADA/44AE income is a
    # Category A defect. PresumptiveScheme.NONE is not a valid ITR-4 election.
    if not any((
        input_data.business_income_44ad,
        input_data.professional_income_44ada,
        input_data.goods_carriage_44ae,
    )):
        errors.append(
            "Ineligible for ITR-4: No presumptive scheme selected. "
            "ITR-4 (Sugam) requires income under Section 44AD, 44ADA, or 44AE. "
            "If the assessee has no presumptive business/professional income, "
            "file ITR-1 or ITR-2 as applicable."
        )

    # The legacy primary-scheme field must still point at a populated block.
    if input_data.presumptive_scheme == PresumptiveScheme.S44AD and not input_data.business_income_44ad:
        errors.append(
            "Ineligible for ITR-4: Presumptive scheme '44AD' selected but "
            "business_income_44ad details not provided. Mandatory."
        )
    if input_data.presumptive_scheme == PresumptiveScheme.S44ADA and not input_data.professional_income_44ada:
        errors.append(
            "Ineligible for ITR-4: Presumptive scheme '44ADA' selected but "
            "professional_income_44ada details not provided. Mandatory."
        )
    if input_data.presumptive_scheme == PresumptiveScheme.S44AE and not input_data.goods_carriage_44ae:
        errors.append(
            "Ineligible for ITR-4: Presumptive scheme '44AE' selected but "
            "goods_carriage_44ae details not provided. Mandatory."
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
    # GAP-3 FIX: Cash-receipts check for 44AD/44ADA uses the statute-correct
    # field (cash_receipts / cash_turnover). The enhanced turnover limit
    # (₹3cr for 44AD, ₹75L for 44ADA) applies ONLY when cash receipts are
    # ≤5% of total receipts. If cash >5%, the base limit (₹2cr / ₹50L) applies
    # and ITR-4 is still eligible, but the cash ratio must be reported.
    if input_data.business_income_44ad:
        biz = input_data.business_income_44ad
        # Statute (Section 44AD(1) proviso): enhanced ₹3cr limit applies only
        # if cash receipts ≤ 5% of total turnover. The schema field
        # `cash_turnover` represents cash receipts.
        if biz.total_turnover > Decimal("20000000"):
            # Enhanced threshold territory (₹2cr < turnover ≤ ₹3cr)
            cash_ratio = (biz.cash_turnover / biz.total_turnover
                          if biz.total_turnover > 0 else Decimal("0"))
            if cash_ratio > Decimal("0.05"):
                result.errors.append(
                    f"Ineligible for ITR-4: 44AD turnover Rs {biz.total_turnover} "
                    f"exceeds ₹2 crore base limit and cash receipts "
                    f"({cash_ratio * 100:.1f}%) exceed 5% threshold. "
                    f"Enhanced ₹3 crore limit not applicable. "
                    f"Tax audit u/s 44AB required — file ITR-3/ITR-5."
                )
        # Cross-field consistency: digital + cash must equal total
        _turnover_sum = (
            biz.digital_turnover + biz.cash_turnover + biz.other_mode_turnover
        )
        if abs(_turnover_sum - biz.total_turnover) > Decimal("1"):
            result.errors.append(
                f"44AD: digital_turnover (Rs {biz.digital_turnover}) + "
                f"cash_turnover (Rs {biz.cash_turnover}) + other_mode_turnover "
                f"(Rs {biz.other_mode_turnover}) = Rs {_turnover_sum} "
                f"does not match total_turnover (Rs {biz.total_turnover})."
            )

    if input_data.professional_income_44ada:
        prof = input_data.professional_income_44ada
        # Statute (Section 44ADA proviso): enhanced ₹75L limit applies only
        # if cash receipts ≤ 5% of total gross receipts.
        if prof.gross_receipts > Decimal("5000000"):
            cash_ratio = (prof.cash_receipts / prof.gross_receipts
                          if prof.gross_receipts > 0 else Decimal("0"))
            if cash_ratio > Decimal("0.05"):
                result.errors.append(
                    f"Ineligible for ITR-4: 44ADA gross receipts Rs "
                    f"{prof.gross_receipts} exceed ₹50 lakh base limit and "
                    f"cash receipts ({cash_ratio * 100:.1f}%) exceed 5% "
                    f"threshold. Enhanced ₹75 lakh limit not applicable. "
                    f"Tax audit u/s 44AB required — file ITR-3/ITR-5."
                )
        # Cross-field consistency: digital + cash must equal gross
        _receipts_sum = (
            prof.digital_receipts + prof.cash_receipts + prof.other_mode_receipts
        )
        if abs(_receipts_sum - prof.gross_receipts) > Decimal("1"):
            result.errors.append(
                f"44ADA: digital_receipts (Rs {prof.digital_receipts}) + "
                f"cash_receipts (Rs {prof.cash_receipts}) + other_mode_receipts "
                f"(Rs {prof.other_mode_receipts}) = Rs "
                f"{_receipts_sum} does not match gross_receipts "
                f"(Rs {prof.gross_receipts})."
            )

    if input_data.goods_carriage_44ae:
        vehicles = input_data.goods_carriage_44ae.vehicles
        # GAP-2 FIX: Vehicle count limit (Section 44AE(1) proviso: ≤10 vehicles)
        if len(vehicles) > 10:
            result.errors.append(
                f"Ineligible for ITR-4: 44AE: {len(vehicles)} vehicles listed. "
                f"Section 44AE(1) proviso limits ITR-4 to 10 goods carriages. "
                f"File ITR-3."
            )
        # GAP-2 FIX: Aggregate months check (CBDT Rule 141)
        # "Number of months for which goods carriage was owned/leased/hired
        #  by assessee more than 12 months AND/OR total period of holding
        #  more than 120 months" → Category A defect
        _total_months = sum(v.months_owned for v in vehicles)
        if _total_months > 120:
            result.errors.append(
                f"Ineligible for ITR-4: 44AE: aggregate holding period "
                f"({_total_months} months across {len(vehicles)} vehicles) "
                f"exceeds 120 months. CBDT Rule 141: total period of holding "
                f"cannot exceed 120 months. File ITR-3."
            )
        # Per-vehicle month cap already enforced by schema (months_owned: 1-12)
        # but double-check at calculator level for safety
        for _i, _v in enumerate(vehicles):
            if _v.months_owned > 12:
                result.errors.append(
                    f"Ineligible for ITR-4: 44AE vehicle {_i+1}: months_owned "
                    f"({_v.months_owned}) exceeds 12. A vehicle cannot be "
                    f"owned for more than 12 months in a single previous year."
                )
        # GAP-2 FIX: Vehicle registration number uniqueness (CBDT Rule 213)
        _regnos = [v for v in input_data.vehicle_registration_numbers
                   if v] if input_data.vehicle_registration_numbers else []
        if _regnos:
            _seen = set()
            for _reg in _regnos:
                if _reg in _seen:
                    result.errors.append(
                        f"Ineligible for ITR-4: 44AE: vehicle registration "
                        f"number '{_reg}' is repeated. CBDT Rule 213: "
                        f"Registration No. cannot be repeated in section 44AE."
                    )
                    break
                _seen.add(_reg)

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
    # Section 10 exemption breakdown
    result.salary_gratuity_exempt = getattr(sal, 'gratuity_exempt', Decimal("0"))
    result.salary_leave_encashment_exempt = getattr(sal, 'leave_encashment_exempt', Decimal("0"))
    result.salary_vrs_exempt = getattr(sal, 'vrs_exempt', Decimal("0"))
    result.salary_commutted_pension_exempt = getattr(sal, 'commuted_pension_exempt', Decimal("0"))
    result.salary_transport_exempt = getattr(sal, 'transport_exempt', Decimal("0"))
    result.salary_children_education_exempt = getattr(sal, 'children_education_exempt', Decimal("0"))
    result.salary_hostel_exempt = getattr(sal, 'hostel_exempt', Decimal("0"))
    result.salary_hra_exempt = getattr(sal, 'hra_exempt', Decimal("0"))
    result.salary_lta_exempt = getattr(sal, 'lta_exempt', Decimal("0"))
    result.salary_uniform_allowance_exempt = getattr(sal, 'uniform_allowance_exempt', Decimal("0"))

    result.advance_tax_paid = input_data.advance_tax_paid
    result.self_assessment_tax_paid = input_data.self_assessment_tax_paid
    result.relief_89 = input_data.relief_89

    # ── 3. House Property ────────────────────────────────────────────────────
    # ITR-4 computes income for only the FIRST house property row (no
    # house_properties list on ITR4Input, unlike ITR-1's up-to-two --
    # confirmed directly: draft_to_itr4_input.py's house_property_income is
    # hp_inputs[0] and filing_gateway_v2.py's _itr4_property_profile also
    # only ever reads normalize_property_details(...)[0]). Nothing in this
    # pipeline actually rejects a draft with a second house property row,
    # though, and _map_24b_loans (shared with ITR-1) tags each loan with its
    # own property_sequence_no regardless -- so loan_details_24b_list could
    # in principle carry a second property's loan under sequence_no 2. Only
    # sequence_no 1's loans are relevant to the interest actually being
    # computed here. See the identical pre-1999 self-occupied interest cap
    # fix in app/engine/calculators/itr1.py and
    # Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §3.1.
    hp = compute_hp(
        input_data.house_property_income,
        regime,
        (
            input_data.house_property_income.ownership_share_percentage
            if input_data.house_property_income is not None else Decimal("100")
        ),
        loan_sanction_dates=[
            loan.sanction_date for loan in input_data.loan_details_24b_list
            if loan.property_sequence_no == 1
        ],
    )
    result.schedules["hp"] = hp
    hp_setoff = apply_inter_head_loss_limit(hp, regime)
    result.house_property_income = hp_setoff.allowed_income
    result.hp_loss_disallowed = hp_setoff.disallowed_loss

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
    if input_data.cg_transactions:
        # Standalone CG schedule runs the complete suite (112A / 111A /
        # section-112 / land-building / other) with grandfathering and the
        # ₹1.25L aggregate threshold. ITR-4 then projects the restricted-112A
        # aggregate view: only the 112A basket is reportable, losses are
        # forfeited, and exemptions/other CG are disallowed (the form
        # classifier surfaces "file ITR-3" guidance).
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
                f"Ineligible for ITR-4: LTCG u/s 112A of Rs {gain_112a} "
                f"exceeds Rs {LTCG_112A_EXEMPTION} limit. File ITR-3."
            )
            return result
        if projection["other_cg_disallowed"] > 0:
            result.errors.append(
                "Ineligible for ITR-4: capital gains outside restricted "
                "Section 112A are present. File ITR-3."
            )
            return result
        if projection["exemptions_disallowed"] > 0:
            result.errors.append(
                "Ineligible for ITR-4: §54/54B/54EC/54F exemption claims "
                "require Schedule CG. File ITR-3."
            )
            return result
        entry = compute_112a(gain_112a)
        cg_112a_income = entry.net_income
        cg_112a_tax = entry.tax_amount
        result.schedules["capital_gains_112a"] = entry
    elif input_data.capital_gains:
        cg = input_data.capital_gains
        if cg.ltcg_112a > LTCG_112A_EXEMPTION:
            result.errors.append(
                f"Ineligible for ITR-4: LTCG u/s 112A of Rs {cg.ltcg_112a} "
                f"exceeds Rs {LTCG_112A_EXEMPTION} limit. File ITR-3."
            )
            return result
        entry = compute_112a(cg.ltcg_112a)
        cg_112a_income = entry.net_income
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
        schedule_80gga=input_data.schedule_80gga,
        schedule_80ggc=input_data.schedule_80ggc,
        assessee_pan=input_data.assessee_pan,
        schedule_80c_entries=input_data.schedule_80c_entries,
        schedule_80e_entries=input_data.schedule_80e_entries,
        loan_rows_80ee=getattr(input_data, "loan_details_80ee_list", None),
        loan_rows_80eea=getattr(input_data, "loan_details_80eea_list", None),
        loan_rows_80eeb=getattr(input_data, "loan_details_80eeb_list", None),
        schedule_80dd=input_data.schedule_80dd,
        schedule_80u=input_data.schedule_80u,
        schedule_80d=input_data.schedule_80d,
    )
    result.schedules["deductions"] = ded
    result.deductions_total = ded.total

    # ── 8. Taxable Income (u/s 288A) ─────────────────────────────────────────
    income_before_rounding = max(Decimal("0"), gti - ded.total)
    ti = round_to_nearest_10(income_before_rounding)
    result.taxable_income = ti

    # ── 9. Normal slab tax (income excluding special-rate income) ─────────────
    # normal_income = TI − 112A (112A taxed at special 12.5% rate, not slab)
    normal_income = max(Decimal("0"), ti - cg_112a_income)
    slab_tax = compute_slab_tax(normal_income, age, regime)
    result.slab_tax = slab_tax

    # Partial integration of agricultural income (old regime only, net agri > Rs 5,000).
    # F7 FIX: NAI (non-agricultural income) for partial integration = TI (total
    # taxable income), NOT normal_income. 112A LTCG is non-agricultural income
    # and must be included in NAI per Finance Act Part I First Schedule.
    pi_tax = Decimal("0")
    if (regime == TaxRegime.OLD and result.net_agricultural_income > Decimal("5000")
            and ti > 0):
        from app.engine.constants import BASIC_EXEMPTION_LIMITS
        basic_exemption = BASIC_EXEMPTION_LIMITS.get(age.value, Decimal("250000"))
        pi_tax = compute_partial_integration_tax(
            ti, result.net_agricultural_income,
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
        tds3_entries=input_data.tds3_entries,
    )
    result.total_tds = tds_tcs.total_tds
    result.total_tcs = tds_tcs.total_tcs
    # Tax credits remain exact whole-rupee amounts until final reconciliation.
    result.total_taxes_paid = (
        result.total_tds + result.total_tcs
        + input_data.advance_tax_paid
        + input_data.self_assessment_tax_paid)

    # ── 15. Interest & Late Fee ──────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date or (get_due_date("ITR-4") if filing_date else None)

    if filing_date and due_date:
        assessed_tax = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs - input_data.advance_tax_paid,
        )
        advance_tax_assessed = max(
            Decimal("0"),
            result.gross_tax_liability - result.relief_89
            - result.total_tds - result.total_tcs,
        )
        ay_start = date(due_date.year, 4, 1)
        result.interest_234a = compute_234a(assessed_tax, filing_date, due_date)
        # F1 FIX: Pass self-assessment-tax challans to 234B so interest runs
        # only until each challan's actual deposit date, not the filing date.
        # Mirrors the ITR-1 calculator's wiring (see itr1.py ~L545).
        _sat_payments = [
            (entry.payment_date, entry.amount)
            for entry in (input_data.tax_payment_entries or [])
            if getattr(entry, "payment_type", "") == "self_assessment"
            and getattr(entry, "payment_date", None) is not None
            and getattr(entry, "amount", Decimal("0")) > 0
        ]
        result.interest_234b = compute_234b(advance_tax_assessed,
            input_data.advance_tax_paid, filing_date, ay_start,
            self_assessment_payments=_sat_payments)
        is_presumptive = bool(
            input_data.business_income_44ad
            or input_data.professional_income_44ada
        )
        if (input_data.advance_tax_q1 is not None or input_data.advance_tax_q2 is not None
                or input_data.advance_tax_q3 is not None or input_data.advance_tax_q4 is not None):
            quarterly = [
                input_data.advance_tax_q1 or Decimal("0"),
                input_data.advance_tax_q2 or Decimal("0"),
                input_data.advance_tax_q3 or Decimal("0"),
                input_data.advance_tax_q4 or Decimal("0"),
            ]
        else:
            # F10 FIX: When only a lump-sum advance_tax_paid is given (no
            # quarterly breakdown), bucket tax_payment_entries by their deposit
            # date into the correct quarter. This prevents the old fallback
            # (which put the entire lump-sum into Q1) from understating 234C.
            if input_data.advance_tax_paid > 0 and input_data.tax_payment_entries:
                _q = [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")]
                for _entry in input_data.tax_payment_entries:
                    if getattr(_entry, "payment_type", "") != "advance":
                        continue
                    _d = getattr(_entry, "payment_date", None)
                    _amt = getattr(_entry, "amount", Decimal("0"))
                    if _d is None or _amt <= 0:
                        continue
                    # AY runs Apr(prev year)–Mar(current year).
                    # Q1: Apr–Jun (15 Jun due)  | Q2: Jul–Sep (15 Sep)
                    # Q3: Oct–Dec (15 Dec)      | Q4: Jan–Mar (15 Mar)
                    _month = _d.month
                    if _month >= 4 and _month <= 6:
                        _q[0] += _amt
                    elif _month >= 7 and _month <= 9:
                        _q[1] += _amt
                    elif _month >= 10 and _month <= 12:
                        _q[2] += _amt
                    else:  # Jan–Mar
                        _q[3] += _amt
                quarterly = _q
            else:
                quarterly = [input_data.advance_tax_paid] if input_data.advance_tax_paid > 0 else [Decimal("0")]
        result.interest_234c = compute_234c(
            quarterly, advance_tax_assessed, ay_start,
            is_presumptive_44ad_44ada=is_presumptive)
        result.late_fee_234f = compute_234f(filing_date, due_date, ti)
        result.fees_234i = compute_234i(filing_date, due_date, ti,
                                        filing_section=input_data.filing_section)
    result.total_interest = result.interest_234a + result.interest_234b + result.interest_234c

    # ── 16. Final payable / refund ───────────────────────────────────────────
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
