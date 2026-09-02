"""
Unit tests for app/engine/schedules/tds_tcs's compute_all() -- added while
fixing Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §15.

Run: pytest tests/test_tds_tcs_schedule.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.schedules.tds_tcs import compute_all


@dataclass
class _FakeTds2Entry:
    tds_deducted: Decimal
    tds_claimed_this_year: Decimal = Decimal("0")
    matched_with_26as: bool = True


@dataclass
class _FakeTds3Entry:
    tds_deducted: Decimal
    tds_claimed: Decimal = Decimal("0")
    matched_with_26as: bool = True


def test_tds2_credit_uses_claimed_this_year_not_full_deducted():
    """A taxpayer legitimately carrying forward part of a TDS2 deduction
    (Rule 37BA(3) -- e.g. FD interest TDS'd on accrual, income offered on
    receipt) must only get credit for the amount claimed this year, not the
    full amount deducted -- previously always used the full amount,
    over-claiming credit."""
    entries = [_FakeTds2Entry(tds_deducted=Decimal("10000"), tds_claimed_this_year=Decimal("3000"))]
    result = compute_all(tds2_entries=entries)
    assert result.total_tds_other == Decimal("3000")
    assert result.total_tds == Decimal("3000")


def test_tds2_credit_falls_back_to_full_deducted_when_claimed_unset():
    """A caller that never sets tds_claimed_this_year (e.g. the legacy flat
    router) must keep getting full-claim behavior, not silently zeroed
    credit."""
    entries = [_FakeTds2Entry(tds_deducted=Decimal("10000"))]
    result = compute_all(tds2_entries=entries)
    assert result.total_tds_other == Decimal("10000")


def test_tds3_credit_reaches_total_tds():
    """TDS3 (Section 195, TDS on payments to non-residents) was previously
    never passed to compute_all by any ITR-1/ITR-4 caller, so it never
    reduced computed tax payable at all."""
    entries = [_FakeTds3Entry(tds_deducted=Decimal("50000"), tds_claimed=Decimal("50000"))]
    result = compute_all(tds3_entries=entries)
    assert result.total_tds_non_resident == Decimal("50000")
    assert result.total_tds == Decimal("50000")


def test_tds3_credit_uses_claimed_not_full_deducted():
    entries = [_FakeTds3Entry(tds_deducted=Decimal("50000"), tds_claimed=Decimal("20000"))]
    result = compute_all(tds3_entries=entries)
    assert result.total_tds_non_resident == Decimal("20000")


def test_all_four_credit_types_aggregate_correctly():
    from app.schemas.itr1 import TCSEntry

    tds1 = [_FakeTds2Entry(tds_deducted=Decimal("5000"))]  # reused shape; TDS1 uses tds_deducted directly
    tds2 = [_FakeTds2Entry(tds_deducted=Decimal("10000"), tds_claimed_this_year=Decimal("4000"))]
    tds3 = [_FakeTds3Entry(tds_deducted=Decimal("2000"), tds_claimed=Decimal("2000"))]
    tcs = [TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("1000"),
        tcs_collected=Decimal("100"), tcs_credit_claimed=Decimal("100"),
    )]
    result = compute_all(tds1_entries=tds1, tds2_entries=tds2, tds3_entries=tds3, tcs_entries=tcs)
    assert result.total_tds == Decimal("5000") + Decimal("4000") + Decimal("2000")
    assert result.total_tcs == Decimal("100")
    assert result.total_taxes_credited == result.total_tds + result.total_tcs
