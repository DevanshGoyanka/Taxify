"""Unified import-document persistence layer.

A single source of truth for the ``imported_document`` table. Both the
portal-automation worker (``app/automation/job_worker.py``) and the
manual-upload endpoints (``app/routers/integration.py``,
``app/routers/tax_v2.py``) call this module, so the two ingestion paths
share one dedup key (client × assessment year × document type) and one
provenance field.

This module exists to close the cross-path gap documented in
``IMPORTS_AND_RECONCILIATION_END_TO_END.md`` §5.3 P1/P2/P4: previously the
automation worker stored its reconciled blob only on ``AutomationJob`` and
wrote nothing to ``imported_document``, so a manual re-upload could not be
diffed against the automation's parsed version, and a manual re-reconcile
could silently lose TDS/TCS credits (P6) because the 26AS row was absent.

Public API:
  - ``upsert_imported_document``  — insert-or-replace a document row
  - ``load_imported_documents``   — read all parsed rows for a client+AY
  - ``reconcile_imported_documents`` — load + reconcile server-side (P6 fix)
"""

from __future__ import annotations

import base64
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import ImportedDocument


# ── Constants ────────────────────────────────────────────────────────────────

#: The four persisted document-type values (the dedup key's third leg).
DOCUMENT_TYPES: tuple[str, ...] = ("ais", "tis", "26as", "prefill")

#: Source provenance values written to the ``source`` column.  This is the
#: field that distinguishes an automation-written row from a manually-uploaded
#: one — the provenance signal referenced by remediation P1/P2.
SOURCE_AUTOMATION: str = "automation"
SOURCE_UPLOAD: str = "upload"


# ── Upsert ───────────────────────────────────────────────────────────────────


def upsert_imported_document(
    db: Session,
    client_id: int,
    user_id: int,
    assessment_year: str,
    document_type: str,
    source: str,
    raw_content: str,
    parsed_content: str,
) -> ImportedDocument:
    """Insert or update an ``ImportedDocument`` row.

    The dedup key is ``(client_id, assessment_year, document_type)`` — the
    table's unique constraint.  On conflict the row's ``raw_content`` and
    ``parsed_content`` are replaced in place (the latest data wins for that
    document type); the ``source`` column is updated so provenance tracks the
    most recent writer (automation vs upload).

    Args:
        db: SQLAlchemy session.
        client_id: Required positive client DB id owned by the user.
        user_id: Owning user id.
        assessment_year: e.g. ``"2026-27"``.
        document_type: one of ``DOCUMENT_TYPES`` (``"ais"``/``"tis"``/
            ``"26as"``/``"prefill"``).
        source: ``SOURCE_AUTOMATION`` or ``SOURCE_UPLOAD``.
        raw_content: base64-encoded bytes (for binary PDFs) or raw JSON text.
        parsed_content: the extractor's parsed JSON (string).

    Returns:
        The persisted ``ImportedDocument`` row (refreshed).
    """
    if client_id <= 0:
        raise ValueError("client_id must be a positive, user-owned client id")

    existing = (
        db.query(ImportedDocument)
        .filter(
            ImportedDocument.client_id == client_id,
            ImportedDocument.assessment_year == assessment_year,
            ImportedDocument.document_type == document_type,
        )
        .first()
    )
    if existing is not None:
        existing.raw_content = raw_content
        existing.parsed_content = parsed_content
        existing.source = source
        db.commit()
        db.refresh(existing)
        return existing
    row = ImportedDocument(
        client_id=client_id,
        user_id=user_id,
        assessment_year=assessment_year,
        document_type=document_type,
        source=source,
        raw_content=raw_content,
        parsed_content=parsed_content,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def encode_bytes(content: bytes) -> str:
    """Base64-encode raw bytes for storage in a ``Text`` column."""
    return base64.b64encode(content).decode("ascii")


def encode_text(content: bytes) -> str:
    """Decode bytes as UTF-8 (replace errors) for JSON storage."""
    return content.decode("utf-8", errors="replace")


# ── Load (re-read) ───────────────────────────────────────────────────────────


def load_imported_documents(
    db: Session,
    client_id: int,
    assessment_year: str,
) -> dict[str, dict[str, Any]]:
    """Load every parsed imported-document row for a client+AY.

    Returns a mapping ``{document_type: {"parsed": <dict>, "source": <str>,
    "raw": <str>}}`` for each row present.  This is the foundation for
    remediation P6: a server-side reconcile call that reads from the
    persisted table instead of depending on frontend in-memory state, so a
    page refresh between upload and reconcile no longer silently drops TDS.

    Args:
        db: SQLAlchemy session.
        client_id: Client DB id.
        assessment_year: e.g. ``"2026-27"``.

    Returns:
        ``{document_type: {"parsed": dict, "source": str, "raw": str}}``;
        empty dict if no rows exist for this client+AY.
    """
    rows = (
        db.query(ImportedDocument)
        .filter(
            ImportedDocument.client_id == client_id,
            ImportedDocument.assessment_year == assessment_year,
        )
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            parsed = json.loads(row.parsed_content or "{}")
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        out[row.document_type] = {
            "parsed": parsed,
            "source": row.source,
            "raw": row.raw_content,
        }
    return out


# ── Server-side reconcile (P6 fix) ───────────────────────────────────────────


def reconcile_imported_documents(
    db: Session,
    client_id: int,
    assessment_year: str,
) -> dict[str, Any]:
    """Load the persisted import set for a client+AY and reconcile it.

    This is the server-side reconcile path that closes P6: it never depends
    on frontend in-memory state — it reads each document's parsed JSON from
    ``imported_document`` and runs ``reconcile()`` on the combination
    present.  The four automation-only keys (``prefill``,
    ``filing_advisory``, ``filing_mode_classification``,
    ``_extraction_errors``) are attached if they were stored (the automation
    worker persists them via the ``prefill`` document row; the advisory /
    classification / errors are attached separately when available).

    Args:
        db: SQLAlchemy session.
        client_id: Client DB id.
        assessment_year: e.g. ``"2026-27"``.

    Returns:
        The reconciled payload (same shape as
        ``ais_extractor.reconciliation.reconcile`` output), with ``prefill``
        attached if a prefill row exists.  If no AIS/TIS/26AS rows exist,
        returns ``{"prefill": <prefill dict or {}>, "summary": {...empty...}}``.
    """
    from ais_extractor.reconciliation import reconcile as _reconcile

    docs = load_imported_documents(db, client_id, assessment_year)
    ais_data = docs.get("ais", {}).get("parsed", {}) if "ais" in docs else {}
    tis_data = docs.get("tis", {}).get("parsed", {}) if "tis" in docs else {}
    as26_data = docs.get("26as", {}).get("parsed", {}) if "26as" in docs else {}
    prefill_data = docs.get("prefill", {}).get("parsed", {}) if "prefill" in docs else {}

    if not (ais_data or tis_data or as26_data):
        # Nothing to reconcile — return an empty shell + prefill if present.
        return {
            "income_heads": {},
            "unmatched": {"tis_only": [], "ais_only": [], "as26_only": []},
            "summary": {
                "total_entries": 0,
                "total_final_income": 0.0,
                "total_discrepancies": 0,
                "matched_all_three": 0,
                "matched_two": 0,
                "matched_one": 0,
                "unmatched_tis": 0,
                "unmatched_ais": 0,
                "unmatched_as26": 0,
            },
            **({"prefill": prefill_data} if prefill_data else {}),
        }

    reconciled = _reconcile(ais_data, tis_data, as26_data)
    if prefill_data:
        reconciled["prefill"] = prefill_data
    return reconciled
