"""Browser-automation WordPress management for Strato, used only because
Strato publishes no API for installing or listing WordPress sites (same
situation as mailbox creation in strato_automation_service.py). An
IT-Master's or Designer's stored Strato customer-login drives a headless
Chromium browser through the real "Website & Shop > WordPress & Co."
customer panel on their behalf.

**This has not been exercised against a live Strato account.** The
selectors below are written from a single screenshot of the WordPress & Co.
overview page (two mode cards - "Flexibilitaets-Modus" / "Sicherheits-Modus"
- each with an "Installieren" button, and a table of existing installations
below with "Bezeichnung" as its first column) - not from inspecting the live
DOM of the actual install dialog, which was never seen. Treat every selector
here as a best guess that will very likely need adjustment the first time
this runs for real; that's why every step is wrapped individually with a
specific error code and a failure screenshot, exactly like
strato_automation_service.py.

Deliberately NOT sharing code with strato_automation_service.py: both
modules are untested browser automation against a third-party site that
changes outside our control, so keeping them independent means fixing a
broken selector in one never risks silently breaking the other.

Known failure modes this cannot handle: see strato_automation_service.py's
docstring - the same caveats (2FA/captcha, Strato UI changes, concurrent
manual session) apply here.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .strato_config_service import StratoCredentials, resolve_strato_credentials

logger = logging.getLogger(__name__)

STEP_LOGIN = "wordpress_automation_login_failed"
STEP_2FA = "wordpress_automation_2fa_or_captcha"
STEP_NAVIGATE = "wordpress_automation_navigation_failed"
STEP_LIST = "wordpress_automation_list_failed"
STEP_INSTALL = "wordpress_automation_install_failed"
STEP_UNEXPECTED = "wordpress_automation_unexpected_error"

INSTALL_MODES = ("flexibility", "security")
_MODE_CARD_TITLES = {"flexibility": "Flexibilitäts-Modus", "security": "Sicherheits-Modus"}


class WordPressAutomationError(Exception):
    """Carries a translatable error code plus an optional failure screenshot
    (base64 PNG) - routes/wordpress.py renders both, same as
    StratoAutomationError in strato_automation_service.py."""

    def __init__(self, code: str, screenshot_base64: str | None = None):
        self.code = code
        self.screenshot_base64 = screenshot_base64
        super().__init__(code)


async def _safe_screenshot(page: Any) -> str | None:
    try:
        data = await page.screenshot(type="png")
        return base64.b64encode(data).decode("ascii")
    except Exception:  # noqa: BLE001 - screenshot is best-effort debug info, never the real failure
        return None


async def _login(page: Any, creds: StratoCredentials) -> None:
    await page.goto("https://www.strato.de/login", wait_until="domcontentloaded", timeout=20000)
    await page.get_by_label(re.compile("Benutzername|Kundennummer", re.I)).first.fill(creds.customer_number)
    await page.get_by_label(re.compile("Passwort", re.I)).first.fill(creds.password)
    await page.get_by_role("button", name=re.compile("Login", re.I)).click()
    await page.wait_for_load_state("networkidle", timeout=20000)
    if await page.get_by_text(re.compile("Captcha|Sicherheitscode|Zwei-Faktor|2FA|Bestätigungscode", re.I)).count() > 0:
        raise WordPressAutomationError(STEP_2FA, await _safe_screenshot(page))


async def _open_wordpress_management(page: Any) -> None:
    website_nav = page.get_by_role("link", name=re.compile("Website.*Shop", re.I))
    if await website_nav.count() > 0:
        await website_nav.first.click()
    wordpress_link = page.get_by_role("link", name=re.compile("WordPress", re.I))
    if await wordpress_link.count() > 0:
        await wordpress_link.first.click()
    await page.wait_for_load_state("networkidle", timeout=20000)


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


async def _install(page: Any, *, mode: str, domain: str) -> None:
    card_title = _MODE_CARD_TITLES[mode]
    heading = page.get_by_text(re.compile(re.escape(card_title), re.I)).first
    install_button = heading.locator("xpath=following::button[1]")
    await install_button.click()
    await page.wait_for_load_state("networkidle", timeout=20000)

    domain_field = page.get_by_label(re.compile("Domain|Subdomain", re.I))
    if await domain_field.count() > 0:
        await domain_field.first.select_option(label=domain)

    confirm_button = page.get_by_role("button", name=re.compile("Installieren|Weiter|Bestätigen", re.I))
    if await confirm_button.count() > 0:
        await confirm_button.first.click()
    await page.wait_for_load_state("networkidle", timeout=20000)
    await page.get_by_text(re.compile("installiert|erfolgreich", re.I)).first.wait_for(timeout=15000)


async def _run_step(page: Any, code: str, awaitable: Any) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        await awaitable
    except WordPressAutomationError:
        raise
    except PlaywrightTimeoutError as exc:
        raise WordPressAutomationError(code, await _safe_screenshot(page)) from exc
    except Exception as exc:  # noqa: BLE001 - never let an unexpected Playwright/site error become a raw 500
        logger.exception("Unexpected error during WordPress automation step %s", code)
        raise WordPressAutomationError(STEP_UNEXPECTED, await _safe_screenshot(page)) from exc


async def list_wordpress_installations(db: Session) -> list[dict[str, str]]:
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    # Imported lazily so the rest of the app works even in environments
    # where the playwright package/browser isn't installed.
    from playwright.async_api import async_playwright

    installations: list[dict[str, str]] = []
    async with async_playwright() as pw:
        browser = None
        try:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(locale="de-DE")
            page = await context.new_page()
            await _run_step(page, STEP_LOGIN, _login(page, creds))
            await _run_step(page, STEP_NAVIGATE, _open_wordpress_management(page))

            async def _scrape() -> None:
                nonlocal installations
                installations = await _scrape_installations(page)

            await _run_step(page, STEP_LIST, _scrape())
        except WordPressAutomationError:
            raise
        except Exception as exc:  # noqa: BLE001 - see _run_step's docstring; same rationale applies to setup
            logger.exception("Unexpected error setting up the WordPress automation browser")
            raise WordPressAutomationError(STEP_UNEXPECTED, None) from exc
        finally:
            if browser is not None:
                await browser.close()

    return installations


async def install_wordpress_via_automation(db: Session, *, mode: str, domain: str) -> dict[str, str]:
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    target_domain = (domain or "").strip().lower()
    if mode not in INSTALL_MODES or not target_domain:
        raise HTTPException(status_code=400, detail="validation")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = None
        try:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(locale="de-DE")
            page = await context.new_page()
            await _run_step(page, STEP_LOGIN, _login(page, creds))
            await _run_step(page, STEP_NAVIGATE, _open_wordpress_management(page))
            await _run_step(page, STEP_INSTALL, _install(page, mode=mode, domain=target_domain))
        except WordPressAutomationError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error setting up the WordPress automation browser")
            raise WordPressAutomationError(STEP_UNEXPECTED, None) from exc
        finally:
            if browser is not None:
                await browser.close()

    return {"domain": target_domain, "mode": mode}
