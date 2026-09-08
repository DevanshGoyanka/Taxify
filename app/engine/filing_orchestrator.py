"""
Mode-agnostic ITD JSON producer — the shared FilingCore.

This orchestrator is the single entry point that both ERI modes share:
  - Type-3 (this season): JSON → validate → export/upload via Playwright.
  - Type-2 (next season):  JSON → validate → signed API envelope via AWS.

It produces a CBDT-compliant ITR JSON for a given ``(client, ay, itr_type)``
by delegating to :func:`app.engine.filing_gateway_v2.generate_cbdt_json`
(ITR-1/2/4; ITR-3 is explicitly rejected — not yet on the canonical
pipeline) and, through it, the per-form builders in :mod:`app.engine.itd`.
The legacy flat-draft :mod:`app.engine.filing_gateway` path is no longer
reachable from this orchestrator.

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

from app.db.models import ImportedDocument, User

_log = logging.getLogger("taxify.engine.filing_orchestrator")


class FilingOrchestratorError(ValueError):
    """Raised when ITD JSON generation fails (computation, schema, or digest)."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]


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
    # Local import avoids a circular dependency at module load time.
    form = itr_type.strip().upper()
    if form not in {"ITR-1", "ITR-2", "ITR-3", "ITR-4"}:
        raise FilingOrchestratorError(
            f"Unsupported ITR form: {form!r}. "
            "Must be one of ITR-1, ITR-2, ITR-3, ITR-4."
        )

    payload = dict(flat_draft)
    payload["form"] = form

    _log.info("Producing ITD JSON for client_id=%s ay=%s form=%s",
              client_id, ay, form)

    official_json: Optional[dict[str, Any]] = None

    if form == "ITR-3":
        raise FilingOrchestratorError(
            "ITR-3 filing is not supported by the canonical filing pipeline yet."
        )

    if form in {"ITR-1", "ITR-2", "ITR-4"}:
        # All currently supported forms use the canonical v2 pipeline. The
        # gateway dispatches by draft.form and runs preparation, input and
        # calculation validation, CBDT building, and official schema
        # validation before returning the generated JSON.
        from app.engine.filing_gateway_v2 import (
            FilingGatewayV2Error,
            generate_cbdt_json,
        )
        from app.schemas.return_draft import ReturnDraft, migrate_stored_draft_payload
        try:
            if "schemaVersion" not in payload:
                raise FilingOrchestratorError(
                    f"{form} filing requires a canonical /v2 ReturnDraft. "
                    "Save the return through /v2/clients/{client_id}/itr/{year} "
                    "before generating or submitting it."
                )
            # This payload may come straight from ClientITR.form_data (the
            # Type-3 export/submission path in app/eri/type3/json_exporter.py
            # loads it without going through the /v2 router's own migration),
            # so the same stored-payload migration must run here too.
            draft = ReturnDraft.model_validate(migrate_stored_draft_payload(payload))
            if draft.form != form:
                raise FilingOrchestratorError(
                    f"Saved canonical draft form is {draft.form}, not {form}."
                )
            if draft.assessmentYear and draft.assessmentYear != ay:
                raise FilingOrchestratorError(
                    f"Saved draft assessment year {draft.assessmentYear} "
                    f"does not match requested year {ay}."
                )
            draft.assessmentYear = ay
            official_json, _summary = generate_cbdt_json(draft)
        except FilingOrchestratorError:
            raise
        except FilingGatewayV2Error as exc:
            raise FilingOrchestratorError(
                f"{form} JSON generation failed: {exc}",
                errors=list(exc.errors),
            ) from exc
        except Exception as exc:
            raise FilingOrchestratorError(
                f"{form} draft mapping or generation failed: {exc}",
            ) from exc
    else:
        # Keep the legacy gateway unavailable for unsupported forms rather
        # than allowing a flat draft to bypass canonical validation.
        raise FilingOrchestratorError(f"Unsupported filing form: {form}.")

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

    Stores under ``document_type="generated_itr"``, ``source="generated"``.
    This is intentionally distinct from ``filed_return`` so producing a new
    return can never overwrite a prior/current return downloaded from ITD.
    """
    raw_content = json.dumps(official_json, ensure_ascii=False)
    existing = (
        db.query(ImportedDocument)
        .filter(
            ImportedDocument.client_id == client_id,
            ImportedDocument.assessment_year == ay,
            ImportedDocument.document_type == "generated_itr",
        )
        .first()
    )
    if existing is None:
        existing = ImportedDocument(
            client_id=client_id,
            user_id=user_id,
            assessment_year=ay,
            document_type="generated_itr",
            source="generated",
            raw_content=raw_content,
            parsed_content=raw_content,
        )
        db.add(existing)
    else:
        existing.user_id = user_id
        existing.source = "generated"
        existing.raw_content = raw_content
        existing.parsed_content = raw_content
    db.commit()
    _log.info(
        "Persisted generated ITD JSON (client_id=%s ay=%s form=%s, %d bytes)",
        client_id, ay, itr_type, len(raw_content),
    )
