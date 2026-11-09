"""Browser-automation mailbox creation for Strato, used only because Strato
publishes no API for this (confirmed by research - only the "E-Mail-
Verwaltung" web panel supports creating a mailbox). An IT-Master's full
Strato customer-login (strato_config_service.py) drives a headless Chromium
browser through the real customer panel to click through mailbox creation on
their behalf.

**This has not been exercised against a live Strato account.** The
selectors below are written from two screenshots of the login page and the
E-Mail-Verwaltung overview - not from inspecting the live DOM of the actual
"Neu anlegen" dialog, which was never seen. Treat every selector here as a
best guess that will very likely need adjustment the first time this runs
for real; that's why every step is wrapped individually with a specific
error code and a failure screenshot, so a human can see exactly where it
broke and fix the one selector that's wrong instead of debugging blind.

Known failure modes this cannot handle:
- Two-factor authentication / CAPTCHA on login (detected best-effort, surfaced
  as a distinct error rather than hanging)
- Any Strato UI change (new field layout, renamed buttons, a confirmation
  step this code doesn't know about)
- Concurrent manual session: logging in here may terminate a session the
  IT-Master has open in their own browser, and vice versa (Strato's login
  page already shows this warning in normal use)
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

STEP_LOGIN = "strato_automation_login_failed"
STEP_2FA = "strato_automation_2fa_or_captcha"
STEP_NAVIGATE = "strato_automation_navigation_failed"
STEP_CREATE = "strato_automation_create_failed"
STEP_UNEXPECTED = "strato_automation_unexpected_error"


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
        raise StratoAutomationError(STEP_2FA, await _safe_screenshot(page))


async def _open_email_management(page: Any) -> None:
    email_nav = page.get_by_role("link", name=re.compile(r"^E-Mail$", re.I))
    if await email_nav.count() > 0:
        await email_nav.first.click()
    management_link = page.get_by_role("link", name=re.compile("E-Mail-Verwaltung", re.I))
    if await management_link.count() > 0:
        await management_link.first.click()
    await page.wait_for_load_state("networkidle", timeout=20000)


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
    await page.wait_for_load_state("networkidle", timeout=20000)
    await page.get_by_text(f"{local_part}@{domain}", exact=False).first.wait_for(timeout=10000)


async def _run_step(page: Any, code: str, awaitable: Any) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        await awaitable
    except StratoAutomationError:
        raise
    except PlaywrightTimeoutError as exc:
        raise StratoAutomationError(code, await _safe_screenshot(page)) from exc
    except Exception as exc:  # noqa: BLE001 - never let an unexpected Playwright/site error become a raw 500
        logger.exception("Unexpected error during Strato automation step %s", code)
        raise StratoAutomationError(STEP_UNEXPECTED, await _safe_screenshot(page)) from exc


async def create_mailbox_via_automation(
    db: Session,
    *,
    local_part: str,
    domain: str,
    password: str,
) -> dict[str, Any]:
    creds = resolve_strato_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    local = (local_part or "").strip().lower()
    target_domain = (domain or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", local) or not target_domain or not password:
        raise HTTPException(status_code=400, detail="validation")

    # Imported lazily so the rest of the app (and the checks above) work even
    # in environments where the playwright package/browser isn't installed.
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = None
        try:
            # Launching Chromium/creating the context/page can itself fail
            # (missing browser binary, OOM, ...) - that's arguably the most
            # likely real-world failure mode of this whole feature, so it
            # must land in StratoAutomationError exactly like the three named
            # steps below, not bypass it as a raw, untranslated 500.
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(locale="de-DE")
            page = await context.new_page()
            await _run_step(page, STEP_LOGIN, _login(page, creds))
            await _run_step(page, STEP_NAVIGATE, _open_email_management(page))
            await _run_step(
                page,
                STEP_CREATE,
                _create_mailbox(page, local_part=local, domain=target_domain, password=password),
            )
        except StratoAutomationError:
            raise
        except Exception as exc:  # noqa: BLE001 - see _run_step's docstring; same rationale applies to setup
            logger.exception("Unexpected error setting up the Strato automation browser")
            raise StratoAutomationError(STEP_UNEXPECTED, None) from exc
        finally:
            if browser is not None:
                await browser.close()

    return {"email": f"{local}@{target_domain}", "local_part": local, "domain": target_domain}
