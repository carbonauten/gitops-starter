from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from app.wordpress_automation_service import _open_wordpress_management

# Regression test for a real live failure found in the sibling mailbox
# automation (confirmed via a live screenshot, 2026-11-24): this account's
# login lands on a single product's "STRATO WordPress Hosting Plus"
# overview page, not a global nav with "Website.*Shop" -> "WordPress" links
# as originally guessed - that selector chain matched nothing there. The
# actual entry point is a content card labeled "WordPress & Co. starten"
# ("Installieren Sie Ihre Wunschanwendung.").
PRODUCT_OVERVIEW_HTML = """
<html><body>
  <a href="#" id="wp-card" onclick="window.wpCardClicked = true; return false;">WordPress &amp; Co. starten</a>
</body></html>
"""


def test_open_wordpress_management_clicks_the_wordpress_card():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(PRODUCT_OVERVIEW_HTML)
                await _open_wordpress_management(page)
                assert await page.evaluate("window.wpCardClicked") is True
            finally:
                await browser.close()

    asyncio.run(_run())


# A fallback path must still exist in case this account ever lands
# somewhere else with the originally guessed link chain instead.
FALLBACK_NAV_HTML = """
<html><body>
  <a href="#" onclick="window.websiteNavClicked = true; return false;">Website &amp; Shop</a>
  <a href="#" onclick="window.wordpressLinkClicked = true; return false;">WordPress</a>
</body></html>
"""


def test_open_wordpress_management_falls_back_to_the_original_link_chain():
    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(FALLBACK_NAV_HTML)
                await _open_wordpress_management(page)
                assert await page.evaluate("window.websiteNavClicked") is True
                assert await page.evaluate("window.wordpressLinkClicked") is True
            finally:
                await browser.close()

    asyncio.run(_run())
