"""Tests for canonical reconciliation evidence on the backend ReturnDraft."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.return_draft import (
    ReconciliationDiscrepancy,
    ReconciliationEvidence,
    ReconciliationState,
    ReturnDraft,
    create_empty_draft,
)


def test_empty_draft_has_empty_reconciliation_state() -> None:
    """A fresh draft exposes an empty reconciliation state."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    assert isinstance(draft.reconciliation, ReconciliationState)
    assert draft.reconciliation.evidence == []
    assert draft.reconciliation.discrepancies == []


def test_strict_model_accepts_reconciliation_evidence() -> None:
    """The strict backend schema round-trips an evidence row including raw."""
    raw = {"information_code": "TDS-192", "custom": "kept", "amount": "1,234"}
    evidence = ReconciliationEvidence(
        id="evidence-ais-1",
        source="AIS",
        sourceCode="TDS-192",
        sourceSection="B1",
        incomeHead="Salary",
        category="salary",
        description="Salary TDS",
        sourceName="ACME",
        sourceIdentifier="ABCD12345E",
        role="TAX_CREDIT",
        relatedTab="TAXES",
        reportedAmount=Decimal("1234"),
        processedAmount=Decimal("1234"),
        acceptedAmount=Decimal("0"),
        taxAmount=Decimal("123.4"),
        status="ACTIVE",
        requiresReview=False,
        raw=raw,
    )
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.reconciliation.evidence.append(evidence)
    payload = draft.model_dump()
    revived = ReturnDraft.model_validate(payload)
    assert revived.reconciliation.evidence[0].raw == raw
    assert revived.reconciliation.evidence[0].role == "TAX_CREDIT"
    assert revived.reconciliation.evidence[0].taxAmount == Decimal("123.4")


def test_strict_model_rejects_unknown_reconciliation_role() -> None:
    """The strict backend rejects unknown role values."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReconciliationEvidence(
            id="x",
            source="AIS",
            sourceCode="TDS-192",
            sourceSection="B1",
            incomeHead="Salary",
            category="salary",
            description="",
            sourceName="",
            sourceIdentifier="",
            role="UNKNOWN_ROLE",  # type: ignore[arg-type]
            relatedTab="TAXES",
            raw={},
        )


def test_discrepancy_status_defaults_to_pending() -> None:
    """A fresh discrepancy defaults to PENDING until confirmed."""
    discrepancy = ReconciliationDiscrepancy(
        id="reconciliation-1",
        category="interest from savings bank",
        description="AIS/TIS mismatch.",
        aisAmount=Decimal("157"),
        tisAcceptedAmount=Decimal("90"),
        as26Amount=Decimal("0"),
        difference=Decimal("67"),
    )
    assert discrepancy.status == "PENDING"
