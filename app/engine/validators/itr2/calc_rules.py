"""ITR-2 calculation validation rules (stub)."""

from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class CalcRuleResult:
    rule_id: str = ""
    passed: bool = True
    message: str = ""
    field: str = ""


@dataclass
class CalcValidationReport:
    rules: List[CalcRuleResult] = field(default_factory=list)

    @property
    def can_upload(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {"rules": len(self.rules)}


def run_calc_validation(input_data: Any, result: Any) -> CalcValidationReport:
    return CalcValidationReport()
