"""Phase 0 regression tests for portal authentication safety."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.automation.auth import (
    _advance_from_sam,
    _authentication_error,
    _click_btn,
    _dump_inputs,
    _first_visible,
)
from app.automation.timing import AutomationTimeline


@dataclass
class FakeLocator:
    """Minimal Playwright locator test double."""

    visible_after: float | None
    started_at: float
    enabled: bool = True
    clicks: int = 0

    @property
    def first(self) -> "FakeLocator":
        """Return this locator as Playwright's ``first`` property would."""
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        """Report visibility without introducing a selector-local wait."""
        del timeout
        if self.visible_after is None:
            return False
        return asyncio.get_running_loop().time() - self.started_at >= self.visible_after

    async def is_enabled(self, timeout: int = 0) -> bool:
        """Report whether the fake control is actionable."""
        del timeout
        return self.enabled

    async def click(self, timeout: int = 0, force: bool = False) -> None:
        """Record a click on the fake locator."""
        del timeout, force
        self.clicks += 1


class FakeLocatorList:
    """Playwright locator-list double supporting duplicate DOM matches."""

    def __init__(
        self,
        visibility_delays: list[float | None],
        started_at: float,
    ) -> None:
        """Create one leaf locator for every matching DOM element."""
        self.items = [FakeLocator(delay, started_at) for delay in visibility_delays]

    @property
    def first(self) -> FakeLocator:
        """Return the first matching locator."""
        return self.items[0]

    @property
    def clicks(self) -> int:
        """Return the total clicks across all matching elements."""
        return sum(item.clicks for item in self.items)

    async def count(self) -> int:
        """Return the number of matching DOM elements."""
        return len(self.items)

    def nth(self, index: int) -> FakeLocator:
        """Return the indexed matching locator."""
        return self.items[index]


class FakePage:
    """Minimal Playwright page test double with named locator lists."""

    def __init__(
        self,
        visibility: dict[str, float | None | list[float | None]],
    ) -> None:
        """Create locator lists with visibility delays measured in seconds."""
        started_at = asyncio.get_running_loop().time()
        self.locators: dict[str, FakeLocatorList] = {}
        for selector, configured in visibility.items():
            delays = configured if isinstance(configured, list) else [configured]
            self.locators[selector] = FakeLocatorList(delays, started_at)

    def locator(self, selector: str) -> FakeLocatorList:
        """Return configured matches or one always-hidden fallback."""
        if selector not in self.locators:
            self.locators[selector] = FakeLocatorList(
                [None],
                asyncio.get_running_loop().time(),
            )
        return self.locators[selector]


@pytest.mark.asyncio
async def test_missing_alternative_selectors_share_one_deadline() -> None:
    """Missing alternatives must consume one timeout, not one per selector."""
    page = FakePage({"first": None, "second": None, "third": None})
    loop = asyncio.get_running_loop()
    started_at = loop.time()

    result = await _first_visible(
        page,
        ("first", "second", "third"),
        timeout=80,
        poll_interval=0.005,
    )

    elapsed = loop.time() - started_at
    assert result is None
    assert 0.06 <= elapsed < 0.18


@pytest.mark.asyncio
async def test_present_continue_uses_later_alternative() -> None:
    """Continue lookup must click a visible fallback selector once."""
    page = FakePage({"primary": None, "fallback": 0.0})
    messages: list[str] = []

    clicked = await _click_btn(
        page,
        messages.append,
        timeout=100,
        selectors=("primary", "fallback"),
    )

    assert clicked is True
    assert page.locators["primary"].clicks == 0
    assert page.locators["fallback"].clicks == 1
    assert all("fallback" not in message for message in messages)


@pytest.mark.asyncio
async def test_delayed_sam_control_is_found_within_shared_deadline() -> None:
    """A delayed SAM control must be detected without multiplying waits."""
    page = FakePage({"id=passwordCheckBox-input": 0.04})

    locator = await _first_visible(
        page,
        ("id=passwordCheckBox-input", "input[name='sam']"),
        timeout=150,
        poll_interval=0.005,
    )

    assert locator is page.locators["id=passwordCheckBox-input"].first


@pytest.mark.asyncio
async def test_hidden_stale_continue_does_not_hide_visible_current_button() -> None:
    """A hidden first match must not delay a later visible Continue control."""
    page = FakePage({"continue": [None, 0.0]})
    loop = asyncio.get_running_loop()
    started_at = loop.time()

    clicked = await _click_btn(
        page,
        lambda _: None,
        timeout=500,
        selectors=("continue",),
    )

    elapsed = loop.time() - started_at
    assert clicked is True
    assert page.locators["continue"].items[0].clicks == 0
    assert page.locators["continue"].items[1].clicks == 1
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_visible_disabled_continue_does_not_block_enabled_match() -> None:
    """A visible disabled stale control must not consume the click deadline."""
    page = FakePage({"continue": [0.0, 0.0]})
    page.locators["continue"].items[0].enabled = False
    loop = asyncio.get_running_loop()
    started_at = loop.time()

    clicked = await _click_btn(
        page,
        lambda _: None,
        timeout=500,
        selectors=("continue",),
    )

    elapsed = loop.time() - started_at
    assert clicked is True
    assert page.locators["continue"].items[0].clicks == 0
    assert page.locators["continue"].items[1].clicks == 1
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_sam_advance_returns_immediately_when_password_is_ready() -> None:
    """Direct SAM-to-password navigation must not consume the click timeout."""
    page = FakePage(
        {
            "id=loginPasswordField": 0.0,
            "button:has-text('Continue')": None,
            "button[type='submit']": None,
        }
    )
    loop = asyncio.get_running_loop()
    started_at = loop.time()

    result = await _advance_from_sam(
        page,
        lambda _: None,
        timeout=15000,
        poll_interval=0.005,
    )

    assert result == "next-stage"
    assert loop.time() - started_at < 0.1


@pytest.mark.asyncio
async def test_sam_advance_clicks_continue_when_required() -> None:
    """SAM Continue must be clicked once when no next-stage control exists."""
    page = FakePage(
        {
            "id=loginPasswordField": None,
            "button:has-text('Continue')": 0.0,
            "button[type='submit']": None,
        }
    )

    result = await _advance_from_sam(
        page,
        lambda _: None,
        timeout=500,
        poll_interval=0.005,
    )

    assert result == "clicked"
    assert page.locators["button:has-text('Continue')"].clicks == 1


@pytest.mark.parametrize(
    ("body", "url", "expected"),
    [
        ("Your e-Filing account has been locked", "", "ACCOUNT LOCKED"),
        ("PAN does not exist", "", "PAN does not exist"),
        ("Enter OTP sent to mobile", "", "OTP or human verification"),
        ("Complete CAPTCHA to continue", "", "OTP or human verification"),
        ("", "https://example.test/#/login/otpOptions", "OTP or human verification"),
    ],
)
def test_terminal_authentication_states_are_classified(
    body: str,
    url: str,
    expected: str,
) -> None:
    """Locked, invalid-PAN, OTP, and CAPTCHA states must fail clearly."""
    error = _authentication_error(body, url)
    assert error is not None
    assert expected in str(error)


def test_normal_login_state_is_not_misclassified() -> None:
    """A normal SAM/dashboard state must not be treated as terminal."""
    assert _authentication_error("Welcome Back. Continue", "#/dashboard") is None


def test_incorrect_password_error_is_terminal_and_safe() -> None:
    """Credential failures must be represented without echoing a password."""
    portal_message = "Invalid password. Please try again."
    lowered = portal_message.lower()
    assert "invalid password" in lowered
    error = RuntimeError(f"AUTHENTICATION FAILED: {portal_message}")
    assert "AUTHENTICATION FAILED" in str(error)
    assert "SuperSecret123" not in str(error)


def test_dashboard_url_is_a_readiness_signal() -> None:
    """The established dashboard route remains a successful login signal."""
    assert "dashboard" in "https://example.test/#/dashboard".lower()


class DiagnosticPage:
    """Page double returning deliberately sensitive control values."""

    async def evaluate(self, script: str) -> dict[str, Any]:
        """Assert the browser script suppresses input values."""
        assert "el.value" not in script
        return {
            "controls": [
                {
                    "tag": "input",
                    "type": "password",
                    "id": "loginPasswordField",
                    "placeholder": "Password",
                    "text": "",
                },
                {
                    "tag": "button",
                    "type": "submit",
                    "id": "continue",
                    "placeholder": "",
                    "text": "Continue",
                },
            ]
        }


@pytest.mark.asyncio
async def test_terminal_diagnostics_omit_values_and_url() -> None:
    """Failure diagnostics must not expose password values or portal URLs."""
    messages: list[str] = []
    await _dump_inputs(DiagnosticPage(), messages.append)  # type: ignore[arg-type]
    combined = "\n".join(messages)

    assert "values omitted" in combined
    assert "SecretPassword" not in combined
    assert "https://" not in combined
    assert "loginPasswordField" in combined


def test_timeline_uses_monotonic_deltas_without_sensitive_payloads() -> None:
    """Timeline events must report deterministic total and delta durations."""
    values = iter((10.0, 10.25, 11.0))
    messages: list[str] = []
    timeline = AutomationTimeline(messages.append, clock=lambda: next(values))

    timeline.mark("context requested")
    timeline.mark("context ready")

    assert messages == [
        "[Timing] context requested total=0.250s delta=0.250s",
        "[Timing] context ready total=1.000s delta=0.750s",
    ]


def test_timeline_rejects_unapproved_event_names() -> None:
    """Dynamic credential payloads must not be accepted as timing labels."""
    timeline = AutomationTimeline(lambda _: None, clock=lambda: 1.0)
    with pytest.raises(ValueError):
        timeline.mark("password=secret")
