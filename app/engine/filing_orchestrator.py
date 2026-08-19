"""
Mode-agnostic ITD JSON producer — the shared FilingCore.

This orchestrator is the single entry point that both ERI modes share:
  - Type-3 (this season): JSON → validate → export/upload via Playwright.
  - Type-2 (next season):  JSON → validate → signed API envelope via AWS.

It produces a CBDT-compliant ITR JSON for a given ``(client, ay, itr_type)``
by delegating to the per-form builders in :mod:`app.engine.itd` and the
existing :func:`app.engine.filing_gateway.generate_filing_artifact`.

The Digest is computed INSIDE the per-form builders (each calls
``_compute_digest(itr_json)`` at the end and injects it into
``CreationInfo.Digest``). Because ``_compute_digest`` and
``_creation_info`` are now env-scoped via :mod:`app.eri.config`, the same
``produce_itd_json()`` call yields a JSON whose SW_ID + Digest match the
active ``(ERI_MODE, ERI_ENV)`` — no transport-specific code is needed here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import Client, ClientITR, ImportedDocument, User

_log = logging.getLogger("taxify.engine.filing_orchestrator")


class FilingOrchestratorError(ValueError):
    """Raised when ITD JSON generation fails (computation, schema, or digest)."""


def produce_itd_json(
    *,
    client_id: int,
    ay: str,
    itr_type: str,
    flat_draft: dict[str, Any],
    user: User,
    db: Session,
    include_official_json: bool = True,
) -> dict[str, Any]:
    """Build, digest, and schema-validate the ITD JSON for a client+AY+form.

    This is the mode-agnostic producer shared by Type-2 (API) and Type-3
    (offline utility) flows. It does NOT touch the ITD gateway.

    Args:
        client_id: The DB client id whose return is being produced.
        ay: Assessment year, e.g. "2026-27" or "2026".
        itr_type: One of "ITR-1", "ITR-2", "ITR-3", "ITR-4".
        flat_draft: The canonical flat draft dict (frontend ReturnDraft payload).
        user: The authenticated user (required by the tax engine).
        db: Database session (used for persistence of the generated JSON).
        include_official_json: If False, only the tax summary is computed
            and an empty dict is returned (used for dry-run previews).

    Returns:
        The official CBDT-compliant ITR JSON dict, with Digest populated.

    Raises:
        FilingOrchestratorError: If the form is unsupported, computation
            fails, schema validation fails, or the builder rejects the input.
    """
    # Local import to avoid a circular dependency at module load time
    # (filing_gateway imports from app.engine, which imports app.engine.itd,
    # which would import this module if we imported eagerly here).
    from app.engine.filing_gateway import (
        FilingGatewayError,
        generate_filing_artifact,
    )

    form = itr_type.strip().upper()
    if form not in {"ITR-1", "ITR-2", "ITR-3", "ITR-4"}:
        raise FilingOrchestratorError(
            f"Unsupported ITR form: {form!r}. "
            "Must be one of ITR-1, ITR-2, ITR-3, ITR-4."
        )

    payload = dict(flat_draft)
    payload["form"] = form
    payload["itrForm"] = form

    _log.info("Producing ITD JSON for client_id=%s ay=%s form=%s",
              client_id, ay, form)

    try:
        result = generate_filing_artifact(
            flat_draft=payload,
            user=user,
            db=db,
            include_official_json=include_official_json,
        )
    except FilingGatewayError as exc:
        raise FilingOrchestratorError(
            f"ITD JSON generation failed for {form}: {exc}",
        ) from exc

    official_json: Optional[dict[str, Any]] = result.official_json
    if not include_official_json or official_json is None:
        # Dry-run preview: return an empty placeholder.
        return {}

    # Persist the generated JSON as an ImportedDocument so it can be
    # re-exported / re-uploaded without recomputing the tax.
    _persist_generated_json(
        db=db,
        client_id=client_id,
        user_id=user.id,
        ay=ay,
        itr_type=form,
        official_json=official_json,
    )

    return official_json


def _persist_generated_json(
    *,
    db: Session,
    client_id: int,
    user_id: int,
    ay: str,
    itr_type: str,
    official_json: dict[str, Any],
) -> None:
    """Persist a generated ITD JSON blob into the ImportedDocument table.

    Stores under ``document_type="filed_return"``, ``source="generated"`` so
    the export/upload step can retrieve it without recomputing the tax.
    Uses ``merge`` to upsert on the (client_id, ay, document_type) unique
    constraint.
    """
    raw_content = json.dumps(official_json, ensure_ascii=False)
    doc = ImportedDocument(
        client_id=client_id,
        user_id=user_id,
        assessment_year=ay,
        document_type="filed_return",
        source="generated",
        raw_content=raw_content,
        parsed_content=raw_content,
    )
    db.merge(doc)
    db.commit()
    _log.info(
        "Persisted generated ITD JSON (client_id=%s ay=%s form=%s, %d bytes)",
        client_id, ay, itr_type, len(raw_content),
    )
