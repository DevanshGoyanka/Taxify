"""Tests for the standalone Phase Two pre-fill downloader."""

from __future__ import annotations

import asyncio
import json
import inspect
from pathlib import Path
from typing import Any, Optional

import pytest

from app.automation import downloader_prefill as prefill
from app.automation import job_worker
from app.automation.downloader_prefill import PrefillState, download_prefill
from app.automation.timing import AutomationTimeline


def test_prefill_timing_labels_are_credential_safe() -> None:
    """Phase Two timing labels must be accepted without dynamic taxpayer data."""
    values = iter((10.0, 10.25, 10.75))
    messages: list[str] = []
    timeline = AutomationTimeline(messages.append, clock=lambda: next(values))

    timeline.mark("Prefill navigation started")
    timeline.mark("Prefill download completed")

    assert messages == [
        "[Timing] Prefill navigation started total=0.250s delta=0.250s",
        "[Timing] Prefill download completed total=0.750s delta=0.500s",
    ]


class Download:
    """Fake browser download which writes configured bytes."""

    def __init__(self, content: bytes) -> None:
        """Store downloaded content."""
        self.content = content

    async def save_as(self, path: str) -> None:
        """Save content at the requested path."""
        Path(path).write_bytes(self.content)


class DownloadInfo:
    """Fake Playwright download-info holder."""

    def __init__(self, content: bytes) -> None:
        """Create a completed download value."""
        self.value = _awaitable(Download(content))


class DownloadContext:
    """Async context manager recording listener arming."""

    def __init__(self, page: "Page") -> None:
        """Retain page for ordering assertions."""
        self.page = page

    async def __aenter__(self) -> DownloadInfo:
        """Arm the download listener."""
        self.page.armed = True
        return DownloadInfo(self.page.content)

    async def __aexit__(self, *args: Any) -> None:
        """Disarm without suppressing errors."""
        self.page.armed = False


class Locator:
    """Minimal semantic locator test double."""

    def __init__(
        self,
        page: "Page",
        kind: str,
        visible: bool = False,
        text: str = "",
        options: Optional[list[str]] = None,
    ) -> None:
        """Configure locator behavior."""
        self.page = page
        self.kind = kind
        self.visible = visible
        self.text = text
        self.options = options or []
        self.selected = ""

    @property
    def first(self) -> "Locator":
        """Return this first match."""
        return self

    def nth(self, index: int) -> "Locator":
        """Return the indexed native select."""
        return self.page.selects[index]

    async def count(self) -> int:
        """Return native select count."""
        return len(self.page.selects) if self.kind == "selects" else len(self.options)

    def locator(self, selector: str) -> "Locator":
        """Return option collections or the selected option."""
        if selector == "option":
            return Locator(self.page, "options", options=self.options)
        if selector == "option:checked":
            return Locator(self.page, "selected", visible=True, text=self.selected)
        return Locator(self.page, "missing")

    async def all_text_contents(self) -> list[str]:
        """Return option labels."""
        return self.options

    async def is_visible(self, timeout: int = 0) -> bool:
        """Return configured visibility."""
        del timeout
        return self.visible

    async def click(self, timeout: int = 0) -> None:
        """Record clicks and enforce listener-before-download ordering."""
        del timeout
        if self.kind == "download":
            assert self.page.armed
            self.page.download_clicks += 1
        elif self.kind == "menu":
            self.page.menu_clicks += 1
        elif self.kind == "option":
            self.page.combo.selected = self.text

    async def select_option(self, label: str, timeout: int = 0) -> None:
        """Select a native option label."""
        del timeout
        if label not in self.options:
            raise ValueError(label)
        self.selected = label

    async def inner_text(self, timeout: int = 0) -> str:
        """Return locator text."""
        del timeout
        return self.text or self.selected

    async def input_value(self) -> str:
        """Return accessible combobox selection."""
        return self.selected

    async def get_attribute(self, name: str) -> Optional[str]:
        """Return no fallback attribute."""
        del name
        return None


class Context:
    """Authenticated browser context fixture."""

    def __init__(self, page: "Page") -> None:
        """Expose one page."""
        self.pages = [page]


class Page:
    """Playwright-like page with configurable semantic strategies."""

    def __init__(
        self,
        content: bytes,
        *,
        body: str = "",
        menu_strategy: str = "role",
        native: bool = True,
    ) -> None:
        """Configure page content and portal states."""
        self.url = "https://eportal.incometax.gov.in/dashboard"
        self.content = content
        self.body = body
        self.menu_strategy = menu_strategy
        self.native = native
        self.armed = False
        self.download_clicks = 0
        self.menu_clicks = 0
        self.selects = (
            [Locator(self, "select", visible=True, options=["2025-26", "AY 2026-27"])]
            if native
            else []
        )
        self.combo = Locator(self, "combo", visible=not native)
        self.context = Context(self)

    def is_closed(self) -> bool:
        """Return that the authenticated page remains open."""
        return False

    def expect_download(self, timeout: int) -> DownloadContext:
        """Return an exact page-scoped download expectation."""
        assert timeout >= 0
        return DownloadContext(self)

    def get_by_role(self, role: str, name: Any) -> Locator:
        """Expose role alternatives for menu, combo, option, and download."""
        pattern = getattr(name, "pattern", str(name)).lower()
        if role == "combobox":
            return self.combo
        if role == "option" and "2026" in pattern:
            return Locator(self, "option", visible=True, text="AY 2026-27")
        if self.menu_strategy == "role" and "pre" in pattern and role == "link":
            return Locator(self, "menu", visible=True)
        if "download" in pattern and "pre" not in pattern and role == "button":
            return Locator(self, "download", visible=True)
        return Locator(self, "missing")

    def get_by_text(self, name: Any, exact: bool = False) -> Locator:
        """Expose exact-text menu alternative."""
        del exact
        pattern = getattr(name, "pattern", str(name)).lower()
        if self.menu_strategy == "text" and "pre" in pattern:
            return Locator(self, "menu", visible=True)
        return Locator(self, "missing")

    def locator(self, selector: str) -> Locator:
        """Expose XPath menu, body state, and dynamic native selects."""
        if selector == "body":
            return Locator(self, "body", visible=True, text=self.body)
        if selector == "select":
            return Locator(self, "selects")
        if self.menu_strategy == "xpath" and "Pre-filled Data" in selector:
            return Locator(self, "menu", visible=True)
        return Locator(self, "missing")


async def _awaitable(value: Any) -> Any:
    """Return a value through an awaitable."""
    return value


@pytest.fixture(autouse=True)
def bypass_shared_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep downloader tests focused while asserting shared flow is invoked."""
    calls: list[str] = []

    async def resolve(page: Any) -> Any:
        calls.append("resolve")
        return page

    async def navigate(page: Any, **kwargs: Any) -> Any:
        del page, kwargs
        calls.append("navigate")
        return None

    monkeypatch.setattr(prefill, "resolve_itd_anchor", resolve)
    monkeypatch.setattr(prefill, "navigate_income_tax_returns", navigate)
    monkeypatch.setattr(prefill, "_test_flow_calls", calls, raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["role", "text", "xpath"])
async def test_semantic_menu_alternatives_and_atomic_valid_download(
    tmp_path: Path, strategy: str
) -> None:
    """Every semantic menu strategy must produce one atomic download click."""
    payload = {"personalInfo": {"pan": "ABCDE1234F"}, "metadata": {"assessmentYear": "2026-27"}}
    page = Page(json.dumps(payload).encode(), menu_strategy=strategy)

    outcome = await download_prefill(page, "abcde1234f", tmp_path, timeout_ms=100)

    final = tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json"
    assert outcome.state is PrefillState.DOWNLOADED
    assert outcome.path == str(final)
    assert final.exists()
    assert not Path(f"{final}.partial").exists()
    assert page.menu_clicks == 1
    assert page.download_clicks == 1
    assert page.selects[0].selected == "AY 2026-27"
    assert prefill._test_flow_calls == ["resolve"]


@pytest.mark.asyncio
async def test_accessible_combobox_fallback_selects_and_verifies(tmp_path: Path) -> None:
    """An accessible AY combobox must work when no native select exists."""
    page = Page(
        json.dumps({"personalInfo": {"pan": "ABCDE1234F"}}).encode(),
        native=False,
    )
    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    assert outcome.state is PrefillState.DOWNLOADED
    assert page.combo.selected == "AY 2026-27"


@pytest.mark.asyncio
async def test_missing_assessment_year_control_is_retryable(tmp_path: Path) -> None:
    """A missing AY control is a transient route/readiness failure."""
    page = Page(b"{}", native=False)
    page.combo.visible = False

    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=5)

    assert outcome.state is PrefillState.RETRYABLE_FAILURE
    assert outcome.path is None
    assert "not ready" in outcome.reason


@pytest.mark.asyncio
async def test_prefill_uses_one_total_elapsed_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Late missing controls must not receive a fresh full timeout budget."""

    async def slow_navigation(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        await asyncio.sleep(0.08)

    monkeypatch.setattr(prefill, "navigate_income_tax_returns", slow_navigation)
    page = Page(b"{}", native=False)
    page.combo.visible = False
    started = asyncio.get_running_loop().time()

    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    elapsed = asyncio.get_running_loop().time() - started

    assert outcome.state is PrefillState.RETRYABLE_FAILURE
    assert elapsed < 0.15


@pytest.mark.asyncio
async def test_stalled_save_respects_prefill_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stalled artifact stream must not outlive the total Prefill budget."""

    async def stalled_save(self: Download, path: str) -> None:
        del self, path
        await asyncio.sleep(1)

    monkeypatch.setattr(Download, "save_as", stalled_save)
    payload = {"personalInfo": {"pan": "ABCDE1234F"}}
    page = Page(json.dumps(payload).encode())
    started = asyncio.get_running_loop().time()

    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    elapsed = asyncio.get_running_loop().time() - started

    assert outcome.state is PrefillState.RETRYABLE_FAILURE
    assert outcome.path is None
    assert elapsed < 0.2
    assert not (tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json.partial").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"", b"not json"])
async def test_empty_and_invalid_json_are_rejected(tmp_path: Path, content: bytes) -> None:
    """Empty and malformed transfers fail without retaining taxpayer partials."""
    page = Page(content)
    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    assert outcome.path is None
    expected = PrefillState.RETRYABLE_FAILURE if not content else PrefillState.VALIDATION_FAILED
    assert outcome.state is expected
    partial = tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json.partial"
    assert not partial.exists()


@pytest.mark.asyncio
async def test_exception_after_write_deletes_nonempty_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An atomic-rename failure must not retain downloaded taxpayer JSON."""
    payload = {"personalInfo": {"pan": "ABCDE1234F"}}
    page = Page(json.dumps(payload).encode())

    def fail_replace(source: Any, destination: Any) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(prefill.os, "replace", fail_replace)
    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)

    assert outcome.state is PrefillState.PERMANENT_FAILURE
    assert outcome.path is None
    assert not (tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json.partial").exists()
    assert not (tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "state"),
    [
        ({"personalInfo": {"pan": "ZZZZZ9999Z"}}, PrefillState.VALIDATION_FAILED),
        ({"metadata": {"assessmentYear": "2025-26"}}, PrefillState.VALIDATION_FAILED),
        ({"IncDeductionsOthIncCPC": {"itrAy": "2025"}}, PrefillState.VALIDATION_FAILED),
        ({"IncDeductionsOthIncCPC": {"itrAy": "2026"}}, PrefillState.DOWNLOADED),
        ({"unrecognized": {"pan": "WRONG", "assessmentYear": "1900-01"}}, PrefillState.VALIDATION_FAILED),
        ({"personalInfo": {"pan": "ABCDE1234F"}}, PrefillState.DOWNLOADED),
    ],
)
async def test_conservative_metadata_validation(
    tmp_path: Path, payload: dict[str, Any], state: PrefillState
) -> None:
    """Known mismatches and unrelated JSON fail; absent AY metadata remains valid."""
    page = Page(json.dumps(payload).encode())
    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    assert outcome.state is state
    if state is PrefillState.VALIDATION_FAILED:
        assert outcome.path is None
        partial = tmp_path / "ABCDE1234F-PREFILL-AY-2026_27.json.partial"
        assert not partial.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "state"),
    [
        ("No pre-filled data is available", PrefillState.NO_DATA),
        ("Something went wrong. Try again", PrefillState.RETRYABLE_FAILURE),
        ("Access denied", PrefillState.PERMANENT_FAILURE),
    ],
)
async def test_terminal_portal_states(tmp_path: Path, body: str, state: PrefillState) -> None:
    """No-data and explicit portal errors stop before clicking Download."""
    page = Page(b"{}", body=body)
    outcome = await download_prefill(page, "ABCDE1234F", tmp_path, timeout_ms=100)
    assert outcome.state is state
    assert page.download_clicks == 0


@pytest.mark.asyncio
async def test_session_expiry_uses_shared_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shared session detection must return a dedicated terminal state."""

    async def expired(page: Any) -> bool:
        del page
        return True

    monkeypatch.setattr(prefill, "session_expired", expired)
    outcome = await download_prefill(Page(b"{}"), "ABCDE1234F", tmp_path)
    assert outcome.state is PrefillState.SESSION_EXPIRED
    assert outcome.path is None


@pytest.mark.asyncio
async def test_local_click_fallback_exposes_prefill_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefill must explicitly click menu levels when shared hover navigation stalls."""
    events: list[str] = []

    class MenuLocator:
        """Stateful menu locator for the local Prefill fallback."""

        def __init__(self, kind: str) -> None:
            """Store the menu level represented by this locator."""
            self.kind = kind

        @property
        def first(self) -> "MenuLocator":
            """Return this locator."""
            return self

        async def is_visible(self, timeout: int = 0) -> bool:
            """Expose menu levels according to prior clicks."""
            del timeout
            if self.kind == "efile":
                return True
            if self.kind == "returns":
                return "efile" in events
            if self.kind == "prefill":
                return "returns" in events
            return False

        async def click(self, timeout: int = 0, force: bool = False) -> None:
            """Record explicit activation of a menu level."""
            del timeout, force
            events.append(self.kind)

        async def hover(self, timeout: int = 0) -> None:
            """Record hover fallback activation."""
            del timeout
            events.append(self.kind)

    class MenuPage:
        """Portal shell where explicit clicks reveal nested actions."""

        def get_by_role(self, role: str, name: Any) -> MenuLocator:
            """Return a stateful locator based on the requested semantic name."""
            del role
            pattern = getattr(name, "pattern", str(name)).lower()
            if "pre" in pattern:
                return MenuLocator("prefill")
            if "income" in pattern:
                return MenuLocator("returns")
            return MenuLocator("efile")

        def get_by_text(self, name: Any, exact: bool = False) -> MenuLocator:
            """Mirror semantic role lookup for text fallbacks."""
            del exact
            return self.get_by_role("link", name)

        def locator(self, selector: str) -> MenuLocator:
            """Return XPath/CSS fallback locators."""
            if "Pre-filled" in selector or "pre-filled" in selector:
                return MenuLocator("prefill")
            if "Income Tax Returns" in selector:
                return MenuLocator("returns")
            return MenuLocator("efile")

    page = MenuPage()
    action = await prefill._open_prefill_action_locally(
        page,
        prefill.MonotonicDeadline.after(1_000),
    )

    assert action is not None
    assert events == ["efile", "returns"]


def test_iter_frames_excludes_playwright_main_frame_duplicate() -> None:
    """The main document must not be scanned once as page and again as frame."""
    page = Page(b"{}")
    main_frame = object()
    child_frame = object()
    page.main_frame = main_frame  # type: ignore[attr-defined]
    page.frames = [main_frame, child_frame]  # type: ignore[attr-defined]

    assert prefill._iter_frames(page) == (page, child_frame)


def test_worker_integrates_prefill_after_core_downloads_without_extraction() -> None:
    """Worker must preserve 26AS→AIS/TIS before Prefill processing.

    The committed worker downloads Prefill after the core AIS/TIS/26AS
    downloads (ordering invariant) and then parses it into
    ``parsed["prefill"]`` within the extraction block so the prefill
    payload is available to downstream consumers.  This test verifies the
    download ordering and that the parsed prefill is surfaced (not
    silently dropped).
    """
    source = inspect.getsource(job_worker._run_job)
    as26_call = source.index("ok, reason, txt_path = await download_26as(")
    ais_call = source.index("ais_outcome = await run_request_ais(")
    prefill_call = source.index("prefill_outcome = await download_prefill(")
    extraction = source.index("# Step 4.5: Extract parsed data")

    assert as26_call < ais_call < prefill_call < extraction
    assert "context.new_page(" not in source
    assert "dashboard_url=" not in source
    assert "page = await restore_dashboard_anchor(" not in source
    assert 'files["prefill"] = prefill_outcome.path' in source
    assert 'artifact_outcomes["prefill"] = prefill_outcome.to_dict()' in source
    assert source.count("artifact_outcomes=json.dumps(artifact_outcomes)") >= 3
    extraction_block = source[extraction:]
    # The worker parses the downloaded prefill so it is surfaced to
    # downstream consumers (previously this was dropped, losing the
    # prefill payload between download and persistence).
    assert 'parsed["prefill"]' in extraction_block


def test_outcome_serialization_is_safe() -> None:
    """Outcome dictionaries contain only typed status metadata."""
    result = prefill.PrefillOutcome(PrefillState.NO_DATA, reason="none").to_dict()
    assert result == {
        "state": "no_data",
        "path": None,
        "reason": "none",
        "ay": "2026-27",
    }
