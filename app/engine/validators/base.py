"""
Core validation framework for CBDT Category A/B/D rules.

Defines the data model for individual rule results and aggregate reports.
Form-specific rules live in per-form subpackages (itr1/, itr4/, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """CBDT Category of Defect."""
    A = "A"   # Return WILL NOT be allowed to upload. Error message displayed.
    B = "B"   # Return uploads, but taxpayer warned of possible 139(9) defect.
    D = "D"   # Return uploads, info that supporting docs may be required.


@dataclass
class ValidationResult:
    """Result of a single validation rule execution."""
    rule_id: str                                    # e.g. "ITR1-R022"
    severity: Severity
    passed: bool
    message: str
    field_path: str = ""                            # JSON path or schema field name
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "passed": self.passed,
            "message": self.message,
            "field_path": self.field_path,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ValidationReport:
    """Aggregate report of all validation rules for one ITR form."""
    form_type: str                                  # "ITR1", "ITR4", etc.
    results: list[ValidationResult] = field(default_factory=list)

    # Summary
    total: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    info: int = 0

    # Convenience
    blocking_errors: list[ValidationResult] = field(default_factory=list)

    def __post_init__(self):
        self._compute_summary()

    def _compute_summary(self):
        self.total = len(self.results)
        self.passed = sum(1 for r in self.results if r.passed)
        self.failed = 0
        self.warnings = 0
        self.info = 0
        self.blocking_errors = []
        for r in self.results:
            if r.passed:
                continue
            if r.severity == Severity.A:
                self.failed += 1
                self.blocking_errors.append(r)
            elif r.severity == Severity.B:
                self.warnings += 1
            elif r.severity == Severity.D:
                self.info += 1

    @property
    def can_upload(self) -> bool:
        """True when no Category A (blocking) failures exist."""
        return self.failed == 0

    def to_dict(self) -> dict:
        return {
            "form_type": self.form_type,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "info": self.info,
            "can_upload": self.can_upload,
            "results": [r.to_dict() for r in self.results],
        }


def merge_reports(*reports: ValidationReport) -> ValidationReport:
    """Merge multiple validation reports (e.g. input + calculation)."""
    merged = ValidationReport(form_type=reports[0].form_type if reports else "")
    merged.results = []
    for report in reports:
        merged.results.extend(report.results)
    merged._compute_summary()
    return merged
