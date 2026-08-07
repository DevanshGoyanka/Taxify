import asyncio
from collections.abc import Callable, Sequence

from playwright.async_api import BrowserContext, Locator, Page

from app.automation.downloader import update_browser_status
from app.automation.timing import AutomationTimeline


LogCallback = Callable[[str], None]


def _authentication_error(body_text: str, url: str = "") -> RuntimeError | None:
    """Classify terminal authentication states from portal text and URL.

    Args:
        body_text: Visible portal text. It must not be logged by this helper.
        url: Current portal URL used only to detect an OTP route.

    Returns:
        A safe RuntimeError for a terminal state, otherwise ``None``.
    """
    text = body_text.lower()
    lowered_url = url.lower()
    if "account has been locked" in text or (
        "e-filing account" in text and "locked" in text
    ):
        return RuntimeError(
            "ACCOUNT LOCKED: This e-filing account has been locked due to security reasons. "
            "The client must unlock their account at the ITD portal before it can be automated."
        )
    if "pan does not exist" in text or "pan is not registered" in text:
        return RuntimeError(
            "AUTHENTICATION FAILED: PAN does not exist on the ITD portal. "
            "Please verify the PAN is correct and registered at eportal.incometax.gov.in."
        )
    if "otpoptions" in lowered_url or any(
        marker in text
        for marker in (
            "enter otp",
            "otp has been sent",
            "one time password",
            "captcha",
            "verify you are human",
        )
    ):
        return RuntimeError(
            "AUTHENTICATION FAILED: The ITD portal requires OTP or human verification. "
            "Automated login cannot continue; log in manually or update the portal settings."
        )
    return None


async def _dump_inputs(page: Page, log: LogCallback) -> None:
    """Log value-free control metadata after a terminal login failure.

    Args:
        page: Failed Playwright login page.
        log: Credential-safe logging callback.
    """
    try:
        info = await page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('input, button, a, [role="button"]')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) continue;
                const isInput = el.tagName.toLowerCase() === 'input';
                out.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    text: isInput
                        ? ''
                        : (el.innerText || '').trim().replace(/\\s+/g,' ').slice(0,60),
                });
            }
            return { controls: out };
        }""")
        log("[Auth] --- Page diagnostics (values omitted) ---")
        for control in info.get("controls", []):
            log(f"[Auth]   {control}")
        log("[Auth] --- End diagnostics ---")
    except Exception as exc:
        log(f"[Auth] diagnostics unavailable: {type(exc).__name__}")


async def _first_visible(
    page: Page,
    selectors: Sequence[str],
    timeout: int,
    poll_interval: float = 0.05,
) -> Locator | None:
    """Return the first visible locator under one shared elapsed deadline.

    Args:
        page: Playwright page containing candidate controls.
        selectors: Alternative selectors representing the same semantic control.
        timeout: Total timeout in milliseconds across all selectors.
        poll_interval: Delay between non-blocking scans in seconds.

    Returns:
        The first visible locator, or ``None`` when the shared deadline expires.
    """
    if timeout <= 0 or not selectors:
        return None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout / 1000)
    while True:
        for selector in selectors:
            candidates = page.locator(selector)
            try:
                count = await candidates.count()
            except Exception:
                continue
            for index in range(count):
                locator = candidates.nth(index)
                try:
                    if (
                        await locator.is_visible(timeout=0)
                        and await locator.is_enabled(timeout=0)
                    ):
                        return locator
                except Exception:
                    continue
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        await asyncio.sleep(min(poll_interval, remaining))


async def _click_btn(
    page: Page,
    log: LogCallback,
    timeout: int = 5000,
    selectors: Sequence[str] = (
        "button:has-text('Continue')",
        "button[type='submit']",
    ),
) -> bool:
    """Click the first enabled semantic button under one shared deadline.

    Args:
        page: Playwright page containing the button.
        log: Credential-safe logging callback.
        timeout: Total timeout in milliseconds across all alternatives.
        selectors: Alternative selectors for the same semantic action.

    Returns:
        ``True`` if a button was clicked, otherwise ``False``.
    """
    button = await _first_visible(page, selectors, timeout)
    if button is None:
        return False
    log("[Auth] Clicking portal Continue control.")
    try:
        await button.click(timeout=max(1, timeout))
        return True
    except Exception:
        return False


async def _advance_from_sam(
    page: Page,
    log: LogCallback,
    timeout: int = 15000,
    poll_interval: float = 0.05,
) -> str:
    """Advance from SAM without waiting after the next stage is already ready.

    The ITD portal varies between requiring a Continue click and advancing
    automatically after the SAM checkbox is selected. This helper races the
    next-stage controls against an actionable Continue button under one shared
    deadline.

    Args:
        page: Playwright page on the SAM step.
        log: Credential-safe logging callback.
        timeout: Total elapsed deadline in milliseconds.
        poll_interval: Delay between non-blocking scans in seconds.

    Returns:
        ``"next-stage"`` when password/method controls are ready,
        ``"clicked"`` when Continue was clicked, or ``"timeout"``.
    """
    if timeout <= 0:
        return "timeout"
    next_stage_selectors = (
        "id=loginPasswordField",
        "xpath=//label[contains(normalize-space(.), 'Password') and not(contains(normalize-space(.), 'OTP'))]",
        "input[type='radio']#mat-radio-0-input",
        "input[type='radio']:first-of-type",
    )
    continue_selectors = (
        "button:has-text('Continue')",
        "button[type='submit']",
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout / 1000)

    while True:
        next_stage = await _first_visible(
            page,
            next_stage_selectors,
            timeout=1,
            poll_interval=0,
        )
        if next_stage is not None:
            return "next-stage"

        continue_button = await _first_visible(
            page,
            continue_selectors,
            timeout=1,
            poll_interval=0,
        )
        if continue_button is not None:
            log("[Auth] Clicking SAM Continue control.")
            try:
                await continue_button.click(timeout=2000)
                return "clicked"
            except Exception:
                pass

        remaining = deadline - loop.time()
        if remaining <= 0:
            return "timeout"
        await asyncio.sleep(min(poll_interval, remaining))


# ── Main login function ───────────────────────────────────────────────────────

async def login_itd(
    user_id: str,
    password: str,
    log_callback: LogCallback,
    context: BrowserContext,
    is_running: Callable[[], bool] | None = None,
    timeline: AutomationTimeline | None = None,
) -> Page:
    """Log in to ITD using the proven PAN, SAM, password sequence.

    Args:
        user_id: Taxpayer PAN used as the ITD user ID.
        password: ITD portal password. It is never logged.
        log_callback: Credential-safe progress logger.
        context: Isolated Playwright browser context.
        is_running: Optional cancellation predicate.
        timeline: Optional monotonic workflow timeline.

    Returns:
        Authenticated ITD dashboard page.
    """
    uid_masked = (user_id[:3] + "XXXXXXX") if user_id and len(user_id) >= 3 else "UNKNOWN"
    auth_timeline = timeline or AutomationTimeline(log_callback)

    auth_timeline.mark("login page requested")
    log_callback("[Auth] Opening new page for ITD login...")
    page = await context.new_page()
    await update_browser_status(page, "Auth: Connecting to ITD Portal...")
    page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))

    try:
        return await _do_login(
            page,
            user_id,
            uid_masked,
            password,
            log_callback,
            is_running,
            auth_timeline,
        )
    except Exception:
        # Close the orphaned login page so failed clients don't leak tabs.
        try:
            await page.close()
        except Exception:
            pass
        raise


async def _do_login(
    page: Page,
    user_id: str,
    uid_masked: str,
    password: str,
    log_callback: LogCallback,
    is_running: Callable[[], bool] | None = None,
    timeline: AutomationTimeline | None = None,
) -> Page:
    """Execute the established ITD login sequence on an existing page."""
    auth_timeline = timeline or AutomationTimeline(log_callback)

    _ITD_LOGIN = "https://eportal.incometax.gov.in/iec/foservices/#/login"
    for _nav_attempt in range(1, 4):
        try:
            log_callback(f"[Auth] Loading ITD Portal{f' (retry {_nav_attempt})' if _nav_attempt > 1 else ''}...")
            await page.goto(_ITD_LOGIN, wait_until="domcontentloaded", timeout=90000)
            auth_timeline.mark("login page ready")
            break
        except Exception as _nav_err:
            err_str = str(_nav_err)
            # Transient network errors — retry with a short backoff
            if any(k in err_str for k in ("ERR_EMPTY_RESPONSE", "ERR_CONNECTION_RESET",
                                           "ERR_CONNECTION_REFUSED", "ERR_NAME_NOT_RESOLVED",
                                           "ERR_TIMED_OUT", "net::")):
                if _nav_attempt < 3:
                    log_callback(f"[Auth] Portal unreachable ({err_str.split(chr(10))[0].strip()}) — retrying in 5 s…")
                    await asyncio.sleep(5)
                    continue
            raise  # non-network error or final attempt — propagate

    # Real Chrome keeps background connections alive so networkidle never fires.
    # domcontentloaded is sufficient; wait for the Angular app to mount the login form.
    await asyncio.sleep(3)

    # ── Maintenance check ────────────────────────────────────────────────────
    # The portal serves a plain HTML maintenance page instead of the Angular
    # app during downtime. Detect it early so we show a clear status.
    try:
        body_text = (await page.inner_text("body")).lower()
        if "maintenance" in body_text or "website will be down" in body_text or "maintance" in body_text:
            import re as _re
            # Try to extract the window from the page text
            raw = await page.inner_text("body")
            m = _re.search(r"([\d]{1,2}\s+\w+\s+\d{4}[^.]*?to[^.]*?IST)", raw, _re.IGNORECASE)
            window = f" ({m.group(1).strip()})" if m else ""
            raise RuntimeError(
                f"ITD portal is under scheduled maintenance{window}. "
                f"Try again after the maintenance window."
            )
    except RuntimeError:
        raise
    except Exception:
        pass  # page.inner_text failed (e.g. blank page) — proceed normally

    # ── Step 1: Fill PAN ─────────────────────────────────────────────────────
    log_callback(f"[Auth] Entering User ID: {uid_masked}")
    await update_browser_status(page, f"Auth: Entering User ID ({uid_masked})...")

    await page.fill("id=panAdhaarUserId", user_id)
    auth_timeline.mark("PAN submitted")
    await asyncio.sleep(0.5)

    # ── Step 2: Click Continue after PAN ─────────────────────────────────────
    log_callback("[Auth] Clicking Continue after PAN...")
    await _click_btn(page, log_callback, timeout=20000)

    # Check for errors shown inline on the PAN screen after Continue
    await asyncio.sleep(1)
    try:
        page_text = (await page.inner_text("body")).lower()
        terminal_error = _authentication_error(page_text, page.url)
        if terminal_error is not None:
            raise terminal_error
    except RuntimeError:
        raise
    except Exception:
        pass

    # ── Step 3: Wait for SAM checkbox, tick it, click Continue ───────────────
    log_callback("[Auth] Waiting for SAM page (Step 2)...")
    await update_browser_status(page, "Auth: Waiting for Step 2...")

    sam_found = False
    for _ in range(200):    # 200 × 300ms = 60s
        await asyncio.sleep(0.3)
        try:
            sam_found = await page.locator("id=passwordCheckBox-input").first.is_visible()
        except Exception:
            sam_found = False
        if sam_found:
            break

        # Fast-fail if locked account or invalid PAN error appears during the wait
        try:
            page_text = (await page.inner_text("body")).lower()
            terminal_error = _authentication_error(page_text, page.url)
            if terminal_error is not None:
                raise terminal_error
        except RuntimeError:
            raise
        except Exception:
            pass

        # B-04: portal may show an "active session" / "already logged in" dialog.
        # Detect any Continue/Proceed/Yes button inside a modal and click it.
        try:
            active_session = await page.evaluate("""() => {
                const keywords = ['already logged', 'active session', 'session exists',
                                  'do you wish to continue', 'existing session'];
                const body = document.body.innerText.toLowerCase();
                return keywords.some(k => body.includes(k));
            }""")
            if active_session:
                for dismiss_sel in (
                    "button:has-text('Continue')",
                    "button:has-text('Proceed')",
                    "button:has-text('Yes')",
                    "button:has-text('OK')",
                ):
                    try:
                        btn = page.locator(dismiss_sel).first
                        if await btn.is_visible(timeout=500):
                            log_callback("[Auth] Active session dialog detected — dismissing...")
                            await btn.click()
                            await asyncio.sleep(1)
                            break
                    except Exception:
                        pass
        except Exception:
            pass

    if not sam_found:
        await _dump_inputs(page, log_callback)
        raise RuntimeError("SAM page (Step 2) did not appear after PAN entry.")

    log_callback("[Auth] SAM page ready — ticking checkbox...")
    auth_timeline.mark("SAM ready")
    try:
        await page.check("id=passwordCheckBox-input", force=True)
    except Exception:
        await page.evaluate("""() => {
            const cb = document.getElementById('passwordCheckBox-input');
            if (cb && !cb.checked) cb.click();
        }""")

    # ── Step 4: Advance to Password login method ──────────────────────────────
    log_callback("[Auth] Advancing from SAM page...")
    sam_advance = await _advance_from_sam(page, log_callback, timeout=15000)
    if sam_advance == "timeout":
        await _dump_inputs(page, log_callback)
        raise RuntimeError("ITD portal did not advance beyond the SAM page.")

    # After SAM the portal may show a method-selection page
    # (#/login/otpOptions) with Password and OTP radios, OR may skip straight
    # to the password field. Wait briefly to see which page we land on.
    log_callback("[Auth] Waiting for method selection or password field...")
    await update_browser_status(page, "Auth: Selecting login method...")

    method_selectors = (
        "xpath=//label[contains(normalize-space(.), 'Password') and not(contains(normalize-space(.), 'OTP'))]",
        "input[type='radio']#mat-radio-0-input",
        "input[type='radio']:first-of-type",
    )
    password_field = page.locator("id=loginPasswordField").first
    try:
        password_already_visible = await password_field.is_visible(timeout=0)
    except Exception:
        password_already_visible = False
    method_control = (
        None
        if password_already_visible
        else await _first_visible(page, method_selectors, timeout=4000)
    )
    _method_selected = method_control is not None
    if method_control is not None:
        try:
            await method_control.click(force=True)
            log_callback("[Auth] Password login method selected.")
        except Exception:
            _method_selected = False

    if _method_selected:
        # Method selection page needs its own Continue click
        log_callback("[Auth] Clicking Continue after selecting Password method...")
        await _click_btn(page, log_callback, timeout=10000)
    else:
        log_callback("[Auth] Method selection page not seen — assuming password field follows directly.")

    # ── Step 5: Wait for password field, fill it ──────────────────────────────
    log_callback("[Auth] Waiting for password field...")
    await update_browser_status(page, "Auth: Entering password...")

    try:
        await page.wait_for_selector("id=loginPasswordField", state="visible", timeout=15000)
    except Exception:
        await _dump_inputs(page, log_callback)
        raise RuntimeError("Password field did not appear after selecting login method.")

    log_callback("[Auth] Entering password...")
    await page.fill("id=loginPasswordField", password)
    auth_timeline.mark("password submitted")

    terminal_error = _authentication_error("", page.url)
    if terminal_error is not None:
        raise terminal_error

    # ── Step 6: Submit with up to 4 attempts ─────────────────────────────────
    log_callback("[Auth] Submitting credentials...")
    await update_browser_status(page, "Auth: Submitting credentials...")

    async def _submit_once(attempt: int) -> bool:
        if attempt > 1:
            log_callback(f"[Auth] Submit attempt {attempt}/4...")
            await asyncio.sleep(3)

        clicked = await _click_btn(page, log_callback, timeout=10000)
        if not clicked:
            log_callback("[Auth] Continue not found — pressing Enter")
            try:
                await page.locator("id=loginPasswordField").first.press("Enter")
            except Exception:
                pass

        # Wait up to 7.5s for URL change or known error
        for _ in range(15):
            await asyncio.sleep(0.5)

            if "dashboard" in page.url.lower():
                return True

            terminal_error = _authentication_error("", page.url)
            if terminal_error is not None:
                raise terminal_error

            # loginMaxAttemptsPopup — too many attempts; click "Login Here"
            try:
                if await page.locator("id=loginMaxAttemptsPopup").first.is_visible(timeout=300):
                    log_callback("[Auth] Max-attempts popup — clicking Login Here...")
                    try:
                        await page.locator("button:has-text('Login Here')").first.click(timeout=3000)
                    except Exception:
                        pass
                    try:
                        await page.wait_for_url(
                            lambda u: "dashboard" in u.lower(), timeout=10000)
                        # ITD throttles the session after a max-attempts popup — the 
                        # Angular router may silently drop navigation events for a few
                        # seconds. Wait for the portal to fully recover before returning.
                        log_callback("[Auth] Rate-limit recovered — waiting for session to stabilise...")
                        await asyncio.sleep(6)
                        return True
                    except Exception:
                        return False
            except Exception:
                pass

            # Inline error — wrong password / other auth failures
            try:
                err = page.locator(
                    "mat-error, .mat-error1, .mat-mdc-form-field-error, "
                    ".error-msg, .errorMessage, div[role='alert'], "
                    "span.error, .invalid-feedback").first
                if await err.is_visible(timeout=300):
                    err_text = (await err.inner_text()).strip()
                    err_low = err_text.lower()
                    log_callback(f"[Auth] Portal error: {err_text}")
                    # Any password/credential error → fail fast, don't retry
                    if any(k in err_low for k in (
                        "invalid password", "incorrect password", "wrong password",
                        "valid password", "password is incorrect",
                        "user id or password", "credentials")):
                        raise RuntimeError(
                            f"AUTHENTICATION FAILED: {err_text or 'Incorrect Password'}")
                    return False   # other transient error — retry
            except RuntimeError:
                raise
            except Exception:
                pass

        return False

    login_success = False
    for attempt in range(1, 5):
        if is_running is not None and not is_running():
            raise RuntimeError("Aborted by user.")
        try:
            login_success = await _submit_once(attempt)
        except RuntimeError:
            raise
        if login_success:
            break

    if not login_success:
        await _dump_inputs(page, log_callback)
        raise RuntimeError("Could not reach dashboard after 4 submit attempts.")

    log_callback("[Auth] Login successful.")
    await update_browser_status(page, "Auth: Login Successful!")

    # ── Step 7: Dashboard settling ────────────────────────────────────────────
    log_callback("[Auth] Dashboard settling...")
    await update_browser_status(page, "Auth: Dashboard settling...")
    sentinel_ok = False
    try:
        await page.wait_for_selector(
            "//div[contains(text(), 'Welcome Back')] | //a[normalize-space(.)='AIS']",
            state="visible", timeout=40000)
        sentinel_ok = True
        await asyncio.sleep(4)
    except Exception:
        log_callback("[Warning] Dashboard sentinel timed out. Proceeding cautiously.")

    # Ensure any loading overlay is gone before handing back the page.
    try:
        await page.locator(".customLoaderBackdrop").wait_for(state="hidden", timeout=30000)
        log_callback("[Auth] Loader overlay cleared.")
    except Exception:
        log_callback("[Auth] Loader overlay already gone or not present.")

    # If the sentinel never fired, give the Angular nav menu extra time to render
    # before handing back the page — without this the e-File hover times out.
    if not sentinel_ok:
        log_callback("[Auth] Waiting extra time for nav menu to render...")
        await asyncio.sleep(8)

    auth_timeline.mark("dashboard ready")
    log_callback("[Auth] Dashboard ready.")
    return page


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout_itd(
    page: Page,
    log_callback: LogCallback,
    timeline: AutomationTimeline | None = None,
) -> None:
    """Log out from ITD and close the owned page.

    Args:
        page: Authenticated ITD page owned by this workflow.
        log_callback: Credential-safe progress logger.
        timeline: Optional monotonic workflow timeline.
    """
    auth_timeline = timeline or AutomationTimeline(log_callback)
    auth_timeline.mark("logout started")
    try:
        log_callback("[Auth] Initiating logout...")
        await update_browser_status(page, "Auth: Logging out...")

        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Strategy 1: direct logout link / button
        try:
            btn = page.locator(
                "//a[normalize-space(text())='Log Out' or normalize-space(text())='Logout'] | "
                "//button[normalize-space(text())='Log Out' or normalize-space(text())='Logout']"
            ).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                log_callback("[Auth] Logout button clicked.")
                await asyncio.sleep(2)
        except Exception:
            pass

        # Strategy 2: profile menu → logout item
        if "login" not in page.url.lower():
            try:
                profile = page.locator(
                    "//a[contains(@class,'profile') or contains(@class,'user') or "
                    "contains(@id,'profile')] | "
                    "//span[contains(@class,'user-name') or contains(@class,'user-profile')] | "
                    "//div[contains(@class,'profile-icon')]"
                ).first
                if await profile.is_visible(timeout=4000):
                    await profile.click()
                    await asyncio.sleep(1.5)
                    item = page.locator(
                        "//a[normalize-space(text())='Log Out' or normalize-space(text())='Logout'] | "
                        "//span[normalize-space(text())='Log Out' or normalize-space(text())='Logout'] | "
                        "//button[normalize-space(text())='Log Out' or normalize-space(text())='Logout']"
                    ).first
                    await item.click()
                    log_callback("[Auth] Logout via profile menu.")
                    await asyncio.sleep(2)
            except Exception:
                pass

        # Strategy 3: force-navigate to login page
        if "login" not in page.url.lower():
            try:
                await page.goto(
                    "https://eportal.incometax.gov.in/iec/foservices/#/login",
                    wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1.5)
                log_callback("[Auth] Session cleared via login page navigation.")
            except Exception as e:
                log_callback(f"[Auth] Logout strategy 3 failed: {e}")

        for _ in range(10):
            await asyncio.sleep(0.5)
            if "login" in page.url.lower():
                log_callback("[Auth] Successfully logged out.")
                break

    except Exception as e:
        log_callback(f"[Auth] Logout warning: {e}")
    finally:
        auth_timeline.mark("logout completed")
        try:
            await page.close()
        except Exception:
            pass
