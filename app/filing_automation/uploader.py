"""Playwright primitives for ERI Type-3 ITR upload and post-filing actions."""

from __future__ import annotations

import datetime
import inspect
import json
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

# CBDT FilingStatus.ReturnFileSec code -> the section the portal's "Filing Type"
# dropdown labels its option with.  The portal gates its ITR list on this: after
# the 139(1) due date it simply stops offering the forms whose due date has gone
# (ITR-1/ITR-2 from 1 August), so filing a belated return under 139(1) leaves the
# wizard stuck on a form list that does not contain the form being filed.
_RETURN_FILE_SEC_TO_SECTION = {
    11: "139(1)",
    12: "139(4)",
    13: "142(1)",
    14: "148",
    16: "153C",
    17: "139(5)",
    18: "139(9)",
    20: "119(2)(b)",
}


# Every step of the offline upload flow lives on this route. Any control that
# navigates off it has taken the wizard somewhere the upload cannot happen.
_FILE_ITR_ROUTE = "fileincometaxreturn"

# Wording the ITD upload page uses when it refuses an attached JSON. Matched
# against rendered text because the block carries no error role or class.
_PORTAL_ERROR_SCAN_JS = """() => {
    const shown = (el) => {
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none') return false;
        if (!el.offsetParent && cs.position !== 'fixed') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    };
    const phrases = [
        'please correct the below mentioned error',
        'error description',
        'invalid software provider',
        'does not have access to upload',
        'in the uploaded json',
    ];
    const body = document.body ? document.body.innerText : '';
    const hit = phrases.find(p => body.toLowerCase().includes(p));
    if (!hit) return null;
    // Report the tightest visible block containing the wording, so the reason
    // is the portal's own sentence rather than the whole page.
    let best = null;
    document.querySelectorAll('div,section,p,li,span,mat-card').forEach(el => {
        if (!shown(el)) return;
        const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
        if (!t || !t.toLowerCase().includes(hit)) return;
        if (best === null || t.length < best.length) best = t;
    });
    return best || body.replace(/\\s+/g, ' ').trim().slice(0, 500);
}"""

# The production portal rejects a UAT software-provider identity outright.
_SW_PROVIDER_ERROR_RE = re.compile(
    r"software provider|swproviderid|does not have access to upload", re.I
)


def _eri_environment_hint() -> str:
    """Explain a SWProviderID rejection in terms of the active ERI bundle.

    This is the not-yet-enabled state, not a malformed identity: the portal
    refuses a software provider it has not authorised to file. Phase 4 of the
    ERI integration plan is what clears it.
    """
    try:
        from app.eri.config import get_eri_credentials

        creds = get_eri_credentials()
        active = f"{creds.sw_id} ({creds.mode}/{creds.environment})"
    except Exception:
        active = "the active ERI bundle"
    return (
        f" The return was stamped with {active}. The portal rejects a software "
        "provider it has not enabled for filing, so this usually means the "
        "SW_ID is not yet authorised rather than that the JSON is wrong. "
        "Complete Phase 4 of Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md — run "
        "scripts/type3_uat_sanity.py and email the pack to "
        "erihelp@incometax.gov.in — and await ITD SW_ID enablement."
    )


class PortalSessionLost(RuntimeError):
    """Raised when the portal session ends part-way through the wizard."""


async def _log_step_state(page: Any, step: str, log: Optional[LogCallback]) -> None:
    """Log the URL and the headings the portal is showing at a wizard step.

    One line per step, so a stalled run shows which page each click landed on
    without needing a live reproduction.
    """
    url = str(getattr(page, "url", "") or "?")
    try:
        headings = await page.evaluate(
            """() => Array.from(document.querySelectorAll('h1,h2,h3,h4,mat-card-title,.page-title'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => (el.innerText || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean).slice(0, 5)"""
        )
    except Exception:
        headings = []
    _emit(log, f"[ITR UPLOAD] Step state {step}: url={url} headings={headings}")


async def _assert_on_file_itr_route(
    page: Any, step: str, log: Optional[LogCallback]
) -> None:
    """Fail as soon as a click navigates the wizard off the File ITR page."""
    url = str(getattr(page, "url", "") or "")
    if _FILE_ITR_ROUTE in url.lower():
        return
    _emit(log, f"[ITR UPLOAD] Left the File ITR wizard while {step}: url={url!r}")
    await _log_page_controls(page, log)
    raise RuntimeError(
        f"The wizard navigated away from the File ITR page while {step} — it is "
        f"now at {url!r}. The offline upload step only exists on the File ITR "
        "route, so no control that leaves it may be clicked."
    )


async def _assert_session(page: Any, step: str, log: Optional[LogCallback]) -> None:
    """Fail at the step that lost the session rather than several steps later.

    Without this, a logout during the wizard surfaced as whatever control was
    missing next — "file input not found" for a session that had actually
    ended while the Assessment Year was being chosen.
    """
    if not await session_expired(page):
        return
    url = str(getattr(page, "url", ""))
    _emit(log, f"[ITR UPLOAD] Session lost while {step} (url={url}).")
    raise PortalSessionLost(f"The ITD portal session ended while {step}.")


def _filing_section_pattern(filing_section: str) -> str:
    """Return a loose regex matching a section in the portal's option labels.

    Portal labels carry surrounding wording ("139(1) - Original Return") and
    inconsistent spacing around the bracket, so only the digits and brackets
    are anchored.
    """
    return r"\s*".join(re.escape(part) for part in re.findall(r"\w+|\(|\)", filing_section))


def _log_json_identity(path: Path, log: Optional[LogCallback]) -> None:
    """Record which artifact is being uploaded, and whose return it is.

    The run only ever logged that a file was attached, never which one, so
    confirming the portal received the return that was just generated — rather
    than a stale file left in the downloads directory — meant inspecting the
    filesystem by hand.
    """
    try:
        stat = path.stat()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _emit(log, f"[ITR UPLOAD] Could not inspect {path}: {exc}")
        return
    forms = payload.get("ITR")
    form_name, pan, ay, section = "?", "?", "?", "?"
    if isinstance(forms, dict):
        for key, body in forms.items():
            if not isinstance(body, dict):
                continue
            form_name = key
            header = body.get(f"Form_{key}")
            if isinstance(header, dict):
                ay = header.get("AssessmentYear", "?")
            filing_status = body.get("FilingStatus")
            if isinstance(filing_status, dict):
                section = filing_status.get("ReturnFileSec", "?")
            personal = body.get("PersonalInfo")
            if isinstance(personal, dict):
                pan = personal.get("PAN", "?")
            break
    _emit(
        log,
        f"[ITR UPLOAD] Uploading {path.name} ({stat.st_size} bytes, modified "
        f"{datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}) "
        f"from {path.parent}",
    )
    _emit(
        log,
        f"[ITR UPLOAD] Artifact contents: form={form_name} pan={pan} "
        f"assessmentYear={ay} ReturnFileSec={section}",
    )


def _filing_section_from_json(path: Path) -> Optional[str]:
    """Read the filing section out of the CBDT JSON that is being uploaded.

    The generated JSON is the single source of truth for what is being filed,
    so the portal's Filing Type is taken from it rather than from a separate
    argument that could drift out of step with the artifact.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    forms = payload.get("ITR")
    if not isinstance(forms, dict):
        return None
    for form_body in forms.values():
        if not isinstance(form_body, dict):
            continue
        filing_status = form_body.get("FilingStatus")
        if isinstance(filing_status, dict):
            return _RETURN_FILE_SEC_TO_SECTION.get(filing_status.get("ReturnFileSec"))
    return None


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
            _log_json_identity(path, log)
            filing_section = _filing_section_from_json(path)
            if filing_section is None:
                return self._failure(
                    PortalUploadState.PERMANENT_FAILURE,
                    "The generated filing JSON does not carry a recognised "
                    "FilingStatus.ReturnFileSec, so the portal's Filing Type "
                    "cannot be selected.",
                )
            _emit(
                log,
                f"[ITR UPLOAD] Opening File Income Tax Return "
                f"(filing section {filing_section} from the JSON).",
            )
            await self.goto_file_itr_page(
                page,
                assessment_year=assessment_year,
                itr_type=itr_type,
                filing_section=filing_section,
                deadline=deadline,
                log=log,
            )
            await self._upload_file(page, path, deadline)
            portal_error = await self._visible_portal_error(page)
            if portal_error:
                _emit(log, f"[ITR UPLOAD] Portal rejected the uploaded JSON: {portal_error}")
                if _SW_PROVIDER_ERROR_RE.search(portal_error):
                    portal_error += _eri_environment_hint()
                return self._failure(
                    PortalUploadState.VALIDATION_FAILED,
                    portal_error,
                )

            _emit(log, "[ITR UPLOAD] Local artifact accepted; submitting return.")
            await self._submit_and_confirm(page, deadline)
            portal_error = await self._visible_portal_error(page)
            if portal_error:
                _emit(log, f"[ITR UPLOAD] Portal rejected the submission: {portal_error}")
                if _SW_PROVIDER_ERROR_RE.search(portal_error):
                    portal_error += _eri_environment_hint()
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
        except (DisabledRouteError, PortalSessionLost) as exc:
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
        filing_section: str = "139(1)",
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
        await _assert_session(page, "opening the File ITR page", log)

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
        selected_ay = await _select_mat_option(page, assessment_year, index=0, log=log)
        _emit(
            log,
            f"[ITR UPLOAD] Assessment Year {assessment_year}: "
            f"{'selected' if selected_ay else 'NOT SELECTED'}.",
        )
        await dismiss_portal_modals(page, log=log)
        await _assert_session(page, "selecting the Assessment Year", log)
        await _log_step_state(page, "after the Assessment Year", log)
        await _assert_on_file_itr_route(page, "selecting the Assessment Year", log)
        await _asyncio.sleep(1.0)  # NRITAX: waitForTimeout(1000)

        # Select "Offline" mode FIRST (before Continue) — NRITAX pattern.
        _emit(log, "[ITR UPLOAD] Selecting Offline mode.")
        await _click_text_option(page, re.compile(r"offline", re.I))
        await dismiss_portal_modals(page, log=log)
        await _assert_session(page, "selecting Offline mode", log)
        await _asyncio.sleep(0.4)  # NRITAX: waitForTimeout(400)

        # Now click Continue — it should be enabled after Offline is selected.
        _emit(log, "[ITR UPLOAD] Clicking Continue after Offline.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|let'?s get started|next", re.I),
            "button",
            4_000,
            log=log,
            step="Continue after Offline mode",
        )
        await dismiss_portal_modals(page, log=log)
        await _assert_session(page, "continuing past the Offline mode step", log)
        await _log_step_state(page, "after Offline mode", log)
        await _assert_on_file_itr_route(page, "continuing past Offline mode", log)
        await _asyncio.sleep(0.5)  # NRITAX: waitForTimeout(500)

        # Select the Filing Type from the Filing Type dropdown (#1).  This was
        # hardcoded to 139(1), which both mis-stated the section a belated or
        # revised return was filed under and stalled the wizard: the portal
        # narrows the ITR list to the forms still filable under the chosen
        # section, so a 139(1) selection after 31 July offered only ITR-3/ITR-4
        # and the ITR-1 selection a few steps later could never succeed.
        # The portal auto-detects Individual taxpayer — we never select it.
        _emit(log, f"[ITR UPLOAD] Selecting Filing Type: {filing_section}.")
        selected_section = await _select_mat_option(
            page, _filing_section_pattern(filing_section), index=1, log=log
        )
        if not selected_section:
            # A lost session presents as every control being absent, so rule
            # that out before blaming the dropdown's contents.
            await _assert_session(page, "selecting the Filing Type", log)
            await _log_page_controls(page, log)
            raise RuntimeError(
                f"Could not select filing section {filing_section!r} in the portal's "
                "Filing Type dropdown — see the option list logged above for what the "
                "portal offered."
            )
        _emit(log, f"[ITR UPLOAD] Filing Type {filing_section}: selected.")
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        _emit(log, "[ITR UPLOAD] Clicking Continue after Filing Type.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|next", re.I),
            "button",
            3_000,
            log=log,
            step="Continue after Filing Type",
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
        await _assert_session(page, "answering the 44AB audit question", log)

        # Select ITR form type from the ITR Form dropdown (#2).
        _emit(log, f"[ITR UPLOAD] Selecting ITR form type: {itr_type}.")
        selected_form = await _select_mat_option(page, itr_type, index=2, log=log)
        if not selected_form:
            # Continuing past this leaves the wizard on a step whose Continue
            # button stays disabled, and the run then fails ten steps later
            # reporting a missing file input — which describes a symptom far
            # from the cause. Stop where the problem actually is.
            await _assert_session(page, "selecting the ITR form type", log)
            await _log_page_controls(page, log)
            raise RuntimeError(
                f"Could not select ITR form type {itr_type!r} in the portal's ITR Form "
                "dropdown — see the option list logged above for what the portal offered. "
                "If the form is genuinely absent, the portal is not accepting it for this "
                "assessment year and filing mode."
            )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        _emit(log, "[ITR UPLOAD] Clicking Continue after ITR form type.")
        await _click_if_visible(
            page,
            re.compile(r"continue|proceed|next|start", re.I),
            "button",
            4_000,
            log=log,
            step="Continue after ITR form type",
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
            log=log,
            step="Continue after PEP question",
        )
        await dismiss_portal_modals(page, log=log)
        await _asyncio.sleep(0.4)

        # The portal's "Download Pre-filled Data" control is NOT part of the
        # offline upload flow. Clicking it leaves the wizard for
        # #/dashboard/downloadPreFilledData — a standalone page that asks for
        # the assessment year again and never renders a file input — and the
        # run then failed reporting an absent upload control while sitting on
        # a completely different page. We generate the CBDT JSON ourselves, so
        # the portal's prefill is never needed and must not be clicked.
        await _log_step_state(page, "before reaching the upload step", log)
        await _assert_on_file_itr_route(page, "completing the wizard questions", log)

        # "Offline / JSON submission / Upload JSON" reaches the upload panel on
        # portal variants that gate it behind a link. It is safe to miss: when
        # the panel is already rendered the file input is simply present.
        clicked_offline = await _click_if_visible(
            page,
            re.compile(r"offline|json submission|upload json", re.I),
            "link",
            3_000,
            log=log,
            step="Offline/JSON submission/Upload JSON link",
        )
        _emit(
            log,
            f"[ITR UPLOAD] Offline/JSON submission/Upload JSON link: "
            f"{'clicked' if clicked_offline else 'not present (upload panel may already be rendered)'}.",
        )
        await dismiss_portal_modals(page, log=log)
        await _assert_session(page, "reaching the upload step", log)
        await _asyncio.sleep(1.0)
        await _log_step_state(page, "at the upload step", log)
        await _assert_on_file_itr_route(page, "reaching the upload step", log)

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
        locator = page.locator("input[type='file']")
        # Wait for ATTACHED, not visible. The portal renders a styled button
        # over an input that is display:none / opacity:0, as most Angular file
        # pickers do, so is_visible() is False for the whole wait and the upload
        # was abandoned even though the input was present. set_input_files()
        # works on a hidden input — that is the supported Playwright pattern —
        # so presence in the DOM is the correct precondition.
        file_input_count = 0
        for _ in range(20):  # 20 × 500ms = 10s max
            try:
                file_input_count = await locator.count()
                if file_input_count:
                    break
            except Exception:
                pass
            await dismiss_portal_modals(page)
            await _asyncio.sleep(0.5)
        if not file_input_count:
            # Record what the page actually was, so the next failure does not
            # need a live reproduction to diagnose.
            try:
                current_url = str(getattr(page, "url", "") or "")
                frame_count = len(getattr(page, "frames", ()) or ())
            except Exception:
                current_url, frame_count = "<unavailable>", -1
            await _log_page_controls(page)
            raise RuntimeError(
                "ITR JSON file input was not found. "
                f"url={current_url!r} frames={frame_count} "
                "(no input[type=file] attached to the DOM after 10s). "
                "The wizard is still on the File ITR page — see the page-control "
                "listing above for the controls the portal actually rendered."
            )
        locator = locator.first
        await locator.set_input_files(
            str(json_path.resolve()),
            timeout=max(1, min(10_000, deadline.remaining_ms)),
        )
        await _click_optional(page, ("Upload", "Proceed", "Continue"), deadline)
        await dismiss_portal_modals(page)
        # The portal validates the attachment server-side. Checking for its
        # rejection banner immediately after the click reads the page before
        # the verdict has rendered, so a refused upload looks accepted.
        await _asyncio.sleep(2.0)

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
        """Return the portal's visible rejection text, if it is showing one.

        The upload page renders its rejection as a plain block — not as
        ``[role=alert]``, ``.alert-danger``, ``.error-message`` or
        ``mat-error`` — so the selector scan below found nothing for a return
        the portal had openly refused. The run then logged "Local artifact
        accepted", went on to submit, and died with "Final ITR submit action
        was not found", which says nothing about the actual rejection. Scan
        the rendered text for the portal's own error wording first.
        """
        try:
            phrase_hit = await page.evaluate(_PORTAL_ERROR_SCAN_JS)
        except Exception:
            phrase_hit = None
        if phrase_hit:
            return str(phrase_hit)[:500]

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
                # "Located", not "selected" — nothing has been chosen yet. The
                # old wording made a failure to find the option read as success.
                _emit(log, f"[ITR UPLOAD] Located mat-select at index {index}.")
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

        # The requested option is not in this dropdown. Record what the portal
        # did offer before closing it: the caller only knows "not selected",
        # and without the actual option list the difference between a changed
        # label and a form the portal is not accepting for this assessment year
        # cannot be told apart without watching a live run.
        try:
            available = await page.evaluate(
                """() => Array.from(document.querySelectorAll('mat-option'))
                        .map(o => (o.innerText || '').replace(/\\s+/g, ' ').trim())
                        .filter(Boolean).slice(0, 20)"""
            )
            _emit(
                log,
                f"[ITR UPLOAD] Option {option_pattern!r} NOT among the "
                f"{len(available)} option(s) offered: {available}",
            )
        except Exception:
            _emit(log, f"[ITR UPLOAD] Option {option_pattern!r} not found; option list unavailable.")

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


async def _log_page_controls(page: Any, log: Any = None) -> None:
    """Record every actionable control currently on the page.

    When the wizard stalls, the only thing worth knowing is what the portal is
    actually showing. Without this the failure reports an absent file input and
    nothing about the page that was rendered instead, so identifying the real
    control means reproducing the run interactively against a live ITD session.
    """
    try:
        report = await page.evaluate(
            """() => {
                // Angular keeps every dialog template in the DOM, so checking an
                // element's own display/visibility reports dozens of off-screen
                // controls as visible. offsetParent plus a non-zero box is what
                // actually distinguishes rendered from parked.
                const shown = (el) => {
                    const cs = getComputedStyle(el);
                    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
                    if (!el.offsetParent && cs.position !== 'fixed') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                const label = (el) =>
                    (el.innerText || el.value || el.getAttribute('aria-label') || '')
                        .replace(/\\s+/g, ' ').trim().slice(0, 70);

                const controls = [];
                document.querySelectorAll('button, a').forEach(el => {
                    if (!shown(el)) return;
                    const text = label(el);
                    if (!text) return;
                    controls.push({
                        kind: el.tagName.toLowerCase(),
                        text,
                        disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
                    });
                });

                const inputs = [];
                document.querySelectorAll('input, mat-select, select').forEach(el => {
                    inputs.push({
                        kind: el.tagName.toLowerCase() +
                              (el.type ? '[' + el.type + ']' : ''),
                        text: (el.name || el.id || el.getAttribute('formcontrolname') || '').slice(0, 60),
                        shown: shown(el),
                    });
                });

                // Which step is the wizard actually displaying?
                const headings = [];
                document.querySelectorAll('h1,h2,h3,h4,mat-card-title,.page-title').forEach(el => {
                    if (shown(el)) { const t = label(el); if (t) headings.push(t); }
                });

                const dialogs = [];
                document.querySelectorAll('mat-dialog-container,[role=dialog],.modal.show')
                    .forEach(el => { if (shown(el)) dialogs.push(label(el).slice(0, 140)); });

                return { controls: controls.slice(0, 25), inputs: inputs.slice(0, 25),
                         headings: headings.slice(0, 8), dialogs: dialogs.slice(0, 5) };
            }"""
        )
    except Exception as exc:  # pragma: no cover - diagnostic path only
        _emit(log, f"[ITR UPLOAD] Could not enumerate page controls: {exc}")
        return

    _emit(log, f"[ITR UPLOAD] Page state at {getattr(page, 'url', '?')}")

    for dialog in report.get("dialogs") or []:
        _emit(log, f"[ITR UPLOAD]   BLOCKING DIALOG: {dialog!r}")

    headings = report.get("headings") or []
    _emit(log, f"[ITR UPLOAD]   headings: {headings if headings else '(none visible)'}")

    controls = report.get("controls") or []
    if not controls:
        _emit(log, "[ITR UPLOAD]   (no visible buttons or links)")
    for item in controls:
        state = ",disabled" if item.get("disabled") else ""
        _emit(log, f"[ITR UPLOAD]   {item.get('kind')}: {item.get('text')!r}{state and ' [' + state.lstrip(',') + ']'}")

    file_inputs = [i for i in (report.get("inputs") or []) if "file" in (i.get("kind") or "")]
    _emit(
        log,
        f"[ITR UPLOAD]   file inputs in DOM: {len(file_inputs)}"
        + (f" -> {file_inputs}" if file_inputs else ""),
    )


async def _click_if_visible(
    page: Any,
    name: "re.Pattern[str]",
    role: str,
    timeout: int,
    log: Optional[LogCallback] = None,
    step: Optional[str] = None,
) -> bool:
    """Click the first visible element with ``role`` matching ``name``.

    Direct port of NRITAX's ``clickIfVisible``. Uses 100ms click timeout
    to match NRITAX's ``.catch(() => undefined)`` — never hangs on
    disabled buttons.

    When ``log`` and ``step`` are given, the text of the element that actually
    matched is recorded along with the URL before and after the click. A
    pattern loose enough to advance several portal variants is also loose
    enough to hit the wrong control, and the label is the only way to tell
    which one it caught.
    """
    import asyncio as _asyncio

    el = page.get_by_role(role, name=name).first
    if log is not None and step:
        matched = ""
        try:
            matched = (await el.inner_text(timeout=200)).replace("\n", " ").strip()[:70]
        except Exception:
            pass
        url_before = str(getattr(page, "url", "") or "?")
        _emit(
            log,
            f"[ITR UPLOAD] {step}: matched {role} {matched!r} at url={url_before}",
        )
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
            if log is not None and step:
                _emit(
                    log,
                    f"[ITR UPLOAD] {step}: clicked; url is now "
                    f"{str(getattr(page, 'url', '') or '?')}",
                )
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
