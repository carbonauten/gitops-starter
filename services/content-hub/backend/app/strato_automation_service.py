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
    # Confirmed via a live screenshot (2026-11-24): after login this account
    # lands on a single product's "STRATO WordPress Hosting Plus" overview
    # page, not a global nav with a plain "E-Mail" link - that originally
    # guessed selector matched nothing there, so this click silently never
    # happened and _create_mailbox()'s own "Neu anlegen" click then failed
    # with a confusing, unrelated-looking error two steps later. The actual
    # entry point on that page is a content card labeled "E-Mails verwalten"
    # ("Informieren Sie sich über Ihre Postfächer."). Try that first; fall
    # back to the originally guessed sidebar link in case this account ever
    # lands somewhere else.
    email_entry = page.get_by_role("link", name=re.compile(r"E-Mails?\s+verwalten", re.I))
    if await email_entry.count() == 0:
        email_entry = page.get_by_text(re.compile(r"E-Mails?\s+verwalten", re.I))
    if await email_entry.count() == 0:
        email_entry = page.get_by_role("link", name=re.compile(r"^E-Mail$", re.I))
    await email_entry.first.click()
    # Strato's pages never go network-idle (confirmed via a live inspection,
    # 2026-11-24 - see strato_login_session.py), so wait for "load" instead.
    await page.wait_for_load_state("load", timeout=20000)

    management_link = page.get_by_role("link", name=re.compile("E-Mail-Verwaltung", re.I))
    if await management_link.count() > 0:
        await management_link.first.click()
        await page.wait_for_load_state("load", timeout=20000)


async def _choose_free_mailbox_tier(page: Any, *, timeout: int = 8000) -> None:
    """Confirmed via a live screenshot (2026-11-24): "Neu anlegen" first
    opens a Basic (free) vs. Business (paid) pricing dialog, before the
    actual address/password form - the previous code went straight for the
    address field and timed out on this blocking dialog instead. Always
    choose the free Basic tier; swallow a timeout since some accounts/flows
    may skip this dialog entirely and go straight to the form (same
    optional-step pattern as strato_login_session._dismiss_cookie_banner).

    A role="button" match against the page alone (first attempt below)
    turned out not to be enough - a live run still got stuck on exactly
    this dialog even with that click in place. Pricing/upsell widgets like
    this one are often served from a separate payment micro-frontend
    embedded via <iframe>, which page-level locators never see into - so
    fall back to a plain text match (covers a non-<button> element with the
    right text) and then to checking every frame directly (covers the
    iframe case) before giving up."""
    pattern = re.compile("Basic-Postfach anlegen", re.I)
    try:
        await page.get_by_role("button", name=pattern).click(timeout=timeout)
        return
    except Exception:  # noqa: BLE001 - try the next strategy below
        pass
    try:
        await page.get_by_text(pattern).first.click(timeout=timeout)
        return
    except Exception:  # noqa: BLE001 - try the next strategy below
        pass
    for frame in page.frames:
        try:
            await frame.get_by_text(pattern).first.click(timeout=2000)
            return
        except Exception:  # noqa: BLE001 - not this frame, or no dialog at all
            continue


async def _select_mailbox_domain(page: Any, domain: str) -> None:
    """Confirmed via a live screenshot (2026-11-24): the domain picker is
    styled as a bordered chevron control next to the e-mail-address field,
    not a plain browser <select> arrow - handle both a native <select> and a
    custom combobox, same pattern as wordpress_automation_service.py's
    _select_domain(). Kept as a separate copy here deliberately - see this
    module's docstring on why the two automations' selectors aren't shared."""
    domain_field = page.get_by_label(re.compile("Domain", re.I)).first
    if await domain_field.count() == 0:
        return
    try:
        tag = await domain_field.evaluate("el => el.tagName.toLowerCase()")
    except Exception:  # noqa: BLE001 - falls through to the combobox path below
        tag = ""
    if tag == "select":
        option = domain_field.locator("option").filter(has_text=domain)
        if await option.count() > 0:
            value = await option.first.get_attribute("value")
            if value is not None:
                await domain_field.select_option(value=value)
        return
    await domain_field.click()
    option = page.get_by_role("option", name=re.compile(re.escape(domain), re.I))
    if await option.count() == 0:
        option = page.get_by_text(re.compile(re.escape(domain), re.I))
    await option.first.click()


async def _fill_mailbox_password(page: Any, password: str) -> None:
    """Confirmed via a live screenshot (2026-11-24): the E-Mail-Adresse and
    Domain fields on this form are properly label-associated (get_by_label
    matches and fills them fine), but the Passwort field - the one field
    with its own password-strength-meter widget, unlike the other two -
    stayed completely empty, silently (get_by_label matched zero elements,
    so the old fill loop simply never ran), leaving "Postfach anlegen"
    disabled and the whole step hanging until its click() timed out. Same
    fallback chain as strato_login_session._find_field: label, then
    placeholder, then the HTML input type itself, which is the one signal
    that can't be wrong regardless of how a strength-meter widget wraps the
    real <input>."""
    pattern = re.compile("Passwort", re.I)
    fields = page.get_by_label(pattern)
    if await fields.count() == 0:
        fields = page.get_by_placeholder(pattern)
    if await fields.count() == 0:
        fields = page.locator('input[type="password"]')
    field_count = await fields.count()
    for index in range(field_count):
        await fields.nth(index).fill(password)


async def _create_mailbox(page: Any, *, local_part: str, domain: str, password: str) -> None:
    await page.get_by_role("button", name=re.compile("Neu anlegen", re.I)).click()
    await _choose_free_mailbox_tier(page)
    await page.get_by_label(re.compile("E-Mail-Adresse|Postfachname|^Name$", re.I)).first.fill(local_part)

    await _select_mailbox_domain(page, domain)

    await _fill_mailbox_password(page, password)

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
