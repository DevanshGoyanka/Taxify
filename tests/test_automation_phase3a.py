"""Focused tests for Phase 3A filed-return inventory capture."""

from __future__ import annotations

import json
from typing import Any, Optional

import pytest

from app.automation import filed_returns_inventory as inventory
from app.automation.filed_returns_inventory import (
    InventoryState,
    capture_filed_return_inventory,
)


CARD = """
A.Y. 2025-26
Filing Type
Revised
ITR : ITR-2
Acknowledgement No : {acknowledgement}
Filed By : self
Filing Date : Dec 31, 2025
Filing Section : 139(5)
Processed with demand due
Successfully e-verified
Pending for e-verification
ITR Filed
View Details
Download Form
Download Receipt
Download JSON
""".format(acknowledgement="".join(["1"] * 15))


class Locator:
    """Minimal semantic control used by inventory tests."""

    def __init__(self, *, visible: bool = False, disabled: bool = False) -> None:
        """Configure control visibility and disabled state."""
        self.visible = visible
        self.disabled = disabled
        self.clicks = 0

    @property
    def first(self) -> "Locator":
        """Return the first matching control."""
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        """Return configured visibility."""
        del timeout
        return self.visible

    async def is_disabled(self) -> bool:
        """Return configured disabled state."""
        return self.disabled

    async def get_attribute(self, name: str) -> Optional[str]:
        """Return an aria-disabled value when requested."""
        return str(self.disabled).lower() if name == "aria-disabled" else None

    async def click(self, timeout: int = 0) -> None:
        """Record activation."""
        del timeout
        self.clicks += 1


class Context:
    """Authenticated single-page browser context."""

    def __init__(self, page: "Page") -> None:
        """Expose the supplied page."""
        self.pages = [page]


class Page:
    """Playwright-like inventory page returning sanitized test snapshots."""

    def __init__(self, body: str, cards: list[str]) -> None:
        """Store visible portal text and card snapshots."""
        self.url = "https://eportal.incometax.gov.in/dashboard"
        self.body = body
        self.cards = cards
        self.view = Locator(visible=True)
        self.next = Locator(visible=True, disabled=True)
        self.context = Context(self)

    def is_closed(self) -> bool:
        """Return that the page is live."""
        return False

    def get_by_role(self, role: str, name: Any) -> Locator:
        """Expose View Filed Returns and disabled next-page actions."""
        pattern = getattr(name, "pattern", str(name)).lower()
        if "view\\ filed\\ returns" in pattern or "view filed returns" in pattern:
            return self.view
        if "next" in pattern and role in {"button", "link"}:
            return self.next
        return Locator()

    def get_by_text(self, name: Any, exact: bool = False) -> Locator:
        """Mirror View Filed Returns text lookup."""
        del exact
        return self.get_by_role("link", name)

    def locator(self, selector: str) -> Locator:
        """Expose XPath View Filed Returns and next-page fallbacks."""
        if "View Filed Returns" in selector:
            return self.view
        if "next" in selector.lower():
            return self.next
        return Locator()

    async def evaluate(self, script: str) -> dict[str, Any]:
        """Return the configured in-memory observation."""
        assert "cards" in script
        return {"body_text": self.body, "cards": self.cards}


@pytest.fixture(autouse=True)
def bypass_portal_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests focused on inventory parsing and privacy contracts."""

    async def resolve(page: Any) -> Any:
        return page

    async def active(page: Any) -> bool:
        del page
        return False

    monkeypatch.setattr(inventory, "resolve_itd_anchor", resolve)
    monkeypatch.setattr(inventory, "session_expired", active)


@pytest.mark.asyncio
async def test_capture_serializes_allowlisted_inventory_without_acknowledgement() -> None:
    """Capture must preserve useful metadata but never serialize acknowledgement."""
    body = "12 Filings till date\nItems per page: 06\n1-1 of 1 items\n1 of 1 pages"
    messages: list[str] = []

    outcome = await capture_filed_return_inventory(
        Page(body, [CARD]), timeout_ms=100, log=messages.append
    )
    payload = outcome.to_dict()
    encoded = json.dumps(payload)

    assert outcome.state is InventoryState.CAPTURED
    assert len(outcome.records) == 1
    record = payload["records"][0]
    assert record["assessment_year"] == "2025-26"
    assert record["filing_type"] == "revised"
    assert record["itr_form"] == "ITR-2"
    assert record["filing_section"] == "139(5)"
    assert record["filed_by"] == "self"
    assert record["acknowledgement_present"] is True
    assert record["json_available"] is True
    assert "".join(["1"] * 15) not in encoded
    assert "".join(["1"] * 15) not in repr(outcome.records[0])
    assert all("".join(["1"] * 15) not in message for message in messages)
    assert payload["portal_filings_till_date"] == 12
    assert payload["pagination"][0] == {
        "page_number": 1,
        "total_pages": 1,
        "page_size": 6,
        "visible_start": 1,
        "visible_end": 1,
        "total_items": 1,
    }


@pytest.mark.asyncio
async def test_duplicate_status_events_are_preserved() -> None:
    """Visually duplicate processing events must not be silently deduplicated."""
    original = CARD.replace("Revised", "Original").replace(
        "Processed with demand due",
        "Processed with no demand/refund\nProcessed with no demand/refund",
    )
    outcome = await capture_filed_return_inventory(Page("1 of 1 pages", [original]))

    events = outcome.to_dict()["records"][0]["status_events"]
    processed = [event for event in events if event["event_type"] == "processed_with_no_demand_or_refund"]
    assert len(processed) == 2


class DelayedPage(Page):
    """Inventory page whose Angular cards render after an initial shell state."""

    def __init__(self) -> None:
        """Configure an initial zero paginator followed by one ready card."""
        super().__init__("", [])
        self.snapshots = [
            {
                "body_text": "View Filed Returns\nItems per page: 06\n0-0 of 0 items\n0 of 0 pages",
                "cards": [],
            },
            {
                "body_text": "View Filed Returns\nItems per page: 06\n1-1 of 1 items\n1 of 1 pages",
                "cards": [CARD],
            },
        ]
        self.snapshot_index = 0

    async def evaluate(self, script: str) -> dict[str, Any]:
        """Advance from the shell snapshot to the terminal card snapshot."""
        assert "cards" in script
        index = min(self.snapshot_index, len(self.snapshots) - 1)
        self.snapshot_index += 1
        return self.snapshots[index]


@pytest.mark.asyncio
async def test_zero_paginator_is_not_treated_as_empty_inventory() -> None:
    """Angular's initial 0-of-0 shell must wait for asynchronously rendered cards."""
    outcome = await capture_filed_return_inventory(
        DelayedPage(),
        timeout_ms=1_000,
    )

    assert outcome.state is InventoryState.CAPTURED
    assert len(outcome.records) == 1
    assert outcome.pagination[0].page_number == 1


@pytest.mark.asyncio
async def test_nonterminal_zero_paginator_times_out_as_retryable() -> None:
    """A persistent 0-of-0 shell without an explicit message is not no-returns."""
    page = Page(
        "View Filed Returns\nItems per page: 06\n0-0 of 0 items\n0 of 0 pages",
        [],
    )

    outcome = await capture_filed_return_inventory(page, timeout_ms=30)

    assert outcome.state is InventoryState.RETRYABLE_FAILURE
    assert outcome.records == ()


@pytest.mark.asyncio
async def test_no_return_state_is_valid() -> None:
    """An empty inventory must produce an explicit no-return outcome."""
    outcome = await capture_filed_return_inventory(
        Page("View Filed Returns\nNo filed returns found\n1 of 1 pages", [])
    )

    assert outcome.state is InventoryState.NO_RETURNS
    assert outcome.records == ()
    assert outcome.to_dict()["reason"] == "No filed-return records were observed."


@pytest.mark.asyncio
async def test_session_expiry_returns_dedicated_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired portal sessions must not be reported as empty inventories."""

    async def expired(page: Any) -> bool:
        del page
        return True

    monkeypatch.setattr(inventory, "session_expired", expired)
    outcome = await capture_filed_return_inventory(Page("", []))

    assert outcome.state is InventoryState.SESSION_EXPIRED
    assert outcome.records == ()


def test_parse_card_keeps_unknown_json_availability_tri_state() -> None:
    """Absence of a JSON action means unknown rather than false."""
    record = inventory._parse_card(CARD.replace("Download JSON", ""), 1, 1)

    assert record is not None
    assert record.json_available is None
    assert "download_json" not in record.available_actions


def test_row_identity_is_random_and_contains_no_sensitive_source_value() -> None:
    """Internal row identities must not derive from acknowledgement values."""
    first = inventory._parse_card(CARD, 1, 1)
    second = inventory._parse_card(CARD, 1, 1)

    assert first is not None and second is not None
    assert first.row_identity != second.row_identity
    assert "".join(["1"] * 15) not in first.row_identity
    assert first.row_identity.startswith("filed-return-")


def test_worker_integrates_inventory_without_selection_or_extraction() -> None:
    """Worker must capture after Prefill and keep inventory out of tax parsing."""
    import inspect

    from app.automation import job_worker

    source = inspect.getsource(job_worker._run_job)
    prefill = source.index("prefill_outcome = await download_prefill(")
    capture = source.index("inventory_outcome = await capture_filed_return_inventory(")
    extraction = source.index("# Step 4.5: Extract parsed data")

    assert prefill < capture < extraction
    assert 'artifact_outcomes["filed_return_inventory"]' in source
    assert 'files["filed_return_inventory"]' not in source
    assert 'parsed["filed_return_inventory"]' not in source
    assert "inventory_data=" not in source


class MenuLocator:
    """Stateful nested-menu locator for the explicit fallback."""

    def __init__(self, page: "MenuPage", kind: str) -> None:
        """Retain the represented menu level."""
        self.page = page
        self.kind = kind

    @property
    def first(self) -> "MenuLocator":
        """Return this locator."""
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        """Expose nested levels only after their parent was activated."""
        del timeout
        if self.kind == "efile":
            return True
        if self.kind == "returns":
            return "efile" in self.page.events
        if self.kind == "view":
            return "returns" in self.page.events
        return False

    async def click(self, timeout: int = 0, force: bool = False) -> None:
        """Record activation of this menu level."""
        del timeout, force
        self.page.events.append(self.kind)

    async def hover(self, timeout: int = 0) -> None:
        """Record hover activation."""
        del timeout
        self.page.events.append(self.kind)


class MenuPage:
    """Portal shell where explicit clicks reveal Filed Returns."""

    def __init__(self) -> None:
        """Initialize menu events."""
        self.events: list[str] = []

    def get_by_role(self, role: str, name: Any) -> MenuLocator:
        """Return a menu level based on its requested semantic name."""
        del role
        pattern = getattr(name, "pattern", str(name)).lower()
        if "view" in pattern and "filed" in pattern:
            return MenuLocator(self, "view")
        if "income" in pattern:
            return MenuLocator(self, "returns")
        return MenuLocator(self, "efile")

    def get_by_text(self, name: Any, exact: bool = False) -> MenuLocator:
        """Mirror semantic role lookup."""
        del exact
        return self.get_by_role("link", name)

    def locator(self, selector: str) -> MenuLocator:
        """Return XPath fallbacks for each menu level."""
        if "View Filed Returns" in selector:
            return MenuLocator(self, "view")
        if "Income Tax Returns" in selector:
            return MenuLocator(self, "returns")
        return MenuLocator(self, "efile")


@pytest.mark.asyncio
async def test_local_click_fallback_exposes_filed_returns_action() -> None:
    """Explicit e-File and Income Tax Returns clicks must reveal the leaf action."""
    page = MenuPage()

    action = await inventory._open_filed_returns_locally(
        page,
        inventory.MonotonicDeadline.after(1_000),
        None,
    )

    assert action is not None
    assert page.events == ["efile", "returns"]


@pytest.mark.asyncio
async def test_capture_performs_no_download_or_detail_selection() -> None:
    """Phase 3A must only click navigation and optional pagination controls."""
    page = Page("1 of 1 pages", [CARD])

    outcome = await capture_filed_return_inventory(page)

    assert outcome.state is InventoryState.CAPTURED
    assert page.view.clicks == 1
    assert page.next.clicks == 0
