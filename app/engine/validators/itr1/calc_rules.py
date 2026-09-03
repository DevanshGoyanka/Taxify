"""
ITR-1 calculation validation rules (post-computation).

These rules mirror CBDT Category A rules for AY 2026-27 that check
computed values AFTER the ITR-1 calculator (compute_itr1) has produced
an ITR1Result.  Rules referencing fields not present in the current schema
or requiring schedule sub-structures are marked informational (Severity.D).

Input: ITR1Input (pre-computation data) + ITR1Result (computed values).
"""

from __future__ import annotations

from decimal import Decimal
from app.schemas.itr1 import ITR1Input, AgeBracket, TaxRegime, PropertyType
from app.engine.calculators.itr1 import ITR1Result
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


def _eq(a: Decimal, b: Decimal, tolerance: Decimal = _z) -> bool:
    """Return True if two Decimals are equal within a small absolute tolerance."""
    return abs(a - b) <= tolerance


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_itr1_calculation(inp: ITR1Input, result: ITR1Result) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    ch6a = inp.deductions_chapter6a
    sal = inp.salary_income
    hp = inp.house_property_income
    osi = inp.other_sources_income
    cg = inp.capital_gains
    is_new = inp.tax_regime == TaxRegime.NEW
    is_old = inp.tax_regime == TaxRegime.OLD
    is_senior = inp.age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)

    # Shortcuts into result for readability
    gti = result.gross_total_income
    ded_total = result.deductions_total
    ti = result.taxable_income
    cg_112a = result.capital_gains_112a

    # ===================================================================
    # SECTION: Arithmetic Consistency — GTI, Income Heads
    # ===================================================================

    # Rule 22: GTI must equal sum of income heads
    expected_gti = result.salary_income + result.house_property_income + result.other_sources_income + cg_112a
    if not _eq(gti, expected_gti):
        results.append(_make(
            "ITR1-R022", False,
            f"Gross Total Income mismatch: computed={gti}, "
            f"expected Salary({result.salary_income}) + HP({result.house_property_income}) "
            f"+ OS({result.other_sources_income}) + LTCG({cg_112a}) = {expected_gti}",
            "gross_total_income",
            expected=str(expected_gti), actual=str(gti),
        ))

    # Rule 160: New regime HP loss → GTI = salary + OS only (HP loss disallowed)
    if is_new and result.hp_loss_disallowed > 0:
        expected_new_gti = result.salary_income + result.other_sources_income + cg_112a
        if not _eq(gti, expected_new_gti):
            results.append(_make(
                "ITR1-R160", False,
                f"New regime with HP loss disallowed: GTI (Rs {gti}) should equal "
                f"Salary ({result.salary_income}) + OS ({result.other_sources_income}) "
                f"+ LTCG 112A ({cg_112a}) = {expected_new_gti}. "
                f"HP loss of Rs {result.hp_loss_disallowed} must be excluded.",
                "gross_total_income",
            ))

    # Rule 174: New regime with positive HP income → GTI must include all heads
    if is_new and result.house_property_income > 0:
        expected_new_pos = (
            result.salary_income + result.house_property_income
            + result.other_sources_income + cg_112a
        )
        if not _eq(gti, expected_new_pos):
            results.append(_make(
                "ITR1-R174", False,
                f"New regime GTI mismatch (positive HP): computed={gti}, "
                f"expected={expected_new_pos}",
                "gross_total_income",
            ))

    # Rule 20: If tax computed, GTI must be > 0
    if result.gross_tax_liability > 0 and gti <= _z:
        results.append(_make(
            "ITR1-R020", False,
            f"Tax liability of Rs {result.gross_tax_liability} is computed but "
            f"Gross Total Income is Rs {gti}. Tax cannot be computed with "
            f"GTI <= 0.",
            "gross_total_income",
            expected="> 0", actual=str(gti)))

    # Rule 21: If taxes paid disclosed, income + tax details must be present
    if result.total_taxes_paid > _z and gti <= _z and result.gross_tax_liability <= _z:
        results.append(_make(
            "ITR1-R021", False,
            f"Total taxes paid (Rs {result.total_taxes_paid}) are disclosed but "
            f"Gross Total Income (Rs {gti}) and tax liability "
            f"(Rs {result.gross_tax_liability}) are absent.",
            "total_taxes_paid",
            expected="Income > 0 or tax computed", actual="Neither"))

    # ===================================================================
    # SECTION: Deductions — Total, Caps, GTI Relationship
    # ===================================================================

    # Rule 24: Total income = GTI - deductions (floor 0)
    expected_ti_before_round = max(_z, gti - ded_total)
    if abs(expected_ti_before_round - ti) > Decimal("9"):
        results.append(_make(
            "ITR1-R024", False,
            f"Total Income mismatch: computed taxable_income={ti}, "
            f"expected GTI({gti}) - Deductions({ded_total}) = {expected_ti_before_round}",
            "taxable_income",
        ))

    # Rule 18: Deductions cannot exceed GTI
    if ded_total > gti:
        results.append(_make(
            "ITR1-R018", False,
            f"Chapter VI-A deductions (Rs {ded_total}) exceed Gross Total Income (Rs {gti})",
            "deductions_total",
        ))

    # Rule 17: Total VIA = sum of individual deductions (schedules check)
    schedules = result.schedules if result.schedules else {}
    ded_sched = schedules.get("deductions") if isinstance(schedules, dict) else None
    if ded_sched and hasattr(ded_sched, "breakdown") and ded_sched.breakdown:
        breakdown_sum = sum(ded_sched.breakdown.values(), _z)
        if "80C+80CCC+80CCD(1)" in ded_sched.breakdown:
            breakdown_sum -= (
                ded_sched.breakdown.get("80CCC", _z)
                + ded_sched.breakdown.get("80CCD(1)", _z)
            )
        if not _eq(ded_total, breakdown_sum, Decimal("1")):
            results.append(_make(
                "ITR1-R017", False,
                f"Total VI-A deductions (Rs {ded_total}) does not match sum of "
                f"individual deductions in breakdown (Rs {breakdown_sum})",
                "deductions_total",
            ))

    # ===================================================================
    # SECTION: Tax Computation — Tax, Rebate, Surcharge, Cess
    # ===================================================================

    # Rule 25: Tax after rebate = tax before rebate - rebate (floor 0)
    expected_tax_after = max(_z, result.tax_before_rebate - result.rebate_87a)
    if not _eq(result.tax_after_rebate, expected_tax_after):
        results.append(_make(
            "ITR1-R025", False,
            f"Tax after rebate mismatch: {result.tax_after_rebate} != "
            f"Tax before rebate({result.tax_before_rebate}) - "
            f"Rebate({result.rebate_87a}) = {expected_tax_after}",
            "tax_after_rebate",
        ))

    # Rule 26: Total tax + cess = tax after rebate + surcharge + HEC
    expected_gross = result.tax_after_rebate + result.surcharge + result.health_education_cess
    if not _eq(result.gross_tax_liability, expected_gross, Decimal("1")):
        results.append(_make(
            "ITR1-R026", False,
            f"Gross tax liability mismatch: {result.gross_tax_liability} != "
            f"Tax after rebate({result.tax_after_rebate}) + "
            f"Surcharge({result.surcharge}) + HEC({result.health_education_cess}) = "
            f"{expected_gross}",
            "gross_tax_liability",
        ))

    # Rule 27: Total Tax Fees Interest = tax+cess+interest+fees - relief
    # CBDT rule 27: Total Tax, Fees & Interest = Gross Tax & Cess + Interest
    # u/s 234A + 234B + 234C + Fees u/s 234I + Fees u/s 234F − Relief u/s 89
    expected_ttfi = (
        result.gross_tax_liability
        + result.total_interest
        + result.fees_234i
        + result.late_fee_234f
        - result.relief_89
    )
    if not _eq(result.net_tax_liability, expected_ttfi, Decimal("10")):
        results.append(_make(
            "ITR1-R027", False,
            f"Total Tax Fees Interest mismatch: {result.net_tax_liability} != "
            f"Gross tax({result.gross_tax_liability}) + "
            f"Interest({result.total_interest}) + Fees 234I({result.fees_234i}) "
            f"+ Fees 234F({result.late_fee_234f}) - "
            f"Relief({result.relief_89}) = {expected_ttfi}",
            "net_tax_liability",
        ))

    # Rule 28: Total interest+fees = 234A + 234B + 234C + 234F + 234I
    expected_interest = (
        result.interest_234a
        + result.interest_234b
        + result.interest_234c
        + result.late_fee_234f
        + result.fees_234i
    )
    total_interest_plus_fees = result.total_interest + result.late_fee_234f + result.fees_234i
    if not _eq(total_interest_plus_fees, expected_interest, Decimal("1")):
        results.append(_make(
            "ITR1-R028", False,
            f"Total Interest+Late Fee mismatch: "
            f"total_interest+late_fee+234i={total_interest_plus_fees} != "
            f"234A({result.interest_234a})+234B({result.interest_234b})+"
            f"234C({result.interest_234c})+234F({result.late_fee_234f})+"
            f"234I({result.fees_234i}) = {expected_interest}",
            "total_interest",
        ))

    # Rule 140: Total Tax Fee Interest = Balance Tax after Relief + Total Interest Fee
    balance_after_relief = result.gross_tax_liability - result.relief_89
    expected_140 = balance_after_relief + result.total_interest + result.late_fee_234f + result.fees_234i
    if not _eq(result.net_tax_liability, expected_140, Decimal("10")):
        results.append(_make(
            "ITR1-R140", False,
            f"Total Tax Fee Interest mismatch (Rule 140): {result.net_tax_liability} != "
            f"Balance after relief({balance_after_relief}) + "
            f"Total Interest Fee({result.total_interest + result.late_fee_234f + result.fees_234i}) = "
            f"{expected_140}",
            "net_tax_liability",
        ))

    # Rule 23: 87A old regime — income must be <= 5,00,000 for rebate
    if is_old and result.rebate_87a > 0:
        if ti > 500_000:
            results.append(_make(
                "ITR1-R023", False,
                f"87A rebate claimed (Rs {result.rebate_87a}) but total income "
                f"(Rs {ti}) exceeds Rs 5,00,000 limit",
                "rebate_87a",
            ))

    # Rule 192: 87A old regime max Rs 12,500
    if is_old and result.rebate_87a > 12_500:
        results.append(_make(
            "ITR1-R192", False,
            f"87A rebate (Rs {result.rebate_87a}) exceeds maximum Rs 12,500 "
            f"in old regime",
            "rebate_87a",
        ))

    # Rule 191: 87A new regime income cap — enforce
    if is_new and result.rebate_87a > _z:
        income_excl_ltcg = gti - cg_112a
        if income_excl_ltcg > Decimal("1270590"):
            results.append(_make(
                "ITR1-R191", False,
                f"87A rebate (Rs {result.rebate_87a}) claimed in new regime but "
                f"income excluding LTCG u/s 112A (Rs {income_excl_ltcg}) exceeds "
                f"Rs 12,70,590. 87A rebate not available in new regime when income "
                f"exceeds this threshold.",
                "rebate_87a",
                expected="income_excl_ltcg <= 12,70,590", actual=str(income_excl_ltcg)))

    # ===================================================================
    # SECTION: Salary Schedule Checks (from schedules arithmetic)
    # ===================================================================

    sal_sched = schedules.get("salary") if isinstance(schedules, dict) else None

    # Rule 59: Gross salary = 17(1) + 17(2) + 17(3)
    if sal_sched and hasattr(sal_sched, "gross_salary"):
        expected_gross_sal = sal.gross_salary + sal.perquisites_value + sal.profits_in_lieu_of_salary
        if not _eq(sal_sched.gross_salary, expected_gross_sal):
            results.append(_make(
                "ITR1-R059", False,
                f"Gross salary mismatch: computed={sal_sched.gross_salary}, "
                f"expected 17(1)({sal.gross_salary}) + 17(2)({sal.perquisites_value}) "
                f"+ 17(3)({sal.profits_in_lieu_of_salary}) = {expected_gross_sal}",
                "salary_income",
            ))

    # Rule 60: Net salary = gross - exempt allowances
    if sal_sched and hasattr(sal_sched, "net_salary") and hasattr(sal_sched, "exempt_allowances"):
        expected_net = sal_sched.gross_salary - sal_sched.exempt_allowances
        if not _eq(sal_sched.net_salary, expected_net, Decimal("1")):
            results.append(_make(
                "ITR1-R060", False,
                f"Net salary mismatch: computed={sal_sched.net_salary}, "
                f"expected Gross({sal_sched.gross_salary}) - "
                f"Exempt({sal_sched.exempt_allowances}) = {expected_net}",
                "salary_income",
            ))

    # Rule 61: Deductions u/s 16 = 16(ia) + 16(ii) + 16(iii)
    if sal_sched and hasattr(sal_sched, "deductions_u16"):
        expected_u16 = (
            sal_sched.standard_deduction
            + sal_sched.entertainment_allowance
            + sal_sched.professional_tax
        )
        if not _eq(sal_sched.deductions_u16, expected_u16):
            results.append(_make(
                "ITR1-R061", False,
                f"Deductions u/s 16 mismatch: computed={sal_sched.deductions_u16}, "
                f"expected 16(ia)({sal_sched.standard_deduction}) + "
                f"16(ii)({sal_sched.entertainment_allowance}) + "
                f"16(iii)({sal_sched.professional_tax}) = {expected_u16}",
                "salary_income",
            ))

    # Rule 62: Income chargeable = net salary - deductions u/s 16
    if sal_sched:
        if hasattr(sal_sched, "income_chargeable") and hasattr(sal_sched, "net_salary") and hasattr(sal_sched, "deductions_u16"):
            expected_chargeable = max(_z, sal_sched.net_salary - sal_sched.deductions_u16)
            if not _eq(sal_sched.income_chargeable, expected_chargeable, Decimal("1")):
                results.append(_make(
                    "ITR1-R062", False,
                    f"Salary income chargeable mismatch: computed={sal_sched.income_chargeable}, "
                    f"expected Net({sal_sched.net_salary}) - Deductions({sal_sched.deductions_u16}) "
                    f"= {expected_chargeable}",
                    "salary_income",
                ))

    # Rule 63: Total exempt allowances cannot exceed gross salary (cannot enforce — no field)
    # Already checked in input_rules for HRA, but general exempt-allowance breakdown
    # not in schema.
    if sal_sched and hasattr(sal_sched, "exempt_allowances") and hasattr(sal_sched, "gross_salary"):
        if sal_sched.exempt_allowances > sal_sched.gross_salary:
            results.append(_make(
                "ITR1-R063", False,
                f"Exempt allowances (Rs {sal_sched.exempt_allowances}) exceed "
                f"Gross Salary (Rs {sal_sched.gross_salary})",
                "salary_income.exempt_allowances",
            ))

    # ===================================================================
    # SECTION: House Property Schedule Checks
    # ===================================================================
    # The ITR-1 calculator stores schedules["hp"] as a list of HPResult
    # objects (one per PropertyDetails row, up to two under the AY 2026-27
    # schema). The legacy single-object path is retained for callers that
    # bypass the multi-property compute path.

    hp_sched_raw = schedules.get("hp") if isinstance(schedules, dict) else None
    if isinstance(hp_sched_raw, list):
        hp_sched_list = hp_sched_raw
    elif hp_sched_raw is None:
        hp_sched_list = []
    else:
        hp_sched_list = [hp_sched_raw]

    hp_input_list = list(inp.house_properties) or ([inp.house_property_income] if inp.house_property_income else [])

    for idx, hp_sched in enumerate(hp_sched_list):
        hp_input = hp_input_list[idx] if idx < len(hp_input_list) else inp.house_property_income
        field_scope = (
            f"house_property_income[{idx}]"
            if len(hp_sched_list) > 1
            else "house_property_income"
        )

        # Rule 46: Balance ALV = GAV - unrealized rent - municipal taxes.
        if hp_input.property_type != PropertyType.SELF_OCCUPIED:
            if all(hasattr(hp_sched, field) for field in (
                "net_annual_value", "gross_annual_value",
                "rent_not_realized", "municipal_taxes",
            )):
                expected_nav = max(
                    _z,
                    hp_sched.gross_annual_value
                    - hp_sched.rent_not_realized
                    - hp_sched.municipal_taxes,
                )
                if not _eq(hp_sched.net_annual_value, expected_nav):
                    results.append(_make(
                        "ITR1-R046", False,
                        f"Balance annual value mismatch (property {idx + 1}): "
                        f"computed={hp_sched.net_annual_value}, "
                        f"expected GAV({hp_sched.gross_annual_value}) - "
                        f"Rent not realized({hp_sched.rent_not_realized}) - "
                        f"Municipal Taxes({hp_sched.municipal_taxes}) = {expected_nav}",
                        field_scope,
                    ))

        # Rule 47: HP income = owned AV - 30% deduction - interest + arrears.
        if hp_input.property_type != PropertyType.SELF_OCCUPIED:
            if all(hasattr(hp_sched, a) for a in ["annual_value_owned", "standard_deduction_30pct", "interest_on_loan", "arrears_unrealised_rent", "income_chargeable"]):
                expected_hp_income = (
                    hp_sched.annual_value_owned
                    - hp_sched.standard_deduction_30pct
                    - hp_sched.interest_on_loan
                    + (hp_sched.arrears_unrealised_rent * Decimal("0.7"))
                )
                if not _eq(hp_sched.income_chargeable, expected_hp_income, Decimal("1")):
                    results.append(_make(
                        "ITR1-R047", False,
                        f"House Property income chargeable mismatch (property {idx + 1}): "
                        f"computed={hp_sched.income_chargeable}, expected "
                        f"owned annual value({hp_sched.annual_value_owned}) - "
                        f"30%({hp_sched.standard_deduction_30pct}) - "
                        f"Interest({hp_sched.interest_on_loan}) + "
                        f"Arrears({hp_sched.arrears_unrealised_rent}) = "
                        f"{expected_hp_income}",
                        field_scope,
                    ))

        # Rule 43: HP standard deduction = 30% of assessee-owned annual value.
        if hp_input.property_type != PropertyType.SELF_OCCUPIED:
            if hasattr(hp_sched, "annual_value_owned") and hasattr(hp_sched, "standard_deduction_30pct"):
                expected_30 = hp_sched.annual_value_owned * Decimal("0.3")
                if not _eq(hp_sched.standard_deduction_30pct, expected_30, Decimal("1")):
                    results.append(_make(
                        "ITR1-R043", False,
                        f"HP 30% standard deduction mismatch (property {idx + 1}): "
                        f"computed={hp_sched.standard_deduction_30pct}, "
                        f"expected 30% of owned annual value"
                        f"({hp_sched.annual_value_owned}) = {expected_30}",
                        field_scope,
                    ))

    # ===================================================================
    # SECTION: Standard Deduction Limits (from schedule values)
    # ===================================================================

    # Rule 112: Old regime standard deduction from salary schedule <= 50,000
    if sal_sched and hasattr(sal_sched, "standard_deduction"):
        if is_old and sal_sched.standard_deduction > 50_000:
            results.append(_make(
                "ITR1-R112", False,
                f"Standard deduction old regime (Rs {sal_sched.standard_deduction}) "
                f"exceeds Rs 50,000",
                "salary_income.standard_deduction_claimed",
            ))

    # Rule 215: New regime standard deduction from salary schedule <= 75,000
    if sal_sched and hasattr(sal_sched, "standard_deduction"):
        if is_new and sal_sched.standard_deduction > 75_000:
            results.append(_make(
                "ITR1-R215", False,
                f"Standard deduction new regime (Rs {sal_sched.standard_deduction}) "
                f"exceeds Rs 75,000",
                "salary_income.standard_deduction_claimed",
            ))

    # ===================================================================
    # SECTION: Other Sources — Family Pension 57(iia)
    # ===================================================================

    fp = osi.family_pension_received
    os_sched = schedules.get("os") if isinstance(schedules, dict) else None

    # Rule 53: 57(iia) only if family pension is offered to tax and old regime selected
    if os_sched and hasattr(os_sched, "deduction_57iia"):
        ded_57iia = os_sched.deduction_57iia
        if is_old:
            if ded_57iia > 0 and fp <= 0:
                results.append(_make(
                    "ITR1-R053", False,
                    "57(iia) deduction claimed but family pension is not offered to tax. "
                    "57(iia) is allowed only when family pension is included in "
                    "Other Sources income.",
                    "other_sources_income.family_pension_received",
                ))

        # Rule 54: Old regime 57(iia) <= min(1/3rd FP, 15,000)
        if is_old and ded_57iia > 0 and fp > 0:
            max_fp_old = min(fp / Decimal("3"), Decimal("15000"))
            if ded_57iia > max_fp_old + Decimal("1"):
                results.append(_make(
                    "ITR1-R054", False,
                    f"57(iia) old regime deduction (Rs {ded_57iia}) exceeds limit: "
                    f"min(1/3 of Family Pension = {fp / Decimal('3')}, Rs 15,000) = "
                    f"{max_fp_old}",
                    "other_sources_income.family_pension_received",
                ))

    # Rule 214: New regime 57(iia) up to min(1/3rd FP, 25,000). This
    # correctly matches app/engine/schedules/other_sources.py's own
    # regime-dependent cap (Rs 15,000 old / Rs 25,000 new, both as
    # min(1/3 of FP, cap)) -- confirmed during the ITR-1/ITR-4 tax-
    # calculation-flow audit, which found and fixed a stale version of this
    # same check in ITR-4's calc_rules.py that had NOT kept up with that
    # regime-dependent cap (see ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md).
    if is_new and os_sched and hasattr(os_sched, "deduction_57iia") and os_sched.deduction_57iia > 0:
        if fp > 0:
            max_fp_new = min(fp / Decimal("3"), Decimal("25000"))
            if os_sched.deduction_57iia > max_fp_new + Decimal("1"):
                results.append(_make(
                    "ITR1-R214", False,
                    f"57(iia) new regime deduction (Rs {os_sched.deduction_57iia}) "
                    f"exceeds limit: min(1/3 of FP, Rs 25,000) = {max_fp_new}",
                    "other_sources_income.family_pension_received",
                ))

    # ===================================================================
    # SECTION: Tax Payments — Consistency
    # ===================================================================

    # Rule 104: Total taxes paid = TDS + TCS + advance + self-assessment
    expected_taxes_paid = (
        result.total_tds
        + result.total_tcs
        + result.advance_tax_paid
        + result.self_assessment_tax_paid
    )
    if not _eq(result.total_taxes_paid, expected_taxes_paid, Decimal("1")):
        results.append(_make(
            "ITR1-R104", False,
            f"Total Taxes Paid mismatch: computed={result.total_taxes_paid}, "
            f"expected TDS({result.total_tds}) + TCS({result.total_tcs}) + "
            f"Advance({result.advance_tax_paid}) + "
            f"Self-Assessment({result.self_assessment_tax_paid}) = "
            f"{expected_taxes_paid}",
            "total_taxes_paid",
        ))

    # Rule 105: Refund = Taxes Paid - Tax Liability
    if result.refund_due > 0:
        expected_refund = result.total_taxes_paid - result.net_tax_liability
        if not _eq(result.refund_due, expected_refund, Decimal("10")):
            results.append(_make(
                "ITR1-R105", False,
                f"Refund due mismatch: computed={result.refund_due}, "
                f"expected Taxes Paid({result.total_taxes_paid}) - "
                f"Tax Liability({result.net_tax_liability}) = {expected_refund}",
                "refund_due",
            ))

    # Rule 106: Tax payable = Tax Liability - Taxes Paid
    if result.balance_payable > 0:
        expected_payable = result.net_tax_liability - result.total_taxes_paid
        if not _eq(result.balance_payable, expected_payable, Decimal("10")):
            results.append(_make(
                "ITR1-R106", False,
                f"Balance payable mismatch: computed={result.balance_payable}, "
                f"expected Tax Liability({result.net_tax_liability}) - "
                f"Taxes Paid({result.total_taxes_paid}) = {expected_payable}",
                "balance_payable",
            ))

    # ===================================================================
    # SECTION: LTCG 112A
    # ===================================================================

    # Rule 117: Total income excluding LTCG <= 50 lakh
    income_excl_ltcg = gti - cg_112a
    if income_excl_ltcg > 5_000_000:
        results.append(_make(
            "ITR1-R117", False,
            f"Total income excluding LTCG 112A (Rs {income_excl_ltcg}) exceeds "
            f"Rs 50 lakh ITR-1 eligibility limit",
            "gross_total_income",
        ))

    # Rule 292: LTCG 112A = GTI_incl_LTCG - GTI_excl_LTCG (informational)
    # We don't have a separate GTI_excl_LTCG field in the result, but the
    # relationship is tautological with above check.
    results.append(_info(
        "ITR1-R292",
        "LTCG u/s 112A must equal difference between GTI including LTCG and "
        "GTI excluding LTCG. Schema does not separately expose both GTI "
        "values; verified indirectly via GTI = sum of heads (Rule 22).",
        "capital_gains_112a",
    ))

    # Rule 138: 80GG requires Form 10BA
    if ch6a and is_old and ch6a.amount_80gg > 0:
        if not inp.form_10ba_filed:
            results.append(_make(
                "ITR1-R138c", False,
                "80GG deduction claimed but Form 10BA (declaration for rent paid) not filed. "
                "Form 10BA is mandatory for 80GG deduction.",
                "form_10ba_filed",
            ))
        adjusted_gti_for_80gg = max(_z, gti - cg_112a - ded_total + ch6a.amount_80gg)
        limit_80gg = min(Decimal("60000"), adjusted_gti_for_80gg * Decimal("0.25"))
        if ch6a.amount_80gg > limit_80gg + Decimal("1"):
            results.append(_make(
                "ITR1-R114", False,
                f"80GG deduction (Rs {ch6a.amount_80gg}) exceeds limit: "
                f"min(Rs 60,000, 25% of adjusted GTI = {limit_80gg})",
                "deductions_chapter6a.amount_80gg",
            ))

    # ===================================================================
    # SECTION: Cross-Schedule Consistency — Enforced (R241-251)
    # ===================================================================
    # Verify that VIA deduction amounts match corresponding schedule totals
    # for sections where schedule detail is available in the input schema.
    ded_result = schedules.get("deductions") if isinstance(schedules, dict) else None
    ded_breakdown = ded_result.breakdown if ded_result else {}

    if ch6a:
        # 80D: VIA amount vs Schedule 80D total
        if ch6a.amount_80d_self_family > _z or ch6a.amount_80d_parents > _z:
            if inp.schedule_80d:
                sd = inp.schedule_80d
                d_via_total = (
                    ch6a.amount_80d_self_family
                    + ch6a.amount_80d_parents
                    + ch6a.amount_80d_preventive_self
                    + ch6a.amount_80d_preventive_parents
                )
                # Schedule total = premiums + preventive checkup (but limited by caps)
                # The engine-computed total is in the breakdown
                eng_80d = ded_breakdown.get("80D", _z)
                if d_via_total != eng_80d and eng_80d > _z:
                    results.append(_make(
                        "ITR1-R241b", False,
                        f"80D VIA total (Rs {d_via_total}) does not match engine-computed "
                        f"eligible amount (Rs {eng_80d})",
                        "deductions_chapter6a",
                        expected=str(eng_80d), actual=str(d_via_total)))

        # 80G: VIA amount vs Schedule 80G eligible
        if ch6a.amount_80g > _z:
            if inp.schedule_80g:
                sg = inp.schedule_80g
                eng_80g = ded_breakdown.get("80G", _z)
                if ch6a.amount_80g > eng_80g and eng_80g > _z:
                    results.append(_make(
                        "ITR1-R242", False,
                        f"80G VIA claimed (Rs {ch6a.amount_80g}) exceeds engine-computed "
                        f"eligible amount (Rs {eng_80g})",
                        "deductions_chapter6a.amount_80g",
                        expected=f"<= {eng_80g}", actual=str(ch6a.amount_80g)))

        # 80EE: VIA amount vs loan_details_80ee
        if ch6a.amount_80ee > _z and inp.loan_details_80ee:
            eng_80ee = ded_breakdown.get("80EE", _z)
            if ch6a.amount_80ee > eng_80ee and eng_80ee > _z:
                results.append(_make(
                    "ITR1-R243", False,
                    f"80EE VIA claimed (Rs {ch6a.amount_80ee}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80ee})",
                    "deductions_chapter6a.amount_80ee",
                    expected=f"<= {eng_80ee}", actual=str(ch6a.amount_80ee)))

        # 80EEA: VIA amount vs loan_details_80eea
        if ch6a.amount_80eea > _z and inp.loan_details_80eea:
            eng_80eea = ded_breakdown.get("80EEA", _z)
            if ch6a.amount_80eea > eng_80eea and eng_80eea > _z:
                results.append(_make(
                    "ITR1-R244", False,
                    f"80EEA VIA claimed (Rs {ch6a.amount_80eea}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80eea})",
                    "deductions_chapter6a.amount_80eea",
                    expected=f"<= {eng_80eea}", actual=str(ch6a.amount_80eea)))

        # 80EEB: VIA amount vs loan_details_80eeb
        if ch6a.amount_80eeb > _z and inp.loan_details_80eeb:
            eng_80eeb = ded_breakdown.get("80EEB", _z)
            if ch6a.amount_80eeb > eng_80eeb and eng_80eeb > _z:
                results.append(_make(
                    "ITR1-R245", False,
                    f"80EEB VIA claimed (Rs {ch6a.amount_80eeb}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80eeb})",
                    "deductions_chapter6a.amount_80eeb",
                    expected=f"<= {eng_80eeb}", actual=str(ch6a.amount_80eeb)))

        # 80DD: VIA amount vs engine-computed eligible
        if ch6a.amount_80dd > _z:
            eng_80dd = ded_breakdown.get("80DD", _z)
            if ch6a.amount_80dd > eng_80dd and eng_80dd > _z:
                results.append(_make(
                    "ITR1-R246", False,
                    f"80DD VIA claimed (Rs {ch6a.amount_80dd}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80dd})",
                    "deductions_chapter6a.amount_80dd",
                    expected=f"<= {eng_80dd}", actual=str(ch6a.amount_80dd)))

        # 80DDB: VIA amount vs engine-computed eligible
        if ch6a.amount_80ddb > _z:
            eng_80ddb = ded_breakdown.get("80DDB", _z)
            if ch6a.amount_80ddb > eng_80ddb and eng_80ddb > _z:
                results.append(_make(
                    "ITR1-R247", False,
                    f"80DDB VIA claimed (Rs {ch6a.amount_80ddb}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80ddb})",
                    "deductions_chapter6a.amount_80ddb",
                    expected=f"<= {eng_80ddb}", actual=str(ch6a.amount_80ddb)))

        # 80U: VIA amount vs engine-computed eligible
        if ch6a.amount_80u > _z:
            eng_80u = ded_breakdown.get("80U", _z)
            if ch6a.amount_80u > eng_80u and eng_80u > _z:
                results.append(_make(
                    "ITR1-R248", False,
                    f"80U VIA claimed (Rs {ch6a.amount_80u}) exceeds engine-computed "
                    f"eligible amount (Rs {eng_80u})",
                    "deductions_chapter6a.amount_80u",
                    expected=f"<= {eng_80u}", actual=str(ch6a.amount_80u)))

    # ===================================================================
    # SECTION: Rules 272-291: Eligible <= User-Entered Amount — Enforced
    # ===================================================================
    # The deduction engine computes eligible amounts stored in 
    # result.schedules["deductions"].breakdown. Each section's engine-computed
    # eligible must not exceed the user-entered VIA amount.
    if ch6a and ded_breakdown:
        # Map of section codes to (ch6a_field, field_path)
        section_map = [
            ("80C", ch6a.amount_80c, "deductions_chapter6a.amount_80c"),
            ("80CCC", ch6a.amount_80ccc, "deductions_chapter6a.amount_80ccc"),
            ("80CCD1", ch6a.amount_80ccd1, "deductions_chapter6a.amount_80ccd1"),
            ("80CCD1B", ch6a.amount_80ccd1b, "deductions_chapter6a.amount_80ccd1b"),
            ("80CCD2", ch6a.amount_80ccd2, "deductions_chapter6a.amount_80ccd2"),
            ("80CCH", ch6a.amount_80cch, "deductions_chapter6a.amount_80cch"),
            ("80D", (
                ch6a.amount_80d_self_family
                + ch6a.amount_80d_parents
                + ch6a.amount_80d_preventive_self
                + ch6a.amount_80d_preventive_parents
            ), "deductions_chapter6a"),
            ("80DD", ch6a.amount_80dd, "deductions_chapter6a.amount_80dd"),
            ("80DDB", ch6a.amount_80ddb, "deductions_chapter6a.amount_80ddb"),
            ("80E", ch6a.amount_80e, "deductions_chapter6a.amount_80e"),
            ("80EE", ch6a.amount_80ee, "deductions_chapter6a.amount_80ee"),
            ("80EEA", ch6a.amount_80eea, "deductions_chapter6a.amount_80eea"),
            ("80EEB", ch6a.amount_80eeb, "deductions_chapter6a.amount_80eeb"),
            ("80G", ch6a.amount_80g, "deductions_chapter6a.amount_80g"),
            ("80GG", ch6a.amount_80gg, "deductions_chapter6a.amount_80gg"),
            ("80TTA", ch6a.amount_80tta, "deductions_chapter6a.amount_80tta"),
            ("80TTB", ch6a.amount_80ttb, "deductions_chapter6a.amount_80ttb"),
            ("80U", ch6a.amount_80u, "deductions_chapter6a.amount_80u"),
        ]
        for sec_code, user_amount, field_path in section_map:
            eng_eligible = ded_breakdown.get(sec_code, _z)
            if eng_eligible > _z and user_amount > eng_eligible:
                results.append(_make(
                    f"ITR1-R272{sec_code}",
                    False,
                    f"{sec_code}: user-entered VIA amount (Rs {user_amount}) exceeds "
                    f"engine-computed eligible amount (Rs {eng_eligible})",
                    field_path,
                    expected=f"<= {eng_eligible}", actual=str(user_amount)))

    # ===================================================================
    # SECTION: Informational Rules (filing-level, not computable)
    # ===================================================================

    # Rule 126: Return u/s 142(1) cannot file u/s 139
    results.append(_info(
        "ITR1-R126",
        "If original return filed u/s 142(1), taxpayer cannot file u/s 139. "
        "Checked at e-Filing portal upload level.",
    ))

    # Rule 152: Once 148 proceeding initiated, no other return u/s 139
    results.append(_info(
        "ITR1-R152",
        "Once proceeding initiated u/s 148, no other return can be filed u/s 139. "
        "Checked at e-Filing portal upload level.",
    ))

    # Rules 19, 212: PAN/Aadhaar match at portal level (informational)
    results.append(_info(
        "ITR1-R019",
        "Name must match PAN database. Verified at e-Filing upload.",
    ))
    results.append(_info(
        "ITR1-R212",
        "Aadhaar number must match PAN profile. Verified at e-Filing upload.",
    ))

    return results
