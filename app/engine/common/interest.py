"""Interest u/s 234A, 234B, 234C, fee u/s 234-I, and late fee u/s 234F.

Section 234A: 1% per month (or part-month) on unpaid tax from the day
  immediately following the due date to the date of filing.

Section 234B: 1% per month (or part-month) on the shortfall in advance tax,
  calculated from 1 April of the assessment year to the date of determination
  of income u/s 143(1), or to the date of filing, whichever is earlier.
  Triggered when advance tax paid < 90% of assessed tax.

Section 234C: Deferred installment interest at 1% per month for shortfall in
  quarterly advance tax installments. Different rules apply for assessees
  declaring profits u/s 44AD/44ADA (single installment by 15 March).

Section 234-I (CBDT Rule R328): Fee for furnishing a revised return u/s 139(5)
  filed after 31 December of the assessment year. Rs. 5,000 if total income
  exceeds Rs. 5 lakh; Rs. 1,000 if total income <= Rs. 5 lakh. Does not apply
  to original returns u/s 139(1) or belated returns u/s 139(4).

Section 234F: Rs 0 (on/before due date), Rs 1,000 (<= 5L TI, after due date
  before Dec 31), Rs 5,000 (>5L TI, after due date before Dec 31),
  Rs 10,000 (any TI, filed after Dec 31).
"""

from decimal import Decimal, ROUND_UP
from datetime import date

_ZERO = Decimal("0")


def _months_between(start: date, end: date) -> int:
    """Count calendar months where a part-month counts as a full month."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        months += 1
    return max(0, months)


def compute_234a(tax_payable: Decimal, filing_date: date, due_date: date) -> Decimal:
    """1% per month on unpaid tax from due date to filing date."""
    if filing_date <= due_date:
        return _ZERO
    months = _months_between(due_date, filing_date)
    interest = tax_payable * Decimal(months) / Decimal("100")
    return interest.quantize(Decimal("1"), rounding=ROUND_UP)


def compute_234b(
    assessed_tax: Decimal,
    advance_tax_paid: Decimal,
    filing_date: date,
    ay_start: date,
    self_assessment_payments: list[tuple[date, Decimal]] | None = None,
) -> Decimal:
    """Compute 234B interest on the actual outstanding balance over time.

    Args:
        assessed_tax: Tax after TDS/TCS credits, before advance-tax credit.
        advance_tax_paid: Total advance tax paid during the previous year.
        filing_date: Return filing/determination date.
        ay_start: 1 April of the assessment year.
        self_assessment_payments: Validated self-assessment challans as
            ``(deposit_date, amount)`` pairs. Each payment reduces the 234B
            principal from its actual deposit date.

    Returns:
        Interest at 1% per month or part-month, rounded up to whole rupees.
    """
    if assessed_tax < Decimal("10000") or assessed_tax <= 0:
        return _ZERO
    if advance_tax_paid >= assessed_tax * Decimal("0.90") or filing_date <= ay_start:
        return _ZERO

    # In a reconciliation preview, a validated SAT challan can be entered
    # after the default filing-date assumption. Interest must run until the
    # actual payment that reduces the outstanding principal, not stop early
    # at that default date.
    raw_payments = [
        (payment_date, amount)
        for payment_date, amount in (self_assessment_payments or [])
        if amount > 0 and payment_date > ay_start
    ]
    reconciliation_end_date = max(
        [filing_date, *(payment_date for payment_date, _ in raw_payments)],
    )

    outstanding = max(_ZERO, assessed_tax - advance_tax_paid)
    period_start = ay_start
    interest = _ZERO
    valid_payments = sorted(
        (
            (payment_date, amount)
            for payment_date, amount in raw_payments
            if payment_date <= reconciliation_end_date
        ),
        key=lambda payment: payment[0],
    )

    for payment_date, amount in valid_payments:
        if outstanding <= 0:
            break
        interest += outstanding * Decimal(_months_between(period_start, payment_date)) / Decimal("100")
        outstanding = max(_ZERO, outstanding - amount)
        period_start = payment_date

    if outstanding > 0:
        interest += outstanding * Decimal(_months_between(period_start, reconciliation_end_date)) / Decimal("100")

    return interest.quantize(Decimal("1"), rounding=ROUND_UP)


def compute_234c(advance_tax_paid: list[Decimal], total_assessed_tax: Decimal,
                 ay_start: date, is_presumptive_44ad_44ada: bool = False) -> Decimal:
    """Deferred installment interest at 1% per month for quarterly shortfalls.

    Installment due dates and cumulative percentages:
      - 15 June: 15%
      - 15 September: 45%
      - 15 December: 75%
      - 15 March: 100%

    For presumptive (44AD/44ADA) taxpayers, only the 15 March (100%) installment
    is required.

    Shortfall is computed cumulatively: if cumulative paid < cumulative required,
    interest is levied at 1% on the shortfall for 3 months (one quarter).

    Section 234C(1)(b) proviso: no interest is charged for the 15 June or
    15 September installment specifically if cumulative advance tax paid by
    that date is at least 12% (June) or 36% (September) of the tax due on
    returned income -- lower "safe harbor" thresholds than the 15%/45%
    otherwise required for those two installments. This proviso applies
    only to the June and September installments; December (75%) and March
    (100%) have no such safe harbor and are enforced strictly.
    """
    if total_assessed_tax < Decimal("10000") or total_assessed_tax <= 0:
        return Decimal("0")
    if not advance_tax_paid:
        advance_tax_paid = [Decimal("0")]

    if is_presumptive_44ad_44ada:
        required_pcts = [Decimal("1.00")]
        safe_harbor_pcts = [None]
        advance_tax_paid = [sum(advance_tax_paid, Decimal("0"))]
    else:
        required_pcts = [Decimal("0.15"), Decimal("0.45"), Decimal("0.75"), Decimal("1.00")]
        safe_harbor_pcts = [Decimal("0.12"), Decimal("0.36"), None, None]

    total_interest = Decimal("0")
    cumulative_paid = Decimal("0")

    for i, req_pct in enumerate(required_pcts):
        paid = advance_tax_paid[i] if i < len(advance_tax_paid) else Decimal("0")
        cumulative_paid += paid
        safe_harbor_pct = safe_harbor_pcts[i]
        if safe_harbor_pct is not None and cumulative_paid >= total_assessed_tax * safe_harbor_pct:
            continue
        required = total_assessed_tax * req_pct
        shortfall = required - cumulative_paid
        if shortfall > 0:
            # CBDT: 1% per month for 3 months per quarter. The final (March)
            # installment shortfall attracts only 1 month of interest
            # (the installment falls on 15 March, leaving ~1 month to the
            # 31 March determination date).
            months = Decimal("1") if i == len(required_pcts) - 1 else Decimal("3")
            total_interest += shortfall * months / Decimal("100")

    return total_interest.quantize(Decimal("1"), rounding=ROUND_UP)


def compute_234i(filing_date: date, due_date: date, total_income: Decimal,
                 filing_section: object = None) -> Decimal:
    """Fee u/s 234-I for furnishing a revised return u/s 139(5) after 31 Dec.

    CBDT Rule R328: Applies only when:
      - filing_section identifies ``139(5)`` / code ``17`` (revised return), AND
      - the return is filed after 31 December of the assessment year.

    Amount:
      - Rs 5,000 if total income > Rs 5,00,000
      - Rs 1,000 if total income <= Rs 5,00,000
    """
    section_value = getattr(filing_section, "value", filing_section)
    if str(section_value) not in {"139(5)", "17"}:
        return _ZERO
    if filing_date <= due_date:
        return _ZERO

    fy_end_year = due_date.year
    dec_31 = date(fy_end_year, 12, 31)

    if filing_date <= dec_31:
        return _ZERO

    return Decimal("1000") if total_income <= Decimal("500000") else Decimal("5000")


def compute_234f(filing_date: date, due_date: date, total_income: Decimal) -> Decimal:
    """Late filing fee u/s 234F.

    Post Finance Act 2021 (applicable AY 2021-22 onwards, still the law for
    AY 2026-27), Section 234F has only two tiers -- the pre-2021 third tier
    (Rs 10,000 for filing after 31 December) was removed; the maximum is now
    Rs 5,000 regardless of how late within the belated-filing window the
    return is filed. The official ITR-1 JSON schema enforces this directly
    (LateFilingFee234F has `maximum: 5000`) -- confirmed by a schema
    validation failure when the old Rs 10,000 tier was still implemented
    here (found 2026-09-03 while fixing the filing_date wiring bug that had
    kept this branch dormant; see
    Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md).

    - Filed on or before due date: Rs 0
    - Filed after due date: Rs 5,000 (Rs 1,000 if total income <= Rs 5,00,000)
    """
    if filing_date <= due_date:
        return _ZERO
    return Decimal("1000") if total_income <= Decimal("500000") else Decimal("5000")
