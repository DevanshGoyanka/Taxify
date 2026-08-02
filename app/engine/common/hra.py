"""House Rent Allowance (HRA) exemption u/s 10(13A).

The exempt portion of HRA is the **least of** the three statutory
conditions:

  1. Actual HRA received during the period of rented accommodation.
  2. Rent paid minus 10% of salary (basic + DA forming part of retirement
     benefits).  Where the result is negative, this condition is zero.
  3. 50% of salary if the assessee lives in a metro city (Mumbai, Delhi,
     Kolkata, Chennai); otherwise 40% of salary.

"Salary" for HRA means basic salary + dearness allowance (if it forms part
of retirement benefits per CBDT Circular 12/2001).  The exemption is
available only under the old regime; the new regime (115BAC) disallows it.

This module performs the statutory computation so the caller never has to
trust a frontend-supplied exempt amount.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

_ZERO = Decimal("0")


@dataclass(frozen=True)
class HRAExemptionResult:
    """Complete HRA exemption computation result.

    Attributes:
        actual_hra_received: Condition 1 — total HRA received.
        rent_minus_10pct_salary: Condition 2 — rent paid less 10% of salary.
        salary_factor: Condition 3 — 50%/40% of salary based on metro status.
        exempt_amount: The statutory exemption (least of the three).
        is_metro: Whether the city is a metro for the 50% factor.
    """

    actual_hra_received: Decimal = _ZERO
    rent_minus_10pct_salary: Decimal = _ZERO
    salary_factor: Decimal = _ZERO
    exempt_amount: Decimal = _ZERO
    is_metro: bool = False


def compute_hra_exemption(
    *,
    actual_hra_received: Decimal = _ZERO,
    rent_paid: Decimal = _ZERO,
    salary: Decimal = _ZERO,
    is_metro: bool = False,
) -> HRAExemptionResult:
    """Compute the HRA exemption u/s 10(13A) as the least of three conditions.

    Args:
        actual_hra_received: Total HRA received for the period of rented
            accommodation.
        rent_paid: Total rent paid for the same period.
        salary: Basic salary + DA (forming part of retirement benefits) used
            for the 10% and 50%/40% computations.
        is_metro: True if the assessee resides in a metro city (Mumbai, Delhi,
            Kolkata, Chennai) — 50% of salary applies; False — 40% applies.

    Returns:
        A typed result with all three conditions and the final exempt amount
        (the least of the three, never negative).
    """
    # Condition 1 — actual HRA received.
    cond1 = max(_ZERO, actual_hra_received)

    # Condition 2 — rent paid minus 10% of salary (floor at zero).
    cond2 = max(_ZERO, rent_paid - (salary * Decimal("0.10")))

    # Condition 3 — 50% of salary (metro) / 40% of salary (non-metro).
    factor = Decimal("0.50") if is_metro else Decimal("0.40")
    cond3 = salary * factor

    exempt = min(cond1, cond2, cond3)

    return HRAExemptionResult(
        actual_hra_received=cond1,
        rent_minus_10pct_salary=cond2,
        salary_factor=cond3,
        exempt_amount=exempt,
        is_metro=is_metro,
    )


def compute_hra_from_details(details: Optional[object]) -> HRAExemptionResult:
    """Compute HRA exemption from an ``HRADetails``-like schema object.

    The schema object must expose ``actual_hra_received``, ``rent_paid``,
    ``salary_for_hra``, and ``is_metro_city`` attributes.  If ``details`` is
    None, a zero-exemption result is returned.

    Args:
        details: An ``HRADetails`` (or compatible) schema instance.

    Returns:
        A typed HRA exemption result.
    """
    if details is None:
        return HRAExemptionResult()
    return compute_hra_exemption(
        actual_hra_received=Decimal(str(getattr(details, "actual_hra_received", _ZERO) or _ZERO)),
        rent_paid=Decimal(str(getattr(details, "rent_paid", _ZERO) or _ZERO)),
        salary=Decimal(str(getattr(details, "salary_for_hra", _ZERO) or _ZERO)),
        is_metro=bool(getattr(details, "is_metro_city", False)),
    )
