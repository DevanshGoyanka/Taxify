"""
ITR-4 validation runner -- executes all Category A validation rules.

Usage:
    from app.engine.validators.itr4 import run_input_validation, run_calc_validation

    input_report = run_input_validation(itr4_input)
    calc_report = run_calc_validation(itr4_input, itr4_result)
    full_report = merge_reports(input_report, calc_report)
"""

from __future__ import annotations

from app.schemas.itr4 import ITR4Input
from app.engine.calculators.itr4 import ITR4Result
from app.engine.validators.base import ValidationReport, merge_reports
from app.engine.validators.itr4.input_rules import validate_itr4_input
from app.engine.validators.itr4.calc_rules import validate_itr4_calculation


def run_input_validation(inp: ITR4Input) -> ValidationReport:
    """Run all ITR-4 input-level (pre-computation) validation rules."""
    results = validate_itr4_input(inp)
    return ValidationReport(form_type="ITR4", results=results)


def run_calc_validation(inp: ITR4Input, result: ITR4Result) -> ValidationReport:
    """Run all ITR-4 post-computation validation rules."""
    results = validate_itr4_calculation(inp, result)
    return ValidationReport(form_type="ITR4", results=results)


def run_all(inp: ITR4Input, result: ITR4Result) -> ValidationReport:
    """Run both input AND calculation validation, return merged report."""
    return merge_reports(run_input_validation(inp), run_calc_validation(inp, result))
