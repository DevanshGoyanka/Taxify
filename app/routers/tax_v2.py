"""Phase 2 canonical ITR-1 tax computation + unified import endpoint."""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import ImportedDocument, User
from app.engine.filing_gateway_v2 import FilingGatewayV2Error, compute_canonical_itr1
from app.schemas.return_draft import ReturnDraft


router = APIRouter(prefix="/v2", tags=["tax_v2"])


@router.post("/tax-summary/compute")
def compute_tax_summary_v2(
    draft: ReturnDraft,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Compute a tax summary directly from a canonical ReturnDraft.

    For ITR-1, uses the v2 canonical pipeline. For ITR-2/3/4, delegates
    to the legacy ``/tax-summary/compute`` endpoint which already supports
    all forms via the flat-payload gateway.

    Args:
        draft: Canonical typed return draft supplied as the direct JSON body.

    Returns:
        A legacy-headline-compatible summary plus structured breakdown/issues.

    Raises:
        HTTPException: With status 422 for mapping or computation failures.
    """
    # ITR-1 uses the v2 canonical pipeline; other forms use the legacy
    # compute path which already supports ITR-2/3/4.
    if draft.form != "ITR-1":
        from app.routers.tax import _compute_tax_summary_impl
        # Convert the canonical ReturnDraft to the flat payload the legacy
        # compute path expects.
        payload = draft.model_dump(by_alias=True, exclude_none=True)
        payload["form"] = draft.form
        if draft.assessmentYear:
            payload["assessmentYear"] = draft.assessmentYear
        try:
            return _compute_tax_summary_impl(
                payload,
                regime="OLD" if draft.regime == "old" else "NEW",
                current_user=current_user,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f"{draft.form} computation failed: {exc}",
                    "errors": [str(exc)],
                },
            ) from exc

    try:
        return compute_canonical_itr1(draft).summary
    except FilingGatewayV2Error as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "errors": exc.errors},
        ) from exc


# ──────────────────────────────────────────────────────────────────────────────
# Unified import endpoint (Phase 2 of the CG + imports workstream)
# ──────────────────────────────────────────────────────────────────────────────

# Lazy imports — the ais_extractor package may be unavailable in some
# deployment environments, and the parsers are heavy (PyMuPDF/pdfplumber).
def _load_parsers() -> dict:
    try:
        from ais_extractor.extractor import extract_ais, extract_ais_json
        from ais_extractor.tis_extractor import extract_tis, tis_to_frontend_json
        from ais_extractor.as26_extractor import extract_26as
        from ais_extractor.reconciliation import reconcile as _reconcile
        from app.engine.importers.prefill_parser import parse_prefill_json, prefill_extraction_to_dict
        return {
            "extract_ais": extract_ais,
            "extract_ais_json": extract_ais_json,
            "extract_tis": extract_tis,
            "tis_to_frontend_json": tis_to_frontend_json,
            "extract_26as": extract_26as,
            "reconcile": _reconcile,
            "parse_prefill_json": parse_prefill_json,
            "prefill_extraction_to_dict": prefill_extraction_to_dict,
        }
    except ImportError as exc:
        raise HTTPException(501, f"Import parsers not available: {exc}") from exc


def _resolve_client_id(raw: Optional[str], db: Session, current_user: User) -> Optional[int]:
    """Resolve a client id from a string (numeric public_id or UUID)."""
    if not raw:
        return None
    from app.db.models import Client
    try:
        numeric = int(raw)
        client = db.query(Client).filter(Client.id == numeric, Client.user_id == current_user.id).first()
        if client is not None:
            return client.id
    except (ValueError, TypeError):
        pass
    client = db.query(Client).filter(
        Client.public_id == raw,
        Client.user_id == current_user.id,
    ).first()
    return client.id if client else None


def _upsert_imported_document(
    db: Session,
    client_id: Optional[int],
    user_id: int,
    assessment_year: str,
    document_type: str,
    source: str,
    raw_content: str,
    parsed_content: str,
) -> None:
    """Insert or update an ImportedDocument row (delegates to shared service).

    Delegates to ``app.db.imported_document_service.upsert_imported_document``
    so the automation worker and the manual-upload endpoints share one dedup
    key and one provenance field (remediation P1/P2/P4).
    """
    from app.db.imported_document_service import upsert_imported_document
    upsert_imported_document(
        db=db,
        client_id=client_id,
        user_id=user_id,
        assessment_year=assessment_year,
        document_type=document_type,
        source=source,
        raw_content=raw_content,
        parsed_content=parsed_content,
    )


def _parse_one_pdf(parsers: dict, doc_type: str, content: bytes) -> dict:
    """Parse a single PDF/JSON document via the correct extractor.

    Accepts either raw PDF bytes (detected by the %PDF- magic) or a
    UTF-8 JSON string.  Returns the extractor's native dict shape.
    """
    if content[:4] == b"%PDF":
        suffix = {"ais": ".pdf", "tis": ".pdf", "form26as": ".pdf"}[doc_type]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            if doc_type == "ais":
                return json.loads(parsers["extract_ais_json"](str(tmp_path)))
            if doc_type == "tis":
                return json.loads(parsers["tis_to_frontend_json"](
                    parsers["extract_tis"](str(tmp_path))
                ))
            if doc_type == "form26as":
                return parsers["extract_26as"](str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)
    # JSON passthrough
    try:
        return json.loads(content.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f"Invalid {doc_type} JSON: {exc}") from exc


@router.post("/imports/parse-reconcile")
async def parse_reconcile(
    ais: UploadFile = File(default=None),
    tis: UploadFile = File(default=None),
    form26as: UploadFile = File(default=None),
    prefill: UploadFile = File(default=None),
    clientId: Optional[str] = Form(default=None),
    assessmentYear: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Parse + reconcile any combination of AIS / TIS / 26AS / Prefill.

    This is the **unified import endpoint** — both the automation worker
    and the manual single-document import UI call it.  Each document is
    optional; the endpoint parses whatever is supplied and runs the
    reconciliation engine on the combination present.

    Returns the full ``ReconciledResults`` payload (including
    ``capital_gain_evidence``, ``capital_gain_controls``, and
    ``capital_gain_control_discrepancies``), plus the prefill extraction
    under the ``prefill`` key.

    All supplied documents are persisted to the ``ImportedDocument``
    table for re-reconciliation without re-download.
    """
    parsers = _load_parsers()
    ay = assessmentYear or ""
    client_db_id = _resolve_client_id(clientId, db, current_user)

    parsed: dict[str, Any] = {}
    raw_blobs: dict[str, bytes] = {}
    extraction_errors: list[str] = []  # P5: attach consistently with automation

    for name, upload in (("ais", ais), ("tis", tis), ("form26as", form26as), ("prefill", prefill)):
        if upload is None:
            continue
        content = await upload.read()
        await upload.seek(0)
        raw_blobs[name] = content
        try:
            if name == "prefill":
                try:
                    payload = json.loads(content.decode("utf-8-sig"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise HTTPException(422, f"Invalid Prefill JSON: {exc}") from exc
                extraction = parsers["parse_prefill_json"](payload, assessment_year=ay)
                parsed["prefill"] = parsers["prefill_extraction_to_dict"](extraction)
            else:
                parsed[name] = _parse_one_pdf(parsers, name, content)
        except HTTPException:
            raise
        except Exception as exc:
            extraction_errors.append(f"{name} extraction failed: {type(exc).__name__}: {exc}")

    # Persist each supplied document to ImportedDocument (durable re-recon).
    for name, content in raw_blobs.items():
        doc_type = "prefill" if name == "prefill" else name
        parsed_str = json.dumps(parsed.get(name, {}), ensure_ascii=False, default=str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, doc_type, "upload",
            raw_content=content.decode("utf-8", errors="replace"),
            parsed_content=parsed_str,
        )

    # Reconcile — run the engine on whatever combination is present.
    if parsed.get("ais") or parsed.get("tis") or parsed.get("form26as"):
        reconciled = parsers["reconcile"](
            ais_data=parsed.get("ais", {}),
            tis_data=parsed.get("tis", {}),
            as26_data=parsed.get("form26as", {}),
            prefill_data=parsed.get("prefill"),
        )
        if parsed.get("prefill"):
            reconciled["prefill"] = parsed["prefill"]
        if extraction_errors:
            reconciled["_extraction_errors"] = extraction_errors
        return reconciled

    # Prefill-only import (no AIS/TIS/26AS) — return the prefill extraction
    # wrapped in the prefill key (no reconciliation to run).
    if parsed.get("prefill"):
        out: dict[str, Any] = {"prefill": parsed["prefill"]}
        if extraction_errors:
            out["_extraction_errors"] = extraction_errors
        return out

    return {"message": "No documents supplied."}
