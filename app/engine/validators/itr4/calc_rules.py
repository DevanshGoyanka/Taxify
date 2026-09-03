"""
ITR-4 calculation validation rules (post-computation arithmetic, limits, regime).

These run AFTER compute() has produced an ITR4Result dataclass.
They verify arithmetic consistency, statutory limits, and cross-schedule
integrity, most of it internal to this calculator rather than official
CBDT-numbered rules on user input (input_rules.py is the module that
implements those). Rule IDs use an "ITR4-C###" (Calculation) namespace,
distinct from input_rules.py's "ITR4-R###" (official Rule) namespace, even
where a check's inline comment cites a nearby official rule number for
context -- the two files' numbering are independent sequences that used to
collide by coincidence before this split (found during the ITR-4 duplicate
rule-ID audit).
"""

from __future__ import annotations

from decimal import Decimal
from app.schemas.itr4 import ITR4Input, PresumptiveScheme
from app.schemas.itr1 import AgeBracket, TaxRegime, PropertyType
from app.engine.calculators.itr4 import ITR4Result
from app.engine.validators.base import ValidationResult, Severity


# ── Helpers ─────────────────────────────────────────��────────────────────────

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


# ── Main entry point ─────────────────────────────────────────────────────────

def validate_itr4_calculation(inp: ITR4Input, result: ITR4Result) -> list[ValidationResult]:
    """Run ALL ITR-4 post-computation validation rules."""
    results: list[ValidationResult] = []
    z = Decimal("0")
    ch6a = inp.deductions_chapter6a
    is_new = inp.tax_regime == TaxRegime.NEW
    is_old = inp.tax_regime == TaxRegime.OLD
    is_senior = inp.age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    sal = inp.salary_income
    hp = inp.house_property_income

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Arithmetic Consistency
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 49: GTI = sum of all income heads
    expected_gti = (
        result.presumptive_income
        + result.salary_income
        + result.house_property_income
        + result.other_sources_income
        + result.capital_gains_112a
    )
    if result.gross_total_income != expected_gti:
        results.append(_make(
            "ITR4-C049", False,
            f"Gross Total Income mismatch: computed={result.gross_total_income}, "
            f"sum of heads={expected_gti}",
            "gross_total_income",
            expected=str(expected_gti), actual=str(result.gross_total_income)))

    # Rule 197: New regime GTI excludes negative HP (HP loss cannot be set off)
    if is_new and result.house_property_income < z:
        expected_gti_new = (
            result.presumptive_income
            + result.salary_income
            + max(z, result.house_property_income)  # HP loss excluded
            + result.other_sources_income
            + result.capital_gains_112a
        )
        if result.gross_total_income != expected_gti_new:
            results.append(_make(
                "ITR4-C197", False,
                f"New regime: negative HP income (Rs {result.house_property_income}) "
                f"must be excluded from GTI. GTI should be Rs {expected_gti_new}, "
                f"not Rs {result.gross_total_income}",
                "gross_total_income",
                expected=str(expected_gti_new), actual=str(result.gross_total_income)))

    # Rule 46: Total income (taxable) = GTI - Chapter VI-A deductions (rounded to nearest 10)
    raw_ti = max(z, result.gross_total_income - result.deductions_total)
    if abs(raw_ti - result.taxable_income) > Decimal("9"):
        results.append(_make(
            "ITR4-C046", False,
            f"Total income (taxable) mismatch: {result.taxable_income} does not "
            f"equal GTI ({result.gross_total_income}) - deductions "
            f"({result.deductions_total}) = {raw_ti}",
            "taxable_income",
            expected=f"~{raw_ti}", actual=str(result.taxable_income)))

    # Rule 52: Tax after rebate = Tax before rebate - Rebate u/s 87A
    expected_tax_after = max(z, result.tax_before_rebate - result.rebate_87a)
    if result.tax_after_rebate != expected_tax_after:
        results.append(_make(
            "ITR4-C052", False,
            f"Tax after rebate mismatch: {result.tax_after_rebate} != "
            f"tax_before_rebate ({result.tax_before_rebate}) - "
            f"rebate ({result.rebate_87a}) = {expected_tax_after}",
            "tax_after_rebate",
            expected=str(expected_tax_after), actual=str(result.tax_after_rebate)))

    # Rule 53: Gross tax liability = Tax after rebate + Surcharge + Health & Education Cess
    expected_gross = result.tax_after_rebate + result.surcharge + result.health_education_cess
    if abs(result.gross_tax_liability - expected_gross) > Decimal("1"):
        results.append(_make(
            "ITR4-C053", False,
            f"Gross tax liability mismatch: {result.gross_tax_liability} != "
            f"tax_after_rebate ({result.tax_after_rebate}) + "
            f"surcharge ({result.surcharge}) + "
            f"cess ({result.health_education_cess}) = {expected_gross}",
            "gross_tax_liability",
            expected=str(expected_gross), actual=str(result.gross_tax_liability)))

    # Rule 54: Net tax liability is the pre-payment liability. Tax credits and
    # challans are reconciled separately into balance payable / refund.
    expected_net = (result.gross_tax_liability + result.total_interest
                    + result.late_fee_234f + result.fees_234i - result.relief_89)
    if abs(result.net_tax_liability - expected_net) > Decimal("10"):
        results.append(_make(
            "ITR4-C054", False,
            f"Net tax liability mismatch: {result.net_tax_liability} != "
            f"{expected_net}",
            "net_tax_liability",
            expected=str(expected_net), actual=str(result.net_tax_liability)))

    # Rule 19: Chapter VI-A deductions cannot exceed GTI
    if result.deductions_total > result.gross_total_income:
        results.append(_make(
            "ITR4-C019", False,
            f"Chapter VI-A deductions ({result.deductions_total}) exceed "
            f"Gross Total Income ({result.gross_total_income})",
            "deductions_total",
            expected=f"<= {result.gross_total_income}",
            actual=str(result.deductions_total)))

    # Rule 56: Total tax payable = Slab tax + Special rate tax
    expected_tax = result.slab_tax + result.special_rate_tax
    if result.tax_before_rebate != expected_tax:
        results.append(_make(
            "ITR4-C056", False,
            f"Total tax before rebate ({result.tax_before_rebate}) != "
            f"slab tax ({result.slab_tax}) + special rate tax "
            f"({result.special_rate_tax}) = {expected_tax}",
            "tax_before_rebate",
            expected=str(expected_tax), actual=str(result.tax_before_rebate)))

    # Rule 105: Health & Education Cess = 4% of (tax after rebate + surcharge)
    expected_cess = (result.tax_after_rebate + result.surcharge) * Decimal("0.04")
    if abs(result.health_education_cess - expected_cess) > Decimal("1"):
        results.append(_make(
            "ITR4-C105", False,
            f"HEC mismatch: {result.health_education_cess} != 4% of "
            f"({result.tax_after_rebate} + {result.surcharge}) = {expected_cess}",
            "health_education_cess",
            expected=str(expected_cess), actual=str(result.health_education_cess)))

    # Rule 106: Total interest = 234A + 234B + 234C
    expected_interest = result.interest_234a + result.interest_234b + result.interest_234c
    if result.total_interest != expected_interest:
        results.append(_make(
            "ITR4-C106", False,
            f"Total interest ({result.total_interest}) != 234A ({result.interest_234a}) "
            f"+ 234B ({result.interest_234b}) + 234C ({result.interest_234c}) "
            f"= {expected_interest}",
            "total_interest",
            expected=str(expected_interest), actual=str(result.total_interest)))

    # Rule 104: Tax payable / refund = taxes paid - liability
    if result.balance_payable > z:
        expected_payable = abs(result.total_taxes_paid
                               - (result.gross_tax_liability + result.total_interest
                                  + result.late_fee_234f))
        if abs(result.balance_payable - expected_payable) > Decimal("10"):
            results.append(_make(
                "ITR4-C104a", False,
                f"Balance payable ({result.balance_payable}) != "
                f"taxes paid ({result.total_taxes_paid}) - "
                f"total liability",
                "balance_payable",
                expected=f"~{expected_payable}", actual=str(result.balance_payable)))

    if result.refund_due > z:
        expected_refund = abs(result.total_taxes_paid
                              - (result.gross_tax_liability + result.total_interest
                                 + result.late_fee_234f))
        if abs(result.refund_due - expected_refund) > Decimal("10"):
            results.append(_make(
                "ITR4-C104b", False,
                f"Refund due ({result.refund_due}) != "
                f"taxes paid ({result.total_taxes_paid}) - "
                f"total liability",
                "refund_due",
                expected=f"~{expected_refund}", actual=str(result.refund_due)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Schedule Cross-Consistency
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 2: GTI business income = Schedule BP presumptive income
    pres_sched = result.schedules.get("presumptive")
    if pres_sched and result.presumptive_income != pres_sched.total_presumptive_income:
        results.append(_make(
            "ITR4-C002", False,
            f"Presumptive income in GTI ({result.presumptive_income}) != "
            f"Schedule BP total ({pres_sched.total_presumptive_income})",
            "presumptive_income",
            expected=str(pres_sched.total_presumptive_income),
            actual=str(result.presumptive_income)))

    # Rule 3: Salary income in GTI = Schedule S income chargeable
    sal_sched = result.schedules.get("salary")
    if sal_sched:
        if result.salary_income != sal_sched.income_chargeable:
            results.append(_make(
                "ITR4-C003", False,
                f"Salary income in GTI ({result.salary_income}) != "
                f"Schedule S chargeable ({sal_sched.income_chargeable})",
                "salary_income",
                expected=str(sal_sched.income_chargeable),
                actual=str(result.salary_income)))

    # Rule 4: HP income in GTI = Schedule HP income chargeable
    hp_sched = result.schedules.get("hp")
    if hp_sched:
        if result.house_property_income != hp_sched.income_chargeable:
            results.append(_make(
                "ITR4-C004", False,
                f"HP income in GTI ({result.house_property_income}) != "
                f"Schedule HP chargeable ({hp_sched.income_chargeable})",
                "house_property_income",
                expected=str(hp_sched.income_chargeable),
                actual=str(result.house_property_income)))

    # Rule 6: OS income in GTI = Schedule OS income chargeable
    os_sched = result.schedules.get("os")
    if os_sched:
        if result.other_sources_income != os_sched.income_chargeable:
            results.append(_make(
                "ITR4-C006", False,
                f"Other sources income in GTI ({result.other_sources_income}) != "
                f"Schedule OS chargeable ({os_sched.income_chargeable})",
                "other_sources_income",
                expected=str(os_sched.income_chargeable),
                actual=str(result.other_sources_income)))

    # Rule 7: Total VI-A deductions = Schedule VIA total
    ded_sched = result.schedules.get("deductions")
    if ded_sched and result.deductions_total != ded_sched.total:
        results.append(_make(
            "ITR4-C007", False,
            f"Chapter VI-A in GTI ({result.deductions_total}) != "
            f"Schedule VIA total ({ded_sched.total})",
            "deductions_total",
            expected=str(ded_sched.total), actual=str(result.deductions_total)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Presumptive Income Checks
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 5: 44AD presumed income >= 6% digital + 8% cash
    pres_sched = result.schedules.get("presumptive")
    if inp.business_income_44ad:
        ad = inp.business_income_44ad
        min_digital = (
            ad.digital_turnover + ad.other_mode_turnover
        ) * Decimal("0.06")
        min_cash = ad.cash_turnover * Decimal("0.08")
        min_total = min_digital + min_cash
        actual_44ad = pres_sched.income_44ad if pres_sched else z
        if actual_44ad < min_total:
            results.append(_make(
                "ITR4-C005", False,
                f"44AD presumptive income ({actual_44ad}) is below "
                f"statutory minimum: 6% of digital ({min_digital}) + "
                f"8% of cash ({min_cash}) = {min_total}",
                "presumptive_income",
                expected=f">= {min_total}", actual=str(actual_44ad)))

    # Rule 14: 44ADA >= 50% of gross professional receipts
    if inp.professional_income_44ada:
        ada = inp.professional_income_44ada
        min_ada = ada.gross_receipts * Decimal("0.50")
        actual_44ada = pres_sched.income_44ada if pres_sched else z
        if actual_44ada < min_ada:
            results.append(_make(
                "ITR4-C014", False,
                f"44ADA presumptive income ({actual_44ada}) is below "
                f"50% of gross receipts ({min_ada})",
                "presumptive_income",
                expected=f">= {min_ada}", actual=str(actual_44ada)))

    # Rule 136: 44AE per-vehicle minimum
    if inp.goods_carriage_44ae:
        ae = inp.goods_carriage_44ae
        expected_44ae = z
        for v in ae.vehicles:
            if v.is_heavy_goods_vehicle:
                wt = v.gross_vehicle_weight_tons or z
                expected_44ae += Decimal("1000") * wt * Decimal(v.months_owned)
            else:
                expected_44ae += Decimal("7500") * Decimal(v.months_owned)
        actual_44ae = pres_sched.income_44ae if pres_sched else z
        if actual_44ae < expected_44ae:
            results.append(_make(
                "ITR4-C136", False,
                f"44AE presumptive income ({actual_44ae}) below "
                f"per-vehicle statutory minimum ({expected_44ae})",
                "presumptive_income",
                expected=f">= {expected_44ae}", actual=str(actual_44ae)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: ITR-4 Eligibility
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 267: Total income excluding LTCG 112A <= Rs 50 lakh
    income_excl_ltcg = result.gross_total_income - result.capital_gains_112a
    if income_excl_ltcg > Decimal("5000000"):
        results.append(_make(
            "ITR4-C267", False,
            f"Total income excluding LTCG 112A ({income_excl_ltcg}) exceeds "
            f"Rs 50 lakh ITR-4 filing limit. File ITR-3.",
            "gross_total_income",
            expected="<= 5000000", actual=str(income_excl_ltcg)))

    # Rule 268: Total income <= Rs 50 lakh (overall cap)
    if result.gross_total_income > Decimal("5000000"):
        results.append(_make(
            "ITR4-C268", False,
            f"Total income ({result.gross_total_income}) exceeds Rs 50 lakh "
            f"ITR-4 limit. File ITR-3.",
            "gross_total_income",
            expected="<= 5000000", actual=str(result.gross_total_income)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 87A Rebate
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 51: 87A old regime — taxable income <= Rs 5,00,000
    if is_old and result.rebate_87a > z:
        ti = result.taxable_income
        if ti > Decimal("500000"):
            results.append(_make(
                "ITR4-C051", False,
                f"87A rebate claimed (Rs {result.rebate_87a}) but total income "
                f"({ti}) exceeds Rs 5,00,000 limit under old regime",
                "rebate_87a",
                expected="0 when TI > 500000", actual=str(result.rebate_87a)))
        if result.rebate_87a > Decimal("12500"):
            results.append(_make(
                "ITR4-C229", False,
                f"87A rebate ({result.rebate_87a}) exceeds maximum Rs 12,500 "
                f"under old regime",
                "rebate_87a",
                expected="<= 12500", actual=str(result.rebate_87a)))

    # Rule 227: 87A new regime — total income <= Rs 12,00,000, rebate <= Rs 60,000
    if is_new and result.rebate_87a > z:
        ti = result.taxable_income
        if ti > Decimal("1200000"):
            results.append(_make(
                "ITR4-C227", False,
                f"87A rebate claimed but total income ({ti}) exceeds "
                f"Rs 12,00,000 under new regime",
                "rebate_87a",
                expected="0 when TI > 1200000", actual=str(result.rebate_87a)))
        if result.rebate_87a > Decimal("60000"):
            results.append(_make(
                "ITR4-C228", False,
                f"87A rebate ({result.rebate_87a}) exceeds maximum Rs 60,000 "
                f"under new regime",
                "rebate_87a",
                expected="<= 60000", actual=str(result.rebate_87a)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Salary Computation Checks
    # ═══════════════════════════════════════════════════════════════════════

    if sal and sal_sched:

        # Rule 59: Salary gross = basic + perquisites + profits_in_lieu
        expected_sal_gross = (sal.gross_salary + sal.perquisites_value
                              + sal.profits_in_lieu_of_salary)
        if result.salary_gross != expected_sal_gross:
            results.append(_make(
                "ITR4-C059", False,
                f"Salary gross ({result.salary_gross}) != "
                f"gross_salary ({sal.gross_salary}) + "
                f"perquisites ({sal.perquisites_value}) + "
                f"profits_in_lieu ({sal.profits_in_lieu_of_salary}) "
                f"= {expected_sal_gross}",
                "salary_gross",
                expected=str(expected_sal_gross), actual=str(result.salary_gross)))

        # Rule 60: Standard deduction should match regime appropriate amount
        if is_old and result.salary_deduction_us16ia > z:
            if result.salary_deduction_us16ia != Decimal("50000"):
                results.append(_make(
                    "ITR4-C060", False,
                    f"Standard deduction old regime ({result.salary_deduction_us16ia}) "
                    f"should be Rs 50,000",
                    "salary_deduction_us16ia",
                    expected="50000", actual=str(result.salary_deduction_us16ia)))

        if is_new and result.salary_deduction_us16ia > z:
            if result.salary_deduction_us16ia != Decimal("75000"):
                results.append(_make(
                    "ITR4-C261", False,
                    f"Standard deduction new regime ({result.salary_deduction_us16ia}) "
                    f"should be Rs 75,000",
                    "salary_deduction_us16ia",
                    expected="75000", actual=str(result.salary_deduction_us16ia)))

        # Rule 62: Salary net = gross - exempt allowances
        if is_old:
            expected_net_sal = (result.salary_gross
                                - sal.hra_exempt_amount
                                - sal.lta_exempt_amount)
            if result.salary_net != expected_net_sal:
                results.append(_make(
                    "ITR4-C062", False,
                    f"Salary net ({result.salary_net}) != "
                    f"gross ({result.salary_gross}) - "
                    f"hra_exempt ({sal.hra_exempt_amount}) - "
                    f"lta_exempt ({sal.lta_exempt_amount}) = {expected_net_sal}",
                    "salary_net",
                    expected=str(expected_net_sal), actual=str(result.salary_net)))
        else:
            # Under new regime, HRA/LTA are nil per 115BAC — net_salary == gross
            if result.salary_net != result.salary_gross:
                results.append(_make(
                    "ITR4-C062", False,
                    f"Salary net ({result.salary_net}) != "
                    f"gross ({result.salary_gross}) under new regime "
                    f"(HRA/LTA not allowed)",
                    "salary_net",
                    expected=str(result.salary_gross), actual=str(result.salary_net)))

        # Rule 63: Salary chargeable = net - u/s 16 deductions (standard + ent + prof tax)
        if is_old:
            expected_charge = (result.salary_net
                               - result.salary_deduction_us16ia
                               - result.salary_entertainment_allowance
                               - result.salary_professional_tax)
            expected_charge = max(z, expected_charge)
            if result.salary_income != expected_charge:
                results.append(_make(
                    "ITR4-C063", False,
                    f"Salary chargeable ({result.salary_income}) != "
                    f"net ({result.salary_net}) - "
                    f"std_ded ({result.salary_deduction_us16ia}) - "
                    f"ent_allow ({result.salary_entertainment_allowance}) - "
                    f"prof_tax ({result.salary_professional_tax}) "
                    f"= {expected_charge}",
                    "salary_income",
                    expected=str(expected_charge), actual=str(result.salary_income)))

        if is_new:
            expected_charge_new = max(z, result.salary_gross
                                      - result.salary_deduction_us16ia)
            if result.salary_income != expected_charge_new:
                results.append(_make(
                    "ITR4-C196", False,
                    f"Salary chargeable new regime ({result.salary_income}) != "
                    f"gross ({result.salary_gross}) - "
                    f"standard_ded ({result.salary_deduction_us16ia}) "
                    f"= {expected_charge_new}",
                    "salary_income",
                    expected=str(expected_charge_new),
                    actual=str(result.salary_income)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: House Property Computation Checks
    # ═══════════════════════════════════════════════════════════════════════

    if hp and hp_sched:
        # Rule 57: HP standard deduction = 30% of assessee-owned annual value.
        if hp.property_type != PropertyType.SELF_OCCUPIED:
            expected_30 = hp_sched.standard_deduction_30pct
            owned_value = hp_sched.annual_value_owned
            expected_30_alt = max(z, owned_value) * Decimal("0.30")
            if abs(expected_30 - expected_30_alt) > Decimal("1"):
                results.append(_make(
                    "ITR4-C057", False,
                    f"HP 30% standard deduction ({expected_30}) != "
                    f"30% of owned annual value ({owned_value}) = {expected_30_alt}",
                    "house_property_income",
                    expected=str(expected_30_alt), actual=str(expected_30)))

        # Rule 48: Self-occupied: GAV should be nil
        if hp.property_type == PropertyType.SELF_OCCUPIED:
            if hp_sched.gross_annual_value > z:
                results.append(_make(
                    "ITR4-C048", False,
                    f"Self-occupied property GAV ({hp_sched.gross_annual_value}) "
                    f"should be nil",
                    "house_property_income",
                    expected="0", actual=str(hp_sched.gross_annual_value)))

        # Rule 47: HP income for self-occupied = 0 or - (capped interest) (old regime)
        if is_old and hp.property_type == PropertyType.SELF_OCCUPIED:
            max_interest = min(hp.home_loan_interest_paid, Decimal("200000"))
            expected_hp = -max_interest
            if result.house_property_income != expected_hp:
                results.append(_make(
                    "ITR4-C047", False,
                    f"Self-occupied HP income ({result.house_property_income}) "
                    f"should equal -min(interest, 200000) = {expected_hp}",
                    "house_property_income",
                    expected=str(expected_hp),
                    actual=str(result.house_property_income)))

        # Rule 57 (old 154): Self-occupied interest cap Rs 2L (cross-check)
        if is_old and hp.property_type == PropertyType.SELF_OCCUPIED:
            if hp.home_loan_interest_paid > Decimal("200000"):
                capped = Decimal("200000")
                actual_interest = hp_sched.interest_on_loan
                if abs(actual_interest - hp.home_loan_interest_paid) <= Decimal("1"):
                    results.append(_make(
                        "ITR4-C154", False,
                        f"Self-occupied interest ({hp.home_loan_interest_paid}) "
                        f"exceeds Rs 2,00,000 but appears uncapped in HP schedule "
                        f"({actual_interest})",
                        "house_property_income.home_loan_interest_paid",
                        expected="<= 200000", actual=str(actual_interest)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Other Sources Checks
    # ═══════════════════════════════════════════════════════════════════════

    op = inp.other_sources_income
    if op and os_sched:
        # Rule 96: 57(iia) family pension deduction: 1/3 of FP or 15,000/25,000
        fp = op.family_pension_received
        if fp > z:
            max_fp_ded = Decimal("15000")
            if is_old:
                max_fp_ded = min(fp / Decimal("3"), Decimal("15000"))
            if os_sched.deduction_57iia > max_fp_ded + Decimal("1"):
                results.append(_make(
                    "ITR4-C096", False,
                    f"57(iia) family pension deduction ({os_sched.deduction_57iia}) "
                    f"exceeds limit: min(1/3 of FP, {max_fp_ded})",
                    "other_sources_income.family_pension_received",
                    expected=f"<= {max_fp_ded}",
                    actual=str(os_sched.deduction_57iia)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Capital Gains — 112A Computation
    # ═══════════════════════════════════════════════════════════════════════

    cg = inp.capital_gains
    if cg and cg.ltcg_112a > z:
        cg_sched = result.schedules.get("capital_gains_112a")
        if cg_sched:
            # Rule 273: LTCG 112A taxable should not exceed gross 112A
            if cg_sched.taxable_income > cg.ltcg_112a:
                results.append(_make(
                    "ITR4-C273", False,
                    f"112A taxable income ({cg_sched.taxable_income}) exceeds "
                    f"gross 112A ({cg.ltcg_112a})",
                    "capital_gains.ltcg_112a"))
            # Rule 264: LTCG 112A capital gains = GTI 112A component.
            # ``result.capital_gains_112a`` holds the FULL pre-exemption
            # net LTCG gain (it flows into GTI), so it must equal the
            # schedule's ``net_income`` (pre-exemption), NOT
            # ``taxable_income`` (post the Rs 1.25L special-rate exemption).
            # The exemption reduces only the special-rate tax, not GTI.
            if result.capital_gains_112a != cg_sched.net_income:
                results.append(_make(
                    "ITR4-C264", False,
                    f"GTI capital gains 112A ({result.capital_gains_112a}) != "
                    f"Schedule 112A net income ({cg_sched.net_income})",
                    "capital_gains_112a",
                    expected=str(cg_sched.net_income),
                    actual=str(result.capital_gains_112a)))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Deduction Limit Cross-Checks
    # ═══════════════════════════════════════════════════════════════════════

    if is_old and ch6a:
        # Rule 18: 80CCD(1) + 80C + 80CCC <= 1,50,000
        pool_80c = ch6a.amount_80c + ch6a.amount_80ccc + ch6a.amount_80ccd1
        ded_80c_actual = ded_sched.breakdown.get("80C+80CCC+80CCD(1)", z) if ded_sched else z
        if ded_80c_actual > z and ded_80c_actual > Decimal("150000"):
            results.append(_make(
                "ITR4-C018", False,
                f"Computed 80C/80CCC/80CCD(1) ({ded_80c_actual}) exceeds "
                f"Rs 1,50,000 combined limit u/s 80CCE",
                "deductions_chapter6a",
                expected="<= 150000", actual=str(ded_80c_actual)))

        # Rule 17: VI-A deductions should not exceed sum of individual heads
        if ded_sched and ded_sched.breakdown:
            bd_sum = sum(
                v for k, v in ded_sched.breakdown.items()
                if not k.startswith("80G") and not k.startswith("80GG")
            )
            # 80G/80GG are computed against adjusted GTI, looser check
            if result.deductions_total > bd_sum + ded_sched.breakdown.get("80G", z) + ded_sched.breakdown.get("80GG", z) + Decimal("10"):
                results.append(_make(
                    "ITR4-C017", False,
                    f"VI-A total ({result.deductions_total}) inconsistent with "
                    f"breakdown sum ({bd_sum + ded_sched.breakdown.get('80G', z) + ded_sched.breakdown.get('80GG', z)})",
                    "deductions_total"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: New Regime — Only 80CCD(2) + 80CCH Allowed
    # ═══════════════════════════════════════════════════════════════════════

    if is_new and ded_sched and ded_sched.breakdown:
        allowed_keys = {"80CCD(2)", "80CCH"}
        for k, v in ded_sched.breakdown.items():
            if v > z and k not in allowed_keys:
                results.append(_make(
                    "ITR4-C185", False,
                    f"New regime: Only 80CCD(2) and 80CCH are allowed. "
                    f"Found non-zero deduction: {k} = {v}",
                    "deductions_chapter6a",
                    expected="0", actual=f"{k}={v}"))

    if is_new:
        # Rule 277: HP loss not allowed in new regime (self-occupied)
        if result.hp_loss_disallowed > z:
            results.append(_info(
                "ITR4-C277",
                f"HP loss of Rs {result.hp_loss_disallowed} disallowed under new "
                f"regime. Cannot be set off or carried forward.",
                "hp_loss_disallowed"))

        # Rule 278: Business loss not allowed (informational)
        if result.presumptive_income < z:
            results.append(_make(
                "ITR4-C278", False,
                f"Presumptive business income ({result.presumptive_income}) is "
                f"negative. Under presumptive schemes (44AD/44ADA/44AE), income "
                f"cannot be a loss. Minimum income is statutory presumptive amount.",
                "presumptive_income"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: TDS / TCS Credit Verification
    # ═══════════════════════════════════════════════════════════════════════

    tds1_sum = sum(e.tds_deducted for e in (inp.tds1_entries or []))
    tds2_sum = sum(e.tds_deducted for e in (inp.tds2_entries or []))
    tcs_sum = sum(e.tcs_collected for e in (inp.tcs_entries or []))

    if result.total_tds != tds1_sum + tds2_sum:
        results.append(_make(
            "ITR4-C114", False,
            f"Total TDS ({result.total_tds}) != "
            f"TDS1 ({tds1_sum}) + TDS2 ({tds2_sum}) = {tds1_sum + tds2_sum}",
            "total_tds",
            expected=str(tds1_sum + tds2_sum), actual=str(result.total_tds)))

    if result.total_tcs != tcs_sum:
        results.append(_make(
            "ITR4-C115", False,
            f"Total TCS ({result.total_tcs}) != "
            f"sum of TCS entries ({tcs_sum})",
            "total_tcs",
            expected=str(tcs_sum), actual=str(result.total_tcs)))

    if result.total_taxes_paid != (result.total_tds + result.total_tcs
                                   + result.advance_tax_paid
                                   + result.self_assessment_tax_paid):
        results.append(_make(
            "ITR4-C116", False,
            f"Total taxes paid ({result.total_taxes_paid}) != "
            f"TDS ({result.total_tds}) + TCS ({result.total_tcs}) + "
            f"Advance Tax ({result.advance_tax_paid}) + "
            f"SA Tax ({result.self_assessment_tax_paid})",
            "total_taxes_paid"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: 44AD / 44ADA / 44AE Higher Declared Income
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 12: 44AD income declared higher but Schedule BP check (informational)
    if inp.business_income_44ad and inp.business_income_44ad.income_declared is not None:
        ad = inp.business_income_44ad
        statutory = (ad.digital_turnover * Decimal("0.06")
                     + ad.cash_turnover * Decimal("0.08"))
        if ad.income_declared > statutory:
            results.append(_info(
                "ITR4-C012",
                f"44AD: Income declared ({ad.income_declared}) exceeds statutory "
                f"presumptive income ({statutory}). Higher declared income accepted "
                f"under Section 44AD(1) proviso.",
                "business_income_44ad.income_declared"))

    # Rule 17: 44AE total months owned check (12 per vehicle, not > 120 total)
    if inp.goods_carriage_44ae:
        if len(inp.goods_carriage_44ae.vehicles) > 10:
            results.append(_make(
                "ITR4-C138", False,
                f"44AE: {len(inp.goods_carriage_44ae.vehicles)} vehicles listed. "
                f"Maximum 10 goods carriages allowed under Section 44AE.",
                "goods_carriage_44ae.vehicles",
                expected="<= 10", actual=str(len(inp.goods_carriage_44ae.vehicles))))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Tax on Presumptive Income — Slab Tax vs Special Rate
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 45: Presumptive income taxed at normal slab rates (not special rate)
    if result.presumptive_income > z:
        results.append(_info(
            "ITR4-C045",
            f"Presumptive income ({result.presumptive_income}) is taxed at normal "
            f"slab rates, not special rates. Only 112A income ("
            f"{result.capital_gains_112a}) is taxed at special rate "
            f"({result.special_rate_tax}).",
            "presumptive_income"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Filing Date Rules
    # ═══════════════════════════════════════════════════════════════════════

    # Rule 107: Late fee u/s 234F check
    if result.late_fee_234f > z:
        results.append(_info(
            "ITR4-C107",
            f"Late filing fee u/s 234F: Rs {result.late_fee_234f}. "
            f"Verify filing date ({inp.filing_date}) vs due date ({inp.due_date}) "
            f"and total income slab for correct late fee computation.",
            "late_fee_234f"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION: Cross-Schedule Integrity (informational)
    # ═══════════════════════════════════════════════════════════════════════

    # Rules 242-252: Cross-schedule matches for Schedule-S, HP, OS, CG, VIA
    results.append(_info(
        "ITR4-C242",
        "Cross-schedule: Verify Schedule-S (salary) field-by-field matches "
        "with Form 16/ITR computation. Not automated.",
        ""))
    results.append(_info(
        "ITR4-C243",
        "Cross-schedule: Verify Schedule-HP field-by-field matches with "
        "ITR computation. Not automated.",
        ""))
    results.append(_info(
        "ITR4-C244",
        "Cross-schedule: Verify Schedule-OS figures match with 26AS/TIS. "
        "Not automated.",
        ""))
    results.append(_info(
        "ITR4-C245",
        "Cross-schedule: Verify capital gains schedule (112A) — sale "
        "consideration, cost, FMV, and exemption match ITR. Not automated.",
        ""))
    results.append(_info(
        "ITR4-C246",
        "Cross-schedule: Verify Schedule-VIA deduction figures match with "
        "individual deduction schedules and supporting documents. Not automated.",
        ""))
    results.append(_info(
        "ITR4-C247",
        "Cross-schedule: Verify Schedule-IT (TDS, TCS, advance tax) matches "
        "Form 26AS and tax payment challans. Not automated.",
        ""))

    # Rule 272: Total special rate income <= Total income
    if result.special_rate_tax > z and result.special_rate_tax > result.tax_before_rebate:
        results.append(_make(
            "ITR4-C272", False,
            f"Special rate tax ({result.special_rate_tax}) exceeds total tax "
            f"before rebate ({result.tax_before_rebate}). This is inconsistent.",
            "special_rate_tax",
            expected=f"<= {result.tax_before_rebate}",
            actual=str(result.special_rate_tax)))

    # Rule 274: LTCG 112A exemption should not exceed 1.25L
    cg_sched = result.schedules.get("capital_gains_112a")
    if cg_sched and cg_sched.exemption_available > Decimal("125000"):
        results.append(_make(
            "ITR4-C274", False,
            f"112A exemption ({cg_sched.exemption_available}) exceeds "
            f"Rs 1,25,000 statutory limit",
            "capital_gains.cost_of_acquisition"))

    # Rule 275: Tax calculation with marginal relief (informational)
    if result.surcharge > z:
        results.append(_info(
            "ITR4-C275",
            f"Surcharge of Rs {result.surcharge} applied. "
            f"Verify marginal relief computation where applicable "
            f"(tax + surcharge should not exceed income above threshold).",
            "surcharge"))

    # Rule 276: Surcharge maximum cap (informational)
    if result.surcharge > z:
        max_surcharge = result.tax_after_rebate * Decimal("0.37")
        if is_new:
            max_surcharge = result.tax_after_rebate * Decimal("0.25")
        if result.surcharge > max_surcharge:
            results.append(_make(
                "ITR4-C276", False,
                f"Surcharge ({result.surcharge}) exceeds maximum rate applicable "
                f"({max_surcharge})",
                "surcharge",
                expected=f"<= {max_surcharge}", actual=str(result.surcharge)))

    # Rule 279: Set-off and carry forward losses — not applicable for ITR-4 (informational)
    results.append(_info(
        "ITR4-C279",
        "ITR-4 does not permit set-off or carry forward of losses. "
        "If the assessee has brought-forward losses, ITR-3 should be filed.",
        ""))

    # Rule 280: Tax credit claimed <= tax payable (informational)
    if result.total_taxes_paid > result.gross_tax_liability:
        results.append(_info(
            "ITR4-C280",
            f"Tax credits ({result.total_taxes_paid}) exceed gross tax liability "
            f"({result.gross_tax_liability}). Refund of Rs {result.refund_due} due.",
            "total_taxes_paid"))

    return results
