"""ERI Type-3 standalone acknowledgement downloader (Playwright).

Per the Dual-Mode ERI Integration Plan §A7, after a return is uploaded and
e-verified, the acknowledgement (ITR-V) PDF is downloadable from the ITD
portal's "View Filed Returns" page. This module is a STANDALONE downloader
that logs in as the taxpayer, navigates to View Filed Returns, locates the
row for a given acknowledgement number, and downloads the acknowledgement
PDF — without depending on (or touching) the working portal uploader in
``app/filing_automation/uploader.py``.

It reuses only the stable, proven automation primitives from
:mod:`app.automation`:
  - :class:`app.automation.browser.BrowserManager` (visible Chromium)
  - :func:`app.automation.auth.login_itd` / :func:`logout_itd` (taxpayer
    login via PAN + vault-decrypted portal password)
  - :func:`app.automation.navigation.navigate_income_tax_returns` and
    :func:`app.automation.navigation.dismiss_portal_modals`
  - :class:`app.automation.timing.AutomationTimeline` (credential-safe
    timing instrumentation)

The download selectors ("View Filed Returns" → row containing the ack
number → "Download Receipt"/"Download Acknowledgement" →
``page.expect_download``) mirror the proven path the uploader uses, so
the standalone downloader navigates the same portal UI that is already
known to work.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.automation.auth import LogCallback, login_itd, logout_itd
from app.automation.browser import browser_manager
from app.automation.navigation import (
    dismiss_portal_modals,
    navigate_income_tax_returns,
)
from app.automation.timing import AutomationTimeline
from app.schemas.security.portal_crypto import decrypt_portal_password

_log = logging.getLogger("taxify.eri.type3.ack_downloader")


@dataclass
class AcknowledgementDownloadResult:
    """Outcome of a standalone acknowledgement download attempt.

    Attributes:
        success: Whether the acknowledgement PDF was downloaded and saved.
        acknowledgement_number: The ARN used to locate the row.
        acknowledgement_path: Absolute path to the saved PDF, or None.
        error: A human-readable error message when ``success`` is False.
    """

    success: bool
    acknowledgement_number: str
    acknowledgement_path: Optional[str] = None
    error: Optional[str] = None


class AcknowledgementDownloadError(RuntimeError):
    """Raised when the acknowledgement PDF cannot be downloaded."""


async def _find_text_action(
    page: Any,
    names: tuple[str, ...],
    timeout_ms: int,
) -> Optional[Any]:
    """Locate the first visible button/link matching any of ``names``.

    Mirrors the proven ``_find_action`` heuristic from the uploader: a
    case-insensitive exact-text search across the common portal control
    surfaces (buttons, links, mat-card actions), returning the first
    visible match within ``timeout_ms``.
    """
    remaining = max(1, min(2_000, timeout_ms))
    for name in names:
        candidates = page.get_by_role("link", name=name, exact=False)
        if await candidates.count() > 0:
            first = candidates.first
            if await first.is_visible(timeout=remaining):
                return first
        button = page.get_by_role("button", name=name, exact=False)
        if await button.count() > 0:
            first = button.first
            if await first.is_visible(timeout=remaining):
                return first
    # Fallback: any element whose text matches (covers mat-card actions).
    for name in names:
        loc = page.get_by_text(name, exact=False).first
        try:
            if await loc.is_visible(timeout=remaining):
                return loc
        except Exception:
            continue
    return None


async def download_acknowledgement(
    *,
    pan: str,
    portal_password_cipher: str,
    acknowledgement_number: str,
    output_dir: str | Path,
    timeout_ms: int = 120_000,
    log_callback: Optional[LogCallback] = None,
    interactive: bool = True,
) -> AcknowledgementDownloadResult:
    """Download the acknowledgement (ITR-V) PDF for a filed return.

    Standalone flow (no uploader dependency):

      1. Decrypt the client's portal password (vault AES-256-GCM).
      2. Launch a visible Chromium context via ``browser_manager``.
      3. Log in as the taxpayer (PAN + portal password) via ``login_itd``.
      4. Navigate to e-File → Income Tax Return → View Filed Returns.
      5. Locate the row whose text contains the acknowledgement number.
      6. Click the row's "Download Receipt" / "Download Acknowledgement"
         control and capture the browser download.
      7. Save the PDF to ``output_dir`` and return the path.

    Args:
        pan: The taxpayer's PAN (portal user id).
        portal_password_cipher: The encrypted portal password ciphertext
            stored on ``Client.portal_password``.
        acknowledgement_number: The ARN of the filed return to download.
        output_dir: Directory to save the acknowledgement PDF into.
        timeout_ms: Overall wall-clock deadline for the download attempt.
        log_callback: Optional progress callback (operator-visible log).
        interactive: Whether to show the browser window (default True —
            the operator must be able to intervene on unexpected prompts).

    Returns:
        An :class:`AcknowledgementDownloadResult` with the saved PDF path
        on success, or an error message on failure.
    """

    def _emit(message: str) -> None:
        if log_callback is not None:
            try:
                log_callback(message)
            except Exception:  # pragma: no cover - defensive
                pass

    start = time.monotonic()

    def _remaining() -> int:
        return max(0, timeout_ms - int((time.monotonic() - start) * 1000))

    try:
        portal_password = decrypt_portal_password(portal_password_cipher)
    except Exception as exc:
        raise AcknowledgementDownloadError(
            f"Could not decrypt the client's portal password: {exc}"
        ) from exc

    timeline = AutomationTimeline(_emit)

    _emit("[ACK] Launching browser context for acknowledgement download.")
    context = await browser_manager.get_context(
        log_callback=_emit,
        interactive=interactive,
        timeline=timeline,
    )
    page: Optional[Any] = None
    try:
        _emit("[ACK] Logging in as the taxpayer.")
        page = await login_itd(
            user_id=pan,
            password=portal_password,
            log_callback=_emit,
            context=context,
            timeline=timeline,
        )
        # Portal modals (tour/cookies) can appear over the navigation.
        await dismiss_portal_modals(page, log=_emit)

        _emit("[ACK] Navigating to View Filed Returns.")
        await navigate_income_tax_returns(
            page,
            timeout_ms=max(1, _remaining()),
            log=_emit,
        )
        view = await _find_text_action(
            page, ("View Filed Returns",), _remaining()
        )
        if view is None:
            raise AcknowledgementDownloadError(
                "Could not locate the 'View Filed Returns' action on the "
                "portal dashboard."
            )
        await view.click(timeout=max(1, min(2_000, _remaining())))

        _emit(f"[ACK] Locating the row for ARN {acknowledgement_number}.")
        row = page.get_by_text(acknowledgement_number, exact=False).first
        try:
            card = row.locator(
                "xpath=ancestor::*[self::mat-card or @role='row'][1]"
            )
            receipt = card.get_by_text(
                re.compile(r"Download\s+(?:Receipt|Acknowledgement)", re.I)
            ).first
            if not await receipt.is_visible(timeout=2_000):
                receipt = await _find_text_action(
                    page,
                    ("Download Receipt", "Download Acknowledgement"),
                    _remaining(),
                )
        except Exception:
            receipt = await _find_text_action(
                page,
                ("Download Receipt", "Download Acknowledgement"),
                _remaining(),
            )
        if receipt is None:
            raise AcknowledgementDownloadError(
                "Could not locate the acknowledgement download control for "
                f"ARN {acknowledgement_number}. The return may not yet be "
                "acknowledged on the portal."
            )

        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        final_path = destination / "ITR-Acknowledgement.pdf"

        _emit("[ACK] Downloading the acknowledgement PDF.")
        remaining_for_download = max(1, _remaining())
        async with page.expect_download(
            timeout=remaining_for_download
        ) as info:
            await receipt.click(timeout=max(1, min(2_000, remaining_for_download)))
        download = await info.value
        await download.save_as(str(final_path))

        if not final_path.exists() or final_path.stat().st_size == 0:
            final_path.unlink(missing_ok=True)
            raise AcknowledgementDownloadError(
                "The portal produced an empty acknowledgement download."
            )

        _emit(f"[ACK] Acknowledgement receipt saved to {final_path}.")
        return AcknowledgementDownloadResult(
            success=True,
            acknowledgement_number=acknowledgement_number,
            acknowledgement_path=str(final_path),
        )
    except AcknowledgementDownloadError as exc:
        _emit(f"[ACK] Download failed: {exc}")
        return AcknowledgementDownloadResult(
            success=False,
            acknowledgement_number=acknowledgement_number,
            error=str(exc),
        )
    except Exception as exc:
        _emit(f"[ACK] Unexpected download failure: {exc}")
        return AcknowledgementDownloadResult(
            success=False,
            acknowledgement_number=acknowledgement_number,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        # Best-effort logout; the context is owned by browser_manager and
        # is recycled by its own lifecycle.
        if page is not None:
            try:
                await logout_itd(page, _emit, timeline=timeline)
            except Exception:  # pragma: no cover - defensive
                pass
