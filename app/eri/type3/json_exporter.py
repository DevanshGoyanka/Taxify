"""CBDT JSON file export for the ERI Type-3 filing flow."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Client, ClientITR, User
from app.engine.filing_orchestrator import produce_itd_json
from app.eri.digest import serialize_for_upload


class Type3JsonExportError(ValueError):
    """Raised when a filing artifact cannot be safely exported."""


def serialize_itd_json(itr_json: dict[str, Any]) -> str:
    """Return the canonical UTF-8 JSON text for upload to the ITD portal.

    Delegates to :func:`app.eri.digest.serialize_for_upload` — the SINGLE
    canonical serializer shared with the Digest computation. The bytes
    written to the ``.json`` file are therefore byte-identical to the
    bytes hashed by :func:`app.eri.digest.compute_digest` (with only the
    ``Digest`` value differing from the placeholder ``"-"`` to the
    computed 44-char digest), so the portal's integrity check never
    mismatches due to formatting drift.
    """
    if not isinstance(itr_json, dict) or not itr_json:
        raise Type3JsonExportError("The ITD JSON payload is empty or invalid.")
    return serialize_for_upload(itr_json)


def export_itd_json_file(
    *,
    client_id: int,
    ay: str,
    itr_type: str,
    flat_draft: dict[str, Any] | None,
    user: User,
    db: Session,
    output_dir: str | Path,
) -> Path:
    """Generate, validate, and write one deterministic CBDT JSON artifact."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        raise Type3JsonExportError("Client not found.")

    filing_draft = (
        dict(flat_draft)
        if flat_draft is not None
        else load_saved_filing_draft(
            db=db,
            client_id=client_id,
            ay=ay,
            itr_type=itr_type,
        )
    )
    official_json = produce_itd_json(
        client_id=client_id,
        ay=ay,
        itr_type=itr_type,
        flat_draft=filing_draft,
        user=user,
        db=db,
    )
    _require_filing_digest(official_json, itr_type)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    # CBDT-prescribed naming convention: {form}_{pan}_AY{year}.json
    # e.g. ITR-1_ABCDE1234F_AY2026-27.json (matches the reference repo).
    form = itr_type.strip().upper()
    pan = _safe_component(client.pan or f"client-{client_id}")
    filename = f"{form}_{pan}_AY{ay}.json"
    final_path = destination / filename
    partial_path = destination / f"{filename}.partial"
    partial_path.write_text(serialize_itd_json(official_json), encoding="utf-8")
    partial_path.replace(final_path)
    return final_path


def load_saved_filing_draft(
    *,
    db: Session,
    client_id: int,
    ay: str,
    itr_type: str,
) -> dict[str, Any]:
    """Load and validate the saved draft used for filing."""
    row = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client_id, ClientITR.year == ay)
        .first()
    )
    if row is None or not row.form_data or row.form_data == "{}":
        raise Type3JsonExportError(
            "No saved ITR draft exists for this client and assessment year."
        )
    try:
        payload = json.loads(row.form_data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise Type3JsonExportError("The saved ITR draft is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise Type3JsonExportError("The saved ITR draft must be a JSON object.")

    requested = itr_type.strip().upper()
    saved = str(payload.get("form") or payload.get("itrForm") or row.itr_type).upper()
    if saved.replace("-", "") != requested.replace("-", ""):
        raise Type3JsonExportError(
            f"Saved draft form {saved} does not match requested form {requested}."
        )
    if requested in {"ITR-1", "ITR-2"} and "schemaVersion" not in payload:
        raise Type3JsonExportError(
            f"{requested} filing requires a canonical /v2 saved draft."
        )
    return payload


def _require_filing_digest(itr_json: dict[str, Any], itr_type: str) -> None:
    """Reject placeholder or malformed digests before an artifact leaves Taxify."""
    form = itr_type.strip().upper().replace("-", "")
    try:
        digest = itr_json["ITR"][form]["CreationInfo"]["Digest"]
    except (KeyError, TypeError) as exc:
        raise Type3JsonExportError(
            f"Generated {itr_type} JSON does not contain CreationInfo.Digest."
        ) from exc
    if not isinstance(digest, str) or digest == "-" or len(digest) != 44:
        raise Type3JsonExportError(
            "Generated ITD JSON has no valid 44-character Digest. "
            "Check the active Type-3 SW_ID, secret key, and iteration count."
        )


def _safe_component(value: str) -> str:
    """Return a filesystem-safe filename component without taxpayer data logs."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    safe = safe.strip("._")
    if not safe:
        raise Type3JsonExportError("A required filename component is empty.")
    return safe
