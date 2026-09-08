"""Filing-action audit logging service.

Per the Dual-Mode ERI Integration Plan §7.5 and §10.1, every filing action
(generate, validate, upload, everify, ack) is audit-logged with the tuple
``{user_id, client_id, ay, mode, environment, action, outcome, itd_code}``.

Critical compliance rule: NO payload, JSON, PAN, password, OTP, or taxpayer
PII is ever stored in the audit log. Only the action descriptor, a
high-level outcome (``ok`` / ``error``), and — for API-driven flows
(Type-2) — an ITD response code. The ``message`` field carries at most a
short, non-PII status string (e.g. "Digest computed" or
"Acknowledgement downloaded"). Audit failures are best-effort and must
never break the filing flow they are logging.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from sqlalchemy.orm import Session

from app.db.models import AuditLog, Client, User

_log = logging.getLogger("taxify.services.audit")

Action = Literal[
    "generate", "validate", "upload", "everify", "ack", "submit", "download"
]
Outcome = Literal["ok", "error"]


def _resolve_creds_descriptor() -> tuple[str, str]:
    """Return the active (mode, environment) for the audit row.

    Imports :func:`app.eri.config.get_eri_credentials` dynamically (at call
    time) so test mocks that patch ``app.eri.config.get_eri_credentials``
    take effect. Falls back to ``("unknown", "unknown")`` if the resolver
    is misconfigured — the audit row must still be written (best-effort),
    so a credential failure during a filing action is itself audit-worthy.
    """
    from app.eri.config import get_eri_credentials
    try:
        creds = get_eri_credentials()
        return creds.mode, creds.environment
    except Exception:
        return "unknown", "unknown"


def log_filing_action(
    *,
    db: Session,
    user: User,
    client: Client,
    assessment_year: str,
    itr_type: str,
    action: Action,
    outcome: Outcome,
    itd_code: Optional[str] = None,
    message: str = "",
) -> None:
    """Append one audit row for a filing action (ORM-object form).

    Use this from request-scoped code where the ``User`` and ``Client``
    ORM objects are already loaded.

    Args:
        db: The request-scoped DB session.
        user: The authenticated user who triggered the action.
        client: The client whose return is being filed.
        assessment_year: e.g. "2026-27".
        itr_type: One of "ITR-1" .. "ITR-4".
        action: The filing action (generate/validate/upload/everify/ack/
            submit/download).
        outcome: ``ok`` or ``error``.
        itd_code: Optional ITD response code (Type-2 API flows only).
        message: Optional short, non-PII status string. Must never carry
            JSON payload, PAN, password, OTP, or taxpayer PII.

    The write is best-effort: an audit-log failure (DB error, full disk,
    etc.) must never break the filing action it is logging, so it is
    swallowed and logged server-side.
    """
    _write_audit_row(
        db=db,
        user_id=user.id,
        client_id=client.id,
        assessment_year=assessment_year,
        itr_type=itr_type,
        action=action,
        outcome=outcome,
        itd_code=itd_code,
        message=message,
    )


def log_filing_action_by_id(
    *,
    db: Session,
    user_id: int,
    client_id: int,
    assessment_year: str,
    itr_type: str,
    action: Action,
    outcome: Outcome,
    itd_code: Optional[str] = None,
    message: str = "",
) -> None:
    """Append one audit row for a filing action (id-keyed form).

    Use this from background workers (e.g. the filing worker) that have
    only the integer ``user_id`` / ``client_id`` from the job row and do
    not need to load the ORM objects. Same PII/effort semantics as
    :func:`log_filing_action`.
    """
    _write_audit_row(
        db=db,
        user_id=user_id,
        client_id=client_id,
        assessment_year=assessment_year,
        itr_type=itr_type,
        action=action,
        outcome=outcome,
        itd_code=itd_code,
        message=message,
    )


def _write_audit_row(
    *,
    db: Session,
    user_id: int,
    client_id: int,
    assessment_year: str,
    itr_type: str,
    action: Action,
    outcome: Outcome,
    itd_code: Optional[str],
    message: str,
) -> None:
    """Best-effort single audit-row write (shared by both public helpers)."""
    mode, environment = _resolve_creds_descriptor()
    # Hard PII guard: cap the message so a payload dump can never fill the
    # log even if a caller accidentally passes more than a status string.
    safe_message = (message or "")[:1000]
    try:
        row = AuditLog(
            user_id=user_id,
            client_id=client_id,
            assessment_year=assessment_year,
            itr_type=itr_type,
            mode=mode,
            environment=environment,
            action=action,
            outcome=outcome,
            itd_code=itd_code,
            message=safe_message,
        )
        db.add(row)
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        # Best-effort: a failed audit write must not break filing.
        try:
            db.rollback()
        except Exception:
            pass
        _log.warning("Audit-log write failed for action=%s: %s", action, exc)
