from __future__ import annotations

import asyncio
import re

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

    def get_by_placeholder(self, pattern):
        # Mirrors the real bug this is a regression test for: Strato's
        # username/password fields only ever match by placeholder, never by
        # label (confirmed via a live screenshot, 2026-11-24).
        if pattern.search("Benutzername") or pattern.search("Passwort"):
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


# Regression test for the real bug (confirmed via a live screenshot,
# 2026-11-24): Strato's login form fields render as placeholder text with
# no associated <label>, so a plain get_by_label() never matches any of
# them - the CAPTCHA went undetected, the subsequent .fill() calls timed
# out waiting for a label-matched element that doesn't exist, and the
# whole thing surfaced as a generic "unexpected error" instead of the
# CAPTCHA prompt. Exercised against a real headless browser (not a fake
# Locator) since the point of this test is specifically that get_by_label
# finds nothing on this markup.
PLACEHOLDER_ONLY_LOGIN_HTML = """
<html><body>
  <input type="text" placeholder="Benutzername oder Kundennummer" />
  <input type="password" placeholder="Passwort" />
  <input type="text" placeholder="Security code" />
  <button type="button">Login</button>
</body></html>
"""


def test_find_field_falls_back_to_placeholder_when_label_is_absent():
    async def _run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(PLACEHOLDER_ONLY_LOGIN_HTML)

                pattern = re.compile("Security code", re.I)
                by_label = page.get_by_label(pattern)
                assert await by_label.count() == 0  # the bug: label-only matching finds nothing

                field = await strato_login_session._find_field(page, pattern)
                assert await field.count() == 1
            finally:
                await browser.close()

    asyncio.run(_run())
