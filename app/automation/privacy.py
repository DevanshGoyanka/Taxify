"""Privacy safeguards for portal automation diagnostics."""

from __future__ import annotations

import logging
import re

_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_DOB_PATTERN = re.compile(r"\b(?:19|20)[0-9]{2}[-/]\d{1,2}[-/]\d{1,2}\b")
_DOWNLOAD_PATH_PATTERN = re.compile(
    r"[A-Za-z]:\\[^\r\n,;]*?\\downloads\\[^\s,'\"}\]]+",
    re.IGNORECASE,
)


def sanitize_automation_text(value: object) -> str:
    """Redact taxpayer identifiers and local artifact paths from diagnostics.

    Args:
        value: Arbitrary value about to be persisted or written to a log.

    Returns:
        A string with PANs, public client UUIDs, full DOBs, and download paths
        replaced by stable non-sensitive labels.
    """
    text = str(value)
    text = _DOWNLOAD_PATH_PATTERN.sub("<download-path>", text)
    text = _PAN_PATTERN.sub("<PAN>", text)
    text = _UUID_PATTERN.sub("<client-id>", text)
    text = _DOB_PATTERN.sub("<DOB>", text)
    return text


class AutomationPrivacyFilter(logging.Filter):
    """Redact sensitive automation data from a Python logging record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize the rendered message and keep the record.

        Args:
            record: Logging record to sanitize in place.

        Returns:
            Always ``True`` so the sanitized record is emitted.
        """
        record.msg = sanitize_automation_text(record.getMessage())
        record.args = ()
        return True


class UvicornAccessPrivacyFilter(logging.Filter):
    """Sanitize Uvicorn request paths without breaking AccessFormatter args."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the raw path while preserving Uvicorn's five arguments.

        Uvicorn's ``AccessFormatter`` requires ``record.args`` to remain the
        tuple ``(client_addr, method, full_path, http_version, status_code)``.

        Args:
            record: Uvicorn access logging record.

        Returns:
            Always ``True`` so the sanitized record is emitted.
        """
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client_addr, method, full_path, http_version, status_code = record.args
            record.args = (
                client_addr,
                method,
                sanitize_automation_text(full_path),
                http_version,
                status_code,
            )
        return True


def install_automation_privacy_filter(logger: logging.Logger) -> None:
    """Install one privacy filter on an automation logger.

    Args:
        logger: Logger that may receive taxpayer-related diagnostics.
    """
    if not any(isinstance(item, AutomationPrivacyFilter) for item in logger.filters):
        logger.addFilter(AutomationPrivacyFilter())


def install_uvicorn_access_privacy_filter(logger: logging.Logger) -> None:
    """Install the structure-preserving filter on Uvicorn's access logger.

    Args:
        logger: The ``uvicorn.access`` logger.
    """
    if not any(isinstance(item, UvicornAccessPrivacyFilter) for item in logger.filters):
        logger.addFilter(UvicornAccessPrivacyFilter())
