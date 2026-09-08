"""Regression tests for AIS SFT-18(Pur) purchase-evidence handling.

The AIS reconciliation emits SFT-18(Pur) purchase aggregates with a quarter
string (e.g. "Q2(Jul-Sep)") in place of a real transaction date, because the
AIS itself reports only the quarter and total purchase amount — no per-day
transaction date.  These rows must not:

1.  crash the ITR-2 capital-gains builder's strict ISO date parser, nor
2.  be reported as disposal transactions in Schedule CG (they are reference
    data only; the reconciled purchase totals feed the restricted-112A
    cost-of-acquisition aggregates).

These tests lock in both behaviours so a future refactor cannot silently
reintroduce the 422 "dateOfAcquisition must be an ISO date" failure that
blocked ITR preparation for clients with mutual-fund purchases.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.routers import tax
from app.routers.tax import _date


def test_date_parses_iso_yyyy_mm_dd() -> None:
    """ISO dates round-trip through ``_date``."""
    assert _date("2026-03-31", "dateOfAcquisition").isoformat() == "2026-03-31"


def test_date_parses_dd_slash_mm_slash_yyyy() -> None:
    """The AIS/frontend DD/MM/YYYY form is accepted and normalised."""
    parsed = _date("31/03/2026", "dateOfTransfer")
    assert parsed is not None
    assert parsed.isoformat() == "2026-03-31"


def test_date_returns_none_for_quarter_placeholder() -> None:
    """A quarter string must degrade to ``None`` instead of raising 422."""
    assert _date("Q2(Jul-Sep)", "dateOfAcquisition") is None


def test_date_returns_none_for_empty_and_garbage() -> None:
    """Empty / non-date values resolve to ``None`` without aborting."""
    assert _date(None, "x") is None
    assert _date("", "x") is None
    assert _date("   ", "x") is None
    assert _date("not-a-date", "x") is None


def _purchase_only_payload(requested_form: str) -> dict:
    """A minimal payload containing a purchase-only evidence row.

    The row mirrors what the AIS reconciliation produces for an SFT-18(Pur)
    mutual-fund purchase aggregate: ``evidenceSide=PURCHASE``, a quarter
    string in ``acquisitionDate``/``purchaseDate``, zero sale value.
    """
    return {
        "assessmentYear": "2026-27",
        "financialYear": "2025-26",
        "age": 45,
        "regime": "OLD",
        "residentialStatus": "ROR",
        "pan": "ABCDE1234F",
        "name": "Test Assessee",
        "requestedForm": requested_form,
        "employerEntries": [],
        "capitalGainTransactions": [
            {
                "assetType": "EQUITY_ORIENTED_MUTUAL_FUND",
                "evidenceSide": "PURCHASE",
                "quarter": "Q2(Jul-Sep)",
                "acquisitionDate": "Q2(Jul-Sep)",
                "purchaseDate": "Q2(Jul-Sep)",
                "actualCost": 499975,
                "purchaseCost": 499975,
                "saleValue": 0,
                "saleCost": 0,
                "description": "ICICI Prudential Mutual Fund",
            },
        ],
        "tdsEntries": [],
        "tcsEntries": [],
    }


def _run_compute(payload: dict) -> object:
    """Invoke the public compute endpoint with a stubbed user."""
    stub_user = SimpleNamespace(id=1, email="t@t.com", full_name="Test")
    return tax.compute_tax_summary(payload, regime="OLD", current_user=stub_user)


def test_itr2_compute_does_not_raise_on_purchase_quarter_date() -> None:
    """ITR-2 preparation must not 422 on a purchase-only quarter date.

    Before the fix, the ITR-2 CG builder iterated every capital-gain row
    including SFT-18(Pur) purchase evidence, whose ``acquisitionDate`` was
    the quarter string "Q2(Jul-Sep)".  The strict ``date.fromisoformat``
    call raised HTTPException 422, blocking return preparation.
    """
    payload = _purchase_only_payload("ITR-2")
    result = _run_compute(payload)
    # The response is a dict-like object; presence of grossIncome confirms
    # the computation completed instead of raising.
    assert isinstance(result, dict)
    # capitalGainsSummary should be present and the purchase-only row must
    # not have been reported as a disposal transaction.
    summary = result.get("capitalGainsSummary")
    assert summary is not None
    assert summary.get("transactionCount", 0) == 0


def test_itr1_compute_does_not_raise_on_purchase_quarter_date() -> None:
    """ITR-1 preparation must not 422 on a purchase-only quarter date."""
    payload = _purchase_only_payload("ITR-1")
    result = _run_compute(payload)
    assert isinstance(result, dict)
    assert result.get("grossIncome", 0) == 0
