"""Browser-automation WordPress management for Strato, used only because
Strato publishes no API for installing or listing WordPress sites (same
situation as mailbox creation in strato_automation_service.py). An
IT-Master's or Designer's stored Strato customer-login drives a headless
Chromium browser through the real "Website & Shop > WordPress & Co."
customer panel on their behalf.

**This has not been exercised end-to-end against a live Strato account.**
The selectors below are written from a single screenshot of the WordPress & Co.
overview page (two mode cards - "Flexibilitaets-Modus" / "Sicherheits-Modus"
- each with an "Installieren" button, and a table of existing installations
below with "Bezeichnung" as its first column) - not from inspecting the live
DOM of the actual install dialog, which was never seen. Treat every selector
here as a best guess that will very likely need adjustment the first time
this runs for real; that's why every step is wrapped individually with a
specific error code and a failure screenshot, exactly like
strato_automation_service.py.

The login step itself (including a CAPTCHA this account's login form always
shows) is handled by strato_login_session.py, shared with
strato_automation_service.py - see that module's docstring for why. The
post-login WordPress-specific automation below stays independent from
strato_automation_service.py's own post-login mailbox automation: both are
untested against a third-party site that changes outside our control, so
keeping them independent means fixing a broken selector in one never risks
silently breaking the other.

Known failure modes this cannot handle: see strato_automation_service.py's
docstring - the same caveats (Strato UI changes, concurrent manual
session) apply here.
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

STEP_LOGIN = "wordpress_automation_login_failed"
STEP_CAPTCHA = "wordpress_automation_2fa_or_captcha"
STEP_SESSION_EXPIRED = "wordpress_automation_captcha_session_expired"
STEP_NAVIGATE = "wordpress_automation_navigation_failed"
STEP_LIST = "wordpress_automation_list_failed"
STEP_INSTALL = "wordpress_automation_install_failed"
STEP_UNEXPECTED = "wordpress_automation_unexpected_error"

INSTALL_MODES = ("flexibility", "security")
_MODE_CARD_TITLES = {"flexibility": "Flexibilitäts-Modus", "security": "Sicherheits-Modus"}

# Maps strato_login_session's generic error codes onto this module's own
# translatable ones (routes/wordpress.py's translate() calls expect these
# specific keys, already shipped in backend/locales/*.json).
_LOGIN_ERROR_CODE_MAP = {
    "strato_login_captcha_rejected": STEP_CAPTCHA,
    "strato_login_failed": STEP_LOGIN,
    "strato_login_session_expired": STEP_SESSION_EXPIRED,
    "strato_login_unexpected_error": STEP_UNEXPECTED,
}


class WordPressAutomationError(Exception):
    """Carries a translatable error code plus an optional failure screenshot
    (base64 PNG) - routes/wordpress.py renders both, same as
    StratoAutomationError in strato_automation_service.py."""

    def __init__(self, code: str, screenshot_base64: str | None = None):
        self.code = code
        self.screenshot_base64 = screenshot_base64
        super().__init__(code)


def _map_login_error(exc: strato_login_session.StratoLoginError) -> WordPressAutomationError:
    code = _LOGIN_ERROR_CODE_MAP.get(exc.code, STEP_UNEXPECTED)
    return WordPressAutomationError(code, exc.screenshot_base64)


async def _open_wordpress_management(page: Any) -> None:
    # Confirmed via a live screenshot (2026-11-24, during the mailbox-
    # creation automation's own debugging - this account lands on the same
    # page regardless of which automation logs in): login lands on a single
    # product's "STRATO WordPress Hosting Plus" overview page, not a global
    # nav - the originally guessed "Website.*Shop" -> "WordPress" link chain
    # matches nothing there. The actual entry point on that page is a
    # content card labeled "WordPress & Co. starten" ("Installieren Sie Ihre
    # Wunschanwendung."). Try that first; fall back to the originally
    # guessed link chain in case this account ever lands somewhere else.
    wordpress_entry = page.get_by_role("link", name=re.compile(r"WordPress.*starten", re.I))
    if await wordpress_entry.count() == 0:
        wordpress_entry = page.get_by_text(re.compile(r"WordPress.*starten", re.I))
    if await wordpress_entry.count() > 0:
        await wordpress_entry.first.click()
    else:
        website_nav = page.get_by_role("link", name=re.compile("Website.*Shop", re.I))
        if await website_nav.count() > 0:
            await website_nav.first.click()
        wordpress_link = page.get_by_role("link", name=re.compile("WordPress", re.I))
        if await wordpress_link.count() > 0:
            await wordpress_link.first.click()
    # Strato's pages never go network-idle (confirmed via a live inspection,
    # 2026-11-24 - see strato_login_session.py), so wait for "load" instead.
    await page.wait_for_load_state("load", timeout=20000)


async def _scrape_installations(page: Any) -> list[dict[str, str]]:
    table = page.locator("table:has-text('Bezeichnung')").first
    rows = table.locator("tbody tr")
    count = await rows.count()
    installations: list[dict[str, str]] = []
    for index in range(count):
        row = rows.nth(index)
        cells = row.locator("td")
        cell_count = await cells.count()
        if cell_count < 2:
            continue  # not a data row
        label = (await cells.nth(0).inner_text()).strip()
        application = (await cells.nth(1).inner_text()).strip()
        link = ""
        if cell_count > 2:
            link_el = cells.nth(2).locator("a").first
            if await link_el.count() > 0:
                link = (await link_el.get_attribute("href")) or (await link_el.inner_text()).strip()
        if not label or "wordpress" not in application.lower():
            continue
        installations.append(
            {
                "label": label,
                "application": application,
                "link": link,
                # Standard WordPress convention, not scraped - Strato's own
                # "Link" column points at the live site, not wp-admin.
                "wp_admin_url": f"{link.rstrip('/')}/wp-admin/" if link else "",
            }
        )
    return installations


async def _select_domain(page: Any, domain: str) -> None:
    # Confirmed via a live screenshot (2026-11-24): the field is labeled
    # "Ihre Domains und Subdomains" and its options combine domain + path
    # ("elphen.ag - /"), so an exact label match against the bare domain
    # would never hit - match on the option containing the domain text
    # instead. Its visual style (bordered box + chevron, not a plain
    # browser <select> arrow) also looks like it could be a custom
    # combobox rather than a native <select>, so this handles both.
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


# Confirmed via a live screenshot (2026-11-24): admin username/password/email
# come pre-filled by Strato itself (customer number, a generated password,
# the account's registered email) - nothing to fill there. "Titel der
# Webseite" is the one field Strato leaves blank; fill it with a reasonable
# default if it's actually empty (never overwrite a value already there).
async def _fill_site_title_if_empty(page: Any, title: str) -> None:
    title_field = page.get_by_label(re.compile("Titel der Webseite|Website-?Titel|Site [Tt]itle", re.I)).first
    if await title_field.count() == 0:
        return
    try:
        current = await title_field.input_value()
    except Exception:  # noqa: BLE001 - not a fillable input after all; skip rather than fail the run
        return
    if not current:
        await title_field.fill(title)


async def _install(page: Any, *, mode: str, domain: str) -> None:
    card_title = _MODE_CARD_TITLES[mode]
    heading = page.get_by_text(re.compile(re.escape(card_title), re.I)).first
    install_button = heading.locator("xpath=following::button[1]")
    await install_button.click()
    await page.wait_for_load_state("load", timeout=20000)

    await _select_domain(page, domain)
    await _fill_site_title_if_empty(page, domain)

    # Confirmed via a live screenshot (2026-11-24): the confirm button is
    # labeled "Fertig" ("Done"), not "Installieren"/"Weiter"/"Bestätigen" as
    # originally guessed.
    confirm_button = page.get_by_role("button", name=re.compile("Fertig|Installieren|Weiter|Bestätigen", re.I))
    if await confirm_button.count() > 0:
        await confirm_button.first.click()
    await page.wait_for_load_state("load", timeout=20000)
    await page.get_by_text(re.compile("installiert|erfolgreich", re.I)).first.wait_for(timeout=15000)


async def _run_step(page: Any, code: str, awaitable: Any) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        await awaitable
    except PlaywrightTimeoutError as exc:
        raise WordPressAutomationError(code, await strato_login_session.safe_screenshot(page)) from exc
    except Exception as exc:  # noqa: BLE001 - never let an unexpected Playwright/site error become a raw 500
        logger.exception("Unexpected error during WordPress automation step %s", code)
        raise WordPressAutomationError(STEP_UNEXPECTED, await strato_login_session.safe_screenshot(page)) from exc


async def _finish_list(page: Any, browser: Any, playwright: Any) -> dict[str, Any]:
    try:
        await _run_step(page, STEP_NAVIGATE, _open_wordpress_management(page))
        installations: list[dict[str, str]] = []

        async def _scrape() -> None:
            nonlocal installations
            installations = await _scrape_installations(page)

        await _run_step(page, STEP_LIST, _scrape())
    finally:
        await browser.close()
        await playwright.stop()
    return {"status": "listed", "installations": installations}


async def _finish_install(page: Any, browser: Any, playwright: Any, *, mode: str, domain: str) -> dict[str, Any]:
    try:
        await _run_step(page, STEP_NAVIGATE, _open_wordpress_management(page))
        await _run_step(page, STEP_INSTALL, _install(page, mode=mode, domain=domain))
    finally:
        await browser.close()
        await playwright.stop()
    return {"status": "installed", "domain": domain, "mode": mode}


async def list_wordpress_installations(db: Session) -> dict[str, Any]:
    """Returns either {"status": "listed", "installations": [...]} or, if
    Strato's login form shows its CAPTCHA, {"status": "captcha_required",
    "session_id": ..., "captcha_image_base64": ...} - the caller must then
    collect the code from a human and call
    resume_list_wordpress_installations()."""
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    try:
        outcome = await strato_login_session.begin_login(creds)
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc

    if isinstance(outcome, strato_login_session.CaptchaRequired):
        return {
            "status": "captcha_required",
            "session_id": outcome.session_id,
            "captcha_image_base64": outcome.captcha_image_base64,
        }

    return await _finish_list(outcome.page, outcome.browser, outcome.playwright)


async def resume_list_wordpress_installations(session_id: str, captcha_code: str) -> dict[str, Any]:
    try:
        outcome = await strato_login_session.resume_login(session_id, captcha_code)
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc
    return await _finish_list(outcome.page, outcome.browser, outcome.playwright)


async def install_wordpress_via_automation(db: Session, *, mode: str, domain: str) -> dict[str, Any]:
    """Returns either {"status": "installed", ...} or, if Strato's login
    form shows its CAPTCHA, {"status": "captcha_required", ...} - see
    list_wordpress_installations() above."""
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    target_domain = (domain or "").strip().lower()
    if mode not in INSTALL_MODES or not target_domain:
        raise HTTPException(status_code=400, detail="validation")

    try:
        outcome = await strato_login_session.begin_login(creds, extra={"mode": mode, "domain": target_domain})
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc

    if isinstance(outcome, strato_login_session.CaptchaRequired):
        return {
            "status": "captcha_required",
            "session_id": outcome.session_id,
            "captcha_image_base64": outcome.captcha_image_base64,
        }

    return await _finish_install(outcome.page, outcome.browser, outcome.playwright, mode=mode, domain=target_domain)


async def resume_install_wordpress_via_automation(session_id: str, captcha_code: str) -> dict[str, Any]:
    try:
        outcome = await strato_login_session.resume_login(session_id, captcha_code)
    except strato_login_session.StratoLoginError as exc:
        raise _map_login_error(exc) from exc
    params = outcome.extra or {}
    return await _finish_install(
        outcome.page, outcome.browser, outcome.playwright, mode=params.get("mode", ""), domain=params.get("domain", "")
    )
