from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from app.wordpress_automation_service import _fill_site_title_if_empty, _select_domain

# Confirmed via a live screenshot (2026-11-24): Strato's domain field
# combines domain + path ("elphen.ag - /") rather than a bare domain name,
# and its exact markup (native <select> vs. a custom combobox) is unknown -
# these fixtures exercise _select_domain() against a real headless browser
# for both possibilities rather than hand-rolled Locator fakes, since the
# xpath/role-based traversal in the real function is easy to get subtly
# wrong against fakes that don't behave like a real DOM.

NATIVE_SELECT_HTML = """
<html><body>
  <label for="domain-select">Ihre Domains und Subdomains</label>
  <select id="domain-select">
    <option value="1">anderedomain.de - /</option>
    <option value="2">elphen.ag - /</option>
  </select>
</body></html>
"""

CUSTOM_COMBOBOX_HTML = """
<html><body>
  <button id="domain-combo" aria-label="Ihre Domains und Subdomains" role="combobox" aria-expanded="false">elphen.ag - /</button>
  <ul id="domain-listbox" style="display:none" role="listbox">
    <li role="option">anderedomain.de - /</li>
    <li role="option">elphen.ag - /</li>
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
            await _select_domain(page, domain)
            if await page.locator("select#domain-select").count() > 0:
                value = await page.locator("select#domain-select").input_value()
                return {"kind": "select", "value": value}
            text = await page.locator("#domain-combo").text_content()
            return {"kind": "combobox", "text": text}
        finally:
            await browser.close()


def test_select_domain_native_select_picks_matching_option():
    result = asyncio.run(_run_select(NATIVE_SELECT_HTML, "elphen.ag"))
    assert result == {"kind": "select", "value": "2"}


def test_select_domain_custom_combobox_clicks_matching_option():
    result = asyncio.run(_run_select(CUSTOM_COMBOBOX_HTML, "elphen.ag"))
    assert result["kind"] == "combobox"
    assert "elphen.ag" in (result["text"] or "")


TITLE_FIELD_HTML = """
<html><body>
  <label for="site-title">Titel der Webseite</label>
  <input id="site-title" type="text" value="{value}" />
</body></html>
"""


async def _run_fill_title(initial_value: str, title: str) -> str:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(TITLE_FIELD_HTML.format(value=initial_value))
            await _fill_site_title_if_empty(page, title)
            return await page.locator("#site-title").input_value()
        finally:
            await browser.close()


def test_fill_site_title_fills_when_empty():
    result = asyncio.run(_run_fill_title("", "carbonauten.com"))
    assert result == "carbonauten.com"


def test_fill_site_title_leaves_existing_value_untouched():
    result = asyncio.run(_run_fill_title("Already Set", "carbonauten.com"))
    assert result == "Already Set"
