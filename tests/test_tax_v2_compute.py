"""Tests for the canonical /v2/tax-summary/compute pipeline."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.routers.tax_v2 import compute_tax_summary_v2
from app.schemas.return_draft import (
    Employer,
    ReconciliationDiscrepancy,
    ReturnDraft,
    WinningIncome,
    create_empty_draft,
)


def test_compute_v2_returns_compatible_headline_keys() -> None:
    """Canonical compute exposes both new and legacy headline aliases."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    summary = compute_tax_summary_v2(draft)
    assert summary["grossTotalIncome"] == summary["gti"]
    assert summary["netTaxLiability"] == summary["totalTaxLiability"]
    assert summary["totalTaxPaid"] == summary["totalTaxesPaid"]
    assert "totalTaxPayable" in summary
    assert "totalTDS" in summary
    assert "balancePayable" in summary
    assert "refund" in summary
    assert "breakdown" in summary
    assert "issues" in summary


def test_compute_v2_rejects_non_itr1_form_with_422() -> None:
    """Unsupported canonical forms fail at the v2 boundary with 422."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-2")
    with pytest.raises(HTTPException) as caught:
        compute_tax_summary_v2(draft)
    assert caught.value.status_code == 422
    assert "ITR-1 only" in caught.value.detail["errors"][0]


def test_compute_v2_surfaces_engine_eligibility_errors() -> None:
    """Out-of-scope winnings produce a clear mapping/computation 422."""
    draft = create_empty_draft("2026-27")
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="LOTTERY", grossAmount=Decimal("1000"),
    )]
    with pytest.raises(HTTPException) as caught:
        compute_tax_summary_v2(draft)
    assert caught.value.status_code == 422
    assert "Lottery" in " ".join(caught.value.detail["errors"])


def test_compute_v2_rejects_pending_reconciliation_discrepancies() -> None:
    """A pending reconciliation discrepancy blocks compute with 422."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    draft.reconciliation.discrepancies.append(
        ReconciliationDiscrepancy(
            id="reconciliation-test",
            category="interest from savings bank",
            description="AIS/TIS mismatch.",
            aisAmount=Decimal("157"),
            tisAcceptedAmount=Decimal("90"),
            as26Amount=Decimal("0"),
            difference=Decimal("67"),
            status="PENDING",
        )
    )
    with pytest.raises(HTTPException) as caught:
        compute_tax_summary_v2(draft)
    assert caught.value.status_code == 422
    assert "reconciliation" in " ".join(caught.value.detail["errors"]).lower()


def test_compute_v2_allows_confirmed_reconciliation_discrepancies() -> None:
    """A confirmed (non-pending) discrepancy no longer blocks compute."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    draft.reconciliation.discrepancies.append(
        ReconciliationDiscrepancy(
            id="reconciliation-test",
            category="interest from savings bank",
            description="AIS/TIS mismatch.",
            aisAmount=Decimal("157"),
            tisAcceptedAmount=Decimal("90"),
            as26Amount=Decimal("0"),
            difference=Decimal("67"),
            status="CONFIRMED_TIS",
        )
    )
    summary = compute_tax_summary_v2(draft)
    assert summary["calculationStatus"].startswith("CALCULATED")
