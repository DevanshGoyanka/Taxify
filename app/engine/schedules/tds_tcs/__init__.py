"""TDS/TCS tax credit schedule modules.

Provides ``compute_all()`` which accepts schema-level TDS/TCS entry lists
and returns aggregated totals plus 26AS matched/unmatched breakdowns.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Any


@dataclass
class TdsTcsResult:
    total_tds_salary: Decimal = Decimal("0")
    total_tds_other: Decimal = Decimal("0")
    total_tds_non_resident: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")
    tds_matched_26as: Decimal = Decimal("0")
    tds_unmatched: Decimal = Decimal("0")
    total_tcs: Decimal = Decimal("0")
    tcs_matched_26as: Decimal = Decimal("0")
    tcs_unmatched: Decimal = Decimal("0")
    total_taxes_credited: Decimal = Decimal("0")


def compute_all(
    tds1_entries: Optional[List[Any]] = None,
    tds2_entries: Optional[List[Any]] = None,
    tcs_entries: Optional[List[Any]] = None,
    tds3_entries: Optional[List[Any]] = None,
) -> TdsTcsResult:
    """Aggregate TDS (salary + other + non-resident) and TCS from schema-level entry lists.

    Each entry is expected to have at minimum:
      - ``tds_deducted`` (TDS1/TDS2) or ``tcs_collected`` (TCS) or
        ``tds_claimed``/``tds_deducted`` (TDS3)
      - ``matched_with_26as`` (bool, optional; defaults to True)
    """
    result = TdsTcsResult()

    for e in (tds1_entries or []):
        # TDS1 (salary) uses ``tax_deducted`` in the official input schema;
        # accept the alternate spelling too for mapped legacy records.
        tds_val = getattr(e, "tax_deducted", getattr(e, "tds_deducted", Decimal("0")))
        result.total_tds_salary += tds_val
        result.total_tds += tds_val
        if getattr(e, "matched_with_26as", True):
            result.tds_matched_26as += tds_val
        else:
            result.tds_unmatched += tds_val

    for e in (tds2_entries or []):
        # A TDS2 row's credit for THIS year is tds_claimed_this_year (Rule
        # 37BA(3) lets a taxpayer spread TDS credit across years matching
        # when the corresponding income is offered to tax -- e.g. FD
        # interest TDS'd on accrual but income declared on receipt), not
        # the full amount deducted. Falls back to tds_deducted when the
        # field is unset (0) -- callers that never populate it (e.g. the
        # legacy app/routers/tax.py flat-blob path) get the same
        # full-claim behavior as before; callers that do populate it (the
        # v2 mapper, which defaults it to the full tax when the user
        # doesn't specify a partial claim) get the taxpayer's actual
        # claimed amount. Previously this always used tds_deducted,
        # silently over-claiming TDS credit -- and inflating the computed
        # refund/understating tax payable -- for any taxpayer who
        # correctly entered a partial current-year claim; the emitted
        # ClaimOutOfTotTDSOnAmtPaid JSON field already showed the correct,
        # smaller figure, so the computed liability and the filed JSON
        # were inconsistent with each other.
        claimed_this_year = getattr(e, "tds_claimed_this_year", Decimal("0")) or Decimal("0")
        tds_val = claimed_this_year if claimed_this_year > 0 else getattr(
            e, "tds_deducted", getattr(e, "tax_deducted", Decimal("0"))
        )
        result.total_tds_other += tds_val
        result.total_tds += tds_val
        if getattr(e, "matched_with_26as", True):
            result.tds_matched_26as += tds_val
        else:
            result.tds_unmatched += tds_val

    for e in (tds3_entries or []):
        # TDS3 (Section 195, TDS on payments to non-residents -- e.g. rent
        # paid to an NRI landlord, or an NRI property purchase) was
        # previously never passed to this function by any ITR-1/ITR-4
        # caller at all, so its credit never reduced computed tax payable
        # even though the mapper captured it and the ITD JSON schedule
        # correctly reported it -- a real taxpayer with a genuine TDS3
        # credit got no benefit from it in the computed liability.
        # TDS3Entry's field is ``tds_claimed`` (not ``tds_claimed_this_year``
        # like TDS2/TDS3 in ITR-2's schema), matching the corrected
        # ITR1-R102 validator below.
        tds_val = getattr(e, "tds_claimed", None)
        if not tds_val:
            tds_val = getattr(e, "tds_deducted", Decimal("0"))
        result.total_tds_non_resident += tds_val
        result.total_tds += tds_val
        if getattr(e, "matched_with_26as", True):
            result.tds_matched_26as += tds_val
        else:
            result.tds_unmatched += tds_val

    for e in (tcs_entries or []):
        tcs_val = getattr(
            e,
            "tcs_credit_claimed",
            getattr(e, "tcs_collected", Decimal("0")),
        )
        result.total_tcs += tcs_val
        if getattr(e, "matched_with_26as", True):
            result.tcs_matched_26as += tcs_val
        else:
            result.tcs_unmatched += tcs_val

    result.total_taxes_credited = result.total_tds + result.total_tcs
    return result