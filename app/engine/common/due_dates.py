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

# Filing sections that remain valid once the section 139(1) due date has gone.
# 139(1) is the only section the due date invalidates: after it, an unfiled
# return must go under 139(4) (belated) and a return that was already filed
# must go under 139(5) (revised). The notice-driven sections (142(1), 148,
# 153C, 139(9)) and condonation of delay (119(2)(b)) are unaffected — they
# are triggered by a departmental action, not by the calendar.
BELATED_SECTION = "139(4)"
REVISED_SECTION = "139(5)"
ON_TIME_SECTION = "139(1)"


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


def is_due_date_passed(
    itr_form: str,
    assessment_year: str = "2026-27",
    on_date: Optional[date] = None,
) -> bool:
    """Return whether the section 139(1) due date has gone for this form/AY.

    Args:
        itr_form: One of ``ITR-1``, ``ITR-2``, ``ITR-3``, ``ITR-4``.
        assessment_year: Assessment year string like ``"2026-27"``.
        on_date: The date to judge against; defaults to today.

    Returns:
        True when the filing date is past the due date.  An unknown form
        yields False — an unknown due date is not evidence that it passed.
    """
    due = get_due_date(itr_form, assessment_year)
    if due is None:
        return False
    return (on_date or date.today()) > due


def applicable_filing_section(
    itr_form: str,
    assessment_year: str = "2026-27",
    *,
    original_return_filed: bool = False,
    on_date: Optional[date] = None,
) -> str:
    """Return the filing section that applies for a return filed ``on_date``.

    Before the due date a first return is on-time under 139(1).  After it,
    a return that was never filed is belated under 139(4), and one that was
    already filed can only be corrected as a revised return under 139(5).
    """
    if original_return_filed:
        return REVISED_SECTION
    if is_due_date_passed(itr_form, assessment_year, on_date):
        return BELATED_SECTION
    return ON_TIME_SECTION


def filing_section_due_date_error(
    filing_section: str,
    itr_form: str,
    assessment_year: str = "2026-27",
    on_date: Optional[date] = None,
) -> Optional[str]:
    """Return an actionable message when the section contradicts the due date.

    Only 139(1) can contradict it: it means "on or before the due date", so
    once that date has gone the return is either belated or revised.  The
    portal enforces the same rule, and it does so by dropping the form from
    its ITR list rather than by reporting an error — which is why this has
    to be caught before the return reaches the portal.

    ``on_date`` is the date the return declares it is being filed on — the
    same value that goes into the CBDT ``Verification.Date`` — falling back
    to today when the return does not declare one.  Judging the section
    against any other date would compare it to a date the return does not
    claim.
    """
    if filing_section != ON_TIME_SECTION:
        return None
    due = get_due_date(itr_form, assessment_year)
    if due is None or not is_due_date_passed(itr_form, assessment_year, on_date):
        return None
    return (
        f"Filing section 139(1) means the return is filed on or before the due date, "
        f"but the {itr_form} due date for AY {assessment_year} was {due.isoformat()} "
        f"and it has passed. Use 139(4) (belated) if this return has not been filed "
        f"yet, or 139(5) (revised) with the original acknowledgement number and "
        f"filing date if it has."
    )
