"""Focused tests for standalone Phase One automation primitives."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect as sqlalchemy_inspect, text

import app.db.init_db as init_db
from app.automation import job_worker
from app.automation.navigation import (
    PortalHandle,
    find_frame_global,
    navigate_income_tax_returns,
    race_portal_navigation,
    resolve_itd_anchor,
    restore_dashboard_anchor,
)
from app.automation.years import TaxYearContext


class FakeLocator:
    """Minimal dynamic locator test double."""

    def __init__(self, visible: bool = False, text: str = "") -> None:
        """Initialize locator visibility and text."""
        self.visible = visible
        self.text = text

    @property
    def first(self) -> "FakeLocator":
        """Return the first locator match."""
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        """Return configured visibility."""
        del timeout
        return self.visible

    async def inner_text(self, timeout: int = 0) -> str:
        """Return configured text."""
        del timeout
        return self.text

    async def hover(self, timeout: int = 0) -> None:
        """Record a successful hover for navigation tests."""
        del timeout

    async def click(self, timeout: int = 0, force: bool = False) -> None:
        """Record a successful click for navigation tests."""
        del timeout, force


class FakeFrame:
    """Frame exposing selector visibility."""

    def __init__(self, visible: bool = False) -> None:
        """Initialize frame visibility."""
        self.visible = visible

    def locator(self, selector: str) -> FakeLocator:
        """Return a locator for any requested selector."""
        del selector
        return FakeLocator(self.visible)


class FakeContext:
    """Browser context supporting page creation."""

    def __init__(self) -> None:
        """Initialize an empty page collection."""
        self.pages: list[FakePage] = []

    async def new_page(self) -> "FakePage":
        """Create a page in this same context."""
        page = FakePage(self, "about:blank")
        self.pages.append(page)
        return page


class FakePage:
    """Page test double supporting navigation, text, and closure."""

    def __init__(self, context: FakeContext, url: str, body: str = "") -> None:
        """Initialize page state."""
        self.context = context
        self.url = url
        self.body = body
        self.closed = False
        self.frames: list[FakeFrame] = []
        self.goto_calls: list[str] = []
        self.reload_calls = 0

    def locator(self, selector: str) -> FakeLocator:
        """Return body or hidden element locators."""
        return FakeLocator(text=self.body) if selector == "body" else FakeLocator()

    async def close(self) -> None:
        """Mark this page closed."""
        self.closed = True

    def is_closed(self) -> bool:
        """Return closure state."""
        return self.closed

    async def reload(self, **kwargs: Any) -> None:
        """Record a true document reload."""
        del kwargs
        self.reload_calls += 1

    async def goto(self, url: str, **kwargs: Any) -> None:
        """Navigate to a URL."""
        del kwargs
        self.goto_calls.append(url)
        self.url = url


class XPathOnlyNavigationPage(FakePage):
    """Dashboard fixture exposing only the proven portal XPath selectors."""

    def locator(self, selector: str) -> FakeLocator:
        """Expose e-File and Income Tax Returns only through XPath fallbacks."""
        visible = selector in {
            "//*[normalize-space(.)='e-File']",
            "//*[normalize-space(.)='Income Tax Returns']",
            "//*[text()='Income Tax Returns']",
        }
        return FakeLocator(visible=visible)

    async def evaluate(self, expression: str) -> None:
        """Accept scroll operations from the hamburger helper."""
        del expression


@pytest.mark.parametrize(
    "value",
    [None, "", "2026", "AY2026-27", "2026/27", "2026-28", "1899-00", "2200-01"],
)
def test_year_rejects_invalid_values(value: Any) -> None:
    """Malformed, non-contiguous, absent, and unreasonable years must fail."""
    with pytest.raises(ValueError):
        TaxYearContext(value)


def test_year_mapping_and_filename_forms() -> None:
    """AY 2026-27 must map to FY and prior AY 2025-26."""
    year = TaxYearContext.parse("AY 2026-27")
    assert year.assessment_year == "2026-27"
    assert year.fiscal_year == "2025-26"
    assert year.financial_year == "2025-26"
    assert year.prior_assessment_year == "2025-26"
    assert year.ay_filename == "2026_27"
    assert year.fy_filename == "2025_26"
    assert TaxYearContext.from_assessment_year("2026-27") == year
    assert TaxYearContext.from_financial_year("2025-26") == year


def test_financial_year_rejects_invalid_values() -> None:
    """Legacy FY reconstruction must reject malformed or non-contiguous values."""
    for value in (None, "", "2025", "2025-27"):
        with pytest.raises(ValueError):
            TaxYearContext.from_financial_year(value)


def test_worker_year_derivation_uses_supported_context_attribute() -> None:
    """The production year helper must execute rather than only compile."""
    assert job_worker._derive_fiscal_year("2026-27") == "2025-26"


def test_worker_passes_assessment_year_to_26as_and_fy_to_ais() -> None:
    """Worker calls must preserve distinct AY/FY semantics and proven core order."""
    source = inspect.getsource(job_worker._run_job)
    as26_call = source.index("ok, reason, txt_path = await download_26as(")
    ais_call = source.index("ais_outcome = await run_request_ais(")
    prefill_call = source.index("prefill_outcome = await download_prefill(")

    assert "assessment_year=assessment_year" in source
    assert source.count("fiscal_year=fiscal_year") >= 2
    assert source.count("page = await resolve_itd_anchor(page)") == 6
    assert "page = await restore_dashboard_anchor(" not in source
    assert as26_call < ais_call < prefill_call
    assert "required_artifact_failures.append" in source
    assert "if required_artifact_failures:" in source
    assert "assessment_year=fiscal_year" not in source


@pytest.mark.asyncio
async def test_navigation_supports_proven_xpath_fallbacks() -> None:
    """Expanded navigation must not spend its full budget on a missing hamburger."""
    context = FakeContext()
    page = XPathOnlyNavigationPage(context, "https://eportal.incometax.gov.in/dashboard")
    context.pages.append(page)
    started = asyncio.get_running_loop().time()

    result = await navigate_income_tax_returns(page, timeout_ms=3_000)
    elapsed = asyncio.get_running_loop().time() - started

    assert isinstance(result, FakeLocator)
    assert result.visible is True
    assert 1.8 <= elapsed < 2.5


def test_additive_migration_backfills_legacy_job_assessment_year(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing FY-only jobs must gain a reconstructed nullable AY safely."""
    database_path = tmp_path / "legacy.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE client ("
                "id INTEGER PRIMARY KEY, user_id INTEGER, pan VARCHAR(10))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE client_itr ("
                "id INTEGER PRIMARY KEY, client_id INTEGER, year VARCHAR(10))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE automation_job ("
                "id INTEGER PRIMARY KEY, fiscal_year VARCHAR(10) NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO client (id) VALUES (1)"))
        connection.execute(
            text("INSERT INTO automation_job (id, fiscal_year) VALUES (1, '2025-26')")
        )
    monkeypatch.setattr(init_db, "engine", engine)

    init_db._apply_additive_sqlite_migrations()
    init_db._apply_additive_sqlite_migrations()

    columns = {
        column["name"] for column in sqlalchemy_inspect(engine).get_columns("automation_job")
    }
    with engine.connect() as connection:
        assessment_year = connection.execute(
            text("SELECT assessment_year FROM automation_job WHERE id = 1")
        ).scalar_one()
        artifact_outcomes = connection.execute(
            text("SELECT artifact_outcomes FROM automation_job WHERE id = 1")
        ).scalar_one()
    assert "assessment_year" in columns
    assert "artifact_outcomes" in columns
    assert assessment_year == "2026-27"
    assert artifact_outcomes == "{}"


@pytest.mark.asyncio
async def test_portal_race_detects_popup_without_serial_timeout() -> None:
    """A newly opened matching child page must win promptly."""
    context = FakeContext()
    origin = FakePage(context, "https://itd.test/dashboard")
    context.pages.append(origin)

    async def trigger() -> None:
        async def add_popup() -> None:
            await asyncio.sleep(0.02)
            context.pages.append(FakePage(context, "https://traces.test/home"))

        asyncio.create_task(add_popup())

    handle = await race_portal_navigation(origin, trigger, r"traces\.test", timeout_ms=500)
    assert handle.child_tab is True
    assert handle.target_page is context.pages[-1]


@pytest.mark.asyncio
async def test_portal_race_detects_same_tab_and_runs_confirmation() -> None:
    """Same-tab URL mutation and optional confirmation must race concurrently."""
    context = FakeContext()
    origin = FakePage(context, "https://itd.test/dashboard")
    context.pages.append(origin)
    confirmed = asyncio.Event()

    async def trigger() -> None:
        return None

    async def confirm() -> None:
        confirmed.set()
        await asyncio.sleep(0.01)
        origin.url = "https://ais.insight.test/home"

    handle = await race_portal_navigation(
        origin, trigger, r"ais\.insight\.test", timeout_ms=500, confirm=confirm
    )
    assert confirmed.is_set()
    assert handle.target_page is origin
    assert handle.anchor_replaced is True
    assert handle.child_tab is False


@pytest.mark.asyncio
async def test_portal_race_reports_explicit_error_promptly() -> None:
    """A terminal portal message must fail before the overall timeout."""
    context = FakeContext()
    origin = FakePage(context, "https://itd.test/dashboard", "Something went wrong")
    context.pages.append(origin)
    started = asyncio.get_running_loop().time()

    with pytest.raises(RuntimeError, match="explicit portal error"):
        await race_portal_navigation(origin, _noop, r"external\.test", timeout_ms=500)
    assert asyncio.get_running_loop().time() - started < 0.2


@pytest.mark.asyncio
async def test_child_cleanup_closes_only_owned_page() -> None:
    """Cleanup must close an owned child while preserving the borrowed anchor."""
    context = FakeContext()
    origin = FakePage(context, "https://itd.test/dashboard")
    child = FakePage(context, "https://traces.test/home")
    context.pages.extend((origin, child))
    handle = PortalHandle(origin, child, True, False, context, origin.url)

    anchor = await handle.cleanup()
    assert child.closed is True
    assert origin.closed is False
    assert anchor is origin


@pytest.mark.asyncio
async def test_same_tab_cleanup_restores_anchor_without_closing_sole_page() -> None:
    """Cleanup must restore same-tab navigation and never close a sole loaned page."""
    context = FakeContext()
    origin = FakePage(context, "https://external.test/home")
    context.pages.append(origin)
    handle = PortalHandle(
        origin, origin, False, True, context, "https://itd.test/dashboard"
    )

    anchor = await handle.cleanup()
    assert anchor is origin
    assert origin.url == "https://itd.test/dashboard"
    assert origin.closed is False


@pytest.mark.asyncio
async def test_closed_same_tab_anchor_is_recreated_in_same_context() -> None:
    """A closed replacement page must produce a fresh anchor in its context."""
    context = FakeContext()
    origin = FakePage(context, "https://external.test/home")
    context.pages.append(origin)
    origin.closed = True
    handle = PortalHandle(
        origin, origin, False, True, context, "https://itd.test/dashboard"
    )

    anchor = await handle.cleanup()
    assert anchor is not origin
    assert anchor.context is context
    assert anchor.url == "https://itd.test/dashboard"


@pytest.mark.asyncio
async def test_resolve_itd_anchor_rebinds_recreated_page() -> None:
    """Worker-facing resolution must return a replacement ITD page."""
    context = FakeContext()
    original = FakePage(context, "https://external.test/home")
    original.closed = True
    replacement = FakePage(
        context, "https://eportal.incometax.gov.in/iec/foservices/#/dashboard"
    )
    context.pages.extend((original, replacement))

    assert await resolve_itd_anchor(original) is replacement


@pytest.mark.asyncio
async def test_frame_search_uses_one_global_timeout() -> None:
    """Many missing frames must consume one timeout rather than one each."""
    context = FakeContext()
    page = FakePage(context, "https://external.test")
    page.frames = [FakeFrame(False) for _ in range(30)]
    started = asyncio.get_running_loop().time()

    result = await find_frame_global(page, "#missing", timeout_ms=80, poll_interval=0.005)
    elapsed = asyncio.get_running_loop().time() - started
    assert result is None
    assert 0.06 <= elapsed < 0.2


async def _noop() -> None:
    """Perform no async action."""
    return None
