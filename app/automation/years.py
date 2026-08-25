"""Strict assessment-year and financial-year value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR_PATTERN = re.compile(r"^(?:AY )?(\d{4})-(\d{2})$")
_MIN_YEAR = 1900
_MAX_YEAR = 2200


@dataclass(frozen=True, slots=True)
class TaxYearContext:
    """Represent one contiguous Indian assessment year and its derived years.

    Args:
        assessment_year: Assessment year in ``YYYY-YY`` or ``AY YYYY-YY`` form.

    Raises:
        ValueError: If the value is absent, malformed, non-contiguous, or outside
            the supported 1900 through 2200 range.
    """

    assessment_year: str
    fiscal_year: str = ""
    prior_assessment_year: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize all year representations."""
        value = self.assessment_year
        if value is None or not isinstance(value, str):
            raise ValueError("Assessment year must be a string in YYYY-YY form.")
        match = _YEAR_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError("Assessment year must use contiguous YYYY-YY form.")
        start = int(match.group(1))
        end = int(match.group(2))
        if start < _MIN_YEAR or start >= _MAX_YEAR:
            raise ValueError("Assessment year is outside the supported range.")
        if end != (start + 1) % 100:
            raise ValueError("Assessment year must contain contiguous years.")

        ay = _format_range(start)
        fy = _format_range(start - 1)
        object.__setattr__(self, "assessment_year", ay)
        object.__setattr__(self, "fiscal_year", fy)
        object.__setattr__(self, "prior_assessment_year", fy)

    @classmethod
    def from_assessment_year(cls, value: str) -> "TaxYearContext":
        """Build a context from an assessment-year value.

        Args:
            value: Assessment year in ``YYYY-YY`` or ``AY YYYY-YY`` form.

        Returns:
            A frozen normalized year context.
        """
        return cls(value)

    @classmethod
    def from_financial_year(cls, value: str) -> "TaxYearContext":
        """Build a context from a contiguous financial-year value.

        Args:
            value: Financial year in ``YYYY-YY`` form.

        Returns:
            A context whose assessment year immediately follows ``value``.

        Raises:
            ValueError: If the financial year is malformed or non-contiguous.
        """
        if value is None or not isinstance(value, str):
            raise ValueError("Financial year must be a string in YYYY-YY form.")
        match = re.fullmatch(r"(\d{4})-(\d{2})", value)
        if match is None:
            raise ValueError("Financial year must use contiguous YYYY-YY form.")
        start = int(match.group(1))
        end = int(match.group(2))
        if end != (start + 1) % 100:
            raise ValueError("Financial year must contain contiguous years.")
        return cls(_format_range(start + 1))

    @classmethod
    def parse(cls, value: str) -> "TaxYearContext":
        """Parse an assessment-year string into a validated context.

        Args:
            value: Assessment year in ``YYYY-YY`` or ``AY YYYY-YY`` form.

        Returns:
            A frozen normalized year context.
        """
        return cls(value)

    @property
    def ay(self) -> str:
        """Return the normalized assessment year without an ``AY`` prefix."""
        return self.assessment_year

    @property
    def financial_year(self) -> str:
        """Return the financial year using the unabbreviated domain name."""
        return self.fiscal_year

    @property
    def fy(self) -> str:
        """Return the normalized financial year."""
        return self.fiscal_year

    @property
    def prior_ay(self) -> str:
        """Return the preceding assessment year."""
        return self.prior_assessment_year

    @property
    def assessment_year_filename(self) -> str:
        """Return the assessment year normalized for filenames."""
        return self.assessment_year.replace("-", "_")

    @property
    def fiscal_year_filename(self) -> str:
        """Return the financial year normalized for filenames."""
        return self.fiscal_year.replace("-", "_")

    @property
    def prior_assessment_year_filename(self) -> str:
        """Return the prior assessment year normalized for filenames."""
        return self.prior_assessment_year.replace("-", "_")

    @property
    def ay_filename(self) -> str:
        """Return the short assessment-year filename representation."""
        return self.assessment_year_filename

    @property
    def fy_filename(self) -> str:
        """Return the short financial-year filename representation."""
        return self.fiscal_year_filename


def _format_range(start: int) -> str:
    """Format a year and its successor as an Indian year range."""
    return f"{start:04d}-{(start + 1) % 100:02d}"
