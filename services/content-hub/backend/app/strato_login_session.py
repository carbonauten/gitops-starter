"""Shared pause/resume primitive for Strato's login flow.

Used by both strato_automation_service.py (mailbox creation) and
wordpress_automation_service.py (WordPress management). Strato's login
form always presents an image CAPTCHA for this account (confirmed via a
live screenshot, 2026-11-23) - no selector fix can solve an image CAPTCHA
automatically, so the only way either automation can ever complete is a
human reading the image and typing the code back in.

That requires keeping the SAME browser page open across two separate HTTP
requests (the CAPTCHA value is tied to that specific page's server-side
session - a fresh browser shows a different code), which is genuinely
stateful and easy to get subtly wrong. Unlike the page-specific selectors
in the two automation files (deliberately kept independent so a broken
selector in one never risks the other), this one piece is shared so the
pause/resume logic only exists once.

Assumes a single application process: this service runs one uvicorn
process behind nginx (see deploy/start.sh), no multiple workers, and
numReplicas = 1 in railway.toml - the pending-session registry below is a
plain in-memory dict, not something that would survive a restart or work
across replicas. If this service is ever scaled to multiple
workers/replicas, this registry needs to move to a shared store (Redis,
the DB, ...) or pin sessions to one instance.
"""

from __future__ import annotations

import base64
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .strato_config_service import StratoCredentials

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 180
LOGIN_URL = "https://www.strato.de/login"

_SESSIONS: dict[str, "_PendingLogin"] = {}


@dataclass
class _PendingLogin:
    playwright: Any
    browser: Any
    page: Any
    creds: StratoCredentials
    created_at: float
    # Opaque per-feature payload (e.g. the mailbox local_part/domain/password
    # a caller was in the middle of creating) - round-tripped back out of
    # resume_login() so callers don't need their own parallel session store
    # that could drift out of sync with this module's TTL/expiry.
    extra: Any = None


class StratoLoginError(Exception):
    """Generic terminal login failure. `code` is a plain string (not tied
    to either automation's own error-code enum, since this module is
    shared by both) - callers map it through their own translate() calls."""

    def __init__(self, code: str, screenshot_base64: str | None = None):
        self.code = code
        self.screenshot_base64 = screenshot_base64
        super().__init__(code)


@dataclass
class LoggedIn:
    page: Any
    browser: Any
    playwright: Any
    extra: Any = None


@dataclass
class CaptchaRequired:
    session_id: str
    captcha_image_base64: str | None


async def safe_screenshot(page: Any) -> str | None:
    try:
        data = await page.screenshot(type="png", full_page=True)
        return base64.b64encode(data).decode("ascii")
    except Exception:  # noqa: BLE001 - screenshot is best-effort debug info
        return None


async def _close_pending(session: "_PendingLogin") -> None:
    try:
        await session.browser.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        await session.playwright.stop()
    except Exception:  # noqa: BLE001
        pass


async def _sweep_expired() -> None:
    now = time.monotonic()
    expired = [sid for sid, s in _SESSIONS.items() if now - s.created_at > SESSION_TTL_SECONDS]
    for sid in expired:
        session = _SESSIONS.pop(sid, None)
        if session is not None:
            await _close_pending(session)


async def _dismiss_cookie_banner(page: Any) -> None:
    try:
        await page.get_by_role("button", name=re.compile("Zustimmen und schließen|Alle akzeptieren", re.I)).click(
            timeout=5000
        )
    except Exception:  # noqa: BLE001 - genuinely optional, never the real failure
        pass


async def _verify_logged_in(page: Any) -> None:
    if (
        await page.get_by_text(
            re.compile("Captcha|Sicherheitscode|Security code|Zwei-Faktor|2FA|Bestätigungscode", re.I)
        ).count()
        > 0
    ):
        raise StratoLoginError("strato_login_captcha_rejected", await safe_screenshot(page))
    if "/login" in page.url:
        raise StratoLoginError("strato_login_failed", await safe_screenshot(page))


async def begin_login(creds: StratoCredentials, *, extra: Any = None) -> "LoggedIn | CaptchaRequired":
    """Starts a browser, navigates to Strato's login page, and either logs
    straight in (no CAPTCHA shown - returns LoggedIn, caller owns the
    browser/playwright and must close both) or hits the CAPTCHA (returns
    CaptchaRequired, ownership of the open browser transfers to this
    module's pending-session registry until resume_login() or expiry)."""
    await _sweep_expired()

    from playwright.async_api import async_playwright

    playwright = None
    browser = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(locale="de-DE")
        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        await _dismiss_cookie_banner(page)

        if await page.get_by_label(re.compile("Security code|Sicherheitscode", re.I)).count() > 0:
            session_id = uuid.uuid4().hex
            screenshot = await safe_screenshot(page)
            _SESSIONS[session_id] = _PendingLogin(playwright, browser, page, creds, time.monotonic(), extra)
            return CaptchaRequired(session_id, screenshot)

        await page.get_by_label(re.compile("Benutzername|Kundennummer", re.I)).first.fill(creds.customer_number)
        await page.get_by_label(re.compile("Passwort", re.I)).first.fill(creds.password)
        await page.get_by_role("button", name=re.compile("Login", re.I)).click()
        await page.wait_for_load_state("networkidle", timeout=20000)
        await _verify_logged_in(page)
        return LoggedIn(page, browser, playwright, extra)
    except StratoLoginError:
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()
        raise
    except Exception as exc:  # noqa: BLE001 - never let an unexpected Playwright/site error become a raw 500
        logger.exception("Unexpected error starting the Strato login")
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()
        raise StratoLoginError("strato_login_unexpected_error", None) from exc


async def resume_login(session_id: str, captcha_code: str) -> LoggedIn:
    """Fills the human-provided CAPTCHA code into the still-open page from
    a prior begin_login() CaptchaRequired result and completes the login.
    Always consumes the pending session (success or failure) - a wrong
    code means starting over via begin_login(), not retrying in place,
    since Strato may show a fresh CAPTCHA image on reload anyway."""
    await _sweep_expired()
    session = _SESSIONS.pop(session_id, None)
    if session is None:
        raise StratoLoginError("strato_login_session_expired", None)

    page = session.page
    try:
        await page.get_by_label(re.compile("Benutzername|Kundennummer", re.I)).first.fill(
            session.creds.customer_number
        )
        await page.get_by_label(re.compile("Passwort", re.I)).first.fill(session.creds.password)
        await page.get_by_label(re.compile("Security code|Sicherheitscode", re.I)).first.fill(captcha_code)
        await page.get_by_role("button", name=re.compile("Login", re.I)).click()
        await page.wait_for_load_state("networkidle", timeout=20000)
        await _verify_logged_in(page)
        return LoggedIn(page, session.browser, session.playwright, session.extra)
    except StratoLoginError:
        await _close_pending(session)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error resuming the Strato login with a CAPTCHA code")
        await _close_pending(session)
        raise StratoLoginError("strato_login_unexpected_error", None) from exc


async def cancel_login(session_id: str) -> None:
    """Explicit cleanup for when the user abandons the CAPTCHA prompt
    (closes the dialog) instead of letting it sit until TTL expiry."""
    session = _SESSIONS.pop(session_id, None)
    if session is not None:
        await _close_pending(session)
