"""Real-browser fetching for JS-rendered vendors (doc 00 §8.4, doc 02 §2).

Playwright is required for the JS vendors (mylife, city-plumbing). Install:
    pip install playwright && playwright install chromium
The scraper falls back to HTTP-only for SSR vendors, so this is only pulled
in when a vendor sets uses_js=True.
"""
from __future__ import annotations

import logging

log = logging.getLogger("scraper.browser")

_page = None


def _get_page():
    global _page
    if _page is not None:
        return _page
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright not installed. JS vendor (mylife, city-plumbing) needs: "
            "pip install playwright && playwright install chromium"
        ) from e
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 900},
        locale="en-GB",
    )
    _page = ctx.new_page()
    return _page


def fetch_js(url: str, wait_selector: str | None = None, timeout_ms: int = 30000) -> str | None:
    """Render a JS page and return its HTML. Reuses one browser/page."""
    page = _get_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
        page.wait_for_timeout(1500)  # let lazy content settle
        return page.content()
    except Exception as e:
        log.warning("playwright fetch failed %s: %s", url, e)
        return None


def close_browser():
    global _page
    if _page is not None:
        try:
            _page.context.browser.close()
        except Exception:
            pass
        _page = None