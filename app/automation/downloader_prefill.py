"""Standalone, validated downloader for ITD pre-filled JSON data."""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence

from app.automation.navigation import (
    MonotonicDeadline,
    navigate_income_tax_returns,
    resolve_itd_anchor,
    session_expired,
)

AY = "2026-27"
_AY_TEXT = re.compile(r"(?:AY\s*)?2026\s*[-–_/]\s*27", re.IGNORECASE)
_DOWNLOAD_PREFILL = re.compile(r"^\s*Download\s+Pre[- ]filled\s+Data\s*$", re.IGNORECASE)
_DOWNLOAD = re.compile(r"^\s*Download\s*$", re.IGNORECASE)
_NO_DATA = re.compile(
    r"no\s+(?:pre[- ]?filled\s+)?data\s+(?:is\s+)?available|no\s+records?\s+found|data\s+not\s+available",
    re.IGNORECASE,
)
_RETRYABLE_ERROR = re.compile(
    r"something\s+went\s+wrong|try\s+again|temporar(?:y|ily)|service\s+unavailable|technical\s+(?:error|issue)|network\s+error",
    re.IGNORECASE,
)
_PERMANENT_ERROR = re.compile(
    r"not\s+eligible|access\s+denied|unauthori[sz]ed|invalid\s+request",
    re.IGNORECASE,
)

# Deliberately conservative: these are schema metadata locations, not recursive searches.
_PAN_PATHS: tuple[tuple[str, ...], ...] = (
    ("personalInfo", "pan"),
    ("personalInfo", "PAN"),
    ("data", "personalInfo", "pan"),
    ("prefillData", "personalInfo", "pan"),
    ("ITR", "personalInfo", "pan"),
)
_AY_PATHS: tuple[tuple[str, ...], ...] = (
    ("assessmentYear",),
    ("assessment_year",),
    ("IncDeductionsOthIncCPC", "itrAy"),
    ("metadata", "assessmentYear"),
    ("metaData", "assessmentYear"),
    ("data", "assessmentYear"),
    ("data", "IncDeductionsOthIncCPC", "itrAy"),
    ("prefillData", "assessmentYear"),
    ("prefillData", "IncDeductionsOthIncCPC", "itrAy"),
    ("ITR", "assessmentYear"),
)
_PREFILL_MARKER_PATHS: tuple[tuple[str, ...], ...] = (
    ("personalInfo",),
    ("IncDeductionsOthIncCPC",),
    ("data", "personalInfo"),
    ("data", "IncDeductionsOthIncCPC"),
    ("prefillData", "personalInfo"),
    ("prefillData", "IncDeductionsOthIncCPC"),
)


class PrefillState(str, Enum):
    """Terminal states produced by a pre-fill download attempt."""

    DOWNLOADED = "downloaded"
    NO_DATA = "no_data"
    RETRYABLE_FAILURE = "retryable_failure"
    VALIDATION_FAILED = "validation_failed"
    SESSION_EXPIRED = "session_expired"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class PrefillOutcome:
    """Structured result of a standalone pre-fill download.

    Attributes:
        state: Terminal result state.
        path: Final validated artifact path, only for successful downloads.
        reason: Non-sensitive human-readable result detail.
        assessment_year: Assessment year requested from the portal.
    """

    state: PrefillState
    path: Optional[str] = None
    reason: str = ""
    ay: str = AY

    @property
    def assessment_year(self) -> str:
        """Return the requested assessment year under its descriptive alias."""
        return self.ay

    def to_dict(self) -> dict[str, Optional[str]]:
        """Return a JSON-safe representation without artifact contents."""
        result = asdict(self)
        result["state"] = self.state.value
        return result


async def download_prefill(
    page: Any,
    pan: str,
    download_dir: str | os.PathLike[str],
    assessment_year: str = AY,
    *,
    timeout_ms: int = 30_000,
    poll_interval: float = 0.1,
    log: Optional[Callable[[str], None]] = None,
) -> PrefillOutcome:
    """Download and validate the ITD pre-filled JSON for AY 2026-27.

    Args:
        page: An authenticated Playwright-compatible ITD page.
        pan: Expected taxpayer PAN. It is never emitted to logs.
        download_dir: Destination directory for the validated artifact.
        assessment_year: Assessment year; Phase Two supports only ``2026-27``.
        timeout_ms: One shared elapsed budget for the entire Prefill workflow.
        poll_interval: State polling interval in seconds.
        log: Optional privacy-safe status callback.

    Returns:
        A typed outcome. A path is exposed only after atomic validation succeeds.
    """
    if page is None:
        return _outcome(PrefillState.PERMANENT_FAILURE, "A browser page is required.", assessment_year)
    if not isinstance(pan, str) or not pan.strip():
        return _outcome(PrefillState.PERMANENT_FAILURE, "A PAN is required.", assessment_year)
    if assessment_year != AY:
        return _outcome(PrefillState.PERMANENT_FAILURE, "Unsupported assessment year.", assessment_year)
    if timeout_ms < 0 or poll_interval < 0:
        return _outcome(PrefillState.PERMANENT_FAILURE, "Invalid polling configuration.", assessment_year)

    partial: Optional[Path] = None
    deadline = MonotonicDeadline.after(timeout_ms)
    try:
        anchor = await resolve_itd_anchor(page)
        if await session_expired(anchor):
            return _outcome(PrefillState.SESSION_EXPIRED, "The portal session has expired.", assessment_year)

        menu = await _find_prefill_action(anchor, min(250, deadline.remaining_ms))
        if menu is None:
            _emit(log, "[PREFILL] Opening Income Tax Returns navigation.")
            navigation_budget = min(5_000, deadline.remaining_ms)
            try:
                await navigate_income_tax_returns(
                    anchor, timeout_ms=navigation_budget, log=log
                )
            except Exception as exc:
                _emit(
                    log,
                    "[PREFILL] Shared navigation did not expose the action; "
                    f"using local click fallback ({type(exc).__name__}).",
                )
            menu = await _find_prefill_action(
                anchor, min(500, deadline.remaining_ms)
            )

        if menu is None and not deadline.expired:
            menu = await _open_prefill_action_locally(anchor, deadline, log=log)

        if await session_expired(anchor):
            return _outcome(PrefillState.SESSION_EXPIRED, "The portal session has expired.", assessment_year)
        if menu is None:
            _emit(log, "[PREFILL] Download Pre-filled Data action was not found.")
            return _outcome(PrefillState.RETRYABLE_FAILURE, "Pre-filled data action was not found.", assessment_year)
        _emit(log, "[PREFILL] Download Pre-filled Data action ready.")
        _emit(log, "[PREFILL] Clicking Download Pre-filled Data action.")
        await menu.click(timeout=max(1, min(750, deadline.remaining_ms)))

        if await session_expired(anchor):
            return _outcome(PrefillState.SESSION_EXPIRED, "The portal session has expired.", assessment_year)
        _emit(log, "[PREFILL] Selecting and verifying Assessment Year.")
        selected = await _select_assessment_year(
            anchor, assessment_year, deadline.remaining_ms, log=log
        )
        if not selected:
            _emit(log, "[PREFILL] Assessment Year control was not ready or could not be verified.")
            return _outcome(PrefillState.RETRYABLE_FAILURE, "Assessment year control was not ready or could not be verified.", assessment_year)
        _emit(log, "[PREFILL] Assessment Year selected and verified.")

        state = await _wait_for_terminal_state(
            anchor, deadline.remaining_ms, poll_interval, log=log
        )
        if state is not None:
            _emit(log, f"[PREFILL] Terminal state: {state[0].value} — {state[1]}")
            return _outcome(state[0], state[1], assessment_year)

        _emit(log, "[PREFILL] Finding Download action.")
        button = await _find_semantic(
            anchor,
            _DOWNLOAD,
            (
                "//button[normalize-space(.)='Download']",
                "//a[normalize-space(.)='Download']",
                "//*[@role='button' and normalize-space(.)='Download']",
                "//input[translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='download']",
            ),
            deadline.remaining_ms,
        )
        if button is None:
            _emit(log, "[PREFILL] Download action was not found.")
            return _outcome(PrefillState.RETRYABLE_FAILURE, "Download action was not found.", assessment_year)

        destination = Path(download_dir)
        destination.mkdir(parents=True, exist_ok=True)
        final = destination / f"{pan.strip().upper()}-PREFILL-AY-2026_27.json"
        partial = Path(f"{final}.partial")
        if partial.exists():
            partial.unlink()

        _emit(log, "[PREFILL] Arming download listener and clicking Download.")
        # The listener is armed before the sole click which can initiate a download.
        download_budget_ms = max(1, deadline.remaining_ms)
        async with anchor.expect_download(timeout=download_budget_ms) as download_info:
            await button.click(timeout=min(750, download_budget_ms))
        download = await download_info.value
        await _bounded(download.save_as(str(partial)), deadline)

        _emit(log, "[PREFILL] Download received; validating JSON structure.")
        if not partial.exists() or partial.stat().st_size == 0:
            if partial.exists():
                partial.unlink()
            return _outcome(PrefillState.RETRYABLE_FAILURE, "The portal returned an empty download.", assessment_year)

        validation_error = _validate_json(partial, pan, assessment_year)
        if validation_error is not None:
            partial.unlink(missing_ok=True)
            return _outcome(PrefillState.VALIDATION_FAILED, validation_error, assessment_year)
        os.replace(partial, final)
        _emit(log, "[PREFILL] Validated pre-filled data download completed.")
        return PrefillOutcome(PrefillState.DOWNLOADED, str(final), "", assessment_year)
    except Exception as exc:
        try:
            if await session_expired(page):
                return _outcome(PrefillState.SESSION_EXPIRED, "The portal session has expired.", assessment_year)
        except Exception:
            pass
        if partial is not None:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
        message = str(exc).lower()
        state = PrefillState.RETRYABLE_FAILURE
        if "permission" in message or "invalid argument" in message:
            state = PrefillState.PERMANENT_FAILURE
        return _outcome(state, "The pre-filled data download did not complete.", assessment_year)


async def _find_prefill_action(page: Any, timeout_ms: int) -> Optional[Any]:
    """Find the actual Prefill leaf action under one short bounded probe."""
    return await _find_semantic(
        page,
        _DOWNLOAD_PREFILL,
        (
            "//*[normalize-space(.)='Download Pre-filled Data']",
            "//*[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))='download pre-filled data']",
            "//*[normalize-space(.)='Download Prefilled Data']",
        ),
        timeout_ms,
    )


async def _open_prefill_action_locally(
    page: Any,
    deadline: MonotonicDeadline,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[Any]:
    """Explicitly click ITD menu levels when hover-only navigation stalls."""
    efile = await _find_semantic(
        page,
        re.compile(r"^\s*e-File\s*$", re.IGNORECASE),
        ("a#e-File", "//*[normalize-space(.)='e-File']"),
        min(2_000, deadline.remaining_ms),
    )
    if efile is None:
        _emit(log, "[PREFILL] Local fallback could not find e-File.")
        return None
    try:
        await efile.click(timeout=max(1, min(750, deadline.remaining_ms)))
    except Exception:
        try:
            await efile.click(force=True, timeout=max(1, min(750, deadline.remaining_ms)))
        except Exception:
            return None

    returns = await _find_semantic(
        page,
        re.compile(r"^\s*Income\s+Tax\s+Returns\s*$", re.IGNORECASE),
        (
            "//*[normalize-space(.)='Income Tax Returns']",
            "//*[text()='Income Tax Returns']",
        ),
        min(2_000, deadline.remaining_ms),
    )
    if returns is None:
        _emit(log, "[PREFILL] Local fallback could not find Income Tax Returns.")
        return None
    try:
        await returns.click(timeout=max(1, min(750, deadline.remaining_ms)))
    except Exception:
        try:
            await returns.hover(timeout=max(1, min(750, deadline.remaining_ms)))
        except Exception:
            return None

    action = await _find_prefill_action(page, min(3_000, deadline.remaining_ms))
    if action is not None:
        _emit(log, "[PREFILL] Local click fallback exposed the Prefill action.")
    return action


async def _find_semantic(
    page: Any,
    name: re.Pattern[str],
    xpaths: Sequence[str],
    timeout_ms: int,
) -> Optional[Any]:
    """Find a visible control using roles, exact text, and normalized XPath."""
    deadline = MonotonicDeadline.after(timeout_ms)
    while True:
        candidates: list[Any] = []
        for role in ("link", "button", "menuitem"):
            try:
                candidates.append(page.get_by_role(role, name=name).first)
            except Exception:
                pass
        try:
            candidates.append(page.get_by_text(name, exact=True).first)
        except Exception:
            pass
        for xpath in xpaths:
            try:
                candidates.append(page.locator(xpath).first)
            except Exception:
                pass
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
    remaining = deadline.remaining_seconds
    if remaining <= 0:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError("Prefill workflow deadline expired.")
    return await asyncio.wait_for(awaitable, timeout=remaining)


async def _select_assessment_year(
    page: Any,
    assessment_year: str,
    timeout_ms: int,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Dynamically discover, select, and verify a native or custom AY control.

    The ITD "Download Pre-filled Data" page renders AY as a custom Angular/JSF
    combobox (``role="combobox"``) rather than a native ``<select>``. Unlike
    TRACES (which uses ``select#AssessmentYearDropDown`` in a frame), this page
    may surface the control in the main document or in an embedded frame, so
    every probe scans all frames. Custom comboboxes are driven by opening the
    trigger element and probing the resulting option panel for AY-matching text,
    which is robust against missing ``aria-label`` attributes.
    """
    deadline = MonotonicDeadline.after(timeout_ms)
    diagnosed = False
    while True:
        if not diagnosed:
            await _diagnose_ay_controls(page, log)
            diagnosed = True

        if await _select_native_ay(page, deadline, log=log):
            return True
        if deadline.expired:
            return False
        if await _select_combobox_ay(page, deadline, log=log):
            return True
        if deadline.expired:
            return False
        await deadline.sleep(0.1)


async def _select_native_ay(
    page: Any,
    deadline: MonotonicDeadline,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Locate and drive a native ``<select>`` containing AY options in any frame.

    Native selects appear on TRACES (``select#AssessmentYearDropDown``) and some
    legacy ITD surfaces. Each candidate is selected by visible label and then
    re-read to confirm the AY text is now the checked option.
    """
    for frame in _iter_frames(page):
        if deadline.expired:
            return False
        try:
            selects = frame.locator("select")
            count = int(await _bounded(selects.count(), deadline))
        except Exception:
            continue
        for index in range(count):
            if deadline.expired:
                return False
            try:
                control = selects.nth(index)
                labels = await _bounded(
                    control.locator("option").all_text_contents(), deadline
                )
                matching = next(
                    (label for label in labels if _AY_TEXT.search(str(label))), None
                )
                if matching is None:
                    continue
                action_ms = max(1, min(750, deadline.remaining_ms))
                await control.select_option(label=matching, timeout=action_ms)
                selected_text = await control.locator("option:checked").first.inner_text(
                    timeout=max(1, min(300, deadline.remaining_ms))
                )
                if _AY_TEXT.search(str(selected_text)):
                    _emit(log, "[PREFILL] AY selected via native <select>.")
                    return True
            except Exception as exc:
                _emit(log, f"[PREFILL] Native select AY attempt error: {type(exc).__name__}")
                continue
    return False


async def _select_combobox_ay(
    page: Any,
    deadline: MonotonicDeadline,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Drive a custom Angular/JSF combobox to choose the AY option.

    Custom comboboxes do not expose ``select_option`` and frequently lack the
    ``aria-label`` needed for ``get_by_role`` name matching, so we enumerate the
    visible combobox triggers, open each one, and probe the resulting option
    panel for an AY-matching option. Selecting it closes the panel and writes
    the value back to the trigger, which we verify before returning.
    """
    triggers = await _discover_combobox_triggers(page, deadline)
    for trigger, frame in triggers:
        if deadline.expired:
            return False
        try:
            if not await _try_combobox_option(
                trigger, frame, page, deadline, log=log
            ):
                await _close_combobox_panel(trigger, frame)
                continue
            value = await _control_value(trigger, deadline)
            if _AY_TEXT.search(value):
                _emit(log, "[PREFILL] AY selected via custom combobox.")
                return True
            # Close any panel left open by a non-matching combobox before the next try.
            await _close_combobox_panel(trigger, frame)
        except Exception as exc:
            _emit(log, f"[PREFILL] Custom combobox AY attempt error: {type(exc).__name__}")
            await _close_combobox_panel(trigger, frame)
            continue
    return False


async def _try_combobox_option(
    trigger: Any,
    frame: Any,
    page: Any,
    deadline: MonotonicDeadline,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Open one combobox and select a delayed AY option from any overlay root."""
    del log
    open_ms = max(1, min(750, deadline.remaining_ms))
    await trigger.click(timeout=open_ms)
    option_deadline = MonotonicDeadline.after(min(2_000, deadline.remaining_ms))
    while not option_deadline.expired:
        for root in _ordered_option_roots(page, frame):
            option = await _find_visible_ay_option(root, option_deadline)
            if option is None:
                continue
            await option.click(timeout=max(1, min(750, deadline.remaining_ms)))
            return True
        await option_deadline.sleep(0.05)
    return False


async def _discover_combobox_triggers(
    page: Any,
    deadline: MonotonicDeadline,
) -> list[tuple[Any, Any]]:
    """Collect AY-scoped controls first, then unique generic fallbacks."""
    scoped_selectors = (
        "[role='combobox'][aria-label*='assessment' i]",
        "[role='combobox'][aria-label*='year' i]",
        "[role='combobox'][name*='assessment' i]",
        "[role='combobox'][id*='assessment' i]",
        "[role='combobox'][formcontrolname*='assessment' i]",
        "[role='combobox'][placeholder*='assessment' i]",
        "mat-form-field:has-text('Assessment Year') [role='combobox']",
        ".mat-form-field:has-text('Assessment Year') [role='combobox']",
        ".form-group:has-text('Assessment Year') [role='combobox']",
        "label:has-text('Assessment Year') + * [role='combobox']",
    )
    generic_selectors = (
        "[role='combobox']",
        ".ui-selectonemenu-trigger",
        ".ng-select-container",
        ".mat-select-trigger",
        ".select2-choice",
        ".chosen-single",
    )
    scoped = await _visible_trigger_candidates(page, scoped_selectors, deadline)
    accessible: list[tuple[Any, Any]] = []
    accessible_names = (
        re.compile(r"assessment\s*year|\bAY\b", re.IGNORECASE),
        re.compile(r".*", re.DOTALL),
    )
    for root in _iter_frames(page):
        for accessible_name in accessible_names:
            try:
                candidate = root.get_by_role(
                    "combobox", name=accessible_name
                ).first
                if await candidate.is_visible(
                    timeout=max(1, min(150, deadline.remaining_ms))
                ):
                    accessible.append((candidate, root))
            except Exception:
                continue
    generic = await _visible_trigger_candidates(page, generic_selectors, deadline)
    return _unique_trigger_candidates((*scoped, *accessible, *generic))


async def _visible_trigger_candidates(
    page: Any,
    selectors: Sequence[str],
    deadline: MonotonicDeadline,
) -> list[tuple[Any, Any]]:
    """Return visible trigger candidates across unique page/frame roots."""
    candidates: list[tuple[Any, Any]] = []
    for root in _iter_frames(page):
        if deadline.expired:
            break
        for selector in selectors:
            try:
                locator = root.locator(selector)
                count = int(await _bounded(locator.count(), deadline))
            except Exception:
                continue
            for index in range(count):
                try:
                    candidate = locator.nth(index)
                    if await candidate.is_visible(
                        timeout=max(1, min(150, deadline.remaining_ms))
                    ):
                        candidates.append((candidate, root))
                except Exception:
                    continue
    return candidates


def _unique_trigger_candidates(
    candidates: Sequence[tuple[Any, Any]],
) -> list[tuple[Any, Any]]:
    """Deduplicate repeated selectors while preserving scoped priority."""
    unique: list[tuple[Any, Any]] = []
    seen: set[str] = set()
    for trigger, root in candidates:
        key = f"{id(root)}:{trigger!s}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((trigger, root))
    return unique


def _ordered_option_roots(page: Any, trigger_root: Any) -> tuple[Any, ...]:
    """Search trigger root, page overlay root, then remaining child frames."""
    roots = (trigger_root, page, *_iter_frames(page))
    unique: list[Any] = []
    seen: set[int] = set()
    for root in roots:
        marker = id(root)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(root)
    return tuple(unique)


async def _find_visible_ay_option(
    frame: Any,
    deadline: MonotonicDeadline,
) -> Optional[Any]:
    """Find a visible option element matching the AY text within the open panel."""
    try:
        accessible = frame.get_by_role("option", name=_AY_TEXT).first
        if await accessible.is_visible(
            timeout=max(1, min(150, deadline.remaining_ms))
        ):
            return accessible
    except Exception:
        pass
    option_selectors = (
        "[role='option']",
        "[role='listitem']",
        ".ui-selectonemenu-items li",
        ".ui-menu-item",
        ".ng-option",
        ".mat-option",
        ".select2-results__option",
        "li.ui-selectonemenu-item",
    )
    for selector in option_selectors:
        try:
            options = frame.locator(selector)
            count = int(await _bounded(options.count(), deadline))
        except Exception:
            continue
        for index in range(count):
            try:
                option = options.nth(index)
                text = await option.inner_text(timeout=max(1, min(150, deadline.remaining_ms)))
                if _AY_TEXT.search(str(text)) and await option.is_visible(timeout=max(1, min(150, deadline.remaining_ms))):
                    return option
            except Exception:
                continue
    return None


async def _close_combobox_panel(trigger: Any, frame: Any) -> None:
    """Dismiss an open combobox panel via Escape, then a backdrop click."""
    for action in (
        lambda: frame.keyboard.press("Escape"),
        lambda: frame.locator("body").click(position={"x": 0, "y": 0}, timeout=250),
    ):
        try:
            await action()
            break
        except Exception:
            continue


def _iter_frames(page: Any) -> tuple[Any, ...]:
    """Yield the page plus unique child frames, excluding its main frame."""
    roots: list[Any] = [page]
    main_frame = getattr(page, "main_frame", None)
    seen: set[int] = {id(page)}
    if main_frame is not None:
        seen.add(id(main_frame))
    for frame in tuple(getattr(page, "frames", ()) or ()):
        marker = id(frame)
        if marker in seen:
            continue
        seen.add(marker)
        roots.append(frame)
    return tuple(roots)


async def _verify_ay_displayed(
    frame: Any,
    deadline: MonotonicDeadline,
) -> bool:
    """Confirm that an AY string is currently shown in the active control."""
    try:
        text = await frame.locator("body").inner_text(
            timeout=max(1, min(300, deadline.remaining_ms))
        )
        return bool(_AY_TEXT.search(text))
    except Exception:
        return False


async def _diagnose_ay_controls(page: Any, log: Optional[Callable[[str], None]]) -> None:
    """Log structural metadata about AY-relevant controls without sensitive data."""
    frames = _iter_frames(page)
    _emit(log, f"[PREFILL] AY control diagnostic: frame_count={len(frames)}")

    total_selects = 0
    total_combos = 0
    for frame_index, frame in enumerate(frames):
        try:
            selects = frame.locator("select")
            count = int(await selects.count())
        except Exception:
            count = -1
        total_selects += max(0, count)
        for index in range(max(0, count)):
            try:
                control = selects.nth(index)
                ctrl_id = await control.get_attribute("id") or ""
                ctrl_name = await control.get_attribute("name") or ""
                aria_label = await control.get_attribute("aria-label") or ""
                option_count = await control.locator("option").count()
                labels = await control.locator("option").all_text_contents()
                has_ay = any(_AY_TEXT.search(str(label)) for label in labels)
                _emit(
                    log,
                    f"[PREFILL] frame[{frame_index}] select[{index}] "
                    f"id={ctrl_id!r} name={ctrl_name!r} aria_label={aria_label!r} "
                    f"options={option_count} has_ay_text={has_ay}",
                )
            except Exception as exc:
                _emit(log, f"[PREFILL] frame[{frame_index}] select[{index}] diagnostic error: {type(exc).__name__}")

        try:
            combos = frame.get_by_role("combobox")
            combo_count = int(await combos.count())
        except Exception:
            combo_count = -1
        total_combos += max(0, combo_count)
        if combo_count:
            _emit(log, f"[PREFILL] frame[{frame_index}] combobox_count={combo_count}")

    _emit(log, f"[PREFILL] AY control diagnostic: total_select_count={total_selects}")
    _emit(log, f"[PREFILL] AY control diagnostic: total_combobox_count={total_combos}")



async def _control_value(control: Any, deadline: MonotonicDeadline) -> str:
    """Read a custom/native combobox value within the shared deadline."""
    for attribute in ("aria-valuetext", "data-value", "value"):
        try:
            value = await _bounded(control.get_attribute(attribute), deadline)
            if value:
                return str(value)
        except Exception:
            continue
    try:
        text = await control.inner_text(
            timeout=max(1, min(300, deadline.remaining_ms))
        )
        if text:
            return str(text)
    except Exception:
        pass
    try:
        return str(await _bounded(control.input_value(), deadline))
    except Exception:
        return ""


async def _wait_for_terminal_state(
    page: Any,
    timeout_ms: int,
    poll_interval: float,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[tuple[PrefillState, str]]:
    """Poll bounded portal feedback until ready or a terminal state appears."""
    deadline = MonotonicDeadline.after(timeout_ms)
    loading_seen = False
    while True:
        if await session_expired(page):
            return PrefillState.SESSION_EXPIRED, "The portal session has expired."
        text = await _body_text(page)
        if _NO_DATA.search(text):
            return PrefillState.NO_DATA, "No pre-filled data is available for the assessment year."
        if _PERMANENT_ERROR.search(text):
            return PrefillState.PERMANENT_FAILURE, "The portal rejected the pre-filled data request."
        if _RETRYABLE_ERROR.search(text):
            return PrefillState.RETRYABLE_FAILURE, "The portal reported a temporary error."
        loading = bool(re.search(r"loading|please\s+wait|processing", text, re.IGNORECASE))
        loading_seen = loading_seen or loading
        if not loading:
            _emit(log, "[PREFILL] Portal ready — no loading state detected.")
            return None
        if deadline.expired:
            reason = "The portal remained in a loading state." if loading_seen else "The portal did not become ready."
            return PrefillState.RETRYABLE_FAILURE, reason
        await deadline.sleep(poll_interval)


async def _body_text(page: Any) -> str:
    """Read body text without allowing diagnostics to raise."""
    try:
        return str(await page.locator("body").inner_text(timeout=1))
    except Exception:
        try:
            value = page.evaluate("() => document.body ? document.body.innerText : ''")
            if asyncio.iscoroutine(value):
                value = await value
            return str(value)
        except Exception:
            return ""


def _validate_json(path: Path, expected_pan: str, assessment_year: str) -> Optional[str]:
    """Parse JSON and validate only explicitly recognized identity metadata."""
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            payload = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return "Downloaded pre-filled data is not valid JSON."
    if not isinstance(payload, Mapping):
        return "Downloaded pre-filled data has an invalid root structure."

    pan_values = _recognized_values(payload, _PAN_PATHS)
    ay_values = _recognized_values(payload, _AY_PATHS)
    markers = _recognized_values(payload, _PREFILL_MARKER_PATHS)
    if not pan_values and not ay_values and not markers:
        return "Downloaded JSON does not have a recognized pre-filled data structure."

    expected = re.sub(r"\s+", "", expected_pan).upper()
    if pan_values and any(re.sub(r"\s+", "", str(value)).upper() != expected for value in pan_values):
        return "Downloaded pre-filled data belongs to a different PAN."

    ay_values = _recognized_values(payload, _AY_PATHS)
    if ay_values and any(_normalize_ay(value) != _normalize_ay(assessment_year) for value in ay_values):
        return "Downloaded pre-filled data has a different assessment year."
    return None


def _recognized_values(root: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> list[Any]:
    """Read values from explicit paths with case-insensitive object keys."""
    values: list[Any] = []
    for path in paths:
        current: Any = root
        found = True
        for component in path:
            if not isinstance(current, Mapping):
                found = False
                break
            key = next((key for key in current if str(key).casefold() == component.casefold()), None)
            if key is None:
                found = False
                break
            current = current[key]
        if found and current not in (None, "") and current not in values:
            values.append(current)
    return values


def _normalize_ay(value: Any) -> str:
    """Normalize a recognized AY metadata value for conservative comparison."""
    text = str(value).strip().upper().replace("ASSESSMENT YEAR", "").replace("AY", "")
    digits = re.sub(r"\D", "", text)
    if len(digits) == 4:
        start = int(digits)
        return f"{start:04d}{(start + 1) % 100:02d}"
    if len(digits) == 6:
        return digits
    if len(digits) == 8 and digits[:4] == "2026" and digits[4:] == "2027":
        return "202627"
    return digits or text


def _outcome(state: PrefillState, reason: str, assessment_year: str) -> PrefillOutcome:
    """Build a failure outcome that never presents a partial artifact as final."""
    return PrefillOutcome(state=state, path=None, reason=reason, ay=assessment_year)


def _emit(log: Optional[Callable[[str], None]], message: str) -> None:
    """Emit only constant, privacy-safe operational messages."""
    if log is not None:
        log(message)
