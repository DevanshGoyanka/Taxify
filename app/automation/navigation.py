"""Reusable, deadline-bounded Playwright portal navigation primitives."""

from __future__ import annotations

import asyncio
import inspect
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence

Clock = Callable[[], float]
LogCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class MonotonicDeadline:
    """A shared elapsed-time deadline suitable for multiple async probes."""

    expires_at: float
    clock: Clock = time.monotonic

    @classmethod
    def after(cls, timeout_ms: int, clock: Clock = time.monotonic) -> "MonotonicDeadline":
        """Create a deadline ``timeout_ms`` from the current monotonic time.

        Args:
            timeout_ms: Non-negative timeout in milliseconds.
            clock: Monotonic clock function.

        Returns:
            A deadline sharing one elapsed-time budget.

        Raises:
            ValueError: If ``timeout_ms`` is negative.
        """
        if timeout_ms < 0:
            raise ValueError("Timeout cannot be negative.")
        return cls(clock() + timeout_ms / 1000.0, clock)

    @property
    def remaining_seconds(self) -> float:
        """Return the non-negative remaining duration in seconds."""
        return max(0.0, self.expires_at - self.clock())

    @property
    def remaining_ms(self) -> int:
        """Return the non-negative remaining duration in milliseconds."""
        return max(0, int(self.remaining_seconds * 1000))

    @property
    def expired(self) -> bool:
        """Return whether the deadline has elapsed."""
        return self.remaining_seconds <= 0.0

    async def sleep(self, interval_seconds: float) -> None:
        """Sleep for no longer than the remaining shared budget.

        Args:
            interval_seconds: Desired non-negative sleep duration.
        """
        if interval_seconds < 0:
            raise ValueError("Sleep interval cannot be negative.")
        await asyncio.sleep(min(interval_seconds, self.remaining_seconds))


@dataclass(slots=True)
class PortalHandle:
    """Track ownership and restoration state for an external portal page.

    Attributes:
        origin_page: Borrowed ITD page from which navigation began.
        target_page: Current external portal page.
        child_tab: Whether the target is an owned child tab.
        anchor_replaced: Whether same-tab navigation replaced the ITD anchor.
        portal_owner: Page/context owner used for lifecycle accountability.
        origin_url: URL used to restore a replaced same-tab anchor.
    """

    origin_page: Any
    target_page: Any
    child_tab: bool
    anchor_replaced: bool
    portal_owner: Any
    origin_url: str
    _cleaned: bool = False

    async def cleanup(self, timeout_ms: int = 30_000) -> Any:
        """Close only owned tabs and preserve or recreate the borrowed ITD anchor.

        Args:
            timeout_ms: Maximum navigation time when restoring an anchor.

        Returns:
            The usable ITD anchor page after cleanup.

        Raises:
            ValueError: If ``timeout_ms`` is negative.
        """
        if timeout_ms < 0:
            raise ValueError("Timeout cannot be negative.")
        if self._cleaned:
            return self.origin_page

        if self.child_tab:
            if self.target_page is not self.origin_page and not _page_is_closed(self.target_page):
                await self.target_page.close()
        elif self.anchor_replaced:
            self.origin_page = await restore_dashboard_anchor(
                self.origin_page, self.origin_url, timeout_ms=timeout_ms
            )
        self._cleaned = True
        return self.origin_page


async def find_frame_global(
    page: Any,
    selectors: str | Sequence[str],
    timeout_ms: int = 3_000,
    poll_interval: float = 0.05,
) -> Optional[Any]:
    """Find a frame containing a visible selector under one global timeout.

    Frames and selectors are repeatedly rescanned, so dynamically attached
    frames participate without multiplying the timeout by frame count.

    Args:
        page: Playwright-like page exposing ``frames``.
        selectors: One selector or ordered selector alternatives.
        timeout_ms: Total elapsed timeout across every frame and selector.
        poll_interval: Delay between scans in seconds.

    Returns:
        The first matching frame, or ``None`` at the deadline.
    """
    if timeout_ms < 0 or poll_interval < 0:
        raise ValueError("Timeout and poll interval cannot be negative.")
    choices = (selectors,) if isinstance(selectors, str) else tuple(selectors)
    if not choices:
        return None
    deadline = MonotonicDeadline.after(timeout_ms)
    while True:
        for frame in tuple(getattr(page, "frames", ())):
            for selector in choices:
                try:
                    locator = frame.locator(selector).first
                    if await locator.is_visible(timeout=1):
                        return frame
                except Exception:
                    continue
        if deadline.expired:
            return None
        await deadline.sleep(poll_interval)


async def wait_for_overlay_clearance(
    page: Any,
    timeout_ms: int = 30_000,
    selectors: Sequence[str] = (
        ".customLoaderBackdrop",
        ".loading-overlay",
        "[aria-busy='true']",
    ),
    poll_interval: float = 0.05,
) -> bool:
    """Wait until all known visible loader/overlay elements have cleared."""
    deadline = MonotonicDeadline.after(timeout_ms)
    while True:
        blocked = False
        for selector in selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=1):
                    blocked = True
                    break
            except Exception:
                continue
        if not blocked:
            return True
        if deadline.expired:
            return False
        await deadline.sleep(poll_interval)


async def open_hamburger(
    page: Any,
    timeout_ms: int = 5_000,
    log: Optional[LogCallback] = None,
) -> bool:
    """Open the first visible dashboard hamburger without serial waits."""
    selectors = (
        "#hamburgerOpen",
        "button[aria-label*='main menu' i]",
        "button[aria-label*='menu' i]",
        "[role='button'][aria-label*='menu' i]",
        ".hamburger",
    )
    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass
    locator = await _first_visible(page, selectors, MonotonicDeadline.after(timeout_ms))
    if locator is None:
        return False
    try:
        await locator.click(timeout=max(1, timeout_ms))
    except Exception:
        await locator.click(force=True, timeout=max(1, timeout_ms))
    if log is not None:
        log("Dashboard navigation menu opened.")
    return True


async def session_expired(page: Any) -> bool:
    """Detect login redirects and explicit session-expiry portal states."""
    url = str(getattr(page, "url", "")).lower()
    if any(token in url for token in ("/login", "sessionexpired", "session-expired")):
        return True
    text = await _body_text(page)
    return bool(
        re.search(
            r"session\s+(?:has\s+)?expired|your session timed out|login again|please log in",
            text,
            re.IGNORECASE,
        )
    )


async def restore_dashboard_anchor(
    page: Any,
    anchor_url: str,
    timeout_ms: int = 30_000,
) -> Any:
    """Restore a same-tab ITD anchor, recreating it in the same context if needed."""
    if not anchor_url:
        raise ValueError("An ITD anchor URL is required for restoration.")
    context = page.context
    anchor = page
    if _page_is_closed(page):
        anchor = await context.new_page()
    current_url = str(getattr(anchor, "url", ""))
    if current_url != anchor_url:
        try:
            await anchor.goto(anchor_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            if not _page_is_closed(anchor):
                raise
            anchor = await context.new_page()
            await anchor.goto(anchor_url, wait_until="domcontentloaded", timeout=timeout_ms)
    return anchor


async def resolve_itd_anchor(page: Any) -> Any:
    """Return the live authenticated ITD anchor from the page's context.

    This rebinds callers when same-tab cleanup had to recreate a closed page.
    It never creates another page because ``PortalHandle.cleanup`` owns that
    responsibility while retaining the original authenticated context.

    Args:
        page: The previous ITD page reference, which may now be closed.

    Returns:
        A live page on the Income Tax e-filing portal.

    Raises:
        RuntimeError: If no live ITD anchor exists in the browser context.
    """
    context = page.context
    for candidate in reversed(tuple(getattr(context, "pages", ()))):
        if _page_is_closed(candidate):
            continue
        candidate_url = str(getattr(candidate, "url", "")).lower()
        if "eportal.incometax.gov.in" in candidate_url:
            return candidate
    if not _page_is_closed(page):
        return page
    raise RuntimeError("No live authenticated ITD anchor exists in this context.")


async def navigate_income_tax_returns(
    page: Any,
    timeout_ms: int = 30_000,
    log: Optional[LogCallback] = None,
) -> Any:
    """Open ``e-File`` then ``Income Tax Returns`` dashboard menus.

    Mirrors the proven prefill JSON download navigation: uses
    ``_find_semantic``-style discovery (roles → text → XPath) and
    ``click()`` with ``force=True`` fallback (not hover). This is
    the exact pattern that works reliably for the prefill downloader.
    """
    import re as _re
    import asyncio as _asyncio

    deadline = MonotonicDeadline.after(timeout_ms)

    # Step 1: Find and click e-File menu
    if log is not None:
        log("[NAV] Finding e-File menu.")
    efile = await _nav_find_semantic(
        page,
        _re.compile(r"^\s*e-File\s*$", _re.IGNORECASE),
        ("a#e-File", "//*[normalize-space(.)='e-File']"),
        min(2_000, deadline.remaining_ms),
    )
    if efile is None:
        raise RuntimeError("e-File dashboard menu was not found before navigation timeout.")
    try:
        await efile.click(timeout=max(1, min(750, deadline.remaining_ms)))
    except Exception:
        try:
            await efile.click(force=True, timeout=max(1, min(750, deadline.remaining_ms)))
        except Exception:
            raise RuntimeError("e-File menu click failed.")
    await _asyncio.sleep(0.5)

    # Step 2: Find and click Income Tax Returns submenu
    if log is not None:
        log("[NAV] Finding Income Tax Returns submenu.")
    returns = await _nav_find_semantic(
        page,
        _re.compile(r"^\s*Income\s+Tax\s+Returns\s*$", _re.IGNORECASE),
        (
            "//*[normalize-space(.)='Income Tax Returns']",
            "//*[text()='Income Tax Returns']",
        ),
        min(2_000, deadline.remaining_ms),
    )
    if returns is None:
        raise RuntimeError(
            "Income Tax Returns submenu was not found before navigation timeout."
        )
    try:
        await returns.click(timeout=max(1, min(750, deadline.remaining_ms)))
    except Exception:
        try:
            await returns.hover(timeout=max(1, min(750, deadline.remaining_ms)))
        except Exception:
            raise RuntimeError("Income Tax Returns submenu click failed.")
    await _asyncio.sleep(0.5)

    if log is not None:
        log("[NAV] Income Tax Returns submenu ready.")
    return returns


async def _nav_find_semantic(
    page: Any,
    name: "re.Pattern[str]",
    xpaths: Sequence[str],
    timeout_ms: int,
) -> Optional[Any]:
    """Find a visible control using roles, exact text, and normalized XPath.

    This is the same discovery pattern used by the prefill downloader's
    ``_find_semantic``: try ``get_by_role`` (link/button/menuitem), then
    ``get_by_text``, then XPath fallbacks, polling under one shared deadline.
    """
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


async def race_portal_navigation(
    origin_page: Any,
    trigger: Callable[[], Awaitable[None]],
    portal_url: str | re.Pattern[str],
    timeout_ms: int = 30_000,
    confirm: Optional[Callable[[], Awaitable[None]]] = None,
    error_patterns: Sequence[str] = (
        r"unable to redirect",
        r"something went wrong",
        r"portal (?:is )?unavailable",
    ),
    poll_interval: float = 0.05,
) -> PortalHandle:
    """Race child-tab, same-tab, confirmation, and explicit error outcomes.

    Args:
        origin_page: Borrowed ITD anchor page.
        trigger: Async callback that initiates portal navigation.
        portal_url: Regex string or compiled expression identifying the target.
        timeout_ms: One total timeout for all concurrent outcomes.
        confirm: Optional async redirect-confirmation callback.
        error_patterns: Body-text regular expressions representing terminal errors.
        poll_interval: Polling interval for URL and error-state observation.

    Returns:
        Ownership metadata for the successfully reached portal.

    Raises:
        RuntimeError: If an explicit error appears or no portal wins the race.
    """
    if timeout_ms < 0 or poll_interval < 0:
        raise ValueError("Timeout and poll interval cannot be negative.")
    deadline = MonotonicDeadline.after(timeout_ms)
    original_url = str(getattr(origin_page, "url", ""))
    context = origin_page.context
    known_pages = tuple(getattr(context, "pages", ()))
    pattern = re.compile(portal_url, re.IGNORECASE) if isinstance(portal_url, str) else portal_url

    await trigger()
    confirm_task: Optional[asyncio.Task[None]] = None
    if confirm is not None:
        confirm_task = asyncio.create_task(confirm())

    try:
        while not deadline.expired:
            for candidate in tuple(getattr(context, "pages", ())):
                if candidate not in known_pages and pattern.search(str(getattr(candidate, "url", ""))):
                    return PortalHandle(origin_page, candidate, True, False, context, original_url)
            if pattern.search(str(getattr(origin_page, "url", ""))):
                return PortalHandle(origin_page, origin_page, False, True, context, original_url)
            body = await _body_text(origin_page)
            for error_pattern in error_patterns:
                if re.search(error_pattern, body, re.IGNORECASE):
                    raise RuntimeError("Portal navigation failed with an explicit portal error.")
            await deadline.sleep(poll_interval)
        raise RuntimeError("Portal navigation timed out before a target page appeared.")
    finally:
        if confirm_task is not None:
            if not confirm_task.done():
                confirm_task.cancel()
            await asyncio.gather(confirm_task, return_exceptions=True)


async def _first_visible(page: Any, selectors: Iterable[str], deadline: MonotonicDeadline) -> Optional[Any]:
    """Return the first visible locator under a shared deadline."""
    choices = tuple(selectors)
    while True:
        for selector in choices:
            try:
                candidate = page.locator(selector).first
                if await candidate.is_visible(timeout=1):
                    return candidate
            except Exception:
                continue
        if deadline.expired:
            return None
        await deadline.sleep(0.05)


async def _semantic_locator(
    page: Any,
    name: str,
    deadline: MonotonicDeadline,
    selectors: Sequence[str] = (),
) -> Optional[Any]:
    """Find a named menu through roles, text, and proven selector fallbacks."""
    while True:
        candidates: list[Any] = []
        for factory in (
            lambda: page.get_by_role(
                "link", name=re.compile(rf"^{re.escape(name)}$", re.I)
            ).first,
            lambda: page.get_by_role(
                "button", name=re.compile(rf"^{re.escape(name)}$", re.I)
            ).first,
            lambda: page.get_by_text(name, exact=True).first,
        ):
            try:
                candidates.append(factory())
            except Exception:
                continue
        for selector in selectors:
            try:
                candidates.append(page.locator(selector).first)
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


async def _hover_or_click(locator: Any, timeout_ms: int) -> None:
    """Hover a semantic menu item without ever triggering a click navigation.

    On the ITD Angular SPA, menu items are ``<a>`` tags with real ``href``
    values. A click fallback (used previously when ``hover()`` timed out)
    navigates the browser to that href, which reloads the Angular route and
    can drop a rate-limited session. This helper now attempts hover exactly
    once, then falls back to a JS ``mouseover``/``mouseenter`` dispatch —
    never a click, and never a retry loop (repeated hovers make the Angular
    menu flicker open/closed, which triggers the portal's anti-automation
    protection and can cause a logout).
    """
    budget = max(1, min(2_000, timeout_ms))
    try:
        await locator.hover(timeout=budget)
        return
    except Exception:
        pass
    # Final fallback: dispatch synthetic mouse events via JS — does not
    # navigate, but still signals the Angular menu directive to expand.
    try:
        handle = await locator.element_handle(timeout=budget)
        if handle is not None:
            await handle.evaluate(
                "(el) => {"
                "el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));"
                "el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));"
                "}"
            )
    except Exception:
        pass


async def _body_text(page: Any) -> str:
    """Read body text without allowing diagnostics to block navigation."""
    try:
        result = page.evaluate(
            "() => document.body ? document.body.innerText : ''"
        )
        if inspect.isawaitable(result):
            result = await result
        return str(result)
    except Exception:
        try:
            result = page.locator("body").inner_text(timeout=1)
            if inspect.isawaitable(result):
                result = await result
            return str(result)
        except Exception:
            return ""


def _page_is_closed(page: Any) -> bool:
    """Return a Playwright-like page's closed state safely."""
    try:
        return bool(page.is_closed())
    except Exception:
        return False


async def dismiss_portal_modals(
    page: Any,
    *,
    max_rounds: int = 5,
    log: Optional[LogCallback] = None,
) -> None:
    """Dismiss ITD portal security/logout/notification modals.

    Ported from the NRITAX portal-fetch service. The ITD portal shows
    several interstitial popups during automation that, if not dismissed,
    block all further interaction and can close the session:

    1. ``"Sure you want to Logout?"`` confirmation — click ``No`` to stay.
    2. ``#securityReasonPopup`` — a security notice; click ``OK``/``No``
       depending on whether the text mentions logout.
    3. ``#continueBtnNav`` / ``#confirmBtnFooter`` / ``#efNotificationPopUp_continue``
       — generic notification continue buttons; click them to proceed.

    This helper loops up to ``max_rounds`` times because multiple modals can
    stack. Each round re-checks all three categories. It never raises — a
    failure to dismiss is best-effort.
    """
    for _ in range(max_rounds):
        # 1. "Sure you want to Logout?" → click No
        try:
            logout_text = page.get_by_text(
                re.compile(r"sure you want to Logout", re.I)
            ).first
            if await logout_text.is_visible(timeout=400):
                no_btn = page.get_by_role("button", name=re.compile(r"^no$", re.I)).first
                if await no_btn.is_visible(timeout=300):
                    await no_btn.click(force=True)
                    await asyncio.sleep(0.4)
                    continue
        except Exception:
            pass

        # 2. #securityReasonPopup
        try:
            security = page.locator(
                "#securityReasonPopup.modal.show, "
                "#securityReasonPopup.show, "
                "#securityReasonPopup"
            ).first
            if await security.is_visible(timeout=400):
                text = ""
                try:
                    text = await security.inner_text(timeout=200)
                except Exception:
                    pass
                if re.search(r"logout", text or "", re.I):
                    no_btn = security.get_by_role(
                        "button", name=re.compile(r"^no$", re.I)
                    ).first
                    if await no_btn.is_visible(timeout=300):
                        await no_btn.click(force=True)
                        await asyncio.sleep(0.3)
                        continue
                else:
                    btn = security.get_by_role(
                        "button",
                        name=re.compile(r"ok|continue|close|got it|confirm|agree", re.I),
                    ).first
                    if await btn.is_visible(timeout=500):
                        await btn.click(force=True)
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        try:
                            await page.keyboard.press("Escape")
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass
                        continue
        except Exception:
            pass

        # 3. Generic notification continue buttons
        try:
            confirm = page.locator(
                "#continueBtnNav, #confirmBtnFooter, #efNotificationPopUp_continue"
            ).first
            if await confirm.is_visible(timeout=250):
                await confirm.click(force=True)
                await asyncio.sleep(0.25)
                continue
        except Exception:
            pass

        break
