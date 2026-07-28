"""ITR-2 validation runner."""
from app.engine.validators.itr2.input_rules import run_input_validation
from app.engine.validators.itr2.calc_rules import run_calc_validation

__all__ = ["run_input_validation", "run_calc_validation"]