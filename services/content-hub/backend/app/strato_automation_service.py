"""Browser-automation mailbox creation for Strato, used only because Strato
publishes no API for this (confirmed by research - only the "E-Mail-
Verwaltung" web panel supports creating a mailbox). An IT-Master's full
Strato customer-login (strato_config_service.py) drives a headless Chromium
browser through the real customer panel to click through mailbox creation on
their behalf.

**This has not been exercised end-to-end against a live Strato account.**
The selectors below are written from screenshots of the login page and the
E-Mail-Verwaltung overview - not from inspecting the live DOM of the actual
"Neu anlegen" dialog, which was never seen. Treat every selector here as a
best guess that will very likely need adjustment the first time this runs
for real; that's why every step is wrapped individually with a specific
error code and a failure screenshot, so a human can see exactly where it
broke and fix the one selector that's wrong instead of debugging blind.

The login step itself (including a CAPTCHA this account's login form
always shows) is handled by strato_login_session.py, shared with
wordpress_automation_service.py - see that module's docstring for why.

Known failure modes this cannot handle:
- Any Strato UI change (new field layout, renamed buttons, a confirmation
  step this code doesn't know about)
- Concurrent manual session: logging in here may terminate a session the
  IT-Master has open in their own browser, and vice versa (Strato's login
  page already shows this warning in normal use)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import strato_login_session
from .strato_config_service import resolve_strato_credentials

logger = logging.getLogger(__name__)

STEP_LOGIN = "strato_automation_login_failed"
STEP_NAVIGATE = "strato_automation_navigation_failed"
STEP_CREATE = "strato_automation_create_failed"
STEP_UNEXPECTED = "strato_automation_unexpected_error"
STEP_CAPTCHA = "strato_automation_2fa_or_captcha"
STEP_SESSION_EXPIRED = "strato_automation_captcha_session_expired"

# Maps strato_login_session's generic error codes onto this module's own
# translatable ones (routes/strato_automation.py's translate() calls expect
# these specific keys, already shipped in backend/locales/*.json).
_LOGIN_ERROR_CODE_MAP = {
    "strato_login_captcha_rejected": STEP_CAPTCHA,
    "strato_login_failed": STEP_LOGIN,
    "strato_login_session_expired": STEP_SESSION_EXPIRED,
    "strato_login_unexpected_error": STEP_UNEXPECTED,
}


class StratoAutomationError(Exception):
    """Carries a translatable error code plus an optional failure screenshot
    (base64 PNG) - routes/strato_automation.py renders both, bypassing the
    app's generic string-only HTTPException error envelope for this one
    endpoint because the screenshot is genuinely useful for debugging a
    selector that broke against the real site."""

    def __init__(self, code: str, screenshot_base64: str | None = None):
        self.code = code
        self.screenshot_base64 = screenshot_base64
        super().__init__(code)


def _map_login_error(exc: strato_login_session.StratoLoginError) -> StratoAutomationError:
    code = _LOGIN_ERROR_CODE_MAP.get(exc.code, STEP_UNEXPECTED)
    return StratoAutomationError(code, exc.screenshot_base64)


async def _open_email_management(page: Any) -> None:
    email_nav = page.get_by_role("link", name=re.compile(r"^E-Mail$", re.I))
    if await email_nav.count() > 0:
        await email_nav.first.click()
    management_link = page.get_by_role("link", name=re.compile("E-Mail-Verwaltung", re.I))
    if await management_link.count() > 0:
        await management_link.first.click()
    # Strato's pages never go network-idle (confirmed via a live inspection,
    # 2026-11-24 - see strato_login_session.py), so wait for "load" instead.
    await page.wait_for_load_state("load", timeout=20000)


async def _create_mailbox(page: Any, *, local_part: str, domain: str, password: str) -> None:
    await page.get_by_role("button", name=re.compile("Neu anlegen", re.I)).click()
    await page.get_by_label(re.compile("E-Mail-Adresse|Postfachname|^Name$", re.I)).first.fill(local_part)

    domain_field = page.get_by_label(re.compile("Domain", re.I))
    if await domain_field.count() > 0:
        await domain_field.first.select_option(label=domain)

    password_fields = page.get_by_label(re.compile("Passwort", re.I))
    field_count = await password_fields.count()
    for index in range(field_count):
        await password_fields.nth(index).fill(password)

    await page.get_by_role("button", name=re.compile("Postfach anlegen", re.I)).click()
    await page.wait_for_load_state("load", timeout=20000)
    await page.get_by_text(f"{local_part}@{domain}", exact=False).first.wait_for(timeout=10000)


async def _run_step(page: Any, code: str, awaitable: Any) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        await awaitable
    except PlaywrightTimeoutError as exc:
        raise StratoAutomationError(code, await strato_login_session.safe_screenshot(page)) from exc
    except Exception as exc:  # noqa: BLE001 - never let an unexpected Playwright/site error become a raw 500
        logger.exception("Unexpected error during Strato automation step %s", code)
        raise StratoAutomationError(STEP_UNEXPECTED, await strato_login_session.safe_screenshot(page)) from exc


def _validate_mailbox_params(local_part: str, domain: str, password: str) -> tuple[str, str]:
    local = (local_part or "").strip().lower()
    target_domain = (domain or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", local) or not target_domain or not password:
        raise HTTPException(status_code=400, detail="validation")
    return local, target_domain


async def _finish_create_mailbox(
    page: Any, browser: Any, playwright: Any, *, local: str, target_domain: str, password: str
) -> dict[str, Any]:
    try:
        await _run_step(page, STEP_NAVIGATE, _open_email_management(page))
        await _run_step(
            page,
            STEP_CREATE,
            _create_mailbox(page, local_part=local, domain=target_domain, password=password),
        )
    finally:
        await browser.close()
        await playwright.stop()
    return {"status": "created", "email": f"{local}@{target_domain}", "local_part": local, "domain": target_domain}


async def create_mailbox_via_automation(
    db: Session,
    *,
    local_part: str,
    domain: str,
    password: str,
) -> dict[str, Any]:
    """Returns either {"status": "created", ...} or, if Strato's login form
    shows its CAPTCHA, {"status": "captcha_required", "session_id": ...,
    "captcha_image_base64": ...} - the caller must then collect the code
    from a human and call resume_create_mailbox_via_automation()."""
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")
    local, target_domain = _validate_mailbox_params(local_part, domain, password)

    try:
        outcome = await strato_login_session.begin_login(
            creds, extra={"local_part": local, "domain": target_domain, "password": password}
        )
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc

    if isinstance(outcome, strato_login_session.CaptchaRequired):
        return {
            "status": "captcha_required",
            "session_id": outcome.session_id,
            "captcha_image_base64": outcome.captcha_image_base64,
        }

    return await _finish_create_mailbox(
        outcome.page, outcome.browser, outcome.playwright, local=local, target_domain=target_domain, password=password
    )


async def resume_create_mailbox_via_automation(session_id: str, captcha_code: str) -> dict[str, Any]:
    try:
        outcome = await strato_login_session.resume_login(session_id, captcha_code)
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc

    params = outcome.extra or {}
    return await _finish_create_mailbox(
        outcome.page,
        outcome.browser,
        outcome.playwright,
        local=params.get("local_part", ""),
        target_domain=params.get("domain", ""),
        password=params.get("password", ""),
    )
