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
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Client, ClientITR, User
from app.routers.clients import ensure_client_active, resolve_owned_client
from app.schemas.return_draft import ReturnDraft, create_empty_draft, draft_from_client_seed

logger = logging.getLogger("taxify.routers.client_itr_v2")

router = APIRouter(prefix="/v2/clients/{client_id}/itr", tags=["client_itr_v2"])


def _normalize_itr_type(form: str) -> str:
    """Map the canonical ``ITR-1`` form string to the legacy ``ClientITR.itr_type`` column.

    The DB column historically stores ``ITR1`` (no hyphen). The canonical
    draft stores ``ITR-1``. We persist the hyphen-bearing form in
    ``form_data`` (the canonical JSON) but mirror the legacy column for
    list/filter queries that read ``itr_type``.
    """
    return form.replace("-", "")


def _migrate_stored_canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove obsolete empty placeholders from previously valid v2 drafts.

    ``otherClauseIVDetail`` was an optional free-text placeholder before the
    official clause-(iv) row structure was introduced as ``clauseIVDetails``.
    An empty legacy value carries no taxpayer data, so it can be removed
    losslessly. A non-empty value is deliberately retained and will fail the
    strict canonical validation rather than being silently discarded.
    """
    filing = payload.get("filing")
    if not isinstance(filing, dict):
        return payload
    seventh_proviso = filing.get("seventhProviso")
    if not isinstance(seventh_proviso, dict):
        return payload
    legacy_detail = seventh_proviso.get("otherClauseIVDetail")
    if not isinstance(legacy_detail, str) or legacy_detail.strip():
        return payload

    migrated = dict(payload)
    migrated_filing = dict(filing)
    migrated_seventh_proviso = dict(seventh_proviso)
    migrated_seventh_proviso.pop("otherClauseIVDetail", None)
    migrated_filing["seventhProviso"] = migrated_seventh_proviso
    migrated["filing"] = migrated_filing
    return migrated


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

    payload = _migrate_stored_canonical_payload(payload)
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
    payload = _migrate_stored_canonical_payload(payload)
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
        logger.error(
            "CBDT JSON generation failed for client %s AY %s: %s",
            client.pan, year, exc.message,
        )
        for issue in exc.errors:
            logger.error("  blocking issue: %s", issue)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "errors": exc.errors},
        ) from exc
    content = json.dumps(official_json, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=CBDT-{draft.form.replace('-', '')}_{client.pan}_{year}.json",
            "X-CBDT-Computation-Status": "FORM_COMPUTATION",
            "X-CBDT-Schema-Valid": "true",
        },
    )


def _load_saved_draft(
    client_id: str,
    year: str,
    current_user: User,
    db: Session,
) -> tuple[Client, ClientITR | None, ReturnDraft]:
    """Load + validate the saved canonical draft for download endpoints.

    Returns the resolved client, the raw ``ClientITR`` row (or None when
    no draft exists yet), and the typed ``ReturnDraft``. Raises 422 for
    legacy flat blobs (no ``schemaVersion``) and 500 for stored drafts
    that fail canonical validation — mirroring the generate-cbdt-json gate.

    Args:
        client_id: Public UUID or legacy numeric client identifier.
        year: Assessment year of the saved draft.
        current_user: Authenticated owner injected by FastAPI.
        db: Request database session.

    Returns:
        ``(client, itr_row, draft)`` — the draft is a seed when no row
        exists, so download endpoints can still emit a valid (empty) draft.

    Raises:
        HTTPException: 404 for unknown client; 422 for legacy blobs or
            a draft/URL year mismatch; 500 for invalid stored JSON or a
            draft that fails canonical validation.
    """
    client = resolve_owned_client(client_id, current_user.id, db)
    itr = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client.id, ClientITR.year == year)
        .first()
    )
    if itr is None or not itr.form_data or itr.form_data == "{}":
        return client, itr, draft_from_client_seed(client, year)
    try:
        payload = json.loads(itr.form_data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stored ITR data is not valid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict) or "schemaVersion" not in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Saved ITR data is a legacy flat blob.",
                "errors": [
                    "Save this return through the canonical /v2 endpoint before download."
                ],
            },
        )
    payload = _migrate_stored_canonical_payload(payload)
    try:
        draft = ReturnDraft.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Stored ITR draft failed canonical validation.",
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
    return client, itr, draft


@router.get("/{year}/download")
def download_client_itr_v2(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the saved canonical draft as a JSON file.

    Returns the exact typed ``ReturnDraft`` JSON that was persisted via
    ``PUT /v2/clients/{id}/itr/{year}`` — round-trip fidelity with the
    save endpoint. When no draft exists yet, seeds an empty draft from
    the ``Client`` master so the download always yields a valid file.

    Args:
        client_id: Public UUID or legacy numeric client identifier.
        year: Assessment year of the saved draft.
        current_user: Authenticated owner injected by FastAPI.
        db: Request database session.

    Returns:
        Download response containing the canonical draft JSON.

    Raises:
        HTTPException: 404 for unknown client; 422 for legacy blobs or a
            draft/URL year mismatch; 500 for invalid stored JSON.
    """
    client, _itr, draft = _load_saved_draft(client_id, year, current_user, db)
    content = draft.model_dump_json(indent=2)
    form_slug = (draft.form or "ITR-1").replace("-", "")
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=ITR_{form_slug}_{client.pan}_{year}.json",
            "X-Return-Form": draft.form or "ITR-1",
            # Starlette requires every header value to be a str; schemaVersion
            # is an int on the ReturnDraft model, so coerce it explicitly.
            "X-Return-SchemaVersion": str(draft.schemaVersion),
        },
    )


@router.get("/{year}/download-pdf")
def download_client_itr_pdf_v2(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download a lightweight PDF snapshot of the saved canonical draft.

    Renders a single-page summary from the typed ``ReturnDraft`` (client
    identity, form, regime, and the income-head totals the draft
    carries). It does not fabricate tax figures — for the official CBDT
    computation, use ``POST /v2/clients/{id}/itr/{year}/generate-cbdt-json``.

    When ``reportlab`` is unavailable, emits a minimal valid PDF shell
    so the endpoint never 500s on a dependency gap (mirrors the legacy
    ``download-pdf`` fallback).

    Args:
        client_id: Public UUID or legacy numeric client identifier.
        year: Assessment year of the saved draft.
        current_user: Authenticated owner injected by FastAPI.
        db: Request database session.

    Returns:
        Download response containing the PDF snapshot.

    Raises:
        HTTPException: 404 for unknown client; 422 for legacy blobs or a
            draft/URL year mismatch; 500 for invalid stored JSON.
    """
    client, itr, draft = _load_saved_draft(client_id, year, current_user, db)

    import io

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        pdf_data = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << >> /Contents 4 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Length 50 >>\nstream\nBT /F1 12 Tf 70 800 Td "
            b"(ITR Computation Report) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n"
            b"0000000111 00000 n\n0000000212 00000 n\ntrailer\n<< /Size 5 >>\n"
            b"startxref\n312\n%%EOF"
        )
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=ITR_{client.pan}_{year}.pdf",
            },
        )

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, f"ITR Computation Report — {client.name}")
    c.setFont("Helvetica", 10)
    form_label = itr.itr_type if itr and itr.itr_type else (draft.form or "ITR-1")
    regime_label = (draft.regime or "new").upper()
    c.drawString(
        50, height - 80,
        f"PAN: {client.pan or 'N/A'}    Year: {year}    Form: {form_label}    Regime: {regime_label}",
    )
    y = height - 110
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Canonical Draft Summary")
    y -= 18
    c.setFont("Helvetica", 9)

    # Surface the typed draft's income-head counts + key personal fields.
    summary_lines: list[str] = [
        f"Schema version: {draft.schemaVersion}",
        f"Assessee: {draft.personal.name or client.name or '—'}",
        f"Employers: {len(draft.employers)}",
        f"House properties: {len(draft.houseProperties)}",
        f"Businesses: {len(draft.businesses)}",
        f"Bank accounts: {len(draft.bankAccounts)}",
        f"TDS credits: {len(draft.taxes.tds)}",
        f"Tax challans: {len(draft.taxes.challans)}",
        f"Filing section: {draft.filing.filingSection}",
    ]
    for line in summary_lines:
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = height - 50
        c.drawString(50, y, line)
        y -= 14

    c.save()
    pdf_bytes = buf.getvalue()
    form_slug = (draft.form or "ITR-1").replace("-", "")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ITR_{form_slug}_{client.pan}_{year}.pdf",
            "X-Return-Form": draft.form or "ITR-1",
        },
    )
