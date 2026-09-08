"""The modal dismisser must never confirm a logout.

``#confirmBtnFooter`` is a shared confirmation button on the ITD portal, and
on the "Sure you want to Logout?" dialog it is the *Yes*.  When the logout
branch could not find its negative button it fell through to the generic
confirm branch and ended the session — silently, because nothing in the
helper logged anything.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import pytest

from app.automation.navigation import dismiss_portal_modals

CONFIRM_SELECTORS = "#continueBtnNav, #confirmBtnFooter, #efNotificationPopUp_continue"


class _FakeLocator:
    """The slice of Playwright's Locator API the dismisser actually uses."""

    def __init__(
        self,
        page: "_FakePage",
        key: str,
        visible: bool,
        text: str = "",
        role_buttons: Optional[dict[str, bool]] = None,
    ) -> None:
        self._page = page
        self._key = key
        self._visible = visible
        self._text = text
        self._role_buttons = role_buttons or {}

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def is_visible(self, timeout: int | None = None) -> bool:
        return self._visible

    async def inner_text(self, timeout: int | None = None) -> str:
        return self._text

    async def click(self, force: bool = False, timeout: int | None = None) -> None:
        self._page.clicks.append(self._key)
        self._page.on_click(self._key)

    def get_by_role(self, role: str, name: "re.Pattern[str] | None" = None) -> "_FakeLocator":
        for label, present in self._role_buttons.items():
            if present and name is not None and name.search(label):
                return _FakeLocator(self._page, f"{self._key}:{label}", True, label)
        return _FakeLocator(self._page, f"{self._key}:none", False)


class _FakeKeyboard:
    def __init__(self, page: "_FakePage") -> None:
        self._page = page

    async def press(self, key: str) -> None:
        self._page.keys.append(key)


class _FakePage:
    def __init__(
        self,
        *,
        logout_prompt: bool = False,
        buttons: Optional[dict[str, bool]] = None,
        security_text: Optional[str] = None,
        security_buttons: Optional[dict[str, bool]] = None,
        confirm_button: bool = False,
    ) -> None:
        self.logout_prompt = logout_prompt
        self.buttons = buttons or {}
        self.security_text = security_text
        self.security_buttons = security_buttons or {}
        self.confirm_button = confirm_button
        self.clicks: list[str] = []
        self.keys: list[str] = []
        self.logs: list[str] = []
        self.keyboard = _FakeKeyboard(self)

    def on_click(self, key: str) -> None:
        """Clear the dialog that was just answered, as the portal would."""
        if key.startswith("logout-prompt") or key.startswith("security"):
            self.logout_prompt = False
            self.security_text = None
        if key == "confirm":
            self.confirm_button = False

    def get_by_text(self, pattern: "re.Pattern[str]") -> _FakeLocator:
        visible = self.logout_prompt and bool(pattern.search("Sure you want to Logout?"))
        return _FakeLocator(self._self_or_none(visible), "logout-prompt-text", visible)

    def _self_or_none(self, _visible: bool) -> "_FakePage":
        return self

    def get_by_role(self, role: str, name: "re.Pattern[str] | None" = None) -> _FakeLocator:
        for label, present in self.buttons.items():
            if present and name is not None and name.search(label):
                return _FakeLocator(self, f"logout-prompt:{label}", True, label)
        return _FakeLocator(self, "page-button:none", False)

    def locator(self, selector: str) -> _FakeLocator:
        if "securityReasonPopup" in selector:
            return _FakeLocator(
                self,
                "security",
                self.security_text is not None,
                self.security_text or "",
                self.security_buttons,
            )
        if "confirmBtnFooter" in selector:
            return _FakeLocator(self, "confirm", self.confirm_button)
        return _FakeLocator(self, "unknown", False)

    def log(self, message: str) -> None:
        self.logs.append(message)


@pytest.mark.asyncio
async def test_logout_dialog_is_answered_no_and_confirm_is_left_alone() -> None:
    page = _FakePage(logout_prompt=True, buttons={"No": True}, confirm_button=True)

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks[0] == "logout-prompt:No"
    assert "confirm" not in page.clicks


@pytest.mark.asyncio
async def test_a_stay_labelled_button_also_counts_as_declining() -> None:
    """The negative button is not always labelled exactly "No"."""
    page = _FakePage(logout_prompt=True, buttons={"No, Stay Logged In": True})

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks == ["logout-prompt:No, Stay Logged In"]


@pytest.mark.asyncio
async def test_logout_dialog_without_a_no_button_never_clicks_the_shared_confirm() -> None:
    """The regression: #confirmBtnFooter is this dialog's Yes."""
    page = _FakePage(logout_prompt=True, buttons={}, confirm_button=True)

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks == []
    assert page.keys == ["Escape"]
    assert any("not confirmed away" in entry for entry in page.logs)


@pytest.mark.asyncio
async def test_security_popup_mentioning_logout_never_clicks_the_shared_confirm() -> None:
    page = _FakePage(
        security_text="You are being logged out for security reasons.",
        security_buttons={},
        confirm_button=True,
    )

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks == []
    assert page.keys == ["Escape"]


@pytest.mark.asyncio
async def test_ordinary_notification_is_still_continued_through() -> None:
    """Guarding the logout case must not stop the helper doing its job."""
    page = _FakePage(confirm_button=True)

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks == ["confirm"]
    assert any("Notification continue button clicked" in entry for entry in page.logs)


@pytest.mark.asyncio
async def test_security_notice_without_logout_wording_is_acknowledged() -> None:
    page = _FakePage(
        security_text="For security reasons your session is being monitored.",
        security_buttons={"OK": True},
    )

    await dismiss_portal_modals(page, log=page.log)

    assert page.clicks == ["security:OK"]
