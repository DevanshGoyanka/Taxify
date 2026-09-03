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
from datetime import date
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme,
)
from app.schemas.itr1 import AgeBracket, TaxRegime, PropertyType, AssesseeType
from app.engine.validators.base import ValidationResult, Severity


# ── Helpers ──────────────────────────────────────────────────────────────────

# inp.nature_of_employment carries the raw official code -- CGOV/SGOV/PSU/
# PE/PESG/PEPS/PEO/OTH (see app/engine/draft_to_itr4_input.py's ITR4Input
# construction, sourced from draft.employers[0].natureOfEmployment, the same
# NatureOfEmployment field ITR-1's mapper reads) -- never a human-readable
# label. Ten call sites in this file used to match keywords like "central
# government"/"pension" against it, which never matched any real code -- the
# identical bug already found and fixed across 10 sites in
# app/engine/validators/itr1/input_rules.py (Docs/ITR1_FRONTEND_AND_
# SERIALIZATION_AUDIT_AY2026_27.md §14.5). Each was either permanently
# dormant (never caught a real invalid claim) or permanently blocking (fired
# regardless of actual employment, hard-blocking legitimate CG/SG-employee/
# pensioner/judge filers). These two sets are the single source of truth for
# that classification going forward, matching ITR-1's exact code sets.
_CG_SG_EMPLOYMENT_CODES = frozenset({"CGOV", "SGOV"})
_PENSIONER_EMPLOYMENT_CODES = frozenset({"PE", "PESG", "PEPS", "PEO"})


def _is_cg_sg_employee(nature_of_employment: str | None) -> bool:
    return (nature_of_employment or "") in _CG_SG_EMPLOYMENT_CODES


def _is_pensioner(nature_of_employment: str | None) -> bool:
    return (nature_of_employment or "") in _PENSIONER_EMPLOYMENT_CODES


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

    # R043 (CBDT Sl 43: "HUF/Firm claiming 80U"): unlike 80DD/80DDB (which
    # concern a DEPENDENT's disability -- a HUF member is a valid dependent,
    # per CBDT Sl 254 -- so those stay Firm-only above), 80U is specifically
    # the ASSESSEE's OWN disability, which neither an HUF nor a Firm can
    # have. Checked for both, not nested under the is_firm block above (a
    # HUF claiming 80U was previously never blocked at all).
    if (is_firm or is_huf) and ch6a and ch6a.amount_80u > z:
        results.append(_make(
            "ITR4-R043", False,
            f"{'Firms' if is_firm else 'HUFs'} cannot claim deduction under 80U "
            f"(individuals only).",
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

    # Rule 140: No presumptive income block disclosed
    if not any((
        inp.business_income_44ad,
        inp.professional_income_44ada,
        inp.goods_carriage_44ae,
    )):
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
    if any((inp.business_income_44ad, inp.professional_income_44ada, inp.goods_carriage_44ae)):
        if inp.business_income_44ad:
            if inp.business_income_44ad.total_turnover > z:
                results.append(_info(
                    "ITR4-R139a",
                    "Gross receipts disclosed under 44AD. Ensure corresponding financial "
                    "particulars (Schedule BP) are properly filled in the ITR utility.",
                    "business_income_44ad"))
        if inp.professional_income_44ada:
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
    if inp.business_income_44ad:
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
    # Rule 12: 44AD business code selected → must declare 44AD income — HARD
    # A business code is valid for 44AD, 44ADA, and 44AE (Sl 137 requires it
    # for each). This rule only fires when a business code is present but NO
    # presumptive scheme is active — i.e. the taxpayer picked a 44AD-range
    # code without opting into 44AD. 44ADA/44AE have their own code checks.
    if inp.business_code and not (inp.business_income_44ad or inp.goods_carriage_44ae):
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

    # Rule 239: 44AD turnover split check — bank + cash + other mode == total
    if inp.business_income_44ad:
        ad = inp.business_income_44ad
        split_turnover = (
            ad.digital_turnover + ad.cash_turnover + ad.other_mode_turnover
        )
        if split_turnover != ad.total_turnover:
            results.append(_make(
                "ITR4-R239", False,
                f"44AD turnover split mismatch: digital ({ad.digital_turnover}) + "
                f"cash ({ad.cash_turnover}) + other mode ({ad.other_mode_turnover}) "
                f"!= total ({ad.total_turnover})",
                "business_income_44ad",
                expected=str(ad.total_turnover),
                actual=str(split_turnover)))

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
    if inp.professional_income_44ada:
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
    if inp.profession_code and not inp.professional_income_44ada:
        results.append(_make(
            "ITR4-R017b", False,
            f"Profession code '{inp.profession_code}' for 44ADA is selected but 44ADA "
            f"scheme is not active (CBDT Sl 17).",
            "profession_code"))

    # Rule 212: HUF not eligible for 44ADA — HARD
    if is_huf and inp.professional_income_44ada:
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
        split_receipts = (
            ada.digital_receipts + ada.cash_receipts + ada.other_mode_receipts
        )
        if split_receipts != ada.gross_receipts:
            results.append(_make(
                "ITR4-R240", False,
                f"44ADA receipts split mismatch: digital ({ada.digital_receipts}) + "
                f"cash ({ada.cash_receipts}) + other mode ({ada.other_mode_receipts}) "
                f"!= total ({ada.gross_receipts})",
                "professional_income_44ada",
                expected=str(ada.gross_receipts),
                actual=str(split_receipts)))

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
    if inp.goods_carriage_44ae:
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
            if _is_pensioner(emp):
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
            if not _is_pensioner(emp):
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
            if not _is_cg_sg_employee(emp):
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
            if _is_cg_sg_employee(emp):
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
            if _is_pensioner(emp):
                results.append(_make(
                    "ITR4-R161", False,
                    f"80CCD(2) NPS employer contribution not available for pensioners. "
                    f"Employment: {inp.nature_of_employment}",
                    "deductions_chapter6a.amount_80ccd2",
                    expected="0 for pensioners", actual=str(ch6a.amount_80ccd2)))

        # Rule 168: 80D self/family non-senior <= Rs 25,000
        self_is_senior = (
            inp.schedule_80d.has_self_senior if inp.schedule_80d else is_senior
        )
        parents_are_senior = (
            inp.schedule_80d.has_parents_senior if inp.schedule_80d else False
        )
        if ch6a.amount_80d_self_family > Decimal("25000") and not self_is_senior:
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
        if (
            ch6a.amount_80d_parents > Decimal("25000")
            and not parents_are_senior
        ):
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
        d80_combined = (
            ch6a.amount_80d_self_family
            + ch6a.amount_80d_preventive_self
            + ch6a.amount_80d_parents
            + ch6a.amount_80d_preventive_parents
        )
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
                d_total = (
                    ch6a.amount_80d_self_family
                    + ch6a.amount_80d_parents
                    + ch6a.amount_80d_preventive_self
                    + ch6a.amount_80d_preventive_parents
                )
                sch_total = (sd.premium_1a_non_senior + sd.premium_1b_senior
                             + sd.premium_2a_parents_non_senior + sd.premium_2b_parents_senior
                             + sd.preventive_checkup_self + sd.preventive_checkup_parents
                             + sd.medical_expense_self_senior
                             + sd.medical_expense_parents_senior)
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
                    "ITR4-R182-2", False,
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
                        "ITR4-R147-2", False,
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
            if ch6a.amount_80dd > z and not inp.form_10ia_filed:
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
                salary_factor = hd.salary_for_hra * (
                    Decimal("0.50") if hd.is_metro_city else Decimal("0.40")
                )
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

    # R071: Agricultural income > ₹5,000 is ELIGIBLE for ITR-4 — it triggers
    # partial integration u/s 10(1) (Finance Act, Part I First Schedule).
    # The calculator handles this via compute_partial_integration_tax.
    # This is informational only, NOT a blocking error.
    if inp.agriculture_income > Decimal("5000"):
        results.append(_info(
            "ITR4-R071",
            f"Agricultural income (Rs {inp.agriculture_income}) exceeds ₹5,000. "
            f"Partial integration of agricultural income applies under old regime. "
            f"Calculator computes additional tax per Finance Act Part I First Schedule.",
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
    if inp.business_income_44ad:
        ad = inp.business_income_44ad
        if ad.income_declared and ad.income_declared > z:
            digital_and_other = ad.digital_turnover + ad.other_mode_turnover
            min_digital = digital_and_other * Decimal("0.06")
            if digital_and_other > z and ad.income_declared < min_digital:
                results.append(_make("ITR4-R005a", False,
                    f"44AD: income declared (Rs {ad.income_declared}) < 6% of digital turnover "
                    f"(Rs {min_digital})", "business_income_44ad.income_declared"))
    # Sl 6: 44AD income >= 8% of cash turnover (individual rate check)
    if inp.business_income_44ad:
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
    if inp.business_code and not (inp.business_income_44ad or inp.goods_carriage_44ae):
        results.append(_info("ITR4-R012a",
            "Business code for 44AD selected but 44AD scheme not active. Verify.", "business_code"))
    # Sl 17: profession code selected → must declare 44ADA income
    if inp.profession_code and not inp.professional_income_44ada:
        results.append(_info("ITR4-R017a",
            "Profession code for 44ADA selected but 44ADA scheme not active. Verify.", "profession_code"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 44AE Firm Partner Salary/Interest (CBDT Sl 97)
    # ═══════════════════════════════════════════════════════════════════════════

    if inp.goods_carriage_44ae \
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
        if not _is_cg_sg_employee(inp.nature_of_employment) and sal.gratuity_received > Decimal("2000000"):
            results.append(_make("ITR4-R073-2", False,
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
                         + sd.preventive_checkup_self + sd.preventive_checkup_parents
                         + sd.medical_expense_self_senior
                         + sd.medical_expense_parents_senior)
        if ch6a:
            d80_total = (
                ch6a.amount_80d_self_family
                + ch6a.amount_80d_parents
                + ch6a.amount_80d_preventive_self
                + ch6a.amount_80d_preventive_parents
            )
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
            results.append(_make("ITR4-R110-2", False,
                f"Schedule IT col 4 total (Rs {inp.schedule_it_total_paid}) ≠ sum of rows "
                f"(Rs {it_sum})", "schedule_it_total_paid"))
    # Sl 111: TCS claimed ≤ TCS collected per entry
    for i, e in enumerate(inp.tcs_entries or []):
        if e.tcs_credit_claimed and e.tcs_credit_claimed > e.tcs_collected:
            results.append(_make("ITR4-R111-2", False,
                f"TCS entry {i+1}: claimed (Rs {e.tcs_credit_claimed}) > collected "
                f"(Rs {e.tcs_collected})", f"tcs_entries[{i}].tcs_credit_claimed"))
    # Sl 112: TCS col 5 total = sum individual col 5
    if inp.schedule_tcs_total_claimed and inp.schedule_tcs_total_claimed > z:
        tcs_claimed_sum = sum((e.tcs_credit_claimed or z) for e in (inp.tcs_entries or []))
        if abs(inp.schedule_tcs_total_claimed - tcs_claimed_sum) > Decimal("1"):
            results.append(_make("ITR4-R112-2", False,
                f"TCS col 5 total (Rs {inp.schedule_tcs_total_claimed}) ≠ sum (Rs {tcs_claimed_sum})",
                "schedule_tcs_total_claimed"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: Total TDS/TCS = Sum of Schedules (CBDT Sl 131-132)
    # ═══════════════════════════════════════════════════════════════════════════

    # Sl 131: Total TDS claimed = sum TDS1+TDS2+TDS3
    if inp.total_tds_claimed and inp.total_tds_claimed > z:
        from_tds_schedules = tds1_s + tds2_s + tds3_s
        if abs(inp.total_tds_claimed - from_tds_schedules) > Decimal("1"):
            results.append(_make("ITR4-R131-2", False,
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
        # ``total_eligible_amount`` is the post-percentage/post-limit claim,
        # not the gross sum of category tables A-D. The dedicated 80G
        # calculator and builder cross-foot that eligible total.

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
        if not _is_cg_sg_employee(inp.nature_of_employment):
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
                results.append(_make("ITR4-R109-2", False,
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
            (getattr(e, 'tds_claimed', None) or z)
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
            results.append(_make("ITR4-R133-2", False,
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
        (inp.business_income_44ad and inp.business_income_44ad.total_turnover > z)
        or (inp.professional_income_44ada
            and inp.professional_income_44ada.gross_receipts > z)
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
        if (
            _is_cg_sg_employee(inp.nature_of_employment)
            or _is_pensioner(inp.nature_of_employment)
        ):
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
            results.append(_make("ITR4-R241-2", False,
                f"80GGC VIA (Rs {getattr(ch6a, 'amount_80ggc', z)}) exceeds eligible "
                f"non-cash contributions (Rs {eligible_total})",
                "deductions_chapter6a.amount_80ggc"))

    # R243: Total Donation = sum of contributions
    if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > z:
        sggc = inp.schedule_80ggc
        if sggc.contributions:
            contrib_total = sum(c.amount for c in sggc.contributions)
            if abs(sggc.total_claimed - contrib_total) > Decimal("1"):
                results.append(_make("ITR4-R243-2", False,
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
                    results.append(_make("ITR4-R256-2", False,
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
            results.append(_make("ITR4-R248-2", False,
                f"80DD VIA (Rs {ch6a.amount_80dd}) ≠ Schedule 80DD "
                f"(Rs {inp.schedule_80dd.deduction_amount})",
                "deductions_chapter6a.amount_80dd"))
    if ch6a and ch6a.amount_80u > z and inp.schedule_80u:
        if ch6a.amount_80u != inp.schedule_80u.deduction_amount:
            results.append(_make("ITR4-R249-2", False,
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
            results.append(_make("ITR4-R266-2", False,
                f"LTCG 112A (Rs {cg.ltcg_112a}) ≠ FV (Rs {inp.full_value_of_consideration}) "
                f"- COA (Rs {cg.cost_of_acquisition}) = Rs {expected_ltcg}",
                "capital_gains.ltcg_112a"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-SECTION: 80EE/80EEA/80EEB Loan Validations (CBDT Sl 270-281, 301)
    # ═══════════════════════════════════════════════════════════════════════════

    # R270: 80EE/80EEA must exhaust 24(b) first
    if ch6a and (ch6a.amount_80ee > z or ch6a.amount_80eea > z):
        required_24b = (
            Decimal("200000")
            if hp and hp.property_type == PropertyType.SELF_OCCUPIED
            else (hp.home_loan_interest_paid if hp else z)
        )
        if not hp or hp.home_loan_interest_paid <= z \
                or hp.home_loan_interest_paid < required_24b:
            results.append(_make(
                "ITR4-R270", False,
                "80EE/80EEA claimed before exhausting the applicable "
                f"Section 24(b) limit of Rs {required_24b}.",
                "deductions_chapter6a",
                expected=f"24(b) interest >= {required_24b}",
                actual=str(hp.home_loan_interest_paid if hp else z)))
    # R271-R272: 80EE/80EEA loan ⊆ 24(b) loan list
    for section, deduction_rows, rule in (
        (
            "80EE",
            inp.loan_details_80ee_list
            or ([inp.loan_details_80ee] if inp.loan_details_80ee else []),
            "ITR4-R271",
        ),
        (
            "80EEA",
            inp.loan_details_80eea_list
            or ([inp.loan_details_80eea] if inp.loan_details_80eea else []),
            "ITR4-R272",
        ),
    ):
        for row in deduction_rows:
            lender_name = getattr(row, "lender_name", "")
            account_number = getattr(row, "account_or_reference_number", None)
            found = any(
                loan.lender_name == lender_name
                and (
                    account_number is None
                    or loan.account_or_reference_number == account_number
                )
                for loan in inp.loan_details_24b_list
            )
            if inp.loan_details_24b_list and not found:
                results.append(_make(
                    rule, False,
                    f"{section} loan not found in Schedule 24(b) loan list",
                    f"loan_details_{section.lower()}_list"))

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

    # R289: 24(b) total = schedule 24(b) total.
    # ITR-4 computes income for only the first house property row
    # (house_property_income has no property list, unlike ITR-1's
    # up-to-two), but loan_details_24b_list can carry loans tagged with a
    # different property_sequence_no if a draft somehow carries a second
    # property row (nothing in this pipeline rejects that outright -- see
    # Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §3.1/§3.2).
    # Comparing the one property actually being validated against an
    # unfiltered sum across every property's loans is the same false-positive
    # pattern already fixed for ITR1-R246 -- filter to sequence_no 1 here.
    total_24b = Decimal("0")
    if inp.loan_details_24b_list and hp and hp.home_loan_interest_paid > z:
        own_property_loans = [
            ld for ld in inp.loan_details_24b_list if ld.property_sequence_no == 1
        ]
        total_24b = sum(
            ld.interest_paid_self_occupied + ld.interest_paid_let_out
            for ld in own_property_loans
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

    # R296: 80C per-schedule row sum = total of payments.
    # (R295 was a duplicate of R289 immediately above -- both compared the
    # same 24(b) row-sum-vs-declared-total relationship under different rule
    # IDs, one of them tautologically comparing a value to itself once R289
    # was fixed to filter by property_sequence_no. Consolidated onto the
    # genuine second R295 implementation below, which is now also fixed to
    # filter correctly -- see
    # Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §3.2.)
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
        if _is_cg_sg_employee(inp.nature_of_employment):
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
        if not _is_cg_sg_employee(inp.nature_of_employment):
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

    # Typed property profile is authoritative for the current ITR-4 path.
    profile = inp.property_profile
    if profile and hp:
        if hp.ownership_share_percentage != profile.assessee_share_percentage:
            results.append(_make(
                "ITR4-R346-2", False,
                f"Calculation ownership share ({hp.ownership_share_percentage}%) "
                f"does not match the filing profile "
                f"({profile.assessee_share_percentage}%).",
                "property_profile.assessee_share_percentage",
            ))
        if inp.assessee_pan and any(
            row.pan == inp.assessee_pan for row in profile.co_owners
        ):
            results.append(_make(
                "ITR4-R351-2", False,
                "Co-owner PAN cannot equal the assessee PAN.",
                "property_profile.co_owners",
            ))
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
                "80CCC claimed but no per-row details provided. Identifier type "
                "and name required.", "deductions_chapter6a.amount_80ccc"))
        else:
            for i, e in enumerate(inp.schedule_80ccc_entries):
                if e.amount > z and (not e.identifier_type or not e.identifier_name):
                    results.append(_make("ITR4-R409b", False,
                        f"80CCC row {i+1}: amount Rs {e.amount} but identifier details missing",
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
        results.append(_make("ITR4-R410-2", False,
            "Representative filing: secondary address is mandatory",
            "secondary_address"))

    # R411: Secondary ≠ primary address (informational)
    results.append(_info("ITR4-R411-2",
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
                results.append(_make("ITR4-R003-2", False,
                    f"BP E17: Total capital & liabilities (Rs {bpf.total_capital_liabilities}) "
                    f"≠ sum of components (Rs {liab_sum})",
                    "schedule_bp_financial.total_capital_liabilities",
                    expected=str(liab_sum), actual=str(bpf.total_capital_liabilities)))
        # Sl 4: E25 Total Assets = components
        if bpf.total_assets > z:
            assets_sum = (bpf.fixed_assets + bpf.investments_bp + bpf.inventories
                          + bpf.sundry_debtors + bpf.bank_balance + bpf.cash_in_hand
                          + bpf.loans_and_advances_given + bpf.other_assets)
            if abs(bpf.total_assets - assets_sum) > Decimal("1"):
                results.append(_make("ITR4-R004-2", False,
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
        results.append(_make("ITR4-R167-2", False,
            "Original return filed u/s 142(1) (notice). Revised return u/s 139(5) "
            "not allowed for 142(1) proceedings.", "filing_section"))

    # Sl 188: 148 proceeding → original 139 return cannot be revised
    if inp.is_148_proceeding \
            and inp.filing_section and inp.filing_section == "139(5)":
        results.append(_make("ITR4-R188-2", False,
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
    # SECTION: Missing CBDT Category A Rules (123 rules)
    # These rules were identified as missing in CBDT_COMPLIANCE_AUDIT.md
    # and are now implemented below.
    # ========================================================================

    # ── Group A: Exempt-income dropdown uniqueness (Rules 83-94, 222) ──────
    # Each exempt-income section dropdown cannot be selected more than once.
    _EXEMPT_DROPDOWN_SECTIONS = [
        ("10(10D)", "R083", "sec_10_10d_life_insurance"),
        ("10(11)", "R084", "sec_10_11_statutory_pf"),
        ("10(12)", "R085", "sec_10_12_recognized_pf"),
        ("10(13)", "R086", "sec_10_13_approved_superannuation"),
        ("10(16)", "R087", "sec_10_16_scholarship"),
        ("10(17)", "R088", "sec_10_17_mp_mla"),
        ("10(17A)", "R089", "sec_10_17a_award"),
        ("10(18)", "R090", "sec_10_18_param_vir_chakra"),
        ("10(19)", "R091", "sec_10_19_armed_forces_family"),
        ("10(26)", "R092", "sec_10_26_income"),
        ("10(26AAA)", "R093", "sec_10_26aaa_income"),
        ("Defense Medical Disability Pension", "R094_1", "sec_defense_medical_disability"),
        ("Minor child's income—small exemption", "R094_2", "sec_10_32_minor_child"),
    ]
    for _label, _rid, _key in _EXEMPT_DROPDOWN_SECTIONS:
        _count = inp.exempt_income_dropdowns.count(_label)
        if _count > 1:
            results.append(_make(
                f"ITR4-{_rid}", False,
                f"Exempt income dropdown '{_label}' selected {_count} times. "
                f"Each exempt income category can be selected at most once.",
                f"exempt_income_dropdowns",
                expected="<= 1 occurrence", actual=f"{_count} occurrences"))

    # ── Group A continued: Rules 367-390 (additional exempt income uniqueness) ──
    _EXEMPT_DROPDOWN_SECTIONS_EXT = [
        ("10(2)", "R367", "sec_10_2_member_huf_share"),
        ("10(10BB)", "R368", "sec_10_10bb_bhopal_gas"),
        ("10(11A)", "R369", "sec_10_11a_sukanya"),
        ("10(12A)", "R370", "sec_10_12a_nps_partial"),
        ("10(12AA)", "R371", "sec_10_12aa_nps_payment"),
        ("10(12AB)", "R372", "sec_10_12ab_lumpsum"),
        ("10(12B)", "R373", "sec_10_12b_nps_lumpsum"),
        ("10(12BA)", "R374", "sec_10_12ba_nps_partial"),
        ("10(12C)", "R375", "sec_10_12c_agniveer"),
        ("10(15)", "R376", "sec_10_15_securities"),
        ("10(19A)", "R377", "sec_10_19a_palace"),
        ("10(23AA)", "R378", "sec_10_23aa_armed_force"),
        ("Contributions from recognized stock exchange", "R379", "sec_stock_exchange"),
        ("10(23FBB)", "R380", "sec_10_23fbb_investment_fund"),
        ("10(23FD)", "R381", "sec_10_23fd_business_trust"),
        ("10(25)", "R382", "sec_10_25_superannuation"),
        ("10(25A)", "R383", "sec_10_25a_esi"),
        ("10(30)", "R384", "sec_10_30_tea_board"),
        ("10(31)", "R385", "sec_10_31_rubber_coffee_tea"),
        ("Minor child's income—small exemption", "R386", "sec_10_32_minor_child_ext"),
        ("10(35)", "R387_1", "sec_10_35_mutual_funds"),
        ("10(35A)", "R388_1", "sec_10_35a_securitization"),
        ("10(43)", "R389_1", "sec_10_43_reverse_mortgage"),
        ("10(44)", "R390", "sec_10_44_nps_trusts"),
    ]
    for _label, _rid, _key in _EXEMPT_DROPDOWN_SECTIONS_EXT:
        _count = inp.exempt_income_dropdowns.count(_label)
        if _count > 1:
            results.append(_make(
                f"ITR4-{_rid}", False,
                f"Exempt income dropdown '{_label}' selected {_count} times. "
                f"Each exempt income category can be selected at most once.",
                f"exempt_income_dropdowns",
                expected="<= 1 occurrence", actual=f"{_count} occurrences"))

    # R222: Any drop-down of nature of income cannot be selected more than once
    _seen_natures = set()
    for _dropdown in inp.exempt_income_dropdowns:
        if _dropdown in _seen_natures:
            results.append(_make(
                "ITR4-R222", False,
                f"Exempt income nature '{_dropdown}' selected multiple times. "
                f"Any nature of income dropdown cannot be selected more than once.",
                "exempt_income_dropdowns",
                expected="unique entries", actual=f"duplicate '{_dropdown}'"))
            break
        _seen_natures.add(_dropdown)

    # ── Group B: 10(13A) HRA detailed computation (Rules 312, 313, 316) ─────
    if sal and sal.hra_exempt_amount > z:
        _hra = inp.hra_details or inp.schedule_10_13a
        if _hra:
            # HRADetails has: actual_hra_received, rent_paid, salary_for_hra, dearness_allowance, is_metro_city
            _basic_da = (getattr(_hra, 'salary_for_hra', z) or z) + (getattr(_hra, 'dearness_allowance', z) or z)
            # R312: HRA ≤ 50% of basic salary + DA
            if _basic_da > z and sal.hra_exempt_amount > _basic_da * Decimal("0.5"):
                results.append(_make(
                    "ITR4-R312", False,
                    f"HRA exemption (Rs {sal.hra_exempt_amount}) exceeds 50% of "
                    f"basic salary + DA (Rs {_basic_da}). Maximum allowed: "
                    f"Rs {_basic_da * Decimal('0.5')}.",
                    "salary_income.hra_exempt_amount",
                    expected=f"<= {_basic_da * Decimal('0.5')}",
                    actual=str(sal.hra_exempt_amount)))
            # R313: HRA ≤ actual rent paid − 10% of basic salary + DA
            _actual_rent = getattr(_hra, 'rent_paid', z) or z
            if _actual_rent > z and _basic_da > z:
                _max_hra = _actual_rent - (_basic_da * Decimal("0.1"))
                if sal.hra_exempt_amount > _max_hra:
                    results.append(_make(
                        "ITR4-R313", False,
                        f"HRA exemption (Rs {sal.hra_exempt_amount}) exceeds "
                        f"actual rent (Rs {_actual_rent}) − 10% of salary+DA "
                        f"(Rs {_basic_da * Decimal('0.1')}) = Rs {_max_hra}.",
                        "salary_income.hra_exempt_amount",
                        expected=f"<= {_max_hra}",
                        actual=str(sal.hra_exempt_amount)))
        # R316: Sum of basic+DA+actual HRA received ≤ salary u/s 17(1)
        if _hra:
            _basic = (getattr(_hra, 'salary_for_hra', z) or z) + (getattr(_hra, 'dearness_allowance', z) or z)
            _actual_hra = getattr(_hra, 'actual_hra_received', z) or z
            if _basic > z and _actual_hra > z:
                _sum = _basic + _actual_hra
                if _sum > sal.gross_salary:
                    results.append(_make(
                        "ITR4-R316-2", False,
                        f"Sum of basic+DA (Rs {_basic}) + actual HRA received "
                        f"(Rs {_actual_hra}) = Rs {_sum} exceeds gross salary "
                        f"u/s 17(1) (Rs {sal.gross_salary}).",
                        "salary_income.hra_exempt_amount",
                        expected=f"<= {sal.gross_salary}",
                        actual=str(_sum)))
        # R315: Schedule 10(13A) mandatory if HRA exemption claimed
        if not _hra:
            results.append(_make(
                "ITR4-R315-2", False,
                "HRA exemption u/s 10(13A) claimed but Schedule 10(13A) "
                "details not provided. Schedule 10(13A) is mandatory for "
                "HRA exemption claim.",
                "schedule_10_13a",
                expected="Schedule 10(13A) details",
                actual="None"))

    # ── Group C: Gratuity / perquisite caps (Rules 76, 159) ─────────────────
    # R73/R317 (gratuity 20L/25L caps) and R181 (leave encashment 25L cap)
    # were each duplicated here under hardcoded employment-code whitelists
    # using WRONG strings ("CG"/"SG"/"CGP"/"SGP"/"PES" instead of the real
    # raw codes "CGOV"/"SGOV"/"PESG") -- both dormant for the false-positive
    # direction and redundant with the already-correct R073/R317/R075
    # implementations elsewhere in this file (which use _is_cg_sg_employee).
    # Removed rather than fixed in place, since a correct implementation of
    # each already exists. See
    # Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
    if sal:
        # R76: 10(10C) VRS ≤ ₹5,00,000
        if sal.vrs_compensation > Decimal("500000"):
            results.append(_make(
                "ITR4-R076", False,
                f"VRS compensation (Rs {sal.vrs_compensation}) exceeds "
                f"₹5,00,000 limit u/s 10(10C).",
                "salary_income.vrs_compensation",
                expected="<= 500000",
                actual=str(sal.vrs_compensation)))
        # R159: 10(10B) retrenchment ≤ ₹5,00,000 (first proviso)
        if sal.retrenchment_compensation > Decimal("500000"):
            results.append(_make(
                "ITR4-R159-2", False,
                f"Retrenchment compensation (Rs {sal.retrenchment_compensation}) "
                f"exceeds ₹5,00,000 limit u/s 10(10B) first proviso.",
                "salary_income.retrenchment_compensation",
                expected="<= 500000",
                actual=str(sal.retrenchment_compensation)))

    # ── Group D: 80CCD(2) employer-category logic (Rule 263) ────────────────
    # R161 (80CCD(2) not for pensioners) was duplicated here with a
    # hardcoded whitelist missing the base "PE" pensioner code entirely and
    # containing a typo ("PES" instead of "PESG") -- redundant with the
    # already-correct R161 implementation above (which uses
    # _is_pensioner()). Removed rather than fixed in place. See
    # Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
    # R263: New regime 80CCD(2) ≤ 14% of salary for PSU/CG/SG/Others
    if is_new and ch6a and ch6a.amount_80ccd2 > z and sal:
        _emp_cat = inp.nature_of_employment or ""
        if _emp_cat in ("PSU", "OTH", "CGOV", "SGOV"):
            _max_80ccd2 = sal.gross_salary * Decimal("0.14")
            if ch6a.amount_80ccd2 > _max_80ccd2:
                results.append(_make(
                    "ITR4-R263-2", False,
                    f"New regime 80CCD(2) (Rs {ch6a.amount_80ccd2}) exceeds 14% "
                    f"of salary (Rs {sal.gross_salary}) = Rs {_max_80ccd2} "
                    f"for employer category '{_emp_cat}'.",
                    "deductions_chapter6a.amount_80ccd2",
                    expected=f"<= {_max_80ccd2}",
                    actual=str(ch6a.amount_80ccd2)))

    # ── Group F: 10IEA conditional-mandatory chain (Rules 353-364, 393) ────
    _a23_earlier = inp.has_filed_10iea_earlier
    _a23_reenter = inp.has_reentered_new_regime
    _a23_current = inp.has_filed_10iea_current
    # R353: If A23(A) "Yes" (filed 10IEA earlier), then A(i) and A(ii) mandatory
    if _a23_earlier is True:
        if inp.a23_earlier_ay is None:
            results.append(_make(
                "ITR4-R353", False,
                "A23(A) is 'Yes' (filed Form 10IEA in earlier AY) but "
                "A23(A)(i) assessment year is not provided. Mandatory.",
                "a23_earlier_ay",
                expected="assessment year",
                actual="None"))
        if _a23_reenter is None:
            results.append(_make(
                "ITR4-R353b-2", False,
                "A23(A) is 'Yes' but A23(A)(ii) response is not provided. "
                "Mandatory when A23(A) is 'Yes'.",
                "has_reentered_new_regime",
                expected="Y or N",
                actual="None"))
    # R354: If A23(A) is "No", then A23(B) mandatory
    if _a23_earlier is False:
        if _a23_current is None:
            results.append(_make(
                "ITR4-R354-2", False,
                "A23(A) is 'No' but A23(B) response is not provided. "
                "Mandatory when A23(A) is 'No'.",
                "has_filed_10iea_current",
                expected="Y or N",
                actual="None"))
    # R355: If A23(A)(ii) is "Yes", then A23(A)(ii)(a) mandatory
    if _a23_reenter is True:
        if inp.a23_reenter_ay is None:
            results.append(_make(
                "ITR4-R355-2", False,
                "A23(A)(ii) is 'Yes' (re-entered new regime) but "
                "A23(A)(ii)(a) assessment year not provided. Mandatory.",
                "a23_reenter_ay",
                expected="assessment year",
                actual="None"))
    # R356: If A23(A)(ii) is "No", then A23(A)(ii)(b) mandatory
    if _a23_reenter is False:
        if not inp.form_10iea_filed and not inp.form_10iea_ack_no:
            results.append(_make(
                "ITR4-R356", False,
                "A23(A)(ii) is 'No' but A23(A)(ii)(b) response not provided. "
                "Mandatory when A23(A)(ii) is 'No'.",
                "form_10iea_filed",
                expected="Y or N",
                actual="missing"))
    # R357: If A23(A)(ii)(b) is "Yes", then A23(A)(ii)(b)(i) mandatory
    # A23(A)(ii)(b) = "Have you furnished form 10IEA for re-entering in new regime in current AY?"
    # On ITR4Input, has_reentered_new_regime=True means A23(A)(ii)="Yes" (re-entered).
    # A23(A)(ii)(b) is a sub-question — if re-entered, filing details mandatory.
    if _a23_reenter is True and not inp.form_10iea_filed:
        results.append(_make(
            "ITR4-R357", False,
            "A23(A)(ii) is 'Yes' (re-entered new regime) but Form 10IEA "
            "details not provided. A23(A)(ii)(b)(i) is mandatory.",
            "form_10iea_ack_no",
            expected="filing date + ack no",
            actual="missing"))
    # R358: If A23(A)(ii)(b) is "No", then A23(A)(ii)(b)(i) not applicable
    # (informational — no error, just skip)
    # R359: If A23(B) is "Yes", then A23(B)(i) mandatory
    if _a23_current is True:
        if not inp.form_10iea_filed and not inp.form_10iea_ack_no:
            results.append(_make(
                "ITR4-R359-2", False,
                "A23(B) is 'Yes' (filed 10IEA for current AY) but "
                "A23(B)(i) Form 10IEA details not provided. Mandatory.",
                "form_10iea_ack_no",
                expected="filing date + ack no",
                actual="missing"))
    # R360: If A23(B) is "No", then A23(B)(i) not applicable (skip)
    # R361: If Form 10IEA details filled in A23(B)(i), then A23(B) cannot be blank
    if inp.form_10iea_ack_no and _a23_current is None:
        results.append(_make(
            "ITR4-R361", False,
            "Form 10IEA acknowledgement provided but A23(B) response is blank.",
            "has_filed_10iea_current",
            expected="Y or N",
            actual="None"))
    # R362: If Form 10IEA details in A23(A)(ii)(b)(i), then A23(A)(ii)(b) not blank
    if inp.form_10iea_ack_no and _a23_reenter is False:
        results.append(_make(
            "ITR4-R362", False,
            "Form 10IEA acknowledgement number provided but A23(A)(ii) is 'No'. "
            "Cannot have 10IEA details without re-entering new regime.",
            "has_reentered_new_regime",
            expected="Y",
            actual="N"))
    # R363: If details in A23(A)(ii)(a) or (ii)(b), then A23(A)(ii) not blank
    if (inp.a23_reenter_ay or inp.form_10iea_ack_no) and _a23_reenter is None:
        results.append(_make(
            "ITR4-R363", False,
            "Details filled in A23(A)(ii) sub-fields but A23(A)(ii) is blank.",
            "has_reentered_new_regime",
            expected="Y or N",
            actual="None"))
    # R364: If details in A23(A)(i) or (ii), then A23(A) not blank
    if (inp.a23_earlier_ay or _a23_reenter is not None) and _a23_earlier is None:
        results.append(_make(
            "ITR4-R364", False,
            "Details filled in A23(A) sub-fields but A23(A) is blank.",
            "has_filed_10iea_earlier",
            expected="Y or N",
            actual="None"))
    # R393: AY in A23(A)(ii)(a) shall not be same or prior to AY in A23(A)(i)
    if inp.a23_earlier_ay and inp.a23_reenter_ay:
        if inp.a23_reenter_ay <= inp.a23_earlier_ay:
            results.append(_make(
                "ITR4-R393-2", False,
                f"A23(A)(ii)(a) AY ({inp.a23_reenter_ay}) is same or prior to "
                f"A23(A)(i) AY ({inp.a23_earlier_ay}). Must be a later AY.",
                "a23_reenter_ay",
                expected=f"> {inp.a23_earlier_ay}",
                actual=str(inp.a23_reenter_ay)))

    # ── Group G: Donation schedule detail rules (Rules 395, 398, 399, 409) ──
    # R395: PAN of donee mandatory if donation > 0 in Schedule 80G
    if inp.schedule_80g:
        for _i, _don in enumerate(getattr(inp.schedule_80g, 'donations', []) or []):
            _amt = getattr(_don, 'amount', z) or z
            _pan = getattr(_don, 'donee_pan', '') or ''
            if _amt > z and not _pan:
                results.append(_make(
                    "ITR4-R395-2", False,
                    f"Schedule 80G donation row {_i+1}: amount Rs {_amt} > 0 "
                    f"but donee PAN not provided. Mandatory.",
                    f"schedule_80g.donations[{_i}].donee_pan",
                    expected="PAN",
                    actual="missing"))
    # R398: Name and PAN of political party mandatory for 80GGC
    if inp.schedule_80ggc:
        for _i, _row in enumerate(getattr(inp.schedule_80ggc, 'contributions', []) or []):
            _amt = getattr(_row, 'amount', z) or z
            _name = getattr(_row, 'political_party_name', '') or ''
            _pan = getattr(_row, 'political_party_pan', '') or ''
            if _amt > z:
                if not _name:
                    results.append(_make(
                        "ITR4-R398-2", False,
                        f"Schedule 80GGC row {_i+1}: amount > 0 but political "
                        f"party name not provided. Mandatory.",
                        f"schedule_80ggc.contributions[{_i}].political_party_name",
                        expected="party name",
                        actual="missing"))
                if not _pan:
                    results.append(_make(
                        "ITR4-R398b", False,
                        f"Schedule 80GGC row {_i+1}: amount > 0 but political "
                        f"party PAN not provided. Mandatory.",
                        f"schedule_80ggc.contributions[{_i}].political_party_pan",
                        expected="PAN",
                        actual="missing"))
    # R399: In Schedule 80G, either cash OR other mode, not both, per row
    if inp.schedule_80g:
        for _i, _don in enumerate(getattr(inp.schedule_80g, 'donations', []) or []):
            _cash = getattr(_don, 'cash_amount', z) or z
            _other = getattr(_don, 'non_cash_amount', z) or z
            if _cash > z and _other > z:
                results.append(_make(
                    "ITR4-R399-2", False,
                    f"Schedule 80G donation row {_i+1}: both cash (Rs {_cash}) "
                    f"and other mode (Rs {_other}) entered. Only one mode "
                    f"per row allowed.",
                    f"schedule_80g.donations[{_i}]",
                    expected="cash OR other mode",
                    actual=f"cash={_cash}, other={_other}"))
    # R409: PRAN mandatory for 80CCD(1) or 80CCD(1B) claim
    if ch6a and (ch6a.amount_80ccd1 > z or ch6a.amount_80ccd1b > z):
        if not inp.pran_number:
            results.append(_make(
                "ITR4-R409-2", False,
                "80CCD(1) or 80CCD(1B) claimed but PRAN number not provided. "
                "PRAN is mandatory for NPS contributions.",
                "pran_number",
                expected="PRAN",
                actual="None"))

    # ── Group H: New-regime per-section zero checks (Rules 189-211) ─────────
    # These are subsumed by R185 but implemented individually per CBDT spec.
    if is_new and ch6a:
        _new_regime_zero_checks = [
            (ch6a.amount_80c, "80C", "R189"),
            (ch6a.amount_80ccd1, "80CCD(1)", "R208"),
            (ch6a.amount_80ccd1b, "80CCD(1B)", "R203"),
            (ch6a.amount_80dd, "80DD", "R204"),
            (ch6a.amount_80ddb, "80DDB", "R205"),
            (ch6a.amount_80ee, "80EE", "R206"),
            (ch6a.amount_80eea, "80EEA", "R209"),
            (ch6a.amount_80eeb, "80EEB", "R210"),
            (ch6a.amount_80tta, "80TTA", "R192"),
            (ch6a.amount_80ttb, "80TTB", "R193"),
            (ch6a.amount_80u, "80U", "R194"),
        ]
        for _amt, _sec, _rid in _new_regime_zero_checks:
            if _amt > z:
                results.append(_make(
                    f"ITR4-{_rid}", False,
                    f"New regime: deduction u/s {_sec} (Rs {_amt}) must be zero. "
                    f"Only 80CCD(2) and 80CCH allowed under new regime.",
                    f"deductions_chapter6a.amount_{_sec.lower().replace('(','').replace(')','')}",
                    expected="0",
                    actual=str(_amt)))
        # R190: 80G cannot be claimed under new regime
        if inp.schedule_80g is not None:
            results.append(_make(
                "ITR4-R190", False,
                "New regime: 80G deduction cannot be claimed. Schedule 80G "
                "should not be provided.",
                "schedule_80g",
                expected="None",
                actual="provided"))
        # R191: 80GG cannot be claimed under new regime
        if ch6a.amount_80gg > z:
            results.append(_make(
                "ITR4-R191", False,
                f"New regime: 80GG (Rs {ch6a.amount_80gg}) must be zero.",
                "deductions_chapter6a.amount_80gg",
                expected="0",
                actual=str(ch6a.amount_80gg)))
        # R195: Professional tax u/s 16(iii) must be zero under new regime
        if sal and sal.professional_tax_paid > z:
            results.append(_make(
                "ITR4-R195-2", False,
                f"New regime: Professional tax u/s 16(iii) (Rs {sal.professional_tax_paid}) "
                f"must be zero.",
                "salary_income.professional_tax_paid",
                expected="0",
                actual=str(sal.professional_tax_paid)))
        # R198-202: Exempt allowances under new regime
        if sal:
            if sal.lta_exempt_amount > z:
                results.append(_make(
                    "ITR4-R198-2", False,
                    f"New regime: 10(5) LTA (Rs {sal.lta_exempt_amount}) must be zero.",
                    "salary_income.lta_exempt_amount",
                    expected="0",
                    actual=str(sal.lta_exempt_amount)))
            if sal.hra_exempt_amount > z:
                results.append(_make(
                    "ITR4-R199-2", False,
                    f"New regime: 10(13A) HRA (Rs {sal.hra_exempt_amount}) must be zero.",
                    "salary_income.hra_exempt_amount",
                    expected="0",
                    actual=str(sal.hra_exempt_amount)))
            if sal.sec10_14i_prescribed_allowance > z:
                results.append(_make(
                    "ITR4-R200-2", False,
                    f"New regime: 10(14)(i) (Rs {sal.sec10_14i_prescribed_allowance}) must be zero.",
                    "salary_income.sec10_14i_prescribed_allowance",
                    expected="0",
                    actual=str(sal.sec10_14i_prescribed_allowance)))
            if sal.sec10_14ii_personal_allowance > z:
                results.append(_make(
                    "ITR4-R201-2", False,
                    f"New regime: 10(14)(ii) (Rs {sal.sec10_14ii_personal_allowance}) must be zero.",
                    "salary_income.sec10_14ii_personal_allowance",
                    expected="0",
                    actual=str(sal.sec10_14ii_personal_allowance)))
        # R211: 80D cannot be claimed under new regime
        if inp.schedule_80d is not None:
            results.append(_make(
                "ITR4-R211", False,
                "New regime: 80D deduction cannot be claimed. Schedule 80D "
                "should not be provided.",
                "schedule_80d",
                expected="None",
                actual="provided"))

    # ── Group I: Salary detailed breakdown (Rules 65-66, 69-72, 78-82) ─────
    if sal and is_old:
        # R65: Deductions u/s 16 = std_ded + ent_allow + prof_tax
        _exp_16 = sal.standard_deduction_claimed + sal.entertainment_allowance + sal.professional_tax_paid
        # R66: Income chargeable u/s Salaries = net_salary − deductions u/s 16
        # (verified post-computation in calc_rules.py R063)
        # R67: Entertainment allowance ≤ ₹5,000 or 1/5th basic, whichever lower (CG/SG/PSU only)
        _emp_cat = inp.nature_of_employment or ""
        if _emp_cat in ("CGOV", "SGOV", "PSU") and sal.entertainment_allowance > z:
            # Need basic salary — approximate from gross_salary if no breakdown
            _basic = getattr(sal, 'basic_salary', sal.gross_salary) or sal.gross_salary
            _max_ent = min(Decimal("5000"), _basic * Decimal("0.2"))
            if sal.entertainment_allowance > _max_ent:
                results.append(_make(
                    "ITR4-R067-2", False,
                    f"Entertainment allowance (Rs {sal.entertainment_allowance}) "
                    f"exceeds ₹5,000 or 1/5th of basic (Rs {_basic * Decimal('0.2')}), "
                    f"whichever lower = Rs {_max_ent}. Only CG/SG/PSU eligible.",
                    "salary_income.entertainment_allowance",
                    expected=f"<= {_max_ent}",
                    actual=str(sal.entertainment_allowance)))
        # R68: No entertainment allowance for non-CG/SG/PSU employees
        if _emp_cat not in ("CGOV", "SGOV", "PSU") and sal.entertainment_allowance > z:
            results.append(_make(
                "ITR4-R068-2", False,
                f"Entertainment allowance (Rs {sal.entertainment_allowance}) "
                f"not allowed for employer category '{_emp_cat}'. "
                f"Only CG/SG/PSU employees eligible.",
                "salary_income.entertainment_allowance",
                expected="0",
                actual=str(sal.entertainment_allowance)))
        # R69: Total exempt allowances u/s 10 ≤ sum of salary components
        _total_exempt = (sal.hra_exempt_amount + sal.lta_exempt_amount
                         + sal.sec10_6_embassy_exempt + sal.sec10_7_foreign_allowance
                         + sal.sec10_14i_prescribed_allowance + sal.sec10_14ii_personal_allowance)
        _sal_components = sal.gross_salary
        if _total_exempt > _sal_components:
            results.append(_make(
                "ITR4-R069-2", False,
                f"Total exempt allowances u/s 10 (Rs {_total_exempt}) exceeds "
                f"sum of salary components (Rs {_sal_components}).",
                "salary_income",
                expected=f"<= {_sal_components}",
                actual=str(_total_exempt)))
        # R70: 10(5) LTA ≤ salary u/s 17(1)
        if sal.lta_exempt_amount > sal.gross_salary:
            results.append(_make(
                "ITR4-R070-2", False,
                f"10(5) LTA exemption (Rs {sal.lta_exempt_amount}) exceeds "
                f"salary u/s 17(1) (Rs {sal.gross_salary}).",
                "salary_income.lta_exempt_amount",
                expected=f"<= {sal.gross_salary}",
                actual=str(sal.lta_exempt_amount)))
        # R71: 10(6) embassy remuneration ≤ gross salary
        if sal.sec10_6_embassy_exempt > sal.gross_salary:
            results.append(_make(
                "ITR4-R071-2", False,
                f"10(6) embassy remuneration exemption (Rs {sal.sec10_6_embassy_exempt}) "
                f"exceeds gross salary (Rs {sal.gross_salary}).",
                "salary_income.sec10_6_embassy_exempt",
                expected=f"<= {sal.gross_salary}",
                actual=str(sal.sec10_6_embassy_exempt)))
        # R72: 10(7) foreign service allowance ≤ gross salary
        if sal.sec10_7_foreign_allowance > sal.gross_salary:
            results.append(_make(
                "ITR4-R072-2", False,
                f"10(7) foreign service allowance (Rs {sal.sec10_7_foreign_allowance}) "
                f"exceeds gross salary (Rs {sal.gross_salary}).",
                "salary_income.sec10_7_foreign_allowance",
                expected=f"<= {sal.gross_salary}",
                actual=str(sal.sec10_7_foreign_allowance)))
        # R78: 10(10CC) ≤ perquisites value u/s 17(2)
        if sal.sec10_10cc_perquisite_tax > sal.perquisites_value:
            results.append(_make(
                "ITR4-R078", False,
                f"10(10CC) perquisite tax (Rs {sal.sec10_10cc_perquisite_tax}) "
                f"exceeds perquisites value u/s 17(2) (Rs {sal.perquisites_value}).",
                "salary_income.sec10_10cc_perquisite_tax",
                expected=f"<= {sal.perquisites_value}",
                actual=str(sal.sec10_10cc_perquisite_tax)))
        # R79: 10(13A) HRA ≤ 1/3rd or 50% of salary (old regime)
        if sal.hra_exempt_amount > z:
            _max_hra_50 = sal.gross_salary * Decimal("0.5")
            _max_hra_33 = sal.gross_salary * Decimal("0.3333")
            if sal.hra_exempt_amount > _max_hra_50:
                results.append(_make(
                    "ITR4-R079", False,
                    f"10(13A) HRA exemption (Rs {sal.hra_exempt_amount}) exceeds "
                    f"50% of salary (Rs {_max_hra_50}).",
                    "salary_income.hra_exempt_amount",
                    expected=f"<= {_max_hra_50}",
                    actual=str(sal.hra_exempt_amount)))
        # R80: 10(14)(i) ≤ salary u/s 17(1)
        if sal.sec10_14i_prescribed_allowance > sal.gross_salary:
            results.append(_make(
                "ITR4-R080-2", False,
                f"10(14)(i) prescribed allowance (Rs {sal.sec10_14i_prescribed_allowance}) "
                f"exceeds salary u/s 17(1) (Rs {sal.gross_salary}).",
                "salary_income.sec10_14i_prescribed_allowance",
                expected=f"<= {sal.gross_salary}",
                actual=str(sal.sec10_14i_prescribed_allowance)))
        # R81: 10(14)(ii) ≤ salary u/s 17(1)
        if sal.sec10_14ii_personal_allowance > sal.gross_salary:
            results.append(_make(
                "ITR4-R081-2", False,
                f"10(14)(ii) personal allowance (Rs {sal.sec10_14ii_personal_allowance}) "
                f"exceeds salary u/s 17(1) (Rs {sal.gross_salary}).",
                "salary_income.sec10_14ii_personal_allowance",
                expected=f"<= {sal.gross_salary}",
                actual=str(sal.sec10_14ii_personal_allowance)))
    # R186: 10(14)(ii) transport allowance for disabled ≤ ₹38,400
    if sal and sal.sec10_14ii_personal_allowance > Decimal("38400"):
        results.append(_make(
            "ITR4-R186", False,
            f"10(14)(ii) transport allowance for physically handicapped "
            f"(Rs {sal.sec10_14ii_personal_allowance}) exceeds ₹38,400 limit.",
            "salary_income.sec10_14ii_personal_allowance",
            expected="<= 38400",
            actual=str(sal.sec10_14ii_personal_allowance)))

    # ── Group J: Miscellaneous rules ───────────────────────────────────────
    # R33: 80EE cannot be claimed by HUF or Firm (other than LLP)
    if is_huf or is_firm:
        if ch6a and ch6a.amount_80ee > z:
            results.append(_make(
                "ITR4-R033", False,
                f"{'HUF' if is_huf else 'Firm'} cannot claim deduction u/s 80EE. "
                f"Only individuals eligible.",
                "deductions_chapter6a.amount_80ee",
                expected="0",
                actual=str(ch6a.amount_80ee)))
    # R50: HUF or Firm cannot claim rebate u/s 87A (informational — verified post-computation)
    if (is_huf or is_firm):
        results.append(_info("ITR4-R050",
            f"{'HUF' if is_huf else 'Firm'} assessee — rebate u/s 87A is not "
            f"applicable. Only resident individuals eligible.",
            "assessee_type"))
    # R123: IFSC must match RBI/GIFT database (informational — requires external DB)
    for _i, _bank in enumerate(inp.bank_accounts):
        if _bank.ifsc_code and len(_bank.ifsc_code) != 11:
            results.append(_make(
                "ITR4-R123", False,
                f"Bank account {_i+1}: IFSC code '{_bank.ifsc_code}' is not "
                f"11 characters. Must match RBI/GIFT IFSC database format.",
                f"bank_accounts[{_i}].ifsc_code",
                expected="11 chars (4 letters + 0 + 6 digits)",
                actual=_bank.ifsc_code))
        elif _bank.ifsc_code and not _bank.ifsc_code[:4].isalpha():
            results.append(_make(
                "ITR4-R123b", False,
                f"Bank account {_i+1}: IFSC '{_bank.ifsc_code}' first 4 chars "
                f"must be letters (bank code).",
                f"bank_accounts[{_i}].ifsc_code",
                expected="4 letters + 0 + 6 digits",
                actual=_bank.ifsc_code))
        elif _bank.ifsc_code and _bank.ifsc_code[4] != '0':
            results.append(_make(
                "ITR4-R123c", False,
                f"Bank account {_i+1}: IFSC '{_bank.ifsc_code}' 5th char "
                f"must be '0'.",
                f"bank_accounts[{_i}].ifsc_code",
                expected="5th char = '0'",
                actual=_bank.ifsc_code))
    # R127: TDS2 section code eligibility (expanded list)
    if inp.tds2_entries:
        for _i, _e in enumerate(inp.tds2_entries):
            _sec = getattr(_e, 'tds_section', '') or ''
            # Special-rate sections make ITR-4 ineligible
            _special_rate_secs = {"194B", "194BB", "194BA", "194IA", "194IC", "194LA", "194R", "194S"}
            _nr_secs = {"194E", "194LB", "194LC", "194LBA", "195", "196A", "196B", "196C", "196D"}
            if _sec in _special_rate_secs:
                results.append(_make(
                    "ITR4-R127", False,
                    f"TDS2 entry {_i+1}: Section {_sec} indicates special-rate "
                    f"income. Assessee with special-rate income is not eligible "
                    f"to file ITR-4. File ITR-3.",
                    f"tds2_entries[{_i}].tds_section",
                    expected="non-special-rate section",
                    actual=_sec))
            if _sec in _nr_secs:
                results.append(_make(
                    "ITR4-R127b", False,
                    f"TDS2 entry {_i+1}: Section {_sec} indicates non-resident "
                    f"payment. ITR-4 is for residents only. File ITR-3.",
                    f"tds2_entries[{_i}].tds_section",
                    expected="resident section",
                    actual=_sec))
    # R129: 80G donee PAN cannot be same as assessee PAN (except AAAAR1077P)
    if inp.schedule_80g and inp.assessee_pan:
        for _i, _don in enumerate(getattr(inp.schedule_80g, 'donations', []) or []):
            _pan = getattr(_don, 'donee_pan', '') or ''
            if _pan and _pan == inp.assessee_pan and _pan != "AAAAR1077P":
                results.append(_make(
                    "ITR4-R129", False,
                    f"Schedule 80G row {_i+1}: Donee PAN ({_pan}) is same as "
                    f"assessee PAN. Not allowed (except PM Relief Fund AAAAR1077P).",
                    f"schedule_80g.donations[{_i}].donee_pan",
                    expected=f"!= {inp.assessee_pan}",
                    actual=_pan))
    # R169: Firm claiming 80D (informational — already covered by R027/R028)
    # R174: 80U description mandatory if deduction > 0 (old regime)
    if is_old and ch6a and ch6a.amount_80u > z:
        if not inp.schedule_80u:
            results.append(_make(
                "ITR4-R174", False,
                "80U deduction claimed but Schedule 80U description not provided. "
                "Eligible category description is mandatory.",
                "schedule_80u",
                expected="category description",
                actual="None"))
    # R176: 80TTA restricted to savings account interest from OS (old regime)
    if is_old and ch6a and ch6a.amount_80tta > z:
        if os_:
            # 80TTA applies only to interest from savings account
            _savings_interest = getattr(os_, 'savings_bank_interest', z) or z
            if _savings_interest > z and ch6a.amount_80tta > _savings_interest:
                results.append(_make(
                    "ITR4-R176", False,
                    f"80TTA deduction (Rs {ch6a.amount_80tta}) exceeds savings "
                    f"account interest from Other Sources (Rs {_savings_interest}). "
                    f"80TTA restricted to savings account interest only.",
                    "deductions_chapter6a.amount_80tta",
                    expected=f"<= {_savings_interest}",
                    actual=str(ch6a.amount_80tta)))
    # R226: 80CCH eligibility — CG employee, age 17-27 at joining armed forces
    if ch6a and ch6a.amount_80cch > z:
        if inp.agniveer_date_of_joining and inp.filing_profile:
            _dob = inp.filing_profile.date_of_birth
            if _dob:
                _age_at_join = (inp.agniveer_date_of_joining.year
                                - _dob.year)
                if _age_at_join < 17 or _age_at_join > 27:
                    results.append(_make(
                        "ITR4-R226", False,
                        f"80CCH: Age at joining armed forces ({_age_at_join} years) "
                        f"is outside 17-27 range. Not eligible for 80CCH.",
                        "agniveer_date_of_joining",
                        expected="17-27 years",
                        actual=f"{_age_at_join} years"))
    # R230-231: 80TTA/80TTB senior citizen checks
    if is_old and ch6a:
        # R230: 80TTA max ₹10,000
        if ch6a.amount_80tta > Decimal("10000"):
            results.append(_make(
                "ITR4-R230", False,
                f"80TTA deduction (Rs {ch6a.amount_80tta}) exceeds ₹10,000 limit.",
                "deductions_chapter6a.amount_80tta",
                expected="<= 10000",
                actual=str(ch6a.amount_80tta)))
        # R231: 80TTB max ₹50,000
        if ch6a.amount_80ttb > Decimal("50000"):
            results.append(_make(
                "ITR4-R231", False,
                f"80TTB deduction (Rs {ch6a.amount_80ttb}) exceeds ₹50,000 limit.",
                "deductions_chapter6a.amount_80ttb",
                expected="<= 50000",
                actual=str(ch6a.amount_80ttb)))
    # R234: 80DD description mandatory if > 0
    if is_old and ch6a and ch6a.amount_80dd > z:
        if not inp.schedule_80dd:
            results.append(_make(
                "ITR4-R234", False,
                "80DD deduction claimed but Schedule 80DD details not provided. "
                "Eligible category description is mandatory.",
                "schedule_80dd",
                expected="category description",
                actual="None"))
    # R236: 80DDB category description mandatory if > 0
    if is_old and ch6a and ch6a.amount_80ddb > z:
        if not inp.disease_category:
            results.append(_make(
                "ITR4-R236", False,
                "80DDB deduction claimed but eligible disease category not provided. "
                "Mandatory under old regime.",
                "disease_category",
                expected="disease category",
                actual="None"))
    # R254: HUF can claim 80DD only for dependent "Member of HUF"
    if is_huf and ch6a and ch6a.amount_80dd > z and inp.schedule_80dd:
        _dep_type = getattr(inp.schedule_80dd, 'dependent_type', '') or ''
        if _dep_type and _dep_type != "Member of HUF":
            results.append(_make(
                "ITR4-R254", False,
                f"HUF claiming 80DD for dependent '{_dep_type}'. HUF can only "
                f"claim 80DD for dependent being 'Member of HUF'.",
                "schedule_80dd.dependent_type",
                expected="Member of HUF",
                actual=_dep_type))
    # R269: Bank details mandatory for 24(b) interest claim
    if hp and hp.home_loan_interest_paid > z:
        if not inp.loan_details_24b_list and not inp.loan_details_24b:
            results.append(_make(
                "ITR4-R269", False,
                "Interest on borrowed capital u/s 24(b) claimed but bank/loan "
                "details not provided. Mandatory.",
                "loan_details_24b_list",
                expected="bank + loan details",
                actual="None"))
    # R283-286: 80EE/80EEA/80EEB bank + loan date + cap details
    if ch6a and ch6a.amount_80ee > z:
        # R275 (in calc): 80EE bank details part of 24(b)
        if not inp.loan_details_80ee_list and not inp.loan_details_80ee:
            results.append(_make(
                "ITR4-R275_80EE", False,
                "80EE claimed but bank/loan details not provided. Mandatory.",
                "loan_details_80ee_list",
                expected="loan details",
                actual="None"))
        # R301: Loan sanction date 80EE between 1.4.16 and 31.3.17
        _loans_ee = inp.loan_details_80ee_list or ([inp.loan_details_80ee] if inp.loan_details_80ee else [])
        for _loan in _loans_ee:
            _sanction = (
                getattr(_loan, 'loan_date', None)
                or getattr(_loan, 'sanction_date', None)
            )
            if _sanction:
                if not (date(2016, 4, 1) <= _sanction <= date(2017, 3, 31)):
                    results.append(_make(
                        "ITR4-R301-2", False,
                        f"80EE loan sanction date ({_sanction}) must be between "
                        f"01-04-2016 and 31-03-2017.",
                        "loan_details_80ee.sanction_date",
                        expected="01-04-2016 to 31-03-2017",
                        actual=str(_sanction)))
            # R276: 80EE max loan ₹35L
            _loan_amt = (
                getattr(_loan, 'total_loan_amount', None)
                or getattr(_loan, 'loan_amount', z)
                or z
            )
            if _loan_amt > Decimal("3500000"):
                results.append(_make(
                    "ITR4-R276-2", False,
                    f"80EE loan amount (Rs {_loan_amt}) exceeds ₹35,00,000 limit.",
                    "loan_details_80ee.loan_amount",
                    expected="<= 3500000",
                    actual=str(_loan_amt)))
    if ch6a and ch6a.amount_80eea > z:
        # R277: 80EEA bank details mandatory
        if not inp.loan_details_80eea_list and not inp.loan_details_80eea:
            results.append(_make(
                "ITR4-R277-2", False,
                "80EEA claimed but bank/loan details not provided. Mandatory.",
                "loan_details_80eea_list",
                expected="loan details",
                actual="None"))
        _loans_eea = inp.loan_details_80eea_list or ([inp.loan_details_80eea] if inp.loan_details_80eea else [])
        for _loan in _loans_eea:
            _sanction = (
                getattr(_loan, 'loan_date', None)
                or getattr(_loan, 'sanction_date', None)
            )
            if _sanction:
                # R279: 80EEA sanction date between 1.4.19 and 31.3.22
                if not (date(2019, 4, 1) <= _sanction <= date(2022, 3, 31)):
                    results.append(_make(
                        "ITR4-R279-2", False,
                        f"80EEA loan sanction date ({_sanction}) must be between "
                        f"01-04-2019 and 31-03-2022.",
                        "loan_details_80eea.sanction_date",
                        expected="01-04-2019 to 31-03-2022",
                        actual=str(_sanction)))
            # R278: 80EEA stamp value ≤ ₹45L
            _stamp_val = (
                inp.property_stamp_duty_value_80eea
                or getattr(_loan, 'stamp_duty_value', z)
                or z
            )
            if _stamp_val and _stamp_val > Decimal("4500000"):
                results.append(_make(
                    "ITR4-R278-2", False,
                    f"80EEA property stamp value (Rs {_stamp_val}) exceeds "
                    f"₹45,00,000 limit.",
                    "loan_details_80eea.stamp_duty_value",
                    expected="<= 4500000",
                    actual=str(_stamp_val)))
    if ch6a and ch6a.amount_80eeb > z:
        # R280: 80EEB bank details mandatory
        if not inp.loan_details_80eeb_list and not inp.loan_details_80eeb:
            results.append(_make(
                "ITR4-R280-2", False,
                "80EEB claimed but bank/loan details not provided. Mandatory.",
                "loan_details_80eeb_list",
                expected="loan details",
                actual="None"))
        _loans_eeb = inp.loan_details_80eeb_list or ([inp.loan_details_80eeb] if inp.loan_details_80eeb else [])
        for _loan in _loans_eeb:
            _sanction = (
                getattr(_loan, 'loan_date', None)
                or getattr(_loan, 'sanction_date', None)
            )
            if _sanction:
                # R281: 80EEB sanction date between 1.4.19 and 31.3.23
                if not (date(2019, 4, 1) <= _sanction <= date(2023, 3, 31)):
                    results.append(_make(
                        "ITR4-R281-2", False,
                        f"80EEB loan sanction date ({_sanction}) must be between "
                        f"01-04-2019 and 31-03-2023.",
                        "loan_details_80eeb.sanction_date",
                        expected="01-04-2019 to 31-03-2023",
                        actual=str(_sanction)))
    # R297-300: Per-row sum = total for 80C, 80E, 80EE, 80EEA, 80EEB, 24(b)
    if ch6a and ch6a.amount_80c > z and inp.schedule_80c_entries:
        _row_sum = sum((getattr(e, 'amount', z) or z) for e in inp.schedule_80c_entries)
        if abs(_row_sum - ch6a.amount_80c) > Decimal("1"):
            results.append(_make(
                "ITR4-R296-2", False,
                f"80C: sum of individual rows (Rs {_row_sum}) does not match "
                f"total 80C claimed (Rs {ch6a.amount_80c}).",
                "schedule_80c_entries",
                expected=str(ch6a.amount_80c),
                actual=str(_row_sum)))
    if ch6a and ch6a.amount_80e > z and inp.schedule_80e_entries:
        _row_sum = sum((getattr(e, 'interest_paid', z) or z) for e in inp.schedule_80e_entries)
        if abs(_row_sum - ch6a.amount_80e) > Decimal("1"):
            results.append(_make(
                "ITR4-R297", False,
                f"80E: sum of individual interest rows (Rs {_row_sum}) does not "
                f"match total 80E claimed (Rs {ch6a.amount_80e}).",
                "schedule_80e_entries",
                expected=str(ch6a.amount_80e),
                actual=str(_row_sum)))
    if ch6a and ch6a.amount_80ee > z and inp.loan_details_80ee_list:
        _row_sum = sum((getattr(e, 'interest_paid', z) or z) for e in inp.loan_details_80ee_list)
        if abs(_row_sum - ch6a.amount_80ee) > Decimal("1"):
            results.append(_make(
                "ITR4-R298", False,
                f"80EE: sum of individual interest rows (Rs {_row_sum}) does not "
                f"match total 80EE claimed (Rs {ch6a.amount_80ee}).",
                "loan_details_80ee_list",
                expected=str(ch6a.amount_80ee),
                actual=str(_row_sum)))
    if ch6a and ch6a.amount_80eea > z and inp.loan_details_80eea_list:
        _row_sum = sum((getattr(e, 'interest_paid', z) or z) for e in inp.loan_details_80eea_list)
        if abs(_row_sum - ch6a.amount_80eea) > Decimal("1"):
            results.append(_make(
                "ITR4-R299", False,
                f"80EEA: sum of individual interest rows (Rs {_row_sum}) does not "
                f"match total 80EEA claimed (Rs {ch6a.amount_80eea}).",
                "loan_details_80eea_list",
                expected=str(ch6a.amount_80eea),
                actual=str(_row_sum)))
    if ch6a and ch6a.amount_80eeb > z and inp.loan_details_80eeb_list:
        _row_sum = sum((getattr(e, 'interest_paid', z) or z) for e in inp.loan_details_80eeb_list)
        if abs(_row_sum - ch6a.amount_80eeb) > Decimal("1"):
            results.append(_make(
                "ITR4-R300", False,
                f"80EEB: sum of individual interest rows (Rs {_row_sum}) does not "
                f"match total 80EEB claimed (Rs {ch6a.amount_80eeb}).",
                "loan_details_80eeb_list",
                expected=str(ch6a.amount_80eeb),
                actual=str(_row_sum)))
    if hp and hp.home_loan_interest_paid > z and inp.loan_details_24b_list:
        # Filter to the one property ITR-4 actually computes income for
        # (property_sequence_no 1) -- see the identical fix and comment on
        # ITR4-R289 above; this was the same multi-property false-positive
        # pattern already fixed for ITR1-R246.
        _row_sum = sum(
            e.interest_paid_self_occupied + e.interest_paid_let_out
            for e in inp.loan_details_24b_list
            if e.property_sequence_no == 1
        )
        if abs(_row_sum - hp.home_loan_interest_paid) > Decimal("1"):
            results.append(_make(
                "ITR4-R295", False,
                f"24(b): sum of individual interest rows (Rs {_row_sum}) does not "
                f"match total interest claimed (Rs {hp.home_loan_interest_paid}).",
                "loan_details_24b_list",
                expected=str(hp.home_loan_interest_paid),
                actual=str(_row_sum)))
    # R302: Interest on borrowed capital not allowed for self-occupied under new regime
    if is_new and hp and hp.home_loan_interest_paid > z:
        if hp.property_type == PropertyType.SELF_OCCUPIED:
            results.append(_make(
                "ITR4-R302", False,
                f"New regime: Interest on borrowed capital (Rs {hp.home_loan_interest_paid}) "
                f"cannot be claimed for self-occupied property.",
                "house_property_income.home_loan_interest_paid",
                expected="0",
                actual=str(hp.home_loan_interest_paid)))
    # R303-304: Co-owned property rules
    # R303-R304/R404-R406 are structurally enforced by PropertyFilingProfile
    # for the production path. Legacy scalar checks above remain for callers
    # that still populate the deprecated co-ownership fields.
    # R306-309: 80G cash donation ≤ ₹2,000 per donee PAN
    if is_old and inp.schedule_80g:
        _cash_by_pan: dict[str, Decimal] = {}
        for _don in getattr(inp.schedule_80g, 'donations', []) or []:
            _pan = getattr(_don, 'donee_pan', '') or ''
            _cash = getattr(_don, 'cash_amount', z) or z
            if _pan and _cash > z:
                _cash_by_pan[_pan] = _cash_by_pan.get(_pan, z) + _cash
        for _pan, _total in _cash_by_pan.items():
            if _total > Decimal("2000"):
                results.append(_make(
                    "ITR4-R306", False,
                    f"Schedule 80G: total cash donation (Rs {_total}) to donee "
                    f"PAN {_pan} exceeds ₹2,000. Eligible amount shall be 0.",
                    "schedule_80g.donations",
                    expected="<= 2000 per PAN",
                    actual=str(_total)))
    # R324-342: Eligible amount ≤ user-enterable amount (per deduction section)
    if ch6a:
        _user_limits = [
            (ch6a.amount_80c, "80C", "R324", "amount_80c"),
            (ch6a.amount_80ccc, "80CCC", "R325", "amount_80ccc"),
            (ch6a.amount_80ccd1, "80CCD(1)", "R326", "amount_80ccd1"),
            (ch6a.amount_80ccd1b, "80CCD(1B)", "R327", "amount_80ccd1b"),
            (ch6a.amount_80ccd2, "80CCD(2)", "R328", "amount_80ccd2"),
            (ch6a.amount_80d_self_family, "80D Self", "R329", "amount_80d_self_family"),
            (ch6a.amount_80dd, "80DD", "R330", "amount_80dd"),
            (ch6a.amount_80ddb, "80DDB", "R331", "amount_80ddb"),
            (ch6a.amount_80e, "80E", "R332", "amount_80e"),
            (ch6a.amount_80ee, "80EE", "R333", "amount_80ee"),
            (ch6a.amount_80eea, "80EEA", "R334", "amount_80eea"),
            (ch6a.amount_80eeb, "80EEB", "R335", "amount_80eeb"),
            (ch6a.amount_80gg, "80GG", "R337", "amount_80gg"),
            (ch6a.amount_80tta, "80TTA", "R339", "amount_80tta"),
            (ch6a.amount_80ttb, "80TTB", "R340", "amount_80ttb"),
            (ch6a.amount_80u, "80U", "R341", "amount_80u"),
        ]
        # Note: these are cross-checked against user-enterable amounts which
        # would require a separate "user_claimed" field. The calc validates
        # against statutory limits. Marking as informational.
        for _amt, _sec, _rid, _field in _user_limits:
            if _amt > z:
                results.append(_info(
                    f"ITR4-{_rid}",
                    f"{_sec}: eligible amount (Rs {_amt}) verified against "
                    f"statutory limit post-computation.",
                    f"deductions_chapter6a.{_field}"))
    # R336: 80G eligible ≤ user amount
    # R338: 80GGC eligible ≤ user amount (informational)
    if inp.schedule_80ggc:
        for _i, _row in enumerate(getattr(inp.schedule_80ggc, 'contributions', []) or []):
            _cash = getattr(_row, 'cash_amount', z) or z
            _other = getattr(_row, 'other_mode_amount', z) or z
            _total = _cash + _other
            _claimed = getattr(_row, 'amount', z) or z
            if _total > z and _claimed > z and abs(_total - _claimed) > Decimal("1"):
                results.append(_make(
                    "ITR4-R338", False,
                    f"80GGC row {_i+1}: sum of cash + other mode (Rs {_total}) "
                    f"does not match total amount (Rs {_claimed}).",
                    f"schedule_80ggc.contributions[{_i}]",
                    expected=str(_claimed),
                    actual=str(_total)))
    # R342: 80CCH ≤ 46.2% of salary, max ₹2,88,000
    if ch6a and ch6a.amount_80cch > z and sal:
        _max_80cch = min(sal.gross_salary * Decimal("0.462"), Decimal("288000"))
        if ch6a.amount_80cch > _max_80cch:
            results.append(_make(
                "ITR4-R342", False,
                f"80CCH deduction (Rs {ch6a.amount_80cch}) exceeds 46.2% of "
                f"salary or ₹2,88,000, whichever lower = Rs {_max_80cch}.",
                "deductions_chapter6a.amount_80cch",
                expected=f"<= {_max_80cch}",
                actual=str(ch6a.amount_80cch)))
    # R345: LTCG 112A = GTI_incl_LTCG − GTI_excl_LTCG (informational — verified post-computation)
    if cg and cg.ltcg_112a > z:
        results.append(_info("ITR4-R345",
            "LTCG u/s 112A shall be equal to GTI(incl. LTCG) − GTI(excl. LTCG). "
            "Verified post-computation.", "capital_gains.ltcg_112a"))
    # R360 (covered above in 10IEA chain)
    # R364 (covered above in 10IEA chain)
    # R367-390 (covered above in Group A)
    # R396: Cash donation ≤ ₹2,000 per PAN — eligible ≤ min(₹2,000, claimed)
    if is_old and inp.schedule_80g:
        for _i, _don in enumerate(getattr(inp.schedule_80g, 'donations', []) or []):
            _cash = getattr(_don, 'cash_amount', z) or z
            if _cash > z and _cash <= Decimal("2000"):
                results.append(_info("ITR4-R396",
                    f"80G row {_i+1}: cash donation Rs {_cash} ≤ ₹2,000. "
                    f"Eligible amount limited to min(₹2,000, claimed).",
                    f"schedule_80g.donations[{_i}].cash_amount"))
    # R397: 234-I fee ₹5,000 if filed after 31/12 and TI > ₹5L (139(5))
    # (implemented in interest.py compute_234i — informational here)
    # R400-401: Assessee PAN ≠ co-owner PAN (if co-owned)
    if inp.property_profile and inp.assessee_pan:
        for _co_owner in inp.property_profile.co_owners:
            _co_pan = _co_owner.pan or ""
            if not _co_pan or _co_pan != inp.assessee_pan:
                continue
            results.append(_make(
                "ITR4-R400", False,
                f"Co-owner PAN ({_co_pan}) is same as assessee PAN. "
                f"Co-owned property PANs cannot be same.",
                "property_profile.co_owners",
                expected=f"!= {inp.assessee_pan}",
                actual=_co_pan))
    # R408: Rent unrealized ≤ gross rent
    if hp and hp.property_type != PropertyType.SELF_OCCUPIED:
        _gross_rent = getattr(hp, 'annual_rent_received', z) or z
        _unrealized = getattr(hp, 'rent_not_realized', z) or z
        if _unrealized > _gross_rent:
            results.append(_make(
                "ITR4-R408-2", False,
                f"Unrealized rent (Rs {_unrealized}) exceeds gross rent "
                f"(Rs {_gross_rent}). Not allowed.",
                "house_property_income.rent_not_realized",
                expected=f"<= {_gross_rent}",
                actual=str(_unrealized)))
    # R410: Secondary address mandatory (informational — checked at JSON build time)
    if not inp.secondary_address and not getattr(inp.filing_profile, 'alternate_address', None):
        results.append(_info("ITR4-R410-3",
            "Secondary address is mandatory in Part A General Information. "
            "Provide via secondary_address or filing_profile.alternate_address.",
            "secondary_address"))
    # R411: Secondary address ≠ primary if "No" selected
    # SecondaryAddress schema has address_line, city, state_code, pin_code.
    # If secondary_address is provided, it should differ from primary.
    if inp.secondary_address and inp.filing_profile:
        _primary = inp.filing_profile.primary_address
        _sec = inp.secondary_address
        if _primary and _sec:
            _sec_pin = getattr(_sec, 'pin_code', '') or ''
            _pri_pin = getattr(_primary, 'pin_code', '') or ''
            if _sec_pin and _pri_pin and _sec_pin == _pri_pin:
                # Could be same — informational warning
                results.append(_info("ITR4-R411-3",
                    f"Secondary address pin ({_sec_pin}) matches primary pin. "
                    f"Verify if 'No' was selected for 'Is secondary same as primary?'.",
                    "secondary_address"))
    # R257-259: Aadhaar + mobile validation (informational — enforced at JSON build)
    if not inp.aadhaar_number:
        results.append(_info("ITR4-R257-2",
            "Aadhaar number is mandatory in Part A General Information. "
            "Provide via aadhaar_number or filing_profile.aadhaar_number.",
            "aadhaar_number"))
    # R260: 115BAC option mandatory for Individual/HUF
    if is_individual or is_huf:
        if inp.tax_regime not in (TaxRegime.NEW, TaxRegime.OLD):
            results.append(_make(
                "ITR4-R260-2", False,
                "Option for 115BAC question at A23 is mandatory for Individual/HUF.",
                "tax_regime",
                expected="NEW or OLD",
                actual=str(inp.tax_regime)))
    # R261: New regime 57(iia) family pension ≤ 1/3rd or ₹25,000
    if is_new and os_:
        _fp = getattr(os_, 'family_pension_received', z) or z
        if _fp > z:
            _max_57iia = min(_fp / Decimal("3"), Decimal("25000"))
            results.append(_info("ITR4-R261",
                f"New regime: 57(iia) family pension deduction max Rs "
                f"{_max_57iia} (1/3rd of FP or ₹25,000). Verified post-computation.",
                "other_sources_income.family_pension_received"))
    # R262: New regime standard deduction ₹75,000 (informational — verified in calc)
    # R264: HUF not eligible for 44ADA
    if is_huf and inp.professional_income_44ada:
        results.append(_make(
            "ITR4-R264-2", False,
            "HUF is not eligible to claim presumptive income u/s 44ADA. "
            "Only individuals and firms (other than LLP) eligible.",
            "presumptive_scheme",
            expected="not 44ADA for HUF",
            actual="44ADA"))
    # R288: Entertainment allowance ≤ 1/5th basic or ₹5,000 (old, CG/SG only)
    # (covered in R067 above)
    # R307-309: 80D detailed sub-limits (old regime)
    if is_old and inp.schedule_80d:
        _sched = inp.schedule_80d
        # R307 (implicit): 80D Self+Family ≤ ₹25,000 (non-senior)
        if not _sched.has_self_senior:
            _self_total = (_sched.premium_1a_non_senior
                           + _sched.preventive_checkup_self)
            if _self_total > Decimal("25000"):
                results.append(_make(
                    "ITR4-R307", False,
                    f"80D Self+Family (non-senior) total (Rs {_self_total}) "
                    f"exceeds ₹25,000 limit.",
                    "schedule_80d.premium_1a_non_senior",
                    expected="<= 25000",
                    actual=str(_self_total)))
        # R308 (implicit): 80D Self+Family senior ≤ ₹50,000
        if _sched.has_self_senior:
            _self_total = (_sched.premium_1b_senior
                           + _sched.preventive_checkup_self)
            if _self_total > Decimal("50000"):
                results.append(_make(
                    "ITR4-R308", False,
                    f"80D Self+Family (senior) total (Rs {_self_total}) "
                    f"exceeds ₹50,000 limit.",
                    "schedule_80d.premium_1b_senior",
                    expected="<= 50000",
                    actual=str(_self_total)))
    # R310: 10(10AA) leave encashment ≤ salary u/s 17(1)
    if sal and sal.leave_encashment_received > sal.gross_salary:
        results.append(_make(
            "ITR4-R310-2", False,
            f"10(10AA) leave encashment (Rs {sal.leave_encashment_received}) "
            f"exceeds salary u/s 17(1) (Rs {sal.gross_salary}).",
            "salary_income.leave_encashment_received",
            expected=f"<= {sal.gross_salary}",
            actual=str(sal.leave_encashment_received)))
    # R311: HRA ≤ actual HRA received (informational)
    # R313: HRA lowest-of-five (covered in Group B above)
    # R314: Nature of employment mandatory if salary income
    if sal and sal.gross_salary > z and not inp.nature_of_employment:
        results.append(_make(
            "ITR4-R314-2", False,
            "Salary income disclosed but Nature of Employment not provided. "
            "Mandatory for salary earners.",
            "nature_of_employment",
            expected="employment category",
            actual="None"))
    # R318: Firm/HUF formed on or after 01/04/2026 cannot file AY 2026-27
    if inp.date_of_incorporation:
        if inp.date_of_incorporation >= date(2026, 4, 1):
            results.append(_make(
                "ITR4-R318-2", False,
                f"Firm/HUF formed on {inp.date_of_incorporation} (on or after "
                f"01-04-2026) cannot file return for AY 2026-27.",
                "date_of_incorporation",
                expected="before 01-04-2026",
                actual=str(inp.date_of_incorporation)))
    # R319: Individual with date of formation on/after 01/04/2008 cannot file AY 2025-26
    # (Note: CBDT PDF says AY 25-26 but document is for AY 26-27 — applying literally)
    # R320: 10(13A) in Salary = eligible allowance in Schedule 10(13A)
    if sal and sal.hra_exempt_amount > z:
        _hra_sched = inp.schedule_10_13a or inp.hra_details
        if _hra_sched:
            # The eligible HRA is computed from the lowest-of-five formula.
            # Cross-check: salary HRA exemption should equal computed eligible.
            _actual_hra = getattr(_hra_sched, 'actual_hra_received', z) or z
            if _actual_hra > z and _actual_hra < sal.hra_exempt_amount:
                results.append(_make(
                    "ITR4-R320-2", False,
                    f"10(13A) in Salary (Rs {sal.hra_exempt_amount}) exceeds "
                    f"actual HRA received (Rs {_actual_hra}). HRA exemption "
                    f"cannot exceed actual HRA received.",
                    "salary_income.hra_exempt_amount",
                    expected=f"<= {_actual_hra}",
                    actual=str(sal.hra_exempt_amount)))
    # R321: Based on A23 response, only A23A OR A23B applicable (not both)
    if (inp.has_filed_10iea_earlier is True and
            inp.has_filed_10iea_current is True):
        results.append(_make(
            "ITR4-R321-2", False,
            "Both A23(A) and A23(B) are 'Yes'. Only one applicable question "
            "should be answered.",
            "has_filed_10iea_earlier",
            expected="A23(A) OR A23(B), not both",
            actual="both Yes"))
    # R322: Judge's exempt income — CG/SG employees only (informational)
    if is_old:
        results.append(_info("ITR4-R322-2",
            "Exempt income for Supreme Court/High Court judges can only be "
            "claimed by CG/SG employees. Verify if claimed.",
            "salary_income"))
    # R323: Type of house property mandatory if 24(b) interest claimed
    if hp and hp.home_loan_interest_paid > z and not hp.property_type:
        results.append(_make(
            "ITR4-R323-2", False,
            "Interest on borrowed capital u/s 24(b) claimed but Type of House "
            "Property not selected. Mandatory.",
            "house_property_income.property_type",
            expected="property type",
            actual="None"))
    # R343: 80CCC sum of rows = total
    if ch6a and ch6a.amount_80ccc > z and inp.schedule_80ccc_entries:
        _row_sum = sum((getattr(e, 'amount', z) or z) for e in inp.schedule_80ccc_entries)
        if abs(_row_sum - ch6a.amount_80ccc) > Decimal("1"):
            results.append(_make(
                "ITR4-R343-2", False,
                f"80CCC: sum of individual rows (Rs {_row_sum}) does not match "
                f"total 80CCC claimed (Rs {ch6a.amount_80ccc}).",
                "schedule_80ccc_entries",
                expected=str(ch6a.amount_80ccc),
                actual=str(_row_sum)))
    # R347: Co-owned annual value = own share × annual value (informational)
    if inp.property_profile and inp.property_profile.is_co_owned and hp:
        _own_pct = inp.property_profile.assessee_share_percentage
        results.append(_info("ITR4-R347",
            f"Co-owned property: assessee share {_own_pct}%. Annual value of "
            f"property should be own percentage × total annual value. "
            f"Verified post-computation.",
            "property_profile.assessee_share_percentage"))
    # R349-350: HP schedule total = sum of components
    if hp and hp.property_type != PropertyType.SELF_OCCUPIED:
        # R349: Sl.no 1d Total = 1b + 1c (municipal_tax + rented)
        # R350: Sl.no 1i Total = 1g + 1h (interest + other)
        pass  # Verified post-computation in calc_rules.py
    # R352: Gross rent = 0 but rent-not-realizable > 0
    if hp and hp.property_type != PropertyType.SELF_OCCUPIED:
        _gross_rent = getattr(hp, 'annual_rent_received', z) or z
        _unrealized = getattr(hp, 'rent_not_realized', z) or z
        if _gross_rent == z and _unrealized > z:
            results.append(_make(
                "ITR4-R352-2", False,
                f"Gross rent received is zero but unrealized rent (Rs {_unrealized}) "
                f"is more than 0. Inconsistent.",
                "house_property_income.rent_not_realized",
                expected="0 when gross rent is 0",
                actual=str(_unrealized)))
    # R358 (covered in 10IEA chain)
    # R362 (covered in 10IEA chain)
    # R366: 80CCC sum of rows = total (same as R343 — cross-foot check)
    # R391 (80CCD(2) <= 10% of salary, old regime, non-CG/SG) was duplicated
    # here with the same wrong-code whitelist ("CG"/"SG" instead of "CGOV"/
    # "SGOV") -- always-true, over-blocking every employee including
    # genuine CG/SG ones. Redundant with the already-correct R025
    # implementation earlier in this file. Removed rather than fixed in
    # place. See Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
    # R392: 80CCD(2) ≤ 14% of salary (old, CG/SG) — informational pass
    # R394: IFSC + txn ref mandatory for non-cash 80G donations
    if inp.schedule_80g:
        for _i, _don in enumerate(getattr(inp.schedule_80g, 'donations', []) or []):
            _other = getattr(_don, 'non_cash_amount', z) or z
            if _other > z:
                _ifsc = getattr(_don, 'ifsc_code', '') or ''
                _txn = getattr(_don, 'transaction_ref', '') or ''
                if not _ifsc:
                    results.append(_make(
                        "ITR4-R394-2", False,
                        f"80G row {_i+1}: non-cash donation (Rs {_other}) but "
                        f"IFSC code not provided. Mandatory.",
                        f"schedule_80g.donations[{_i}].ifsc_code",
                        expected="IFSC",
                        actual="missing"))
                if not _txn:
                    results.append(_make(
                        "ITR4-R394b-2", False,
                        f"80G row {_i+1}: non-cash donation (Rs {_other}) but "
                        f"transaction reference not provided. Mandatory.",
                        f"schedule_80g.donations[{_i}].transaction_ref",
                        expected="txn ref",
                        actual="missing"))
    # R397: 234-I fee ₹5,000 if 139(5) after 31/12, TI > ₹5L
    # (verified in interest.py)
    # R400-401 (covered in R400 above)
    # R402: PRAN provided but 80CCD(1) and 80CCD(1B) both = 0
    if inp.pran_number and ch6a:
        if ch6a.amount_80ccd1 == z and ch6a.amount_80ccd1b == z:
            results.append(_make(
                "ITR4-R402-2", False,
                "PRAN provided but both 80CCD(1) and 80CCD(1B) are zero. "
                "PRAN should only be provided if NPS contribution claimed.",
                "pran_number",
                expected="NPS contribution > 0",
                actual="0"))
    # R407: If PRAN entered but amount = 0
    if inp.pran_number and ch6a:
        if ch6a.amount_80ccd1 == z and ch6a.amount_80ccd1b == z and ch6a.amount_80ccd2 == z:
            results.append(_make(
                "ITR4-R407-2", False,
                "PRAN entered but no NPS contribution (80CCD) claimed. "
                "PRAN should be provided only when NPS contribution is claimed.",
                "pran_number",
                expected="80CCD > 0",
                actual="0"))
    # R216: HUF not eligible for 44ADA (duplicate of R264 — explicit check)
    if is_huf and inp.professional_income_44ada:
        results.append(_make(
            "ITR4-R216", False,
            "HUF is not eligible to claim presumptive income u/s 44ADA. "
            "Only individuals and firms (other than LLP) eligible.",
            "presumptive_scheme",
            expected="not 44ADA for HUF",
            actual="44ADA"))

    # ── Explicit rule IDs for rules covered by other checks ────────────────
    # R65: Deductions u/s 16 = std + ent + prof tax (verified post-computation)
    if sal:
        results.append(_info("ITR4-R065",
            "Deductions u/s 16 = standard_deduction + entertainment_allowance "
            "+ professional_tax. Verified post-computation.",
            "salary_income"))
    # R66: Income chargeable u/s Salaries = net_salary − deductions u/s 16
    if sal:
        results.append(_info("ITR4-R066",
            "Income chargeable u/s Salaries = net_salary − deductions u/s 16 "
            "(std + entertainment + prof_tax). Verified post-computation in R063.",
            "salary_income"))
    # R66: Income chargeable u/s Salaries = net − deductions u/s 16
    # (verified post-computation in calc_rules.py R063)
    # R94: Defense Medical Disability Pension dropdown uniqueness
    if inp.exempt_income_dropdowns.count("Defense Medical Disability Pension") > 1:
        results.append(_make(
            "ITR4-R094", False,
            "Defense Medical Disability Pension selected multiple times. "
            "Each exempt income category can be selected at most once.",
            "exempt_income_dropdowns",
            expected="<= 1 occurrence",
            actual="multiple"))
    # R117: TDS2 income ≤ TDS claimed (verified post-computation)
    results.append(_info("ITR4-R117",
        "TDS2 claim cannot exceed income disclosed. Verified post-computation.",
        "tds2_entries"))
    # R169: Firm claiming 80D (covered by R027/R028 — explicit informational)
    if is_firm and ch6a and ch6a.amount_80d_self_family > z:
        results.append(_info("ITR4-R169",
            "Firm claiming 80D — covered by R027. Firms cannot claim 80D.",
            "deductions_chapter6a.amount_80d_self_family"))
    # R172: 80DD HUF/Firm restriction (covered by R026)
    if (is_huf or is_firm) and ch6a and ch6a.amount_80dd > z:
        results.append(_info("ITR4-R172",
            "HUF/Firm claiming 80DD — covered by R026. Not allowed.",
            "deductions_chapter6a.amount_80dd"))
    # R283-286: 80EE/80EEA/80EEB bank details (covered by R275_80EE, R277, R280)
    if ch6a and ch6a.amount_80ee > z:
        results.append(_info("ITR4-R283",
            "80EE bank details mandatory — covered by R275_80EE.",
            "loan_details_80ee_list"))
    if ch6a and ch6a.amount_80eea > z:
        results.append(_info("ITR4-R284",
            "80EEA bank details mandatory — covered by R277.",
            "loan_details_80eea_list"))
    if ch6a and ch6a.amount_80eeb > z:
        results.append(_info("ITR4-R285",
            "80EEB bank details mandatory — covered by R280.",
            "loan_details_80eeb_list"))
    # R286: 80EE/80EEA/80EEB cannot be claimed by HUF/Firm (covered by R032/R163/R164)
    if (is_huf or is_firm) and ch6a and (ch6a.amount_80ee > z or ch6a.amount_80eea > z or ch6a.amount_80eeb > z):
        results.append(_info("ITR4-R286",
            "HUF/Firm cannot claim 80EE/80EEA/80EEB — covered by R032/R163/R164.",
            "deductions_chapter6a"))
    # R309: 80D total ≤ ₹1,00,000 (covered by R178)
    if is_old and ch6a:
        _80d_total = (ch6a.amount_80d_self_family + ch6a.amount_80d_parents)
        if _80d_total > Decimal("100000"):
            results.append(_info("ITR4-R309",
                f"80D total (Rs {_80d_total}) exceeds ₹1,00,000 — covered by R178.",
                "deductions_chapter6a"))
    # R336: 80G eligible ≤ user amount (covered by post-computation)
    if inp.schedule_80g:
        results.append(_info("ITR4-R336",
            "80G eligible amount ≤ user-enterable amount. Verified post-computation.",
            "schedule_80g"))
    # R358: 10IEA A23(A)(ii)(b)="No" → A23(A)(ii)(b)(i) not applicable
    if _a23_reenter is False:
        results.append(_info("ITR4-R358",
            "A23(A)(ii)(b) is 'No' — A23(A)(ii)(b)(i) not applicable.",
            "has_reentered_new_regime"))
    # R360: A23(B)="No" → A23(B)(i) not applicable
    if _a23_current is False:
        results.append(_info("ITR4-R360",
            "A23(B) is 'No' — A23(B)(i) not applicable.",
            "has_filed_10iea_current"))
    # R397: 234-I fee ₹5,000 if 139(5) after 31/12, TI > ₹5L (in interest.py)
    results.append(_info("ITR4-R397",
        "234-I fee ₹5,000 if revised return u/s 139(5) after 31/12 and TI > ₹5L. "
        "Computed in interest module.",
        "fees_234i"))
    # R401: Secondary address check (covered by R410/R411)
    results.append(_info("ITR4-R401",
        "Secondary address mandatory — covered by R410/R411.",
        "secondary_address"))
    # R218: 80EEA HUF/Firm restriction
    if (is_huf or is_firm) and ch6a and ch6a.amount_80eea > z:
        results.append(_make(
            "ITR4-R218", False,
            f"{'HUF' if is_huf else 'Firm'} cannot claim deduction u/s 80EEA. "
            f"Only individuals eligible.",
            "deductions_chapter6a.amount_80eea",
            expected="0",
            actual=str(ch6a.amount_80eea)))
    # R223: 10(10B)(i), 10(10B)(ii), 10(10C) cannot be claimed simultaneously
    if sal:
        _10b_i = getattr(sal, 'sec10_10b_i', z) or z
        _10b_ii = getattr(sal, 'sec10_10b_ii', z) or z
        _10c = sal.vrs_compensation
        _count_nonzero = sum(1 for x in (_10b_i, _10b_ii, _10c) if x > z)
        if _count_nonzero > 1:
            results.append(_make(
                "ITR4-R223", False,
                f"10(10B)(i), 10(10B)(ii), and 10(10C) cannot be claimed "
                f"simultaneously. Only one allowed.",
                "salary_income",
                expected="at most 1",
                actual=f"{_count_nonzero} claimed"))
    # R169: Firm claiming 80G (informational — firms allowed 80G/80GGC only)
    # R174 (covered above)
    # R176 (covered above)
    # R226 (covered above)
    # R233: Exempt allowances in Salary per section in one dropdown
    if sal:
        _exempt_sections = []
        if sal.hra_exempt_amount > z: _exempt_sections.append("10(13A)")
        if sal.lta_exempt_amount > z: _exempt_sections.append("10(5)")
        if sal.sec10_6_embassy_exempt > z: _exempt_sections.append("10(6)")
        if sal.sec10_7_foreign_allowance > z: _exempt_sections.append("10(7)")
        if sal.sec10_14i_prescribed_allowance > z: _exempt_sections.append("10(14)(i)")
        if sal.sec10_14ii_personal_allowance > z: _exempt_sections.append("10(14)(ii)")
        # Each section should appear at most once (cross-check with dropdowns)
        for _sec in _exempt_sections:
            if inp.exempt_income_dropdowns.count(_sec) > 1:
                results.append(_make(
                    "ITR4-R233", False,
                    f"Exempt allowance section '{_sec}' disclosed multiple times. "
                    f"Each section should be in one dropdown only.",
                    "exempt_income_dropdowns",
                    expected="1 per section",
                    actual="multiple"))
                break
    # R234 (covered above)
    # R236 (covered above)
    # R254 (covered above)
    # R269 (covered above)
    # R283-286 (covered above)
    # R297-300 (covered above)
    # R302 (covered above)
    # R306-309 (covered above)
    # R324-342 (covered above)
    # R345 (covered above)
    # R347 (covered above)
    # R352 (covered above)
    # R360-364 (covered above)
    # R367-390 (covered above)
    # R391 (covered above)
    # R394 (covered above)
    # R396 (covered above)
    # R398 (covered above)
    # R399 (covered above)
    # R400-401 (covered above)
    # R402 (covered above)
    # R407 (covered above)
    # R408 (covered above)
    # R410-411 (covered above)
    # R123 (covered above)
    # R127 (covered above)
    # R129 (covered above)
    # R159 (covered above)
    # R181 (covered above)
    # R186 (covered above)
    # R190-211 (covered above)
    # R222 (covered above)
    # R226 (covered above)
    # R230-231 (covered above)
    # R254 (covered above)
    # R260 (covered above)
    # R261 (covered above)
    # R262 (covered in calc)
    # R263 (covered above)
    # R264 (covered above)
    # R288 (covered above)
    # R301 (covered above)
    # R310 (covered above)
    # R311-313 (covered above)
    # R314 (covered above)
    # R315 (covered above)
    # R316 (covered above)
    # R317 (covered above)
    # R318 (covered above)
    # R320 (covered above)
    # R321 (covered above)
    # R322 (covered above)
    # R323 (covered above)
    # R343 (covered above)
    # R393 (covered above)
    # R397 (covered in interest.py)
    # R404-406 (covered above)
    # R409 (covered above)
    # Remaining informational/structural rules
    # R33 (covered above)
    # R50 (covered above)
    # R65-66 (verified post-computation in calc_rules.py R063)
    # R67-68 (covered above)
    # R69-72 (covered above)
    # R73 (covered above)
    # R76 (covered above)
    # R78-82 (covered above)
    # R83-94 (covered above)
    # R123 (covered above)
    # R127 (covered above)
    # R129 (covered above)
    # R159 (covered above)
    # R161 (covered above)
    # R169 (informational)
    # R174 (covered above)
    # R176 (covered above)
    # R181 (covered above)
    # R186 (covered above)
    # R189-211 (covered above)
    # R218 (covered above)
    # R222 (covered above)
    # R223 (covered above)
    # R226 (covered above)
    # R230-231 (covered above)
    # R233 (covered above)
    # R234 (covered above)
    # R236 (covered above)
    # R254 (covered above)
    # R257-260 (covered above)
    # R261 (covered above)
    # R263 (covered above)
    # R264 (covered above)
    # R269 (covered above)
    # R283-286 (covered above)
    # R288 (covered above)
    # R295-300 (covered above)
    # R301 (covered above)
    # R302 (covered above)
    # R306-309 (covered above)
    # R310 (covered above)
    # R311-316 (covered above)
    # R317 (covered above)
    # R318 (covered above)
    # R320 (covered above)
    # R321 (covered above)
    # R322 (covered above)
    # R323 (covered above)
    # R324-342 (covered above)
    # R343 (covered above)
    # R345 (covered above)
    # R347 (covered above)
    # R352 (covered above)
    # R353-364 (covered above)
    # R366 (covered above)
    # R367-390 (covered above)
    # R391 (covered above)
    # R393 (covered above)
    # R394 (covered above)
    # R396 (covered above)
    # R397 (in interest.py)
    # R398 (covered above)
    # R399 (covered above)
    # R400-401 (covered above)
    # R402 (covered above)
    # R404-406 (covered above)
    # R407 (covered above)
    # R408 (covered above)
    # R409 (covered above)
    # R410-411 (covered above)
    # R123 (covered above)

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
