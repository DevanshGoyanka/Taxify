"""Regression tests for Section 112A calculation unification.

These tests verify:
1. A manually-entered PURCHASE-ONLY row (no sale) does NOT produce a gain.
2. Only one canonical 112A calculation path exists.
"""

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("PORTAL_ENCRYPTION_KEY", "BF4X7PwLyjUJAZ68rDLJ7ba33LIeR5EyqS4CJkAyeAE=")

from decimal import Decimal

import pytest

from app.engine.schedules.restricted_112a import compute_restricted_112a


def test_purchase_only_row_produces_no_gain():
    """A manually entered purchase with NO sale must not be treated as a gain."""
    rows = [
        {
            "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
            "acquisitionDate": "2024-01-15",
            "actualCost": 500000,          # purchase cost only
            "saleValue": None,              # no sale
            "transferDate": None,           # no transfer
            "recordKind": "TRANSACTION",     # manually entered, not imported evidence
        }
    ]
    portfolio = compute_restricted_112a(rows)
    # No sale means no gain — must not report 499975 or 500000 as LTCG.
    assert portfolio.gross_gain == Decimal("0"), (
        f"Purchase-only row produced a gain of {portfolio.gross_gain} — "
        f"this is the bug where cost is treated as sale value."
    )
    # A purchase-only row is evidence of a holding, not a disposal.  It must
    # not block ITR-1/ITR-4 filing (the user simply hasn't sold anything yet).
    assert portfolio.status in {"EVIDENCE_ONLY", "EMPTY", "VALID"}, (
        f"Unexpected status {portfolio.status}"
    )
    assert portfolio.evidence_count == 1, (
        f"Expected 1 evidence row, got {portfolio.evidence_count}"
    )


def test_purchase_only_row_with_empty_sale_value_produces_no_gain():
    """A row with saleValue=0 (not None) must also not produce a gain."""
    rows = [
        {
            "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
            "acquisitionDate": "2024-01-15",
            "actualCost": 500000,
            "saleValue": 0,
            "transferDate": None,
            "recordKind": "TRANSACTION",
        }
    ]
    portfolio = compute_restricted_112a(rows)
    assert portfolio.gross_gain == Decimal("0"), (
        f"Row with saleValue=0 produced gain {portfolio.gross_gain}"
    )


def test_completed_sale_with_loss_is_detected():
    """A real sale below cost must report SECTION_112A_LOSS (not be hidden)."""
    rows = [
        {
            "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
            "acquisitionDate": "2024-01-15",
            "transferDate": "2025-06-15",   # > 12 months → long-term
            "actualCost": 16044,
            "saleValue": 15000,
            "recordKind": "TRANSACTION",
        }
    ]
    portfolio = compute_restricted_112a(rows)
    # A completed sale with loss must report SECTION_112A_LOSS issue.
    issue_codes = [issue.code.value for issue in portfolio.issues]
    assert "SECTION_112A_LOSS" in issue_codes, (
        f"Expected SECTION_112A_LOSS issue for sale-below-cost, got {issue_codes}"
    )


def test_purchase_only_row_without_record_kind_produces_no_gain():
    """Manually entered purchase (no recordKind, no sale) must not produce a gain.

    This reproduces the reported bug where a client with only a ~Rs 5,00,000
    purchase and NO sale was reported as having Rs 4,99,975 LTCG 112A.
    """
    rows = [
        {
            "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
            "acquisitionDate": "2024-01-15",
            "actualCost": 500000,
            # No saleValue, no transferDate, no recordKind — pure purchase.
        }
    ]
    portfolio = compute_restricted_112a(rows)
    assert portfolio.gross_gain == Decimal("0"), (
        f"Purchase-only row without recordKind produced gain {portfolio.gross_gain}"
    )
    # A purchase-only row is evidence, not a gain.  It must not block ITR-1.
    assert portfolio.evidence_count == 1, (
        f"Expected 1 evidence row, got {portfolio.evidence_count}"
    )


def test_purchase_only_row_with_zero_sale_produces_no_gain():
    """A row with saleValue=0 and actualCost=500000 must not produce a gain."""
    rows = [
        {
            "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
            "acquisitionDate": "2024-01-15",
            "transferDate": "2025-06-15",
            "actualCost": 500000,
            "saleValue": 0,
            "recordKind": "TRANSACTION",
        }
    ]
    portfolio = compute_restricted_112a(rows)
    assert portfolio.gross_gain == Decimal("0"), (
        f"Row with saleValue=0 produced gain {portfolio.gross_gain}"
    )


def test_single_unified_112a_calculation_entrypoint():
    """There must be ONE canonical 112A computation entrypoint for ITR-1/4.

    The restricted portfolio path (compute_112a / compute_restricted_112a in
    restricted_112a.py) is the single source of truth for ITR-1/ITR-4 112A
    eligibility and gain.  The capital_gains.py compute_112a is the ITR-2/3
    per-scrip path and is a different responsibility (full Schedule CG with
    grandfathering, indexation, per-scrip detail) — it must not be invoked
    from the ITR-1/4 filing pipeline.
    """
    from app.engine.schedules import restricted_112a, capital_gains, special_rates
    # Restricted path is the ITR-1/4 entrypoint — now has a canonical alias.
    assert hasattr(restricted_112a, "compute_112a")
    assert hasattr(restricted_112a, "compute_restricted_112a")
    # The canonical alias must be the same function as the explicit name.
    assert restricted_112a.compute_112a is restricted_112a.compute_restricted_112a

    # The other two modules exist but serve different responsibilities:
    # - capital_gains.compute_112a: ITR-2/3 per-scrip gain aggregation
    # - special_rates.compute_112a: Schedule-SI tax entry (exemption + tax)
    assert hasattr(capital_gains, "compute_112a")
    assert hasattr(special_rates, "compute_112a")
    # They must NOT be the same function as the ITR-1/4 entrypoint.
    assert capital_gains.compute_112a is not restricted_112a.compute_112a
    assert special_rates.compute_112a is not restricted_112a.compute_112a


def test_filing_gateway_uses_canonical_112a_entrypoint():
    """The filing gateway must use the canonical restricted-112a entrypoint."""
    import inspect
    from app.engine import filing_gateway
    source = inspect.getsource(filing_gateway)
    # The gateway imports the canonical entry point, not a duplicate.
    assert "compute_112a as compute_restricted_112a" in source or (
        "from app.engine.schedules.restricted_112a import compute_112a" in source
    ), "Filing gateway must import the canonical 112a entrypoint"
    # It must NOT import the ITR-2/3 per-scrip path.
    assert "from app.engine.schedules.capital_gains import compute_112a" not in source, (
        "Filing gateway must not use the ITR-2/3 per-scrip 112a path"
    )
