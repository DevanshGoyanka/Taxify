"""Assessment-year-aware due dates for ITR form filing.

For AY 2026-27 (FY 2025-26), the CBDT due dates are:
  - ITR-1 (Sahaj): 31 July 2026
  - ITR-2: 31 July 2026
  - ITR-3: 31 August 2026
  - ITR-4 (Sugam): 31 August 2026

These are the non-audit due dates under section 139(1).  Audit cases
(section 44AB) get 31 October, but that is handled separately by the
eligibility layer, not by this default-date resolver.
"""

from datetime import date
from typing import Optional


def get_due_date(itr_form: str, assessment_year: str = "2026-27") -> Optional[date]:
    """Return the default filing due date for the given ITR form and AY.

    Args:
        itr_form: One of ``ITR-1``, ``ITR-2``, ``ITR-3``, ``ITR-4``.
        assessment_year: Assessment year string like ``"2026-27"``.

    Returns:
        The due date as a ``date``, or ``None`` if the combination is unknown.
    """
    form = itr_form.upper().replace("-", "").strip()
    try:
        due_year = int(assessment_year.split("-")[0])
    except (ValueError, IndexError, AttributeError):
        due_year = 2026  # default to AY 2026-27

    if form in ("ITR1", "ITR2"):
        return date(due_year, 7, 31)
    if form in ("ITR3", "ITR4"):
        return date(due_year, 8, 31)
    return None


def get_default_filing_date() -> date:
    """Return today's date as the default filing date for pre-filing previews."""
    return date.today()
