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
    parser = argparse.ArgumentParser(description="Run the end-to-end SEC filing pipeline for a company.")
    parser.add_argument("ticker", help="Ticker to analyze")
    parser.add_argument("--demo", action="store_true", help="Display the browser while scraping")
    parser.add_argument("--headless", action="store_true", help="Run without visible UI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings.SCRAPER_HEADLESS = args.headless or not args.demo
    settings.SCRAPER_SLOW_MO = 500 if args.demo else 0
    ticker = args.ticker.upper()

    logging.info("==================================================")
    logging.info("FINANCIAL RESEARCH AUTOMATION")
    logging.info("==================================================")
    logging.info("[INFO] Ticker: %s", ticker)

    filing = discover_latest_filing(ticker)
    logger.info("[OK] Company resolved: %s", filing["company_name"])

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    result = scrape_filing(ticker, filing["filing_url"], demo=args.demo)
    logger.info("[OK] Pipeline complete for %s", ticker)
    print(result)

    close_browser()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
