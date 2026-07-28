"""ITR-2 input validation rules (stub)."""

from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class InputRuleResult:
    rule_id: str = ""
    passed: bool = True
    message: str = ""
    field: str = ""


@dataclass
class ValidationReport:
    rules: List[InputRuleResult] = field(default_factory=list)
    blocking_errors: List[InputRuleResult] = field(default_factory=list)

    @property
    def can_upload(self) -> bool:
        return len(self.blocking_errors) == 0

    def to_dict(self) -> dict:
        return {"rules": len(self.rules), "blocking_errors": len(self.blocking_errors)}


def run_input_validation(input_data: Any) -> ValidationReport:
    return ValidationReport()
