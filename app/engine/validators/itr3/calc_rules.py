"""Baseline ITR-3 post-computation validation rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine.validators.base import Severity, ValidationReport, ValidationResult
from app.schemas.itr3 import ITR3Input


def run_calc_validation(input_data: ITR3Input, result: Any) -> ValidationReport:
    """Validate core arithmetic invariants exposed by the ITR-3 result."""
    checks: list[tuple[str, bool, str, str, Any, Any]] = [
        (
            "ITR3-C001",
            result.gross_total_income >= Decimal("0"),
            "Gross total income must not be negative.",
            "gross_total_income",
            ">= 0",
            result.gross_total_income,
        ),
        (
            "ITR3-C002",
            result.taxable_income >= Decimal("0"),
            "Taxable income must not be negative.",
            "taxable_income",
            ">= 0",
            result.taxable_income,
        ),
        (
            "ITR3-C003",
            result.total_taxes_paid >= Decimal("0"),
            "Total taxes paid must not be negative.",
            "total_taxes_paid",
            ">= 0",
            result.total_taxes_paid,
        ),
    ]
    results = [
        ValidationResult(
            rule_id=rule_id,
            severity=Severity.A,
            passed=passed,
            message=message,
            field_path=field_path,
            expected=expected,
            actual=actual,
        )
        for rule_id, passed, message, field_path, expected, actual in checks
    ]
    return ValidationReport(form_type="ITR3", results=results)


__all__ = ["run_calc_validation"]
