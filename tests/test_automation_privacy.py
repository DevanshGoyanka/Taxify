"""Privacy regression tests for portal automation logs."""

from __future__ import annotations

import logging

from app.automation.pdf_unlocker import unlock_pdf
from app.automation.privacy import (
    AutomationPrivacyFilter,
    UvicornAccessPrivacyFilter,
    sanitize_automation_text,
)
from uvicorn.logging import AccessFormatter


def test_sanitize_automation_text_redacts_taxpayer_data() -> None:
    """PAN, UUID, DOB, and download paths must be removed from diagnostics."""
    raw = (
        "client 86aa1f54-6e9f-4a2a-a9fc-179127c60ea4 "
        "PAN ABCDE1234F DOB 1978-08-21 path "
        r"C:\Users\Example\Taxify\downloads\2\2025-26\ABCDE1234F-AIS.pdf"
    )

    sanitized = sanitize_automation_text(raw)

    assert "86aa1f54" not in sanitized
    assert "ABCDE1234F" not in sanitized
    assert "1978-08-21" not in sanitized
    assert r"C:\Users\Example" not in sanitized
    assert "<client-id>" in sanitized
    assert "<PAN>" in sanitized
    assert "<DOB>" in sanitized
    assert "<download-path>" in sanitized


def test_logging_filter_redacts_formatted_arguments() -> None:
    """The logger filter must sanitize values supplied through format args."""
    record = logging.LogRecord(
        name="taxify.automation.worker",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Client %s downloaded %s",
        args=(
            "ABCDE1234F",
            r"C:\Taxify\downloads\2\2025-26\ABCDE1234F-TIS.pdf",
        ),
        exc_info=None,
    )

    keep = AutomationPrivacyFilter().filter(record)

    assert keep is True
    assert record.args == ()
    assert "ABCDE1234F" not in str(record.msg)
    assert "<PAN>" in str(record.msg)
    assert "<download-path>" in str(record.msg)


def test_uvicorn_access_filter_preserves_formatter_arguments() -> None:
    """Uvicorn access formatting must remain valid after path redaction."""
    client_id = "86aa1f54-6e9f-4a2a-a9fc-179127c60ea4"
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "127.0.0.1:50132",
            "GET",
            f"/clients/{client_id}/itr/2026-27",
            "1.1",
            200,
        ),
        exc_info=None,
    )

    keep = UvicornAccessPrivacyFilter().filter(record)
    rendered = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s').format(record)

    assert keep is True
    assert isinstance(record.args, tuple)
    assert len(record.args) == 5
    assert client_id not in rendered
    assert "/clients/<client-id>/itr/2026-27" in rendered
    assert 'GET /clients/<client-id>/itr/2026-27 HTTP/1.1' in rendered
    assert rendered.endswith("200 OK")


def test_uvicorn_access_filter_leaves_unexpected_records_intact() -> None:
    """Nonstandard access records must not be mutated or crash formatting."""
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="plain access message",
        args=(),
        exc_info=None,
    )

    assert UvicornAccessPrivacyFilter().filter(record) is True
    assert record.msg == "plain access message"
    assert record.args == ()


def test_unlock_pdf_candidate_path_has_no_stale_diagnostic_name(
    tmp_path,
    monkeypatch,
) -> None:
    """Candidate diagnostics must not reference a removed masked variable."""
    pdf_path = tmp_path / "ABCDE1234F-TIS.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    class FakePdf:
        """Context-manager double for a successfully decrypted PDF."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> bool:
            del exc_type, exc, traceback
            return False

        def save(self, path: str) -> None:
            """Write a replacement PDF for the in-place unlock operation."""
            from pathlib import Path

            Path(path).write_bytes(b"%PDF-1.4\nunlocked")

    import pikepdf

    def fake_open(path: str, password: str | None = None) -> FakePdf:
        del path
        if password is None:
            raise pikepdf.PasswordError("encrypted")
        return FakePdf()

    monkeypatch.setattr(pikepdf, "open", fake_open)
    result = unlock_pdf(
        str(pdf_path),
        pan="ABCDE1234F",
        dob="1990-01-01",
        log=lambda _: None,
    )

    assert result["unlocked"] is True
