"""
ITR-4 input validation rules (pre-computation, conditional mandatory fields).

These rules mirror CBDT Category A rules from the ITR-4 Validation Rules
document for AY 2026-27. They run BEFORE computation.

Rules covering assessee_type (individual/HUF/firm) are informational only
because the schema does not carry an assessee_type field. Rules requiring
fields not in the schema (business_code, registration_number, etc.) are
likewise informational (Severity.D, passed=True).

Organization follows CBDT rule sections:
  44AD, 44ADA, 44AE presumptive schemes
  ITR-4 eligibility
  Firm/HUF restrictions (informational)
  Deduction limits (old regime)
  New regime restrictions
  House property validations
  Salary validations
  80TTA / 80TTB
  80G / 80GGC
  80GG
  80DD / 80U / 80DDB
  TDS / TCS / Tax credits
  Capital gains
"""

from __future__ import annotations

from decimal import Decimal
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme,
)
from app.schemas.itr1 import AgeBracket, TaxRegime, PropertyType, AssesseeType
from app.engine.validators.base import ValidationResult, Severity


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make(rule_id: str, passed: bool, message: str, field_path: str = "",
          expected=None, actual=None) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id, severity=Severity.A, passed=passed,
        message=message, field_path=field_path,
        expected=expected, actual=actual,
    )


def _info(rule_id: str, message: str, field_path: str = "") -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id, severity=Severity.D, passed=True,
        message=message, field_path=field_path,
    )


def _warn(rule_id: str, message: str, field_path: str = "") -> ValidationResult:
    """Category B warning — the input is unusual but may still be correct."""
    return ValidationResult(
        rule_id=rule_id, severity=Severity.B, passed=True,
        message=message, field_path=field_path,
    )


# ── Main entry point ─────────────────────────────────────────────────────────

def validate_itr4_input(inp: ITR4Input) -> list[ValidationResult]:
    """Run ALL ITR-4 input-level validation rules."""
    results: list[ValidationResult] = []
    z = Decimal("0")
    ch6a = inp.deductions_chapter6a
    is_new = inp.tax_regime == TaxRegime.NEW
    is_old = inp.tax_regime == TaxRegime.OLD
    is_senior = inp.age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    sal = inp.salary_income
    hp = inp.house_property_income
    os_ = inp.other_sources_income
    cg = inp.capital_gains
    assessee = inp.assessee_type
    is_individual = assessee == AssesseeType.INDIVIDUAL
    is_huf = assessee == AssesseeType.HUF
    is_firm = assessee == AssesseeType.FIRM

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Assessee Type Restrictions (R020, R023-R028, R031-R033, etc.)
    # ═══════════════════════════════════════════════════════════════════════

    if is_firm:
        # R020: Firm cannot claim 80C/80CCC/80CCD(1)
        if ch6a and (ch6a.amount_80c > z or ch6a.amount_80ccc > z or ch6a.amount_80ccd1 > z):
            results.append(_make(
                "ITR4-R020", False,
                "Firms cannot claim deductions under 80C, 80CCC, or 80CCD(1). "
                "Only individuals/HUFs are eligible.",
                "assessee_type"))
        # R027: Firm cannot claim 80D
        if ch6a and (ch6a.amount_80d_self_family > z or ch6a.amount_80d_parents > z):
            results.append(_make(
                "ITR4-R027", False,
                "Firms cannot claim deduction under 80D.",
                "assessee_type"))
        # R028: Firm cannot claim 80DD
        if ch6a and ch6a.amount_80dd > z:
            results.append(_make(
                "ITR4-R028", False,
                "Firms cannot claim deduction under 80DD.",
                "assessee_type"))
        # R031: Firm cannot claim 80DDB
        if ch6a and ch6a.amount_80ddb > z:
            results.append(_make(
                "ITR4-R031", False,
                "Firms cannot claim deduction under 80DDB.",
                "assessee_type"))
        # R043: Firm cannot claim 80U
        if ch6a and ch6a.amount_80u > z:
            results.append(_make(
                "ITR4-R043", False,
                "Firms cannot claim deduction under 80U (individuals only).",
                "assessee_type"))

    if not is_individual:
        # R023: Non-individual cannot claim 80CCD(1)
        if ch6a and ch6a.amount_80ccd1 > z:
            results.append(_make(
                "ITR4-R023", False,
                "80CCD(1) is only available to individuals.",
                "assessee_type"))
        # R024: Non-individual cannot claim 80CCD(1B)
        if ch6a and ch6a.amount_80ccd1b > z:
            results.append(_make(
                "ITR4-R024", False,
                "80CCD(1B) is only available to individuals.",
                "assessee_type"))
        # R026: 80CCD(2) restricted for HUF/Firm
        if ch6a and ch6a.amount_80ccd2 > z:
            results.append(_make(
                "ITR4-R026", False,
                "80CCD(2) is not available to HUFs or Firms.",
                "assessee_type"))
        # R032: 80EE individual/LLP only, not HUF/Firm
        if ch6a and ch6a.amount_80ee > z:
            results.append(_make(
                "ITR4-R032", False,
                "80EE is only available to individuals.",
                "assessee_type"))
        # R050: 87A only for resident individuals
        pass  # Handled in calc_rules
        # R163: 80EEA individual only
        if ch6a and ch6a.amount_80eea > z:
            results.append(_make(
                "ITR4-R163", False,
                "80EEA is only available to individuals.",
                "assessee_type"))
        # R164: 80EEB individual only
        if ch6a and ch6a.amount_80eeb > z:
            results.append(_make(
                "ITR4-R164", False,
                "80EEB is only available to individuals.",
                "assessee_type"))
        # R180: Family pension not for Firm/HUF
        if os_ and os_.family_pension_received > z:
            results.append(_make(
                "ITR4-R180", False,
                "Family pension income cannot be claimed by non-individuals.",
                "assessee_type"))
        # R165 (CBDT Sl 165): HUF/Firm cannot have TDS1 (salary TDS)
        if is_huf or is_firm:
            if inp.tds1_entries and len(inp.tds1_entries) > 0:
                results.append(_make(
                    "ITR4-R165", False,
                    "HUF/Firm cannot claim TDS on salary (TDS1 entries). "
                    "Only resident individuals are eligible for salary TDS (CBDT Sl 165).",
                    "tds1_entries"))
        # R166 (CBDT Sl 166): HUF/Firm cannot have salary income
        if is_huf or is_firm:
            if sal and sal.gross_salary > z:
                results.append(_make(
                    "ITR4-R166", False,
                    "HUF/Firm cannot have salary income (CBDT Sl 166). "
                    "Salary is only for individuals.",
                    "salary_income"))
        # R303 (CBDT Sl 303): Firm cannot fill disallowed schedules
        if is_firm:
            firm_disallowed = []
            if inp.schedule_80c_entries:
                firm_disallowed.append("80C")
            if inp.schedule_80e_entries:
                firm_disallowed.append("80E")
            if inp.loan_details_80ee_list or inp.loan_details_80ee:
                firm_disallowed.append("80EE")
            if inp.loan_details_80eea_list or inp.loan_details_80eea:
                firm_disallowed.append("80EEA")
            if inp.loan_details_80eeb_list or inp.loan_details_80eeb:
                firm_disallowed.append("80EEB")
            if inp.schedule_10_13a:
                firm_disallowed.append("10(13A)")
            if firm_disallowed:
                results.append(_make(
                    "ITR4-R303", False,
                    f"Firm cannot fill these schedules: {', '.join(firm_disallowed)} "
                    f"(CBDT Sl 303).", "assessee_type"))
        # R304 (CBDT Sl 304): HUF cannot fill disallowed schedules
        if is_huf:
            huf_disallowed = []
            if inp.schedule_80ccc_entries:
                huf_disallowed.append("80CCC")
            if inp.schedule_80e_entries:
                huf_disallowed.append("80E")
            if inp.loan_details_80ee_list or inp.loan_details_80ee:
                huf_disallowed.append("80EE")
            if inp.loan_details_80eea_list or inp.loan_details_80eea:
                huf_disallowed.append("80EEA")
            if inp.loan_details_80eeb_list or inp.loan_details_80eeb:
                huf_disallowed.append("80EEB")
            if huf_disallowed:
                results.append(_make(
                    "ITR4-R304", False,
                    f"HUF cannot fill these schedules: {', '.join(huf_disallowed)} "
                    f"(CBDT Sl 304).", "assessee_type"))

    # HUF-specific restrictions (R231, R232)
    if is_huf and ch6a:
        # R232: HUF cannot claim 80D parent insurance (sections 2a/2b)
        if ch6a.amount_80d_parents > z:
            results.append(_make(
                "ITR4-R232", False,
                "HUF cannot claim 80D deduction for parents (sections 2a/2b). "
                "Only self/family premium is allowed.",
                "assessee_type"))

    # ITR-4 eligibility: no LLP
    if assessee == AssesseeType.LLP:
        results.append(_make(
            "ITR4-R235b", False,
            "LLPs are not eligible to file ITR-4. Use ITR-5 instead.",
            "assessee_type"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Section 10 Exempt Allowances Consistency (ITR-4 R100-R115)
    # ═══════════════════════════════════════════════════════════════════════

    if sal:
        if sal.gratuity_received > z and sal.gratuity_received > sal.gross_salary:
            results.append(_make(
                "ITR4-R100", False,
                f"Gratuity exempt amount (Rs {sal.gratuity_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}).",
                "salary_income.gratuity_received",
            ))
        if sal.commuted_pension_received > z and sal.commuted_pension_received > sal.gross_salary:
            results.append(_make(
                "ITR4-R101", False,
                f"Commuted pension (Rs {sal.commuted_pension_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}).",
                "salary_income.commuted_pension_received",
            ))
        if sal.leave_encashment_received > z and sal.leave_encashment_received > sal.gross_salary:
            results.append(_make(
                "ITR4-R102", False,
                f"Leave encashment (Rs {sal.leave_encashment_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}).",
                "salary_income.leave_encashment_received",
            ))
        if sal.vrs_compensation > 500_000:
            results.append(_make(
                "ITR4-R103", False,
                f"VRS compensation exempt amount (Rs {sal.vrs_compensation}) "
                f"exceeds Rs 5,00,000 statutory limit.",
                "salary_income.vrs_compensation",
            ))
        if sal.retrenchment_compensation > Decimal("500000"):
            results.append(_make(
                "ITR4-R159", False,
                f"10(10B) First/Second Proviso: Retrenchment compensation (Rs {sal.retrenchment_compensation}) "
                f"exceeds ₹5,00,000 statutory maximum (CBDT Sl 159 + 226).",
                "salary_income.retrenchment_compensation",
                expected="<= 500000", actual=str(sal.retrenchment_compensation)))
        if sal.transport_allowance > 38_400:
            results.append(_make(
                "ITR4-R105", False,
                f"Transport allowance (Rs {sal.transport_allowance}) exceeds "
                f"Rs 38,400 reasonable annual maximum.",
                "salary_income.transport_allowance",
            ))
        if sal.lta_amount_received > z and sal.lta_exempt_amount == z:
            results.append(_info(
                "ITR4-R106",
                f"LTA received (Rs {sal.lta_amount_received}) but exempt amount is 0.",
                "salary_income.lta_exempt_amount",
            ))
        if sal.lta_exempt_amount > sal.lta_amount_received:
            results.append(_make(
                "ITR4-R107", False,
                f"LTA exempt (Rs {sal.lta_exempt_amount}) exceeds LTA received "
                f"(Rs {sal.lta_amount_received}).",
                "salary_income.lta_exempt_amount",
            ))
        if is_new:
            if sal.gratuity_received > z:
                results.append(_make(
                    "ITR4-R108", False,
                    f"Gratuity exemption not available under new tax regime.",
                    "salary_income.gratuity_received",
                ))
            if sal.commuted_pension_received > z:
                results.append(_make(
                    "ITR4-R109", False,
                    f"Commuted pension exemption not available under new tax regime.",
                    "salary_income.commuted_pension_received",
                ))
            if sal.leave_encashment_received > z:
                results.append(_make(
                    "ITR4-R110", False,
                    f"Leave encashment exemption not available under new tax regime.",
                    "salary_income.leave_encashment_received",
                ))
            if sal.vrs_compensation > z:
                results.append(_make(
                    "ITR4-R111", False,
                    f"VRS compensation exemption not available under new tax regime.",
                    "salary_income.vrs_compensation",
                ))
            if sal.retrenchment_compensation > z:
                results.append(_make(
                    "ITR4-R112", False,
                    f"Retrenchment compensation exemption not available under new tax regime.",
                    "salary_income.retrenchment_compensation",
                ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: ITR-4 Eligibility
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 140: No presumptive scheme selected
    if inp.presumptive_scheme == PresumptiveScheme.NONE:
        results.append(_make(
            "ITR4-R140", False,
            "ITR-4 requires presumptive income under 44AD, 44ADA, or 44AE to be disclosed",
            "presumptive_scheme"))

    # Rule 265: LTCG 112A exceeds Rs 1,25,000
    if cg and cg.ltcg_112a > Decimal("125000"):
        results.append(_make(
            "ITR4-R265", False,
            f"LTCG u/s 112A of Rs {cg.ltcg_112a} exceeds Rs 1,25,000 ITR-4 limit. File ITR-3",
            "capital_gains.ltcg_112a",
            expected="<= 125000", actual=str(cg.ltcg_112a)))



    # Rule 139: Gross receipts mentioned but financial particulars not filled (informational)
    if inp.presumptive_scheme != PresumptiveScheme.NONE:
        if inp.presumptive_scheme == PresumptiveScheme.S44AD and inp.business_income_44ad:
            if inp.business_income_44ad.total_turnover > z:
                results.append(_info(
                    "ITR4-R139a",
                    "Gross receipts disclosed under 44AD. Ensure corresponding financial "
                    "particulars (Schedule BP) are properly filled in the ITR utility.",
                    "business_income_44ad"))
        if inp.presumptive_scheme == PresumptiveScheme.S44ADA and inp.professional_income_44ada:
            if inp.professional_income_44ada.gross_receipts > z:
                results.append(_info(
                    "ITR4-R139b",
                    "Gross receipts disclosed under 44ADA. Ensure corresponding financial "
                    "particulars (Schedule BP) are properly filled in the ITR utility.",
                    "professional_income_44ada"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 44AD — Presumptive Business Income
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 1: Schedule BP must be filled when 44AD claimed
    if inp.presumptive_scheme == PresumptiveScheme.S44AD and inp.business_income_44ad is None:
        results.append(_make(
            "ITR4-R001a", False,
            "44AD scheme selected but business income details (Schedule BP) not provided",
            "business_income_44ad"))

    # Rule 8: Income declared u/s 44AD exceeds gross turnover (informational - flagged)
    if inp.business_income_44ad and inp.business_income_44ad.income_declared is not None:
        ad = inp.business_income_44ad
        if ad.income_declared > ad.total_turnover and ad.total_turnover > z:
            results.append(_make(
                "ITR4-R008", False,
                f"44AD income declared ({ad.income_declared}) exceeds total turnover "
                f"({ad.total_turnover}). Income cannot exceed gross receipts.",
                "business_income_44ad.income_declared",
                expected=f"<= {ad.total_turnover}", actual=str(ad.income_declared)))

    # Rule 9: 44AD turnover exceeds Rs 3 crore
    if inp.business_income_44ad and inp.business_income_44ad.total_turnover > Decimal("30000000"):
        results.append(_make(
            "ITR4-R009", False,
            f"Gross turnover u/s 44AD of Rs {inp.business_income_44ad.total_turnover} "
            f"exceeds Rs 3 crore limit. File ITR-3",
            "business_income_44ad.total_turnover",
            expected="<= 30000000", actual=str(inp.business_income_44ad.total_turnover)))

    # Rule 10: 44AD not for commission/brokerage agents (informational)
    if inp.presumptive_scheme == PresumptiveScheme.S44AD:
        results.append(_info(
            "ITR4-R010",
            "44AD not available for commission agents, brokerage, or insurance agents. "
            "Assessee type (agent/business) not captured in schema.",
            "presumptive_scheme"))

    # Rule 11: Business code mandatory for 44AD — HARD
    if inp.business_income_44ad and inp.business_income_44ad.total_turnover > z:
        if not inp.business_code:
            results.append(_make(
                "ITR4-R011", False,
                "Business code must be provided in Schedule BP when declaring income "
                "under 44AD (CBDT Sl 11).",
                "business_code"))
    # Rule 12: Business code selected → must declare 44AD income — HARD
    if inp.business_code and inp.presumptive_scheme != PresumptiveScheme.S44AD:
        results.append(_make(
            "ITR4-R012", False,
            f"Business code '{inp.business_code}' for 44AD is selected but 44AD scheme "
            f"is not active (CBDT Sl 12).",
            "business_code"))

    # Rule 237: 44AD > Rs 2 crore with cash > 5% → tax audit required
    if inp.business_income_44ad and inp.business_income_44ad.total_turnover > Decimal("20000000"):
        ad = inp.business_income_44ad
        if ad.total_turnover > z:
            cash_ratio = ad.cash_turnover / ad.total_turnover
            if cash_ratio > Decimal("0.05"):
                results.append(_make(
                    "ITR4-R237", False,
                    f"44AD turnover exceeds Rs 2 crore and cash receipts ({ad.cash_turnover}) "
                    f"exceed 5% of turnover. Tax audit u/s 44AB mandatory. File ITR-3",
                    "business_income_44ad",
                    expected="Cash <= 5% of turnover", actual=f"Cash ratio {cash_ratio}"))

    # Rule 239: 44AD turnover split check — digital + cash == total
    if inp.business_income_44ad:
        ad = inp.business_income_44ad
        if ad.digital_turnover + ad.cash_turnover != ad.total_turnover:
            results.append(_make(
                "ITR4-R239", False,
                f"44AD turnover split mismatch: digital ({ad.digital_turnover}) + "
                f"cash ({ad.cash_turnover}) != total ({ad.total_turnover})",
                "business_income_44ad",
                expected=str(ad.total_turnover),
                actual=str(ad.digital_turnover + ad.cash_turnover)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 44ADA — Presumptive Professional Income
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 1: Schedule BP must be filled when 44ADA claimed
    if inp.presumptive_scheme == PresumptiveScheme.S44ADA and inp.professional_income_44ada is None:
        results.append(_make(
            "ITR4-R001b", False,
            "44ADA scheme selected but professional income details (Schedule BP) not provided",
            "professional_income_44ada"))

    # Rule 13: 44ADA income declared exceeds gross receipts
    if inp.professional_income_44ada and inp.professional_income_44ada.income_declared is not None:
        ada = inp.professional_income_44ada
        if ada.income_declared > ada.gross_receipts and ada.gross_receipts > z:
            results.append(_make(
                "ITR4-R013", False,
                f"44ADA income declared ({ada.income_declared}) exceeds gross receipts "
                f"({ada.gross_receipts}). Income cannot exceed gross receipts.",
                "professional_income_44ada.income_declared",
                expected=f"<= {ada.gross_receipts}", actual=str(ada.income_declared)))

    # Rule 15: 44ADA not available for business income (informational)
    if inp.presumptive_scheme == PresumptiveScheme.S44ADA:
        results.append(_info(
            "ITR4-R015",
            "44ADA is only for specified professions (legal, medical, engineering, "
            "architectural, accountancy, technical consultancy, interior decoration). "
            "Profession type not captured in schema.",
            "professional_income_44ada"))

    # Rule 16: Profession code mandatory for 44ADA — HARD
    if inp.professional_income_44ada and inp.professional_income_44ada.gross_receipts > z:
        if not inp.profession_code:
            results.append(_make(
                "ITR4-R016", False,
                "Profession code must be provided in Schedule BP when declaring income "
                "under 44ADA (CBDT Sl 16).",
                "profession_code"))
    # Rule 17: Profession code selected → must declare 44ADA income — HARD
    if inp.profession_code and inp.presumptive_scheme != PresumptiveScheme.S44ADA:
        results.append(_make(
            "ITR4-R017b", False,
            f"Profession code '{inp.profession_code}' for 44ADA is selected but 44ADA "
            f"scheme is not active (CBDT Sl 17).",
            "profession_code"))

    # Rule 212: HUF not eligible for 44ADA — HARD
    if is_huf and inp.presumptive_scheme == PresumptiveScheme.S44ADA:
        results.append(_make(
            "ITR4-R212", False,
            "HUF is not eligible for Section 44ADA presumptive scheme (CBDT Sl 212). "
            "Only resident individuals and partnership firms can opt for 44ADA.",
            "assessee_type"))

    # Rule 238: 44ADA > Rs 50L with cash > 5% → audit required
    if inp.professional_income_44ada and inp.professional_income_44ada.gross_receipts > Decimal("5000000"):
        ada = inp.professional_income_44ada
        if ada.gross_receipts > z:
            cash_ratio = ada.cash_receipts / ada.gross_receipts
            if cash_ratio > Decimal("0.05"):
                results.append(_make(
                    "ITR4-R238", False,
                    f"44ADA gross receipts exceed Rs 50 lakh and cash receipts "
                    f"({ada.cash_receipts}) exceed 5%. Tax audit u/s 44AB mandatory. File ITR-3",
                    "professional_income_44ada",
                    expected="Cash <= 5% of gross receipts", actual=f"Cash ratio {cash_ratio}"))

    # Rule 240: 44ADA gross receipts split check
    if inp.professional_income_44ada:
        ada = inp.professional_income_44ada
        if ada.digital_receipts + ada.cash_receipts != ada.gross_receipts:
            results.append(_make(
                "ITR4-R240", False,
                f"44ADA receipts split mismatch: digital ({ada.digital_receipts}) + "
                f"cash ({ada.cash_receipts}) != total ({ada.gross_receipts})",
                "professional_income_44ada",
                expected=str(ada.gross_receipts),
                actual=str(ada.digital_receipts + ada.cash_receipts)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 44AE — Presumptive Goods Carriage Income
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 1: Schedule BP must be filled when 44AE claimed
    if inp.presumptive_scheme == PresumptiveScheme.S44AE and inp.goods_carriage_44ae is None:
        results.append(_make(
            "ITR4-R001c", False,
            "44AE scheme selected but goods carriage details (Schedule BP) not provided",
            "goods_carriage_44ae"))

    # Rule 135: Presumptive income field (E5) > 0 but 44AE schedule not filed
    # (ITR-4 always has presumptive; check that 44AE data exists when scheme is 44AE)
    if inp.presumptive_scheme == PresumptiveScheme.S44AE:
        ae = inp.goods_carriage_44ae
        if ae and len(ae.vehicles) == 0:
            results.append(_make(
                "ITR4-R135", False,
                "44AE scheme selected but no vehicles listed in goods carriage schedule",
                "goods_carriage_44ae.vehicles"))

    # Rule 137: Business code mandatory for 44AE — HARD
    if inp.goods_carriage_44ae and len(inp.goods_carriage_44ae.vehicles) > 0:
        if not inp.business_code:
            results.append(_make(
                "ITR4-R137", False,
                "Business code must be provided in Schedule BP when declaring income "
                "under 44AE (CBDT Sl 137).",
                "business_code"))
    # Rule 138: Business code selected → must declare 44AE income — HARD
    if inp.business_code and inp.presumptive_scheme not in (PresumptiveScheme.S44AE, PresumptiveScheme.S44AD):
        if inp.presumptive_scheme != PresumptiveScheme.S44AE:
            results.append(_make(
                "ITR4-R138a", False,
                f"Business code '{inp.business_code}' for 44AE is selected but 44AE scheme "
                f"is not active (CBDT Sl 138).",
                "business_code"))

    # Rule 141: Per-vehicle months owned > 12; total months across vehicles > 120
    if inp.goods_carriage_44ae:
        total_months = 0
        for i, v in enumerate(inp.goods_carriage_44ae.vehicles):
            if v.months_owned > 12:
                results.append(_make(
                    "ITR4-R141a", False,
                    f"Vehicle {i+1}: months owned ({v.months_owned}) exceeds 12",
                    f"goods_carriage_44ae.vehicles[{i}].months_owned",
                    expected="<= 12", actual=str(v.months_owned)))
            total_months += v.months_owned
        if total_months > 120:
            results.append(_make(
                "ITR4-R141b", False,
                f"Total months owned across all vehicles ({total_months}) exceeds 120 "
                f"({len(inp.goods_carriage_44ae.vehicles)} vehicles × 12 months max)",
                "goods_carriage_44ae.vehicles"))

    # Rule 144: Per-vehicle minimum income check (declared >= statutory)
    if inp.goods_carriage_44ae:
        for i, v in enumerate(inp.goods_carriage_44ae.vehicles):
            declared = v.income_declared
            if declared is not None and declared > z:
                if v.is_heavy_goods_vehicle:
                    wt = v.gross_vehicle_weight_tons or z
                    statutory = Decimal("1000") * wt * Decimal(v.months_owned)
                else:
                    statutory = Decimal("7500") * Decimal(v.months_owned)
                if declared < statutory:
                    results.append(_make(
                        "ITR4-R144", False,
                        f"Vehicle {i+1}: declared income ({declared}) is below "
                        f"statutory presumptive minimum ({statutory})",
                        f"goods_carriage_44ae.vehicles[{i}].income_declared",
                        expected=f">= {statutory}", actual=str(declared)))



    # ═══════════════════════════════════════════════════════════════════════
    # NOTE: Firm/HUF/Non-individual restrictions (R020-R032, R043, R050, R163-R164,
    # R180, R231-R232, R254, R303-R304) are enforced as HARD Severity A checks at
    # the top of this file. No redundant informational duplicates needed.
    # ═══════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Deduction Limits — Old Regime
    # ═══════════════════════════════════════════════════════════════════════

    if is_old and ch6a:

        # Rule 21: 80C + 80CCC + 80CCD(1) <= Rs 1,50,000
        pool_80c = ch6a.amount_80c + ch6a.amount_80ccc + ch6a.amount_80ccd1
        if pool_80c > Decimal("150000"):
            results.append(_make(
                "ITR4-R021", False,
                f"80C + 80CCC + 80CCD(1) total ({pool_80c}) exceeds Rs 1,50,000 "
                f"combined limit u/s 80CCE",
                "deductions_chapter6a",
                expected="<= 150000", actual=str(pool_80c)))

        # Rule 22: 80CCD(1) pensioner cap — enforce if nature_of_employment available
        if ch6a.amount_80ccd1 > z:
            emp = inp.nature_of_employment or ""
            if "pension" in emp.lower():
                gti_14 = max((sal.gross_salary if sal else z), z)  # GTI approx at input level
                max_pensioner = gti_14 * Decimal("0.20")
                if ch6a.amount_80ccd1 > max_pensioner:
                    results.append(_make(
                        "ITR4-R022a", False,
                        f"80CCD(1) for pensioner capped at 20% of gross salary. "
                        f"Claimed: Rs {ch6a.amount_80ccd1}, limit: Rs {max_pensioner}",
                        "deductions_chapter6a.amount_80ccd1",
                        expected=f"<= {max_pensioner}", actual=str(ch6a.amount_80ccd1)))
            # Rule 155: 80CCD(1) non-pensioner/non-salaried ≤ 10% salary (hard enforcement)
        if ch6a.amount_80ccd1 > z and is_old:
            emp = inp.nature_of_employment or ""
            if "pension" not in emp.lower():
                # For salaried: 10% of salary; for others: capped at 10% of estimated GTI
                base_salary = sal.gross_salary if sal else z
                cap_10pct = base_salary * Decimal("0.10")
                if cap_10pct > z and ch6a.amount_80ccd1 > cap_10pct:
                    results.append(_make(
                        "ITR4-R155", False,
                        f"80CCD(1) for non-pensioner capped at 10% of salary "
                        f"(Rs {cap_10pct}). Claimed: Rs {ch6a.amount_80ccd1}",
                        "deductions_chapter6a.amount_80ccd1",
                        expected=f"<= {cap_10pct}", actual=str(ch6a.amount_80ccd1)))

        # Rule 25: 80CCD(2) non-CG/SG <= 10% salary (HARD enforcement)
        if ch6a.amount_80ccd2 > z and is_old:
            emp = inp.nature_of_employment or ""
            if "central government" not in emp.lower() and "state government" not in emp.lower():
                base_salary = sal.gross_salary if sal else z
                cap_10pct = base_salary * Decimal("0.10")
                if cap_10pct > z and ch6a.amount_80ccd2 > cap_10pct:
                    results.append(_make(
                        "ITR4-R025", False,
                        f"80CCD(2) for non-CG/SG employee capped at 10% of salary "
                        f"(Rs {cap_10pct}). Claimed: Rs {ch6a.amount_80ccd2}. "
                        f"Employment: {inp.nature_of_employment}",
                        "deductions_chapter6a.amount_80ccd2",
                        expected=f"<= {cap_10pct}", actual=str(ch6a.amount_80ccd2)))
                elif cap_10pct == z:
                    results.append(_info(
                        "ITR4-R025i",
                        f"80CCD(2) claimed Rs {ch6a.amount_80ccd2} but no salary to compute "
                        f"10% cap. Verify actual salary+DA for NPS employer contribution.",
                        "deductions_chapter6a.amount_80ccd2"))

        # Rule 47: 80CCD(2) CG/SG <= 14% salary (HARD enforcement)
        if ch6a.amount_80ccd2 > z and is_old:
            emp = inp.nature_of_employment or ""
            if "central government" in emp.lower() or "state government" in emp.lower():
                base_salary = sal.gross_salary if sal else z
                cap_14pct = base_salary * Decimal("0.14")
                if cap_14pct > z and ch6a.amount_80ccd2 > cap_14pct:
                    results.append(_make(
                        "ITR4-R047", False,
                        f"80CCD(2) for CG/SG employee capped at 14% of salary "
                        f"(Rs {cap_14pct}). Claimed: Rs {ch6a.amount_80ccd2}. "
                        f"Employment: {inp.nature_of_employment}",
                        "deductions_chapter6a.amount_80ccd2",
                        expected=f"<= {cap_14pct}", actual=str(ch6a.amount_80ccd2)))

        # Rule 263: New regime 80CCD(2) <= 14% for PSU/Others/CG/SG
        if ch6a.amount_80ccd2 > z and is_new:
            base_salary = sal.gross_salary if sal else z
            cap_14_new = base_salary * Decimal("0.14")
            if cap_14_new > z and ch6a.amount_80ccd2 > cap_14_new:
                results.append(_make(
                    "ITR4-R263", False,
                    f"80CCD(2) new regime: capped at 14% of salary "
                    f"(Rs {cap_14_new}). Claimed: Rs {ch6a.amount_80ccd2}",
                    "deductions_chapter6a.amount_80ccd2",
                    expected=f"<= {cap_14_new}", actual=str(ch6a.amount_80ccd2)))

        # Rule 145: 80CCD(1B) <= Rs 50,000
        if ch6a.amount_80ccd1b > Decimal("50000"):
            results.append(_make(
                "ITR4-R145", False,
                f"80CCD(1B) deduction ({ch6a.amount_80ccd1b}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ccd1b",
                expected="<= 50000", actual=str(ch6a.amount_80ccd1b)))

        # Rule 146: 80DD disability fixed amount = Rs 75,000 (informational)
        if ch6a.amount_80dd > z:
            results.append(_info(
                "ITR4-R546",
                "80DD deduction is Rs 75,000 for normal disability and Rs 1,25,000 "
                "for severe disability. The schema captures the claimed amount but not "
                "the disability severity level.",
                "deductions_chapter6a.amount_80dd"))

        # Rule 147: 80DD severe max Rs 1,25,000
        if ch6a.amount_80dd > Decimal("125000"):
            results.append(_make(
                "ITR4-R147", False,
                f"80DD deduction ({ch6a.amount_80dd}) exceeds Rs 1,25,000 maximum "
                f"(even for severe disability)",
                "deductions_chapter6a.amount_80dd",
                expected="<= 125000", actual=str(ch6a.amount_80dd)))

        # Rule 148: 80DDB non-senior <= Rs 40,000
        if not is_senior and ch6a.amount_80ddb > Decimal("40000"):
            results.append(_make(
                "ITR4-R148", False,
                f"80DDB deduction ({ch6a.amount_80ddb}) exceeds Rs 40,000 limit "
                f"for non-senior citizens",
                "deductions_chapter6a.amount_80ddb",
                expected="<= 40000", actual=str(ch6a.amount_80ddb)))

        # Rule 149: 80DDB senior <= Rs 1,00,000
        if is_senior and ch6a.amount_80ddb > Decimal("100000"):
            results.append(_make(
                "ITR4-R149", False,
                f"80DDB deduction ({ch6a.amount_80ddb}) exceeds Rs 1,00,000 limit "
                f"for senior citizens",
                "deductions_chapter6a.amount_80ddb",
                expected="<= 100000", actual=str(ch6a.amount_80ddb)))

        # Rule 150: 80EE <= Rs 50,000
        if ch6a.amount_80ee > Decimal("50000"):
            results.append(_make(
                "ITR4-R150", False,
                f"80EE deduction ({ch6a.amount_80ee}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ee",
                expected="<= 50000", actual=str(ch6a.amount_80ee)))

        # Rule 152: 80TTA <= Rs 10,000
        if ch6a.amount_80tta > Decimal("10000"):
            results.append(_make(
                "ITR4-R152", False,
                f"80TTA deduction ({ch6a.amount_80tta}) exceeds Rs 10,000 limit",
                "deductions_chapter6a.amount_80tta",
                expected="<= 10000", actual=str(ch6a.amount_80tta)))

        # Rule 153: 80TTB <= Rs 50,000
        if ch6a.amount_80ttb > Decimal("50000"):
            results.append(_make(
                "ITR4-R153", False,
                f"80TTB deduction ({ch6a.amount_80ttb}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ttb",
                expected="<= 50000", actual=str(ch6a.amount_80ttb)))

        # Rule 155: 80CCD(1) non-pensioner <= 10% GTI (informational)
        if ch6a.amount_80ccd1 > z:
            results.append(_info(
                "ITR4-R455",
                "80CCD(1) for non-salaried/non-pensioner assessees capped at 10% of GTI. "
                "Employment category not captured in schema.",
                "deductions_chapter6a.amount_80ccd1"))

        # Rule 156: 80EEA <= Rs 1,50,000
        if ch6a.amount_80eea > Decimal("150000"):
            results.append(_make(
                "ITR4-R156", False,
                f"80EEA deduction ({ch6a.amount_80eea}) exceeds Rs 1,50,000 limit",
                "deductions_chapter6a.amount_80eea",
                expected="<= 150000", actual=str(ch6a.amount_80eea)))

        # Rule 157: 80EE / 80EEA mutual exclusion
        if ch6a.amount_80ee > z and ch6a.amount_80eea > z:
            results.append(_make(
                "ITR4-R157", False,
                "Both 80EE and 80EEA cannot be claimed simultaneously for the same "
                "property. Only one deduction is allowed.",
                "deductions_chapter6a"))

        # Rule 158: 80EEB <= Rs 1,50,000
        if ch6a.amount_80eeb > Decimal("150000"):
            results.append(_make(
                "ITR4-R158", False,
                f"80EEB deduction ({ch6a.amount_80eeb}) exceeds Rs 1,50,000 limit",
                "deductions_chapter6a.amount_80eeb",
                expected="<= 150000", actual=str(ch6a.amount_80eeb)))

        # Rule 161: 80CCD(2) not for pensioners (HARD enforcement)
        if ch6a.amount_80ccd2 > z:
            emp = inp.nature_of_employment or ""
            if "pension" in emp.lower():
                results.append(_make(
                    "ITR4-R161", False,
                    f"80CCD(2) NPS employer contribution not available for pensioners. "
                    f"Employment: {inp.nature_of_employment}",
                    "deductions_chapter6a.amount_80ccd2",
                    expected="0 for pensioners", actual=str(ch6a.amount_80ccd2)))

        # Rule 168: 80D self/family non-senior <= Rs 25,000
        if ch6a.amount_80d_self_family > Decimal("25000") and not is_senior:
            results.append(_make(
                "ITR4-R168", False,
                f"80D Self/Family ({ch6a.amount_80d_self_family}) exceeds Rs 25,000 "
                f"limit for non-senior citizens",
                "deductions_chapter6a.amount_80d_self_family",
                expected="<= 25000", actual=str(ch6a.amount_80d_self_family)))

        # Rule 170: Preventive health checkup component within 80D <= Rs 5,000
        if inp.schedule_80d:
            sd = inp.schedule_80d
            if sd.preventive_checkup_self > Decimal("5000"):
                results.append(_make(
                    "ITR4-R170a", False,
                    f"Preventive health checkup for self/family (Rs {sd.preventive_checkup_self}) "
                    f"exceeds Rs 5,000 cap",
                    "schedule_80d.preventive_checkup_self",
                    expected="<= 5000", actual=str(sd.preventive_checkup_self)))
            if sd.preventive_checkup_parents > Decimal("5000"):
                results.append(_make(
                    "ITR4-R170b", False,
                    f"Preventive health checkup for parents (Rs {sd.preventive_checkup_parents}) "
                    f"exceeds Rs 5,000 cap",
                    "schedule_80d.preventive_checkup_parents",
                    expected="<= 5000", actual=str(sd.preventive_checkup_parents)))

        # Rule 171: 80D self/family senior <= Rs 50,000
        if ch6a.amount_80d_self_family > Decimal("50000"):
            results.append(_make(
                "ITR4-R171", False,
                f"80D Self/Family ({ch6a.amount_80d_self_family}) exceeds Rs 50,000 "
                f"limit for senior citizen self/family",
                "deductions_chapter6a.amount_80d_self_family",
                expected="<= 50000", actual=str(ch6a.amount_80d_self_family)))

        # Rule 173: 80D parents non-senior <= Rs 25,000
        if ch6a.amount_80d_parents > Decimal("25000"):
            results.append(_make(
                "ITR4-R173", False,
                f"80D Parents ({ch6a.amount_80d_parents}) exceeds applicable limit. "
                f"Non-senior parents cap: Rs 25,000",
                "deductions_chapter6a.amount_80d_parents",
                expected="<= 50000 (senior) / <= 25000 (non-senior)",
                actual=str(ch6a.amount_80d_parents)))

        # Rule 175: 80D parents senior <= Rs 50,000
        if ch6a.amount_80d_parents > Decimal("50000"):
            results.append(_make(
                "ITR4-R175", False,
                f"80D Parents ({ch6a.amount_80d_parents}) exceeds Rs 50,000 "
                f"maximum for senior citizen parents",
                "deductions_chapter6a.amount_80d_parents",
                expected="<= 50000", actual=str(ch6a.amount_80d_parents)))

        # Rule 177: 80D combined total <= Rs 1,00,000
        d80_combined = ch6a.amount_80d_self_family + ch6a.amount_80d_parents
        if d80_combined > Decimal("100000"):
            results.append(_make(
                "ITR4-R177", False,
                f"80D total deduction ({d80_combined}) exceeds Rs 1,00,000 "
                f"combined limit",
                "deductions_chapter6a",
                expected="<= 100000", actual=str(d80_combined)))

        # Rule 179: 80D claimed but detailed schedule not provided — enforce
        if ch6a.amount_80d_self_family > z or ch6a.amount_80d_parents > z:
            if not inp.schedule_80d:
                results.append(_make(
                    "ITR4-R179", False,
                    "80D deduction claimed but Schedule 80D (health insurance details) not "
                    "provided. Policy numbers, premium paid, and insured persons are required.",
                    "schedule_80d",
                ))
            else:
                # Rule 179b: 80D VIA total must match Schedule 80D total (match ITR-1 R138)
                sd = inp.schedule_80d
                d_total = ch6a.amount_80d_self_family + ch6a.amount_80d_parents
                sch_total = (sd.premium_1a_non_senior + sd.premium_1b_senior
                             + sd.premium_2a_parents_non_senior + sd.premium_2b_parents_senior
                             + sd.preventive_checkup_self + sd.preventive_checkup_parents)
                if d_total != sch_total:
                    results.append(_make(
                        "ITR4-R179b", False,
                        f"80D VIA total (Rs {d_total}) does not match Schedule 80D total "
                        f"(Rs {sch_total})",
                        "deductions_chapter6a",
                        expected=str(sch_total), actual=str(d_total)))

                # ---- Per-policy enforcement (ITR-4 equivalents of R128/R131/R133/R135/R137/R256-R259) ----
                if sd.policies:
                    from collections import defaultdict
                    section_sums: dict = defaultdict(lambda: Decimal("0"))
                    for pol in sd.policies:
                        sec = pol.section
                        section_sums[sec] += pol.premium_paid

                        # Cash-mode premium not allowed for 80D
                        if pol.payment_mode_cash and pol.premium_paid > 0:
                            results.append(_make(
                                "ITR4-R437", False,
                                f"80D policy in section {sec}: premium of Rs {pol.premium_paid} "
                                f"paid in cash. Cash payments are NOT eligible for 80D deduction.",
                                "schedule_80d.policies",
                            ))

                        # Insurer name + policy number required if premium > 0
                        if pol.premium_paid > 0 and (not pol.insurer_name or not pol.policy_number):
                            results.append(_make(
                                "ITR4-R256" if sec == "1a" else
                                "ITR4-R257" if sec == "1b" else
                                "ITR4-R258" if sec == "2a" else "ITR4-R259", False,
                                f"80D section {sec}: premium of Rs {pol.premium_paid} claimed "
                                f"but insurer name ('{pol.insurer_name}') or policy number "
                                f"('{pol.policy_number}') is missing.",
                                "schedule_80d.policies",
                            ))

                    # Per-section sum must match Schedule 80D aggregate fields
                    if section_sums["1a"] != sd.premium_1a_non_senior and sd.premium_1a_non_senior > 0:
                        results.append(_make(
                            "ITR4-R128", False,
                            f"80D 1a: sum of per-policy premiums (Rs {section_sums['1a']}) "
                            f"!= Schedule 80D premium_1a_non_senior "
                            f"(Rs {sd.premium_1a_non_senior})",
                            "schedule_80d.premium_1a_non_senior",
                        ))
                    if section_sums["1b"] != sd.premium_1b_senior and sd.premium_1b_senior > 0:
                        results.append(_make(
                            "ITR4-R131", False,
                            f"80D 1b: sum of per-policy premiums (Rs {section_sums['1b']}) "
                            f"!= Schedule 80D premium_1b_senior "
                            f"(Rs {sd.premium_1b_senior})",
                            "schedule_80d.premium_1b_senior",
                        ))
                    if section_sums["2a"] != sd.premium_2a_parents_non_senior and sd.premium_2a_parents_non_senior > 0:
                        results.append(_make(
                            "ITR4-R133", False,
                            f"80D 2a: sum of per-policy premiums (Rs {section_sums['2a']}) "
                            f"!= Schedule 80D premium_2a_parents_non_senior "
                            f"(Rs {sd.premium_2a_parents_non_senior})",
                            "schedule_80d.premium_2a_parents_non_senior",
                        ))
                    if section_sums["2b"] != sd.premium_2b_parents_senior and sd.premium_2b_parents_senior > 0:
                        results.append(_make(
                            "ITR4-R435", False,
                            f"80D 2b: sum of per-policy premiums (Rs {section_sums['2b']}) "
                            f"!= Schedule 80D premium_2b_parents_senior "
                            f"(Rs {sd.premium_2b_parents_senior})",
                            "schedule_80d.premium_2b_parents_senior",
                        ))

        # Rule 42 (normal) + 182 (severe): 80U per-category fixed amounts
        if inp.schedule_80u and inp.schedule_80u.disability_type:
            dtype = inp.schedule_80u.disability_type.lower()
            if "severe" in dtype:
                # CBDT Sl 182: Severe disability → exactly ₹1,25,000
                if ch6a.amount_80u != Decimal("125000"):
                    results.append(_make(
                        "ITR4-R182", False,
                        f"80U severe disability: amount must be exactly Rs 1,25,000. "
                        f"Claimed: Rs {ch6a.amount_80u}",
                        "deductions_chapter6a.amount_80u",
                        expected="125000", actual=str(ch6a.amount_80u)))
            else:
                # CBDT Sl 42: Normal disability → exactly ₹75,000
                if ch6a.amount_80u != Decimal("75000"):
                    results.append(_make(
                        "ITR4-R042", False,
                        f"80U disability: amount must be exactly Rs 75,000. "
                        f"Claimed: Rs {ch6a.amount_80u}",
                        "deductions_chapter6a.amount_80u",
                        expected="75000", actual=str(ch6a.amount_80u)))
        else:
            # No disability_type in schedule — fallback generic check
            if ch6a.amount_80u > Decimal("125000"):
                results.append(_make(
                    "ITR4-R182", False,
                    f"80U deduction ({ch6a.amount_80u}) exceeds Rs 1,25,000 maximum",
                    "deductions_chapter6a.amount_80u",
                    expected="<= 125000", actual=str(ch6a.amount_80u)))
            elif ch6a.amount_80u > z and ch6a.amount_80u not in (Decimal("75000"), Decimal("125000")):
                results.append(_make(
                    "ITR4-R182b", False,
                    f"80U amount (Rs {ch6a.amount_80u}) must be exactly Rs 75,000 "
                    f"(normal disability) or Rs 1,25,000 (severe disability). "
                    f"Specify disability_type in Schedule 80U.",
                    "deductions_chapter6a.amount_80u"))
        # NOTE: R287 (generic Form 10-IA check) removed — R252 (80DD-specific) and
        # R253 (80U-specific) in the NEW VALIDATORS section provide better granularity.

        # Rule 146/147 (CBDT Sl 146-147): 80DD per-category fixed amounts
        if inp.schedule_80dd and inp.schedule_80dd.disability_type:
            dtype_dd = inp.schedule_80dd.disability_type.lower()
            if "severe" in dtype_dd:
                # CBDT Sl 147: Severe disability → exactly ₹1,25,000
                if ch6a.amount_80dd != Decimal("125000"):
                    results.append(_make(
                        "ITR4-R147", False,
                        f"80DD severe disability: amount must be exactly Rs 1,25,000. "
                        f"Claimed: Rs {ch6a.amount_80dd}",
                        "deductions_chapter6a.amount_80dd",
                        expected="125000", actual=str(ch6a.amount_80dd)))
            else:
                # CBDT Sl 146: Normal disability → exactly ₹75,000
                if ch6a.amount_80dd != Decimal("75000"):
                    results.append(_make(
                        "ITR4-R146", False,
                        f"80DD disability: amount must be exactly Rs 75,000. "
                        f"Claimed: Rs {ch6a.amount_80dd}",
                        "deductions_chapter6a.amount_80dd",
                        expected="75000", actual=str(ch6a.amount_80dd)))
        else:
            # Fallback — check amount is one of the two legal values
            if ch6a.amount_80dd > z and ch6a.amount_80dd not in (Decimal("75000"), Decimal("125000")):
                results.append(_make(
                    "ITR4-R446", False,
                    f"80DD amount (Rs {ch6a.amount_80dd}) must be exactly Rs 75,000 "
                    f"(dependent with disability) or Rs 1,25,000 (dependent with severe "
                    f"disability). Specify disability_type in Schedule 80DD.",
                    "deductions_chapter6a.amount_80dd"))
            if not inp.form_10ia_filed:
                results.append(_make(
                    "ITR4-R287b", False,
                    "80DD claimed but Form 10-IA (disability certificate) not filed. "
                    "Form 10-IA is mandatory for 80DD.",
                    "form_10ia_filed",
                ))

        # Rule 224: 80CCH <= 46.2% salary, max Rs 2,88,000 (informational)
        if ch6a.amount_80cch > z:
            # Rule 224: 80CCH ≤ 46.2% salary, max Rs 2,88,000 — enforce
            salary_17_1 = sal.gross_salary if sal else z
            max_80cch = min(Decimal("288000"), Decimal("0.462") * salary_17_1) if salary_17_1 > z else Decimal("288000")
            if ch6a.amount_80cch > max_80cch and max_80cch > z:
                results.append(_make(
                    "ITR4-R224", False,
                    f"80CCH contribution (Rs {ch6a.amount_80cch}) exceeds 46.2% of "
                    f"salary u/s 17(1) capped at Rs 2,88,000. Maximum allowed: Rs {max_80cch}",
                    "deductions_chapter6a.amount_80cch",
                    expected=f"<= {max_80cch}", actual=str(ch6a.amount_80cch)))
            # Rule 225: 80CCH requires Central Government employment — enforce
            if inp.nature_of_employment != "Central Government":
                results.append(_make(
                    "ITR4-R225", False,
                    "80CCH (Agniveer Corpus Fund) is only available to Central Government "
                    f"employees. Current nature of employment: {inp.nature_of_employment or 'Not specified'}",
                    "nature_of_employment",
                    expected="Central Government", actual=str(inp.nature_of_employment or "None")))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: New Regime Restrictions
    # ═══════════════════════════════════════════════════════════════════════

    if is_new:

        # Rule 183: Most deductions must be 0 (only 80CCD(2) and 80CCH allowed)
        if ch6a:
            disallowed_fields = [
                ("amount_80c", "80C"),
                ("amount_80ccc", "80CCC"),
                ("amount_80ccd1", "80CCD(1)"),
                ("amount_80ccd1b", "80CCD(1B)"),
                ("amount_80d_self_family", "80D Self/Family"),
                ("amount_80d_parents", "80D Parents"),
                ("amount_80tta", "80TTA"),
                ("amount_80ttb", "80TTB"),
                ("amount_80e", "80E"),
                ("amount_80dd", "80DD"),
                ("amount_80ddb", "80DDB"),
                ("amount_80u", "80U"),
                ("amount_80ee", "80EE"),
                ("amount_80eea", "80EEA"),
                ("amount_80eeb", "80EEB"),
                ("amount_80g", "80G"),
                ("amount_80gg", "80GG"),
                ("amount_80gga", "80GGA"),
                ("amount_80ggc", "80GGC"),
            ]
            for field, label in disallowed_fields:
                val = getattr(ch6a, field, z)
                if val > z:
                    results.append(_make(
                        "ITR4-R183", False,
                        f"New Tax Regime (Section 115BAC) disallows deduction under "
                        f"{label}. Claimed: Rs {val}. Only 80CCD(2) and 80CCH are allowed.",
                        f"deductions_chapter6a.{field}",
                        expected="0", actual=str(val)))

        # Rule 184: New regime exempt allowances must be 0 (informational)
        if sal and (sal.hra_exempt_amount > z or sal.lta_exempt_amount > z):
            results.append(_info(
                "ITR4-R184",
                f"New Tax Regime disallows HRA (Rs {sal.hra_exempt_amount}) and "
                f"LTA (Rs {sal.lta_exempt_amount}) exemptions. These should be 0 "
                f"under Section 115BAC.",
                "salary_income"))

        # NOTE: Individual new regime deduction rules (R189-R211) are covered
        # by the unified R183 loop above which blocks ALL disallowed deductions
        # with individual field names. No redundant per-rule duplicates needed.

        # Rule 195: New regime professional tax must be 0
        if sal and sal.professional_tax_paid > z:
            results.append(_make(
                "ITR4-R195", False,
                f"Professional tax u/s 16(iii) is not allowed under new tax regime. "
                f"Claimed: Rs {sal.professional_tax_paid}",
                "salary_income.professional_tax_paid",
                expected="0", actual=str(sal.professional_tax_paid)))

        # Rule 198: LTA must be 0 under new regime
        if sal and sal.lta_exempt_amount > z:
            results.append(_make(
                "ITR4-R198", False,
                f"LTA exemption is not allowed under new tax regime. "
                f"Claimed: Rs {sal.lta_exempt_amount}",
                "salary_income.lta_exempt_amount",
                expected="0", actual=str(sal.lta_exempt_amount)))

        # Rule 199: HRA must be 0 under new regime
        if sal and sal.hra_exempt_amount > z:
            results.append(_make(
                "ITR4-R199", False,
                f"HRA exemption is not allowed under new tax regime. "
                f"Claimed: Rs {sal.hra_exempt_amount}",
                "salary_income.hra_exempt_amount",
                expected="0", actual=str(sal.hra_exempt_amount)))







        # Rule 207/302: Self-occupied HP interest must be 0 under new regime
        # R207/R302: New regime self-occupied HP interest must be 0
        if hp and hp.property_type == PropertyType.SELF_OCCUPIED and hp.home_loan_interest_paid > z:
            results.append(_make(
                "ITR4-R207", False,
                f"Self-occupied property interest ({hp.home_loan_interest_paid}) "
                f"is not allowed under new tax regime (R207+R302 combined)",
                "house_property_income.home_loan_interest_paid",
                expected="0", actual=str(hp.home_loan_interest_paid)))

        # Rule 305 (CBDT Sl 305): Individual new regime cannot fill disallowed schedules — HARD
        if is_individual and is_new:
            schedule_checks = [
                (inp.schedule_80c_entries, "Schedule 80C"),
                (inp.schedule_80e_entries, "Schedule 80E"),
                (inp.loan_details_80ee_list or ([inp.loan_details_80ee] if inp.loan_details_80ee else []), "Schedule 80EE"),
                (inp.loan_details_80eea_list or ([inp.loan_details_80eea] if inp.loan_details_80eea else []), "Schedule 80EEA"),
                (inp.loan_details_80eeb_list or ([inp.loan_details_80eeb] if inp.loan_details_80eeb else []), "Schedule 80EEB"),
                (inp.schedule_10_13a, "Schedule 10(13A)"),
            ]
            for entries, name in schedule_checks:
                if entries and (isinstance(entries, list) and len(entries) > 0) or \
                   (not isinstance(entries, list) and entries):
                    results.append(_make(
                        "ITR4-R305", False,
                        f"New tax regime: {name} is populated but not allowed under "
                        f"Section 115BAC (CBDT Sl 305).",
                        "tax_regime"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: House Property Validations
    # ═══════════════════════════════════════════════════════════════════════

    if hp:
        # Rule 55: NAV check — Annual Value = Rent minus Municipal Tax
        if hp.property_type in (PropertyType.LET_OUT, PropertyType.DEEMED_LET_OUT):
            nav = hp.annual_rent_received - hp.municipal_taxes_paid
            if nav <= z:
                results.append(_make(
                    "ITR4-R055", False,
                    f"Net Annual Value ({nav}) should be positive for let-out property. "
                    f"Gross rent: {hp.annual_rent_received}, "
                    f"Municipal tax: {hp.municipal_taxes_paid}",
                    "house_property_income"))

        # Rule 58: Municipal tax claimed when rent is 0 (already implied, made explicit)
        if hp.municipal_taxes_paid > z and hp.annual_rent_received <= z:
            results.append(_make(
                "ITR4-R058", False,
                "Municipal tax cannot be claimed when gross rent is 0 or nil",
                "house_property_income.municipal_taxes_paid",
                expected="0 if rent is 0", actual=str(hp.municipal_taxes_paid)))

        # Rule 59: Let-out/deemed must have rent > 0
        if hp.property_type in (PropertyType.LET_OUT, PropertyType.DEEMED_LET_OUT):
            if hp.annual_rent_received <= z:
                results.append(_make(
                    "ITR4-R059", False,
                    "Annual rent received must be greater than 0 for let-out or "
                    "deemed let-out property",
                    "house_property_income.annual_rent_received",
                    expected="> 0", actual=str(hp.annual_rent_received)))

        # Rule 61: Municipal tax not for self-occupied
        if hp.property_type == PropertyType.SELF_OCCUPIED and hp.municipal_taxes_paid > z:
            results.append(_make(
                "ITR4-R061", False,
                "Municipal taxes cannot be deducted for self-occupied property",
                "house_property_income.municipal_taxes_paid",
                expected="0", actual=str(hp.municipal_taxes_paid)))

        # Rule 154: Self-occupied interest <= Rs 2,00,000 (old regime)
        if is_old and hp.property_type == PropertyType.SELF_OCCUPIED:
            if hp.home_loan_interest_paid > Decimal("200000"):
                results.append(_make(
                    "ITR4-R154", False,
                    f"Self-occupied property interest ({hp.home_loan_interest_paid}) "
                    f"exceeds Rs 2,00,000 cap u/s 24(b) under old regime",
                    "house_property_income.home_loan_interest_paid",
                    expected="<= 200000", actual=str(hp.home_loan_interest_paid)))

        # Rule 323: Property type mandatory if 24(b) interest claimed (informational)
        if hp.home_loan_interest_paid > z:
            results.append(_info(
                "ITR4-R323",
                f"Home loan interest of Rs {hp.home_loan_interest_paid} claimed. "
                f"Ensure property type (self-occupied/let-out) is correctly selected "
                f"and interest certificate is available. Property subtype details "
                f"(co-ownership percentage, date of acquisition) not in schema.",
                "house_property_income"))

        # NOTE: Co-ownership hard checks (R346-R351) are in the NEW VALIDATORS section.

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Salary Validations
    # ═══════════════════════════════════════════════════════════════════════

    if sal:
        # Rule 67: Entertainment allowance cap for govt employees: min(5000, 1/5 salary)
        if sal.entertainment_allowance > z:
            if not sal.is_government_employee:
                results.append(_make(
                    "ITR4-R068", False,
                    "Entertainment allowance u/s 16(ii) is available only to "
                    "Government employees",
                    "salary_income.entertainment_allowance",
                    expected="0 for non-govt", actual=str(sal.entertainment_allowance)))
            else:
                one_fifth_salary = sal.gross_salary / Decimal("5")
                actual_cap = min(Decimal("5000"), one_fifth_salary)
                if sal.entertainment_allowance > actual_cap:
                    results.append(_make(
                        "ITR4-R067", False,
                        f"Entertainment allowance u/s 16(ii) capped at min(Rs 5,000, 1/5 of salary) "
                        f"= Rs {actual_cap}. Claimed: Rs {sal.entertainment_allowance} "
                        f"(salary: Rs {sal.gross_salary}, 1/5 salary: Rs {one_fifth_salary})",
                        "salary_income.entertainment_allowance",
                        expected=f"<= {actual_cap}", actual=str(sal.entertainment_allowance)))

        # Rule 143: Standard deduction old regime max Rs 50,000
        if is_old and sal.standard_deduction_claimed > Decimal("50000"):
            results.append(_make(
                "ITR4-R143", False,
                f"Standard deduction in old regime ({sal.standard_deduction_claimed}) "
                f"exceeds Rs 50,000 limit u/s 16(ia)",
                "salary_income.standard_deduction_claimed",
                expected="<= 50000", actual=str(sal.standard_deduction_claimed)))

        # Rule 262: Standard deduction new regime max Rs 75,000
        if is_new and sal.standard_deduction_claimed > Decimal("75000"):
            results.append(_make(
                "ITR4-R262", False,
                f"Standard deduction in new regime ({sal.standard_deduction_claimed}) "
                f"exceeds Rs 75,000 limit u/s 16(ia)",
                "salary_income.standard_deduction_claimed",
                expected="<= 75000", actual=str(sal.standard_deduction_claimed)))

        # Rule 255: Nature of employment mandatory with salary — enforce
        if sal.gross_salary > z:
            if not inp.nature_of_employment:
                results.append(_make(
                    "ITR4-R255", False,
                    "Salary income is present but nature of employment is not specified. "
                    "Nature of employment (Central Govt, State Govt, PSU, Private, Pensioner, etc.) "
                    "is mandatory in ITR form.",
                    "nature_of_employment",
                ))

        # Rule 314: Exempt allowances with salary — verify HRA details
        if sal.hra_exempt_amount > z:
            if inp.hra_details:
                hd = inp.hra_details
                if sal.hra_exempt_amount > hd.actual_hra_received:
                    results.append(_make(
                        "ITR4-R314b", False,
                        f"HRA exemption claimed (Rs {sal.hra_exempt_amount}) exceeds actual "
                        f"HRA received (Rs {hd.actual_hra_received})",
                        "salary_income.hra_exempt_amount",
                    ))
                rent_factor = hd.rent_paid - (hd.salary_for_hra * Decimal("0.10"))
                salary_factor = hd.salary_for_hra * (Decimal("0.40") if hd.is_metro_city else Decimal("0.50"))
                max_hra = min(hd.actual_hra_received, max(rent_factor, z), salary_factor)
                if sal.hra_exempt_amount > max_hra:
                    results.append(_make(
                        "ITR4-R314", False,
                        f"HRA exemption claimed (Rs {sal.hra_exempt_amount}) exceeds the "
                        f"permissible limit (Rs {max_hra}) computed as least of: "
                        f"actual HRA received (Rs {hd.actual_hra_received}), "
                        f"{'40%' if hd.is_metro_city else '50%'} of salary (Rs {salary_factor}), "
                        f"and rent paid minus 10% salary (Rs {max(rent_factor, z)})",
                        "salary_income.hra_exempt_amount",
                    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 80TTA / 80TTB
    # ═══════════════════════════════════════════════════════════════════════

    if ch6a:
        # Rule 38: 80TTA restricted to savings bank interest — enforce cross-check
        if ch6a.amount_80tta > z:
            savings_interest = os_.savings_bank_interest if os_ else z
            if ch6a.amount_80tta > savings_interest:
                results.append(_make(
                    "ITR4-R038", False,
                    f"80TTA deduction (Rs {ch6a.amount_80tta}) exceeds savings bank interest "
                    f"(Rs {savings_interest}). 80TTA is restricted to savings account interest only.",
                    "deductions_chapter6a.amount_80tta",
                ))

        # Rule 39: 80TTA not available for senior citizens
        if ch6a.amount_80tta > z and is_senior:
            results.append(_make(
                "ITR4-R039", False,
                "80TTA deduction is not available for senior citizens (age >= 60). "
                "Senior citizens should claim 80TTB instead.",
                "deductions_chapter6a.amount_80tta",
                expected="0 for senior citizens", actual=str(ch6a.amount_80tta)))

        # Rule 40: 80TTB not available for non-seniors
        if ch6a.amount_80ttb > z and not is_senior:
            results.append(_make(
                "ITR4-R040", False,
                "80TTB is available only for senior citizens (age >= 60). "
                "Non-senior citizens should use 80TTA instead.",
                "deductions_chapter6a.amount_80ttb",
                expected="0 for non-senior", actual=str(ch6a.amount_80ttb)))

        # Rule 41: 80TTB restricted to interest income — enforce cross-check
        if ch6a.amount_80ttb > z:
            total_osi_interest = (
                os_.savings_bank_interest + os_.fixed_deposit_interest
                + os_.dividend_income
            ) if os_ else z
            if ch6a.amount_80ttb > total_osi_interest:
                results.append(_make(
                    "ITR4-R041", False,
                    f"80TTB deduction (Rs {ch6a.amount_80ttb}) exceeds interest income from "
                    f"Other Sources (Rs {total_osi_interest}). 80TTB is restricted to deposit "
                    f"interest only.",
                    "deductions_chapter6a.amount_80ttb",
                ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 80G / 80GGC
    # ═══════════════════════════════════════════════════════════════════════

    if ch6a:
        # Rule 34: 80G claimed but donation schedule not provided
        if ch6a.amount_80g > z:
            if not ch6a.donations_80g or len(ch6a.donations_80g) == 0:
                results.append(_make(
                    "ITR4-R034", False,
                    "80G deduction claimed but Schedule 80G details (donations list) "
                    "are not provided",
                    "deductions_chapter6a.donations_80g"))

        # Rule 35/36: 80G VIA vs schedule_80g cross-consistency — enforce
        if ch6a.amount_80g > z:
            if inp.schedule_80g:
                sg = inp.schedule_80g
                # R035: schedule_80g total_eligible_amount vs VIA claimed amount
                if sg.total_eligible_amount > ch6a.amount_80g:
                    results.append(_make(
                        "ITR4-R035", False,
                        f"80G Schedule eligible amount (Rs {sg.total_eligible_amount}) "
                        f"exceeds VIA claimed amount (Rs {ch6a.amount_80g}). "
                        f"The claimed deduction must not be less than the computed eligible amount.",
                        "deductions_chapter6a.amount_80g",
                        expected=f">= {sg.total_eligible_amount}", actual=str(ch6a.amount_80g)))
                # R036: donations list sum in schedule_80g vs donations_80g list
                if sg.donations:
                    sch_donations_sum = sum(
                        d.cash_amount + d.non_cash_amount for d in sg.donations
                    )
                    donations_list_sum = sum(
                        d.cash_amount + d.non_cash_amount
                        for d in (ch6a.donations_80g or [])
                    )
                    if donations_list_sum != sch_donations_sum:
                        results.append(_make(
                            "ITR4-R036", False,
                            f"80G donation entries sum (Rs {donations_list_sum}) does not match "
                            f"Schedule 80G donations total (Rs {sch_donations_sum})",
                            "deductions_chapter6a.donations_80g",
                            expected=str(sch_donations_sum), actual=str(donations_list_sum)))
            else:
                # No schedule_80g but donations exist — informational
                if ch6a.donations_80g:
                    results.append(_info(
                        "ITR4-R535",
                        f"80G claimed (Rs {ch6a.amount_80g}) with donation entries but no "
                        f"schedule_80g aggregate. Engine will compute eligible amount from "
                        f"individual donation entries.",
                        "deductions_chapter6a.amount_80g"))



        # NOTE: R108 (80G per-PAN cash aggregate) is in the NEW VALIDATORS section.
        # R408: Per-entry 80G cash > ₹2,000 cap (also part of CBDT Sl 108)
        if inp.schedule_80g and inp.schedule_80g.donations:
            for i, d in enumerate(inp.schedule_80g.donations):
                if d.cash_amount > Decimal("2000"):
                    results.append(_make(
                        "ITR4-R408", False,
                        f"80G donation entry #{i+1}: individual cash amount "
                        f"(Rs {d.cash_amount}) exceeds ₹2,000 (CBDT Sl 108).",
                        f"schedule_80g.donations[{i}].cash_amount",
                        expected="<= 2000", actual=str(d.cash_amount)))



    # 80GGA / 80GGC enforcement (on inp, not ch6a)
    if inp.schedule_80gga:
        sgga = inp.schedule_80gga
        if sgga.total_claimed > z:
            if sgga.cash_donations > Decimal("2000"):
                results.append(_make(
                    "ITR4-R241", False,
                    f"80GGA cash donations (Rs {sgga.cash_donations}) exceed "
                    f"Rs 2,000 limit. Section 80GGA does not allow cash donations "
                    f"exceeding Rs 2,000 per donee.",
                    "schedule_80gga.cash_donations",
                    expected="<= 2000", actual=str(sgga.cash_donations)))
            if sgga.donee_pan_list and len(sgga.donee_pan_list) != len(set(sgga.donee_pan_list)):
                results.append(_make(
                    "ITR4-R242", False,
                    "80GGA: same Donee PAN appears more than once. "
                    "Each PAN can only be listed once per donation mode.",
                    "schedule_80gga.donee_pan_list"))
            if sgga.cash_donations + sgga.non_cash_donations != sgga.total_claimed:
                results.append(_make(
                    "ITR4-R243", False,
                    f"80GGA total mismatch: cash ({sgga.cash_donations}) + "
                    f"non-cash ({sgga.non_cash_donations}) != "
                    f"total_claimed ({sgga.total_claimed})",
                    "schedule_80gga.total_claimed",
                    expected=str(sgga.cash_donations + sgga.non_cash_donations),
                    actual=str(sgga.total_claimed)))

    if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > z:
        sggc = inp.schedule_80ggc
        if sggc.non_cash_contributions != sggc.total_claimed:
            results.append(_make(
                "ITR4-R244", False,
                f"80GGC: political contributions must be entirely non-cash "
                f"(cheque/draft/ECS). Cash contributions are not deductible. "
                f"Total claimed: Rs {sggc.total_claimed}, non-cash: Rs {sggc.non_cash_contributions}",
                "schedule_80ggc",
                expected=str(sggc.total_claimed),
                actual=str(sggc.non_cash_contributions)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 80GG
    # ═══════════════════════════════════════════════════════════════════════

    if ch6a:
        # Rule 37: 80GG max = min(Rs 60,000, 25% of GTI) (informational — GTI not pre-computed)
        if ch6a.amount_80gg > z:
            results.append(_info(
                "ITR4-R037",
                "80GG deduction max = minimum of: (a) Rs 5,000/month = Rs 60,000/year; "
                "(b) 25% of adjusted GTI; (c) actual rent paid minus 10% of adjusted GTI. "
                "GTI not available pre-computation for automated check.",
                "deductions_chapter6a.amount_80gg"))

        # Rule 151: HRA exempt + 80GG mutual exclusion
        # CBDT Sl 151: "HRA u/s 10(13A) is claimed, hence deduction u/s 80GG above
        # Rs 55,000 not allowed." If 80GG ≤ ₹55,000, HRA+80GG both permissible.
        if sal and sal.hra_exempt_amount > z and ch6a.amount_80gg > Decimal("55000"):
            results.append(_make(
                "ITR4-R151", False,
                f"80GG deduction (Rs {ch6a.amount_80gg}) cannot exceed ₹55,000 when "
                f"HRA exemption u/s 10(13A) is also claimed (Rs {sal.hra_exempt_amount}).",
                "deductions_chapter6a.amount_80gg",
                expected="<= 55000 or 0", actual=str(ch6a.amount_80gg)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 80DD / 80U / 80DDB — Description Requirements
    # ═══════════════════════════════════════════════════════════════════════

    if ch6a:
        # Rule 29 (CBDT Sl 29): 80DD — disability type and dependent details required
        if ch6a.amount_80dd > z:
            dd_sched = inp.schedule_80dd
            if not dd_sched or not dd_sched.disability_type:
                results.append(_make(
                    "ITR4-R029", False,
                    "80DD deducted Rs {0} but disability type (normal/severe) not "
                    "specified in Schedule 80DD (CBDT Sl 29).".format(ch6a.amount_80dd),
                    "schedule_80dd.disability_type"))

        # Rule 30 (CBDT Sl 30): 80DDB — disease category required
        if ch6a.amount_80ddb > z:
            if not inp.disease_category:
                results.append(_make(
                    "ITR4-R030", False,
                    "80DDB deducted Rs {0} but specified disease category not "
                    "provided (CBDT Sl 30).".format(ch6a.amount_80ddb),
                    "disease_category"))

        # Rule 44 (CBDT Sl 44): 80U — disability type required
        if ch6a.amount_80u > z:
            u_sched = inp.schedule_80u
            if not u_sched or not u_sched.disability_type:
                results.append(_make(
                    "ITR4-R044", False,
                    "80U deducted Rs {0} but disability type (normal/severe) not "
                    "specified in Schedule 80U (CBDT Sl 44).".format(ch6a.amount_80u),
                    "schedule_80u.disability_type"))

        # Rules 248-253: 80DD/80U schedule-VIA details matching (informational)
        if ch6a.amount_80dd > z:
            results.append(_info(
                "ITR4-R248",
                "80DD: Ensure PAN/Aadhaar of disabled dependent and disability "
                "certificate details are entered in Schedule VIA. Not captured in schema.",
                "deductions_chapter6a.amount_80dd"))
        if ch6a.amount_80u > z:
            results.append(_info(
                "ITR4-R249",
                "80U: Ensure disability certificate number, issuing authority, and "
                "PAN/Aadhaar of the assessee are entered in Schedule VIA. "
                "Not captured in schema.",
                "deductions_chapter6a.amount_80u"))

        # Rule 387: Form 10-IA for 80U/80DD filing (informational)
        if ch6a.amount_80dd > z or ch6a.amount_80u > z:
            results.append(_info(
                "ITR4-R387",
                "Form 10-IA (certificate from medical authority) must be furnished "
                "for 80DD and 80U claims. Not captured in schema.",
                "deductions_chapter6a"))

        # Rule 388: Specified disease details for 80DDB (informational)
        if ch6a.amount_80ddb > z:
            results.append(_info(
                "ITR4-R388",
                "80DDB: Specified disease must be listed in Rule 11DD of Income-tax "
                "Rules. Prescription and certificate from specialist doctor required. "
                "Not captured in schema.",
                "deductions_chapter6a.amount_80ddb"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: TDS / TCS / Tax Credits
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 110: Schedule IT — total TDS/TCS/tax paid consistency (informational)
    tds1_entries = inp.tds1_entries or []
    tds2_entries = inp.tds2_entries or []
    tcs_entries = inp.tcs_entries or []
    if tds1_entries or tds2_entries or tcs_entries:
        results.append(_info(
            "ITR4-R410",
            "Schedule IT totals: Verify TDS as per Form 16/16A, TCS as per Form 27D, "
            "and advance tax / self-assessment tax challans match the ITR. "
            "Cross-form verification not automated.",
            ""))

    # Rule 111: TCS claimed must not exceed TCS collected
    tcs_total = sum(e.tcs_collected for e in tcs_entries)
    if tcs_entries and tcs_total <= z:
        results.append(_make(
            "ITR4-R411", False,
            "TCS entries present but total TCS collected is zero or negative. "
            "Verify TCS schedule entries.",
            "tcs_entries"))

    # Rule 113: TDS2 claimed must not exceed TDS deducted
    for i, entry in enumerate(tds2_entries):
        if entry.tds_deducted <= z and entry.gross_amount > z:
            results.append(_make(
                "ITR4-R113", False,
                f"TDS2 entry {i+1}: Gross amount ({entry.gross_amount}) > 0 but "
                f"TDS deducted ({entry.tds_deducted}) is 0. TDS should be deducted "
                f"on TDS2 entries.",
                f"tds2_entries[{i}].tds_deducted"))

    # NOTE: R142a/R142b (TDS claimed but income not offered) merged into the
    # NEW VALIDATORS section as ITR4-R142/ITR4-R142b with improved income detection.

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Exempt Income Dropdown Uniqueness (R071-R095)
    # ═══════════════════════════════════════════════════════════════════════

    if inp.agriculture_income > Decimal("5000"):
        results.append(_make(
            "ITR4-R071", False,
            f"Agricultural income shown as exempt (Rs {inp.agriculture_income}) exceeds "
            f"Rs 5,000. Agricultural income above this threshold affects tax rate computation.",
            "agriculture_income"))

    if len(inp.exempt_income_dropdowns) != len(set(inp.exempt_income_dropdowns)):
        results.append(_make(
            "ITR4-R072", False,
            "Duplicate exempt income dropdown selections detected. Each exempt income "
            "category must be selected only once per dropdown.",
            "exempt_income_dropdowns"))

    # Exempt income breakdown vs dropdown consistency
    if sal:
        dropdown_to_expected = {
            "Agricultural Income": inp.agriculture_income,
            "HRA Exemption": sal.hra_exempt_amount,
            "LTA Exemption": sal.lta_exempt_amount,
        }
        for dropdown, expected_val in dropdown_to_expected.items():
            if dropdown in inp.exempt_income_dropdowns:
                actual = inp.exempt_income_breakdown.get(dropdown, z)
                if actual != expected_val and expected_val > z:
                    results.append(_make(
                        "ITR4-R073", False,
                        f"Exempt income dropdown '{dropdown}' selected but breakdown value "
                        f"(Rs {actual}) does not match expected (Rs {expected_val})",
                        "exempt_income_breakdown",
                    ))

    if inp.exempt_income_dropdowns:
        breakdown_sum = sum(
            v for k, v in inp.exempt_income_breakdown.items()
            if k in inp.exempt_income_dropdowns
        )
        if breakdown_sum == z:
            results.append(_make(
                "ITR4-R074", False,
                f"Exempt income dropdowns selected ({', '.join(inp.exempt_income_dropdowns)}) "
                f"but no corresponding exempt income breakdown values provided.",
                "exempt_income_breakdown"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Form Requirements (10BA, 10E, 10IA, 10IEA)
    # ═══════════════════════════════════════════════════════════════════════

    # 80GG requires Form 10BA
    if ch6a and ch6a.amount_80gg > z and not inp.form_10ba_filed:
        results.append(_make(
            "ITR4-R282", False,
            "80GG deduction claimed but Form 10BA (declaration for rent paid) "
            "has not been filed. Form 10BA is mandatory for 80GG claims.",
            "form_10ba_filed"))

    # Relief u/s 89 requires Form 10E
    if inp.form_10e_filed:
        has_salary = sal.gross_salary > z if sal else False
        has_family_pension = os_.family_pension_received > z if os_ else False
        if not has_salary and not has_family_pension:
            results.append(_make(
                "ITR4-R389", False,
                "Form 10E filed for relief u/s 89, but neither salary income nor "
                "family pension is present. Relief u/s 89 requires salary/family "
                "pension arrears.",
                "form_10e_filed"))

    # 80DD/80U requires Form 10-IA
    if ch6a and (ch6a.amount_80dd > z or ch6a.amount_80u > z):
        if not inp.form_10ia_filed:
            results.append(_make(
                "ITR4-R288", False,
                "80DD/80U deduction claimed but Form 10-IA (medical authority "
                "certificate) has not been filed.",
                "form_10ia_filed"))



    # ========================================================================
    # SECTION: NEW VALIDATORS — Previously NOT IMPLEMENTED (CBDT Sl 64-411 gaps)
    # ========================================================================

    from collections import Counter, defaultdict

    # ── Pre-compute TDS/TCS sums used throughout ────────────────────────────
    tds1_s = sum(e.tds_deducted for e in (inp.tds1_entries or []))
    tds2_s = sum(e.tds_deducted for e in (inp.tds2_entries or []))
    tds3_s = sum(e.tds_deducted for e in (inp.tds3_entries or []))
    exempt_dds = inp.exempt_income_dropdowns or []
    r10b_count = sum(1 for d in exempt_dds if "10(10B)" in d)
    has_10c = any("10(10C)" in d for d in exempt_dds)

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: BP Financial Cross-Foots (CBDT Sl 3-4)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 3: BP E17: Capital+Liabilities = sum of components
    if inp.schedule_bp_financial:
        bpf = inp.schedule_bp_financial
        cl_sum = (bpf.partners_capital + bpf.secured_loans + bpf.unsecured_loans
                  + bpf.advances_received + bpf.sundry_creditors + bpf.other_liabilities)
        if bpf.total_capital_liabilities > z and abs(bpf.total_capital_liabilities - cl_sum) > Decimal("1"):
            results.append(_make("ITR4-R003", False,
                f"BP E17: total capital+liabilities (Rs {bpf.total_capital_liabilities}) "
                f"≠ sum of components (Rs {cl_sum})",
                "schedule_bp_financial.total_capital_liabilities"))
        # Sl 4: BP E25: Assets = sum of components
        assets_sum = (bpf.fixed_assets + bpf.investments_bp + bpf.inventories
                      + bpf.sundry_debtors + bpf.bank_balance + bpf.cash_in_hand
                      + bpf.loans_and_advances_given + bpf.other_assets)
        if bpf.total_assets > z and abs(bpf.total_assets - assets_sum) > Decimal("1"):
            results.append(_make("ITR4-R004", False,
                f"BP E25: total assets (Rs {bpf.total_assets}) ≠ sum of components (Rs {assets_sum})",
                "schedule_bp_financial.total_assets"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 44AD Individual Rate Checks (CBDT Sl 5-6)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 5: 44AD income >= 6% of digital turnover (individual rate check)
    if inp.presumptive_scheme == PresumptiveScheme.S44AD and inp.business_income_44ad:
        ad = inp.business_income_44ad
        if ad.income_declared and ad.income_declared > z:
            min_digital = ad.digital_turnover * Decimal("0.06")
            if ad.digital_turnover > z and ad.income_declared < min_digital:
                results.append(_make("ITR4-R005a", False,
                    f"44AD: income declared (Rs {ad.income_declared}) < 6% of digital turnover "
                    f"(Rs {min_digital})", "business_income_44ad.income_declared"))
    # Sl 6: 44AD income >= 8% of cash turnover (individual rate check)
    if inp.presumptive_scheme == PresumptiveScheme.S44AD and inp.business_income_44ad:
        ad = inp.business_income_44ad
        if ad.income_declared and ad.income_declared > z:
            min_cash = ad.cash_turnover * Decimal("0.08")
            if ad.cash_turnover > z and ad.income_declared < min_cash:
                results.append(_make("ITR4-R006", False,
                    f"44AD: income declared (Rs {ad.income_declared}) < 8% of cash turnover "
                    f"(Rs {min_cash})", "business_income_44ad.income_declared"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Reverse Code-to-Income Rules (CBDT Sl 12, 17)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 12: business code selected → must declare 44AD income
    if inp.business_code and inp.presumptive_scheme != PresumptiveScheme.S44AD:
        results.append(_info("ITR4-R012a",
            "Business code for 44AD selected but 44AD scheme not active. Verify.", "business_code"))
    # Sl 17: profession code selected → must declare 44ADA income
    if inp.profession_code and inp.presumptive_scheme != PresumptiveScheme.S44ADA:
        results.append(_info("ITR4-R017a",
            "Profession code for 44ADA selected but 44ADA scheme not active. Verify.", "profession_code"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 44AE Firm Partner Salary/Interest (CBDT Sl 97)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.presumptive_scheme == PresumptiveScheme.S44AE and inp.goods_carriage_44ae \
            and is_firm and inp.schedule_bp_financial:
        bpf = inp.schedule_bp_financial
        if bpf.salary_to_partners > z or bpf.interest_to_partners > z:
            results.append(_info("ITR4-R097",
                f"44AE Firm: partner salary Rs {bpf.salary_to_partners}, interest Rs "
                f"{bpf.interest_to_partners}. Presumptive income at E5 must be reduced "
                f"by these amounts.", "schedule_bp_financial"))

    # NOTE: 80CCD(2) hard caps (Sl 25, 47, 161, 263) enforced in Deduction Limits
    # section above (R025, R047, R161, R263). No duplicate checks here.

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Total Exempt ≤ Sum of Salary Components (CBDT Sl 69)
    # ═══════════════════════════════════════════════════════════════════════════

    if sal and inp.total_exempt_income and inp.total_exempt_income > z:
        total_sal_components = (sal.gross_salary + sal.perquisites_value
                                + sal.profits_in_lieu_of_salary)
        if inp.total_exempt_income > total_sal_components:
            results.append(_make("ITR4-R069", False,
                f"Total exempt allowances (Rs {inp.total_exempt_income}) > "
                f"17(1)+17(2)+17(3) (Rs {total_sal_components})", "total_exempt_income"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Gratuity Per-Category Cap (CBDT Sl 73 + 317)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 73: Gratuity ≤ ₹20L non-CG/SG
    if sal and sal.gratuity_received > z and inp.nature_of_employment:
        emp_l = inp.nature_of_employment.lower()
        is_cg_sg = any(kw in emp_l for kw in ("central", "state")) and "government" in emp_l
        if not is_cg_sg and sal.gratuity_received > Decimal("2000000"):
            results.append(_make("ITR4-R073", False,
                f"Gratuity (Rs {sal.gratuity_received}) exceeds ₹20L for non-CG/SG",
                "salary_income.gratuity_received"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80D Sub-Section Conditioned Sums (CBDT Sl 169, 172, 174, 176, 178)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 178: 80D Sl 3 = 1a+1b+2a+2b+PHC self+PHC parents
    if is_old and inp.schedule_80d:
        sd = inp.schedule_80d
        section_total = (sd.premium_1a_non_senior + sd.premium_1b_senior
                         + sd.premium_2a_parents_non_senior + sd.premium_2b_parents_senior
                         + sd.preventive_checkup_self + sd.preventive_checkup_parents)
        if ch6a:
            d80_total = ch6a.amount_80d_self_family + ch6a.amount_80d_parents
            if d80_total > z and d80_total != section_total:
                results.append(_make("ITR4-R178", False,
                    f"80D Sl 3 (Rs {d80_total}) ≠ 1a+1b+2a+2b+PHC (Rs {section_total})",
                    "deductions_chapter6a"))
        # Additional senior citizen cross-checks for R168/R173 (schedule_80d flags)
        if is_old and ch6a:
            # R168 supplement: if self not senior per schedule_80d, cap at ₹25,000
            if not sd.has_self_senior and ch6a.amount_80d_self_family > Decimal("25000"):
                results.append(_make("ITR4-R168b", False,
                    f"80D Self/Family (Rs {ch6a.amount_80d_self_family}) exceeds ₹25,000 — "
                    f"schedule_80d.has_self_senior is False.", "deductions_chapter6a.amount_80d_self_family"))
            # R173 supplement: if parents not senior per schedule_80d, cap at ₹25,000
            if not sd.has_parents_senior and ch6a.amount_80d_parents > Decimal("25000"):
                results.append(_make("ITR4-R173b", False,
                    f"80D Parents (Rs {ch6a.amount_80d_parents}) exceeds ₹25,000 — "
                    f"schedule_80d.has_parents_senior is False.", "deductions_chapter6a.amount_80d_parents"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Dividend = Sum Quarterly (CBDT Sl 185)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.dividend_quarterly_breakdown and os_ and os_.dividend_income > z:
        q_sum = sum(v for v in inp.dividend_quarterly_breakdown.values())
        if abs(os_.dividend_income - q_sum) > Decimal("1"):
            results.append(_make("ITR4-R485", False,
                f"Dividend income (Rs {os_.dividend_income}) ≠ sum of quarterly breakup "
                f"(Rs {q_sum})", "other_sources_income.dividend_income"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Schedule IT/TCS Totals (CBDT Sl 110-112)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 110: Schedule IT col 4 total = sum rows
    if inp.schedule_it_total_paid and inp.schedule_it_total_paid > z and inp.tax_payment_entries:
        it_sum = sum(tp.amount for tp in inp.tax_payment_entries)
        if abs(inp.schedule_it_total_paid - it_sum) > Decimal("1"):
            results.append(_make("ITR4-R110", False,
                f"Schedule IT col 4 total (Rs {inp.schedule_it_total_paid}) ≠ sum of rows "
                f"(Rs {it_sum})", "schedule_it_total_paid"))
    # Sl 111: TCS claimed ≤ TCS collected per entry
    for i, e in enumerate(inp.tcs_entries or []):
        if e.tcs_credit_claimed and e.tcs_credit_claimed > e.tcs_collected:
            results.append(_make("ITR4-R111", False,
                f"TCS entry {i+1}: claimed (Rs {e.tcs_credit_claimed}) > collected "
                f"(Rs {e.tcs_collected})", f"tcs_entries[{i}].tcs_credit_claimed"))
    # Sl 112: TCS col 5 total = sum individual col 5
    if inp.schedule_tcs_total_claimed and inp.schedule_tcs_total_claimed > z:
        tcs_claimed_sum = sum((e.tcs_credit_claimed or z) for e in (inp.tcs_entries or []))
        if abs(inp.schedule_tcs_total_claimed - tcs_claimed_sum) > Decimal("1"):
            results.append(_make("ITR4-R112", False,
                f"TCS col 5 total (Rs {inp.schedule_tcs_total_claimed}) ≠ sum (Rs {tcs_claimed_sum})",
                "schedule_tcs_total_claimed"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Total TDS/TCS = Sum of Schedules (CBDT Sl 131-132)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 131: Total TDS claimed = sum TDS1+TDS2+TDS3
    if inp.total_tds_claimed and inp.total_tds_claimed > z:
        from_tds_schedules = tds1_s + tds2_s + tds3_s
        if abs(inp.total_tds_claimed - from_tds_schedules) > Decimal("1"):
            results.append(_make("ITR4-R131", False,
                f"Total TDS claimed (Rs {inp.total_tds_claimed}) ≠ TDS1+TDS2+TDS3 "
                f"(Rs {from_tds_schedules})", "total_tds_claimed"))
    # Sl 132: Total TCS claimed = sum TCS schedule
    if inp.total_tcs_claimed and inp.total_tcs_claimed > z:
        tcs_s = sum((e.tcs_credit_claimed or e.tcs_collected) for e in (inp.tcs_entries or []))
        if abs(inp.total_tcs_claimed - tcs_s) > Decimal("1"):
            results.append(_make("ITR4-R132", False,
                f"Total TCS claimed (Rs {inp.total_tcs_claimed}) ≠ sum (Rs {tcs_s})",
                "total_tcs_claimed"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: TDS Bring-Forward + TDS col8 (CBDT Sl 114-115, 121-122)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 114-115: TDS year must not be null if brought-forward claim — HARD
    for e in inp.tds2_entries or []:
        if getattr(e, 'is_brought_forward', False):
            if getattr(e, 'tds_year', None) is None:
                results.append(_make("ITR4-R114", False,
                    "TDS2: brought-forward entry has no tds_year", "tds2_entries"))
    for e in inp.tds3_entries or []:
        if getattr(e, 'is_brought_forward', False):
            if getattr(e, 'tds_year', None) is None:
                results.append(_make("ITR4-R115", False,
                    "TDS3: brought-forward entry has no tds_year", "tds3_entries"))
    # Sl 121-122: TDS2 col6 claimed → col7+col8 mandatory — HARD
    for i, e in enumerate(inp.tds2_entries or []):
        tds_c = getattr(e, 'tds_claimed_this_year', None) or z
        if tds_c > z:
            if e.gross_amount <= z:
                results.append(_make("ITR4-R121b", False,
                    f"TDS2 entry {i+1}: TDS claimed but col 7 gross amount is 0",
                    f"tds2_entries[{i}].gross_amount"))
            if not getattr(e, 'head_of_income', None):
                results.append(_make("ITR4-R122", False,
                    f"TDS2 entry {i+1}: TDS claimed but col 8 head of income not provided",
                    f"tds2_entries[{i}].head_of_income"))
    # Sl 116-117 (CBDT Sl 116-117): TDS2 col6 claim ≤ col7 gross amount
    for i, e in enumerate(inp.tds2_entries or []):
        tds_c = getattr(e, 'tds_claimed_this_year', None) or e.tds_deducted
        if tds_c > z and e.gross_amount > z and tds_c > e.gross_amount:
            results.append(_make("ITR4-R116", False,
                f"TDS2 entry {i+1}: TDS claimed (Rs {tds_c}) exceeds income offered "
                f"(Rs {e.gross_amount}) — claim cannot exceed gross amount (CBDT Sl 116-117).",
                f"tds2_entries[{i}]"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Tax Computed / Taxes Paid Consistency (CBDT Sl 124-125)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 124: Tax computed but GTI 0 — post-computation; info here
    results.append(_info("ITR4-R124",
        "Tax computation disclosed but Gross Total Income is zero. Verify.", ""))
    # Sl 125: Taxes paid but no income — HARD
    if inp.total_taxes_paid and inp.total_taxes_paid > z:
        has_any_income = (
            (sal and sal.gross_salary > z)
            or (hp and hp.annual_rent_received > z)
            or (os_ and (os_.savings_bank_interest > z or os_.fixed_deposit_interest > z
                         or os_.dividend_income > z or os_.family_pension_received > z))
            or (inp.business_income_44ad and inp.business_income_44ad.total_turnover > z)
            or (inp.professional_income_44ada and inp.professional_income_44ada.gross_receipts > z)
            or (inp.goods_carriage_44ae and len(inp.goods_carriage_44ae.vehicles) > 0)
            or (cg and cg.ltcg_112a > z)
        )
        if not has_any_income:
            results.append(_make("ITR4-R125", False,
                "Taxes paid disclosed but no income found in any head of income "
                "(CBDT Sl 125). Income must be disclosed with tax payments.",
                "total_taxes_paid"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 148 Proceeding + 139(5) Conflict (CBDT Sl 188)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.is_148_proceeding and inp.filing_section == "139(5)":
        results.append(_make("ITR4-R188", False,
            "Proceeding u/s 148 initiated. Original return u/s 139 cannot be revised "
            "to ITR-4.", "filing_section"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Vehicle Registration Duplicate Check — HARD (CBDT Sl 213)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.vehicle_registration_numbers and len(inp.vehicle_registration_numbers) > 1:
        reg_counts = Counter(inp.vehicle_registration_numbers)
        for reg, cnt in reg_counts.items():
            if cnt > 1:
                results.append(_make("ITR4-R213", False,
                    f"Vehicle registration '{reg}' appears {cnt} times. Cannot repeat in 44AE.",
                    "vehicle_registration_numbers"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80G Table E = A+B+C+D (CBDT Sl 103)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.schedule_80g and inp.schedule_80g.donations:
        cats: dict[str, Decimal] = {"A": z, "B": z, "C": z, "D": z}
        for d in inp.schedule_80g.donations:
            cat = d.donation_category or "A"
            cats[cat] = cats.get(cat, z) + (d.total_donation or z)
        if inp.schedule_80g.total_eligible_amount and inp.schedule_80g.total_eligible_amount > z:
            e_sum = sum(v for v in cats.values())
            if abs(inp.schedule_80g.total_eligible_amount - e_sum) > Decimal("1"):
                results.append(_make("ITR4-R103", False,
                    f"80G Table E total (Rs {inp.schedule_80g.total_eligible_amount}) "
                    f"≠ sum A+B+C+D (Rs {e_sum})", "schedule_80g.total_eligible_amount"))

    # NOTE: 80G per-PAN cash aggregation (R108) and per-entry cash cap (R408)
    # are enforced in the main 80G/80GGC section above. No duplicate here.

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Salary Exemption Cross-Foots (CBDT Sl 64-81, 100-115)
    # ═══════════════════════════════════════════════════════════════════════════

    # R064: LTA exempt ≤ Salary 17(1)
    if sal and sal.lta_exempt_amount > z and sal.lta_exempt_amount > sal.gross_salary:
        results.append(_make("ITR4-R064", False,
            f"LTA exemption (Rs {sal.lta_exempt_amount}) exceeds gross salary 17(1) "
            f"(Rs {sal.gross_salary})", "salary_income.lta_exempt_amount"))

    # R070: LTA ≤ Salary 17(1) (old regime)
    if is_old and sal and sal.lta_amount_received > z and sal.lta_amount_received > sal.gross_salary:
        results.append(_make("ITR4-R070", False,
            f"LTA received (Rs {sal.lta_amount_received}) exceeds salary 17(1) "
            f"(Rs {sal.gross_salary})", "salary_income.lta_amount_received"))

    # R071: 10(6) embassy official ≤ gross salary
    if sal and getattr(sal, 'sec10_6_embassy_exempt', z) > z:
        embassy_val = getattr(sal, 'sec10_6_embassy_exempt', z)
        if embassy_val > sal.gross_salary:
            results.append(_make("ITR4-R071a", False,
                f"Sec 10(6) embassy exemption (Rs {embassy_val}) exceeds gross salary",
                "salary_income.sec10_6_embassy_exempt"))

    # R072: 10(7) foreign allowance ≤ salary
    if sal and getattr(sal, 'sec10_7_foreign_allowance', z) > z:
        fa_val = getattr(sal, 'sec10_7_foreign_allowance', z)
        if fa_val > sal.gross_salary:
            results.append(_make("ITR4-R072a", False,
                f"Sec 10(7) foreign allowance (Rs {fa_val}) exceeds gross salary",
                "salary_income.sec10_7_foreign_allowance"))

    # R073: 10(10CC) ≤ perquisites (17(2))
    if sal and getattr(sal, 'sec10_10cc_perquisite_tax', z) > z:
        pt_val = getattr(sal, 'sec10_10cc_perquisite_tax', z)
        if pt_val > sal.perquisites_value:
            results.append(_make("ITR4-R073b", False,
                f"Sec 10(10CC) perquisite tax (Rs {pt_val}) exceeds perquisites 17(2) "
                f"(Rs {sal.perquisites_value})", "salary_income.sec10_10cc_perquisite_tax"))

    # R075: Leave encashment ≤ ₹25L non-govt
    if sal and sal.leave_encashment_received > Decimal("2500000"):
        emp = (inp.nature_of_employment or "").lower()
        if not any(kw in emp for kw in ("central government", "state government")):
            results.append(_make("ITR4-R075", False,
                f"Leave encashment (Rs {sal.leave_encashment_received}) exceeds ₹25,00,000 "
                f"for non-government employees", "salary_income.leave_encashment_received"))

    # R077: Only one of 10(10B)(i)/(ii)/10(10C)
    if r10b_count > 1 and has_10c:
        results.append(_make("ITR4-R077", False,
            "Only one of 10(10B)(i), 10(10B)(ii), or 10(10C) can be selected in exempt allowances",
            "exempt_income_dropdowns"))

    # R080-R081: 10(14)(i)/(ii) ≤ 17(1) old regime
    if is_old and sal:
        if getattr(sal, 'sec10_14i_prescribed_allowance', z) > sal.gross_salary:
            results.append(_make("ITR4-R080", False,
                f"10(14)(i) allowance (Rs {sal.sec10_14i_prescribed_allowance}) exceeds "
                f"salary 17(1)", "salary_income.sec10_14i_prescribed_allowance"))
        if getattr(sal, 'sec10_14ii_personal_allowance', z) > sal.gross_salary:
            results.append(_make("ITR4-R081", False,
                f"10(14)(ii) allowance (Rs {sal.sec10_14ii_personal_allowance}) exceeds "
                f"salary 17(1)", "salary_income.sec10_14ii_personal_allowance"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Per-Dropdown Exempt Income Uniqueness (CBDT Sl 82-95)
    # ═══════════════════════════════════════════════════════════════════════════

    dd_counts: dict[str, int] = {}
    for dd in exempt_dds:
        if dd:
            dd_counts[dd] = dd_counts.get(dd, 0) + 1
    for dd_name, count in dd_counts.items():
        if count > 1:
            results.append(_make("ITR4-R082", False,
                f"Exempt income '{dd_name}' selected {count} times. "
                f"Each exemption can be selected once.", "exempt_income_dropdowns"))

    # NOTE: R222 (catch-all dropdown uniqueness) removed — R082 covers this better.

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80G Donation Validations (CBDT Sl 98-109, 394-399)
    # ═══════════════════════════════════════════════════════════════════════════

    # R098: Donee PAN ≠ Assessee PAN in 80G
    if inp.schedule_80g and inp.assessee_pan:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.donee_pan and d.donee_pan == inp.assessee_pan:
                results.append(_make("ITR4-R098", False,
                    f"80G donation row {i+1}: Donee PAN ({d.donee_pan}) cannot equal "
                    f"assessee PAN", f"schedule_80g.donations[{i}].donee_pan"))

    # R099-R107: 80G per-table cash/non-cash mandatory + cross-foots
    if inp.schedule_80g and inp.schedule_80g.donations:
        for cat in ("A", "B", "C", "D"):
            cat_donations = [d for d in inp.schedule_80g.donations
                             if d.donation_category == cat]
            for d in cat_donations:
                if d.total_donation and d.total_donation > z:
                    if d.cash_amount == z and d.non_cash_amount == z:
                        results.append(_make("ITR4-R099", False,
                            f"80G Table {cat}: total donation Rs {d.total_donation} but "
                            f"no cash/non-cash entered", "schedule_80g.donations"))
                    if abs(d.cash_amount + d.non_cash_amount - d.total_donation) > Decimal("1"):
                        results.append(_make("ITR4-R104", False,
                            f"80G Table {cat}: total (Rs {d.total_donation}) != cash "
                            f"({d.cash_amount}) + non-cash ({d.non_cash_amount})",
                            "schedule_80g.donations"))

    # R109: 80G same PAN not repeated
    if inp.schedule_80g and inp.schedule_80g.donations:
        pan_counts = Counter(
            d.donee_pan for d in inp.schedule_80g.donations if d.donee_pan
        )
        for pan, cnt in pan_counts.items():
            if cnt > 1 and pan != "AAAAR1077P":
                results.append(_make("ITR4-R109", False,
                    f"80G: Donee PAN '{pan}' appears {cnt} times. Each PAN can appear "
                    f"once except AAAAR1077P.", "schedule_80g.donations"))

    # R394-R395: IFSC/Transaction ref + Donee PAN for 80G non-cash
    if inp.schedule_80g:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.non_cash_amount > z:
                if not d.ifsc_code:
                    results.append(_make("ITR4-R394", False,
                        f"80G row {i+1}: non-cash donation needs IFSC code",
                        f"schedule_80g.donations[{i}].ifsc_code"))
                if not d.transaction_ref:
                    results.append(_make("ITR4-R394b", False,
                        f"80G row {i+1}: non-cash donation needs transaction reference",
                        f"schedule_80g.donations[{i}].transaction_ref"))
                if not d.donee_pan:
                    results.append(_make("ITR4-R395", False,
                        f"80G row {i+1}: donee PAN mandatory when donation > 0",
                        f"schedule_80g.donations[{i}].donee_pan"))

    # R399: 80G either cash or non-cash per row (not both)
    if inp.schedule_80g:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.cash_amount > z and d.non_cash_amount > z:
                results.append(_make("ITR4-R399", False,
                    f"80G row {i+1}: both cash and non-cash entered — each row must be "
                    f"one or the other", f"schedule_80g.donations[{i}]"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: TDS1/TDS2/TDS3 Column Totals (CBDT Sl 118-120)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.schedule_tds1_total and inp.schedule_tds1_total > z \
            and abs(inp.schedule_tds1_total - tds1_s) > Decimal("1"):
        results.append(_make("ITR4-R118", False,
            "Schedule TDS1 col 4 total ≠ sum of TDS deducted per row", "tds1_entries"))
    if inp.schedule_tds2_total_claimed and inp.schedule_tds2_total_claimed > z:
        tds2_claimed_sum = sum(
            (getattr(e, 'tds_claimed_this_year', None) or z)
            for e in (inp.tds2_entries or [])
        )
        if abs(inp.schedule_tds2_total_claimed - tds2_claimed_sum) > Decimal("1"):
            results.append(_make("ITR4-R119", False,
                "Schedule TDS2 col 6 total ≠ sum of claims per row", "tds2_entries"))
    if inp.schedule_tds3_total_claimed and inp.schedule_tds3_total_claimed > z:
        tds3_claimed_sum = sum(
            (getattr(e, 'tds_claimed_this_year', None) or z)
            for e in (inp.tds3_entries or [])
        )
        if abs(inp.schedule_tds3_total_claimed - tds3_claimed_sum) > Decimal("1"):
            results.append(_make("ITR4-R120", False,
                "Schedule TDS3 col 7 total ≠ sum of claims per row", "tds3_entries"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: TDS Claimed But Income Not Offered (CBDT Sl 142 — merged)
    # ═══════════════════════════════════════════════════════════════════════════

    if tds1_s > z and (not sal or sal.gross_salary <= z):
        results.append(_make("ITR4-R142a", False,
            f"TDS on salary Rs {tds1_s} claimed but salary income is 0. "
            f"Corresponding receipts must be offered for taxation (CBDT Sl 142).",
            "tds1_entries", expected="salary > 0", actual="salary = 0"))
    if tds2_s > z:
        has_os = os_ and (
            os_.savings_bank_interest > z or os_.fixed_deposit_interest > z
            or os_.family_pension_received > z or os_.dividend_income > z
        )
        has_biz = (
            (inp.business_income_44ad and inp.business_income_44ad.total_turnover > z)
            or (inp.professional_income_44ada
                and inp.professional_income_44ada.gross_receipts > z)
        )
        has_cg = cg and cg.ltcg_112a > z
        if not has_os and not has_biz and not has_cg:
            results.append(_make("ITR4-R142b", False,
                "TDS on other income claimed but no corresponding income offered "
                "under OS / Business / Capital Gains. Receipts must be offered for "
                "taxation (CBDT Sl 142).", "tds2_entries"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Tax Payments Cross-Consistency (CBDT Sl 126, 130, 133-134)
    # ═══════════════════════════════════════════════════════════════════════════

    # R126: Total taxes paid = sum of schedules
    if inp.total_taxes_paid and inp.total_taxes_paid > z:
        tcs_collected_s = sum(e.tcs_collected for e in (inp.tcs_entries or []))
        from_schedules = (
            tds1_s + tds2_s + tds3_s + tcs_collected_s
            + inp.advance_tax_paid + inp.self_assessment_tax_paid
        )
        if from_schedules > z and abs(inp.total_taxes_paid - from_schedules) > Decimal("1"):
            results.append(_make("ITR4-R126", False,
                f"Total taxes paid (Rs {inp.total_taxes_paid}) ≠ sum of schedules "
                f"(Rs {from_schedules})", "total_taxes_paid"))

    # R130: Agriculture income > 5000 selected once only
    if inp.agriculture_income > 5000:
        agri_count = sum(1 for d in exempt_dds if "agricultur" in d.lower())
        if agri_count > 1:
            results.append(_make("ITR4-R130", False,
                "Agricultural income exempt dropdown selected more than once",
                "exempt_income_dropdowns"))

    # R133-R134: Advance/SA tax match schedule IT
    if inp.advance_tax_paid and inp.advance_tax_paid > z and inp.tax_payment_entries:
        adv_from_entries = sum(
            tp.amount for tp in inp.tax_payment_entries if tp.payment_type == "advance"
        )
        if adv_from_entries > z and abs(inp.advance_tax_paid - adv_from_entries) > Decimal("1"):
            results.append(_make("ITR4-R133", False,
                f"Advance tax declared (Rs {inp.advance_tax_paid}) ≠ sum of advance "
                f"entries (Rs {adv_from_entries})", "advance_tax_paid"))
    if inp.self_assessment_tax_paid and inp.self_assessment_tax_paid > z \
            and inp.tax_payment_entries:
        sa_from_entries = sum(
            tp.amount for tp in inp.tax_payment_entries if tp.payment_type == "self_assessment"
        )
        if sa_from_entries > z \
                and abs(inp.self_assessment_tax_paid - sa_from_entries) > Decimal("1"):
            results.append(_make("ITR4-R134", False,
                f"SA tax declared (Rs {inp.self_assessment_tax_paid}) ≠ sum of SA entries "
                f"(Rs {sa_from_entries})", "self_assessment_tax_paid"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: OS Income Cross-Foot (CBDT Sl 62, 95)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 62: OS income total = sum of individual columns
    if os_ and inp.other_sources_total and inp.other_sources_total > z:
        os_sum = (os_.savings_bank_interest + os_.fixed_deposit_interest
                  + os_.dividend_income + os_.family_pension_received
                  + os_.interest_on_it_refund)
        if abs(inp.other_sources_total - os_sum) > Decimal("1"):
            results.append(_make("ITR4-R062", False,
                f"Other Sources total (Rs {inp.other_sources_total}) ≠ sum of "
                f"individual columns (Rs {os_sum}) (CBDT Sl 62).",
                "other_sources_total", expected=str(os_sum),
                actual=str(inp.other_sources_total)))

    # Sl 95: 57(iia) deduction only if Family Pension in OS dropdowns
    if os_ and os_.family_pension_received > z:
        fp_in_dropdowns = any(
            "family pension" in dd.lower() for dd in inp.other_sources_dropdowns
        )
        if not fp_in_dropdowns:
            results.append(_make("ITR4-R095", False,
                "Family pension received (Rs {0}) but 'Family Pension' not selected in "
                "Other Sources income dropdowns (CBDT Sl 95).".format(os_.family_pension_received),
                "other_sources_dropdowns"))

    # Sl 139: Gross receipts in BP but no financial particulars — HARD
    has_turnover = (
        (inp.presumptive_scheme == PresumptiveScheme.S44AD
         and inp.business_income_44ad and inp.business_income_44ad.total_turnover > z)
        or (inp.presumptive_scheme == PresumptiveScheme.S44ADA
            and inp.professional_income_44ada and inp.professional_income_44ada.gross_receipts > z)
    )
    if has_turnover and not inp.schedule_bp_financial:
        results.append(_make("ITR4-R139", False,
            "Gross receipts/turnover disclosed in Schedule BP but Financial Particulars "
            "(sundry creditors, inventories, cash-in-hand etc.) not filled (CBDT Sl 139).",
            "schedule_bp_financial"))

    # Sl 160: Exempt allowances total = sum of individual exempt values
    if inp.total_exempt_income and inp.total_exempt_income > z:
        breakdown_sum = sum(v for v in inp.exempt_income_breakdown.values())
        if breakdown_sum > z and abs(inp.total_exempt_income - breakdown_sum) > Decimal("1"):
            results.append(_make("ITR4-R160", False,
                f"Total exempt allowances (Rs {inp.total_exempt_income}) ≠ sum of "
                f"individual exempt values (Rs {breakdown_sum}) (CBDT Sl 160).",
                "total_exempt_income", expected=str(breakdown_sum),
                actual=str(inp.total_exempt_income)))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Filing Section Constraints (CBDT Sl 167)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.original_filing_section == "142(1)" and inp.filing_section in ("139(1)", "139(4)"):
        results.append(_make("ITR4-R167", False,
            f"Original filed u/s 142(1), cannot file fresh u/s {inp.filing_section}. "
            f"Only 139(5) is permitted.", "filing_section"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 10(10B) Retrenchment Checks (CBDT Sl 185, 226)
    # ═══════════════════════════════════════════════════════════════════════════

    # R185: 10(10B) not for CG/SG/pensioners
    if sal and sal.retrenchment_compensation > z and inp.nature_of_employment:
        emp_l = inp.nature_of_employment.lower()
        if any(kw in emp_l for kw in ("central", "state", "pension")):
            results.append(_make("ITR4-R185", False,
                f"10(10B) retrenchment exemption claimed but employment is "
                f"'{inp.nature_of_employment}'. Only industrial workers covered by "
                f"ID Act qualify.", "salary_income.retrenchment_compensation"))

    # NOTE: Sl 226 (10(10B) Second Proviso ≤ ₹5,00,000) is covered by ITR4-R104 above
    # which enforces ₹500,000 cap for both First and Second Proviso (same cap).

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: New Regime Hard Enforcement (CBDT Sl 200-202)
    # ═══════════════════════════════════════════════════════════════════════════

    if is_new and sal:
        if getattr(sal, 'sec10_14i_prescribed_allowance', z) > z:
            results.append(_make("ITR4-R200", False,
                "New regime: 10(14)(i) must be 0",
                "salary_income.sec10_14i_prescribed_allowance"))
        if getattr(sal, 'sec10_14ii_personal_allowance', z) > z:
            results.append(_make("ITR4-R201", False,
                "New regime: 10(14)(ii) must be 0",
                "salary_income.sec10_14ii_personal_allowance"))

    if is_new and any("10(17)" in d for d in exempt_dds):
        results.append(_make("ITR4-R202", False,
            "New regime: Sec 10(17) MP/MLA/MLC allowance is not available",
            "exempt_income_dropdowns"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 10(10B)/10(10C) Mutual Exclusion (CBDT Sl 214-215)
    # ═══════════════════════════════════════════════════════════════════════════

    # R214: 10(10B)+10(10C) simultaneous block
    if r10b_count > 0 and has_10c:
        results.append(_make("ITR4-R214", False,
            "10(10B) and 10(10C) cannot be claimed simultaneously",
            "exempt_income_dropdowns"))

    # R215: 10(10CC) ≤ TDS u/s 192
    if sal and getattr(sal, 'sec10_10cc_perquisite_tax', z) > z:
        pt_val2 = getattr(sal, 'sec10_10cc_perquisite_tax', z)
        tds192 = tds1_s  # TDS u/s 192 is in TDS1
        if pt_val2 > tds192:
            results.append(_make("ITR4-R215", False,
                f"10(10CC) Rs {pt_val2} exceeds TDS u/s 192 Rs {tds192}",
                "salary_income.sec10_10cc_perquisite_tax"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80D Dropdown Consistency (CBDT Sl 216-221)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.schedule_80d:
        sd = inp.schedule_80d
        if sd.not_claiming_self \
                and (sd.premium_1a_non_senior > z or sd.premium_1b_senior > z):
            results.append(_make("ITR4-R220", False,
                "80D: 'Not claiming Self/Family' selected but premium entered in 1a or 1b",
                "schedule_80d"))
        if sd.not_claiming_parents \
                and (sd.premium_2a_parents_non_senior > z or sd.premium_2b_parents_senior > z):
            results.append(_make("ITR4-R221", False,
                "80D: 'Not claiming Parents' selected but premium entered in 2a or 2b",
                "schedule_80d"))
        if not sd.has_self_senior and sd.premium_1b_senior > z:
            results.append(_make("ITR4-R217", False,
                "80D 1b: Senior citizen premium entered but 'Self senior' flag is No",
                "schedule_80d.has_self_senior"))
        if not sd.has_parents_senior and sd.premium_2b_parents_senior > z:
            results.append(_make("ITR4-R219", False,
                "80D 2b: Senior parent premium entered but 'Parents senior' flag is No",
                "schedule_80d.has_parents_senior"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80CCH Age at Joining (CBDT Sl 225)
    # ═══════════════════════════════════════════════════════════════════════════

    if ch6a and ch6a.amount_80cch > z and inp.agniveer_date_of_joining:
        age_years = (inp.agniveer_date_of_joining - date(2000, 1, 1)).days / 365.25
        if age_years < 17 or age_years > 27:
            results.append(_make("ITR4-R225b", False,
                f"80CCH: joining age ~{int(age_years)}. Must be 17-27.",
                "agniveer_date_of_joining"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80GGC Detailed Cross-Foots (CBDT Sl 241-247, 256, 398)
    # ═══════════════════════════════════════════════════════════════════════════

    # R241: 80GGC VIA cannot exceed eligible non-cash contributions
    if ch6a and getattr(ch6a, 'amount_80ggc', z) > z and inp.schedule_80ggc:
        eligible_total = (
            inp.schedule_80ggc.non_cash_contributions
            if inp.schedule_80ggc.contributions
            else inp.schedule_80ggc.total_claimed
        )
        if getattr(ch6a, 'amount_80ggc', z) > eligible_total:
            results.append(_make("ITR4-R241", False,
                f"80GGC VIA (Rs {getattr(ch6a, 'amount_80ggc', z)}) exceeds eligible "
                f"non-cash contributions (Rs {eligible_total})",
                "deductions_chapter6a.amount_80ggc"))

    # R243: Total Donation = sum of contributions
    if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > z:
        sggc = inp.schedule_80ggc
        if sggc.contributions:
            contrib_total = sum(c.amount for c in sggc.contributions)
            if abs(sggc.total_claimed - contrib_total) > Decimal("1"):
                results.append(_make("ITR4-R243", False,
                    f"80GGC total claimed (Rs {sggc.total_claimed}) ≠ sum of contributions "
                    f"(Rs {contrib_total})", "schedule_80ggc.total_claimed"))
            # R245: cash + non-cash = total
            cash_sum = sum(c.amount for c in sggc.contributions
                           if getattr(c, 'contribution_mode', '') == "cash")
            non_cash_sum = sum(c.amount for c in sggc.contributions
                               if getattr(c, 'contribution_mode', '') != "cash")
            if abs(cash_sum + non_cash_sum - sggc.total_claimed) > Decimal("1"):
                results.append(_make("ITR4-R245", False,
                    "80GGC: cash + non-cash ≠ total", "schedule_80ggc"))
            # R246: Date mandatory per contribution
            for i, c in enumerate(sggc.contributions):
                if c.amount > z and not c.contribution_date:
                    results.append(_make("ITR4-R246", False,
                        f"80GGC contribution {i+1}: date is mandatory",
                        f"schedule_80ggc.contributions[{i}].contribution_date"))
        # R247: Non-cash claimed but no row details
        if getattr(sggc, 'non_cash_contributions', z) > z and not sggc.contributions:
            results.append(_make("ITR4-R247", False,
                "80GGC non-cash contributions claimed but no row details",
                "schedule_80ggc.contributions"))

    # R256: 80GGC date range 01.04.2025-31.03.2026
    if inp.schedule_80ggc and inp.schedule_80ggc.contributions:
        for i, c in enumerate(inp.schedule_80ggc.contributions):
            if c.contribution_date:
                if c.contribution_date < date(2025, 4, 1) \
                        or c.contribution_date > date(2026, 3, 31):
                    results.append(_make("ITR4-R256", False,
                        f"80GGC contribution {i+1}: date {c.contribution_date} outside "
                        f"01.04.2025-31.03.2026",
                        f"schedule_80ggc.contributions[{i}].contribution_date"))

    # R398: 80GGC party name + PAN required
    if inp.schedule_80ggc and inp.schedule_80ggc.contributions:
        for i, c in enumerate(inp.schedule_80ggc.contributions):
            if c.amount > z \
                    and (not getattr(c, 'political_party_name', None)
                         or not getattr(c, 'political_party_pan', None)):
                results.append(_make("ITR4-R398", False,
                    f"80GGC row {i+1}: political party name and PAN required",
                    f"schedule_80ggc.contributions[{i}]"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80DD/80U VIA = Schedule Values (CBDT Sl 248-253)
    # ═══════════════════════════════════════════════════════════════════════════

    # R248-R249: 80DD/80U VIA = Schedule values
    if ch6a and ch6a.amount_80dd > z and inp.schedule_80dd:
        if ch6a.amount_80dd != inp.schedule_80dd.deduction_amount:
            results.append(_make("ITR4-R248", False,
                f"80DD VIA (Rs {ch6a.amount_80dd}) ≠ Schedule 80DD "
                f"(Rs {inp.schedule_80dd.deduction_amount})",
                "deductions_chapter6a.amount_80dd"))
    if ch6a and ch6a.amount_80u > z and inp.schedule_80u:
        if ch6a.amount_80u != inp.schedule_80u.deduction_amount:
            results.append(_make("ITR4-R249", False,
                f"80U VIA (Rs {ch6a.amount_80u}) ≠ Schedule 80U "
                f"(Rs {inp.schedule_80u.deduction_amount})",
                "deductions_chapter6a.amount_80u"))

    # R250-R253: 80DD/80U details required + Form 10IA (specific checks kept, generic R287 removed)
    if inp.schedule_80dd and inp.schedule_80dd.deduction_amount > z:
        if not inp.schedule_80dd.disability_type:
            results.append(_make("ITR4-R250", False,
                "80DD > 0: disability type (normal/severe) must be specified",
                "schedule_80dd.disability_type"))
        if not inp.form_10ia_filed_80dd:
            results.append(_make("ITR4-R252", False,
                "80DD claimed but separate Form 10-IA not filed for 80DD",
                "form_10ia_filed_80dd"))
    if inp.schedule_80u and inp.schedule_80u.deduction_amount > z:
        if not inp.schedule_80u.disability_type:
            results.append(_make("ITR4-R251", False,
                "80U > 0: disability type must be specified",
                "schedule_80u.disability_type"))
        if not inp.form_10ia_filed_80u:
            results.append(_make("ITR4-R253", False,
                "80U claimed but separate Form 10-IA not filed for 80U",
                "form_10ia_filed_80u"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Capital Gains / LTCG 112A (CBDT Sl 266)
    # ═══════════════════════════════════════════════════════════════════════════

    # R266i: Informational — every LTCG filer gets this formula reminder
    if cg and cg.ltcg_112a > z:
        results.append(_info("ITR4-R266",
            "LTCG u/s 112A should equal sale consideration minus cost of acquisition. "
            "Ensure FMV as on 31-01-2018 is used for grandfathering.",
            "capital_gains.ltcg_112a"))

    # R266: LTCG 112A = FV - COA (hard cross-foot when both values present)
    if inp.full_value_of_consideration and cg and cg.cost_of_acquisition > z:
        expected_ltcg = inp.full_value_of_consideration - cg.cost_of_acquisition
        if abs(cg.ltcg_112a - expected_ltcg) > Decimal("1"):
            results.append(_make("ITR4-R266", False,
                f"LTCG 112A (Rs {cg.ltcg_112a}) ≠ FV (Rs {inp.full_value_of_consideration}) "
                f"- COA (Rs {cg.cost_of_acquisition}) = Rs {expected_ltcg}",
                "capital_gains.ltcg_112a"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80EE/80EEA/80EEB Loan Validations (CBDT Sl 270-281, 301)
    # ═══════════════════════════════════════════════════════════════════════════

    # R270: 80EE/80EEA must exhaust 24(b) first
    if ch6a and (ch6a.amount_80ee > z or ch6a.amount_80eea > z):
        if hp and hp.home_loan_interest_paid <= z:
            results.append(_make("ITR4-R270", False,
                "80EE/80EEA claimed but no 24(b) home loan interest. 24(b) must be "
                "claimed first.", "deductions_chapter6a"))

    # R271-R272: 80EE/80EEA loan ⊆ 24(b) loan list
    if inp.loan_details_80ee and inp.loan_details_24b_list:
        found = any(
            ld.lender_name == getattr(inp.loan_details_80ee, 'lender_name', '')
            for ld in inp.loan_details_24b_list
        )
        if not found:
            results.append(_make("ITR4-R271", False,
                "80EE loan not found in Schedule 24(b) loan list", "loan_details_80ee"))
    if inp.loan_details_80eea and inp.loan_details_24b_list:
        found = any(
            ld.lender_name == getattr(inp.loan_details_80eea, 'lender_name', '')
            for ld in inp.loan_details_24b_list
        )
        if not found:
            results.append(_make("ITR4-R272", False,
                "80EEA loan not found in Schedule 24(b) loan list", "loan_details_80eea"))

    # R273-R275, R277, R280: Bank/schedule details required when deduction claimed
    if ch6a and ch6a.amount_80c > z and not inp.schedule_80c_entries:
        results.append(_make("ITR4-R273", False,
            "80C: deduction of Rs {0} claimed but no Schedule 80C row details "
            "provided. Schedule 80C entries are mandatory (CBDT Sl 273).".format(ch6a.amount_80c),
            "deductions_chapter6a.amount_80c"))
    if ch6a and ch6a.amount_80e > z and not inp.schedule_80e_entries:
        results.append(_make("ITR4-R274", False,
            "80E: deduction of Rs {0} claimed but no Schedule 80E details "
            "provided (CBDT Sl 274).".format(ch6a.amount_80e),
            "deductions_chapter6a.amount_80e"))
    if ch6a and ch6a.amount_80ee > z and not inp.loan_details_80ee_list \
            and not inp.loan_details_80ee:
        results.append(_make("ITR4-R275", False,
            "80EE: deduction of Rs {0} claimed but no loan details "
            "provided (CBDT Sl 275).".format(ch6a.amount_80ee),
            "deductions_chapter6a.amount_80ee"))
    if ch6a and ch6a.amount_80eea > z and not inp.loan_details_80eea_list \
            and not inp.loan_details_80eea:
        results.append(_make("ITR4-R277", False,
            "80EEA: deduction of Rs {0} claimed but no loan details "
            "provided (CBDT Sl 277).".format(ch6a.amount_80eea),
            "deductions_chapter6a.amount_80eea"))
    if ch6a and ch6a.amount_80eeb > z and not inp.loan_details_80eeb_list \
            and not inp.loan_details_80eeb:
        results.append(_make("ITR4-R280", False,
            "80EEB: deduction of Rs {0} claimed but no loan details "
            "provided (CBDT Sl 280).".format(ch6a.amount_80eeb),
            "deductions_chapter6a.amount_80eeb"))

    # R276: 80EE max loan ≤ ₹35 lakh
    if ch6a and ch6a.amount_80ee > z and inp.loan_details_80ee:
        if inp.loan_details_80ee.loan_amount > Decimal("3500000"):
            results.append(_make("ITR4-R276", False,
                f"80EE loan amount (Rs {inp.loan_details_80ee.loan_amount}) exceeds "
                f"₹35 lakh", "loan_details_80ee.loan_amount"))

    # R278: 80EEA stamp duty ≤ ₹45 lakh
    if ch6a and ch6a.amount_80eea > z and inp.loan_details_80eea:
        if inp.loan_details_80eea.loan_amount > Decimal("4500000"):
            results.append(_make("ITR4-R278", False,
                f"80EEA loan (Rs {inp.loan_details_80eea.loan_amount}) exceeds ₹45 lakh "
                f"stamp value limit", "loan_details_80eea.loan_amount"))

    # R279-R281: 80EEA/80EEB sanction date ranges
    if inp.loan_details_80eea and getattr(inp.loan_details_80eea, 'sanction_date', None):
        sd = inp.loan_details_80eea.sanction_date
        if sd < date(2019, 4, 1) or sd > date(2022, 3, 31):
            results.append(_make("ITR4-R279", False,
                f"80EEA loan sanction {sd} outside 01.04.2019-31.03.2022",
                "loan_details_80eea.sanction_date"))
    if inp.loan_details_80eeb and getattr(inp.loan_details_80eeb, 'sanction_date', None):
        sd = inp.loan_details_80eeb.sanction_date
        if sd < date(2019, 4, 1) or sd > date(2023, 3, 31):
            results.append(_make("ITR4-R281", False,
                f"80EEB loan sanction {sd} outside 01.04.2019-31.03.2023",
                "loan_details_80eeb.sanction_date"))

    # R301: 80EE sanction date 01.04.2016-31.03.2017
    if inp.loan_details_80ee and getattr(inp.loan_details_80ee, 'sanction_date', None):
        sd = inp.loan_details_80ee.sanction_date
        if sd < date(2016, 4, 1) or sd > date(2017, 3, 31):
            results.append(_make("ITR4-R301", False,
                f"80EE loan sanction {sd} outside 01.04.2016-31.03.2017",
                "loan_details_80ee.sanction_date"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 24(b) / 80C / 80E / 80EE / 80EEA / 80EEB Schedule Totals
    # (CBDT Sl 289-296)
    # ═══════════════════════════════════════════════════════════════════════════

    # R289: 24(b) total = schedule 24(b) total
    total_24b = Decimal("0")
    if inp.loan_details_24b_list and hp and hp.home_loan_interest_paid > z:
        total_24b = sum(
            ld.interest_paid_self_occupied + ld.interest_paid_let_out
            for ld in inp.loan_details_24b_list
        )
        if total_24b > z and abs(hp.home_loan_interest_paid - total_24b) > Decimal("1"):
            results.append(_make("ITR4-R289", False,
                f"24(b) interest (Rs {hp.home_loan_interest_paid}) ≠ sum of loan rows "
                f"(Rs {total_24b})", "house_property_income.home_loan_interest_paid"))

    # R290-R294: 80C/80E/80EE/80EEA/80EEB VIA = schedule total
    if ch6a and ch6a.amount_80c > z and inp.schedule_80c_entries:
        sc_sum = sum(e.amount for e in inp.schedule_80c_entries)
        if sc_sum > z and ch6a.amount_80c != sc_sum:
            results.append(_make("ITR4-R290", False,
                f"80C VIA (Rs {ch6a.amount_80c}) ≠ Schedule 80C total (Rs {sc_sum})",
                "deductions_chapter6a.amount_80c"))
    if ch6a and ch6a.amount_80e > z and inp.schedule_80e_entries:
        se_sum = sum(e.interest_paid for e in inp.schedule_80e_entries)
        if se_sum > z and ch6a.amount_80e != se_sum:
            results.append(_make("ITR4-R291", False,
                f"80E VIA (Rs {ch6a.amount_80e}) ≠ Schedule 80E total (Rs {se_sum})",
                "deductions_chapter6a.amount_80e"))
    if ch6a and ch6a.amount_80ee > z and inp.loan_details_80ee_list:
        ee_sum = sum(e.interest_paid for e in inp.loan_details_80ee_list)
        if ee_sum > z and ch6a.amount_80ee != ee_sum:
            results.append(_make("ITR4-R292", False,
                f"80EE VIA (Rs {ch6a.amount_80ee}) ≠ Schedule 80EE total (Rs {ee_sum})",
                "deductions_chapter6a.amount_80ee"))
    if ch6a and ch6a.amount_80eea > z and inp.loan_details_80eea_list:
        eea_sum = sum(e.interest_paid for e in inp.loan_details_80eea_list)
        if eea_sum > z and ch6a.amount_80eea != eea_sum:
            results.append(_make("ITR4-R293", False,
                f"80EEA VIA (Rs {ch6a.amount_80eea}) ≠ Schedule 80EEA total (Rs {eea_sum})",
                "deductions_chapter6a.amount_80eea"))
    if ch6a and ch6a.amount_80eeb > z and inp.loan_details_80eeb_list:
        eeb_sum = sum(e.interest_paid for e in inp.loan_details_80eeb_list)
        if eeb_sum > z and ch6a.amount_80eeb != eeb_sum:
            results.append(_make("ITR4-R294", False,
                f"80EEB VIA (Rs {ch6a.amount_80eeb}) ≠ Schedule 80EEB total (Rs {eeb_sum})",
                "deductions_chapter6a.amount_80eeb"))

    # R295-R296: Per-schedule row sum = total of payments
    if inp.loan_details_24b_list:
        total_rows = sum(
            ld.interest_paid_self_occupied + ld.interest_paid_let_out
            for ld in inp.loan_details_24b_list
        )
        if total_rows != total_24b and total_24b > z:
            results.append(_make("ITR4-R295", False,
                "24(b): sum of individual rows ≠ total", "loan_details_24b_list"))
    if inp.schedule_80c_entries:
        sc_sum2 = sum(e.amount for e in inp.schedule_80c_entries)
        if ch6a and ch6a.amount_80c > z and ch6a.amount_80c != sc_sum2:
            results.append(_make("ITR4-R296", False,
                "80C: sum of individual rows ≠ total", "schedule_80c_entries"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Section 192 Not in TDS2/TDS3 (CBDT Sl 310)
    # ═══════════════════════════════════════════════════════════════════════════

    for i, e in enumerate(inp.tds2_entries or []):
        if getattr(e, 'tds_section', '') == '192':
            results.append(_make("ITR4-R310", False,
                f"TDS2 entry {i+1}: Section 192 must be in TDS1 not TDS2",
                f"tds2_entries[{i}].tds_section"))
    for i, e in enumerate(inp.tds3_entries or []):
        if getattr(e, 'tds_section', '') == '192':
            results.append(_make("ITR4-R310b", False,
                f"TDS3 entry {i+1}: Section 192 must be in TDS1",
                f"tds3_entries[{i}].tds_section"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: HRA Formulae + Schedule 10(13A) (CBDT Sl 311-313, 315-316, 320)
    # ═══════════════════════════════════════════════════════════════════════════

    # R311: HRA exemption formula guidance
    if sal and sal.hra_exempt_amount > z:
        results.append(_info("ITR4-R311",
            "HRA exemption = least of: actual HRA, rent paid - 10%(basic+DA), "
            "40/50%(basic+DA). Ensure salary_for_hra in HRA Details represents basic+DA.",
            "hra_details"))

    # R315-R316: Schedule 10(13A) required for HRA; basic+DA+HRA ≤ 17(1)
    if sal and sal.hra_exempt_amount > z:
        if not inp.hra_details and not inp.schedule_10_13a:
            results.append(_make("ITR4-R315", False,
                "HRA exemption claimed but Schedule 10(13A) not provided", "hra_details"))
    if inp.schedule_10_13a:
        hra_s = inp.schedule_10_13a
        if hra_s.salary_for_hra + hra_s.actual_hra_received > sal.gross_salary:
            results.append(_make("ITR4-R316", False,
                "10(13A): Basic+DA+HRA exceeds salary 17(1)", "schedule_10_13a"))

    # R320: 10(13A) exempt = Schedule 10(13A) eligible
    if inp.schedule_10_13a and sal and sal.hra_exempt_amount > z:
        if sal.hra_exempt_amount > inp.schedule_10_13a.exempt_amount_claimed:
            results.append(_make("ITR4-R320", False,
                f"HRA exempt (Rs {sal.hra_exempt_amount}) ≠ Schedule 10(13A) eligible "
                f"(Rs {inp.schedule_10_13a.exempt_amount_claimed})",
                "salary_income.hra_exempt_amount"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Gratuity CG/SG ₹25L Cap (CBDT Sl 317)
    # ═══════════════════════════════════════════════════════════════════════════

    if sal and sal.gratuity_received > z and inp.nature_of_employment:
        emp_l = inp.nature_of_employment.lower()
        if any(kw in emp_l for kw in ("central", "state")) and "government" in emp_l:
            if sal.gratuity_received > Decimal("2500000"):
                results.append(_make("ITR4-R317", False,
                    f"Gratuity (Rs {sal.gratuity_received}) exceeds ₹25L for CG/SG",
                    "salary_income.gratuity_received"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION: Tax Regime + Filing Section + BP (moved from Post-Computation section)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 235: Tax regime not applicable for Firm — must be "not applicable"
    if is_firm:
        if inp.tax_regime and inp.tax_regime != TaxRegime.OLD:
            results.append(_make("ITR4-R235", False,
                "Firm: Tax regime must be Old / Not Applicable.",
                "tax_regime"))

    # Sl 260: 115BAC (A23) mandatory selection for Individual/HUF
    if is_individual or is_huf:
        if inp.tax_regime is None:
            results.append(_make("ITR4-R260", False,
                "A23: Tax regime selection (115BAC) is mandatory for Individual and HUF.",
                "tax_regime"))

    # Sl 264: Firm: A23 fields must be blank
    if is_firm:
        if (inp.has_filed_10iea_earlier is not None
                or inp.has_reentered_new_regime is not None
                or inp.has_filed_10iea_current is not None
                or inp.a23_earlier_ay is not None
                or inp.a23_reenter_ay is not None):
            results.append(_make("ITR4-R264", False,
                "Firm: A23 10-IEA fields must be blank/greyed out. "
                "Tax regimes and 10-IEA are for Individuals/HUFs only.",
                "tax_regime"))

    # Sl 321: Only one of A23A or A23B applicable
    if not is_firm:
        a23a_filled = (inp.has_filed_10iea_earlier is not None
                       or inp.a23_earlier_ay is not None
                       or inp.has_reentered_new_regime is not None
                       or inp.a23_reenter_ay is not None)
        a23b_filled = inp.has_filed_10iea_current is not None
        if a23a_filled and a23b_filled:
            results.append(_make("ITR4-R321", False,
                "A23: Both A23A (earlier 10-IEA path) and A23B (current year 10-IEA "
                "path) filled. Only one should be applicable per taxpayer situation.",
                "has_filed_10iea_earlier"))

    # Sl 228: 10-IEA details mandatory if "filed in earlier AY" = Yes
    if inp.has_filed_10iea_earlier is True:
        if not inp.form_10iea_filing_date and not inp.form_10iea_ack_no:
            results.append(_make("ITR4-R228", False,
                "A23(A)(i): 'Filed Form 10-IEA in earlier AY' is Yes, but no 10-IEA "
                "details (date/acknowledgement number) provided.",
                "form_10iea_filing_date"))

    # Sl 353-364, 393: 10-IEA complex chain
    if inp.has_filed_10iea_earlier is True:
        if inp.a23_earlier_ay is None:
            results.append(_make("ITR4-R353a", False,
                "A23(A)(i): Assessment year when first 10-IEA filed is mandatory.",
                "a23_earlier_ay"))
        if inp.has_reentered_new_regime is None:
            results.append(_make("ITR4-R353b", False,
                "A23(A)(ii): 'Re-entered new regime via 10-IEA?' is mandatory "
                "when A23 = Yes.", "has_reentered_new_regime"))
    if inp.has_filed_10iea_earlier is False:
        if inp.has_filed_10iea_current is None:
            results.append(_make("ITR4-R354", False,
                "A23: 'Filed 10-IEA earlier' is No, so A23(B) 'Filed 10-IEA current AY?' "
                "is mandatory.", "has_filed_10iea_current"))
    if inp.has_reentered_new_regime is True:
        if not inp.a23_reenter_ay and not inp.form_10iea_ack_no:
            results.append(_make("ITR4-R355", False,
                "A23(A)(ii)(a): Re-entered new regime — must provide AY and/or "
                "10-IEA acknowledgement number.", "a23_reenter_ay"))
    if inp.has_filed_10iea_current is True:
        if not inp.form_10iea_filing_date and not inp.form_10iea_ack_no:
            results.append(_make("ITR4-R359", False,
                "A23(B)(i): 'Filed 10-IEA current AY' is Yes — must provide "
                "date/acknowledgement number.", "form_10iea_filing_date"))
    if inp.a23_reenter_ay and inp.a23_earlier_ay:
        if inp.a23_reenter_ay <= inp.a23_earlier_ay:
            results.append(_make("ITR4-R393", False,
                f"A23(A)(ii)(a) re-enter AY ({inp.a23_reenter_ay}) must be > "
                f"original AY ({inp.a23_earlier_ay})", "a23_reenter_ay"))

    # NOTE: BP balance sheet cross-foot (Sl 3-4) is in the NEW VALIDATORS section
    # NOTE: Filing section constraints (Sl 167, 188) are in the NEW VALIDATORS section
    # NOTE: Firm A23 / 10-IEA chain (Sl 264, 321, 353-364) is above — consolidated here

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Judge Exemption (CBDT Sl 322, 365)
    # ═══════════════════════════════════════════════════════════════════════════

    # R322: Judge exemption only CG/SG
    if "Judge Salaries Act" in exempt_dds:
        emp_l = (inp.nature_of_employment or "").lower()
        if not any(kw in emp_l for kw in ("central government", "state government")):
            results.append(_make("ITR4-R322", False,
                f"Judge Salaries Act exemption claimed but employment is "
                f"'{inp.nature_of_employment}'", "exempt_income_dropdowns"))

    # R365: Judge exemption new regime = 0
    if is_new and "Judge Salaries Act" in exempt_dds:
        results.append(_make("ITR4-R365", False,
            "Judge Salaries Act exemption not available under new regime",
            "exempt_income_dropdowns"))

    # ═══════════════════════════════════════════════════════════════════════════
    # NOTE: CBDT Sl 324-342 — Eligible ≤ user-entered loop removed.
    # Each deduction already has a hard cap rule (R021, R145, R150, etc.) that
    # enforces the statutory maximum. Duplicate _info is unnecessary.
    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 89(1) Without Form 10E — Cat D:1 (CBDT Sl 162)
    # ═══════════════════════════════════════════════════════════════════════════

    # Cat D:1 — 89(1) relief claimed but Form 10E not furnished
    if sal and hasattr(sal, 'relief_us_89') and sal.relief_us_89 > z \
            and not inp.form_10e_filed:
        results.append(_info("ITR4-D001",
            "Relief u/s 89(1) claimed but Form 10E has not been furnished. "
            "Claim may be disallowed.", "form_10e_filed"))

    # R162: Relief u/s 89 requires salary/pension income
    if inp.form_10e_filed:
        has_sal = sal and sal.gross_salary > z
        has_fp = os_ and os_.family_pension_received > z
        if not has_sal and not has_fp:
            results.append(_make("ITR4-R162", False,
                "Form 10E filed but no salary or family pension income. "
                "Relief u/s 89 requires salary/family pension.", "form_10e_filed"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Co-Ownership, House Property Info (CBDT Sl 344-352, 405-408)
    # ═══════════════════════════════════════════════════════════════════════════

    # R344: Representative details — name, email, phone mandatory
    if inp.representative_details and inp.representative_details.capacity:
        if not inp.representative_details.represented_person_name:
            results.append(_make("ITR4-R344", False,
                "Representative: name is mandatory",
                "representative_details.represented_person_name"))
        if not inp.representative_email:
            results.append(_make("ITR4-R344b", False,
                "Representative: email is mandatory", "representative_email"))
        if not inp.representative_phone:
            results.append(_make("ITR4-R344c", False,
                "Representative: phone is mandatory", "representative_phone"))

    # R346-R351: Co-ownership HP details
    if inp.is_property_co_owned and inp.co_ownership_details:
        cod = inp.co_ownership_details
        if abs(cod.ownership_percentage + inp.other_co_owner_percentage
               - Decimal("100")) > Decimal("1"):
            results.append(_make("ITR4-R346", False,
                f"Co-owned: assessee % ({cod.ownership_percentage}) + other % "
                f"({inp.other_co_owner_percentage}) ≠ 100%",
                "co_ownership_details.ownership_percentage"))
        if cod.ownership_percentage <= z and hp and hp.home_loan_interest_paid > z:
            results.append(_make("ITR4-R348", False,
                "Co-owned with 0% share: interest cannot be claimed",
                "house_property_income.home_loan_interest_paid"))
        if inp.assessee_pan and cod.co_owner_pan and inp.assessee_pan == cod.co_owner_pan:
            results.append(_make("ITR4-R351", False,
                "Co-owned: assessee PAN = co-owner PAN",
                "co_ownership_details.co_owner_pan"))
    if not inp.is_property_co_owned and inp.co_ownership_details \
            and inp.co_ownership_details.ownership_percentage < 100:
        results.append(_make("ITR4-R404", False,
            "Not co-owned: assessee share must be 100%",
            "co_ownership_details.ownership_percentage"))

    # R405-R406: Co-owned → shares 0-100% exclusive
    if inp.is_property_co_owned and inp.co_ownership_details:
        if inp.co_ownership_details.ownership_percentage >= 100:
            results.append(_make("ITR4-R406", False,
                "Co-owned: assessee share must be < 100%",
                "co_ownership_details.ownership_percentage"))
        if inp.other_co_owner_percentage <= z \
                or inp.other_co_owner_percentage >= 100:
            results.append(_make("ITR4-R405", False,
                "Co-owned: other co-owner share must be > 0 and < 100%",
                "other_co_owner_percentage"))

    # R347: Co-owned AV = share * total AV
    if inp.is_property_co_owned and hp and inp.co_ownership_details:
        pct = inp.co_ownership_details.ownership_percentage / Decimal("100")
        if hp.annual_rent_received > z and pct > z:
            results.append(_info("ITR4-R347",
                f"Co-owned: your AV share should be {pct * 100}% of total annual value. "
                f"Verify.", "house_property_income"))
    results.append(_info("ITR4-R349",
        "HP: Sl 1d Total = 1b+1c (gross rent + arrears). Portal-level.",
        "house_property_income"))
    results.append(_info("ITR4-R350",
        "HP: Sl 1i Total = 1g+1h (interest payable on loan). Portal-level.",
        "house_property_income"))

    # R352,R408: Unrealized rent ≤ gross rent
    if hp and hp.arrears_unrealised_rent_received > z \
            and hp.annual_rent_received <= z:
        results.append(_make("ITR4-R352", False,
            "Unrealized rent > 0 but gross rent is 0", "house_property_income"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80CCC Sum Rows = VIA Total (CBDT Sl 366, 409)
    # ═══════════════════════════════════════════════════════════════════════════

    # R366: 80CCC sum rows = VIA total
    if ch6a and ch6a.amount_80ccc > z and inp.schedule_80ccc_entries:
        sc_sum = sum(e.amount for e in inp.schedule_80ccc_entries)
        if ch6a.amount_80ccc != sc_sum:
            results.append(_make("ITR4-R366", False,
                f"80CCC VIA (Rs {ch6a.amount_80ccc}) ≠ Schedule 80CCC total (Rs {sc_sum})",
                "deductions_chapter6a.amount_80ccc"))

    # R409: 80CCC > 0 → row details mandatory
    if ch6a and ch6a.amount_80ccc > z:
        if not inp.schedule_80ccc_entries:
            results.append(_make("ITR4-R409", False,
                "80CCC claimed but no per-row details provided. Insurer name, "
                "policy number required.", "deductions_chapter6a.amount_80ccc"))
        else:
            for i, e in enumerate(inp.schedule_80ccc_entries):
                if e.amount > z and (not e.insurer_name or not e.policy_number):
                    results.append(_make("ITR4-R409b", False,
                        f"80CCC row {i+1}: amount Rs {e.amount} but insurer/policy missing",
                        f"schedule_80ccc_entries[{i}]"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: New Regime 10(32) Minor Child + 234-I (CBDT Sl 391-392)
    # ═══════════════════════════════════════════════════════════════════════════

    # R391: New regime 10(32) minor child = 0
    if is_new and any("minor child" in d.lower() for d in exempt_dds):
        results.append(_make("ITR4-R391", False,
            "New regime: Sec 10(32) minor child income exemption not allowed",
            "exempt_income_dropdowns"))

    # R392: 234-I fees for revised returns after 31/12/2026
    if inp.filing_section == "139(5)" and inp.filing_date \
            and inp.filing_date > date(2026, 12, 31):
        results.append(_make("ITR4-R392", True,
            "Revised return filed after 31/12/2026. Fee u/s 234-I: ₹1,000 if "
            "TI ≤ ₹5L, ₹5,000 if TI > ₹5L.", "filing_date"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: PRAN + Representative Validation (CBDT Sl 402-403, 407, 410-411)
    # ═══════════════════════════════════════════════════════════════════════════

    # R402: PRAN required for 80CCD(1)/80CCD(1B)
    if ch6a and (ch6a.amount_80ccd1 > z or ch6a.amount_80ccd1b > z) \
            and not inp.pran_number:
        results.append(_make("ITR4-R402", False,
            "80CCD(1)/80CCD(1B) claimed but PRAN not provided", "pran_number"))

    # R403: Rep email/phone ≠ taxpayer
    if inp.representative_email and inp.assessee_email_primary \
            and inp.representative_email.lower() == inp.assessee_email_primary.lower():
        results.append(_make("ITR4-R403", False,
            "Representative email must differ from assessee email",
            "representative_email"))
    if inp.representative_phone and inp.assessee_phone_primary \
            and inp.representative_phone == inp.assessee_phone_primary:
        results.append(_make("ITR4-R403b", False,
            "Representative phone must differ from assessee phone",
            "representative_phone"))

    # R407: PRAN entered but 80CCD(1)+80CCD(1B)=0 — HARD (CBDT Sl 407)
    if inp.pran_number and ch6a and ch6a.amount_80ccd1 == z \
            and ch6a.amount_80ccd1b == z:
        results.append(_make("ITR4-R407", False,
            f"PRAN ({inp.pran_number}) provided but 80CCD(1) and 80CCD(1B) "
            f"are 0. PRAN requires at least one of these deductions (CBDT Sl 407).",
            "pran_number"))

    # R410: Secondary address mandatory for representative
    if inp.representative_details and inp.representative_details.capacity \
            and not inp.secondary_address:
        results.append(_make("ITR4-R410", False,
            "Representative filing: secondary address is mandatory",
            "secondary_address"))

    # R411: Secondary ≠ primary address (informational)
    results.append(_info("ITR4-R411",
        "Secondary address must not equal primary address. Portal-level check.",
        "secondary_address"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: DOI Blocks (CBDT Sl 318-319)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.date_of_incorporation:
        if is_firm or is_huf:
            if inp.date_of_incorporation >= date(2026, 4, 1):
                results.append(_make("ITR4-R318", False,
                    f"Firm/HUF formed on/after 01/04/2026 ({inp.date_of_incorporation}) "
                    f"cannot file AY 2026-27", "date_of_incorporation"))
        elif is_individual:
            if inp.date_of_incorporation >= date(2008, 4, 1):
                results.append(_make("ITR4-R319", False,
                    f"Individual with DOI on/after 01/04/2008 "
                    f"({inp.date_of_incorporation}) cannot file ITR-4",
                    "date_of_incorporation"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Schedule BP Balance Sheet Cross-Foot (CBDT Sl 3-4)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.schedule_bp_financial:
        bpf = inp.schedule_bp_financial
        # Sl 3: E17 Total Capital+Liabilities = components
        if bpf.total_capital_liabilities > z:
            liab_sum = (bpf.partners_capital + bpf.secured_loans + bpf.unsecured_loans
                        + bpf.advances_received + bpf.sundry_creditors + bpf.other_liabilities)
            if abs(bpf.total_capital_liabilities - liab_sum) > Decimal("1"):
                results.append(_make("ITR4-R003", False,
                    f"BP E17: Total capital & liabilities (Rs {bpf.total_capital_liabilities}) "
                    f"≠ sum of components (Rs {liab_sum})",
                    "schedule_bp_financial.total_capital_liabilities",
                    expected=str(liab_sum), actual=str(bpf.total_capital_liabilities)))
        # Sl 4: E25 Total Assets = components
        if bpf.total_assets > z:
            assets_sum = (bpf.fixed_assets + bpf.investments_bp + bpf.inventories
                          + bpf.sundry_debtors + bpf.balance_with_banks + bpf.cash_in_hand
                          + bpf.loans_and_advances + bpf.other_assets)
            if abs(bpf.total_assets - assets_sum) > Decimal("1"):
                results.append(_make("ITR4-R004", False,
                    f"BP E25: Total assets (Rs {bpf.total_assets}) "
                    f"≠ sum of components (Rs {assets_sum})",
                    "schedule_bp_financial.total_assets",
                    expected=str(assets_sum), actual=str(bpf.total_assets)))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Filing Section / Revision Blocks (CBDT Sl 167, 188)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 167: 142(1) original → cannot file revised return
    if inp.original_filing_section and inp.original_filing_section == "142(1)" \
            and inp.filing_section and inp.filing_section == "139(5)":
        results.append(_make("ITR4-R167", False,
            "Original return filed u/s 142(1) (notice). Revised return u/s 139(5) "
            "not allowed for 142(1) proceedings.", "filing_section"))

    # Sl 188: 148 proceeding → original 139 return cannot be revised
    if inp.is_148_proceeding \
            and inp.filing_section and inp.filing_section == "139(5)":
        results.append(_make("ITR4-R188", False,
            "Proceeding u/s 148 initiated — original return filed u/s 139 cannot be "
            "revised u/s 139(5).", "filing_section"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Post-Computation Info / Cat D Rules
    # ═══════════════════════════════════════════════════════════════════════════

    # R343: LTCG 112A = GTI_incl - GTI_excl (informational post-computation)
    results.append(_info("ITR4-R343",
        "LTCG 112A should equal GTI including LTCG minus GTI excluding LTCG. "
        "Verified post-computation.", "capital_gains"))

    # R185-R187: Old regime 10(14)(i)/(ii) info
    if is_old and sal:
        if getattr(sal, 'sec10_14i_prescribed_allowance', z) > z:
            results.append(_info("ITR4-R187",
                f"10(14)(i) allowance Rs {sal.sec10_14i_prescribed_allowance} claimed. "
                "Ensure actual incurrence for official duties.",
                "salary_income.sec10_14i_prescribed_allowance"))

    # Cat D rule 2: 80GG ≤ ₹5,000/month or actual rent
    results.append(_info("ITR4-D002",
        "80GG deduction max: ₹5,000/month (₹60,000/year) or actual rent paid, "
        "whichever lower. Verified post-computation.", "deductions_chapter6a.amount_80gg"))

    # ========================================================================
    # SECTION: CBDT Category B — Warnings (ITR-4 specific)
    # ========================================================================

    # CBDT B1: TDS1 cannot exceed gross salary
    if sal and tds1_s > z and tds1_s > sal.gross_salary:
        results.append(_warn("ITR4-B001_CBDT",
            f"TDS on salary (Rs {tds1_s}) exceeds gross salary "
            f"(Rs {sal.gross_salary}).", "tds1_entries"))

    # CBDT B3: Aadhaar-PAN linking
    results.append(_warn("ITR4-B003_CBDT",
        "Aadhaar-PAN linking required per CBDT Circular 03/2023.", "aadhaar_number"))

    # CBDT B4: Quoting Aadhaar
    results.append(_warn("ITR4-B004_CBDT",
        "Quoting Aadhaar in ITR mandatory u/s 139(AA).", "aadhaar_number"))

    # CBDT B5: Nil return — check AIS/26AS
    results.append(_info("ITR4-B005_CBDT",
        "Nil return filers should check AIS/26AS before filing.", ""))

    # CBDT B6-B8: TDS2 special-rate / NR sections → ITR-4 ineligible
    ineligible_tds = {"194B", "194BB", "194BA", "194IA", "194IC", "194LA", "194R", "194S"}
    nr_tds = {"194E", "194LB", "194LC", "194LBA", "195", "196A", "196B", "196C", "196D"}
    for i, e in enumerate(inp.tds2_entries or []):
        sec = getattr(e, 'tds_section', '') or ''
        if sec in ineligible_tds:
            results.append(_warn("ITR4-B006_CBDT",
                f"TDS2 entry {i+1}: Section {sec} indicates special-rate income. "
                f"ITR-4 may not apply.", f"tds2_entries[{i}].tds_section"))
        if sec in nr_tds:
            results.append(_warn("ITR4-B008_CBDT",
                f"TDS2 entry {i+1}: Section {sec} indicates NR/foreign income. "
                f"ITR-4 is for residents only.", f"tds2_entries[{i}].tds_section"))

    # B1-B13 internal ITR-4 warnings (existing)
    if sal and sal.gross_salary > 5_000_000:
        results.append(_warn("ITR4-B001",
            f"Gross salary (Rs {sal.gross_salary}) > ₹50L — consider ITR-3.",
            "salary_income.gross_salary"))
    if sal and sal.hra_exempt_amount > z and sal.gross_salary > z \
            and sal.hra_exempt_amount / sal.gross_salary > Decimal("0.5"):
        results.append(_warn("ITR4-B002",
            f"HRA > 50% of salary — unusually high.",
            "salary_income.hra_exempt_amount"))
    if sal and sal.professional_tax_paid > 2_500:
        results.append(_warn("ITR4-B003",
            f"Professional tax Rs {sal.professional_tax_paid} > ₹2,500 cap.",
            "salary_income.professional_tax_paid"))
    if sal and sal.gross_salary > z and sal.standard_deduction_claimed == z:
        results.append(_warn("ITR4-B004",
            "Standard deduction not claimed despite salary income.",
            "salary_income.standard_deduction_claimed"))
    if ch6a and ch6a.amount_80c > z and sal and sal.gross_salary > z \
            and ch6a.amount_80c > sal.gross_salary:
        results.append(_warn("ITR4-B005",
            f"80C (Rs {ch6a.amount_80c}) exceeds salary.",
            "deductions_chapter6a.amount_80c"))
    if hp and hp.home_loan_interest_paid > z and inp.loan_details_24b_list:
        total_principal = sum(ld.loan_amount for ld in inp.loan_details_24b_list)
        if total_principal > z and hp.home_loan_interest_paid > total_principal * 2:
            results.append(_warn("ITR4-B006",
                f"Home loan interest > 2x principal.",
                "house_property_income.home_loan_interest_paid"))
    if ch6a and ch6a.amount_80d_self_family == 25_000 and inp.schedule_80d \
            and not inp.schedule_80d.has_self_senior:
        results.append(_warn("ITR4-B007",
            "80D Self exactly ₹25K — verify senior flag.",
            "deductions_chapter6a.amount_80d_self_family"))
    if ch6a and ch6a.amount_80d_parents == 25_000 and inp.schedule_80d \
            and not inp.schedule_80d.has_parents_senior:
        results.append(_warn("ITR4-B008",
            "80D Parents exactly ₹25K — verify senior flag.",
            "deductions_chapter6a.amount_80d_parents"))
    if ch6a and ch6a.amount_80eea > z and (not hp or hp.home_loan_interest_paid == z):
        results.append(_warn("ITR4-B009",
            "80EEA claimed but no home loan interest.",
            "deductions_chapter6a.amount_80eea"))
    if inp.business_income_44ad and inp.business_income_44ad.total_turnover > z \
            and inp.business_income_44ad.total_turnover < 50_000:
        results.append(_warn("ITR4-B010",
            f"Turnover Rs {inp.business_income_44ad.total_turnover} very low.",
            "business_income_44ad.total_turnover"))
    if inp.tds1_entries and len(inp.tds1_entries) > 3:
        results.append(_warn("ITR4-B011",
            f"{len(inp.tds1_entries)} TDS1 entries — verify.", "tds1_entries"))
    if sal and sal.gross_salary > 300_000 \
            and (not inp.tds1_entries or len(inp.tds1_entries) == 0):
        results.append(_warn("ITR4-B012",
            f"Salary Rs {sal.gross_salary} but no TDS1.", "tds1_entries"))
    if cg and cg.ltcg_112a == z:
        results.append(_warn("ITR4-B013",
            "Capital gains schedule populated but LTCG=0.", "capital_gains"))

    return results
