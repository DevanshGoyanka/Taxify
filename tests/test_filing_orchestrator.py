"""Boundary tests for the shared filing orchestrator."""

from __future__ import annotations

import pytest

from app.engine import filing_orchestrator
from app.schemas.return_draft import create_empty_draft


def test_itr1_requires_canonical_v2_draft() -> None:
    with pytest.raises(filing_orchestrator.FilingOrchestratorError) as caught:
        filing_orchestrator.produce_itd_json(
            client_id=1,
            ay="2026-27",
            itr_type="ITR-1",
            flat_draft={"form": "ITR-1"},
            user=object(),
            db=object(),
        )

    assert "canonical /v2 ReturnDraft" in str(caught.value)


def test_itr2_requires_canonical_v2_draft() -> None:
    with pytest.raises(filing_orchestrator.FilingOrchestratorError) as caught:
        filing_orchestrator.produce_itd_json(
            client_id=1,
            ay="2026-27",
            itr_type="ITR-2",
            flat_draft={"form": "ITR-2"},
            user=object(),
            db=object(),
        )

    assert "canonical /v2 ReturnDraft" in str(caught.value)


def test_itr3_is_explicitly_rejected() -> None:
    with pytest.raises(filing_orchestrator.FilingOrchestratorError) as caught:
        filing_orchestrator.produce_itd_json(
            client_id=1,
            ay="2026-27",
            itr_type="ITR-3",
            flat_draft={"form": "ITR-3", "schemaVersion": 1},
            user=object(),
            db=object(),
        )

    assert "ITR-3" in str(caught.value)
    assert "not supported" in str(caught.value)


def test_itr2_passes_saved_canonical_draft_to_v2_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = create_empty_draft("2026-27", "ITR-2", "new")
    captured: dict[str, object] = {}
    official = {"ITR": {"ITR2": {"CreationInfo": {"Digest": "x" * 44}}}}

    def generate(saved_draft: object) -> tuple[dict, dict]:
        captured["draft"] = saved_draft
        return official, {}

    monkeypatch.setattr("app.engine.filing_gateway_v2.generate_cbdt_json", generate)
    monkeypatch.setattr(filing_orchestrator, "_persist_generated_json", lambda **_: None)

    result = filing_orchestrator.produce_itd_json(
        client_id=1,
        ay="2026-27",
        itr_type="ITR-2",
        flat_draft=draft.model_dump(mode="json"),
        user=type("User", (), {"id": 1})(),
        db=object(),
    )

    assert result == official
    assert captured["draft"].form == "ITR-2"


def test_itr1_passes_saved_canonical_draft_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    captured: dict[str, object] = {}
    official = {"ITR": {"ITR1": {"CreationInfo": {"Digest": "x" * 44}}}}

    def generate(saved_draft: object) -> tuple[dict, dict]:
        captured["draft"] = saved_draft
        return official, {}

    monkeypatch.setattr(
        "app.engine.filing_gateway_v2.generate_cbdt_json",
        generate,
    )
    monkeypatch.setattr(filing_orchestrator, "_persist_generated_json", lambda **_: None)

    result = filing_orchestrator.produce_itd_json(
        client_id=1,
        ay="2026-27",
        itr_type="ITR-1",
        flat_draft=draft.model_dump(mode="json"),
        user=type("User", (), {"id": 1})(),
        db=object(),
    )

    assert result == official
    assert captured["draft"].schemaVersion == draft.schemaVersion
    assert captured["draft"].assessmentYear == "2026-27"


def test_itr1_preserves_gateway_validation_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.engine.filing_gateway_v2 import FilingGatewayV2Error

    draft = create_empty_draft("2026-27", "ITR-1", "new")

    def reject(_: object) -> tuple[dict, dict]:
        raise FilingGatewayV2Error(
            "Category A validation failed.",
            ["Dividend quarterly breakup is mandatory."],
        )

    monkeypatch.setattr("app.engine.filing_gateway_v2.generate_cbdt_json", reject)

    with pytest.raises(filing_orchestrator.FilingOrchestratorError) as caught:
        filing_orchestrator.produce_itd_json(
            client_id=1,
            ay="2026-27",
            itr_type="ITR-1",
            flat_draft=draft.model_dump(mode="json"),
            user=object(),
            db=object(),
        )

    assert caught.value.errors == ["Dividend quarterly breakup is mandatory."]
