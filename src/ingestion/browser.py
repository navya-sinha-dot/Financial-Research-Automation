from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from src.core.config import settings
from src.core.constants import DEBUG_DIR

logger = logging.getLogger(__name__)

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_contexts: List[BrowserContext] = []

# Realistic, current desktop Chrome UA strings to rotate through. Avoids the
# single static User-Agent that automation frameworks default to.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# Common desktop viewport sizes; picking from a pool beats one fixed size.
_VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
]

_TIMEZONES = ["America/New_York", "America/Chicago", "America/Los_Angeles"]

# Patches applied on every new document to remove the most common automation
# fingerprints (navigator.webdriver, empty plugin/mimeType lists, missing
# window.chrome). This is standard, defensive scraping hygiene against a
# public government site that has no login/paywall to bypass -- it just
# avoids looking like a bare headless client on every request.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : undefined;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
        parameters && parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
}
"""


def launch_browser() -> Browser:
    global _playwright, _browser
    if _browser is not None:
        return _browser
    headless = str(getattr(settings, "SCRAPER_HEADLESS", False)).lower() in {"1", "true", "yes"}
    slow_mo = int(getattr(settings, "SCRAPER_SLOW_MO", 0))
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    logger.info("Chromium launched with headless=%s slow_mo=%s", headless, slow_mo)
    return _browser


def create_page() -> Page:
    """Creates a fresh browser context (randomized fingerprint) and returns its page.

    A new context per logical scraping session keeps cookies/storage isolated
    and lets each session present a slightly different, still-realistic
    fingerprint rather than one static signature reused on every request.
    """
    browser = launch_browser()
    context = browser.new_context(
        viewport=random.choice(_VIEWPORTS),
        user_agent=random.choice(_USER_AGENTS),
        locale="en-US",
        timezone_id=random.choice(_TIMEZONES),
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    context.add_init_script(_STEALTH_INIT_SCRIPT)
    _contexts.append(context)
    page = context.new_page()
    return page


def human_delay(min_ms: Optional[int] = None, max_ms: Optional[int] = None) -> None:
    """Sleeps a short, randomized interval to avoid a robotic fixed-cadence request pattern."""
    lo = min_ms if min_ms is not None else int(getattr(settings, "SCRAPER_MIN_DELAY_MS", 250))
    hi = max_ms if max_ms is not None else int(getattr(settings, "SCRAPER_MAX_DELAY_MS", 900))
    if hi <= 0:
        return
    time.sleep(random.uniform(lo, hi) / 1000.0)


def close_browser() -> None:
    global _browser, _playwright, _contexts
    for context in _contexts:
        try:
            context.close()
        except Exception:
            pass
    _contexts = []
    if _browser is not None:
        _browser.close()
        _browser = None
        logger.info("Chromium browser closed")
    if _playwright is not None:
        _playwright.stop()
        _playwright = None


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
