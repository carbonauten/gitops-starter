from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from app.strato_automation_service import _choose_free_mailbox_tier, _fill_mailbox_password, _select_mailbox_domain

# Regression test for a real live failure (confirmed via a live screenshot,
# 2026-11-24): "Neu anlegen" opens a Basic (free) vs. Business (paid)
# pricing dialog first, before the actual address/password form - the
# automation went straight for the address field and got stuck on this
# blocking dialog. The button renders a short beat after the dialog opens
# (simulated here via setTimeout, same pattern as the delayed-cookie-banner
# regression test in test_strato_login_session.py).
DELAYED_TIER_DIALOG_HTML = """
<html><body>
  <script>
    setTimeout(() => {
      const el = document.createElement('button');
      el.textContent = 'Basic-Postfach anlegen';
      el.onclick = () => { document.body.setAttribute('data-tier', 'basic'); el.remove(); };
      document.body.appendChild(el);
    }, 300);
  </script>
</body></html>
"""

NO_TIER_DIALOG_HTML = "<html><body><p>No pricing dialog on this flow</p></body></html>"


def test_choose_free_mailbox_tier_clicks_basic_when_dialog_appears():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(DELAYED_TIER_DIALOG_HTML)
                await _choose_free_mailbox_tier(page, timeout=2000)
                assert await page.locator("body[data-tier='basic']").count() == 1
            finally:
                await browser.close()

    asyncio.run(_run())


# Regression test for a second live failure, same day: with the plain
# page-level button click above already deployed, a live run still got
# stuck on exactly this dialog. Pricing/upsell widgets like this one are
# often served from a separate payment micro-frontend embedded via
# <iframe>, which page-level locators never see into - verifies the frame
# fallback actually reaches into one.
def test_choose_free_mailbox_tier_reaches_into_an_iframe():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content("<html><body><iframe id='dialog-frame'></iframe></body></html>")
                frame_element = await page.query_selector("#dialog-frame")
                frame = await frame_element.content_frame()
                await frame.set_content(
                    "<html><body><button onclick=\"document.body.setAttribute('data-tier','basic')\">"
                    "Basic-Postfach anlegen</button></body></html>"
                )
                await _choose_free_mailbox_tier(page, timeout=2000)
                assert await frame.locator("body[data-tier='basic']").count() == 1
            finally:
                await browser.close()

    asyncio.run(_run())


def test_choose_free_mailbox_tier_is_a_noop_when_dialog_is_absent():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(NO_TIER_DIALOG_HTML)
                # Must not raise even though the button never appears.
                await _choose_free_mailbox_tier(page, timeout=500)
            finally:
                await browser.close()

    asyncio.run(_run())


NATIVE_SELECT_HTML = """
<html><body>
  <label for="domain-select">Domain</label>
  <select id="domain-select">
    <option value="1">anderedomain.de</option>
    <option value="2">elphen.ag</option>
  </select>
</body></html>
"""

CUSTOM_COMBOBOX_HTML = """
<html><body>
  <button id="domain-combo" aria-label="Domain" role="combobox" aria-expanded="false">elphen.ag</button>
  <ul id="domain-listbox" style="display:none" role="listbox">
    <li role="option">anderedomain.de</li>
    <li role="option">elphen.ag</li>
  </ul>
  <script>
    document.getElementById('domain-combo').addEventListener('click', () => {
      document.getElementById('domain-listbox').style.display = 'block';
    });
    document.querySelectorAll('#domain-listbox li').forEach((el) => {
      el.addEventListener('click', () => {
        document.getElementById('domain-combo').textContent = el.textContent;
      });
    });
  </script>
</body></html>
"""


async def _run_select(html: str, domain: str) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(html)
            await _select_mailbox_domain(page, domain)
            if await page.locator("select#domain-select").count() > 0:
                value = await page.locator("select#domain-select").input_value()
                return {"kind": "select", "value": value}
            text = await page.locator("#domain-combo").text_content()
            return {"kind": "combobox", "text": text}
        finally:
            await browser.close()


def test_select_mailbox_domain_native_select_picks_matching_option():
    result = asyncio.run(_run_select(NATIVE_SELECT_HTML, "elphen.ag"))
    assert result == {"kind": "select", "value": "2"}


def test_select_mailbox_domain_custom_combobox_clicks_matching_option():
    result = asyncio.run(_run_select(CUSTOM_COMBOBOX_HTML, "elphen.ag"))
    assert result["kind"] == "combobox"
    assert "elphen.ag" in (result["text"] or "")


# Regression test for a third live failure, same day: with the tier dialog
# and domain picker both fixed, a live run filled E-Mail-Adresse and Domain
# fine (both are properly label-associated) but left Passwort completely
# empty - that field has its own password-strength-meter widget, unlike the
# other two, and apparently isn't label-associated the same way, so
# get_by_label matched nothing and the old fill loop silently never ran.
STRENGTH_METER_PASSWORD_HTML = """
<html><body>
  <div class="strength-meter-widget">
    <span class="floating-label">Passwort</span>
    <input type="password" />
    <div class="bars"></div>
  </div>
</body></html>
"""


def test_fill_mailbox_password_falls_back_to_input_type_when_label_is_unassociated():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(STRENGTH_METER_PASSWORD_HTML)
                assert await page.get_by_label(re.compile("Passwort", re.I)).count() == 0

                await _fill_mailbox_password(page, "a-strong-password-1")
                assert await page.locator('input[type="password"]').input_value() == "a-strong-password-1"
            finally:
                await browser.close()

    asyncio.run(_run())
