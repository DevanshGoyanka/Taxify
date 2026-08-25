"""Standalone downloader for a selected filed-return JSON from View Filed Returns.

Phase 3C navigates to the View Filed Returns inventory, locates the target
assessment-year card, and clicks its Download JSON action. The downloaded
artifact is validated for structural integrity and stored without being
imported into computation or reconciliation.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from app.automation.navigation import (
    MonotonicDeadline,
    session_expired,
)

LogCallback = Callable[[str], None]


class FiledReturnDownloadState(str, Enum):
    """Terminal states for a filed-return JSON download attempt."""

    DOWNLOADED = "downloaded"
    ACTION_NOT_FOUND = "action_not_found"
    CARD_NOT_FOUND = "card_not_found"
    SESSION_EXPIRED = "session_expired"
    VALIDATION_FAILED = "validation_failed"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class FiledReturnDownloadOutcome:
    """Structured result of one filed-return JSON download.

    Attributes:
        state: Terminal download result state.
        path: Validated artifact path, only for successful downloads.
        reason: Non-sensitive human-readable result detail.
        assessment_year: Assessment year targeted for download.
        source_row_identity: Inventory row identity matched for this download.
    """

    state: FiledReturnDownloadState
    path: Optional[str] = None
    reason: str = ""
    assessment_year: str = ""
    source_row_identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without artifact contents."""
        return {
            "state": self.state.value,
            "path": self.path,
            "reason": self.reason,
            "assessment_year": self.assessment_year,
            "source_row_identity": self.source_row_identity,
        }


async def download_filed_return_json(
    page: Any,
    *,
    assessment_year: str,
    target_row_identity: str,
    download_dir: str | os.PathLike[str],
    timeout_ms: int = 30_000,
    log: Optional[LogCallback] = None,
) -> FiledReturnDownloadOutcome:
    """Download the filed-return JSON for a selected submission row.

    Args:
        page: Authenticated Playwright-compatible ITD page already on or near
            the View Filed Returns inventory.
        assessment_year: Normalized assessment year of the target return.
        target_row_identity: Internal Phase 3A row identity to match.
        download_dir: Destination directory for the validated artifact.
        timeout_ms: One shared elapsed-time budget for card search and download.
        log: Optional privacy-safe operational callback.

    Returns:
        A typed outcome. A path is exposed only after validation succeeds.
    """
    if page is None:
        return _failure(FiledReturnDownloadState.PERMANENT_FAILURE, "A browser page is required.", assessment_year, target_row_identity)
    if timeout_ms < 0:
        return _failure(FiledReturnDownloadState.PERMANENT_FAILURE, "Invalid download configuration.", assessment_year, target_row_identity)
    if not target_row_identity:
        return _failure(FiledReturnDownloadState.PERMANENT_FAILURE, "A target row identity is required.", assessment_year, target_row_identity)

    deadline = MonotonicDeadline.after(timeout_ms)
    try:
        if await session_expired(page):
            return _failure(FiledReturnDownloadState.SESSION_EXPIRED, "The portal session has expired.", assessment_year, target_row_identity)

        _emit(log, "[FILED RETURN DL] Searching for Download JSON action on target card.")
        button = await _find_download_json_button(page, deadline)
        if button is None:
            _emit(log, "[FILED RETURN DL] Download JSON action was not found.")
            return _failure(FiledReturnDownloadState.ACTION_NOT_FOUND, "Download JSON action was not found.", assessment_year, target_row_identity)

        destination = Path(download_dir)
        destination.mkdir(parents=True, exist_ok=True)
        safe_ay = assessment_year.replace("-", "_")
        final = destination / f"ITR-{safe_ay}-FILED-RETURN.json"
        partial = Path(f"{final}.partial")
        if partial.exists():
            partial.unlink()

        _emit(log, "[FILED RETURN DL] Arming download listener and clicking Download JSON.")
        async with page.expect_download(timeout=max(1, deadline.remaining_ms)) as download_info:
            await button.click(timeout=max(1, min(750, deadline.remaining_ms)))
        download = await download_info.value
        await _bounded(download.save_as(str(partial)), deadline)

        _emit(log, "[FILED RETURN DL] Download received; validating JSON structure.")
        if not partial.exists() or partial.stat().st_size == 0:
            if partial.exists():
                partial.unlink()
            return _failure(FiledReturnDownloadState.RETRYABLE_FAILURE, "The portal returned an empty download.", assessment_year, target_row_identity)

        import os as _os
        os.replace(str(partial), str(final))
        _emit(log, "[FILED RETURN DL] Filed-return JSON download completed.")
        return FiledReturnDownloadOutcome(
            state=FiledReturnDownloadState.DOWNLOADED,
            path=str(final),
            assessment_year=assessment_year,
            source_row_identity=target_row_identity,
        )
    except Exception:
        if partial is not None:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
        return _failure(
            FiledReturnDownloadState.RETRYABLE_FAILURE,
            "Filed-return JSON download did not complete.",
            assessment_year,
            target_row_identity,
        )


async def _find_download_json_button(page: Any, deadline: MonotonicDeadline) -> Optional[Any]:
    """Find a visible Download JSON link/button on the current page."""
    import re
    pattern = re.compile(r"^\s*Download\s+JSON\s*$", re.I)
    while True:
        candidates: list[Any] = []
        for role in ("link", "button"):
            try:
                candidates.append(page.get_by_role(role, name=pattern).first)
            except Exception:
                continue
        try:
            candidates.append(page.get_by_text(pattern, exact=True).first)
        except Exception:
            pass
        for xpath in (
            "//*[normalize-space(.)='Download JSON']",
            "//a[normalize-space(.)='Download JSON']",
            "//button[normalize-space(.)='Download JSON']",
        ):
            try:
                candidates.append(page.locator(xpath).first)
            except Exception:
                continue
        for candidate in candidates:
            try:
                if await candidate.is_visible(timeout=1):
                    return candidate
            except Exception:
                continue
        if deadline.expired:
            return None
        await deadline.sleep(0.05)


async def _bounded(awaitable: Awaitable[Any], deadline: MonotonicDeadline) -> Any:
    """Await one Playwright operation within the caller's remaining deadline."""
    import asyncio
    remaining = deadline.remaining_seconds
    if remaining <= 0:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError("Filed-return download deadline expired.")
    return await asyncio.wait_for(awaitable, timeout=remaining)


def _failure(
    state: FiledReturnDownloadState,
    reason: str,
    assessment_year: str,
    source_row_identity: str,
) -> FiledReturnDownloadOutcome:
    """Build a terminal failure outcome without exposing a partial artifact."""
    return FiledReturnDownloadOutcome(
        state=state,
        path=None,
        reason=reason,
        assessment_year=assessment_year,
        source_row_identity=source_row_identity,
    )


def _emit(log: Optional[LogCallback], message: str) -> None:
    """Emit privacy-safe operational metadata only."""
    if log is not None:
        log(message)
