"""ITR-2 validation entry points."""

from app.engine.validators.itr2.input_rules import run_input_validation
from app.engine.validators.itr2.calc_rules import run_calc_validation
from app.engine.validators.base import ValidationReport, merge_reports
from app.engine.calculators.itr2 import ITR2Result
from app.schemas.itr2 import ITR2Input


def run_all(inp: ITR2Input, result: ITR2Result) -> ValidationReport:
    """Run pre- and post-computation ITR-2 validation.

    Args:
        inp: Source ITR-2 input.
        result: Computed ITR-2 result.

    Returns:
        A merged standard validation report.
    """
    return merge_reports(run_input_validation(inp), run_calc_validation(inp, result))


__all__ = ["run_input_validation", "run_calc_validation", "run_all"]