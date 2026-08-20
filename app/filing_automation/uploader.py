"""Playwright primitives for ERI Type-3 ITR upload and post-filing actions."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
import asyncio

from app.automation.navigation import (
    MonotonicDeadline,
    dismiss_portal_modals,
    navigate_income_tax_returns,
    session_expired,
    wait_for_overlay_clearance,
)

LogCallback = Callable[[str], None]
OtpCallback = Callable[[str], str | Awaitable[str]]

_otp_waiters: dict[int, asyncio.Future[str]] = {}


async def wait_for_job_otp(job_id: int, prompt: str, timeout_seconds: int = 300) -> str:
    """Wait in memory for an OTP/EVC supplied to a running filing job."""
    del prompt
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    old = _otp_waiters.pop(job_id, None)
    if old is not None and not old.done():
        old.cancel()
    _otp_waiters[job_id] = future
    try:
        return await asyncio.wait_for(future, timeout=timeout_seconds)
    finally:
        _otp_waiters.pop(job_id, None)


def provide_job_otp(job_id: int, otp: str) -> bool:
    """Deliver an OTP/EVC to a waiting job without persisting or logging it."""
    future = _otp_waiters.get(job_id)
    if future is None or future.done():
        return False
    future.set_result(otp)
    return True


def job_is_awaiting_otp(job_id: int) -> bool:
    """Return whether a running filing job currently awaits user input."""
    future = _otp_waiters.get(job_id)
    return future is not None and not future.done()


class PortalUploadState(str, Enum):
    """Terminal states for one portal upload attempt."""

    SUBMITTED = "submitted"
    VALIDATION_FAILED = "validation_failed"
    SESSION_EXPIRED = "session_expired"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


class DisabledRouteError(RuntimeError):
    """Raised when the portal renders a navigation link as disabled.

    After a rate-limit recovery (Max-attempts popup → Login Here), the ITD
    portal places the session in a restricted state where filing actions are
    disabled (class="disabledRoute", aria-label="...unavailable"). Retrying
    with the same session cannot succeed — the session must be cleared and
    a fresh login performed.
    """


@dataclass(frozen=True, slots=True)
class PortalUploadOutcome:
    """Privacy-aware result of an ITR portal upload."""

    state: PortalUploadState
    acknowledgement_number: Optional[str] = None
    everify_status: Optional[str] = None
    acknowledgement_path: Optional[str] = None
    reason: str = ""

    @property
    def succeeded(self) -> bool:
        return self.state is PortalUploadState.SUBMITTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "acknowledgement_number": self.acknowledgement_number,
            "everify_status": self.everify_status,
            "acknowledgement_path": self.acknowledgement_path,
            "reason": self.reason,
        }


class PortalUploader:
    """Upload a locally generated CBDT JSON through an authenticated ITD page."""

    async def upload(
        self,
        page: Any,
        *,
        assessment_year: str,
        itr_type: str,
        json_path: str | Path,
        verification_mode: str = "LATER",
        otp_callback: Optional[OtpCallback] = None,
        acknowledgement_dir: str | Path | None = None,
        timeout_ms: int = 180_000,
        log: Optional[LogCallback] = None,
    ) -> PortalUploadOutcome:
        """Navigate, upload, submit, optionally e-verify, and download receipt."""
        path = Path(json_path)
        if not path.is_file() or path.suffix.lower() != ".json":
            return self._failure(
                PortalUploadState.PERMANENT_FAILURE,
                "The generated filing JSON is missing or invalid.",
            )
        if timeout_ms <= 0:
            return self._failure(
                PortalUploadState.PERMANENT_FAILURE,
                "Invalid portal upload timeout.",
            )

        deadline = MonotonicDeadline.after(timeout_ms)
        try:
            if await session_expired(page):
                return self._failure(
                    PortalUploadState.SESSION_EXPIRED,
                    "The ITD portal session has expired.",
                )
            _emit(log, "[ITR UPLOAD] Opening File Income Tax Return.")
            await self.goto_file_itr_page(
                page,
                assessment_year=assessment_year,
                itr_type=itr_type,
                deadline=deadline,
                log=log,
            )
            await self._upload_file(page, path, deadline)
            portal_error = await self._visible_portal_error(page)
            if portal_error:
                return self._failure(
                    PortalUploadState.VALIDATION_FAILED,
                    portal_error,
                )

            _emit(log, "[ITR UPLOAD] Local artifact accepted; submitting return.")
            await self._submit_and_confirm(page, deadline)
            portal_error = await self._visible_portal_error(page)
            if portal_error:
                return self._failure(
                    PortalUploadState.VALIDATION_FAILED,
                    portal_error,
                )

            acknowledgement = await self._extract_acknowledgement(page, deadline)
            if not acknowledgement:
                return self._failure(
                    PortalUploadState.RETRYABLE_FAILURE,
                    "The portal did not display an acknowledgement number after submission.",
                )

            everify = await self.everify_on_portal(
                page,
                mode=verification_mode,
                otp_callback=otp_callback,
                deadline=deadline,
                log=log,
            )
            acknowledgement_path: Optional[str] = None
            if acknowledgement_dir is not None and everify == "verified":
                acknowledgement_path = await self.download_acknowledgement(
                    page,
                    acknowledgement=acknowledgement,
                    output_dir=acknowledgement_dir,
                    deadline=deadline,
                    log=log,
                )
            _emit(log, "[ITR UPLOAD] Filing workflow completed.")
            return PortalUploadOutcome(
                state=PortalUploadState.SUBMITTED,
                acknowledgement_number=acknowledgement,
                everify_status=everify,
                acknowledgement_path=acknowledgement_path,
            )
        except DisabledRouteError as exc:
            _emit(
                log,
                f"[ITR UPLOAD] Session restricted: {exc}",
            )
            return self._failure(
                PortalUploadState.SESSION_EXPIRED,
                str(exc),
            )
        except Exception as exc:
            _emit(
                log,
                f"[ITR UPLOAD] Filing failed at step: "
                f"{type(exc).__name__}: {exc}",
            )
            return self._failure(
                PortalUploadState.RETRYABLE_FAILURE,
                f"Portal filing did not complete ({type(exc).__name__}).",
            )

    async def goto_file_itr_page(
        self,
        page: Any,
        *,
        assessment_year: str,
        itr_type: str,
        deadline: MonotonicDeadline,
        log: Optional[LogCallback] = None,
    ) -> None:
        """Open the portal's offline JSON upload workflow.

        Uses direct URL navigation to the File ITR page
        (``#/dashboard/fileIncomeTaxReturn``) instead of menu hover/click
        navigation. This avoids the anti-automation protection that was
        triggering session restrictions. Also dismisses portal security
        modals (logout confirmation, security popups) at each step.

        Pattern ported from the NRITAX portal-fetch service.
        """
        import asyncio as _asyncio

        # Step 1: Dismiss any portal modals (logout/security popups) that
        # may have appeared after login.
        await dismiss_portal_modals(page, log=log)

        # Step 2: Navigate directly to the File ITR page URL.
        # This bypasses the e-File → Income Tax Returns menu navigation
        # that was triggering the portal's anti-automation protection.
        _emit(log, "[ITR UPLOAD] Navigating directly to File ITR page URL.")
        try:
            await page.goto(
                "https://eportal.incometax.gov.in/iec/foservices/#/dashboard/fileIncomeTaxReturn",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception as exc:
            _emit(log, f"[ITR UPLOAD] Direct navigation failed: {exc}")
            # Fallback: try menu navigation
            _emit(log, "[ITR UPLOAD] Falling back to e-File menu navigation.")
            await navigate_income_tax_returns(
                page,
                timeout_ms=max(1, deadline.remaining_ms),
                log=log,
            )

        # Step 3: Wait for the page to settle and dismiss any modals that
        # appeared during navigation.
        await _asyncio.sleep(2.0)
        await dismiss_portal_modals(page, log=log)

        # Step 4: Verify we're on the File ITR page by checking for the
        # Assessment Year mat-select control.
        _emit(log, "[ITR UPLOAD] Checking for Assessment Year control.")
        ay_visible = False
        try:
            ay_control = page.get_by_label(
                re.compile(re.escape("Assessment Year"), re.I)
            ).first
            ay_visible = await ay_control.is_visible(timeout=3_000)
        except Exception:
            ay_visible = False

        if not ay_visible:
            # Try the mat-select pattern used by the ITD portal
            try:
                mat_select = page.locator(
                    "mat-select.mat-mdc-select-required, "
                    "mat-select#filterStyleForChip, "
                    "mat-select:not(#langMatSelect)"
                ).first
                ay_visible = await mat_select.is_visible(timeout=2_000)
            except Exception:
                pass

        if not ay_visible:
            # Final fallback: try menu navigation
            _emit(log, "[ITR UPLOAD] AY control not visible; trying e-File menu navigation.")
            await navigate_income_tax_returns(
                page,
                timeout_ms=max(1, deadline.remaining_ms),
                log=log,
            )
            await _asyncio.sleep(1.0)
            await dismiss_portal_modals(page, log=log)

        _emit(log, "[ITR UPLOAD] On File ITR page; selecting Assessment Year.")
        # AY is dropdown #0. Use the mat-select pattern directly.
        await _select_mat_option(page, assessment_year, index=0, log=log)
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(1.0)  # NRITAX: waitForTimeout(1000)

        # Select "Offline" mode FIRST (before Continue) — NRITAX pattern.
        _emit(log, "[ITR UPLOAD] Selecting Offline mode.")
        await _click_text_option(page, re.compile(r"offline", re.I))
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)  # NRITAX: waitForTimeout(400)

        # Now click Continue — it should be enabled after Offline is selected.
        _emit(log, "[ITR UPLOAD] Clicking Continue after Offline.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|let'?s get started|next", re.I),
            "button",
            4_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.5)  # NRITAX: waitForTimeout(500)

        # Select Filing Type: "139(1)" from the Filing Type dropdown (#1).
        # The portal auto-detects Individual taxpayer — we never select it.
        _emit(log, "[ITR UPLOAD] Selecting Filing Type: 139(1).")
        await _select_mat_option(page, r"139\s*\(1\)", index=1, log=log)
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        _emit(log, "[ITR UPLOAD] Clicking Continue after Filing Type.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|next", re.I),
            "button",
            3_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        # Answer "No" to 44AB audit question (ITR-1 standard).
        _emit(log, "[ITR UPLOAD] Answering 44AB audit question (No).")
        await _answer_yes_no(
            page,
            re.compile(r"audited u\/?s\s*44AB|political party as per section 13A", re.I),
            False,
        )
        await dismiss_portal_modals(page, log=log)

        # Select ITR form type from the ITR Form dropdown (#2).
        _emit(log, f"[ITR UPLOAD] Selecting ITR form type: {itr_type}.")
        await _select_mat_option(page, itr_type, index=2, log=log)
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        _emit(log, "[ITR UPLOAD] Clicking Continue after ITR form type.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|next|start", re.I),
            "button",
            4_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        # Answer "No" to PEP (Politically Exposed Person) question.
        _emit(log, "[ITR UPLOAD] Answering PEP question (No).")
        await _answer_yes_no(
            page,
            re.compile(r"politically exposed|political(ly)? exposed person|\bpep\b", re.I),
            False,
        )
        await dismiss_portal_modals(page, log=log)

        _emit(log, "[ITR UPLOAD] Clicking Continue after PEP.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|next|ok|submit", re.I),
            "button",
            4_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        # NRITAX pattern: click "Download pre-fill" / "Prefill" button
        # then "Download pre-fill" link, then "Offline/JSON submission/Upload JSON"
        _emit(log, "[ITR UPLOAD] Clicking Download Pre-fill / Prefill button.")
        await _click_if_visible(
            page,
            re.compile(
                r"download pre-?fill|download prefill|pre-?fill(ed)? (data|json)|get pre-?fill|prefill and",
                re.I,
            ),
            "button",
            6_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        _emit(log, "[ITR UPLOAD] Clicking Download Pre-fill link.")
        await _click_if_visible(
            page,
            re.compile(r"download pre-?fill|download prefill|pre-?fill(ed)? (data|json)", re.I),
            "link",
            4_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        # Click "Offline / JSON submission / Upload JSON" to reach the
        # file upload step.
        _emit(log, "[ITR UPLOAD] Clicking Offline/JSON submission/Upload JSON.")
        await _click_if_visible(
            page,
            re.compile(r"offline|json submission|upload json", re.I),
            "link",
            3_000,
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(1.0)

    async def _upload_file(
        self,
        page: Any,
        json_path: Path,
        deadline: MonotonicDeadline,
    ) -> None:
        await dismiss_portal_modals(page)
        # Wait for the file input to appear — the portal may need a moment
        # to render the upload panel after the wizard completes.
        import asyncio as _asyncio
        locator = page.locator("input[type='file']").first
        # Try to find the file input with a generous timeout (up to 10s)
        # but don't hang forever.
        file_input_found = False
        for _ in range(20):  # 20 × 500ms = 10s max
            try:
                if await locator.is_visible(timeout=500):
                    file_input_found = True
                    break
            except Exception:
                pass
            await dismiss_portal_modals(page)
            await _asyncio.sleep(0.5)
        if not file_input_found:
            raise RuntimeError("ITR JSON file input was not found.")
        await locator.set_input_files(
            str(json_path.resolve()),
            timeout=max(1, min(10_000, deadline.remaining_ms)),
        )
        await _click_optional(page, ("Upload", "Proceed", "Continue"), deadline)
        await dismiss_portal_modals(page)

    async def _submit_and_confirm(
        self,
        page: Any,
        deadline: MonotonicDeadline,
    ) -> None:
        await dismiss_portal_modals(page)
        submit = await _find_action(
            page,
            ("Submit Return", "Submit ITR", "Submit"),
            deadline,
        )
        if submit is None:
            raise RuntimeError("Final ITR submit action was not found.")
        await submit.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        await dismiss_portal_modals(page)
        confirm = await _find_action(
            page,
            ("Confirm", "Yes, Submit", "Submit"),
            deadline,
            timeout_cap_ms=8_000,
        )
        if confirm is not None:
            await confirm.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
            await dismiss_portal_modals(page)

    async def _extract_acknowledgement(
        self,
        page: Any,
        deadline: MonotonicDeadline,
    ) -> Optional[str]:
        pattern = re.compile(
            r"(?:Acknowledg(?:e)?ment|Receipt|ARN)(?:\s+No\.?)?\s*[:\-]?\s*([A-Z0-9]{12,30})",
            re.IGNORECASE,
        )
        while not deadline.expired:
            body = await page.locator("body").inner_text(
                timeout=max(1, min(2_000, deadline.remaining_ms))
            )
            match = pattern.search(body or "")
            if match:
                return match.group(1)
            await deadline.sleep(0.25)
        return None

    async def everify_on_portal(
        self,
        page: Any,
        *,
        mode: str,
        otp_callback: Optional[OtpCallback],
        deadline: MonotonicDeadline,
        log: Optional[LogCallback] = None,
    ) -> str:
        """Complete a supported e-verification choice without persisting OTP."""
        normalized = mode.strip().upper().replace("-", "_")
        if normalized in {"LATER", "VERIFY_LATER"}:
            later = await _find_action(
                page,
                ("Verify Later", "e-Verify Later"),
                deadline,
                timeout_cap_ms=5_000,
            )
            if later is not None:
                await later.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
                await _click_optional(page, ("Continue", "Confirm"), deadline)
            _emit(log, "[E-VERIFY] Return submitted with verification pending.")
            return "pending"

        if normalized not in {"AADHAAR", "AADHAAR_OTP", "BANK_EVC"}:
            raise ValueError(f"Unsupported e-verification mode: {mode}.")
        if otp_callback is None:
            raise RuntimeError("An OTP callback is required for this e-verification mode.")

        option_names = (
            ("Aadhaar OTP", "OTP on mobile number registered with Aadhaar")
            if normalized in {"AADHAAR", "AADHAAR_OTP"}
            else ("Bank EVC", "EVC through Bank Account")
        )
        option = await _find_action(page, option_names, deadline)
        if option is None:
            raise RuntimeError("Requested e-verification option was not found.")
        await option.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        generate = await _find_action(
            page,
            ("Generate OTP", "Generate EVC", "Continue"),
            deadline,
        )
        if generate is None:
            raise RuntimeError("OTP/EVC generation action was not found.")
        await generate.click(timeout=max(1, min(2_000, deadline.remaining_ms)))

        prompt = "Enter Aadhaar OTP" if normalized != "BANK_EVC" else "Enter Bank EVC"
        otp = otp_callback(prompt)
        if inspect.isawaitable(otp):
            otp = await otp
        otp = str(otp).strip()
        if not re.fullmatch(r"[A-Za-z0-9]{4,12}", otp):
            raise ValueError("The supplied OTP/EVC has an invalid format.")
        otp_input = page.locator(
            "input[autocomplete='one-time-code'], input[name*='otp' i], "
            "input[id*='otp' i], input[name*='evc' i]"
        ).first
        await otp_input.fill(otp, timeout=max(1, min(5_000, deadline.remaining_ms)))
        submit = await _find_action(
            page,
            ("Verify", "Submit OTP", "Submit EVC", "Continue"),
            deadline,
        )
        if submit is None:
            raise RuntimeError("E-verification submit action was not found.")
        await submit.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        _emit(log, "[E-VERIFY] E-verification completed.")
        return "verified"

    async def download_acknowledgement(
        self,
        page: Any,
        *,
        acknowledgement: str,
        output_dir: str | Path,
        deadline: MonotonicDeadline,
        log: Optional[LogCallback] = None,
    ) -> Optional[str]:
        """Download the acknowledgement receipt for the submitted return."""
        await navigate_income_tax_returns(
            page,
            timeout_ms=max(1, deadline.remaining_ms),
            log=log,
        )
        view = await _find_action(page, ("View Filed Returns",), deadline)
        if view is None:
            return None
        await view.click(timeout=max(1, min(2_000, deadline.remaining_ms)))

        row = page.get_by_text(acknowledgement, exact=False).first
        try:
            card = row.locator("xpath=ancestor::*[self::mat-card or @role='row'][1]")
            receipt = card.get_by_text(
                re.compile(r"Download\s+(?:Receipt|Acknowledgement)", re.I)
            ).first
            if not await receipt.is_visible(timeout=2_000):
                receipt = await _find_action(
                    page,
                    ("Download Receipt", "Download Acknowledgement"),
                    deadline,
                )
        except Exception:
            receipt = await _find_action(
                page,
                ("Download Receipt", "Download Acknowledgement"),
                deadline,
            )
        if receipt is None:
            return None

        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        final_path = destination / "ITR-Acknowledgement.pdf"
        async with page.expect_download(
            timeout=max(1, deadline.remaining_ms)
        ) as info:
            await receipt.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        download = await info.value
        await download.save_as(str(final_path))
        if not final_path.exists() or final_path.stat().st_size == 0:
            final_path.unlink(missing_ok=True)
            return None
        _emit(log, "[ACK] Acknowledgement receipt downloaded.")
        return str(final_path)

    async def _visible_portal_error(self, page: Any) -> Optional[str]:
        selectors = (
            ("[role='alert']", True),
            (".alert-danger", False),
            (".error-message", False),
            ("mat-error", False),
        )
        for selector, require_error_word in selectors:
            locator = page.locator(selector).first
            try:
                if await locator.is_visible(timeout=100):
                    text = " ".join((await locator.inner_text()).split())
                    lowered = text.lower()
                    is_error = any(
                        marker in lowered
                        for marker in (
                            "error",
                            "invalid",
                            "failed",
                            "cannot",
                            "not valid",
                            "rejected",
                        )
                    )
                    if text and (not require_error_word or is_error):
                        return text[:500]
            except Exception:
                continue
        return None

    @staticmethod
    def _failure(state: PortalUploadState, reason: str) -> PortalUploadOutcome:
        return PortalUploadOutcome(state=state, reason=reason)


async def _find_action(
    page: Any,
    names: tuple[str, ...],
    deadline: MonotonicDeadline,
    *,
    timeout_cap_ms: int = 20_000,
) -> Optional[Any]:
    """Find a visible semantic action under one shared deadline."""
    local = MonotonicDeadline.after(min(timeout_cap_ms, deadline.remaining_ms))
    while not local.expired and not deadline.expired:
        for name in names:
            pattern = re.compile(rf"^\s*{re.escape(name)}\s*$", re.I)
            for role in ("button", "link", "radio", "option"):
                try:
                    locator = page.get_by_role(role, name=pattern).first
                    if await locator.is_visible(timeout=1):
                        return locator
                except Exception:
                    continue
            try:
                locator = page.get_by_text(pattern, exact=True).first
                if await locator.is_visible(timeout=1):
                    return locator
            except Exception:
                pass
        await local.sleep(0.05)
    return None


async def _click_optional(
    page: Any,
    names: tuple[str, ...],
    deadline: MonotonicDeadline,
) -> bool:
    action = await _find_action(page, names, deadline, timeout_cap_ms=3_000)
    if action is None:
        return False
    await action.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
    return True


async def _select_value(
    page: Any,
    label: str,
    value: str,
    deadline: MonotonicDeadline,
    *,
    required: bool = True,
) -> bool:
    """Select native or Angular material controls by visible label/value.

    Handles four control types (tried in order):
    1. Angular Material ``mat-select`` — click trigger to open, find
       ``mat-option`` by text regex (pattern from NRITAX).
    2. Native ``<select>`` — use ``select_option``.
    3. Custom combobox — click trigger, then find option by text across
       all frames.
    4. Plain text/button — use ``_find_action``.
    """
    import asyncio as _asyncio

    # 1. Angular Material mat-select (ITD portal's AY dropdown)
    try:
        mat_select = page.locator(
            "mat-select.mat-mdc-select-required, "
            "mat-select#filterStyleForChip, "
            "mat-select:not(#langMatSelect)"
        ).first
        if await mat_select.is_visible(timeout=1_000):
            await mat_select.click(force=True)
            await _asyncio.sleep(0.6)
            # Find the mat-option matching the value text
            try:
                opt = page.locator("mat-option").filter(
                    has_text=re.compile(re.escape(value), re.I)
                ).first
                if await opt.is_visible(timeout=3_000):
                    await opt.click()
                    await _asyncio.sleep(0.5)
                    return True
            except Exception:
                pass
            # Try "current A.Y" variant
            try:
                opt = page.locator("mat-option").filter(
                    has_text=re.compile(r"current\s*a\.?y", re.I)
                ).first
                if await opt.is_visible(timeout=1_000):
                    await opt.click()
                    await _asyncio.sleep(0.5)
                    return True
            except Exception:
                pass
            # Close the dropdown if we didn't find the option
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
    except Exception:
        pass

    # 2. Native <select>
    try:
        control = page.get_by_label(re.compile(re.escape(label), re.I)).first
        if await control.is_visible(timeout=100):
            try:
                await control.select_option(label=value)
                return True
            except Exception:
                # Not a native select — it's a custom combobox. Click to open.
                await control.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
                await _asyncio.sleep(0.5)
                # Now find the option by text across all frames
                option = await _find_option_by_text(page, value, deadline)
                if option is not None:
                    await option.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
                    return True
                raise RuntimeError(f"{label} option {value} was not found.")
    except RuntimeError:
        raise
    except Exception:
        pass

    # 3. Fallback: try _find_action (buttons/links/roles)
    option = await _find_action(page, (value,), deadline, timeout_cap_ms=3_000)
    if option is not None:
        await option.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        return True

    # 4. Final fallback: search by text across all frames
    option = await _find_option_by_text(page, value, deadline)
    if option is not None:
        await option.click(timeout=max(1, min(2_000, deadline.remaining_ms)))
        return True

    if required:
        raise RuntimeError(f"{label} selection was not available.")
    return False


async def _find_option_by_text(
    page: Any,
    value: str,
    deadline: MonotonicDeadline,
) -> Optional[Any]:
    """Find an option by visible text across all frames.

    Mirrors the prefill downloader's frame-scanning pattern for finding
    options in custom Angular dropdowns. Uses ``get_by_text`` with exact
    match, falling back to partial match.
    """
    import asyncio as _asyncio

    # Scan main page and all frames
    frames = list(getattr(page, "frames", ()))
    if not frames:
        frames = [page]

    for frame in frames:
        if deadline.expired:
            return None
        # Try exact text match
        try:
            locator = frame.get_by_text(value, exact=True).first
            if await locator.is_visible(timeout=500):
                return locator
        except Exception:
            pass
        # Try partial text match (for "AY 2026-27" etc.)
        try:
            pattern = re.compile(re.escape(value), re.I)
            locator = frame.get_by_text(pattern).first
            if await locator.is_visible(timeout=500):
                return locator
        except Exception:
            pass
    return None


def _emit(log: Optional[LogCallback], message: str) -> None:
    if log is not None:
        log(message)


async def _select_mat_option(
    page: Any,
    option_pattern: str,
    *,
    label: Optional[str] = None,
    index: Optional[int] = None,
    log: Optional[LogCallback] = None,
) -> bool:
    """Open an Angular Material mat-select dropdown and click an option.

    Mirrors NRITAX's ``selectAssessmentYear`` mat-select pattern:
    1. Find the mat-select trigger (by index, label, or first available)
    2. Click it to open the dropdown panel
    3. Find the mat-option matching the text pattern
    4. Click the option

    Args:
        page: Playwright page.
        option_pattern: Regex pattern string for the option text (e.g. ``r"139\\s*\\(1\\)"``).
        label: Optional label text to find the mat-select by its nearby label.
        index: Optional zero-based index of the mat-select on the page
            (e.g. ``0`` for AY, ``1`` for Filing Type, ``2`` for ITR Form).
        log: Optional log callback.

    Returns:
        ``True`` if an option was selected, otherwise ``False``.
    """
    import asyncio as _asyncio

    pattern = re.compile(option_pattern, re.I)

    # Find the mat-select trigger.
    mat_select = None

    # Strategy 1: Use index if provided (most reliable)
    if index is not None:
        try:
            all_selects = page.locator("mat-select:not(#langMatSelect)")
            count = await all_selects.count()
            _emit(log, f"[ITR UPLOAD] Found {count} mat-select(s); selecting index {index}.")
            if count > index:
                mat_select = all_selects.nth(index)
                _emit(log, f"[ITR UPLOAD] Selected mat-select at index {index}.")
        except Exception:
            pass

    # Strategy 2: Find by label
    if mat_select is None and label:
        try:
            label_pattern = re.compile(re.escape(label), re.I)
            form_field = page.locator("mat-form-field").filter(
                has_text=label_pattern
            ).first
            try:
                ff_visible = False
                try:
                    ff_visible = await form_field.is_visible(timeout=1_000)
                except Exception:
                    ff_visible = False
                if ff_visible:
                    mat_select = form_field.locator("mat-select").first
                    _emit(log, f"[ITR UPLOAD] Found mat-select by label '{label}'.")
            except Exception:
                pass
        except Exception:
            pass

    if mat_select is None:
        # Fallback: find any non-language mat-select.
        mat_select = page.locator(
            "mat-select.mat-mdc-select-required, "
            "mat-select#filterStyleForChip, "
            "mat-select:not(#langMatSelect)"
        ).first

    try:
        visible = False
        try:
            visible = await mat_select.is_visible(timeout=2_000)
        except Exception:
            try:
                visible = await mat_select.is_visible()
            except Exception:
                visible = False
        if not visible:
            _emit(log, "[ITR UPLOAD] mat-select trigger not visible.")
            # Fallback: try clickTextOption (radio/button/text)
            return await _click_text_option(page, pattern)

        # Click the trigger to open the dropdown panel
        try:
            await mat_select.click(force=True, timeout=2_000)
        except Exception:
            try:
                await mat_select.click(timeout=2_000)
            except Exception:
                _emit(log, "[ITR UPLOAD] Failed to click mat-select trigger.")
                return await _click_text_option(page, pattern)

        await _asyncio.sleep(0.6)  # NRITAX: waitForTimeout(600)

        # Find the mat-option matching the pattern
        opt = page.locator("mat-option").filter(
            has_text=pattern
        ).first

        try:
            opt_visible = False
            try:
                opt_visible = await opt.is_visible(timeout=3_000)
            except Exception:
                try:
                    opt_visible = await opt.is_visible()
                except Exception:
                    opt_visible = False
            if opt_visible:
                await opt.click()
                await _asyncio.sleep(0.5)  # NRITAX: waitForTimeout(500)
                return True
        except Exception:
            pass

        # Fallback: try clicking any visible mat-option matching the pattern
        try:
            options = page.locator("mat-option")
            count = await options.count()
            for i in range(count):
                el = options.nth(i)
                try:
                    text = await el.inner_text(timeout=100)
                except Exception:
                    text = ""
                if pattern.search(text or ""):
                    try:
                        if await el.is_visible(timeout=100):
                            await el.click()
                            await _asyncio.sleep(0.5)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass

        # Close the dropdown if we didn't find the option
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    except Exception:
        pass

    # Final fallback: try clickTextOption
    return await _click_text_option(page, pattern)


async def _click_text_option(
    page: Any,
    text: "re.Pattern[str]",
) -> bool:
    """Click the first visible element matching ``text`` across roles.

    Ported from NRITAX's ``clickTextOption``. Tries in order:
    radio → option → button → link → text (partial match).
    Also adds Angular Material selectors between role and text candidates.
    Uses 100ms timeouts and iterates through ALL matches (not just .first)
    to find the first visible one — this avoids clicking hidden/header elements.
    """
    import asyncio as _asyncio

    # Build a regex source string for XPath construction
    text_source = text.pattern if hasattr(text, 'pattern') else str(text)
    # Escape for XPath
    xpath_escaped = (
        text_source
        .replace("\\", "")
        .replace("'", "&apos;")
    )

    candidates = [
        page.get_by_role("radio", name=text),
        page.get_by_role("option", name=text),
        page.get_by_role("button", name=text),
        page.get_by_role("link", name=text),
        # Angular Material radio buttons (not always caught by get_by_role)
        page.locator(
            f"//mat-radio-button[contains(normalize-space(.), '{xpath_escaped}')]"
        ),
        # Angular Material options
        page.locator(
            f"//mat-option[contains(normalize-space(.), '{xpath_escaped}')]"
        ),
        # Angular Material cards/tiles
        page.locator(
            f"//mat-card[contains(normalize-space(.), '{xpath_escaped}')] | "
            f"//div[contains(@class, 'option') and contains(normalize-space(.), '{xpath_escaped}')] | "
            f"//span[contains(@class, 'option') and contains(normalize-space(.), '{xpath_escaped}')]"
        ),
        # Generic clickable elements with the text (but NOT in header/nav)
        page.locator(
            f"//*[not(ancestor::header) and not(ancestor::nav) and not(contains(@class, 'header'))]"
            f"[contains(normalize-space(.), '{xpath_escaped}')]"
        ),
        page.get_by_text(text, exact=False),
    ]
    for loc in candidates:
        # Iterate through all matches to find the first visible one.
        # This prevents clicking hidden elements (e.g. in collapsed headers).
        try:
            count = await loc.count()
        except Exception:
            count = 0
        for i in range(min(count, 10)):  # cap at 10 to avoid long loops
            el = loc.nth(i)
            try:
                visible = False
                try:
                    visible = await el.is_visible(timeout=100)
                except Exception:
                    try:
                        visible = await el.is_visible()
                    except Exception:
                        visible = False
                if visible:
                    try:
                        await el.click(timeout=100)
                    except Exception:
                        try:
                            await el.click(force=True, timeout=100)
                        except Exception:
                            continue
                    await _asyncio.sleep(0.4)
                    return True
            except Exception:
                continue
    return False


async def _click_if_visible(
    page: Any,
    name: "re.Pattern[str]",
    role: str,
    timeout: int,
) -> bool:
    """Click the first visible element with ``role`` matching ``name``.

    Direct port of NRITAX's ``clickIfVisible``. Uses 100ms click timeout
    to match NRITAX's ``.catch(() => undefined)`` — never hangs on
    disabled buttons.
    """
    import asyncio as _asyncio

    el = page.get_by_role(role, name=name).first
    try:
        # NRITAX: if (await el.isVisible({ timeout }).catch(() => false))
        visible = False
        try:
            visible = await el.is_visible(timeout=timeout)
        except Exception:
            try:
                visible = await el.is_visible()
            except Exception:
                visible = False
        if visible:
            # NRITAX: await el.click().catch(() => undefined)
            try:
                await el.click(timeout=100)
            except Exception:
                try:
                    await el.click(force=True, timeout=100)
                except Exception:
                    return False
            await _asyncio.sleep(0.5)  # NRITAX: waitForTimeout(500)
            return True
    except Exception:
        pass
    return False


async def _answer_yes_no(
    page: Any,
    question: "re.Pattern[str]",
    yes: bool,
) -> None:
    """Answer a Yes/No question on the portal.

    Direct port of NRITAX's ``answerYesNo``. Finds the question text, then
    clicks Yes/No in the same row/section. Uses 100ms timeouts to match
    NRITAX's ``.catch(() => undefined)``.
    """
    q = page.get_by_text(question).first
    try:
        visible = False
        try:
            visible = await q.is_visible(timeout=1_500)
        except Exception:
            try:
                visible = await q.is_visible()
            except Exception:
                visible = False
        if not visible:
            return
    except Exception:
        return

    # Find the Yes/No option in the same row/section.
    try:
        row = q.locator(
            "xpath=ancestor::*[self::div or self::section or self::mat-form-field][1]"
        )
        label = re.compile(r"^yes$" if yes else r"^no$", re.I)
        opt = row.get_by_text(label).first
        opt_visible = False
        try:
            opt_visible = await opt.is_visible(timeout=1_000)
        except Exception:
            try:
                opt_visible = await opt.is_visible()
            except Exception:
                opt_visible = False
        if opt_visible:
            try:
                await opt.click(timeout=100)
            except Exception:
                try:
                    await opt.click(force=True, timeout=100)
                except Exception:
                    pass
            return
    except Exception:
        pass

    # Fallback: click Yes/No by role/text anywhere on the page.
    await _click_text_option(page, re.compile(r"^(yes|y)$" if yes else r"^(no|n)$", re.I))
