import os
import sys
import subprocess
import threading
import asyncio
import logging

from playwright.async_api import async_playwright

from app.automation.timing import AutomationTimeline

# Dedicated debug logger so browser lifecycle failures leave a clear trail in
# the systemd journal.Independent of the request-scoped `log_callback` (which
# only flows into the job's own status log), so launch/recovery failures are
# visible even when no caller supplied a callback — e.g. the silent retry path
# inside `_ensure_browser` that previously turned a missing-binary error into
# an opaque "future belongs to a different loop" ValueError (2026-09-08 incident).
logger = logging.getLogger("taxify.automation.browser")
# Ensure debug lifecycle logs are visible even before app/main.py's logging
# config runs (e.g. when the module is imported by a standalone script or a
# worker that bypasses the FastAPI lifespan). If the parent ``taxify`` logger
# was already configured by main.py, this no-ops (level already set there).
if not logger.level:
    logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


def _get_system_proxy() -> dict | None:
    """
    Read Windows system proxy settings from the registry.
    Returns a Playwright-compatible proxy dict or None if no proxy is set.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not proxy_enable:
            return None
        proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not proxy_server:
            return None
        # ProxyServer may be "host:port" or "http=host:port;https=host:port"
        if "=" in proxy_server:
            # Parse per-protocol format
            for part in proxy_server.split(";"):
                if part.startswith("https="):
                    proxy_server = part[6:]
                    break
                if part.startswith("http="):
                    proxy_server = part[5:]
        if not proxy_server.startswith("http"):
            proxy_server = "http://" + proxy_server
        return {"server": proxy_server}
    except Exception:
        return None


def _playwright_browsers_dir() -> str:
    """
    Stable directory for Playwright browser binaries.
    Always stored in AppData (~/Library/Application Support on macOS,
    ~/.local/share on Linux) so they survive app updates and are
    shared across runs.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "AayDocCapio", "browsers")
    os.makedirs(path, exist_ok=True)
    return path


def _playwright_cli() -> str:
    """
    Path to the playwright CLI executable.
    When frozen by Nuitka/PyInstaller the bundled playwright package
    ships its own entry-point script; find it relative to the package.
    """
    if getattr(sys, "frozen", False):
        # Nuitka one-dir: playwright package is next to the exe
        exe_dir = os.path.dirname(sys.executable)
        for candidate in [
            os.path.join(exe_dir, "playwright", "__main__.py"),
            os.path.join(exe_dir, "_internal", "playwright", "__main__.py"),
        ]:
            if os.path.exists(candidate):
                return candidate
        # Last resort: let the OS find it
        return "playwright"
    else:
        # Running as script: use the same Python to invoke playwright module
        return None   # signals: use sys.executable -m playwright


def _chromium_binary_present(headless: bool) -> bool:
    """Pre-flight check: is the Playwright Chromium binary (or headless-shell)
    actually present on disk?

    Playwright's ``channel="chrome"`` launch in modern-headless mode still
    needs ``chromium_headless_shell-<build>/chrome-headless-shell`` even when
    a system Google Chrome is installed — modern headless runs the headless
    driver binary, not the full Chrome. After a Playwright pip upgrade the
    build number in the path increments and the old binary is gone, so
    ``launch()`` raises ``Executable doesn't exist at .../chromium_headless_shell-NNNN/``
    — which previously triggered a broken recovery path that turned a clear
    "missing binary" error into an opaque
    ``ValueError: The future belongs to a different loop`` (2026-09-08 incident).
    This check lets us install proactively *before* the launch attempt, keeping
    the Playwright object loop binding clean.
    """
    browsers_dir = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or _playwright_browsers_dir()
    try:
        entries = os.listdir(browsers_dir)
    except FileNotFoundError:
        return False
    # Playwright's binary dirs are named ``chromium-<build>`` (full) and
    # ``chromium_headless_shell-<build>`` (headless driver). Any matching
    # entry whose nested executable exists is good enough.
    needed_prefix = "chromium_headless_shell-" if headless else "chromium-"
    for name in entries:
        if name.startswith(needed_prefix):
            top = os.path.join(browsers_dir, name)
            # Layout differs by platform; just confirm the dir is non-empty
            # and contains an executable-like file.
            try:
                for root, _dirs, files in os.walk(top):
                    if any(f.startswith("chrome") for f in files):
                        return True
            except OSError:
                continue
    return False


async def _install_chromium(log_callback=None, headless: bool = True):
    """Download Chromium (and, for modern headless mode, the headless-shell
    driver) into the stable browsers directory.

    Playwright splits the download into two packages: ``chromium`` (the full
    browser) and ``chromium-headless-shell`` (the lightweight headless driver
    that modern ``--headless=new`` mode actually launches). Both live under
    ``PLAYWRIGHT_BROWSERS_PATH``. Installing only ``chromium`` leaves the
    headless path broken — exactly the gap that caused the 2026-09-08
    "Executable doesn't exist at .../chromium_headless_shell-1234/" failures.
    """
    browsers_dir = _playwright_browsers_dir()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_dir

    # Install the headless shell when launching headless, and the full
    # chromium otherwise (interactive visible mode uses the full browser).
    packages = ["chromium-headless-shell"] if headless else ["chromium"]
    logger.info("Installing Playwright browser packages %s into %s", packages, browsers_dir)
    if log_callback:
        log_callback(
            f"[Browser] Downloading {', '.join(packages)} — this only happens once, please wait..."
        )

    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        driver_executable, driver_cli = compute_driver_executable()
        base_cmd = [driver_executable, driver_cli, "install"]
        env = {**os.environ, **get_driver_env(), "PLAYWRIGHT_BROWSERS_PATH": browsers_dir}
    except Exception as e:
        logger.warning("Playwright internals unavailable (%s); falling back to sys.executable", e)
        if log_callback:
            log_callback(f"[Browser] Internals error: {e}, falling back to system execution...")
        cli = _playwright_cli()
        if cli is None or cli == "playwright":
            base_cmd = [sys.executable, "-m", "playwright", "install"]
        else:
            py = os.environ.get("PYTHONPATH_FOR_PLAYWRIGHT") or "python"
            base_cmd = [py, cli, "install"]
        env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": browsers_dir}

    for pkg in packages:
        cmd = base_cmd + [pkg]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            tail = (stderr or b"").decode(errors="replace")[:500]
            raise RuntimeError(
                f"Playwright `{pkg}` install failed (exit {proc.returncode}):\n{tail}"
            )
        logger.info("Playwright package `%s` installed successfully", pkg)
    if log_callback:
        log_callback(f"[Browser] {', '.join(packages)} installed successfully.")


class BrowserManager:
    """
    Singleton Playwright browser manager with self-healing Chromium install.
    Stores browser binaries in AppData so they persist across app updates.
    """
    _instance = None
    _playwright = None
    _browser = None
    # Tracks the headless state of the currently-running singleton browser
    # so a later get_context(interactive=True) reuses a visible browser, or
    # relaunches as visible when the singleton was launched headless by a
    # prior headless job (e.g. a background import worker). Without this,
    # an interactive ack-download call would reuse a headless browser and
    # the operator would see no window even though interactive=True.
    _headless = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Dedicated thread + Proactor event loop for Playwright.
        #
        # uvicorn --reload forces a WindowsSelectorEventLoop (see uvicorn's
        # `use_subprocess = reload or workers > 1`), and a Selector loop cannot
        # spawn subprocesses — the exact `NotImplementedError` Playwright raises
        # when it tries to launch its Node driver via create_subprocess_exec.
        # Playwright objects are bound to the loop where `.start()` runs, so the
        # whole browser session must live on ONE loop. We give the manager its
        # own daemon thread running a Proactor loop (subprocess-capable) and
        # route all browser work through `dispatch()`, independent of whether
        # the server was launched with --reload.
        if not hasattr(self, "_loop"):
            self._loop: asyncio.AbstractEventLoop | None = None
            self._loop_thread: threading.Thread | None = None
            self._loop_lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Return the manager's dedicated Proactor event loop, starting the
        background thread that owns it on first use."""
        with self._loop_lock:
            if self._loop is None or not self._loop.is_running():
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(
                        asyncio.WindowsProactorEventLoopPolicy()
                    )
                loop = asyncio.new_event_loop()
                self._loop = loop
                thread = threading.Thread(
                    target=self._run_loop,
                    name="playwright-loop",
                    daemon=True,
                )
                self._loop_thread = thread
                thread.start()
            return self._loop

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def dispatch(self, coro):
        """Run ``coro`` (an awaitable) on the dedicated Playwright loop/thread
        and return its result. Lets browser work run on a subprocess-capable
        Proactor loop regardless of the caller's event loop (e.g. uvicorn's
        Selector loop under --reload).

        Note: the job worker and most routers currently call ``get_context``
        directly (``await browser_manager.get_context(...)``) rather than via
        ``dispatch``. That is fine on Linux (the default uvicorn loop spawns
        subprocesses there) but means the dedicated background loop is only
        exercised by callers that route through ``dispatch``. The loop-binding
        bug fixed in ``_ensure_browser``'s recovery path (2026-09-08) does not
        depend on which loop the caller is on — it was a stale
        ``async_playwright`` object surviving a ``stop()``/``start()`` cycle.
        """
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return await asyncio.wrap_future(future)

    def _set_browsers_env(self):
        """Tell Playwright where to find/store browsers before any API call."""
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _playwright_browsers_dir()

    async def initialize(self, log_callback=None):
        """Start the Playwright engine if not already running.

        Idempotent: a no-op when ``self._playwright`` is set. The recovery path
        in ``_ensure_browser`` clears ``_playwright`` (after ``stop()``) before
        re-entering here, so a fresh ``async_playwright().start()`` always binds
        to the currently-running loop — never reusing a stale Playwright object
        from a prior loop binding (the 2026-09-08 "future belongs to a
        different loop" regression).
        """
        if self._playwright is None:
            self._set_browsers_env()
            logger.info("Starting Playwright engine (PLAYWRIGHT_BROWSERS_PATH=%s)",
                        os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))
            if log_callback:
                log_callback("[Browser] Starting Playwright engine...")
            self._playwright = await async_playwright().start()
            logger.info("Playwright engine started.")

    # No --start-maximized: it fights the fixed 1600x900 viewport and distorts
    # the aspect ratio (collapsing the ITD nav). The competitor relies purely
    # on the viewport, letting the window auto-size to it.
    _LAUNCH_ARGS = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--password-store=basic",
        "--use-mock-keychain",
    ]
    _IGNORE_DEFAULT_ARGS = ["--enable-automation"]

    async def _launch(self, headless, log_callback=None):
        """
        Launch the browser. Prefer the user's installed Google Chrome
        (channel='chrome') — the Insight/AIS portal's download buttons only
        fire on real Chrome; bundled Chromium silently no-ops them.
        Fall back to bundled Chromium if Chrome is absent (26AS still works,
        but AIS/TIS downloads will fail — warn the user).
        Automatically picks up Windows system proxy from the registry.
        """
        proxy = _get_system_proxy()
        if proxy:
            logger.info("System proxy detected: %s", proxy["server"])
            if log_callback:
                log_callback(f"[Browser] System proxy detected: {proxy['server']}")
        args = list(self._LAUNCH_ARGS)
        if headless:
            # Force modern headless mode and suppress any leaked window on ARM64
            args += [
                "--headless=new",
                "--disable-gpu",
                "--window-position=-10000,-10000",
            ]
        launch_kwargs = dict(
            headless=headless,
            args=args,
            ignore_default_args=self._IGNORE_DEFAULT_ARGS,
        )
        if proxy:
            launch_kwargs["proxy"] = proxy
        # Pre-flight: modern --headless=new needs the chromium-headless-shell
        # driver binary even when channel="chrome" is requested (Playwright
        # runs the headless driver, not the system Chrome, for modern headless).
        # Missing it is the root cause of the 2026-09-08 incident.
        if headless and not _chromium_binary_present(headless=True):
            logger.warning(
                "chromium-headless-shell binary not found in %s — installing "
                "before launch to avoid the 'future belongs to a different loop' "
                "recovery path",
                os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
            )
            if log_callback:
                log_callback("[Browser] Headless driver missing — installing now...")
            await _install_chromium(log_callback, headless=True)
        elif not headless and not _chromium_binary_present(headless=False):
            logger.info("Full chromium binary not found — installing before launch")
            if log_callback:
                log_callback("[Browser] Chromium not found — installing now...")
            await _install_chromium(log_callback, headless=False)
        logger.info("Launching browser (channel=chrome, headless=%s)", headless)
        try:
            browser = await self._playwright.chromium.launch(
                channel="chrome", **launch_kwargs
            )
            self._channel = "chrome"
            logger.info("Browser launched via channel=chrome")
            return browser
        except Exception as e:
            logger.warning("channel=chrome launch failed (%s); falling back to bundled Chromium", e)
            if log_callback:
                log_callback(
                    "[Browser] WARNING: Google Chrome not found — using bundled Chromium. "
                    "26AS will work, but AIS/TIS downloads need Google Chrome installed "
                    "(https://www.google.com/chrome/)."
                )
            browser = await self._playwright.chromium.launch(**launch_kwargs)
            self._channel = "chromium"
            logger.info("Browser launched via bundled chromium")
            return browser

    async def _ensure_browser(self, log_callback=None, interactive=True):
        headless = not interactive
        logger.info(
            "_ensure_browser: interactive=%s headless=%s "
            "playwright_set=%s browser_set=%s browser_connected=%s prev_headless=%s",
            interactive, headless,
            self._playwright is not None,
            self._browser is not None,
            bool(self._browser and self._browser.is_connected()),
            getattr(self, "_headless", None),
        )
        await self.initialize(log_callback)
        # Relaunch when the singleton is missing/disconnected OR when the
        # caller needs a different visibility mode than the running browser.
        # An interactive (visible) ack/e-verify flow must not silently reuse
        # a headless browser that a background import worker launched.
        needs_relaunch = (
            self._browser is None
            or not self._browser.is_connected()
            or self._headless != headless
        )
        if not needs_relaunch:
            logger.info("_ensure_browser: reusing existing connected browser (channel=%s)",
                        getattr(self, "_channel", "chromium"))
        if needs_relaunch:
            if self._browser is not None and self._headless != headless:
                logger.info("_ensure_browser: switching %s -> %s",
                            "headless" if self._headless else "visible",
                            "headless" if headless else "visible")
                if log_callback:
                    log_callback(
                        f"[Browser] Switching from "
                        f"{'headless' if self._headless else 'visible'} "
                        f"to {'headless' if headless else 'visible'} mode."
                    )
                try:
                    await self._browser.close()
                except Exception as close_err:
                    logger.warning("_ensure_browser: close of prior browser failed: %s", close_err)
                self._browser = None
            try:
                self._browser = await self._launch(headless, log_callback)
                self._headless = headless
                logger.info("_ensure_browser: launched via %s", getattr(self, "_channel", "chromium"))
                if log_callback:
                    log_callback(f"[Browser] Launched via {getattr(self, '_channel', 'chromium')}")
            except Exception as e:
                err_str = str(e)
                err_lower = err_str.lower()
                # Detect the specific "missing binary" failure shape. Note
                # the keyword list deliberately EXCLUDES "none"/"attribute" —
                # those matched too broadly and masked unrelated errors by
                # routing every ValueError through the chromium-install path.
                # The 2026-09-08 "different loop" failure was a symptom of
                # this: the real cause (missing chromium-headless-shell) was
                # caught here, but the recovery re-started Playwright in a
                # broken loop state.
                is_missing_binary = any(
                    k in err_lower
                    for k in ("executable", "not found", "doesn't exist",
                              "no such file", "playwright install")
                )
                logger.error("_ensure_browser: launch failed (missing_binary=%s): %s",
                             is_missing_binary, err_str, exc_info=True)
                if not is_missing_binary:
                    if log_callback:
                        log_callback(f"[Error] Failed to launch browser: {e}")
                    raise
                if log_callback:
                    log_callback(f"[Browser] Binary missing — reinstalling ({e})...")
                # Full teardown BEFORE reinstall: stop the Playwright transport
                # cleanly so the subsequent ``async_playwright().start()`` rebinds
                # to the current running loop instead of straddling a stale one.
                # This is the exact point where the prior code produced
                # "The future belongs to a different loop" — it cleared
                # ``_playwright = None`` after ``stop()`` but left the door
                # open for a half-torn-down transport; ``_full_teardown``
                # guarantees a clean slate.
                await self._full_teardown(log_callback)

                # Reinstall the correct package for the launch mode (headless
                # mode needs chromium-headless-shell; visible mode needs the
                # full chromium). The previous code always installed
                # ``chromium`` regardless of mode, so a headless launch stayed
                # broken even after recovery.
                await _install_chromium(log_callback, headless=headless)

                # Re-init and retry on a clean Playwright object.
                self._set_browsers_env()
                await self.initialize(log_callback)
                self._browser = await self._launch(headless, log_callback)
                self._headless = headless
                logger.info("_ensure_browser: recovered and launched via %s after reinstall",
                            getattr(self, "_channel", "chromium"))

    async def _full_teardown(self, log_callback=None):
        """Fully stop and null out the Playwright object and browser.

        Guarantees that the next ``initialize()`` call starts from a clean
        slate — no transport, no connection, no stale loop binding. The
        recovery path in ``_ensure_browser`` must call this before reinstalling
        Chromium; without it, ``stop()`` can leave a half-closed transport
        whose pending futures are bound to a loop that no longer matches the
        one ``launch()`` is awaited on, surfacing as
        ``ValueError: The future belongs to a different loop`` (2026-09-08).
        """
        logger.info("_full_teardown: stopping browser=%s playwright=%s",
                    self._browser is not None, self._playwright is not None)
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception as e:
            logger.warning("_full_teardown: browser.close failed: %s", e)
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("_full_teardown: playwright.stop failed: %s", e)
        finally:
            self._browser = None
            self._playwright = None
            logger.info("_full_teardown: complete")

    async def get_context(
        self,
        log_callback=None,
        interactive=True,
        timeline: AutomationTimeline | None = None,
    ):
        """Create an isolated portal browser context.

        Args:
            log_callback: Optional progress logging callback.
            interactive: Whether to show the browser window.
            timeline: Optional monotonic workflow timeline.

        Returns:
            A configured Playwright browser context.
        """
        if timeline is not None:
            timeline.mark("context requested")
        logger.info("get_context: interactive=%s", interactive)
        try:
            await self._ensure_browser(log_callback, interactive)
        except Exception as e:
            logger.warning("get_context: first attempt failed (%s) — tearing down and retrying", e, exc_info=True)
            if log_callback:
                log_callback(f"[Browser] Retrying after error: {e}")
            # Full teardown (not just nulling the browser) so the retry's
            # ``async_playwright().start()`` binds to the current loop cleanly.
            await self._full_teardown(log_callback)
            await self._ensure_browser(log_callback, interactive)

        # Match the competitor's working context exactly: fixed 1600x900 viewport,
        # no bypass_csp (real Chrome handles CSP fine and the portal expects it).
        _context_kwargs = dict(
            viewport={"width": 1600, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            accept_downloads=True,
        )
        try:
            ctx = await self._browser.new_context(**_context_kwargs)
        except Exception as e:
            # Browser object is stale (disconnected Chrome process) — force a full restart.
            logger.warning("get_context: new_context failed (%s) — full restart", e, exc_info=True)
            if log_callback:
                log_callback(f"[Browser] Context creation failed ({e}), restarting browser...")
            await self._full_teardown(log_callback)
            await self._ensure_browser(log_callback, interactive)
            ctx = await self._browser.new_context(**_context_kwargs)
        logger.info("get_context: context ready")

        # Spoof automation-detection properties
        await ctx.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
            window.chrome = window.chrome || { runtime: {} };
        }""")
        if timeline is not None:
            timeline.mark("context ready")
        return ctx

    async def close(self):
        await self._full_teardown()


# Shared global instance
browser_manager = BrowserManager()
