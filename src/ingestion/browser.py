from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from src.core.config import settings
from src.core.constants import DEBUG_DIR

logger = logging.getLogger(__name__)

_browser: Optional[Browser] = None


def launch_browser() -> Browser:
    global _browser
    if _browser is not None:
        return _browser
    headless = str(getattr(settings, "SCRAPER_HEADLESS", False)).lower() in {"1", "true", "yes"}
    slow_mo = int(getattr(settings, "SCRAPER_SLOW_MO", 0))
    playwright = sync_playwright().start()
    _browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
    logger.info("Chromium launched with headless=%s slow_mo=%s", headless, slow_mo)
    return _browser


def create_page() -> Page:
    browser = launch_browser()
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    return page


def close_browser() -> None:
    global _browser
    if _browser is not None:
        _browser.close()
        _browser = None
        logger.info("Chromium browser closed")


def save_debug_screenshot(name: str, page=None) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / name
    if page is not None:
        page.screenshot(path=str(path), full_page=True)
    return path


def save_debug_html(name: str, html: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / name
    path.write_text(html, encoding="utf-8")
    return path
