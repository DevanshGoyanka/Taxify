"""
/v2 client ITR router — canonical typed draft endpoints (Phase 1).

These endpoints accept and return the canonical ``ReturnDraft`` JSON
(``app/schemas/return_draft.py``) — no flat-blob aliases, no legacy
scalar duplicates. The draft is validated by Pydantic on write
(``extra="forbid"``), so unknown keys are rejected at the boundary.

The legacy ``GET/PUT /clients/{id}/itr/{year}`` endpoints remain
unchanged for the existing frontend flow. The /v2 endpoints are
opt-in and will be wired to the frontend in Phase 3 via a
``VITE_USE_V2`` feature flag.

Phase 1 scope: load + save only. Compute and CBDT-generation move to
/v2 in Phase 2.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Client, ClientITR, User
from app.routers.clients import ensure_client_active, resolve_owned_client
from app.schemas.return_draft import ReturnDraft, create_empty_draft, draft_from_client_seed


router = APIRouter(prefix="/v2/clients/{client_id}/itr", tags=["client_itr_v2"])


def _normalize_itr_type(form: str) -> str:
    """Map the canonical ``ITR-1`` form string to the legacy ``ClientITR.itr_type`` column.

    The DB column historically stores ``ITR1`` (no hyphen). The canonical
    draft stores ``ITR-1``. We persist the hyphen-bearing form in
    ``form_data`` (the canonical JSON) but mirror the legacy column for
    list/filter queries that read ``itr_type``.
    """
    return form.replace("-", "")


@router.get("/{year}")
def get_client_itr_v2(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Load a client's ITR draft for the given assessment year.

    Returns the canonical ``ReturnDraft`` JSON. When no draft exists yet,
    seeds an empty draft from the ``Client`` master (personal info only)
    — mirroring the legacy ``GET /clients/{id}/itr/{year}`` fallback.

    Raises 404 if the client does not exist or belongs to another user.
    """
    client = resolve_owned_client(client_id, current_user.id, db)
    itr = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client.id, ClientITR.year == year)
        .first()
    )
    if itr is None or not itr.form_data or itr.form_data == "{}":
        draft = draft_from_client_seed(client, year)
        return json.loads(draft.model_dump_json())

    try:
        payload = json.loads(itr.form_data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stored ITR data is not valid JSON: {exc}",
        )

    # If the stored blob is the legacy flat shape (no ``schemaVersion``
    # key), return an empty seed rather than a half-typed draft. Phase 7
    # adds a one-time flat→draft migrator; until then, /v2 only serves
    # drafts that were saved via /v2.
    if not isinstance(payload, dict) or "schemaVersion" not in payload:
        draft = draft_from_client_seed(client, year)
        return json.loads(draft.model_dump_json())

    try:
        draft = ReturnDraft.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Stored ITR draft failed canonical validation.",
                "errors": exc.errors(),
            },
        )
    # Always pin the assessment year to the URL (the draft is per-AY).
    if not draft.assessmentYear:
        draft.assessmentYear = year
    return json.loads(draft.model_dump_json())


@router.put("/{year}")
def save_client_itr_v2(
    client_id: str,
    year: str,
    draft: ReturnDraft,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist a canonical ``ReturnDraft`` for the given client + AY.

    The draft is validated by Pydantic (``extra="forbid"``) before it
    reaches this handler, so unknown keys are rejected with 422 at the
    framework boundary. On success, the typed JSON is stored in
    ``ClientITR.form_data`` and the ``itr_type`` column mirrors the
    draft's ``form`` field for legacy list queries.

    Raises 404 if the client does not exist; 409 if the client is archived.
    """
    client = resolve_owned_client(client_id, current_user.id, db)
    ensure_client_active(client)

    if draft.assessmentYear and draft.assessmentYear != year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Draft assessmentYear ({draft.assessmentYear}) does not match "
                f"the URL year ({year})."
            ),
        )
    draft.assessmentYear = year

    payload_json = draft.model_dump_json()

    itr = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client.id, ClientITR.year == year)
        .first()
    )
    if itr is None:
        itr = ClientITR(
            client_id=client.id,
            year=year,
            itr_type=_normalize_itr_type(draft.form),
            status="In Progress",
            form_data=payload_json,
            computed_result="{}",
        )
        db.add(itr)
    else:
        itr.form_data = payload_json
        itr.itr_type = _normalize_itr_type(draft.form)
        itr.status = "In Progress"

    db.commit()
    db.refresh(itr)

    # Return the exact typed JSON we persisted — round-trip fidelity.
    return json.loads(payload_json)


@router.post("/{year}/generate-cbdt-json")
def generate_client_cbdt_json_v2(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Generate schema-valid CBDT JSON from the saved canonical draft only.

    Unlike the legacy endpoint, this route does not accept a live flat body.
    It loads ``ClientITR.form_data``, requires a ``schemaVersion`` marker,
    validates the complete ``ReturnDraft``, then runs the Phase 2 single-
    compute filing gateway.

    Args:
        client_id: Public UUID or legacy numeric client identifier.
        year: Assessment year of the saved draft.
        current_user: Authenticated owner injected by FastAPI.
        db: Request database session.

    Returns:
        Download response containing validated official CBDT JSON.

    Raises:
        HTTPException: For missing drafts, legacy blobs, canonical validation,
            mapping/computation errors, or official schema failures.
    """
    client = resolve_owned_client(client_id, current_user.id, db)
    itr = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client.id, ClientITR.year == year)
        .first()
    )
    if itr is None or not itr.form_data or itr.form_data == "{}":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved canonical ITR draft exists for this assessment year.",
        )
    try:
        payload = json.loads(itr.form_data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Saved ITR data is not valid JSON.", "errors": [str(exc)]},
        ) from exc
    if not isinstance(payload, dict) or "schemaVersion" not in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Saved ITR data is a legacy flat blob.",
                "errors": [
                    "Migrate or save this return through the canonical /v2 endpoint before CBDT generation."
                ],
            },
        )
    try:
        draft = ReturnDraft.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Saved ITR draft failed canonical validation.",
                "errors": [str(error) for error in exc.errors()],
            },
        ) from exc
    if draft.assessmentYear and draft.assessmentYear != year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Saved draft assessment year does not match the requested year.",
                "errors": [f"Draft has {draft.assessmentYear}; URL requests {year}."],
            },
        )
    from app.engine.filing_gateway_v2 import FilingGatewayV2Error, generate_cbdt_json

    try:
        official_json, _summary = generate_cbdt_json(draft)
    except FilingGatewayV2Error as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "errors": exc.errors},
        ) from exc
    content = json.dumps(official_json, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=CBDT-ITR1_{client.pan}_{year}.json",
            "X-CBDT-Computation-Status": "FORM_COMPUTATION",
            "X-CBDT-Schema-Valid": "true",
        },
    )
