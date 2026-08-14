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
) -> TdsTcsResult:
    """Aggregate TDS (salary + other) and TCS from schema-level entry lists.

    Each entry is expected to have at minimum:
      - ``tds_deducted`` (TDS1/TDS2) or ``tcs_collected`` (TCS)
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
        tds_val = getattr(e, "tds_deducted", getattr(e, "tax_deducted", Decimal("0")))
        result.total_tds_other += tds_val
        result.total_tds += tds_val
        if getattr(e, "matched_with_26as", True):
            result.tds_matched_26as += tds_val
        else:
            result.tds_unmatched += tds_val

    for e in (tcs_entries or []):
        tcs_val = getattr(e, "tcs_collected", Decimal("0"))
        result.total_tcs += tcs_val
        if getattr(e, "matched_with_26as", True):
            result.tcs_matched_26as += tcs_val
        else:
            result.tcs_unmatched += tcs_val

    result.total_taxes_credited = result.total_tds + result.total_tcs
    return result