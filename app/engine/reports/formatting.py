"""Display formatting helpers for the Statement of Income report.

Pure presentation utilities only — no tax logic lives here. Every amount
shown in the report is sourced from the calculator's own result fields;
this module only decides how a ``Decimal``/date/assessment-year string is
printed on the page (Indian digit grouping, DD-Mon-YYYY dates, etc).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Union

_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _indian_group(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    last3 = digits[-3:]
    rest = digits[:-3]
    parts: list[str] = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts) + "," + last3


def format_inr(
    amount: Optional[Union[Decimal, int, float]],
    *,
    zero_as_dash: bool = False,
) -> str:
    """Format a rupee amount with Indian digit grouping, no decimals.

    Negative amounts are shown in parentheses (standard accounting style).
    """
    if amount is None:
        return "-" if zero_as_dash else "0"
    amt = Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if amt == 0:
        return "-" if zero_as_dash else "0"
    negative = amt < 0
    grouped = _indian_group(str(abs(int(amt))))
    return f"({grouped})" if negative else grouped


def format_date(value: Optional[Union[str, date, datetime]]) -> str:
    """Render a date as ``DD-Mon-YYYY`` (locale-independent month names)."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day:02d}-{_MONTHS[value.month - 1]}-{value.year}"


def format_assessment_year(ay: str) -> str:
    """``"2026-27"`` -> ``"2026-2027"``."""
    if not ay or "-" not in ay:
        return ay or ""
    start, end = ay.split("-", 1)
    if len(end) == 2 and len(start) == 4:
        end = start[:2] + end
    return f"{start}-{end}"


def previous_year_label(ay: str) -> str:
    """``"2026-27"`` -> ``"2025-2026"`` (the year preceding the AY start)."""
    if not ay or "-" not in ay:
        return ""
    try:
        start = int(ay.split("-", 1)[0])
    except ValueError:
        return ""
    return f"{start - 1}-{start}"
