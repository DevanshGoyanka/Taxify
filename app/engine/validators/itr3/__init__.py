"""ITR-3 validation runner."""
from app.engine.validators.itr3.input_rules import run_input_validation
from app.engine.validators.itr3.calc_rules import run_calc_validation

__all__ = ["run_input_validation", "run_calc_validation"]