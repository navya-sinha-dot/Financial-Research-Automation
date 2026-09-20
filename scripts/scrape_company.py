from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.config import settings
from src.core.logging_config import configure_logging
from src.ingestion.browser import close_browser
from src.ingestion.filing_discovery import discover_latest_filing
from src.ingestion.scraper import scrape_filing

configure_logging(level=getattr(settings, "LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape a company filing from SEC EDGAR using Chromium and Playwright.")
    parser.add_argument("ticker", help="Ticker to analyze, e.g. AAPL")
    parser.add_argument("--demo", action="store_true", help="Open a visible browser for demonstration")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser window")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings.SCRAPER_HEADLESS = args.headless or not args.demo
    settings.SCRAPER_SLOW_MO = 500 if args.demo else 0

    ticker = args.ticker.upper()
    filing = discover_latest_filing(ticker)
    logger.info("Resolved %s for %s", filing["company_name"], ticker)
    try:
        result = scrape_filing(ticker, filing["filing_url"], demo=args.demo)
        print(result)
        return 0
    finally:
        close_browser()


if __name__ == "__main__":
    raise SystemExit(main())
