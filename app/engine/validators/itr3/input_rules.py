"""Baseline ITR-3 input validation rules.

These rules cover invariants that can be evaluated from the typed ITR-3 input
without pretending to implement the complete CBDT rule inventory. Official
rule coverage remains tracked separately in the production plan.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.validators.base import Severity, ValidationReport, ValidationResult
from app.schemas.itr3 import ITR3Input


def _result(
    rule_id: str,
    passed: bool,
    message: str,
    field_path: str,
    expected: Any = None,
    actual: Any = None,
) -> ValidationResult:
    """Create a blocking Category A validation result."""
    return ValidationResult(
        rule_id=rule_id,
        severity=Severity.A,
        passed=passed,
        message=message,
        field_path=field_path,
        expected=expected,
        actual=actual,
    )


def _date_result(rule_id: str, value: str | None, field_path: str) -> ValidationResult:
    """Validate an optional ISO calendar date."""
    if value is None or value == "":
        return _result(rule_id, True, "Optional date is absent.", field_path)
    try:
        date.fromisoformat(value)
    except ValueError:
        return _result(
            rule_id,
            False,
            "Date must use ISO YYYY-MM-DD format.",
            field_path,
            "YYYY-MM-DD",
            value,
        )
    return _result(rule_id, True, "Date is valid.", field_path)


def run_input_validation(input_data: ITR3Input) -> ValidationReport:
    """Run baseline pre-computation validation for an ITR-3 input.

    The validator deliberately checks only typed-input invariants that are
    independent of the incomplete schedule implementation. Pydantic performs
    field-level bounds validation before this function is called.
    """
    results: list[ValidationResult] = []
    business = input_data.business_income
    results.append(_result(
        "ITR3-R001",
        business is not None,
        "ITR-3 requires business or professional income.",
        "business_income",
        "present",
        "present" if business is not None else "missing",
    ))

    monetary_fields = (
        "advance_tax_paid",
        "self_assessment_tax_paid",
        "relief_89",
    )
    for field_name in monetary_fields:
        value = getattr(input_data, field_name)
        results.append(_result(
            "ITR3-R002" if field_name == "advance_tax_paid" else
            "ITR3-R003" if field_name == "self_assessment_tax_paid" else
            "ITR3-R004",
            value.is_finite() and value >= Decimal("0"),
            f"{field_name} must be a finite non-negative amount.",
            field_name,
            ">= 0",
            value,
        ))

    results.append(_date_result("ITR3-R005", input_data.assessee_dob, "assessee_dob"))
    results.append(_date_result("ITR3-R006", input_data.verification_date, "verification_date"))
    if input_data.filing_date is not None:
        results.append(_result(
            "ITR3-R007",
            input_data.verification_date is None or input_data.filing_date.isoformat() == input_data.verification_date,
            "Filing date must match the declared verification date when both are present.",
            "filing_date",
            input_data.verification_date,
            input_data.filing_date.isoformat(),
        ))
    else:
        results.append(_result("ITR3-R007", True, "Filing date is deferred to the gateway.", "filing_date"))

    return ValidationReport(form_type="ITR3", results=results)


__all__ = ["run_input_validation"]
