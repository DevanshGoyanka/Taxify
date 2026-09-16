"""Arithmetic validation for the AY 2026-27 ITR-3 PARTA_PL sequence."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any


class PartAPLArithmeticError(ValueError):
    """Raised when explicitly supplied PARTA_PL totals contradict their inputs."""


def _nested(source: Mapping[str, Any], *path: str) -> Any:
    """Return a raw nested value, or ``None`` when any path component is absent."""
    current: Any = source
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _decimal(value: Any) -> Decimal | None:
    """Convert an explicitly supplied finite scalar to Decimal."""
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _check(
    source: Mapping[str, Any],
    total_path: tuple[str, ...],
    operand_paths: tuple[tuple[str, ...], ...],
    operation: str,
) -> bool:
    """Check one formula only when its total and every operand are supplied."""
    total = _decimal(_nested(source, *total_path))
    operands = [_decimal(_nested(source, *path)) for path in operand_paths]
    if total is None or any(operand is None for operand in operands):
        return False
    values = [operand for operand in operands if operand is not None]
    expected = values[0]
    if operation == "add":
        for value in values[1:]:
            expected += value
    else:
        for value in values[1:]:
            expected -= value
    if total != expected:
        label = ".".join(total_path)
        raise PartAPLArithmeticError(
            f"PARTA_PL arithmetic contradiction at {label}: supplied {total} "
            f"but expected {expected}."
        )
    return True


def validate_parta_pl_arithmetic(source: Mapping[str, Any]) -> None:
    """Reject contradictory complete PARTA_PL arithmetic chains.

    The official AY 2026-27 sequence is checked as follows: total credits are
    gross profit transferred from the trading account plus total other income;
    PBIDTA is total credits less operating expenditure; PBT is PBIDTA less
    interest and depreciation/amortisation; and PAT is PBT less current and
    deferred tax. A chain is skipped when any required operand is absent, so
    incomplete workspaces are not rejected and no zero is fabricated.

    Args:
        source: Raw PARTA_PL workspace mapping, before typed default values are
            applied.

    Raises:
        PartAPLArithmeticError: If a supplied complete formula is inconsistent.
    """
    if not isinstance(source, Mapping):
        return
    credits = ("CreditsToPL",)
    debits = ("DebitsToPL",)
    tax = ("TaxProvAppr",)
    required_paths = (
        ("Expenditure",),
        credits + ("GrossProfitTrnsfFrmTrdAcc",),
        credits + ("OthIncome", "TotOthIncome"),
        credits + ("TotCreditsToPL",),
        debits + ("PBIDTA",),
        debits + ("InterestExpdrtDtls", "InterestExpdr"),
        debits + ("DepreciationAmort",),
        debits + ("PBT",),
        tax + ("ProvForCurrTax",),
        tax + ("ProvDefTax",),
        tax + ("ProfitAfterTax",),
    )
    if any(_decimal(_nested(source, *path)) is None for path in required_paths):
        return
    _check(
        source,
        credits + ("TotCreditsToPL",),
        (credits + ("GrossProfitTrnsfFrmTrdAcc",), credits + ("OthIncome", "TotOthIncome")),
        "add",
    )
    _check(
        source,
        debits + ("PBIDTA",),
        (credits + ("TotCreditsToPL",), ("Expenditure",)),
        "subtract",
    )
    _check(
        source,
        debits + ("PBT",),
        (debits + ("PBIDTA",), debits + ("InterestExpdrtDtls", "InterestExpdr"), debits + ("DepreciationAmort",)),
        "subtract",
    )
    _check(
        source,
        tax + ("ProfitAfterTax",),
        (debits + ("PBT",), tax + ("ProvForCurrTax",), tax + ("ProvDefTax",)),
        "subtract",
    )


__all__ = ["PartAPLArithmeticError", "validate_parta_pl_arithmetic"]
