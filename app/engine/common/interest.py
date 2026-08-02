"""Interest u/s 234A, 234B, 234C, fees u/s 234I, and late fee u/s 234F.

Section 234A: 1% per month (or part-month) on unpaid tax from the day
  immediately following the due date to the date of filing.

Section 234B: 1% per month (or part-month) on the shortfall in advance tax,
  calculated from 1 April of the assessment year to the date of determination
  of income u/s 143(1), or to the date of filing, whichever is earlier.
  Triggered when advance tax paid < 90% of assessed tax.

Section 234C: Deferred installment interest at 1% per month for shortfall in
  quarterly advance tax installments. Different rules apply for assessees
  declaring profits u/s 44AD/44ADA (single installment by 15 March).

Section 234I: Fee for default in furnishing return u/s 139(1) when a return is
  revised or belated. Rs 1,000 if total income <= Rs 5,00,000; otherwise
  Rs 5,000. Applies when the return is filed after the due date u/s 139(1)
  (i.e., belated u/s 139(4) or revised u/s 139(5)) after 31 December of the
  relevant assessment year.

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


def compute_234b(assessed_tax: Decimal, advance_tax_paid: Decimal,
                 filing_date: date, ay_start: date) -> Decimal:
    """1% per month for shortfall in advance tax from 1 Apr of AY to filing date.

    ``assessed_tax`` = tax on total income (TDS/TCS already credited).
    Non-taxpaying if assessed_tax < Rs 10,000.
    Triggered if advance_tax_paid < 90% of assessed_tax.
    Interest runs from April 1 of AY to the date of determination (filing date).
    """
    if assessed_tax < Decimal("10000") or assessed_tax <= 0:
        return Decimal("0")
    if advance_tax_paid >= assessed_tax * Decimal("0.90"):
        return Decimal("0")

    shortfall = assessed_tax - advance_tax_paid
    months = _months_between(ay_start, filing_date)
    interest = shortfall * Decimal(months) / Decimal("100")
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
    """
    if total_assessed_tax < Decimal("10000") or total_assessed_tax <= 0:
        return Decimal("0")
    if not advance_tax_paid:
        advance_tax_paid = [Decimal("0")]

    if is_presumptive_44ad_44ada:
        required_pcts = [Decimal("1.00")]
        advance_tax_paid = [sum(advance_tax_paid, Decimal("0"))]
    else:
        required_pcts = [Decimal("0.15"), Decimal("0.45"), Decimal("0.75"), Decimal("1.00")]

    total_interest = Decimal("0")
    cumulative_paid = Decimal("0")

    for i, req_pct in enumerate(required_pcts):
        paid = advance_tax_paid[i] if i < len(advance_tax_paid) else Decimal("0")
        cumulative_paid += paid
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


def compute_234f(filing_date: date, due_date: date, total_income: Decimal) -> Decimal:
    """Late filing fee u/s 234F.

    - Filed on or before due date: Rs 0
    - Filed after due date but on or before 31 Dec: Rs 5,000 (Rs 1,000 if TI <= 5L)
    - Filed after 31 Dec: Rs 10,000
    """
    if filing_date <= due_date:
        return _ZERO

    fy_end_year = due_date.year
    dec_31 = date(fy_end_year, 12, 31)

    if filing_date <= dec_31:
        return Decimal("1000") if total_income <= Decimal("500000") else Decimal("5000")
    return Decimal("10000")


def compute_234i(filing_date: date, due_date: date, total_income: Decimal) -> Decimal:
    """Fee u/s 234I for default in furnishing return u/s 139(1).

    Applies to belated (u/s 139(4)) or revised (u/s 139(5)) returns filed
    after 31 December of the assessment year.

    - Filed on or before the due date u/s 139(1): Rs 0
    - Filed after the due date but on or before 31 December: Rs 1,000 if
      total income <= Rs 5,00,000, otherwise Rs 5,000
    - Filed after 31 December: Rs 5,000 (Rs 1,000 if total income <= Rs 5,00,000)

    Note: This fee is distinct from the late-filing fee u/s 234F. Section 234I
    applies specifically when a return is revised under section 139(5) or
    filed belatedly under section 139(4) after the December cut-off of the
    relevant assessment year.
    """
    if filing_date <= due_date:
        return _ZERO

    fy_end_year = due_date.year
    dec_31 = date(fy_end_year, 12, 31)

    is_low_income = total_income <= Decimal("500000")
    if filing_date <= dec_31:
        return Decimal("1000") if is_low_income else Decimal("5000")
    return Decimal("1000") if is_low_income else Decimal("5000")
