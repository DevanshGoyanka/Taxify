"""ITR-2 post-computation arithmetic and reconciliation validation rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine.calculators.itr2 import ITR2Result
from app.engine.validators.base import Severity, ValidationReport, ValidationResult
from app.schemas.itr2 import ITR2Input

_ZERO = Decimal("0")
_TOLERANCE = Decimal("1")


def _result(
    rule_id: str,
    message: str,
    field_path: str,
    expected: Any,
    actual: Any,
) -> ValidationResult:
    """Build a blocking post-computation validation failure."""
    return ValidationResult(
        rule_id=rule_id,
        severity=Severity.A,
        passed=False,
        message=message,
        field_path=field_path,
        expected=expected,
        actual=actual,
    )


def _different(left: Decimal, right: Decimal, tolerance: Decimal = _TOLERANCE) -> bool:
    """Return whether two monetary values differ beyond rounding tolerance."""
    return abs(left - right) > tolerance


def validate_itr2_calculation(inp: ITR2Input, result: ITR2Result) -> list[ValidationResult]:
    """Validate ITR-2 post-computation arithmetic and schedule reconciliation.

    Args:
        inp: Source ITR-2 input used by the calculator.
        result: Completed ITR-2 calculator result.

    Returns:
        Actionable Category-A validation failures. An empty list indicates that
        represented arithmetic and reconciliation invariants hold.
    """
    results: list[ValidationResult] = []

    expected_before = (
        max(_ZERO, result.salary_income)
        + max(_ZERO, result.house_property_income)
        + result.capital_gains_income
        + max(_ZERO, result.other_sources_income)
    )
    if _different(result.gti_before_loss_setoff, expected_before):
        results.append(_result(
            "ITR2-CALC-001", "GTI before loss set-off does not equal the sum of positive income heads.",
            "gti_before_loss_setoff", str(expected_before), str(result.gti_before_loss_setoff),
        ))

    expected_after = result.gti_before_loss_setoff - result.cyla_total_set_off - result.bfla_total_set_off
    if _different(result.gti_after_loss_setoff, expected_after):
        results.append(_result(
            "ITR2-CALC-002", "GTI after loss set-off does not reconcile with CYLA and BFLA.",
            "gti_after_loss_setoff", str(expected_after), str(result.gti_after_loss_setoff),
        ))
    if _different(result.gross_total_income, result.gti_after_loss_setoff):
        results.append(_result(
            "ITR2-CALC-003", "Gross total income must equal GTI after loss set-off.",
            "gross_total_income", str(result.gti_after_loss_setoff), str(result.gross_total_income),
        ))
    if result.cyla_total_set_off > result.gti_before_loss_setoff:
        results.append(_result(
            "ITR2-CALC-004", "Current-year loss set-off cannot exceed available income.",
            "cyla_total_set_off", f"<= {result.gti_before_loss_setoff}", str(result.cyla_total_set_off),
        ))
    available_after_cyla = max(_ZERO, result.gti_before_loss_setoff - result.cyla_total_set_off)
    if result.bfla_total_set_off > available_after_cyla:
        results.append(_result(
            "ITR2-CALC-005", "Brought-forward loss set-off cannot exceed income remaining after CYLA.",
            "bfla_total_set_off", f"<= {available_after_cyla}", str(result.bfla_total_set_off),
        ))
    if result.deductions_total > max(_ZERO, result.gross_total_income):
        results.append(_result(
            "ITR2-CALC-006", "Chapter VI-A deductions cannot exceed gross total income.",
            "deductions_total", f"<= {max(_ZERO, result.gross_total_income)}", str(result.deductions_total),
        ))

    raw_taxable = max(_ZERO, result.gross_total_income - result.deductions_total)
    if abs(result.taxable_income - raw_taxable) > Decimal("5"):
        results.append(_result(
            "ITR2-CALC-007", "Taxable income does not equal rounded GTI less deductions.",
            "taxable_income", f"within 5 of {raw_taxable}", str(result.taxable_income),
        ))
    expected_aggregate = result.taxable_income + result.net_agricultural_income
    if _different(result.aggregate_income, expected_aggregate):
        results.append(_result(
            "ITR2-CALC-008", "Aggregate income must equal taxable plus net agricultural income.",
            "aggregate_income", str(expected_aggregate), str(result.aggregate_income),
        ))

    expected_tax_before_relief = result.slab_tax + result.special_rate_tax + result.amt_tax
    if _different(result.total_tax_before_relief, expected_tax_before_relief):
        results.append(_result(
            "ITR2-CALC-009", "Total tax before relief must equal slab, special-rate, and AMT tax.",
            "total_tax_before_relief", str(expected_tax_before_relief), str(result.total_tax_before_relief),
        ))
    expected_after_rebate = max(_ZERO, result.tax_before_rebate - result.rebate_87a)
    if _different(result.tax_after_rebate, expected_after_rebate):
        results.append(_result(
            "ITR2-CALC-010", "Tax after rebate does not reconcile.",
            "tax_after_rebate", str(expected_after_rebate), str(result.tax_after_rebate),
        ))
    expected_cess = (result.tax_after_rebate + result.surcharge) * Decimal("0.04")
    if _different(result.health_education_cess, expected_cess):
        results.append(_result(
            "ITR2-CALC-011", "Health and education cess must be 4% of tax plus surcharge.",
            "health_education_cess", str(expected_cess), str(result.health_education_cess),
        ))
    expected_gross_tax = result.tax_after_rebate + result.surcharge + result.health_education_cess
    amt_schedule = result.schedules.get("amt")
    if amt_schedule is None and _different(result.gross_tax_liability, expected_gross_tax):
        results.append(_result(
            "ITR2-CALC-012", "Gross tax liability does not reconcile with tax, surcharge, and cess.",
            "gross_tax_liability", str(expected_gross_tax), str(result.gross_tax_liability),
        ))
    if result.relief_89 + result.relief_90_91 > result.gross_tax_liability:
        results.append(_result(
            "ITR2-CALC-013", "Tax relief cannot exceed gross tax liability.",
            "relief_90_91", f"combined relief <= {result.gross_tax_liability}",
            str(result.relief_89 + result.relief_90_91),
        ))

    expected_interest = result.interest_234a + result.interest_234b + result.interest_234c
    if _different(result.total_interest, expected_interest):
        results.append(_result(
            "ITR2-CALC-014", "Total interest must equal sections 234A, 234B, and 234C interest.",
            "total_interest", str(expected_interest), str(result.total_interest),
        ))
    expected_tds = sum(entry.tds_deducted for entry in inp.tds1_entries)
    expected_tds += sum(entry.tds_claimed_this_year for entry in inp.tds2_entries)
    expected_tds += sum(entry.tds_claimed_this_year for entry in inp.tds3_entries)
    expected_tcs = sum(entry.tcs_credit_claimed for entry in inp.tcs_entries)
    if _different(result.total_tds, expected_tds):
        results.append(_result(
            "ITR2-CALC-015", "Computed TDS does not equal the source schedule total.",
            "total_tds", str(expected_tds), str(result.total_tds),
        ))
    if _different(result.total_tcs, expected_tcs):
        results.append(_result(
            "ITR2-CALC-016", "Computed TCS does not equal the source schedule total.",
            "total_tcs", str(expected_tcs), str(result.total_tcs),
        ))
    expected_paid = (
        result.total_tds + result.total_tcs + result.total_advance_tax + result.total_self_assessment_tax
    )
    if _different(result.total_taxes_paid, expected_paid):
        results.append(_result(
            "ITR2-CALC-017", "Total taxes paid does not reconcile with all tax credits/payments.",
            "total_taxes_paid", str(expected_paid), str(result.total_taxes_paid),
        ))

    payable_diff = result.net_tax_liability - result.total_taxes_paid
    expected_payable = max(_ZERO, payable_diff)
    expected_refund = max(_ZERO, -payable_diff)
    if _different(result.balance_payable, expected_payable):
        results.append(_result(
            "ITR2-CALC-018", "Balance payable does not reconcile with liability and taxes paid.",
            "balance_payable", str(expected_payable), str(result.balance_payable),
        ))
    if _different(result.refund_due, expected_refund):
        results.append(_result(
            "ITR2-CALC-019", "Refund due does not reconcile with liability and taxes paid.",
            "refund_due", str(expected_refund), str(result.refund_due),
        ))
    if result.balance_payable > _ZERO and result.refund_due > _ZERO:
        results.append(_result(
            "ITR2-CALC-020", "A return cannot simultaneously have tax payable and a refund.",
            "balance_payable", "only one of payable/refund positive",
            f"payable={result.balance_payable}, refund={result.refund_due}",
        ))

    nonnegative_fields = (
        "capital_gains_income", "vda_income", "gti_before_loss_setoff", "cyla_total_set_off",
        "bfla_total_set_off", "gross_total_income", "deductions_total", "taxable_income",
        "slab_tax", "special_rate_tax", "amt_tax", "rebate_87a", "tax_after_rebate",
        "surcharge", "health_education_cess", "gross_tax_liability", "relief_89",
        "relief_90_91", "total_interest", "net_tax_liability", "total_tds", "total_tcs",
        "total_taxes_paid", "balance_payable", "refund_due", "cyla_remaining", "bfla_remaining",
    )
    for field_name in nonnegative_fields:
        value = getattr(result, field_name)
        if value < _ZERO:
            results.append(_result(
                "ITR2-CALC-021", f"Computed field {field_name} cannot be negative.",
                field_name, ">= 0", str(value),
            ))

    for key, field_name, expected_value in (
        ("salary", "salary_income", result.salary_income),
        ("hp", "house_property_income", result.house_property_income),
        ("os", "other_sources_income", result.other_sources_income - result.clubbing_income),
    ):
        schedule = result.schedules.get(key)
        schedule_value = getattr(schedule, "income_chargeable", None) if schedule is not None else None
        if schedule_value is not None and _different(schedule_value, expected_value):
            results.append(_result(
                "ITR2-CALC-022", f"{key.upper()} schedule does not reconcile with the result head.",
                field_name, str(schedule_value), str(expected_value),
            ))
    deduction_schedule = result.schedules.get("deductions")
    if deduction_schedule is not None and _different(
        getattr(deduction_schedule, "total", _ZERO), result.deductions_total
    ):
        results.append(_result(
            "ITR2-CALC-023", "Deduction schedule total does not reconcile with result deductions.",
            "deductions_total", str(getattr(deduction_schedule, "total", _ZERO)),
            str(result.deductions_total),
        ))

    # Verify 112A threshold applied exactly once
    si = result.schedules.get("si")
    if si is not None:
        for entry in si.entries:
            if entry.section == "112A":
                from app.engine.constants import LTCG_112A_EXEMPTION
                if entry.exemption_available > LTCG_112A_EXEMPTION:
                    results.append(_result(
                        "ITR2-CALC-024", "Section 112A exemption exceeds the statutory ₹1.25L threshold.",
                        "si.112A.exemption_available",
                        f"<= {LTCG_112A_EXEMPTION}", str(entry.exemption_available),
                    ))
                if entry.taxable_income < _ZERO:
                    results.append(_result(
                        "ITR2-CALC-025", "Section 112A taxable income cannot be negative.",
                        "si.112A.taxable_income", ">= 0", str(entry.taxable_income),
                    ))

    # Verify surcharge 15% cap on 111A/112/112A/dividend
    if si is not None and si.surcharge_cap_tax > 0:
        from app.engine.constants import LTCG_112A_EXEMPTION as _ex
        max_capped_tax_at_15pct = si.surcharge_cap_income * Decimal("0.15")
        if si.surcharge_cap_tax > max_capped_tax_at_15pct + Decimal("1"):
            results.append(_result(
                "ITR2-CALC-026",
                "Capped special-rate tax exceeds 15% of capped income (surcharge base).",
                "si.surcharge_cap_tax",
                f"<= {max_capped_tax_at_15pct}", str(si.surcharge_cap_tax),
            ))

    return results


def run_calc_validation(inp: ITR2Input, result: ITR2Result) -> ValidationReport:
    """Run ITR-2 post-computation validation and return a standard report."""
    return ValidationReport(form_type="ITR2", results=validate_itr2_calculation(inp, result))
