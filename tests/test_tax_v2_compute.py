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


def test_compute_v2_surfaces_per_row_capital_gains_for_simplified_112a() -> None:
    """Simplified-112A compute carries per-row transactions + bottom totals.

    Regression for the real-client capital-gains display bug: the v2
    summary must surface a non-zero per-row ``transactions`` entry (with
    ``gain``/``actual_cost``/``transfer_expenses``) and the bottom
    ``totalLTCG``/``totalCapitalGains`` keys so the frontend
    CapitalGainsEntryManager readouts do not show ₹0 even though the
    engine's capitalGains112A is correct.
    """
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    draft.capitalGainsSchedule = {  # type: ignore[assignment]
        "simplified112A": {
            "totalSaleConsideration": Decimal("41871"),
            "totalCostAcquisition": Decimal("20586"),
        }
    }
    summary = compute_tax_summary_v2(draft)
    cg = summary["capitalGainsSummary"]
    assert cg["status"] == "VALID"
    assert cg["transactionCount"] == 1
    tx = cg["transactions"][0]
    assert tx["sale_value"] == 41871.0
    assert tx["actual_cost"] == 20586.0
    assert tx["gain"] == 21285.0  # 41871 - 20586
    # The engine's authoritative aggregate must match the per-row gain.
    assert summary["breakdown"]["income"]["capitalGains112A"] == 21285.0
    # Bottom-of-schedule totals the frontend reads directly.
    assert summary["totalLTCG"] == 21285.0
    assert summary["totalCapitalGains"] == 21285.0
    assert summary["totalSTCG"] == 0.0  # STCG equity is not reportable on ITR-4


def test_compute_v2_rejects_non_itr1_form_with_422() -> None:
    """Unsupported canonical forms fail at the v2 boundary with 422."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-2")
    with pytest.raises(HTTPException) as caught:
        compute_tax_summary_v2(draft)
    assert caught.value.status_code == 422
    assert "not supported by the v2 pipeline" in caught.value.detail["errors"][0]


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
