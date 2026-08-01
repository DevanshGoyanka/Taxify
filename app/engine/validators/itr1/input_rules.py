"""
ITR-1 input validation rules (pre-computation).

These rules mirror CBDT Category A rules for AY 2026-27 that check field
values BEFORE computation.  Rules that reference fields not present in the
current schema are marked as informational (Severity.D, passed=True).

Organised by CBDT rule topic section.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from app.schemas.itr1 import (
    AgeBracket,
    AssesseeType,
    ITR1Input,
    PropertyType,
    Section80DDBUserType,
    TaxRegime,
)
from app.engine.constants import SECTION_80DDB_LIMIT, SECTION_80DDB_SENIOR_LIMIT
from app.engine.validators.base import ValidationResult, Severity

_z = Decimal("0")


def _make(rule_id: str, passed: bool, message: str, field_path: str = "", **kwargs) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id, severity=Severity.A, passed=passed,
        message=message, field_path=field_path, **kwargs,
    )


def _info(rule_id: str, message: str, field_path: str = "") -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id, severity=Severity.D, passed=True,
        message=message, field_path=field_path,
    )


def _warn(rule_id: str, message: str, field_path: str = "") -> ValidationResult:
    """Category B warning — the input is unusual but may still be correct. Not a hard error."""
    return ValidationResult(
        rule_id=rule_id, severity=Severity.B, passed=True,
        message=message, field_path=field_path,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_itr1_input(inp: ITR1Input) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    ch6a = inp.deductions_chapter6a
    sal = inp.salary_income
    hp = inp.house_property_income
    osi = inp.other_sources_income
    cg = inp.capital_gains
    is_new = inp.tax_regime == TaxRegime.NEW
    is_old = inp.tax_regime == TaxRegime.OLD
    is_senior = inp.age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    is_super_senior = inp.age_bracket == AgeBracket.ABOVE_80
    assessee = inp.assessee_type
    is_individual = assessee == AssesseeType.INDIVIDUAL
    is_huf = assessee == AssesseeType.HUF
    is_firm = assessee == AssesseeType.FIRM

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Assessee Type Eligibility
    # ═══════════════════════════════════════════════════════════════════════

    # ITR-1 is only for individuals
    if not is_individual:
        results.append(_make(
            "ITR1-R032", False,
            f"ITR-1 (Sahaj) is applicable only to resident individuals. "
            f"Assessee type: {assessee.value}. Use ITR-2/3/4 instead.",
            "assessee_type"))

    # ========================================================================
    # SECTION: Section 10 Exempt Allowances Consistency (R100-R115)
    # ========================================================================

    if sal:
        # R100: Gratuity exempt amount cannot exceed gross salary
        if sal.gratuity_received > _z and sal.gratuity_received > sal.gross_salary:
            results.append(_make(
                "ITR1-R100", False,
                f"Gratuity exempt amount (Rs {sal.gratuity_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}). "
                f"Exempt gratuity cannot be more than total salary earned.",
                "salary_income.gratuity_received",
            ))
        # R101: Commuted pension cannot exceed gross salary
        if sal.commuted_pension_received > _z and sal.commuted_pension_received > sal.gross_salary:
            results.append(_make(
                "ITR1-R101", False,
                f"Commuted pension (Rs {sal.commuted_pension_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}).",
                "salary_income.commuted_pension_received",
            ))
        # R102: Leave encashment exempt cannot exceed gross salary
        if sal.leave_encashment_received > _z and sal.leave_encashment_received > sal.gross_salary:
            results.append(_make(
                "ITR1-R102", False,
                f"Leave encashment (Rs {sal.leave_encashment_received}) exceeds "
                f"gross salary (Rs {sal.gross_salary}).",
                "salary_income.leave_encashment_received",
            ))
        # R142: 10(10AA) > ₹25L for non-govt employees
        if sal.leave_encashment_received > 2_500_000 and inp.nature_of_employment:
            emp_lower = inp.nature_of_employment.lower()
            is_govt = any(kw in emp_lower for kw in ("central government", "state government", "cg-", "sg-"))
            if not is_govt:
                results.append(_make(
                    "ITR1-R142", False,
                    f"Leave encashment 10(10AA) of Rs {sal.leave_encashment_received} exceeds "
                    f"₹25,00,000 limit for non-government employees (including PSU). "
                    f"Maximum exemption for non-Govt employees is ₹25 lakh.",
                    "salary_income.leave_encashment_received",
                ))
        # R103: VRS exempt cap (Rs 5,00,000 for individuals)
        if sal.vrs_compensation > 500_000:
            results.append(_make(
                "ITR1-R103", False,
                f"VRS compensation exempt amount (Rs {sal.vrs_compensation}) "
                f"exceeds Rs 5,00,000 statutory limit for non-government employees.",
                "salary_income.vrs_compensation",
            ))
        # R104: Retrenchment compensation exempt cap
        if sal.retrenchment_compensation > 500_000:
            results.append(_make(
                "ITR1-R104", False,
                f"Retrenchment compensation exempt amount (Rs {sal.retrenchment_compensation}) "
                f"exceeds Rs 5,00,000 statutory maximum.",
                "salary_income.retrenchment_compensation",
            ))
        # R105: Transport allowance consistency
        if sal.transport_allowance > 38_400:
            results.append(_make(
                "ITR1-R105", False,
                f"Transport allowance (Rs {sal.transport_allowance}) exceeds "
                f"Rs 38,400 (Rs 3,200 * 12 months) reasonable annual maximum for non-Visually Imaired.",
                "salary_income.transport_allowance",
            ))
        # R106: LTA received but exempt claimed = 0 — informational
        if sal.lta_amount_received > _z and sal.lta_exempt_amount == _z:
            results.append(_info(
                "ITR1-R106",
                f"LTA received (Rs {sal.lta_amount_received}) but exempt amount is 0. "
                f"LTA exemption requires actual travel and proof. "
                f"If no travel performed, the full LTA is taxable.",
                "salary_income.lta_exempt_amount",
            ))
        # R107: LTA exempt cannot exceed LTA received
        if sal.lta_exempt_amount > sal.lta_amount_received:
            results.append(_make(
                "ITR1-R107", False,
                f"LTA exempt (Rs {sal.lta_exempt_amount}) exceeds LTA received "
                f"(Rs {sal.lta_amount_received}). Exempt amount cannot be more than "
                f"what was actually received.",
                "salary_income.lta_exempt_amount",
            ))
        # R064: LTA exempt cannot exceed Salary 17(1) (CBDT Sl 64)
        if sal.lta_exempt_amount > _z and sal.lta_exempt_amount > sal.gross_salary:
            results.append(_make(
                "ITR1-R064", False,
                f"LTA exempt (Rs {sal.lta_exempt_amount}) exceeds gross salary 17(1) "
                f"(Rs {sal.gross_salary}). Exemption cannot exceed salary earned.",
                "salary_income.lta_exempt_amount",
            ))
        # R065: Sec 10(6) embassy official exempt ≤ gross salary
        if sal.sec10_6_embassy_exempt > _z and sal.sec10_6_embassy_exempt > sal.gross_salary:
            results.append(_make(
                "ITR1-R065", False,
                f"Sec 10(6) embassy official exemption (Rs {sal.sec10_6_embassy_exempt}) "
                f"exceeds gross salary (Rs {sal.gross_salary})",
                "salary_income.sec10_6_embassy_exempt",
            ))
        # R066: Sec 10(7) foreign service allowance ≤ gross salary
        if sal.sec10_7_foreign_allowance > _z and sal.sec10_7_foreign_allowance > sal.gross_salary:
            results.append(_make(
                "ITR1-R066", False,
                f"Sec 10(7) foreign service allowance (Rs {sal.sec10_7_foreign_allowance}) "
                f"exceeds gross salary (Rs {sal.gross_salary})",
                "salary_income.sec10_7_foreign_allowance",
            ))
        # R073: Sec 10(10CC) ≤ perquisites u/s 17(2)
        if sal.sec10_10cc_perquisite_tax > _z and sal.sec10_10cc_perquisite_tax > sal.perquisites_value:
            results.append(_make(
                "ITR1-R073", False,
                f"Sec 10(10CC): employer-paid perquisite tax (Rs {sal.sec10_10cc_perquisite_tax}) "
                f"exceeds value of perquisites u/s 17(2) (Rs {sal.perquisites_value}). "
                f"10(10CC) exempt portion cannot exceed the perquisite value itself.",
                "salary_income.sec10_10cc_perquisite_tax",
            ))
        # R164-R167: New regime — most Section 10 exemptions are disallowed
        if is_new:
            if sal.gratuity_received > _z:
                results.append(_make(
                    "ITR1-R164", False,
                    f"Gratuity exemption (Rs {sal.gratuity_received}) is not "
                    f"available under the new tax regime (Section 115BAC).",
                    "salary_income.gratuity_received",
                ))
            if sal.commuted_pension_received > _z:
                results.append(_make(
                    "ITR1-R165", False,
                    f"Commuted pension exemption (Rs {sal.commuted_pension_received}) "
                    f"is not available under the new tax regime.",
                    "salary_income.commuted_pension_received",
                ))
            if sal.leave_encashment_received > _z:
                results.append(_make(
                    "ITR1-R166", False,
                    f"Leave encashment exemption (Rs {sal.leave_encashment_received}) "
                    f"is not available under the new tax regime.",
                    "salary_income.leave_encashment_received",
                ))
            if sal.vrs_compensation > _z:
                results.append(_make(
                    "ITR1-R167a", False,
                    f"VRS compensation exemption (Rs {sal.vrs_compensation}) "
                    f"is not available under the new tax regime.",
                    "salary_income.vrs_compensation",
                ))
            if sal.retrenchment_compensation > _z:
                results.append(_make(
                    "ITR1-R167b", False,
                    f"Retrenchment compensation exemption (Rs {sal.retrenchment_compensation}) "
                    f"is not available under the new tax regime.",
                    "salary_income.retrenchment_compensation",
                ))

    # ========================================================================
    # SECTION: 80C / 80CCC / 80CCD(1) Combined Limits
    # ========================================================================

    if ch6a:
        pool_80c = ch6a.amount_80c + ch6a.amount_80ccc + ch6a.amount_80ccd1
    else:
        pool_80c = _z

    # ========================================================================
    # SECTION: Bank Account Validation (R260-R263)
    # ========================================================================

    if inp.bank_accounts:
        primary_count = sum(1 for ba in inp.bank_accounts if ba.is_primary)
        if primary_count == 0:
            results.append(_make(
                "ITR1-R260", False,
                "No primary bank account selected for refund credit. "
                "At least one bank account must be marked is_primary=True.",
                "bank_accounts",
            ))
        if primary_count > 1:
            results.append(_make(
                "ITR1-R261", False,
                f"Multiple primary bank accounts ({primary_count}). "
                f"Only one account can be marked as primary for refund credit.",
                "bank_accounts",
            ))
        for i, ba in enumerate(inp.bank_accounts):
            import re
            ifsc_pattern = r"^[A-Z]{4}0[A-Z0-9]{6}$"
            if ba.ifsc_code and not re.match(ifsc_pattern, ba.ifsc_code):
                results.append(_make(
                    "ITR1-R262", False,
                    f"Bank account #{i+1}: IFSC code '{ba.ifsc_code}' is invalid. "
                    f"Expected 11 characters: first 4 letters, 5th is 0, last 6 alphanumeric.",
                    f"bank_accounts[{i}].ifsc_code",
                ))
            from app.schemas.itr1 import BankAccountType
            valid_account_types = {account_type.value for account_type in BankAccountType}
            if ba.account_type not in valid_account_types:
                results.append(_make(
                    "ITR1-R263", False,
                    f"Bank account #{i+1}: account_type '{ba.account_type}' is invalid. "
                    f"Must be one of: {', '.join(sorted(valid_account_types))}.",
                    f"bank_accounts[{i}].account_type",
                ))

    # Rule 1: 80C+80CCC+80CCD(1) <= 1,50,000 (old regime)
    if is_old and pool_80c > 150_000:
        results.append(_make(
            "ITR1-R001", False,
            f"80C+80CCC+80CCD(1) total (Rs {pool_80c}) exceeds Rs 1,50,000 combined limit u/s 80CCE",
            "deductions_chapter6a", expected="<=150000", actual=str(pool_80c),
        ))

    # Rule 153: New regime 80C/80CCC/80CCD(1) must be 0
    if is_new and pool_80c > 0:
        results.append(_make(
            "ITR1-R153", False,
            f"New Tax Regime (115BAC) does not allow 80C/80CCC/80CCD(1). Claimed: Rs {pool_80c}",
            "deductions_chapter6a",
        ))

    # ========================================================================
    # SECTION: 80CCD(1B) Additional NPS
    # ========================================================================

    if ch6a:
        # Rule 115: 80CCD(1B) <= 50,000 (old regime)
        if is_old and ch6a.amount_80ccd1b > 50_000:
            results.append(_make(
                "ITR1-R115", False,
                f"80CCD(1B) deduction (Rs {ch6a.amount_80ccd1b}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ccd1b",
            ))

        # Rule 169: New regime 80CCD(1B) must be 0
        if is_new and ch6a.amount_80ccd1b > 0:
            results.append(_make(
                "ITR1-R169", False,
                f"New Tax Regime does not allow 80CCD(1B). Claimed: Rs {ch6a.amount_80ccd1b}",
                "deductions_chapter6a.amount_80ccd1b",
            ))

    # ========================================================================
    # SECTION: 80CCD(2) Employer NPS (mostly informational — no employer_category field)
    # ========================================================================

    if ch6a and ch6a.amount_80ccd2 > 0:
        emp = inp.nature_of_employment or ""

        # If nature_of_employment not set, flag it first
        if not emp:
            results.append(_make(
                "ITR1-R004", False,
                f"80CCD(2) claimed (Rs {ch6a.amount_80ccd2}) but nature of employment not "
                f"specified. Employer category determines 80CCD(2) limit.",
                "nature_of_employment",
            ))
        else:
            # Rule 116: Pensioners cannot claim 80CCD(2)
            if "pension" in emp.lower():
                results.append(_make(
                    "ITR1-R116", False,
                    f"80CCD(2) claimed (Rs {ch6a.amount_80ccd2}) but assessee is a pensioner "
                    f"({emp}). Pensioners cannot claim 80CCD(2) employer NPS contribution.",
                    "deductions_chapter6a.amount_80ccd2",
                ))

            # Rule 120: Old regime, CG/SG employer => 14% salary
            if is_old:
                is_cg_sg = any(kw in emp.lower() for kw in ("central", "state", "government"))
                if is_cg_sg:
                    max_ccd2 = sal.gross_salary * Decimal("0.14")
                    if ch6a.amount_80ccd2 > max_ccd2:
                        results.append(_make(
                            "ITR1-R120", False,
                            f"80CCD(2) for CG/SG employees limited to 14% of salary "
                            f"(Rs {max_ccd2}). Claimed: Rs {ch6a.amount_80ccd2}",
                            "deductions_chapter6a.amount_80ccd2",
                        ))
                    else:
                        results.append(_info(
                            "ITR1-R120",
                            f"80CCD(2) CG/SG employee: 14% salary limit (Rs {max_ccd2}). "
                            f"Claimed: Rs {ch6a.amount_80ccd2} is within limit.",
                            "deductions_chapter6a.amount_80ccd2",
                        ))
                else:
                    max_ccd2 = sal.gross_salary * Decimal("0.10")
                    if ch6a.amount_80ccd2 > max_ccd2:
                        results.append(_make(
                            "ITR1-R119", False,
                            f"80CCD(2) for non-CG/SG employees limited to 10% of salary "
                            f"(Rs {max_ccd2}). Claimed: Rs {ch6a.amount_80ccd2}",
                            "deductions_chapter6a.amount_80ccd2",
                        ))

            # Rule 216: New regime 80CCD(2) => 14% salary
            if is_new:
                max_ccd2_new = sal.gross_salary * Decimal("0.14")
                if ch6a.amount_80ccd2 > max_ccd2_new:
                    results.append(_make(
                        "ITR1-R216", False,
                        f"80CCD(2) in new regime limited to 14% of salary "
                        f"(Rs {max_ccd2_new}). Claimed: Rs {ch6a.amount_80ccd2}",
                        "deductions_chapter6a.amount_80ccd2",
                    ))
                else:
                    results.append(_info(
                        "ITR1-R216",
                        f"80CCD(2) new regime: 14% salary limit (Rs {max_ccd2_new}). "
                        f"Claimed: Rs {ch6a.amount_80ccd2} is within limit.",
                        "deductions_chapter6a.amount_80ccd2",
                    ))

    # Rule 3: 80CCD(1) <= 10% salary non-pensioner
    if ch6a and ch6a.amount_80ccd1 > 0 and is_old:
        emp = inp.nature_of_employment or ""
        if "pension" not in emp.lower():
            max_ccd1 = sal.gross_salary * Decimal("0.10")
            if ch6a.amount_80ccd1 > max_ccd1:
                results.append(_make(
                    "ITR1-R003", False,
                    f"80CCD(1) for non-pensioner employees limited to 10% of salary "
                    f"(Rs {max_ccd1}). Claimed: Rs {ch6a.amount_80ccd1}",
                    "deductions_chapter6a.amount_80ccd1",
                ))

    # Rule 2: 80CCD(1) pensioner <= 20% GTI (pre-check with estimated GTI)
    if ch6a and ch6a.amount_80ccd1 > 0 and is_old:
        emp = inp.nature_of_employment or ""
        if "pension" in emp.lower():
            # Estimate GTI as sum of income heads (actual GTI comes post-computation)
            estimated_gti = (sal.gross_salary - sal.standard_deduction_claimed - sal.professional_tax_paid
                             + osi.savings_bank_interest + osi.fixed_deposit_interest
                             + osi.dividend_income + osi.family_pension_received
                             + osi.interest_on_it_refund
                             - min(max(hp.home_loan_interest_paid, _z), Decimal("200000"))
                             + (cg.ltcg_112a if cg else _z))
            estimated_gti = max(_z, estimated_gti)
            max_ccd1_pensioner = estimated_gti * Decimal("0.20")
            if ch6a.amount_80ccd1 > max_ccd1_pensioner:
                results.append(_make(
                    "ITR1-R002", False,
                    f"80CCD(1) for pensioner limited to 20% of estimated GTI "
                    f"(~Rs {estimated_gti}) = Rs {max_ccd1_pensioner}. "
                    f"Claimed: Rs {ch6a.amount_80ccd1}",
                    "deductions_chapter6a.amount_80ccd1",
                ))

    # ========================================================================
    # SECTION: 80D Health Insurance
    # ========================================================================

    if ch6a:
        d_self = ch6a.amount_80d_self_family
        d_parents = ch6a.amount_80d_parents
        d_total = d_self + d_parents
        sd80d = inp.schedule_80d

        # With schedule_80d available, we can apply precise caps
        if sd80d:
            # Determine self/family cap based on senior citizen flag
            self_max = 50_000 if sd80d.has_self_senior else 25_000
            if is_old and d_self > self_max:
                results.append(_make(
                    "ITR1-R130" if sd80d.has_self_senior else "ITR1-R127", False,
                    f"80D Self/Family (Rs {d_self}) exceeds Rs {self_max:,} limit "
                    f"({'senior' if sd80d.has_self_senior else 'non-senior'} category)",
                    "deductions_chapter6a.amount_80d_self_family",
                ))

            # Determine parents cap based on senior citizen flag
            parents_max = 50_000 if sd80d.has_parents_senior else 25_000
            if is_old and d_parents > parents_max:
                results.append(_make(
                    "ITR1-R134" if sd80d.has_parents_senior else "ITR1-R132", False,
                    f"80D Parents (Rs {d_parents}) exceeds Rs {parents_max:,} limit "
                    f"({'senior' if sd80d.has_parents_senior else 'non-senior'} category)",
                    "deductions_chapter6a.amount_80d_parents",
                ))

            # Preventative health checkup <= 5,000 per group
            if sd80d.preventive_checkup_self > 5_000:
                results.append(_make(
                    "ITR1-R129", False,
                    f"Preventive health checkup for self/family (Rs {sd80d.preventive_checkup_self}) "
                    f"exceeds Rs 5,000 limit",
                    "schedule_80d.preventive_checkup_self",
                ))
            if sd80d.preventive_checkup_parents > 5_000:
                results.append(_make(
                    "ITR1-R129b", False,
                    f"Preventive health checkup for parents (Rs {sd80d.preventive_checkup_parents}) "
                    f"exceeds Rs 5,000 limit",
                    "schedule_80d.preventive_checkup_parents",
                ))

            # Rule 138: 80D in VIA must match Schedule 80D total
            sch_total = (sd80d.premium_1a_non_senior + sd80d.premium_1b_senior
                         + sd80d.premium_2a_parents_non_senior + sd80d.premium_2b_parents_senior
                         + sd80d.preventive_checkup_self + sd80d.preventive_checkup_parents)
            if is_old and d_total > 0 and d_total != sch_total:
                results.append(_make(
                    "ITR1-R138", False,
                    f"80D VIA total (Rs {d_total}) does not match Schedule 80D total "
                    f"(Rs {sch_total})",
                    "deductions_chapter6a",
                ))

            # ---- Per-policy enforcement (R128, R131, R133, R135, R137, R256-R259) ----
            if sd80d.policies:
                from collections import defaultdict
                section_sums: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
                for pol in sd80d.policies:
                    sec = pol.section
                    section_sums[sec] += pol.premium_paid

                    # Cash-mode premium not allowed (only preventive checkup in cash)
                    if pol.payment_mode_cash and pol.premium_paid > 0:
                        results.append(_make(
                            "ITR1-R137", False,
                            f"80D policy in section {sec}: premium of Rs {pol.premium_paid} "
                            f"paid in cash. Cash payments are NOT eligible for 80D deduction "
                            f"(only preventive health checkups up to ₹5,000 may be in cash).",
                            "schedule_80d.policies",
                        ))

                    # Insurer name + policy number required per CBDT R256-R259
                    if pol.premium_paid > 0 and (not pol.insurer_name or not pol.policy_number):
                        results.append(_make(
                            "ITR1-R256" if sec == "1a" else
                            "ITR1-R257" if sec == "1b" else
                            "ITR1-R258" if sec == "2a" else "ITR1-R259", False,
                            f"80D section {sec}: premium of Rs {pol.premium_paid} claimed "
                            f"but insurer name ('{pol.insurer_name}') or policy number "
                            f"('{pol.policy_number}') is missing.",
                            "schedule_80d.policies",
                        ))

                # R128: same as CBDT rule - 1a per-policy sum = Schedule 80D field
                if section_sums["1a"] != sd80d.premium_1a_non_senior and sd80d.premium_1a_non_senior > 0:
                    results.append(_make(
                        "ITR1-R128", False,
                        f"80D 1a: sum of per-policy premiums (Rs {section_sums['1a']}) "
                        f"!= Schedule 80D premium_1a_non_senior "
                        f"(Rs {sd80d.premium_1a_non_senior})",
                        "schedule_80d.premium_1a_non_senior",
                    ))
                if section_sums["1b"] != sd80d.premium_1b_senior and sd80d.premium_1b_senior > 0:
                    results.append(_make(
                        "ITR1-R131", False,
                        f"80D 1b: sum of per-policy premiums (Rs {section_sums['1b']}) "
                        f"!= Schedule 80D premium_1b_senior "
                        f"(Rs {sd80d.premium_1b_senior})",
                        "schedule_80d.premium_1b_senior",
                    ))
                if section_sums["2a"] != sd80d.premium_2a_parents_non_senior and sd80d.premium_2a_parents_non_senior > 0:
                    results.append(_make(
                        "ITR1-R133", False,
                        f"80D 2a: sum of per-policy premiums (Rs {section_sums['2a']}) "
                        f"!= Schedule 80D premium_2a_parents_non_senior "
                        f"(Rs {sd80d.premium_2a_parents_non_senior})",
                        "schedule_80d.premium_2a_parents_non_senior",
                    ))
                if section_sums["2b"] != sd80d.premium_2b_parents_senior and sd80d.premium_2b_parents_senior > 0:
                    results.append(_make(
                        "ITR1-R135", False,
                        f"80D 2b: sum of per-policy premiums (Rs {section_sums['2b']}) "
                        f"!= Schedule 80D premium_2b_parents_senior "
                        f"(Rs {sd80d.premium_2b_parents_senior})",
                        "schedule_80d.premium_2b_parents_senior",
                    ))

        else:
            # No schedule_80d provided — conservative caps
            if is_old and d_self > 50_000:
                results.append(_make(
                    "ITR1-R130", False,
                    f"80D Self/Family (Rs {d_self}) exceeds maximum Rs 50,000",
                    "deductions_chapter6a.amount_80d_self_family",
                ))
            if is_old and d_self > 25_000 and d_self <= 50_000:
                results.append(_info(
                    "ITR1-R127",
                    "80D Self/Family claimed between Rs 25,001-50,000 but no schedule_80d "
                    "provided. This is allowed only if self/family includes senior citizen(s).",
                    "deductions_chapter6a.amount_80d_self_family",
                ))

            if is_old and d_parents > 50_000:
                results.append(_make(
                    "ITR1-R134", False,
                    f"80D Parents (Rs {d_parents}) exceeds maximum Rs 50,000",
                    "deductions_chapter6a.amount_80d_parents",
                ))
            if is_old and d_parents > 25_000 and d_parents <= 50_000:
                results.append(_info(
                    "ITR1-R132",
                    "80D Parents claimed between Rs 25,001-50,000 but no schedule_80d "
                    "provided. This is allowed only if parents include senior citizen(s).",
                    "deductions_chapter6a.amount_80d_parents",
                ))

            # Rule 254: 80D claimed but schedule not provided
            if is_old and d_total > 0:
                results.append(_info(
                    "ITR1-R254",
                    "80D claimed. Schedule 80D details (insurer, policy numbers, "
                    "senior citizen flags) are required but not provided.",
                    "deductions_chapter6a",
                ))

        # Rule 136: 80D total <= 1,00,000
        max_80d = 100_000
        if d_total > max_80d:
            results.append(_make(
                "ITR1-R136", False,
                f"80D total (Self+Parents = Rs {d_total}) exceeds Rs 1,00,000 overall limit",
                "deductions_chapter6a",
            ))

        # Rule 173: New regime 80D must be 0
        if is_new and d_total > 0:
            results.append(_make(
                "ITR1-R173", False,
                f"New Tax Regime does not allow 80D. Claimed: Rs {d_total}",
                "deductions_chapter6a",
            ))

        # ====================================================================
        # R178-R183: 80D claiming-status dropdown logic
        # ====================================================================
        if sd80d:
            # R178: 1a (non-senior Self) only if has_self_senior == False
            if sd80d.has_self_senior and sd80d.premium_1a_non_senior > _z:
                results.append(_make(
                    "ITR1-R178", False,
                    f"80D Sl.1a (non-senior Self/Family) claimed Rs {sd80d.premium_1a_non_senior} "
                    f"but 'has_self_senior' is True. Use Sl.1b for senior citizen self/family.",
                    "schedule_80d.has_self_senior",
                ))
            # R179: 1b (senior Self) only if has_self_senior == True
            if not sd80d.has_self_senior and sd80d.premium_1b_senior > _z:
                results.append(_make(
                    "ITR1-R179", False,
                    f"80D Sl.1b (senior Self/Family) claimed Rs {sd80d.premium_1b_senior} "
                    f"but 'has_self_senior' is False. Use Sl.1a for non-senior self/family.",
                    "schedule_80d.has_self_senior",
                ))
            # R180: 2a (non-senior Parents) only if has_parents_senior == False
            if sd80d.has_parents_senior and sd80d.premium_2a_parents_non_senior > _z:
                results.append(_make(
                    "ITR1-R180", False,
                    f"80D Sl.2a (non-senior Parents) claimed Rs {sd80d.premium_2a_parents_non_senior} "
                    f"but 'has_parents_senior' is True. Use Sl.2b for senior citizen parents.",
                    "schedule_80d.has_parents_senior",
                ))
            # R181: 2b (senior Parents) only if has_parents_senior == True
            if not sd80d.has_parents_senior and sd80d.premium_2b_parents_senior > _z:
                results.append(_make(
                    "ITR1-R181", False,
                    f"80D Sl.2b (senior Parents) claimed Rs {sd80d.premium_2b_parents_senior} "
                    f"but 'has_parents_senior' is False. Use Sl.2a for non-senior parents.",
                    "schedule_80d.has_parents_senior",
                ))
            # R182: If dropdown is "Not claiming for Self/Family", 1a and 1b must both be 0
            if sd80d.not_claiming_self and (sd80d.premium_1a_non_senior > _z or sd80d.premium_1b_senior > _z):
                results.append(_make(
                    "ITR1-R182", False,
                    f"80D dropdown says 'Not claiming for Self/Family' but Sl.1a/1b has "
                    f"non-zero amounts (1a: {sd80d.premium_1a_non_senior}, 1b: {sd80d.premium_1b_senior})",
                    "schedule_80d",
                ))
            # R183: If dropdown is "Not claiming for Parents", 2a and 2b must both be 0
            if sd80d.not_claiming_parents and (sd80d.premium_2a_parents_non_senior > _z or sd80d.premium_2b_parents_senior > _z):
                results.append(_make(
                    "ITR1-R183", False,
                    f"80D dropdown says 'Not claiming for Parents' but Sl.2a/2b has "
                    f"non-zero amounts (2a: {sd80d.premium_2a_parents_non_senior}, 2b: {sd80d.premium_2b_parents_senior})",
                    "schedule_80d",
                ))

    # ========================================================================
    # SECTION: 80DDB Specified Diseases
    # ========================================================================

    if ch6a and ch6a.amount_80ddb > 0:
        details_80ddb = ch6a.details_80ddb
        # Rule 5/7: cap follows the treated person's official category.
        if details_80ddb is not None:
            is_80ddb_senior = (
                details_80ddb.user_type
                is Section80DDBUserType.SELF_OR_DEPENDENT_SENIOR
            )
            net_80ddb = max(
                _z,
                ch6a.amount_80ddb - details_80ddb.reimbursement_amount,
            )
        else:
            is_80ddb_senior = is_senior
            net_80ddb = ch6a.amount_80ddb
        cap_80ddb = (
            SECTION_80DDB_SENIOR_LIMIT
            if is_80ddb_senior
            else SECTION_80DDB_LIMIT
        )
        if is_old and net_80ddb > cap_80ddb:
            rule_id = "ITR1-R005d" if is_80ddb_senior else "ITR1-R007"
            results.append(_make(
                rule_id, False,
                f"80DDB net claim (Rs {net_80ddb}) exceeds Rs {cap_80ddb} maximum "
                "for the selected beneficiary category",
                "deductions_chapter6a.amount_80ddb",
                expected=f"<= {cap_80ddb}",
                actual=str(net_80ddb),
            ))

        # Rule 6: exact official beneficiary and disease details required.
        if details_80ddb is None:
            results.append(_make(
                "ITR1-R006", False,
                "80DDB deduction claimed but official beneficiary category and specified disease are missing.",
                "deductions_chapter6a.details_80ddb",
            ))
        elif details_80ddb.reimbursement_amount > ch6a.amount_80ddb:
            results.append(_make(
                "ITR1-R006b", False,
                "80DDB reimbursement cannot exceed gross treatment expenditure.",
                "deductions_chapter6a.details_80ddb.reimbursement_amount",
                expected=f"<= {ch6a.amount_80ddb}",
                actual=str(details_80ddb.reimbursement_amount),
            ))

    # Rule 155: New regime 80DDB must be 0
    if is_new and ch6a and ch6a.amount_80ddb > 0:
        results.append(_make(
            "ITR1-R155", False,
            f"New Tax Regime does not allow 80DDB. Claimed: Rs {ch6a.amount_80ddb}",
            "deductions_chapter6a.amount_80ddb",
        ))

    # ========================================================================
    # SECTION: 80G Donations
    # ========================================================================

    if ch6a:
        # Rule 8: 80G claimed but Schedule 80G not provided
        if is_old and ch6a.amount_80g > 0:
            if not ch6a.donations_80g or len(ch6a.donations_80g) == 0:
                results.append(_make(
                    "ITR1-R008", False,
                    "Schedule 80G details (donations_80g entries) are mandatory when "
                    "80G deduction is claimed",
                    "deductions_chapter6a.donations_80g",
                ))
            # Rule 88: Cash donation per donee PAN capped at Rs 2,000
            if ch6a.donations_80g:
                for i, d in enumerate(ch6a.donations_80g):
                    if d.cash_amount > 2_000:
                        results.append(_make(
                            "ITR1-R088", False,
                            f"80G donation entry #{i+1}: cash amount (Rs {d.cash_amount}) "
                            f"exceeds Rs 2,000 cap per donee PAN",
                            f"deductions_chapter6a.donations_80g[{i}].cash_amount",
                        ))
                # R088/R327: 80G per-PAN cash aggregation check
                # If multiple entries with same PAN, aggregate and check against Rs 2,000
                pan_cash: dict = {}
                for d in ch6a.donations_80g:
                    if d.donee_pan and d.cash_amount > _z:
                        pan_cash[d.donee_pan] = pan_cash.get(d.donee_pan, _z) + d.cash_amount
                for pan, total_cash in pan_cash.items():
                    if total_cash > 2_000:
                        results.append(_make(
                            "ITR1-R327", False,
                            f"80G: multiple cash donations to same PAN '{pan}' aggregate "
                            f"to Rs {total_cash}. Total cash donations per PAN cannot exceed "
                            f"Rs 2,000; the eligible amount will be restricted.",
                            "deductions_chapter6a.donations_80g",
                        ))
                    else:
                        # R327 alt: sum ≤ 2000 → eligible = min(2000, claimed)
                        results.append(_info(
                            "ITR1-R327", True,
                            f"80G: total cash donations to PAN '{pan}' sum to Rs {total_cash}, "
                            f"which is within Rs 2,000 limit. Eligible amount = min(Rs 2,000, claimed).",
                        ))
            # Rule 139: 80G eligible amount consistency check using schedule_80g
            if inp.schedule_80g:
                sg = inp.schedule_80g
                if sg.total_eligible_amount > ch6a.amount_80g:
                    results.append(_make(
                        "ITR1-R139", False,
                        f"80G Schedule eligible amount (Rs {sg.total_eligible_amount}) "
                        f"exceeds VIA claimed amount (Rs {ch6a.amount_80g})",
                        "deductions_chapter6a.amount_80g",
                    ))
            else:
                # No schedule_80g but donations list exists — informational
                results.append(_info(
                    "ITR1-R139",
                    "80G claimed with donation entries but no schedule_80g aggregate. "
                    "Engine will compute eligible amount from individual entries.",
                    "deductions_chapter6a.amount_80g",
                ))

        # Rule 156: New regime 80G must be 0
        if is_new and ch6a.amount_80g > 0:
            results.append(_make(
                "ITR1-R156", False,
                f"New Tax Regime does not allow 80G. Claimed: Rs {ch6a.amount_80g}",
                "deductions_chapter6a.amount_80g",
            ))

    # ========================================================================
    # SECTION: 80TTA / 80TTB Interest Deductions
    # ========================================================================

    if ch6a:
        # Rule 11: 80TTA max 10,000
        if ch6a.amount_80tta > 10_000:
            results.append(_make(
                "ITR1-R011", False,
                f"80TTA deduction (Rs {ch6a.amount_80tta}) exceeds Rs 10,000 limit",
                "deductions_chapter6a.amount_80tta",
            ))

        # Rule 13: 80TTA cannot be claimed by senior citizens
        if ch6a.amount_80tta > 0 and is_senior:
            results.append(_make(
                "ITR1-R013", False,
                "80TTA cannot be claimed by Senior Citizens (age >= 60). Use 80TTB instead",
                "deductions_chapter6a.amount_80tta",
            ))

        # Rule 12: 80TTA restricted to savings account interest — enforce cross-check
        if ch6a.amount_80tta > 0:
            savings_int = osi.savings_bank_interest if osi else _z
            if ch6a.amount_80tta > savings_int:
                results.append(_make(
                    "ITR1-R012", False,
                    f"80TTA deduction (Rs {ch6a.amount_80tta}) exceeds savings bank interest "
                    f"(Rs {savings_int}). 80TTA is restricted to savings account interest only.",
                    "deductions_chapter6a.amount_80tta",
                ))

        # Rule 14: 80TTB max 50,000
        if ch6a.amount_80ttb > 50_000:
            results.append(_make(
                "ITR1-R014", False,
                f"80TTB deduction (Rs {ch6a.amount_80ttb}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ttb",
            ))

        # Rule 15: 80TTB cannot be claimed by non-seniors
        if ch6a.amount_80ttb > 0 and not is_senior:
            results.append(_make(
                "ITR1-R015", False,
                "80TTB can only be claimed by Senior Citizens (age >= 60). Use 80TTA instead",
                "deductions_chapter6a.amount_80ttb",
            ))

        # Rule 16: 80TTB restricted to interest from OS — enforce cross-check
        if is_old and is_senior and ch6a.amount_80ttb > 0:
            # 80TTB is restricted to INTEREST income from deposits only.
            # Dividend income is NOT interest and should be excluded per CBDT rule 16.
            total_osi_interest = (
                osi.savings_bank_interest + osi.fixed_deposit_interest
            ) if osi else _z
            if ch6a.amount_80ttb > total_osi_interest:
                results.append(_make(
                    "ITR1-R016", False,
                    f"80TTB deduction (Rs {ch6a.amount_80ttb}) exceeds interest income from "
                    f"Other Sources (Rs {total_osi_interest}). 80TTB is restricted to deposit "
                    f"interest only.",
                    "deductions_chapter6a.amount_80ttb",
                ))

        # Rule 157: New regime 80TTA must be 0
        if is_new and ch6a.amount_80tta > 0:
            results.append(_make(
                "ITR1-R157", False,
                f"New Tax Regime does not allow 80TTA. Claimed: Rs {ch6a.amount_80tta}",
                "deductions_chapter6a.amount_80tta",
            ))

        # Rule 158: New regime 80TTB must be 0
        if is_new and ch6a.amount_80ttb > 0:
            results.append(_make(
                "ITR1-R158", False,
                f"New Tax Regime does not allow 80TTB. Claimed: Rs {ch6a.amount_80ttb}",
                "deductions_chapter6a.amount_80ttb",
            ))

    # ========================================================================
    # SECTION: 80DD / 80U / 80CCH (Disability & Agniveer)
    # ========================================================================

    if ch6a:
        # Rule 154: New regime 80DD must be 0
        if is_new and ch6a.amount_80dd > 0:
            results.append(_make(
                "ITR1-R154", False,
                f"New Tax Regime does not allow 80DD. Claimed: Rs {ch6a.amount_80dd}",
                "deductions_chapter6a.amount_80dd",
            ))

        # Rule 159: New regime 80U must be 0
        if is_new and ch6a.amount_80u > 0:
            results.append(_make(
                "ITR1-R159", False,
                f"New Tax Regime does not allow 80U. Claimed: Rs {ch6a.amount_80u}",
                "deductions_chapter6a.amount_80u",
            ))

        # Rule 200d: 80U — nature of disability required (still info, disability_type not in schema)
        if is_old and ch6a.amount_80u > 0:
            if not inp.form_10ia_filed:
                results.append(_make(
                    "ITR1-R200d", False,
                    "80U deduction claimed but Form 10-IA (disability certificate) not filed. "
                    "Form 10-IA is mandatory for 80U deduction.",
                    "deductions_chapter6a.amount_80u",
                ))
            if ch6a.amount_80u not in (75_000, 125_000):
                results.append(_make(
                    "ITR1-R200", False,
                    f"80U amount (Rs {ch6a.amount_80u}) must be exactly Rs 75,000 (disability) "
                    f"or Rs 1,25,000 (severe disability)",
                    "deductions_chapter6a.amount_80u",
                ))

        # Rule 203d: 80DD — nature of disability required
        if is_old and ch6a.amount_80dd > 0:
            if not inp.form_10ia_filed:
                results.append(_make(
                    "ITR1-R203d", False,
                    "80DD deduction claimed but Form 10-IA (disability certificate) not filed. "
                    "Form 10-IA is mandatory for 80DD deduction.",
                    "deductions_chapter6a.amount_80dd",
                ))
            if ch6a.amount_80dd not in (75_000, 125_000):
                results.append(_make(
                    "ITR1-R203", False,
                    f"80DD amount (Rs {ch6a.amount_80dd}) must be exactly Rs 75,000 (dependent "
                    f"with disability) or Rs 1,25,000 (dependent with severe disability)",
                    "deductions_chapter6a.amount_80dd",
                ))

        # Rule 186: 80CCH — enforce PRAN requirement and hard cap
        if ch6a.amount_80cch > 0:
            if not inp.pran_number:
                results.append(_make(
                    "ITR1-R186", False,
                    "80CCH Agniveer Corpus Fund claimed but PRAN number not provided. "
                    "PRAN is mandatory for 80CCH.",
                    "deductions_chapter6a.amount_80cch",
                ))
            if ch6a.amount_80cch > 288_000:
                results.append(_make(
                    "ITR1-R186h", False,
                    f"80CCH (Rs {ch6a.amount_80cch}) exceeds absolute maximum Rs 2,88,000",
                    "deductions_chapter6a.amount_80cch",
                ))
            # R186: 80CCH ≤ 46.2% of salary 17(1)
            if sal.gross_salary > _z:
                cch_limit = sal.gross_salary * Decimal("0.462")
                if ch6a.amount_80cch > cch_limit:
                    results.append(_make(
                        "ITR1-R186", False,
                        f"80CCH (Rs {ch6a.amount_80cch}) exceeds 46.2%% of salary 17(1) "
                        f"(Rs {sal.gross_salary}) = Rs {cch_limit}",
                        "deductions_chapter6a.amount_80cch",
                    ))
        # R187: 80CCH CG employee age 17-27 at joining
        if ch6a.amount_80cch > _z and inp.nature_of_employment:
            emp_lower = inp.nature_of_employment.lower()
            if "central government" not in emp_lower:
                results.append(_make(
                    "ITR1-R187", False,
                    f"80CCH Agniveer Corpus Fund claimed but assessee is not a Central "
                    f"Government employee (employment: '{inp.nature_of_employment}'). "
                    f"80CCH is only for Agniveer soldiers.",
                    "nature_of_employment",
                ))
            if inp.agniveer_date_of_joining:
                from datetime import date as dt_date
                age_years = (inp.agniveer_date_of_joining - date(2000, 1, 1)).days / 365.25
                if age_years < 17 or age_years > 27:
                    results.append(_make(
                        "ITR1-R187b", False,
                        f"80CCH: joining age ~{int(age_years)} years. "
                        f"Must be between 17 and 27 years at joining.",
                        "agniveer_date_of_joining",
                    ))

    # ========================================================================
    # SECTION: 80EE / 80EEA / 80EEB (Home Loan / EV Loan)
    # ========================================================================

    if ch6a:
        # Rule 121: 80EE max 50,000 (old regime)
        if is_old and ch6a.amount_80ee > 50_000:
            results.append(_make(
                "ITR1-R121", False,
                f"80EE deduction (Rs {ch6a.amount_80ee}) exceeds Rs 50,000 limit",
                "deductions_chapter6a.amount_80ee",
            ))

        # Rule 122: 80EEA max 1,50,000 (old regime)
        if is_old and ch6a.amount_80eea > 150_000:
            results.append(_make(
                "ITR1-R122", False,
                f"80EEA deduction (Rs {ch6a.amount_80eea}) exceeds Rs 1,50,000 limit",
                "deductions_chapter6a.amount_80eea",
            ))

        # Rule 123: 80EE and 80EEA mutual exclusion
        if ch6a.amount_80ee > 0 and ch6a.amount_80eea > 0:
            results.append(_make(
                "ITR1-R123", False,
                "Only one of 80EE or 80EEA can be claimed. Both are currently > 0",
                "deductions_chapter6a",
            ))

        # Rule 124: 80EEB max 1,50,000 (old regime)
        if is_old and ch6a.amount_80eeb > 150_000:
            results.append(_make(
                "ITR1-R124", False,
                f"80EEB deduction (Rs {ch6a.amount_80eeb}) exceeds Rs 1,50,000 limit",
                "deductions_chapter6a.amount_80eeb",
            ))

        # Rule 170: New regime 80EE must be 0
        if is_new and ch6a.amount_80ee > 0:
            results.append(_make(
                "ITR1-R170", False,
                f"New Tax Regime does not allow 80EE. Claimed: Rs {ch6a.amount_80ee}",
                "deductions_chapter6a.amount_80ee",
            ))

        # Rule 171: New regime 80EEA must be 0
        if is_new and ch6a.amount_80eea > 0:
            results.append(_make(
                "ITR1-R171", False,
                f"New Tax Regime does not allow 80EEA. Claimed: Rs {ch6a.amount_80eea}",
                "deductions_chapter6a.amount_80eea",
            ))

        # Rule 172: New regime 80EEB must be 0
        if is_new and ch6a.amount_80eeb > 0:
            results.append(_make(
                "ITR1-R172", False,
                f"New Tax Regime does not allow 80EEB. Claimed: Rs {ch6a.amount_80eeb}",
                "deductions_chapter6a.amount_80eeb",
            ))

        # 80EE loan sanction date 01-Apr-2016 to 31-Mar-2017
        if ch6a.amount_80ee > 0:
            if inp.loan_details_80ee:
                ld = inp.loan_details_80ee
                if ld.sanction_date:
                    if not (date(2016, 4, 1) <= ld.sanction_date <= date(2017, 3, 31)):
                        results.append(_make(
                            "ITR1-R225", False,
                            f"80EE loan sanction date ({ld.sanction_date}) not within "
                            f"01-Apr-2016 to 31-Mar-2017",
                            "loan_details_80ee.sanction_date",
                        ))
                if ld.loan_amount > 3_500_000:
                    results.append(_make(
                        "ITR1-R225b", False,
                        f"80EE loan amount (Rs {ld.loan_amount}) exceeds Rs 35,00,000 limit",
                        "loan_details_80ee.loan_amount",
                    ))
            else:
                results.append(_info(
                    "ITR1-R225",
                    "80EE claimed but loan_details_80ee not provided. "
                    "Loan sanction date (01-Apr-2016 to 31-Mar-2017) must be verified.",
                    "deductions_chapter6a.amount_80ee",
                ))

        if ch6a.amount_80eea > 0:
            if inp.loan_details_80eea:
                ld = inp.loan_details_80eea
                if ld.sanction_date:
                    if not (date(2019, 4, 1) <= ld.sanction_date <= date(2022, 3, 31)):
                        results.append(_make(
                            "ITR1-R228", False,
                            f"80EEA loan sanction date ({ld.sanction_date}) not within "
                            f"01-Apr-2019 to 31-Mar-2022",
                            "loan_details_80eea.sanction_date",
                        ))
                if ld.loan_amount > 4_500_000:
                    results.append(_make(
                        "ITR1-R228b", False,
                        f"80EEA loan amount (Rs {ld.loan_amount}) exceeds Rs 45,00,000 "
                        f"stamp duty value limit",
                        "loan_details_80eea.loan_amount",
                    ))
            else:
                results.append(_info(
                    "ITR1-R228",
                    "80EEA claimed but loan_details_80eea not provided. "
                    "Loan sanction date (01-Apr-2019 to 31-Mar-2022) must be verified.",
                    "deductions_chapter6a.amount_80eea",
                ))

        if ch6a.amount_80eeb > 0:
            if inp.loan_details_80eeb:
                ld = inp.loan_details_80eeb
                if ld.sanction_date:
                    if not (date(2019, 4, 1) <= ld.sanction_date <= date(2023, 3, 31)):
                        results.append(_make(
                            "ITR1-R231", False,
                            f"80EEB loan sanction date ({ld.sanction_date}) not within "
                            f"01-Apr-2019 to 31-Mar-2023",
                            "loan_details_80eeb.sanction_date",
                        ))
            else:
                results.append(_info(
                    "ITR1-R231",
                    "80EEB claimed but loan_details_80eeb not provided. "
                    "Loan sanction date (01-Apr-2019 to 31-Mar-2023) must be verified.",
                    "deductions_chapter6a.amount_80eeb",
                ))

    # ========================================================================
    # SECTION: 80GG (Rent Paid — No HRA)
    # ========================================================================

    if ch6a:
        # Rule 119: HRA + 80GG mutual exclusion
        if sal.hra_exempt_amount > 0 and ch6a.amount_80gg > 0:
            results.append(_make(
                "ITR1-R119", False,
                "80GG deduction cannot be claimed when HRA exemption u/s 10(13A) is claimed. "
                f"HRA exempt: Rs {sal.hra_exempt_amount}, 80GG claimed: Rs {ch6a.amount_80gg}",
                "deductions_chapter6a.amount_80gg",
            ))

    # ========================================================================
    # SECTION: New Regime — Comprehensive Deduction Restrictions (Rule 146)
    # ========================================================================

    if is_new and ch6a:
        disallowed_deductions: list[tuple[str, str, Decimal]] = [
            ("amount_80c", "80C", ch6a.amount_80c),
            ("amount_80ccc", "80CCC", ch6a.amount_80ccc),
            ("amount_80ccd1", "80CCD(1)", ch6a.amount_80ccd1),
            ("amount_80ccd1b", "80CCD(1B)", ch6a.amount_80ccd1b),
            ("amount_80d_self_family", "80D Self/Family", ch6a.amount_80d_self_family),
            ("amount_80d_parents", "80D Parents", ch6a.amount_80d_parents),
            ("amount_80dd", "80DD", ch6a.amount_80dd),
            ("amount_80ddb", "80DDB", ch6a.amount_80ddb),
            ("amount_80u", "80U", ch6a.amount_80u),
            ("amount_80tta", "80TTA", ch6a.amount_80tta),
            ("amount_80ttb", "80TTB", ch6a.amount_80ttb),
            ("amount_80e", "80E", ch6a.amount_80e),
            ("amount_80ee", "80EE", ch6a.amount_80ee),
            ("amount_80eea", "80EEA", ch6a.amount_80eea),
            ("amount_80eeb", "80EEB", ch6a.amount_80eeb),
            ("amount_80g", "80G", ch6a.amount_80g),
            ("amount_80gg", "80GG", ch6a.amount_80gg),
        ]
        for field, label, val in disallowed_deductions:
            if val > 0:
                results.append(_make(
                    "ITR1-R146", False,
                    f"New Tax Regime (115BAC) does not allow deduction u/s {label}. "
                    f"Claimed: Rs {val}",
                    f"deductions_chapter6a.{field}",
                ))

        # Rule 175: New regime 80GGA/80GGC must be 0
        if inp.schedule_80gga:
            if inp.schedule_80gga.total_claimed > 0:
                results.append(_make(
                    "ITR1-R175", False,
                    f"New Tax Regime does not allow 80GGA. "
                    f"Claimed: Rs {inp.schedule_80gga.total_claimed}",
                    "schedule_80gga.total_claimed",
                ))
        if inp.schedule_80ggc:
            if inp.schedule_80ggc.total_claimed > 0:
                results.append(_make(
                    "ITR1-R175b", False,
                    f"New Tax Regime does not allow 80GGC. "
                    f"Claimed: Rs {inp.schedule_80ggc.total_claimed}",
                    "schedule_80ggc.total_claimed",
                ))

    # ========================================================================
    # SECTION: New Regime — Salary & HP Restrictions
    # ========================================================================

    if is_new:
        # Rule 163: New regime entertainment allowance must be 0
        if sal.entertainment_allowance > 0:
            results.append(_make(
                "ITR1-R163", False,
                f"New Tax Regime does not allow entertainment allowance u/s 16(ii). "
                f"Claimed: Rs {sal.entertainment_allowance}",
                "salary_income.entertainment_allowance",
            ))

        # Rule 164: New regime LTA must be 0
        if sal.lta_exempt_amount > 0:
            results.append(_make(
                "ITR1-R164", False,
                f"New Tax Regime does not allow LTA exemption u/s 10(5). "
                f"Claimed: Rs {sal.lta_exempt_amount}",
                "salary_income.lta_exempt_amount",
            ))

        # Rule 165: New regime HRA must be 0
        if sal.hra_exempt_amount > 0:
            results.append(_make(
                "ITR1-R165", False,
                f"New Tax Regime does not allow HRA exemption u/s 10(13A). "
                f"Claimed: Rs {sal.hra_exempt_amount}",
                "salary_income.hra_exempt_amount",
            ))

        # Rule 168: New regime professional tax must be 0
        if sal.professional_tax_paid > 0:
            results.append(_make(
                "ITR1-R168", False,
                f"New Tax Regime does not allow professional tax u/s 16(iii). "
                f"Claimed: Rs {sal.professional_tax_paid}",
                "salary_income.professional_tax_paid",
            ))

        # Rule 162 / 253: New regime self-occupied interest must be 0
        if hp.property_type == PropertyType.SELF_OCCUPIED and hp.home_loan_interest_paid > 0:
            results.append(_make(
                "ITR1-R162", False,
                f"New Tax Regime does not allow interest on borrowed capital for self-occupied "
                f"property. Claimed: Rs {hp.home_loan_interest_paid}",
                "house_property_income.home_loan_interest_paid",
            ))

    # ========================================================================
    # SECTION: Old Regime — Salary Validations
    # ========================================================================

    if is_old:
        # Rule 58: Entertainment allowance only for government employees
        if sal.entertainment_allowance > 0 and not sal.is_government_employee:
            results.append(_make(
                "ITR1-R058", False,
                "Entertainment allowance u/s 16(ii) is only available to Government employees "
                "(Central/State Govts)",
                "salary_income.entertainment_allowance",
            ))

        # Rule 57: Entertainment allowance cap: min(5000, 1/5th salary) for govt employees
        if sal.entertainment_allowance > 0 and sal.is_government_employee:
            if sal.entertainment_allowance > 5_000:
                results.append(_make(
                    "ITR1-R057", False,
                    f"Entertainment allowance u/s 16(ii) capped at Rs 5,000. "
                    f"Claimed: Rs {sal.entertainment_allowance}",
                    "salary_income.entertainment_allowance",
                ))
            # One-fifth of salary check is informational (need to know exact 17(1) salary)
            one_fifth = sal.gross_salary / Decimal("5")
            if sal.entertainment_allowance > one_fifth:
                results.append(_info(
                    "ITR1-R057b",
                    f"Entertainment allowance (Rs {sal.entertainment_allowance}) exceeds "
                    f"1/5th of salary u/s 17(1) (Rs {one_fifth}). "
                    "Deduction is min(Rs 5,000, 1/5th salary). Engine will cap correctly.",
                    "salary_income.entertainment_allowance",
                ))

        # Rule 37: Professional tax <= 2,500
        if sal.professional_tax_paid > 2_500:
            results.append(_make(
                "ITR1-R037", False,
                f"Professional tax u/s 16(iii) cannot exceed Rs 2,500. "
                f"Claimed: Rs {sal.professional_tax_paid}",
                "salary_income.professional_tax_paid",
            ))

        # Rule 141: Standard deduction old regime <= 50,000
        sd = sal.standard_deduction_claimed
        if sd > 50_000:
            results.append(_make(
                "ITR1-R112", False,  # CBDT Sl 112: Standard deduction old regime ≤ 50,000
                f"Standard deduction in old regime (Rs {sd}) exceeds Rs 50,000 limit",
                "salary_income.standard_deduction_claimed",
            ))

        # Rule 74: HRA exemption <= 17(1) salary (informational — HRA engine computes this)
        if sal.hra_exempt_amount > 0 and sal.gross_salary > 0:
            if sal.hra_exempt_amount > sal.gross_salary:
                results.append(_make(
                    "ITR1-R074", False,
                    f"HRA exemption (Rs {sal.hra_exempt_amount}) exceeds salary u/s 17(1) "
                    f"(Rs {sal.gross_salary})",
                    "salary_income.hra_exempt_amount",
                ))

        # Rule 176: HRA — enforce 10(13A) breakdown if HRA details provided
        if sal.hra_exempt_amount > 0:
            if inp.hra_details:
                hd = inp.hra_details
                # HRA exempt cannot exceed actual HRA received
                if sal.hra_exempt_amount > hd.actual_hra_received:
                    results.append(_make(
                        "ITR1-R176", False,
                        f"HRA exemption claimed (Rs {sal.hra_exempt_amount}) exceeds actual "
                        f"HRA received (Rs {hd.actual_hra_received})",
                        "salary_income.hra_exempt_amount",
                    ))
                # HRA is least of 3 conditions: actual HRA received, 50/40% salary,
                # rent-paid-minus-10%
                rent_factor = hd.rent_paid - (hd.salary_for_hra * Decimal("0.10"))
                salary_factor = hd.salary_for_hra * (Decimal("0.50") if hd.is_metro_city else Decimal("0.40"))
                max_hra = min(hd.actual_hra_received, max(rent_factor, _z), salary_factor)
                if sal.hra_exempt_amount > max_hra:
                    results.append(_make(
                        "ITR1-R176", False,
                        f"HRA exemption claimed (Rs {sal.hra_exempt_amount}) exceeds the "
                        f"permissible limit (Rs {max_hra}) computed as least of: "
                        f"actual HRA received (Rs {hd.actual_hra_received}), "
                        f"{'40%' if hd.is_metro_city else '50%'} of salary (Rs {salary_factor}), "
                        f"and rent paid minus 10% salary (Rs {max(rent_factor, _z)})",
                        "salary_income.hra_exempt_amount",
                    ))

        # Rule 210: Nature of employment mandatory if salary > 0
        if sal.gross_salary > 0 and not inp.nature_of_employment:
            results.append(_make(
                "ITR1-R210", False,
                "Salary income is present but nature of employment is not specified. "
                "Nature of employment (Central Govt, State Govt, PSU, Private, Pensioner, etc.) "
                "is mandatory in ITR form.",
                "nature_of_employment",
            ))

    # ========================================================================
    # SECTION: New Regime — Standard Deduction Cap
    # ========================================================================

    if is_new:
        # Rule 215: Standard deduction new regime <= 75,000
        sd = sal.standard_deduction_claimed
        if sd > 75_000:
            results.append(_make(
                "ITR1-R215", False,
                f"Standard deduction in new regime (Rs {sd}) exceeds Rs 75,000 limit",
                "salary_income.standard_deduction_claimed",
            ))

    # ========================================================================
    # SECTION: House Property Validations
    # ========================================================================

    # Rule 45: Let-out / deemed let-out must have rent > 0
    if hp.property_type in (PropertyType.LET_OUT, PropertyType.DEEMED_LET_OUT):
        if hp.annual_rent_received <= 0:
            results.append(_make(
                "ITR1-R045", False,
                "Annual rent received must be greater than 0 for let-out or deemed let-out property",
                "house_property_income.annual_rent_received",
            ))

    # Rule 44: Municipal tax not allowed when rent is 0
    if hp.municipal_taxes_paid > 0 and hp.annual_rent_received <= 0:
        results.append(_make(
            "ITR1-R044", False,
            "Municipal taxes cannot be claimed when gross rent is 0 or nil",
            "house_property_income.municipal_taxes_paid",
        ))

    # Rule 49: Municipal tax not for self-occupied
    if hp.property_type == PropertyType.SELF_OCCUPIED and hp.municipal_taxes_paid > 0:
        results.append(_make(
            "ITR1-R049", False,
            "Municipal taxes cannot be deducted for self-occupied property",
            "house_property_income.municipal_taxes_paid",
        ))

    # Rule 48: Self-occupied interest <= 2,00,000 (old regime)
    if hp.property_type == PropertyType.SELF_OCCUPIED and is_old:
        if hp.home_loan_interest_paid > 200_000:
            results.append(_make(
                "ITR1-R048", False,
                f"Self-occupied property interest (Rs {hp.home_loan_interest_paid}) "
                f"exceeds Rs 2,00,000 cap u/s 24(b)",
                "house_property_income.home_loan_interest_paid",
            ))

    # ========================================================================
    # SECTION: LTCG 112A
    # ========================================================================

    if cg:
        # Rule 217: LTCG 112A <= 1,25,000
        if cg.ltcg_112a > 125_000:
            results.append(_make(
                "ITR1-R217", False,
                f"LTCG u/s 112A (Rs {cg.ltcg_112a}) exceeds Rs 1,25,000 limit for ITR-1. "
                f"File ITR-2 instead",
                "capital_gains.ltcg_112a",
            ))

        # Rule 218: LTCG 112A = Full Value of Consideration - Cost of Acquisition
        if inp.full_value_of_consideration and cg.cost_of_acquisition > _z:
            expected_ltcg = inp.full_value_of_consideration - cg.cost_of_acquisition
            if abs(cg.ltcg_112a - expected_ltcg) > Decimal("1"):
                results.append(_make(
                    "ITR1-R218", False,
                    f"LTCG u/s 112A (Rs {cg.ltcg_112a}) does not match "
                    f"Full Value of Consideration (Rs {inp.full_value_of_consideration}) - "
                    f"Cost of Acquisition (Rs {cg.cost_of_acquisition}) = Rs {expected_ltcg}",
                    "capital_gains",
                    expected=str(expected_ltcg), actual=str(cg.ltcg_112a)))
        elif cg.cost_of_acquisition > _z and not inp.full_value_of_consideration:
            results.append(_info(
                "ITR1-R218",
                "LTCG 112A: Cost of Acquisition provided but Full Value of Consideration "
                "not captured. LTCG = FV - COA validation skipped.",
                "capital_gains",
            ))

    # ========================================================================
    # SECTION: Other Sources Income — Dropdown + Cross-Foot (R050-R056)
    # ========================================================================

    # R050: "Interest from savings account" dropdown cannot be selected more than once
    # R051: "Interest from Deposits" dropdown cannot be selected more than once
    # R055: "Interest from IT Refund" dropdown cannot be selected more than once
    # R056: "Family pension" dropdown cannot be selected more than once
    # Covered generically by R184 catch-all, but here as individual rule numbers
    if inp.other_sources_dropdowns:
        os_dropdowns_seen: dict = {}
        for dd in inp.other_sources_dropdowns:
            if dd:
                os_dropdowns_seen[dd] = os_dropdowns_seen.get(dd, 0) + 1
        for dd_name, count in os_dropdowns_seen.items():
            if count > 1:
                results.append(_make(
                    "ITR1-R050", False,
                    f"Other Sources dropdown '{dd_name}' selected {count} times. "
                    f"Each nature of income can be selected only once.",
                    "other_sources_dropdowns",
                ))

    # R052: OS income = sum of individual columns (cross-foot)
    if osi:
        osi_sum = (osi.savings_bank_interest + osi.fixed_deposit_interest
                   + osi.dividend_income + osi.family_pension_received
                   + osi.interest_on_it_refund)
        if inp.other_sources_total and inp.other_sources_total > _z and osi_sum > _z:
            if abs(inp.other_sources_total - osi_sum) > Decimal("1"):
                results.append(_make(
                    "ITR1-R052", False,
                    f"Other Sources total income (Rs {inp.other_sources_total}) does not "
                    f"equal sum of individual columns: savings({osi.savings_bank_interest}) + "
                    f"FD({osi.fixed_deposit_interest}) + dividend({osi.dividend_income}) + "
                    f"family pension({osi.family_pension_received}) + IT refund({osi.interest_on_it_refund}) "
                    f"= Rs {osi_sum}",
                    "other_sources_income",
                ))

    # R145: Dividend income = sum of quarterly breakup
    if osi and osi.dividend_income > _z and inp.dividend_quarterly_breakdown:
        qbr = inp.dividend_quarterly_breakdown
        div_sum = (qbr.get("Q1", _z) + qbr.get("Q2", _z)
                   + qbr.get("Q3", _z) + qbr.get("Q4", _z))
        if div_sum > _z:
            if abs(osi.dividend_income - div_sum) > Decimal("1"):
                results.append(_make(
                    "ITR1-R145", False,
                    f"Dividend income (Rs {osi.dividend_income}) does not equal "
                    f"sum of quarterly breakup: Q1({qbr.get('Q1', 0)}) + Q2({qbr.get('Q2', 0)}) + "
                    f"Q3({qbr.get('Q3', 0)}) + Q4({qbr.get('Q4', 0)}) = Rs {div_sum}",
                    "dividend_quarterly_breakdown",
                ))
    elif osi and osi.dividend_income > _z and not inp.dividend_quarterly_breakdown:
        results.append(_make(
            "ITR1-R145", False,
            f"Dividend income (Rs {osi.dividend_income}) declared but quarterly "
            f"breakup not provided. CBDT requires quarterly breakup of dividend income.",
            "dividend_quarterly_breakdown",
        ))

    # ========================================================================
    # SECTION: TDS / TCS
    # ========================================================================

    tds1_total = sum(e.tds_deducted for e in (inp.tds1_entries or []))
    tds2_total = sum(e.tds_deducted for e in (inp.tds2_entries or []))
    tds3_total = sum(e.tds_deducted for e in (inp.tds3_entries or []))
    tcs_total = sum(e.tcs_collected for e in (inp.tcs_entries or []))
    total_tds = tds1_total + tds2_total + tds3_total

    if total_tds > 0:
        salary_has_income = sal.gross_salary > 0
        osi_has_income = (
            osi.savings_bank_interest > 0
            or osi.fixed_deposit_interest > 0
            or osi.family_pension_received > 0
            or osi.dividend_income > 0
        )
        has_cg = cg is not None and cg.ltcg_112a > 0

        # Rule 113: TDS claimed but corresponding income not offered
        if not (salary_has_income or osi_has_income or has_cg):
            results.append(_make(
                "ITR1-R113", True,  # Warning level — informational
                "TDS credit is claimed but no income appears to be offered to tax. "
                "Corresponding income must be disclosed in Salary, Other Sources, or "
                "Capital Gains schedule.",
                "tds1_entries / tds2_entries",
            ))

    # ========================================================================
    # SECTION: TDS/TCS Column Total Cross-Foot (R095-R103, R108-R111)
    # ========================================================================

    # R095: Schedule IT col 4 Total Tax Paid = sum of individual values
    tax_payments = inp.tax_payment_entries or []
    it_total_paid = sum(tp.amount for tp in tax_payments)
    if inp.schedule_it_total_paid and inp.schedule_it_total_paid > _z and it_total_paid > _z:
        if abs(inp.schedule_it_total_paid - it_total_paid) > Decimal("1"):
            results.append(_make(
                "ITR1-R095", False,
                f"Schedule IT: Total Tax Paid (Rs {inp.schedule_it_total_paid}) does not "
                f"equal sum of individual payment entries (Rs {it_total_paid})",
                "tax_payment_entries",
            ))

    # R096: TCS claimed ≤ Tax collected (per entry)
    for i, tcs_e in enumerate(inp.tcs_entries or []):
        if tcs_e.tcs_credit_claimed > tcs_e.tcs_collected:
            results.append(_make(
                "ITR1-R096", False,
                f"TCS entry #{i+1}: credit claimed (Rs {tcs_e.tcs_credit_claimed}) exceeds "
                f"tax collected (Rs {tcs_e.tcs_collected})",
                f"tcs_entries[{i}].tcs_credit_claimed",
            ))

    # R097: Schedule TCS col 6 total = sum of individual values
    tcs_claimed_sum = sum(
        e.tcs_credit_claimed for e in (inp.tcs_entries or [])
        if e.tcs_credit_claimed is not None
    )  # type: ignore[attr-defined]
    if inp.schedule_tcs_total_claimed and inp.schedule_tcs_total_claimed > _z and tcs_claimed_sum > _z:
        if abs(inp.schedule_tcs_total_claimed - tcs_claimed_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R097", False,
                f"Schedule TCS: total credit claimed (Rs {inp.schedule_tcs_total_claimed}) "
                f"does not equal sum of individual entries (Rs {tcs_claimed_sum})",
                "tcs_entries",
            ))

    # R098: TDS2 claimed per entry ≤ Tax deducted
    for i, e in enumerate(inp.tds2_entries or []):
        tds2_claimed = getattr(e, 'tds_claimed_this_year', None)
        if tds2_claimed and tds2_claimed > e.tds_deducted:
            results.append(_make(
                "ITR1-R098", False,
                f"TDS2 entry #{i+1}: TDS claimed (Rs {tds2_claimed}) exceeds "
                f"tax deducted (Rs {e.tds_deducted})",
                f"tds2_entries[{i}]",
            ))

    # R100: TDS1 col 5 Total Tax Deducted = sum of individual values
    if inp.schedule_tds1_total and inp.schedule_tds1_total > _z and tds1_total > _z:
        if abs(inp.schedule_tds1_total - tds1_total) > Decimal("1"):
            results.append(_make(
                "ITR1-R100", False,
                f"Schedule TDS1: declared total (Rs {inp.schedule_tds1_total}) does not "
                f"equal sum of individual TDS deducted values (Rs {tds1_total})",
                "tds1_entries",
            ))

    # R101: TDS2 col 6 total claimed = sum of individual values
    tds2_claimed_sum = sum(
        getattr(e, 'tds_claimed_this_year', _z)
        for e in (inp.tds2_entries or [])
    )
    if inp.schedule_tds2_total_claimed and inp.schedule_tds2_total_claimed > _z and tds2_claimed_sum > _z:
        if abs(inp.schedule_tds2_total_claimed - tds2_claimed_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R101", False,
                f"Schedule TDS2: declared total claimed (Rs {inp.schedule_tds2_total_claimed}) "
                f"does not equal sum of individual claims (Rs {tds2_claimed_sum})",
                "tds2_entries",
            ))

    # R102: TDS3 col 7 total claimed = sum of individual values
    tds3_claimed_sum = sum(
        getattr(e, 'tds_claimed_this_year', _z)
        for e in (inp.tds3_entries or [])
    )
    if inp.schedule_tds3_total_claimed and inp.schedule_tds3_total_claimed > _z and tds3_claimed_sum > _z:
        if abs(inp.schedule_tds3_total_claimed - tds3_claimed_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R102", False,
                f"Schedule TDS3: declared total claimed (Rs {inp.schedule_tds3_total_claimed}) "
                f"does not equal sum of individual claims (Rs {tds3_claimed_sum})",
                "tds3_entries",
            ))

    # R103: Total Tax Paid (IT + TDS1 + TDS2 + TCS) = details in each schedule
    total_from_schedules = it_total_paid + total_tds + tcs_total
    if inp.total_taxes_paid and inp.total_taxes_paid > _z and total_from_schedules > _z:
        if abs(inp.total_taxes_paid - total_from_schedules) > Decimal("1"):
            results.append(_make(
                "ITR1-R103", False,
                f"Total Taxes Paid (Rs {inp.total_taxes_paid}) does not equal "
                f"sum of IT ({it_total_paid}) + TDS1 ({tds1_total}) + TDS2 ({tds2_total}) "
                f"+ TDS3 ({tds3_total}) + TCS ({tcs_total}) = Rs {total_from_schedules}",
                "total_taxes_paid",
            ))

    # R108: Total TDS claimed = sum of TDS1 + TDS2 + TDS3
    if inp.total_tds_claimed and inp.total_tds_claimed > _z and total_tds > _z:
        if abs(inp.total_tds_claimed - total_tds) > Decimal("1"):
            results.append(_make(
                "ITR1-R108", False,
                f"Total TDS claimed (Rs {inp.total_tds_claimed}) does not equal "
                f"sum of TDS1 ({tds1_total}) + TDS2 ({tds2_total}) + TDS3 ({tds3_total}) = Rs {total_tds}",
                "total_tds_claimed",
            ))

    # R109: Total TCS claimed = sum of TCS schedule
    if inp.total_tcs_claimed and inp.total_tcs_claimed > _z and tcs_total > _z:
        if abs(inp.total_tcs_claimed - tcs_total) > Decimal("1"):
            results.append(_make(
                "ITR1-R109", False,
                f"Total TCS claimed (Rs {inp.total_tcs_claimed}) does not equal "
                f"sum of TCS entries (Rs {tcs_total})",
                "total_tcs_claimed",
            ))

    # R110: Advance Tax = sum of IT entries before 31/03 of PY
    # R111: Self-Assessment Tax = sum of IT entries after 31/03 of AY
    if inp.advance_tax_paid and inp.advance_tax_paid > _z:
        adv_from_entries = sum(
            tp.amount for tp in tax_payments
            if tp.payment_type == "advance" and tp.payment_date
            and tp.payment_date <= (inp.filing_date or date.today()).replace(month=3, day=31)
        )
        if adv_from_entries > _z:
            if abs(inp.advance_tax_paid - adv_from_entries) > Decimal("1"):
                results.append(_make(
                    "ITR1-R110", False,
                    f"Advance Tax declared (Rs {inp.advance_tax_paid}) does not equal "
                    f"sum of advance-tax payment entries (Rs {adv_from_entries})",
                    "advance_tax_paid",
                ))
    if inp.self_assessment_tax_paid and inp.self_assessment_tax_paid > _z:
        sa_from_entries = sum(
            tp.amount for tp in tax_payments
            if tp.payment_type == "self_assessment"
        )
        if sa_from_entries > _z:
            if abs(inp.self_assessment_tax_paid - sa_from_entries) > Decimal("1"):
                results.append(_make(
                    "ITR1-R111", False,
                    f"Self-Assessment Tax declared (Rs {inp.self_assessment_tax_paid}) "
                    f"does not equal sum of self-assessment entries (Rs {sa_from_entries})",
                    "self_assessment_tax_paid",
                ))

    # ========================================================================
    # SECTION: Filing & Regime
    # ========================================================================

    # Rule 151: Old Tax Regime cannot be selected after due date of filing
    if is_old and inp.filing_date and inp.due_date:
        if inp.filing_date > inp.due_date:
            results.append(_make(
                "ITR1-R151", False,
                f"Old Tax Regime cannot be selected after the due date of filing "
                f"({inp.due_date}). Filing date is {inp.filing_date}.",
                "tax_regime / filing_date",
            ))

    # Rule 189: Revised return u/s 139(5) where original was u/s 139(4) → old regime blocked
    if inp.filing_section and inp.original_filing_section:
        if inp.filing_section == "139(5)" and inp.original_filing_section == "139(4)":
            if is_old:
                results.append(_make(
                    "ITR1-R189", False,
                    "Revised return u/s 139(5) with original filed u/s 139(4) cannot select "
                    "Old Tax Regime",
                    "tax_regime",
                ))

    # Rule 190: Late filing regime block
    if inp.filing_section:
        if inp.filing_section != "139(1)":
            if inp.filing_date and inp.due_date:
                if inp.filing_date > inp.due_date:
                    results.append(_make(
                        "ITR1-R190", False,
                        f"Option to change tax regime not available for belated/revised returns "
                        f"(filing section: {inp.filing_section}, date: {inp.filing_date})",
                        "filing_section",
                    ))

    # ========================================================================
    # SECTION: Additional Active Validations (formerly informational)
    # ========================================================================

    # Rule 29: Agricultural income shown as exempt
    if inp.agriculture_income > 5_000:
        results.append(_make(
            "ITR1-R029", False,
            f"Agricultural income shown as exempt (Rs {inp.agriculture_income}) exceeds "
            f"Rs 5,000. Agricultural income above this threshold affects tax rate computation.",
            "agriculture_income",
        ))

    # Exempt income dropdown uniqueness checks
    if len(inp.exempt_income_dropdowns) != len(set(inp.exempt_income_dropdowns)):
        results.append(_make(
            "ITR1-R031", False,
            "Duplicate entries found in exempt income dropdown selections. "
            "Each exempt income category can be selected only once.",
            "exempt_income_dropdowns",
        ))

    # Exempt income breakdown vs dropdown consistency
    dropdown_to_expected = {
        "Agricultural Income": inp.agriculture_income,
        "HRA Exemption": sal.hra_exempt_amount,
        "LTA Exemption": sal.lta_exempt_amount,
    }
    for dropdown, expected_val in dropdown_to_expected.items():
        if dropdown in inp.exempt_income_dropdowns:
            actual = inp.exempt_income_breakdown.get(dropdown, _z)
            if actual != expected_val and expected_val > 0:
                results.append(_make(
                    "ITR1-R030b", False,
                    f"Exempt income dropdown '{dropdown}' selected but breakdown value "
                    f"(Rs {actual}) does not match expected (Rs {expected_val})",
                    "exempt_income_breakdown",
                ))

    # Rule 30: Exempt income total = sum of individual exempt income columns
    if inp.exempt_income_dropdowns:
        breakdown_sum = sum(
            v for k, v in inp.exempt_income_breakdown.items()
            if k in inp.exempt_income_dropdowns
        )
        total_in_dropdowns = len(inp.exempt_income_dropdowns)
        if total_in_dropdowns > 0 and breakdown_sum == _z:
            results.append(_make(
                "ITR1-R030", False,
                f"Exempt income dropdowns selected ({', '.join(inp.exempt_income_dropdowns)}) "
                f"but no corresponding exempt income breakdown values provided. "
                f"Sum of exempt income columns must equal total exempt income.",
                "exempt_income_breakdown",
            ))

    # Rule 125: Relief u/s 89 requires salary or family pension income
    if inp.form_10e_filed:
        has_salary = sal.gross_salary > _z
        has_family_pension = osi.family_pension_received > _z
        if not has_salary and not has_family_pension:
            results.append(_make(
                "ITR1-R125", False,
                "Form 10E filed for relief u/s 89, but neither salary income nor "
                "family pension is present. Relief u/s 89 is only applicable when "
                "salary or family pension arrears are received.",
                "form_10e_filed",
            ))

    # Rule 240: HP 24(b) interest consistency with loan schedule (per-loan)
    if hp.home_loan_interest_paid > _z and inp.loan_details_24b_list:
        total_loan_amount = sum(
            ld.loan_amount for ld in inp.loan_details_24b_list)
        total_interest = sum(
            ld.interest_paid_self_occupied + ld.interest_paid_let_out
            for ld in inp.loan_details_24b_list)
        if total_loan_amount > _z and hp.home_loan_interest_paid > total_loan_amount:
            results.append(_make(
                "ITR1-R240", False,
                f"Home loan interest claimed (Rs {hp.home_loan_interest_paid}) exceeds "
                f"total loan principal across all loans (Rs {total_loan_amount}). "
                f"Interest cannot exceed sanctioned loan amount.",
                "house_property_income.home_loan_interest_paid",
                expected=f"<= {total_loan_amount}", actual=str(hp.home_loan_interest_paid)))

    # ========================================================================
    # SECTION: Rules 220-231 — Loan Details Required for Schedules
    # ========================================================================

    # Rule 220: 24(b) claimed → loan details in schedule 24(b) required
    if hp.home_loan_interest_paid > _z and not inp.loan_details_24b_list:
        results.append(_make(
            "ITR1-R220", False,
            "Interest on borrowed capital claimed under 24(b) but loan details "
            "not provided in Schedule 24(b). Bank/lender details are mandatory.",
            "loan_details_24b_list",
        ))

    # Rule 225: 80EE claimed → loan details in schedule 80EE required
    if ch6a and ch6a.amount_80ee > _z and not inp.loan_details_80ee:
        results.append(_make(
            "ITR1-R225", False,
            "80EE deduction claimed but loan details not provided in schedule 80EE. "
            "Lender name, loan amount and sanction date are mandatory.",
            "loan_details_80ee",
        ))

    # Rule 228: 80EEA claimed → loan details in schedule 80EEA required
    if ch6a and ch6a.amount_80eea > _z and not inp.loan_details_80eea:
        results.append(_make(
            "ITR1-R228", False,
            "80EEA deduction claimed but loan details not provided in schedule 80EEA. "
            "Lender name, loan amount and sanction date are mandatory.",
            "loan_details_80eea",
        ))

    # Rule 231: 80EEB claimed → loan details in schedule 80EEB required
    if ch6a and ch6a.amount_80eeb > _z and not inp.loan_details_80eeb:
        results.append(_make(
            "ITR1-R231", False,
            "80EEB deduction claimed but loan details not provided in schedule 80EEB. "
            "Lender name, loan amount and sanction date are mandatory.",
            "loan_details_80eeb",
        ))

    # Rule 221: 80EE/80EEA can only be claimed when 24(b) limit is exhausted
    # (at least one of them and 24(b) both have values)
    if ch6a and (ch6a.amount_80ee > _z or ch6a.amount_80eea > _z):
        if hp.home_loan_interest_paid <= _z:
            results.append(_make(
                "ITR1-R221", False,
                f"80EE/80EEA deduction claimed (80EE={ch6a.amount_80ee}, "
                f"80EEA={ch6a.amount_80eea}) but no 24(b) interest reported. "
                f"80EE/80EEA are additional deductions over and above 24(b). "
                f"The 24(b) limit must be exhausted first.",
                "deductions_chapter6a",
                expected="24(b) interest > 0", actual="24(b) = 0"))

    # Rule 227: 80EE — max loan ≤ Rs 35 lakh
    if ch6a and ch6a.amount_80ee > _z and inp.loan_details_80ee:
        ld_80ee = inp.loan_details_80ee
        if ld_80ee.loan_amount and ld_80ee.loan_amount > 3_500_000:
            results.append(_make(
                "ITR1-R227", False,
                f"80EE deduction claimed but loan amount (Rs {ld_80ee.loan_amount}) "
                f"exceeds Rs 35 lakh limit. 80EE is only available for loans ≤ Rs 35 lakh.",
                "loan_details_80ee.loan_amount",
                expected="<= 35,00,000", actual=str(ld_80ee.loan_amount)))

    # Rule 229: 80EEA — stamp duty value ≤ Rs 45 lakh
    if ch6a and ch6a.amount_80eea > _z and inp.loan_details_80eea:
        ld_80eea = inp.loan_details_80eea
        if ld_80eea.loan_amount and ld_80eea.loan_amount > 4_500_000:
            results.append(_make(
                "ITR1-R229", False,
                f"80EEA deduction claimed but loan amount (Rs {ld_80eea.loan_amount}) "
                f"exceeds Rs 45 lakh stamp duty value limit. "
                f"80EEA is only available for residential property with "
                f"stamp duty value ≤ Rs 45 lakh.",
                "loan_details_80eea.loan_amount",
                expected="<= 45,00,000", actual=str(ld_80eea.loan_amount)))

    # Rule 252: 80EE loan sanction date 01.04.2016 – 31.03.2017
    if ch6a and ch6a.amount_80ee > _z and inp.loan_details_80ee:
        ld = inp.loan_details_80ee
        if ld.sanction_date:
            sd = ld.sanction_date
            if sd < date(2016, 4, 1) or sd > date(2017, 3, 31):
                results.append(_make(
                    "ITR1-R252", False,
                    f"80EE loan sanction date ({sd}) is outside the valid range: "
                    f"01.04.2016 to 31.03.2017.",
                    "loan_details_80ee.sanction_date",
                    expected="01.04.2016 - 31.03.2017", actual=str(sd)))

    # Rule 230: 80EEA loan sanction date 01.04.2019 – 31.03.2022
    if ch6a and ch6a.amount_80eea > _z and inp.loan_details_80eea:
        ld = inp.loan_details_80eea
        if ld.sanction_date:
            sd = ld.sanction_date
            if sd < date(2019, 4, 1) or sd > date(2022, 3, 31):
                results.append(_make(
                    "ITR1-R230", False,
                    f"80EEA loan sanction date ({sd}) is outside the valid range: "
                    f"01.04.2019 to 31.03.2022.",
                    "loan_details_80eea.sanction_date",
                    expected="01.04.2019 - 31.03.2022", actual=str(sd)))

    # Rule 232: 80EEB loan sanction date 01.04.2019 – 31.03.2023
    if ch6a and ch6a.amount_80eeb > _z and inp.loan_details_80eeb:
        ld = inp.loan_details_80eeb
        if ld.sanction_date:
            sd = ld.sanction_date
            if sd < date(2019, 4, 1) or sd > date(2023, 3, 31):
                results.append(_make(
                    "ITR1-R232", False,
                    f"80EEB loan sanction date ({sd}) is outside the valid range: "
                    f"01.04.2019 to 31.03.2023.",
                    "loan_details_80eeb.sanction_date",
                    expected="01.04.2019 - 31.03.2023", actual=str(sd)))

    # Rule 271: Property type mandatory if 24(b) interest claimed
    if hp.home_loan_interest_paid > _z and not hp.property_type:
        results.append(_make(
            "ITR1-R271", False,
            "Interest on borrowed capital u/s 24(b) is claimed but no property type "
            "selected. Property type (self-occupied / let-out / deemed let-out) is mandatory.",
            "house_property_income.property_type",
        ))

    # ========================================================================
    # SECTION: Schedule 80GGA — Scientific Research/Rural Development Donations
    # (Rules 89-94, 118, 143-144)
    # ========================================================================

    if inp.schedule_80gga:
        sgga = inp.schedule_80gga

        # Rule 89: 80GGA donation — cash or non-cash must be entered
        if sgga.total_claimed > _z and sgga.cash_donations == _z and sgga.non_cash_donations == _z:
            results.append(_make(
                "ITR1-R089", False,
                "80GGA deduction claimed but neither cash nor non-cash donation "
                "amount provided in Schedule 80GGA.",
                "schedule_80gga",
            ))

        # Rule 90: Total donation = cash + non-cash
        expected_80gga = sgga.cash_donations + sgga.non_cash_donations
        if sgga.total_claimed > _z and sgga.total_claimed != expected_80gga:
            results.append(_make(
                "ITR1-R090", False,
                f"Schedule 80GGA total donation (Rs {sgga.total_claimed}) does not equal "
                f"sum of cash (Rs {sgga.cash_donations}) + non-cash (Rs {sgga.non_cash_donations}) = "
                f"Rs {expected_80gga}",
                "schedule_80gga",
                expected=str(expected_80gga), actual=str(sgga.total_claimed)))

        # Rule 94: Donee PAN in 80GGA cannot be same as assessee PAN or verification PAN
        for pan in sgga.donee_pan_list:
            if pan:
                # Check against a representative PAN if available
                pass  # Schema doesn't store assessee PAN; informational

    # Rule 143: 80GGA cash donations above Rs 2,000 not allowed
    if inp.schedule_80gga and inp.schedule_80gga.cash_donations > 2_000:
        results.append(_make(
            "ITR1-R143", False,
            f"Schedule 80GGA cash donation (Rs {inp.schedule_80gga.cash_donations}) "
            f"exceeds Rs 2,000. Cash donations above Rs 2,000 are not deductible u/s 80GGA.",
            "schedule_80gga.cash_donations",
        ))

    # Rule 144: 80GGA same Donee PAN not repeated
    if inp.schedule_80gga and inp.schedule_80gga.donee_pan_list:
        pans = inp.schedule_80gga.donee_pan_list
        seen = set()
        dups = set(p for p in pans if p and (p in seen or seen.add(p)))
        if dups:
            results.append(_make(
                "ITR1-R144", False,
                f"Schedule 80GGA: duplicate Donee PAN(s) detected: {', '.join(sorted(dups))}. "
                f"Each Donee PAN can appear only once in the schedule.",
                "schedule_80gga.donee_pan_list",
            ))

    # ========================================================================
    # SECTION: Schedule 80GGC — Political Contributions (Rules 195-199, 329)
    # ========================================================================

    if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > 0:
        sggc = inp.schedule_80ggc

        # Rule 195: Total = cash + non-cash (80GGC is only non-cash)
        if sggc.total_claimed != sggc.non_cash_contributions:
            results.append(_make(
                "ITR1-R195", False,
                f"Schedule 80GGC total (Rs {sggc.total_claimed}) does not equal "
                f"non-cash contributions (Rs {sggc.non_cash_contributions}). "
                f"80GGC is only for non-cash (cheque/draft/ECS) contributions.",
                "schedule_80ggc",
                expected=str(sggc.non_cash_contributions), actual=str(sggc.total_claimed)))

        # Rule 329: Political party name and PAN required for 80GGC
        if not sggc.political_party_name or not sggc.political_party_pan:
            results.append(_make(
                "ITR1-R329", False,
                "Schedule 80GGC: name and PAN of the political party / electoral trust "
                "are mandatory for claiming deduction u/s 80GGC.",
                "schedule_80ggc",
            ))

    # ========================================================================
    # SECTION: Schedule 80G — IFSC & Transaction Ref for Non-Cash Donations
    # (Rules 325-326, 330)
    # ========================================================================

    if inp.schedule_80g:
        for i, d in enumerate(inp.schedule_80g.donations):
            # Rule 330: Either cash or non-cash (not both over 0 for same row)
            if d.cash_amount > _z and d.non_cash_amount > _z:
                results.append(_make(
                    "ITR1-R330", False,
                    f"Schedule 80G row {i+1}: both cash (Rs {d.cash_amount}) and non-cash "
                    f"(Rs {d.non_cash_amount}) entered. Each donation row must be either "
                    f"cash or non-cash, not both.",
                    f"schedule_80g.donations[{i}]",
                ))
            # Rules 325-326: Non-cash donations need IFSC + transaction ref
            if d.non_cash_amount > _z:
                if not d.ifsc_code:
                    results.append(_make(
                        "ITR1-R325", False,
                        f"Schedule 80G row {i+1}: non-cash donation of Rs {d.non_cash_amount} "
                        f"but IFSC code not provided. IFSC code is mandatory for "
                        f"non-cash donations (NEFT/RTGS/IMPS/UPI).",
                        f"schedule_80g.donations[{i}].ifsc_code",
                    ))
                if not d.transaction_ref:
                    results.append(_make(
                        "ITR1-R326", False,
                        f"Schedule 80G row {i+1}: non-cash donation of Rs {d.non_cash_amount} "
                        f"but transaction reference number not provided. "
                        f"UPI ref / cheque no / IMPS/NEFT/RTGS ref is mandatory.",
                        f"schedule_80g.donations[{i}].transaction_ref",
                    ))

    # ========================================================================
    # SECTION: Schedule 80C — Cross-Schedule Consistency (Rules 224, 241, 247)
    # ========================================================================

    if ch6a and ch6a.amount_80c > _z and inp.schedule_80c_entries:
        total_80c_schedule = sum(e.amount for e in inp.schedule_80c_entries)
        # Rule 247: Sum of 80C payment rows = Total of Payments in Schedule 80C
        if total_80c_schedule > _z and ch6a.amount_80c != total_80c_schedule:
            results.append(_make(
                "ITR1-R241", False,  # CBDT Sl 241: 80C VIA = Schedule 80C total
                f"80C VIA amount (Rs {ch6a.amount_80c}) does not match schedule 80C "
                f"total (Rs {total_80c_schedule}). Both must be equal.",
                "deductions_chapter6a.amount_80c",
                expected=str(total_80c_schedule), actual=str(ch6a.amount_80c)))

        # Rule 224: Each 80C entry must have identifier details
        for i, e in enumerate(inp.schedule_80c_entries):
            if e.amount > _z:
                if not e.payment_type:
                    results.append(_make(
                        "ITR1-R224", False,
                        f"Schedule 80C row {i+1}: amount of Rs {e.amount} entered but "
                        f"payment type (LIC/PPF/ELSS/EPF/tuition etc.) not specified.",
                        f"schedule_80c_entries[{i}].payment_type",
                    ))
                if not e.identifier_number:
                    results.append(_make(
                        "ITR1-R224b", False,
                        f"Schedule 80C row {i+1}: identifier number (policy/folio/PRAN) "
                        f"required for the investment/payment of Rs {e.amount}.",
                        f"schedule_80c_entries[{i}].identifier_number",
                    ))

    # ========================================================================
    # SECTION: Schedule 80CCC — Per-Row Validation (Rules 302, 337)
    # ========================================================================

    if ch6a and ch6a.amount_80ccc > _z:
        total_80ccc_schedule = sum(e.amount for e in inp.schedule_80ccc_entries)
        # Rule 302: Sum of 80CCC rows = VIA amount
        if inp.schedule_80ccc_entries and total_80ccc_schedule > _z:
            if ch6a.amount_80ccc != total_80ccc_schedule:
                results.append(_make(
                    "ITR1-R302", False,
                    f"80CCC VIA amount (Rs {ch6a.amount_80ccc}) does not match "
                    f"schedule 80CCC total (Rs {total_80ccc_schedule}). Both must be equal.",
                    "deductions_chapter6a.amount_80ccc",
                    expected=str(total_80ccc_schedule), actual=str(ch6a.amount_80ccc)))

        # Rule 337: 80CCC > 0 → at least one row with identifier details required
        if not inp.schedule_80ccc_entries:
            results.append(_make(
                "ITR1-R337", False,
                "80CCC deduction claimed (Rs {ch6a.amount_80ccc}) but no row details "
                "provided in Schedule 80CCC. Insurer name, policy number and amount "
                "are mandatory.",
                "deductions_chapter6a.amount_80ccc"))
        else:
            for i, e in enumerate(inp.schedule_80ccc_entries):
                if e.amount > _z and (not e.insurer_name or not e.policy_number):
                    results.append(_make(
                        "ITR1-R337b", False,
                        f"Schedule 80CCC row {i+1}: amount of Rs {e.amount} entered but "
                        f"insurer name and/or policy number missing.",
                        f"schedule_80ccc_entries[{i}]",
                    ))

    # ========================================================================
    # SECTION: Schedule 80E — Education Loan Cross-Schedule (Rules 242, 248)
    # ========================================================================

    if ch6a and ch6a.amount_80e > _z:
        total_80e_schedule = sum(e.interest_paid for e in inp.schedule_80e_entries)
        if inp.schedule_80e_entries:
            # Rule 242: VIA 80E = total interest in schedule 80E
            if total_80e_schedule > _z and ch6a.amount_80e != total_80e_schedule:
                results.append(_make(
                    "ITR1-R242", False,
                    f"80E VIA amount (Rs {ch6a.amount_80e}) does not match "
                    f"Schedule 80E total interest (Rs {total_80e_schedule}). "
                    f"Both must be equal.",
                    "deductions_chapter6a.amount_80e",
                    expected=str(total_80e_schedule), actual=str(ch6a.amount_80e)))

        # Rule 274: 80E claimed → loan details required
        if not inp.schedule_80e_entries:
            results.append(_make(
                "ITR1-R274", False,
                f"80E deduction claimed (Rs {ch6a.amount_80e}) but no education loan "
                f"details provided in Schedule 80E. Lender name, loan amount and "
                f"interest paid are mandatory.",
                "deductions_chapter6a.amount_80e"))

    # ========================================================================
    # SECTION: Rules 250-251 — 80DD/80U > 0 → Form 10-IA Details Required
    # ========================================================================

    if ch6a and ch6a.amount_80dd > _z:
        if not inp.form_10ia_filed:
            results.append(_make(
                "ITR1-R238", False,
                "80DD deduction claimed (Rs {ch6a.amount_80dd}) but Form 10-IA not filed. "
                "Form 10-IA (medical certificate) is mandatory for 80DD/80U deductions.",
                "form_10ia_filed"))

    if ch6a and ch6a.amount_80u > _z:
        if not inp.form_10ia_filed:
            results.append(_make(
                "ITR1-R238b", False,
                "80U deduction claimed (Rs {ch6a.amount_80u}) but Form 10-IA not filed. "
                "Form 10-IA (medical certificate) is mandatory for 80DD/80U deductions.",
                "form_10ia_filed"))

    # Rule 233: 80GG requires Form 10BA
    if ch6a and ch6a.amount_80gg > _z and not inp.form_10ba_filed:
        results.append(_make(
            "ITR1-R233", False,
            "80GG deduction claimed but Form 10BA (declaration) not filed. "
            "Form 10BA is mandatory for claiming 80GG deduction.",
            "form_10ba_filed",
        ))

    # ========================================================================
    # SECTION: PRAN Rules (Rules 226, 335)
    # ========================================================================

    pran = inp.pran_number
    if pran:
        # Rule 335: PRAN entered but 80CCD(1) and 80CCD(1B) both zero
        if ch6a and ch6a.amount_80ccd1 == _z and ch6a.amount_80ccd1b == _z:
            results.append(_make(
                "ITR1-R335", False,
                f"PRAN number ({pran}) is provided but neither 80CCD(1) nor 80CCD(1B) "
                f"deduction is claimed. PRAN is only required when contributing to NPS.",
                "pran_number",
            ))

    # Rule 226: 80CCD(1) or 80CCD(1B) claimed but PRAN not provided
    if ch6a and (ch6a.amount_80ccd1 > _z or ch6a.amount_80ccd1b > _z) and not pran:
        results.append(_make(
            "ITR1-R226", False,
            f"80CCD(1)/80CCD(1B) deduction claimed (80CCD1={ch6a.amount_80ccd1}, "
            f"80CCD1B={ch6a.amount_80ccd1b}) but PRAN number not provided. "
            f"PRAN is mandatory for NPS deductions.",
            "pran_number",
        ))

    # ========================================================================
    # SECTION: Rule 77 — Exempt Allowance Cross-Foot (Salary)
    # ========================================================================
    # Total exempt allowances in salary should equal sum of individual exempt items.

    if sal:
        exempt_items = [
            ("LTA", sal.lta_exempt_amount),
            ("HRA", sal.hra_exempt_amount),
            ("Gratuity", sal.gratuity_received),
            ("Commuted Pension", sal.commuted_pension_received),
            ("Leave Encashment", sal.leave_encashment_received),
            ("VRS", sal.vrs_compensation),
            ("Retrenchment", sal.retrenchment_compensation),
            ("Transport", sal.transport_allowance),
        ]
        total_exempt_sum = sum(amt for _, amt in exempt_items)
        # We check if total_exempt is in exempt_income_breakdown
        exempt_total_key = "Total Exempt u/s 10"
        decl_total = inp.exempt_income_breakdown.get(exempt_total_key, _z)
        if decl_total > _z and total_exempt_sum > _z:
            if not (abs(decl_total - total_exempt_sum) <= Decimal("1")):
                results.append(_make(
                    "ITR1-R077", False,
                    f"Total exempt allowances u/s 10 (Rs {decl_total}) does not match "
                    f"sum of individual items (Rs {total_exempt_sum}). "
                    f"Sum = LTA({sal.lta_exempt_amount}) + HRA({sal.hra_exempt_amount}) + "
                    f"Gratuity({sal.gratuity_received}) + CommPension({sal.commuted_pension_received}) + "
                    f"LeaveEncash({sal.leave_encashment_received}) + VRS({sal.vrs_compensation}) + "
                    f"Retrench({sal.retrenchment_compensation}) + Transport({sal.transport_allowance})",
                    "salary_income",
                    expected=str(total_exempt_sum), actual=str(decl_total)))

    # Rule 213: Each exempt allowance section disclosed once per dropdown
    # (already enforced per-section via R031-R042; this is informational for the whole set)
    if inp.exempt_income_dropdowns:
        seen = set()
        dups = [d for d in inp.exempt_income_dropdowns if d and (d in seen or seen.add(d))]
        if dups:
            results.append(_make(
                "ITR1-R213", False,
                f"Duplicate exempt allowance dropdown selections: {', '.join(dups)}. "
                f"Each section 10 exemption can only be selected once.",
                "exempt_income_dropdowns",
            ))

    # Rule 184: General exempt income dropdown uniqueness (catch-all)
    if inp.exempt_income_dropdowns:
        seen_all = {}
        for d in inp.exempt_income_dropdowns:
            if d in seen_all:
                results.append(_make(
                    "ITR1-R184", False,
                    f"Exempt income dropdown '{d}' selected more than once. "
                    f"Each nature of exempt income can be selected only once.",
                    "exempt_income_dropdowns",
                ))
                break
            seen_all[d] = True

    # ========================================================================
    # SECTION: Schedule 80D Policy-Level Validation (Rules 234-239, 256-259)
    # ========================================================================

    if inp.schedule_80d and inp.schedule_80d.policies:
        sd = inp.schedule_80d
        for i, pol in enumerate(sd.policies):
            # Per-policy premium must be ≤ sum of all premiums + preventive checkup
            # Rules 256-259: each sub-section's policies need insurer + policy number
            if pol.premium_paid > _z:
                if not pol.insurer_name:
                    results.append(_make(
                        "ITR1-R256", False,
                        f"Schedule 80D policy {i+1}: premium of Rs {pol.premium_paid} but "
                        f"insurer name not provided. Insurer name is mandatory.",
                        f"schedule_80d.policies[{i}].insurer_name",
                    ))
                if not pol.policy_number:
                    results.append(_make(
                        "ITR1-R257", False,
                        f"Schedule 80D policy {i+1}: premium of Rs {pol.premium_paid} but "
                        f"policy number not provided. Policy number is mandatory.",
                        f"schedule_80d.policies[{i}].policy_number",
                    ))
                # Cash payment for health insurance premium not allowed
                if pol.payment_mode_cash:
                    results.append(_make(
                        "ITR1-R258", False,
                        f"Schedule 80D policy {i+1}: premium of Rs {pol.premium_paid} "
                        f"paid in cash. Health insurance premiums must be paid via "
                        f"non-cash mode for 80D deduction.",
                        f"schedule_80d.policies[{i}].payment_mode_cash",
                    ))

    # ========================================================================
    # SECTION: Rules 255 — New Regime: Prohibited Schedules Filled
    # ========================================================================

    if is_new:
        prohibited_schedules = []
        if inp.schedule_80c_entries:
            prohibited_schedules.append("80C")
        if inp.schedule_80ccc_entries:
            prohibited_schedules.append("80CCC")
        if inp.schedule_80e_entries:
            prohibited_schedules.append("80E")
        if inp.schedule_80g and inp.schedule_80g.donations:
            prohibited_schedules.append("80G")
        if inp.schedule_80gga:
            prohibited_schedules.append("80GGA")
        if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > 0:
            prohibited_schedules.append("80GGC")
        if inp.schedule_80d and inp.schedule_80d.policies:
            prohibited_schedules.append("80D")
        if inp.hra_details:
            prohibited_schedules.append("10(13A)")
        if inp.loan_details_80ee:
            prohibited_schedules.append("80EE")
        if inp.loan_details_80eea:
            prohibited_schedules.append("80EEA")
        if inp.loan_details_80eeb:
            prohibited_schedules.append("80EEB")

        if prohibited_schedules:
            results.append(_make(
                "ITR1-R255", False,
                f"New tax regime selected but schedule(s) filled that are not "
                f"allowed under section 115BAC: {', '.join(prohibited_schedules)}. "
                f"These deductions/schedules are not available in the new regime.",
                "tax_regime",
            ))

    # ========================================================================
    # SECTION: Rules 332-334, 296, 300 — Co-Ownership Consistency
    # ========================================================================

    if inp.is_property_co_owned:
        # Rule 332: Assessee share must be < 100% when co-owned
        if inp.co_ownership_details:
            if inp.co_ownership_details.ownership_percentage >= 100:
                results.append(_make(
                    "ITR1-R332", False,
                    f"Property is co-owned but assessee's ownership percentage "
                    f"({inp.co_ownership_details.ownership_percentage}%) is not less than 100%. "
                    f"Co-owned property requires partial ownership.",
                    "co_ownership_details.ownership_percentage",
                ))

        # Rule 333: Other co-owner share must be > 0% and < 100%
        if inp.other_co_owner_percentage <= _z or inp.other_co_owner_percentage >= 100:
            results.append(_make(
                "ITR1-R333", False,
                f"Other co-owner's percentage ({inp.other_co_owner_percentage}%) "
                f"must be between 0% and 100% (exclusive).",
                "other_co_owner_percentage",
            ))

    # Rule 334: If not co-owned, assessee share = 100%
    if not inp.is_property_co_owned and inp.co_ownership_details:
        if inp.co_ownership_details.ownership_percentage < 100:
            results.append(_make(
                "ITR1-R334", False,
                f"Property is not co-owned but assessee's ownership percentage "
                f"is {inp.co_ownership_details.ownership_percentage}%. "
                f"Sole ownership requires 100% share.",
                "co_ownership_details.ownership_percentage",
            ))

    # Rule 300: Assessee PAN and co-owner PAN cannot be the same
    # (Informational — schema doesn't store assessee PAN; portal-level check)

    # ========================================================================
    # SECTION: Rules 272-291 — Eligible Deduction ≤ User-Entered Amount
    # ========================================================================
    # These are informational at the input level — the computation engine
    # calculates the actual eligible amount and cross-validates in calc_rules.py.
    # We mark them as informational here to close the schema gap.

    results.append(_info(
        "ITR1-R272-291",
        "Eligible deduction amounts (80C-80U) are computed by the engine and "
        "validated against user-entered amounts in calc_rules.py. "
        "The engine enforces that no eligible amount exceeds what the user entered.",
    ))

    # ========================================================================
    # SECTION: Rules 293-294, 338-339 — Representative & Secondary Address
    # ========================================================================

    # Rule 338: Secondary address mandatory
    if inp.representative_details and inp.representative_details.capacity and not inp.secondary_address:
        results.append(_make(
            "ITR1-R338", False,
            "Secondary address is mandatory in Schedule Part A when filing as a "
            "representative assessee.",
            "secondary_address",
        ))

    # Rule 339: Secondary address must not equal primary address
    # (Portal-level — schema doesn't store primary address)

    # Rule 293: Representative name and contact mandatory
    if inp.representative_details and inp.representative_details.capacity:
        rd = inp.representative_details
        if not rd.represented_person_name:
            results.append(_make(
                "ITR1-R293", False,
                "Representative assessee: represented person's name is mandatory.",
                "representative_details.represented_person_name",
            ))

    # Rule 294: If representative flag, details must be provided
    if inp.representative_details and inp.representative_details.capacity:
        if not inp.representative_details.represented_person_name and not inp.representative_details.represented_person_pan:
            results.append(_make(
                "ITR1-R294", False,
                "Representative assessee filing: at minimum, the represented person's "
                "name and PAN are required.",
                "representative_details",
            ))

    # ========================================================================
    # SECTION: Rule 255 — New Regime with Prohibited Exempt Allowances by
    # nature-of-employment (Rules 148-150, 161-167, 301)
    # ========================================================================

    if is_new:
        # Rule 148: Transport allowance only for VIsually Imaired (cap Rs 38,400)
        if sal.transport_allowance > 0:
            results.append(_make(
                "ITR1-R148", False,
                f"Transport allowance of Rs {sal.transport_allowance} claimed under "
                f"new regime. Only exempt for physically handicapped assessees and "
                f"must not exceed Rs 38,400.",
                "salary_income.transport_allowance",
            ))

        # Rule 149: LTA and HRA not available in new regime
        if sal.lta_amount_received > _z or sal.lta_exempt_amount > _z:
            results.append(_make(
                "ITR1-R149", False,
                f"LTA exemption claimed under new regime. LTA (Sec 10(5)) is not "
                f"available in the new tax regime.",
                "salary_income.lta_exempt_amount",
            ))
        if sal.hra_exempt_amount > _z:
            results.append(_make(
                "ITR1-R149b", False,
                f"HRA exemption claimed under new regime. HRA (Sec 10(13A)) is not "
                f"available in the new tax regime.",
                "salary_income.hra_exempt_amount",
            ))

        # Rule 161: MP/MLA/MLC allowance not in new regime
        # Rule 301: Judges' exempt not in new regime
        # (Informational — these are edge cases)

    # ========================================================================
    # SECTION: Rule 301 — Judges exemption only for judges
    # ========================================================================

    judges_key = "Judge Salaries Act"
    if judges_key in inp.exempt_income_dropdowns:
        # Only judges covered under SC/HC Judges Act can claim this
        emp = inp.nature_of_employment or ""
        if "central government" not in emp.lower() and "state government" not in emp.lower():
            results.append(_make(
                "ITR1-R301", False,
                f"Exempt income under 'Judge Salaries Act' selected but nature of "
                f"employment is '{inp.nature_of_employment}'. This exemption is only "
                f"available to judges covered under the Supreme Court/High Court Judges Act.",
                "exempt_income_dropdowns",
            ))

    # ========================================================================
    # SECTION: Rules 336 — Unrealized Rent ≤ Gross Rent Received
    # ========================================================================

    if hp.arrears_unrealised_rent_received > _z:
        total_rent = (hp.annual_rent_received or _z) + (hp.arrears_unrealised_rent_received or _z)
        if hp.arrears_unrealised_rent_received > hp.annual_rent_received:
            results.append(_make(
                "ITR1-R336", False,
                f"Arrears/Unrealised rent (Rs {hp.arrears_unrealised_rent_received}) "
                f"exceeds gross rent received/receivable (Rs {hp.annual_rent_received}). "
                f"Unrealized rent cannot be more than the total gross rent.",
                "house_property_income.arrears_unrealised_rent_received",
            ))

    # Schedule 80GGA: Donee PAN uniqueness
    if inp.schedule_80gga and inp.schedule_80gga.donee_pan_list:
        pans = inp.schedule_80gga.donee_pan_list
        if len(pans) != len(set(pans)):
            results.append(_make(
                "ITR1-R118", False,
                "Schedule 80GGA: same Donee PAN appears more than once. "
                "Each PAN can only be listed once per donation mode.",
                "schedule_80gga.donee_pan_list",
            ))
        # Cash donations in 80GGA capped at Rs 2,000
        if inp.schedule_80gga.cash_donations > 2_000:
            results.append(_make(
                "ITR1-R118b", False,
                f"Schedule 80GGA cash donations (Rs {inp.schedule_80gga.cash_donations}) "
                f"exceed Rs 2,000 per-donee limit (cannot claim any cash amount)",
                "schedule_80gga.cash_donations",
            ))

    # Schedule 80GGC: Must be non-cash only
    if inp.schedule_80ggc and inp.schedule_80ggc.total_claimed > 0:
        if inp.schedule_80ggc.non_cash_contributions != inp.schedule_80ggc.total_claimed:
            results.append(_make(
                "ITR1-R193", False,
                "Schedule 80GGC: political contributions must be entirely non-cash "
                "(cheque/draft/ECS). Cash contributions are not deductible.",
                "schedule_80ggc",
            ))

    # Form 10E (relief u/s 89) requirement
    if inp.form_10e_filed:
        results.append(_info(
            "ITR1-RD1",
            f"Form 10E filed for relief u/s 89. Verify that relief is computed correctly "
            f"and salary details support the relief claim.",
            "form_10e_filed",
        ))

    # Co-ownership: 80EEA requires full ownership
    if ch6a and ch6a.amount_80eea > 0 and inp.co_ownership_details:
        cod = inp.co_ownership_details
        if cod.ownership_percentage != 100:
            results.append(_make(
                "ITR1-R295", False,
                f"80EEA deduction requires assessee to be the sole owner of the property. "
                f"Current ownership percentage: {cod.ownership_percentage}%",
                "co_ownership_details.ownership_percentage",
            ))

    # Representative assessee validations
    if inp.representative_details:
        rd = inp.representative_details
        if rd.capacity:
            if not rd.represented_person_name or not rd.represented_person_pan:
                results.append(_make(
                    "ITR1-R293", False,
                    "Representative assessee filing: represented person's name and PAN are "
                    "mandatory when capacity is specified",
                    "representative_details",
                ))
            if not inp.secondary_address:
                results.append(_make(
                    "ITR1-R294", False,
                    "Representative assessee filing: secondary address of the representative "
                    "is mandatory",
                    "secondary_address",
                ))

    # ITR1-R126: u/s 142(1) → cannot file u/s 139
    if inp.filing_section:
        if inp.original_filing_section == "142(1)" and inp.filing_section in ("139(1)", "139(4)"):
            results.append(_make(
                "ITR1-R126", False,
                f"Original return filed u/s 142(1) → cannot file a fresh return u/s "
                f"{inp.filing_section}. Only a revised return u/s 139(5) is permitted.",
                "filing_section",
            ))

    # ========================================================================
    # SECTION: Category B — Warnings (unusual but potentially valid input)
    # ========================================================================

    # B1: Gross salary > 50L unusual for ITR-1 filer
    if sal.gross_salary > 5_000_000:
        results.append(_warn(
            "ITR1-B001",
            f"Gross salary (Rs {sal.gross_salary}) exceeds Rs 50,00,000. "
            f"This is unusual for ITR-1 (Sahaj) filers. Consider whether ITR-2 is more appropriate.",
            "salary_income.gross_salary",
        ))

    # B2: HRA exempt > 50% of gross salary
    if sal.hra_exempt_amount > _z and sal.gross_salary > _z:
        hra_pct = sal.hra_exempt_amount / sal.gross_salary
        if hra_pct > Decimal("0.5"):
            results.append(_warn(
                "ITR1-B002",
                f"HRA exemption (Rs {sal.hra_exempt_amount}) is {float(hra_pct)*100:.1f}% "
                f"of gross salary (Rs {sal.gross_salary}). This is unusually high. "
                f"HRA exemption is the least of: actual HRA received, 50% of salary (metro) / "
                f"40% (non-metro), or rent paid minus 10% of salary.",
                "salary_income.hra_exempt_amount",
            ))

    # B3: Professional tax > 2500
    if sal.professional_tax_paid > 2_500:
        results.append(_warn(
            "ITR1-B003",
            f"Professional tax paid (Rs {sal.professional_tax_paid}) exceeds Rs 2,500. "
            f"Most states cap professional tax at Rs 2,500/year. Verify the amount.",
            "salary_income.professional_tax_paid",
        ))

    # B4: Standard deduction not claimed
    if sal.gross_salary > _z and sal.standard_deduction_claimed == _z:
        results.append(_warn(
            "ITR1-B004",
            f"Standard deduction is not claimed despite gross salary of Rs {sal.gross_salary}. "
            f"Did you mean to claim the standard deduction (Rs 50,000 old regime / Rs 75,000 new regime)?",
            "salary_income.standard_deduction_claimed",
        ))

    # B5: 80C claimed with very low salary ratio
    if ch6a and ch6a.amount_80c > _z and sal.gross_salary > _z:
        if ch6a.amount_80c > sal.gross_salary:
            results.append(_warn(
                "ITR1-B005",
                f"80C deduction (Rs {ch6a.amount_80c}) exceeds gross salary "
                f"(Rs {sal.gross_salary}). 80C is typically limited to the actual salary earned. "
                f"Verify the source of 80C-eligible investments.",
                "deductions_chapter6a.amount_80c",
            ))

    # B6: HP interest > 2x loan principal (unusual)
    if hp.home_loan_interest_paid > _z and inp.loan_details_24b_list:
        total_principal = sum(ld.loan_amount for ld in inp.loan_details_24b_list)
        if total_principal > _z and hp.home_loan_interest_paid > total_principal * 2:
            results.append(_warn(
                "ITR1-B006",
                f"Home loan interest (Rs {hp.home_loan_interest_paid}) is more than 2x "
                f"the total loan principal (Rs {total_principal}). "
                f"This may be valid for very old loans but is unusual.",
                "house_property_income.home_loan_interest_paid",
            ))

    # B7: 80D self exactly 25,000 — might be missing senior flag
    if ch6a and ch6a.amount_80d_self_family == 25_000 and inp.schedule_80d:
        if not inp.schedule_80d.has_self_senior:
            results.append(_warn(
                "ITR1-B007",
                f"80D Self/Family claimed exactly Rs 25,000 without the senior citizen flag. "
                f"If the insured person is a senior citizen (60+), "
                f"the limit is Rs 50,000. Verify has_self_senior in Schedule 80D.",
                "deductions_chapter6a.amount_80d_self_family",
            ))

    # B8: 80D parents exactly 25,000 — might be missing parents senior flag
    if ch6a and ch6a.amount_80d_parents == 25_000 and inp.schedule_80d:
        if not inp.schedule_80d.has_parents_senior:
            results.append(_warn(
                "ITR1-B008",
                f"80D Parents claimed exactly Rs 25,000 without the parents senior citizen flag. "
                f"If any parent is a senior citizen (60+), "
                f"the limit is Rs 50,000. Verify has_parents_senior in Schedule 80D.",
                "deductions_chapter6a.amount_80d_parents",
            ))

    # B9: 80EEA claimed but no HP income
    if ch6a and ch6a.amount_80eea > _z:
        if hp.home_loan_interest_paid == _z and hp.annual_rent_received == _z:
            results.append(_warn(
                "ITR1-B009",
                f"80EEA deduction (Rs {ch6a.amount_80eea}) is claimed but no house property "
                f"income or home loan interest is reported. "
                f"80EEA requires a first-time home loan for a self-occupied property.",
                "deductions_chapter6a.amount_80eea",
            ))

    # ========================================================================
    # PHASE 2: New Code Gap Validators (CBDT Rules previously unimplemented)
    # ========================================================================

    # --- R009: 80G Table F = sum of A+B+C+D categories ---
    if ch6a and ch6a.donations_80g and is_old:
        cat_sums: dict[str, Decimal] = {}
        for d in ch6a.donations_80g:
            cat = d.donation_category if d.donation_category else "A"
            cat_sums[cat] = cat_sums.get(cat, _z) + d.cash_amount + d.non_cash_amount
        total_from_cats = sum(cat_sums.values(), _z)
        if inp.schedule_80g and inp.schedule_80g.donations:
            sg_total = sum(d.cash_amount + d.non_cash_amount for d in inp.schedule_80g.donations)
            if sg_total > _z and abs(total_from_cats - sg_total) > Decimal("1"):
                results.append(_make(
                    "ITR1-R009", False,
                    f"80G Table F total donation (Rs {sg_total}) does not equal sum of "
                    f"A+B+C+D category totals (Rs {total_from_cats})",
                    "schedule_80g",
                ))

    # --- R030: Exempt income total = sum of breakdown columns ---
    if inp.total_exempt_income and inp.total_exempt_income > _z:
        breakdown_sum = sum(inp.exempt_income_breakdown.values(), _z)
        if breakdown_sum > _z:
            if abs(inp.total_exempt_income - breakdown_sum) > Decimal("1"):
                results.append(_make(
                    "ITR1-R030", False,
                    f"Total exempt income (Rs {inp.total_exempt_income}) does not equal "
                    f"sum of individual exempt income columns (Rs {breakdown_sum})",
                    "exempt_income_breakdown",
                ))

    # --- R079-R087: 80G per-table cash/non-cash mandatory + cross-foot ---
    if ch6a and ch6a.donations_80g and inp.schedule_80g:
        cat_label = {"A": "100% without qualifying limit", "B": "50% without qualifying limit",
                     "C": "100% subject to qualifying limit", "D": "50% subject to qualifying limit"}
        for cat in ("A", "B", "C", "D"):
            cat_donations = [d for d in inp.schedule_80g.donations if d.donation_category == cat]
            if cat_donations:
                cat_cash = sum(d.cash_amount for d in cat_donations)
                cat_noncash = sum(d.non_cash_amount for d in cat_donations)
                cat_total = cat_cash + cat_noncash
                # R079-R082: each table needs cash or non-cash entries before total
                for i, d in enumerate(cat_donations):
                    if d.total_donation and d.total_donation > _z:
                        if d.cash_amount == _z and d.non_cash_amount == _z:
                            results.append(_make(
                                "ITR1-R079", False,
                                f"80G Table {cat}: total donation of Rs {d.total_donation} entered "
                                f"but neither cash nor non-cash amount provided",
                                f"schedule_80g.donations",
                            ))
                    # R084-R087: per-row total = cash + non-cash
                    if d.total_donation and abs(d.cash_amount + d.non_cash_amount - d.total_donation) > Decimal("1"):
                        results.append(_make(
                            f"ITR1-R084", False,
                            f"80G Table {cat}: total donation (Rs {d.total_donation}) != "
                            f"cash (Rs {d.cash_amount}) + non-cash (Rs {d.non_cash_amount}) "
                            f"= Rs {d.cash_amount + d.non_cash_amount}",
                            f"schedule_80g.donations",
                        ))

    # --- R091: 80GGA claimed → details in schedule ---
    if ch6a and ch6a.amount_80gga > 0 and not inp.schedule_80gga:
        results.append(_make(
            "ITR1-R091", False,
            "80GGA deduction claimed but Schedule 80GGA details not provided",
            "deductions_chapter6a.amount_80gga",
        ))

    # --- R092-R093: 80GGA eligible ≤ total; VIA ≤ schedule eligible ---
    if inp.schedule_80gga:
        sgga = inp.schedule_80gga
        if sgga.total_claimed > _z and sgga.eligible_amount > _z:
            if sgga.eligible_amount > sgga.total_claimed:
                results.append(_make(
                    "ITR1-R092", False,
                    f"80GGA eligible amount (Rs {sgga.eligible_amount}) exceeds "
                    f"total donations (Rs {sgga.total_claimed})",
                    "schedule_80gga.eligible_amount",
                ))
            if ch6a and ch6a.amount_80gga > sgga.eligible_amount:
                results.append(_make(
                    "ITR1-R093", False,
                    f"80GGA VIA claimed (Rs {ch6a.amount_80gga}) exceeds schedule "
                    f"eligible amount (Rs {sgga.eligible_amount})",
                    "deductions_chapter6a.amount_80gga",
                ))

    # --- R107: IFSC match RBI/GIFT DB (informational only — no local DB) ---
    if inp.schedule_80g:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.ifsc_code and d.non_cash_amount > _z:
                results.append(_info(
                    "ITR1-R107",
                    f"80G donation row {i+1}: IFSC code {d.ifsc_code} must match RBI/GIFT "
                    f"IFSC database. Verification is portal-level only.",
                    f"schedule_80g.donations[{i}].ifsc_code",
                ))

    # --- R147: 80G PAN in one block only ---
    if ch6a and ch6a.donations_80g:
        pan_blocks: dict[str, set] = {}
        for d in ch6a.donations_80g:
            if d.donee_pan:
                pan_blocks.setdefault(d.donee_pan, set()).add(d.donation_category)
        for pan, blocks in pan_blocks.items():
            if len(blocks) > 1:
                results.append(_make(
                    "ITR1-R147", False,
                    f"Donee PAN '{pan}' appears in multiple 80G blocks: {blocks}. "
                    f"Same PAN must not be entered under different 80G tables.",
                    "deductions_chapter6a.donations_80g",
                ))

    # --- R150: Old regime 10(14)(i)/(ii) caps ---
    if is_old and sal:
        if sal.sec10_14i_prescribed_allowance > _z:
            if sal.sec10_14i_prescribed_allowance > sal.gross_salary:
                results.append(_make(
                    "ITR1-R150", False,
                    f"Old regime 10(14)(i) prescribed allowance (Rs {sal.sec10_14i_prescribed_allowance}) "
                    f"exceeds salary 17(1) (Rs {sal.gross_salary})",
                    "salary_income.sec10_14i_prescribed_allowance",
                ))
            else:
                results.append(_info(
                    "ITR1-R150b",
                    f"Old regime 10(14)(i) allowance of Rs {sal.sec10_14i_prescribed_allowance} "
                    f"claimed. Verify actual incurrence for official duties per Rule 2BB.",
                    "salary_income.sec10_14i_prescribed_allowance",
                ))
        if sal.sec10_14ii_personal_allowance > _z:
            if sal.sec10_14ii_personal_allowance > sal.gross_salary:
                results.append(_make(
                    "ITR1-R150c", False,
                    f"Old regime 10(14)(ii) personal allowance (Rs {sal.sec10_14ii_personal_allowance}) "
                    f"exceeds salary 17(1) (Rs {sal.gross_salary})",
                    "salary_income.sec10_14ii_personal_allowance",
                ))

    # --- R166-R167: New regime 10(14)(i)/(ii) = 0 ---
    if is_new and sal:
        if sal.sec10_14i_prescribed_allowance > _z:
            results.append(_make(
                "ITR1-R166", False,
                f"New regime: 10(14)(i) prescribed allowance of Rs {sal.sec10_14i_prescribed_allowance} "
                f"is not allowed under Section 115BAC",
                "salary_income.sec10_14i_prescribed_allowance",
            ))
        if sal.sec10_14ii_personal_allowance > _z:
            results.append(_make(
                "ITR1-R167", False,
                f"New regime: 10(14)(ii) personal allowance of Rs {sal.sec10_14ii_personal_allowance} "
                f"is not allowed under Section 115BAC",
                "salary_income.sec10_14ii_personal_allowance",
            ))

    # --- R177: 10(10CC) ≤ TDS u/s 192 ---
    if sal and sal.sec10_10cc_perquisite_tax > _z:
        tds192_total = sum(e.tds_deducted for e in (inp.tds1_entries or []))
        if sal.sec10_10cc_perquisite_tax > tds192_total:
            results.append(_make(
                "ITR1-R177", False,
                f"10(10CC) exempt perquisite tax (Rs {sal.sec10_10cc_perquisite_tax}) exceeds "
                f"TDS u/s 192 in TDS1 (Rs {tds192_total}). Employer-paid tax on perquisite "
                f"cannot exceed total salary TDS.",
                "salary_income.sec10_10cc_perquisite_tax",
            ))

    # --- R185: 10(10B) not allowed for CG/SG/pensioners ---
    if sal and sal.retrenchment_compensation > _z and inp.nature_of_employment:
        emp_lower = inp.nature_of_employment.lower()
        if any(kw in emp_lower for kw in ("central", "state", "pension", "cg-", "sg-")):
            results.append(_make(
                "ITR1-R185", False,
                f"10(10B) retrenchment compensation of Rs {sal.retrenchment_compensation} "
                f"claimed but assessee is a government employee/pensioner ({inp.nature_of_employment}). "
                f"10(10B) exemption is only for industrial workers covered by ID Act.",
                "salary_income.retrenchment_compensation",
            ))

    # --- R202: 80U VIA = Schedule 80U ---
    if ch6a and ch6a.amount_80u > _z and inp.schedule_80u:
        su = inp.schedule_80u
        if ch6a.amount_80u != su.deduction_amount:
            results.append(_make(
                "ITR1-R202", False,
                f"80U VIA amount (Rs {ch6a.amount_80u}) does not match Schedule 80U "
                f"deduction amount (Rs {su.deduction_amount})",
                "deductions_chapter6a.amount_80u",
            ))

    # --- R205: 80DD VIA = Schedule 80DD ---
    if ch6a and ch6a.amount_80dd > _z and inp.schedule_80dd:
        sdd = inp.schedule_80dd
        if ch6a.amount_80dd != sdd.deduction_amount:
            results.append(_make(
                "ITR1-R205", False,
                f"80DD VIA amount (Rs {ch6a.amount_80dd}) does not match Schedule 80DD "
                f"deduction amount (Rs {sdd.deduction_amount})",
                "deductions_chapter6a.amount_80dd",
            ))

    # --- R206-R207: 80DD/80U > 0 → details required ---
    if inp.schedule_80dd and inp.schedule_80dd.deduction_amount > _z:
        if not inp.schedule_80dd.disability_type:
            results.append(_make(
                "ITR1-R206", False,
                "80DD deduction > 0 but disability type not specified. "
                "Specify 'dependent person with disability' or 'dependent person with severe disability'",
                "schedule_80dd.disability_type",
            ))
    if inp.schedule_80u and inp.schedule_80u.deduction_amount > _z:
        if not inp.schedule_80u.disability_type:
            results.append(_make(
                "ITR1-R207", False,
                "80U deduction > 0 but disability type not specified. "
                "Specify 'self with disability' or 'self with severe disability'",
                "schedule_80u.disability_type",
            ))

    # --- R211: 80GGC date range 01.04.2025 - 31.03.2026 ---
    if inp.schedule_80ggc and inp.schedule_80ggc.contributions:
        for i, c in enumerate(inp.schedule_80ggc.contributions):
            if c.contribution_date:
                ay25_start, ay25_end = date(2025, 4, 1), date(2026, 3, 31)
                if c.contribution_date < ay25_start or c.contribution_date > ay25_end:
                    results.append(_make(
                        "ITR1-R211", False,
                        f"80GGC contribution {i+1} date ({c.contribution_date}) is outside "
                        f"the valid period 01.04.2025-31.03.2026 for AY 2026-27",
                        f"schedule_80ggc.contributions[{i}].contribution_date",
                    ))

    # --- R222-R223: 80EE/80EEA loan must be part of 24(b) loans ---
    if inp.loan_details_80ee and inp.loan_details_24b_list:
        ld80ee = inp.loan_details_80ee
        found = any(
            ld.lender_name == ld80ee.lender_name and
            abs(ld.loan_amount - ld80ee.loan_amount) <= Decimal("1")
            for ld in inp.loan_details_24b_list
        )
        if not found:
            results.append(_make(
                "ITR1-R222", False,
                f"80EE loan (lender: {ld80ee.lender_name}, amount: Rs {ld80ee.loan_amount}) "
                f"must also appear in Schedule 24(b) loan details. 80EE is an additional "
                f"deduction over and above 24(b).",
                "loan_details_80ee",
            ))
    if inp.loan_details_80eea and inp.loan_details_24b_list:
        ld80eea = inp.loan_details_80eea
        found = any(
            ld.lender_name == ld80eea.lender_name and
            abs(ld.loan_amount - ld80eea.loan_amount) <= Decimal("1")
            for ld in inp.loan_details_24b_list
        )
        if not found:
            results.append(_make(
                "ITR1-R223", False,
                f"80EEA loan (lender: {ld80eea.lender_name}, amount: Rs {ld80eea.loan_amount}) "
                f"must also appear in Schedule 24(b) loan details.",
                "loan_details_80eea",
            ))

    # --- R246: 24(b) sum of individual rows = total interest ---
    if inp.loan_details_24b_list and hp.home_loan_interest_paid > _z:
        total_24b_interest = sum(
            ld.interest_paid_self_occupied + ld.interest_paid_let_out
            for ld in inp.loan_details_24b_list
        )
        if total_24b_interest > _z:
            if abs(hp.home_loan_interest_paid - total_24b_interest) > Decimal("1"):
                results.append(_make(
                    "ITR1-R246", False,
                    f"24(b) total interest claimed (Rs {hp.home_loan_interest_paid}) does not "
                    f"equal sum of individual loan interest amounts (Rs {total_24b_interest})",
                    "house_property_income.home_loan_interest_paid",
                ))

    # --- R249-R251: 80EE/80EEA/80EEB per-row sum = VIA total ---
    if ch6a and ch6a.amount_80ee > _z and inp.loan_details_80ee_list:
        ee_sum = sum(e.interest_paid for e in inp.loan_details_80ee_list)
        if ee_sum > _z and abs(ch6a.amount_80ee - ee_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R249", False,
                f"80EE VIA (Rs {ch6a.amount_80ee}) != sum of Schedule 80EE per-row "
                f"interest (Rs {ee_sum})",
                "deductions_chapter6a.amount_80ee",
            ))
    if ch6a and ch6a.amount_80eea > _z and inp.loan_details_80eea_list:
        eea_sum = sum(e.interest_paid for e in inp.loan_details_80eea_list)
        if eea_sum > _z and abs(ch6a.amount_80eea - eea_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R250", False,
                f"80EEA VIA (Rs {ch6a.amount_80eea}) != sum of Schedule 80EEA per-row "
                f"interest (Rs {eea_sum})",
                "deductions_chapter6a.amount_80eea",
            ))
    if ch6a and ch6a.amount_80eeb > _z and inp.loan_details_80eeb_list:
        eeb_sum = sum(e.interest_paid for e in inp.loan_details_80eeb_list)
        if eeb_sum > _z and abs(ch6a.amount_80eeb - eeb_sum) > Decimal("1"):
            results.append(_make(
                "ITR1-R251", False,
                f"80EEB VIA (Rs {ch6a.amount_80eeb}) != sum of Schedule 80EEB per-row "
                f"interest (Rs {eeb_sum})",
                "deductions_chapter6a.amount_80eeb",
            ))

    # --- R260: Section 192 must not appear in TDS2/TDS3 ---
    for i, e in enumerate(inp.tds2_entries or []):
        if getattr(e, 'tds_section', '') == '192':
            results.append(_make(
                "ITR1-R260", False,
                f"TDS2 entry #{i+1}: Section 192 (salary TDS) must only be in Schedule TDS1, "
                f"not TDS2 (which is for income OTHER than salary).",
                f"tds2_entries[{i}].tds_section",
            ))
    for i, e in enumerate(inp.tds3_entries or []):
        if getattr(e, 'tds_section', '') == '192':
            results.append(_make(
                "ITR1-R260b", False,
                f"TDS3 entry #{i+1}: Section 192 cannot appear in TDS3",
                f"tds3_entries[{i}].tds_section",
            ))

    # --- R265-R266: Schedule 10(13A) must be filled + basic+DA+HRA ≤ 17(1) ---
    if sal and sal.hra_exempt_amount > _z:
        if not inp.hra_details and not inp.schedule_10_13a:
            results.append(_make(
                "ITR1-R265", False,
                "HRA exemption claimed but Schedule 10(13A) not provided. "
                "Schedule 10(13A) is mandatory for claiming HRA exemption.",
                "hra_details",
            ))
    if inp.schedule_10_13a:
        hra_sched = inp.schedule_10_13a
        if hra_sched.salary_for_hra > _z and hra_sched.actual_hra_received > _z:
            combined = hra_sched.salary_for_hra + hra_sched.actual_hra_received
            if combined > sal.gross_salary:
                results.append(_make(
                    "ITR1-R266", False,
                    f"Schedule 10(13A): Basic Salary+DA (Rs {hra_sched.salary_for_hra}) + "
                    f"Actual HRA (Rs {hra_sched.actual_hra_received}) = Rs {combined} exceeds "
                    f"salary u/s 17(1) (Rs {sal.gross_salary})",
                    "schedule_10_13a",
                ))

    # --- R267: Gratuity ≤ ₹25L for CG/SG employees ---
    if sal and sal.gratuity_received > _z and inp.nature_of_employment:
        emp_lower = inp.nature_of_employment.lower()
        is_cg_sg = any(kw in emp_lower for kw in ("central", "state")) and "government" in emp_lower
        if is_cg_sg and sal.gratuity_received > 2_500_000:
            results.append(_make(
                "ITR1-R267", False,
                f"Gratuity claimed (Rs {sal.gratuity_received}) exceeds ₹25,00,000 limit for "
                f"Central/State Government employees.",
                "salary_income.gratuity_received",
            ))
        is_psu_private = any(kw in emp_lower for kw in ("psu", "private", "other", "pension"))
        if is_psu_private and sal.gratuity_received > 2_000_000:
            results.append(_make(
                "ITR1-R067", False,
                f"Gratuity claimed (Rs {sal.gratuity_received}) exceeds ₹20,00,000 limit for "
                f"non-Government employees.",
                "salary_income.gratuity_received",
            ))

    # --- R268: DOI ≥ 01/04/2008 → blocked for individuals ---
    if inp.date_of_incorporation and inp.date_of_incorporation >= date(2008, 4, 1):
        results.append(_make(
            "ITR1-R268", False,
            f"Individual with date of formation (DOI {inp.date_of_incorporation}) on or after "
            f"01/04/2008 cannot file ITR-1 for AY 2026-27. Use ITR-2 or ITR-4.",
            "date_of_incorporation",
        ))

    # --- R295-R299: Co-ownership HP details ---
    if inp.is_property_co_owned and inp.co_ownership_details:
        cod = inp.co_ownership_details
        # R295: Assessee share + other share = 100%
        if abs(cod.ownership_percentage + inp.other_co_owner_percentage - Decimal("100")) > Decimal("1"):
            results.append(_make(
                "ITR1-R295", False,
                f"Co-owned property: assessee share ({cod.ownership_percentage}%) + "
                f"other co-owner share ({inp.other_co_owner_percentage}%) ≠ 100%",
                "co_ownership_details.ownership_percentage",
            ))
        # R297: Zero share → interest cannot be claimed
        if cod.ownership_percentage <= _z and hp.home_loan_interest_paid > _z:
            results.append(_make(
                "ITR1-R297", False,
                "Co-owned property with 0% assessee share: interest on borrowed capital "
                "cannot be claimed.",
                "house_property_income.home_loan_interest_paid",
            ))
        # R300: Assessee PAN ≠ co-owner PAN
        if inp.assessee_pan and cod.co_owner_pan and inp.assessee_pan == cod.co_owner_pan:
            results.append(_make(
                "ITR1-R300", False,
                f"Co-owned property: assessee PAN ({inp.assessee_pan}) cannot be the same "
                f"as co-owner PAN ({cod.co_owner_pan})",
                "co_ownership_details.co_owner_pan",
            ))

    # --- R323: New regime 10(32) minor child = 0 ---
    child_income_key = "Sec 10(32) Minor Child Income"
    if is_new and child_income_key in inp.exempt_income_dropdowns:
        results.append(_make(
            "ITR1-R323", False,
            f"New regime: Exempt income u/s 10(32) (minor child income) is not available.",
            "exempt_income_dropdowns",
        ))

    # --- R324, R328: 234-I late fee ---
    if inp.filing_section == "139(5)" and inp.filing_date:
        cutoff = date(2026, 12, 31)  # Fees apply for revised returns filed after 31 Dec
        if inp.filing_date > cutoff:
            # R324/R328: 234-I fee — ₹1,000 if TI ≤ 5L, ₹5,000 if TI > 5L (hard info)
            results.append(_make(
                "ITR1-R324", True,
                f"Revised return filed after 31/12/2026. Fee u/s 234-I applies: "
                f"₹1,000 if total income ≤ ₹5L, ₹5,000 if total income > ₹5L. "
                f"This is computed by the engine and verified in calc_rules.",
                "filing_date",
            ))

    # --- R331: Representative email/contact ≠ taxpayer ---
    if inp.representative_details and inp.representative_details.capacity:
        if inp.representative_email and inp.assessee_email_primary:
            if inp.representative_email.lower() == inp.assessee_email_primary.lower():
                results.append(_make(
                    "ITR1-R331", False,
                    f"Representative email ({inp.representative_email}) must not match "
                    f"assessee's primary email",
                    "representative_email",
                ))
        if inp.representative_phone and inp.assessee_phone_primary:
            if inp.representative_phone == inp.assessee_phone_primary:
                results.append(_make(
                    "ITR1-R331b", False,
                    f"Representative phone ({inp.representative_phone}) must not match "
                    f"assessee's primary phone",
                    "representative_phone",
                ))

    # --- R339: Secondary address ≠ primary address ---
    if inp.secondary_address:
        # Portal-level check — informational since we don't have primary address in schema
        results.append(_info(
            "ITR1-R339",
            "Secondary address must not be same as primary address. "
            "Verified at e-Filing upload level.",
            "secondary_address",
        ))

    # --- R079-R082: 80G per-table cash/noncash mandatory for total deduction column ---
    if inp.schedule_80g:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.cash_amount == _z and d.non_cash_amount == _z and ch6a and ch6a.amount_80g > _z:
                results.append(_make(
                    "ITR1-R079", False,
                    f"80G donation row {i+1}: neither cash nor non-cash amount entered "
                    f"but 80G deduction claimed. Each donation row must have an amount.",
                    f"schedule_80g.donations[{i}]",
                ))

    # --- R083: 80G Table E = sum of A+B+C+D ---
    if inp.schedule_80g:
        cats_total = {"A": _z, "B": _z, "C": _z, "D": _z}
        for d in inp.schedule_80g.donations:
            cats_total[d.donation_category] = cats_total.get(d.donation_category, _z) + d.cash_amount + d.non_cash_amount
        table_e_sum = cats_total["A"] + cats_total["B"] + cats_total["C"] + cats_total["D"]
        sg_all = sum(d.cash_amount + d.non_cash_amount for d in inp.schedule_80g.donations)
        if sg_all > _z and abs(table_e_sum - sg_all) > Decimal("1"):
            results.append(_make(
                "ITR1-R083", False,
                f"80G Table E: sum of tables A+B+C+D (Rs {table_e_sum}) != "
                f"total of all donations (Rs {sg_all})",
                "schedule_80g",
            ))

    # --- R094: 80GGA Donee PAN ≠ Assessee PAN ---
    if inp.schedule_80gga and inp.assessee_pan:
        for pan in inp.schedule_80gga.donee_pan_list:
            if pan and pan == inp.assessee_pan:
                results.append(_make(
                    "ITR1-R094", False,
                    f"80GGA: Donee PAN ({pan}) cannot be the same as Assessee PAN",
                    "schedule_80gga.donee_pan_list",
                ))

    # --- R078: 80G Donee PAN ≠ Assessee PAN ---
    if inp.schedule_80g and inp.assessee_pan:
        for i, d in enumerate(inp.schedule_80g.donations):
            if d.donee_pan and d.donee_pan == inp.assessee_pan:
                results.append(_make(
                    "ITR1-R078", False,
                    f"80G donation row {i+1}: Donee PAN ({d.donee_pan}) cannot be the same "
                    f"as Assessee PAN",
                    f"schedule_80g.donations[{i}].donee_pan",
                ))

    # --- R193: 80GGC VIA = Schedule 80GGC total ---
    if ch6a and ch6a.amount_80ggc > _z and inp.schedule_80ggc:
        if ch6a.amount_80ggc != inp.schedule_80ggc.total_claimed:
            results.append(_make(
                "ITR1-R193", False,
                f"80GGC VIA claimed (Rs {ch6a.amount_80ggc}) does not match Schedule 80GGC "
                f"total (Rs {inp.schedule_80ggc.total_claimed})",
                "deductions_chapter6a.amount_80ggc",
            ))

    # --- R194-R199: 80GGC per-row validations ---
    if inp.schedule_80ggc and inp.schedule_80ggc.contributions:
        sggc = inp.schedule_80ggc
        total_from_rows = sum(c.amount for c in sggc.contributions)
        # R195: Total = cash + non-cash (80GGC is non-cash only)
        if sggc.total_claimed > _z and sggc.total_claimed != total_from_rows:
            results.append(_make(
                "ITR1-R195", False,
                f"80GGC total claimed (Rs {sggc.total_claimed}) does not equal sum of "
                f"per-contribution amounts (Rs {total_from_rows})",
                "schedule_80ggc.total_claimed",
            ))
        for i, c in enumerate(sggc.contributions):
            # R198: Date of contribution mandatory
            if c.amount > _z and not c.contribution_date:
                results.append(_make(
                    "ITR1-R198", False,
                    f"80GGC contribution {i+1}: date of contribution is mandatory",
                    f"schedule_80ggc.contributions[{i}].contribution_date",
                ))
            # R199: Non-cash mode details required
            if c.amount > _z and c.contribution_mode == "non_cash" and not c.transaction_ref:
                results.append(_make(
                    "ITR1-R199", False,
                    f"80GGC contribution {i+1}: non-cash contribution of Rs {c.amount} "
                    f"requires transaction reference (cheque number / ECS ref)",
                    f"schedule_80ggc.contributions[{i}].transaction_ref",
                ))
            # R329: Political party name and PAN required
            if c.amount > _z and (not c.political_party_name or not c.political_party_pan):
                results.append(_make(
                    "ITR1-R329", False,
                    f"80GGC contribution {i+1}: political party name and PAN are mandatory",
                    f"schedule_80ggc.contributions[{i}]",
                ))

    # --- R219: 139(9) defective response A23 match (portal-level) ---
    results.append(_info(
        "ITR1-R219",
        "139(9) defective return response: A23 answers must match the defective "
        "ITR against which the response is submitted. Portal-level check.",
        "filing_section",
    ))

    # --- R270: Judges exemption — only CG/SG employees ---
    judges_key = "Judge Salaries Act"
    if judges_key in inp.exempt_income_dropdowns:
        emp_lower = (inp.nature_of_employment or "").lower()
        if not any(govt in emp_lower for govt in ("central government", "state government", "cg-", "sg-")):
            results.append(_make(
                "ITR1-R270", False,
                f"Judge Salaries Act exemption claimed but nature of employment is "
                f"'{inp.nature_of_employment}'. Only Supreme Court / High Court judges are eligible.",
                "exempt_income_dropdowns",
            ))

    # --- R301: Judges exemption new regime = 0 ---
    if judges_key in inp.exempt_income_dropdowns and is_new:
        results.append(_make(
            "ITR1-R301", False,
            "Judge Salaries Act exemption is not available under the new tax regime",
            "exempt_income_dropdowns",
        ))

    # --- R089-R090: 80GGA — duplicate Donee PAN check per mode ---
    if inp.schedule_80gga and inp.schedule_80gga.donee_pan_list:
        pan_at_indices: dict[str, list[int]] = {}
        for i, pan in enumerate(inp.schedule_80gga.donee_pan_list):
            if pan:
                pan_at_indices.setdefault(pan, []).append(i)
        for pan, indices in pan_at_indices.items():
            if len(indices) > 1:
                results.append(_make(
                    "ITR1-R118", False,
                    f"80GGA: Donee PAN '{pan}' appears at positions {indices}. "
                    f"Each PAN must appear at most once.",
                    "schedule_80gga.donee_pan_list",
                ))

    # --- R089-R090: 80GGA cash or non-cash mandatory ---
    if inp.schedule_80gga:
        sgga2 = inp.schedule_80gga
        if sgga2.total_claimed > _z:
            if sgga2.cash_donations == _z and sgga2.non_cash_donations == _z and not sgga2.donee_pan_list:
                results.append(_make(
                    "ITR1-R089", False,
                    "80GGA deduction claimed but no cash/non-cash donation details provided",
                    "schedule_80gga",
                ))

    # ========================================================================
    # SECTION: CBDT Category B — TDS Section Code + Aadhaar Warnings
    # ========================================================================

    # CBDT B1: Aadhaar-PAN linking required
    results.append(_warn(
        "ITR1-B_AADHAAR_PAN_LINK",
        "Linking of Aadhaar and PAN is required as per CBDT Circular 03/2023. "
        "Failure to link may result in PAN becoming inoperative.",
        "aadhaar_number",
    ))

    # CBDT B2: Quoting of Aadhaar in ITR required
    results.append(_warn(
        "ITR1-B_AADHAAR_QUOTE",
        "Quoting of Aadhaar in ITR is mandatory u/s 139(AA) in applicable cases.",
        "aadhaar_number",
    ))

    # TDS section codes that disqualify ITR-1 (special-rate income)
    # CBDT B3: 194B/194BB/194BA/194IA/194IC/194LA/194S in TDS2 → ITR-1 ineligible
    ineligible_sections_tds2_tds3 = {
        "194B", "194BB", "194BA", "194IA", "194IC", "194LA", "194S",
    }
    # CBDT B5: 194E/194LB/194LC/194LBA etc. in TDS2 → NR/foreign income (ITR-1 ineligible)
    nr_sections = {
        "194E", "194LB", "194LC", "194LBA", "195", "196A", "196B", "196C", "196D",
    }
    # CBDT B7: 194Q/194C/194R in TDS2 — ITR-1 not applicable (business income TDS)
    business_sections = {"194Q", "194C", "194R"}

    for i, e in enumerate(inp.tds2_entries or []):
        tds_sec = getattr(e, 'tds_section', '') or ''
        if tds_sec in ineligible_sections_tds2_tds3:
            results.append(_warn(
                "ITR1-B_TDS2_INELIGIBLE",
                f"TDS2 entry #{i+1}: Section {tds_sec} indicates special-rate income "
                f"(lottery, horse racing, immovable property purchase, etc.). "
                f"ITR-1 (Sahaj) may not be applicable — consider ITR-2.",
                f"tds2_entries[{i}].tds_section",
            ))
        if tds_sec in nr_sections:
            results.append(_warn(
                "ITR1-B_TDS2_NR_INCOME",
                f"TDS2 entry #{i+1}: Section {tds_sec} indicates non-resident / foreign "
                f"income source. ITR-1 is only for resident individuals. "
                f"Verify residency status; ITR-2/ITR-3 may be required.",
                f"tds2_entries[{i}].tds_section",
            ))
        if tds_sec in business_sections:
            results.append(_warn(
                "ITR1-B_TDS2_BUSINESS",
                f"TDS2 entry #{i+1}: Section {tds_sec} indicates business/professional "
                f"income (contracts, purchases). ITR-1 cannot be used for business income — "
                f"ITR-3 or ITR-4 is applicable.",
                f"tds2_entries[{i}].tds_section",
            ))

    for i, e in enumerate(inp.tds3_entries or []):
        tds_sec = getattr(e, 'tds_section', '') or ''
        if tds_sec in ineligible_sections_tds2_tds3:
            results.append(_warn(
                "ITR1-B_TDS3_INELIGIBLE",
                f"TDS3 entry #{i+1}: Section {tds_sec} indicates special-rate income. "
                f"ITR-1 (Sahaj) may not be applicable — consider ITR-2.",
                f"tds3_entries[{i}].tds_section",
            ))
        if tds_sec in nr_sections:
            results.append(_warn(
                "ITR1-B_TDS3_NR_INCOME",
                f"TDS3 entry #{i+1}: Section {tds_sec} indicates non-resident / foreign income. "
                f"Verify residency status; ITR-2/ITR-3 may be required.",
                f"tds3_entries[{i}].tds_section",
            ))
        if tds_sec in business_sections:
            results.append(_warn(
                "ITR1-B_TDS3_BUSINESS",
                f"TDS3 entry #{i+1}: Section {tds_sec} indicates business income. "
                f"ITR-3 or ITR-4 is applicable, not ITR-1.",
                f"tds3_entries[{i}].tds_section",
            ))

    # CBDT B9: TDS1 salary TDS ≤ gross salary
    for i, e in enumerate(inp.tds1_entries or []):
        if e.tds_deducted > sal.gross_salary and sal.gross_salary > _z:
            results.append(_warn(
                "ITR1-B_TDS1_EXCEEDS_SALARY",
                f"TDS1 entry #{i+1}: TDS deducted (Rs {e.tds_deducted}) exceeds gross "
                f"salary (Rs {sal.gross_salary}). This suggests misreported income or "
                f"incorrect TDS entry.",
                f"tds1_entries[{i}].tds_deducted",
            ))

    # CBDT B3/B4 also: 194B/194BB etc. in TDS2 → ITR-1 ineligible (summarized)
    if any(getattr(e, 'tds_section', '') in ineligible_sections_tds2_tds3
           for e in (inp.tds2_entries or [])):
        results.append(_warn(
            "ITR1-B_ITR1_INELIGIBLE",
            "One or more TDS entries indicate special-rate income (194B/194BB/194IA etc.). "
            "ITR-1 (Sahaj) is not designed for such income. The return may be considered "
            "defective u/s 139(9).",
            "tds2_entries",
        ))

    # CBDT B7/B8: 194Q/194C/194R → business income → ITR-1 not applicable
    if any(getattr(e, 'tds_section', '') in business_sections
           for e in (inp.tds2_entries or []) + (inp.tds3_entries or [])):
        results.append(_warn(
            "ITR1-B_BUSINESS_INCOME",
            "One or more TDS entries indicate business/professional income "
            "(section 194C/194Q/194R). ITR-1 cannot be used for business income. "
            "ITR-3 or ITR-4 must be filed instead.",
            "tds2_entries / tds3_entries",
        ))

    return results
