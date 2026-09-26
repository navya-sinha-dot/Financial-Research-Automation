from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.core.config import settings
from src.core.constants import DEBUG_DIR

logger = logging.getLogger(__name__)


def detect_captcha(page) -> bool:
    selectors = [
        "text=verify you are human",
        "text=access challenge",
        "text=captcha",
        "text=verify you are a human",
        # Cloudflare-style interstitial challenges
        "text=checking your browser",
        "text=just a moment",
        "iframe[src*='challenges.cloudflare.com']",
        "#cf-challenge-running",
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            pass
    return False


def handle_captcha(page, *, is_demo: bool = False) -> bool:
    if not detect_captcha(page):
        return False

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(DEBUG_DIR / "captcha_detected.png"), full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        (DEBUG_DIR / "captcha_detected.html").write_text(html, encoding="utf-8")
    except Exception:
        pass

    logger.warning("CAPTCHA or access challenge detected.")
    if is_demo:
        logger.warning("CAPTCHA/access challenge detected. Please complete it manually in Chromium. The pipeline will continue after completion.")
        page.wait_for_timeout(int(getattr(settings, "SCRAPER_TIMEOUT", 30000)))
        return False
    raise RuntimeError("CAPTCHA or access challenge detected. The pipeline stopped safely without bypassing it.")
