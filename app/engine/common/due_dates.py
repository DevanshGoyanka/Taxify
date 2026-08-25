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


def resolve_filing_dates(
    itr_form: str,
    assessment_year: str = "2026-27",
    verification_date: Optional[str] = None,
) -> tuple[Optional[date], Optional[date]]:
    """Return the ``(filing_date, due_date)`` pair the calculators need.

    The interest and late-fee block in every calculator is guarded by
    ``if filing_date and due_date:``. Without both, sections 234A/B/C and the
    section 234F late-filing fee are skipped in full — so a belated return
    carries the right ``ReturnFileSec`` but a zero fee, which understates the
    liability rather than merely omitting a field.

    ``verification_date`` is the date the return declares it is filed on (the
    canonical draft's ``verification.date``). It is the only date the return
    itself claims, so it is what the fee must be judged against; when the draft
    has not set one yet, the return is being prepared now, so today applies.

    Args:
        itr_form: One of ``ITR-1``, ``ITR-2``, ``ITR-3``, ``ITR-4``.
        assessment_year: Assessment year string like ``"2026-27"``.
        verification_date: ISO date string from the draft, or None.

    Returns:
        ``(filing_date, due_date)``. ``due_date`` is None for an unknown form,
        which leaves the calculators in their existing neutral state instead of
        charging a fee against a due date nobody knows.
    """
    filing_date: Optional[date] = None
    if verification_date:
        try:
            filing_date = date.fromisoformat(str(verification_date).strip()[:10])
        except ValueError:
            filing_date = None
    if filing_date is None:
        filing_date = date.today()
    return filing_date, get_due_date(itr_form, assessment_year)


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

    Two sections can contradict it, in opposite directions:

    * 139(1) means "on or before the due date", so once that date has gone the
      return is either belated or revised.  The portal enforces this by dropping
      the form from its ITR list rather than by reporting an error, which is why
      it has to be caught before the return reaches the portal.
    * 139(4) means "after the due date".  A return filed on or before the due
      date is simply not belated, and declaring it so understates nothing but
      misstates the return — the portal rejects the combination.

    139(5) is deliberately not checked: a revised return may be filed either
    side of the due date, so its date carries no contradiction.

    The two directions matter independently because the due dates differ by
    form — ITR-1/ITR-2 fall on 31 July while ITR-3/ITR-4 run to 31 August — so
    in August an ITR-1 must be belated on exactly the day an ITR-4 must not be.

    ``on_date`` is the date the return declares it is being filed on — the
    same value that goes into the CBDT ``Verification.Date`` — falling back
    to today when the return does not declare one.  Judging the section
    against any other date would compare it to a date the return does not
    claim.
    """
    due = get_due_date(itr_form, assessment_year)
    if due is None:
        return None
    passed = is_due_date_passed(itr_form, assessment_year, on_date)

    if filing_section == ON_TIME_SECTION and passed:
        return (
            f"Filing section 139(1) means the return is filed on or before the due date, "
            f"but the {itr_form} due date for AY {assessment_year} was {due.isoformat()} "
            f"and it has passed. Use 139(4) (belated) if this return has not been filed "
            f"yet, or 139(5) (revised) with the original acknowledgement number and "
            f"filing date if it has."
        )
    if filing_section == BELATED_SECTION and not passed:
        filed_on = (on_date or date.today()).isoformat()
        return (
            f"Filing section 139(4) means the return is filed after the due date, but "
            f"the {itr_form} due date for AY {assessment_year} is {due.isoformat()} and "
            f"it has not passed — this return is dated {filed_on}. Use 139(1) while the "
            f"return is still on time, or 139(5) if you are revising a return that was "
            f"already filed."
        )
    return None
