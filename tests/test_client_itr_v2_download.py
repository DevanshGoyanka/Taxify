"""Phase 5 tests — v2 download endpoints (download + download-pdf).

Verifies the two new /v2 download routes are registered and that the
shared ``_load_saved_draft`` helper enforces the same canonical-validation
gate as the generate-cbdt-json endpoint (legacy blobs rejected, year
mismatch rejected, seed returned when no row).

Run: pytest tests/test_client_itr_v2_download.py -v
"""

from __future__ import annotations

import json

import pytest

from app.routers.client_itr_v2 import (
    generate_client_cbdt_json_v2,
    get_client_itr_v2,
    _load_saved_draft,
    router as v2_router,
)
from app.routers.client_itr import router as legacy_router
from app.schemas.return_draft import ReturnDraft, migrate_stored_draft_payload


def _router_paths(router) -> set[str]:
    """Return the set of paths a router's leaf routes expose."""
    return {route.path for route in router.routes if hasattr(route, "path")}


# ── Route registration ──────────────────────────────────────────────────────

def test_v2_download_routes_registered() -> None:
    """The /v2 download + download-pdf routes are registered on the v2 router."""
    paths = _router_paths(v2_router)
    assert "/v2/clients/{client_id}/itr/{year}/download" in paths
    assert "/v2/clients/{client_id}/itr/{year}/download-pdf" in paths


def test_v2_download_routes_use_get() -> None:
    """Both download routes respond to GET (not POST)."""
    by_path = {r.path: r for r in v2_router.routes if hasattr(r, "path")}
    v2_download = by_path["/v2/clients/{client_id}/itr/{year}/download"]
    v2_pdf = by_path["/v2/clients/{client_id}/itr/{year}/download-pdf"]
    assert "GET" in v2_download.methods
    assert "GET" in v2_pdf.methods


def test_legacy_download_routes_still_registered() -> None:
    """Regression: the legacy download-pdf route stays until Phase 7."""
    paths = _router_paths(legacy_router)
    assert "/clients/{client_id}/itr/{year}/download-pdf" in paths


# ── _load_saved_draft helper ────────────────────────────────────────────────


class _FakeUser:
    id = 1


class _FakeClient:
    def __init__(self, name: str = "Rahul", pan: str = "ABCDE1234F") -> None:
        self.id = 1
        self.name = name
        self.pan = pan
        self.email = "r@example.com"
        self.mobile = "9876543210"
        self.dob = "1990-01-15"


class _FakeQuery:
    def __init__(self, itr_row) -> None:
        self._itr_row = itr_row

    def filter(self, *_) -> "_FakeQuery":
        return self

    def first(self):
        return self._itr_row


class _FakeDb:
    def __init__(self, itr_row) -> None:
        self._query = _FakeQuery(itr_row)

    def query(self, *_):
        return self._query


class _FakeITR:
    def __init__(self, form_data: str, itr_type: str = "ITR1") -> None:
        self.form_data = form_data
        self.itr_type = itr_type


def _canonical_draft_json(form: str = "ITR-1", year: str = "2026-27") -> str:
    """Build a minimal valid canonical draft JSON string."""
    from app.schemas.return_draft import create_empty_draft

    draft = create_empty_draft(year, form, "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.name = "Rahul"
    return draft.model_dump_json()


def test_load_saved_draft_returns_seed_when_no_row(monkeypatch) -> None:
    """No saved row → seed an empty draft from the client master."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    client, itr, draft = _load_saved_draft("c1", "2026-27", _FakeUser(), _FakeDb(None))
    assert itr is None
    assert draft.form == "ITR-1"
    assert draft.assessmentYear == "2026-27"
    assert draft.personal.pan == "ABCDE1234F"


def test_load_saved_draft_loads_canonical_row(monkeypatch) -> None:
    """A saved canonical draft row is loaded + validated."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    payload = _canonical_draft_json()
    itr_row = _FakeITR(payload, "ITR1")
    client, itr, draft = _load_saved_draft("c1", "2026-27", _FakeUser(), _FakeDb(itr_row))
    assert itr is itr_row
    assert draft.form == "ITR-1"
    assert draft.personal.pan == "ABCDE1234F"


def test_load_saved_draft_accepts_empty_legacy_clause_iv_placeholder(monkeypatch) -> None:
    """Old v2 drafts with an empty scalar placeholder remain loadable."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    payload = json.loads(_canonical_draft_json())
    payload["filing"]["seventhProviso"]["otherClauseIVDetail"] = ""
    itr_row = _FakeITR(json.dumps(payload), "ITR1")

    _, _, draft = _load_saved_draft(
        "c1", "2026-27", _FakeUser(), _FakeDb(itr_row)
    )

    assert draft.filing.seventhProviso.clauseIVDetails == []


def test_get_client_itr_v2_migrates_empty_legacy_clause_iv_placeholder(
    monkeypatch,
) -> None:
    """The canonical GET must not return 500 for the historical empty field."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    payload = json.loads(_canonical_draft_json())
    payload["filing"]["seventhProviso"]["otherClauseIVDetail"] = ""
    itr_row = _FakeITR(json.dumps(payload), "ITR1")

    result = get_client_itr_v2(
        "c1", "2026-27", _FakeUser(), _FakeDb(itr_row)
    )

    seventh = result["filing"]["seventhProviso"]
    assert "otherClauseIVDetail" not in seventh
    assert seventh["clauseIVDetails"] == []


def test_stored_draft_migration_preserves_nonempty_legacy_clause_iv_detail() -> None:
    """Ambiguous historical disclosure text must never be silently discarded."""
    payload = json.loads(_canonical_draft_json())
    seventh = payload["filing"]["seventhProviso"]
    seventh["otherClauseIVDetail"] = "Historical taxpayer disclosure"

    migrated = migrate_stored_draft_payload(payload)

    assert (
        migrated["filing"]["seventhProviso"]["otherClauseIVDetail"]
        == "Historical taxpayer disclosure"
    )


def test_stored_draft_migration_strips_vestigial_employer_salary_fields() -> None:
    """ltaExempt/otherExempt/salaryNatureRows/perquisiteNatureRows were removed
    from the Employer schema (Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md
    §11.9) -- a stored draft carrying an employer row with any of them must
    still validate after migration, with the obsolete keys stripped and every
    other field on the row preserved untouched."""
    payload = json.loads(_canonical_draft_json())
    payload["employers"] = [{
        "id": "e1", "employerName": "Acme", "basic": "500000",
        "ltaExempt": "1000", "otherExempt": "2000",
        "salaryNatureRows": [{"id": "r1", "natureCode": "10(6)", "otherDescription": "", "amount": "0"}],
        "perquisiteNatureRows": [],
    }]

    migrated = migrate_stored_draft_payload(payload)

    row = migrated["employers"][0]
    assert "ltaExempt" not in row
    assert "otherExempt" not in row
    assert "salaryNatureRows" not in row
    assert "perquisiteNatureRows" not in row
    assert row["employerName"] == "Acme"
    assert row["basic"] == "500000"
    # And the migrated payload must actually validate end-to-end.
    ReturnDraft.model_validate(migrated)


def test_load_saved_draft_rejects_legacy_blob(monkeypatch) -> None:
    """A legacy flat blob (no schemaVersion) is rejected with 422."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    legacy_payload = json.dumps({"name": "Rahul", "hraReceived": 5000})  # no schemaVersion
    itr_row = _FakeITR(legacy_payload, "ITR1")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        _load_saved_draft("c1", "2026-27", _FakeUser(), _FakeDb(itr_row))
    assert caught.value.status_code == 422
    assert "legacy flat blob" in caught.value.detail["message"].lower()


def test_load_saved_draft_rejects_year_mismatch(monkeypatch) -> None:
    """A draft whose assessmentYear ≠ URL year is rejected with 422."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    payload = _canonical_draft_json(year="2025-26")  # mismatch with URL 2026-27
    itr_row = _FakeITR(payload, "ITR1")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        _load_saved_draft("c1", "2026-27", _FakeUser(), _FakeDb(itr_row))
    assert caught.value.status_code == 422
    assert "assessment year does not match" in caught.value.detail["message"].lower()


def test_load_saved_draft_rejects_invalid_json(monkeypatch) -> None:
    """Invalid stored JSON raises 500."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    itr_row = _FakeITR("{not valid json", "ITR1")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        _load_saved_draft("c1", "2026-27", _FakeUser(), _FakeDb(itr_row))
    assert caught.value.status_code == 500


# ── generate-cbdt-json filename ─────────────────────────────────────────────


def test_generate_cbdt_json_v2_filename_matches_actual_form(monkeypatch) -> None:
    """The downloaded filename must reflect the draft's own form, not a
    hardcoded ITR-1 — regression for a bug where every downloaded CBDT JSON
    (ITR-2 included) was named CBDT-ITR1_... regardless of the real form."""
    monkeypatch.setattr(
        "app.routers.client_itr_v2.resolve_owned_client",
        lambda client_id, user_id, db: _FakeClient(),
    )
    monkeypatch.setattr(
        "app.engine.filing_gateway_v2.generate_cbdt_json",
        lambda draft: ({"ITR": {"ITR2": {}}}, {}),
    )
    payload = _canonical_draft_json(form="ITR-2")
    itr_row = _FakeITR(payload, "ITR2")

    response = generate_client_cbdt_json_v2(
        "c1", "2026-27", _FakeUser(), _FakeDb(itr_row)
    )

    assert "CBDT-ITR2_" in response.headers["content-disposition"]
    assert "CBDT-ITR1_" not in response.headers["content-disposition"]
