from __future__ import annotations

import asyncio

import pytest

from app import strato_login_session
from app.strato_config_service import StratoCredentials


class _FakeLocator:
    """Minimal stand-in for a Playwright Locator used by the fakes below."""

    def __init__(self, count: int = 0, on_click=None):
        self._count = count
        self._on_click = on_click
        self.first = self

    async def count(self):
        return self._count

    async def click(self, timeout=None):
        if self._on_click is not None:
            await self._on_click()
        elif self._count == 0:
            raise TimeoutError("element not found")

    async def fill(self, value):
        pass

    async def wait_for(self, timeout=None):
        pass


class FakePage:
    """Just enough of a Playwright Page to exercise begin_login/resume_login
    without a real browser: shows (or not) a CAPTCHA field, and "logs in"
    (moves the URL off /login) only when the Login button is clicked."""

    def __init__(self, *, show_captcha: bool):
        self.show_captcha = show_captcha
        self.url = "https://www.strato.de/login"

    async def goto(self, url, wait_until=None, timeout=None):
        self.url = url

    async def wait_for_load_state(self, state=None, timeout=None):
        pass

    async def screenshot(self, type="png", full_page=False):
        return b"fake-png-bytes"

    def get_by_role(self, role, name=None):
        is_login_button = bool(name and name.search("Login"))

        async def _on_click():
            if is_login_button:
                self.url = "https://www.strato.de/kundenlogin/dashboard"
            else:
                raise TimeoutError("element not found")

        return _FakeLocator(count=1 if is_login_button else 0, on_click=_on_click)

    def get_by_label(self, pattern):
        if self.show_captcha and pattern.search("Security code"):
            return _FakeLocator(count=1)
        return _FakeLocator(count=0)

    def get_by_text(self, pattern):
        return _FakeLocator(count=0)


def _fake_async_playwright(page: FakePage):
    class FakeBrowser:
        async def new_context(self, locale=None):
            class FakeContext:
                async def new_page(self_inner):
                    return page

            return FakeContext()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, headless=True):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def stop(self):
            pass

    class FakeStarter:
        async def start(self):
            return FakePlaywright()

    return lambda: FakeStarter()


def test_begin_login_detects_captcha_then_resume_completes_login(monkeypatch):
    creds = StratoCredentials("12345", "secret")
    page = FakePage(show_captcha=True)
    monkeypatch.setattr("playwright.async_api.async_playwright", _fake_async_playwright(page))

    outcome = asyncio.run(strato_login_session.begin_login(creds, extra={"foo": "bar"}))
    assert isinstance(outcome, strato_login_session.CaptchaRequired)
    assert outcome.captcha_image_base64  # non-empty base64 screenshot

    resumed = asyncio.run(strato_login_session.resume_login(outcome.session_id, "0802"))
    assert isinstance(resumed, strato_login_session.LoggedIn)
    assert resumed.extra == {"foo": "bar"}
    assert "/login" not in resumed.page.url

    # The session was consumed - resuming again with the same id must fail.
    with pytest.raises(strato_login_session.StratoLoginError) as exc_info:
        asyncio.run(strato_login_session.resume_login(outcome.session_id, "0802"))
    assert exc_info.value.code == "strato_login_session_expired"


def test_begin_login_without_captcha_logs_straight_in(monkeypatch):
    creds = StratoCredentials("12345", "secret")
    page = FakePage(show_captcha=False)
    monkeypatch.setattr("playwright.async_api.async_playwright", _fake_async_playwright(page))

    outcome = asyncio.run(strato_login_session.begin_login(creds))
    assert isinstance(outcome, strato_login_session.LoggedIn)
    assert "/login" not in outcome.page.url


def test_resume_login_with_unknown_session_raises():
    with pytest.raises(strato_login_session.StratoLoginError) as exc_info:
        asyncio.run(strato_login_session.resume_login("does-not-exist", "0802"))
    assert exc_info.value.code == "strato_login_session_expired"
