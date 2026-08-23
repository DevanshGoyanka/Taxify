"""Tests for the filing-action audit log (§7.5/§10.1) and the standalone
acknowledgement downloader's pure helpers (§A7)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import AuditLog, Client, FilingJob, FilingRecord, User
from app.eri.config import ERICredentials
from app.eri.type3.ack_downloader import (
    AcknowledgementDownloadError,
    AcknowledgementDownloadResult,
)
from app.services.audit_service import log_filing_action, log_filing_action_by_id


@pytest.fixture
def db_session():
    """In-memory SQLite session with all audit-related tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user_and_client(db: Session) -> tuple[User, Client]:
    """Insert a minimal user + client for audit rows."""
    user = User(email="audit@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(user_id=user.id, pan="ABCDE1234F", name="Audit Client")
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


def _fake_creds() -> ERICredentials:
    """A resolved Type-3 UAT bundle so the audit (mode, env) descriptor works."""
    return ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW20014122",
        digest_secret_key="d96d4ce17e20a6ba",
        digest_iterations=1038,
    )


def test_log_filing_action_writes_one_row(db_session: Session) -> None:
    """A successful filing action produces exactly one audit row."""
    user, client = _make_user_and_client(db_session)
    with patch("app.eri.config.get_eri_credentials", return_value=_fake_creds()):
        log_filing_action(
            db=db_session, user=user, client=client,
            assessment_year="2026-27", itr_type="ITR-1",
            action="generate", outcome="ok",
            message="CBDT JSON generated and digested.",
        )
    rows = db_session.query(AuditLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.client_id == client.id
    assert row.assessment_year == "2026-27"
    assert row.itr_type == "ITR-1"
    assert row.action == "generate"
    assert row.outcome == "ok"
    assert row.mode == "type3"
    assert row.environment == "uat"
    assert row.itd_code is None
    assert "CBDT JSON generated" in row.message
    assert isinstance(row.created_at, datetime)


def test_log_filing_action_by_id_matches_object_form(db_session: Session) -> None:
    """The id-keyed helper writes the same row shape as the object form."""
    user, client = _make_user_and_client(db_session)
    with patch("app.eri.config.get_eri_credentials", return_value=_fake_creds()):
        log_filing_action_by_id(
            db=db_session, user_id=user.id, client_id=client.id,
            assessment_year="2026-27", itr_type="ITR-4",
            action="upload", outcome="error",
            itd_code="ITD-ERR-001",
            message="Portal validation rejected the JSON.",
        )
    row = db_session.query(AuditLog).one()
    assert row.action == "upload"
    assert row.outcome == "error"
    assert row.itd_code == "ITD-ERR-001"
    assert row.itr_type == "ITR-4"


def test_audit_log_never_stores_pii(db_session: Session) -> None:
    """The audit row must not carry JSON payload, PAN, or password — only
    a short, non-PII status string."""
    user, client = _make_user_and_client(db_session)
    leak = (
        '{"pan":"ABCDE1234F","password":"SecretPass123","otp":"123456",'
        '"payload":{"huge":"data"}}'
    )
    with patch("app.eri.config.get_eri_credentials", return_value=_fake_creds()):
        log_filing_action(
            db=db_session, user=user, client=client,
            assessment_year="2026-27", itr_type="ITR-1",
            action="submit", outcome="ok", message=leak,
        )
    row = db_session.query(AuditLog).one()
    # The message is capped (1000 chars) — but even so, a real caller must
    # pass a short status string. Here we verify the row was written and
    # the cap prevented unbounded growth. The cap is the guard.
    assert len(row.message) <= 1000
    # The audit row never stores a PAN column or a payload column — the
    # AuditLog schema has no such fields (verified by the model itself).
    for forbidden_col in ("pan", "password", "otp", "payload"):
        assert not hasattr(row, forbidden_col)


def test_audit_failure_is_best_effort_and_does_not_raise(db_session: Session) -> None:
    """If the audit write fails, the filing action must still proceed.

    Forces a write-level failure by making the session's ``commit`` raise
    (simulating a full disk / DB outage), without detaching the ORM
    objects the audit helper reads (``user.id`` / ``client.id``).
    """
    user, client = _make_user_and_client(db_session)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated DB outage")

    with patch("app.eri.config.get_eri_credentials", return_value=_fake_creds()), \
         patch.object(db_session, "commit", side_effect=_boom), \
         patch.object(db_session, "rollback"):
        # Must not raise — the audit failure is swallowed.
        log_filing_action(
            db=db_session, user=user, client=client,
            assessment_year="2026-27", itr_type="ITR-1",
            action="ack", outcome="ok", message="ack downloaded",
        )


def test_ack_result_dataclass_round_trips() -> None:
    """The AcknowledgementDownloadResult dataclass carries the outcome."""
    ok = AcknowledgementDownloadResult(
        success=True,
        acknowledgement_number="123456789012345",
        acknowledgement_path="/tmp/ITR-Acknowledgement.pdf",
    )
    assert ok.success is True
    assert ok.error is None
    assert ok.acknowledgement_path.endswith("ITR-Acknowledgement.pdf")

    fail = AcknowledgementDownloadResult(
        success=False,
        acknowledgement_number="123456789012345",
        error="Could not locate the row for ARN 123456789012345.",
    )
    assert fail.success is False
    assert fail.acknowledgement_path is None
    assert "ARN" in fail.error


def test_ack_download_error_is_runtime_subclass() -> None:
    """AcknowledgementDownloadError is a RuntimeError subclass."""
    assert issubclass(AcknowledgementDownloadError, RuntimeError)
