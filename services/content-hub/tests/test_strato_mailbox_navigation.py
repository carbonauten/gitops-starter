from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from app.strato_automation_service import _open_email_management

# Regression test for a real live failure (confirmed via a live screenshot,
# 2026-11-24): this account's login lands on a single product's "STRATO
# WordPress Hosting Plus" overview page, not a global nav with a plain
# "E-Mail" link as originally guessed - that selector matched nothing, the
# click silently never happened, and _create_mailbox()'s own "Neu anlegen"
# click then failed with an unrelated-looking error two steps later. The
# actual entry point on that page is a content card labeled "E-Mails
# verwalten". The card's onclick swaps itself for an "E-Mail-Verwaltung"
# link (simulating the real two-step navigation) instead of using a real
# href, since this test has no server behind it to navigate to.
PRODUCT_OVERVIEW_HTML = """
<html><body>
  <a href="#" id="email-card" onclick="
    window.emailCardClicked = true;
    this.remove();
    const link = document.createElement('a');
    link.href = '#';
    link.textContent = 'E-Mail-Verwaltung';
    link.onclick = () => { window.managementLinkClicked = true; return false; };
    document.body.appendChild(link);
    return false;
  ">E-Mails verwalten</a>
</body></html>
"""


def test_open_email_management_clicks_card_then_management_link():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(PRODUCT_OVERVIEW_HTML)
                await _open_email_management(page)
                assert await page.evaluate("window.emailCardClicked") is True
                assert await page.evaluate("window.managementLinkClicked") is True
            finally:
                await browser.close()

    asyncio.run(_run())
