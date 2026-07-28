"""
ITR-1 validation runner -- executes all Category A validation rules.

Usage:
    from app.engine.validators.itr1 import run_input_validation, run_calc_validation

    input_report = run_input_validation(itr1_input)
    calc_report = run_calc_validation(itr1_input, itr1_result)
    full_report = merge_reports(input_report, calc_report)
"""

from __future__ import annotations

from app.schemas.itr1 import ITR1Input
from app.engine.calculators.itr1 import ITR1Result
from app.engine.validators.base import ValidationReport, merge_reports
from app.engine.validators.itr1.input_rules import validate_itr1_input
from app.engine.validators.itr1.calc_rules import validate_itr1_calculation


def run_input_validation(inp: ITR1Input) -> ValidationReport:
    """Run all ITR-1 input-level (pre-computation) validation rules."""
    results = validate_itr1_input(inp)
    return ValidationReport(form_type="ITR1", results=results)


def run_calc_validation(inp: ITR1Input, result: ITR1Result) -> ValidationReport:
    """Run all ITR-1 post-computation validation rules."""
    results = validate_itr1_calculation(inp, result)
    return ValidationReport(form_type="ITR1", results=results)


def run_all(inp: ITR1Input, result: ITR1Result) -> ValidationReport:
    """Run both input AND calculation validation, return merged report."""
    return merge_reports(run_input_validation(inp), run_calc_validation(inp, result))
