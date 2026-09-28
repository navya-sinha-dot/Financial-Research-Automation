"""SEC filing scraper built around Playwright and Chromium."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from src.core.config import settings
from src.ingestion.browser import close_browser, create_page, human_delay, save_debug_html, save_debug_screenshot
from src.ingestion.captcha_handler import handle_captcha
from src.ingestion.filing_discovery import discover_recent_filings
from src.ingestion.normalizer import normalize_financial_value

logger = logging.getLogger(__name__)


def open_filing(url: str, page=None):
    """Navigates to a filing URL, creating a new page if one isn't supplied.

    Passing an existing `page` lets multi-quarter backfill reuse a single
    browser context/tab across filings instead of relaunching per filing.
    """
    page = page or create_page()
    _goto_with_retry(page, url)
    logger.info("[BROWSER] goto(%s)", url)
    save_debug_screenshot("01_sec_page.png", page)
    return page


@retry(
    retry=retry_if_exception_type(PlaywrightTimeoutError),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=20),
    reraise=True,
)
def _goto_with_retry(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=int(getattr(settings, "SCRAPER_TIMEOUT", 30000)))


def wait_for_filing(page, *, timeout: int = 30000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout)
    if handle_captcha(page, is_demo=str(getattr(settings, "SCRAPER_HEADLESS", "false")).lower() == "false"):
        logger.info("[BROWSER] challenge cleared")
    human_delay()
    logger.info("[BROWSER] page loaded")
    save_debug_screenshot("02_filing_loaded.png", page)


def locate_income_statement(page):
    locator = page.locator("text=CONSOLIDATED STATEMENTS OF OPERATIONS")
    if locator.count() > 0:
        logger.info('[BROWSER] searching for "CONSOLIDATED STATEMENTS OF OPERATIONS"')
        return True
    return False


def locate_balance_sheet(page):
    return (
        page.locator("text=CONSOLIDATED BALANCE SHEETS").count() > 0 or page.locator("text=BALANCE SHEET").count() > 0
    )


def locate_cash_flow_statement(page):
    return (
        page.locator("text=CONSOLIDATED STATEMENTS OF CASH FLOWS").count() > 0
        or page.locator("text=CASH FLOW").count() > 0
    )


def extract_table(page, table_text_hint: str):
    """Finds the data table for a statement heading like "CONSOLIDATED
    STATEMENTS OF OPERATIONS".

    Real SEC filings also list that same heading inside their Table of
    Contents (as a sentence like "Consolidated Statements of Operations for
    the years ended ..."), which sits inside its own <table> earlier in the
    document. Naively searching "does any table contain this text" matches
    the ToC first and never reaches the real data. Instead: find the
    heading as its own short, standalone element (not itself inside a
    table -- the ToC entry is), then take the table that follows it.
    """
    soup = BeautifulSoup(page.content(), "lxml")
    hint = table_text_hint.lower()

    for el in soup.find_all(string=lambda s: s and hint in s.lower()):
        parent = el.parent
        if parent is None or parent.find_parent("table") is not None:
            continue  # inside a table -- likely a Table of Contents entry
        own_text = " ".join(parent.get_text(" ").split())
        if len(own_text) > len(hint) + 60:
            continue  # a long sentence that happens to mention the heading
        table = parent.find_next("table")
        if table is not None:
            return table

    # Fallback for filings where the heading isn't its own element: search
    # inside every table directly, same as before.
    tables = soup.find_all("table")
    for table in tables:
        if hint in table.get_text(" ").lower():
            return table
    if tables:
        return tables[0]
    raise ValueError(f"Could not locate table for {table_text_hint}.")


def extract_financial_rows(page, table_text_hint: str) -> dict[str, Any]:
    table = extract_table(page, table_text_hint)
    result: dict[str, Any] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = " ".join(cells[0].get_text(" ").split())
        value = " ".join(cells[1].get_text(" ").split())
        if label and value:
            result[label] = value
    return result


def extract_financial_value(raw_text: str) -> float | None:
    return normalize_financial_value(raw_text)


def scrape_filing(
    ticker: str, filing_url: str, *, demo: bool = False, page=None, keep_open: bool = False
) -> dict[str, Any]:
    """Scrapes a single filing. Pass `page` + `keep_open=True` to reuse a
    browser tab across multiple filings during historical backfill instead
    of paying the launch/context cost for every quarter.
    """
    logger.info(
        "[3/10] Opening filing for %s (%s)", ticker.upper(), "reused tab" if page is not None else "new browser"
    )
    active_page = open_filing(filing_url, page=page)
    logger.info("[OK] Browser ready")

    logger.info("[4/10] Waiting for filing to render")
    wait_for_filing(active_page)
    logger.info("[OK] Filing loaded")

    # Save the raw HTML immediately, before attempting extraction. If
    # extraction fails below, this is the artifact you need to diagnose why
    # -- saving it only on success would mean it's missing exactly when
    # you need it most.
    save_debug_html("filing_content.html", active_page.content())

    statements: dict[str, dict[str, Any]] = {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    for step_name, hint, key in [
        ("[5/10] Scraping Income Statement", "CONSOLIDATED STATEMENTS OF OPERATIONS", "income_statement"),
        ("[6/10] Scraping Balance Sheet", "CONSOLIDATED BALANCE SHEETS", "balance_sheet"),
        ("[7/10] Scraping Cash Flow", "CONSOLIDATED STATEMENTS OF CASH FLOWS", "cash_flow"),
    ]:
        logger.info(step_name)
        raw_rows = extract_financial_rows(active_page, hint)
        if not raw_rows:
            raise ValueError(f"Could not locate the {key} in the filing.")
        for label, raw in raw_rows.items():
            normalized = extract_financial_value(raw)
            if normalized is not None:
                statements[key][label] = normalized
        logger.info("[OK] %s extracted", key.replace("_", " ").title())
        human_delay()

    if not keep_open:
        close_browser()
        logger.info("[10/10] Closing browser")

    return {
        "ticker": ticker.upper(),
        "statements": {**statements},
    }


def _infer_period(period_of_report: str) -> tuple[str, int]:
    """Derive a calendar (period_type, fiscal_year) pair from a filing's report date."""
    report_date = date.fromisoformat(period_of_report)
    quarter = (report_date.month - 1) // 3 + 1
    return f"Q{quarter}", report_date.year


def fetch_company_financials(ticker: str) -> dict[str, Any]:
    """Scrapes multiple recent SEC filings (historical backfill) so ratio
    analytics (YoY/QoQ) have real multi-quarter data instead of one snapshot.

    Reuses a single browser tab across filings for speed, and raises if no
    filing can be found or parsed -- there is no synthetic fallback data.
    """
    limit = int(getattr(settings, "SCRAPER_BACKFILL_QUARTERS", 4))
    filings = discover_recent_filings(ticker, limit=limit)

    company_name: str | None = None
    periods: list[dict[str, Any]] = []
    page = create_page()
    try:
        for i, filing in enumerate(filings):
            company_name = company_name or filing["company_name"]
            try:
                result = scrape_filing(ticker, filing["filing_url"], demo=False, page=page, keep_open=True)
            except Exception as exc:
                logger.warning(
                    "Skipping filing %s for %s after scrape failure: %s", filing.get("accession_number"), ticker, exc
                )
                continue

            period_type, fiscal_year = _infer_period(filing["period_of_report"])
            periods.append(
                {
                    "period_type": period_type,
                    "fiscal_year": fiscal_year,
                    "report_date": filing["period_of_report"],
                    "items": {
                        **result["statements"].get("income_statement", {}),
                        **result["statements"].get("balance_sheet", {}),
                        **result["statements"].get("cash_flow", {}),
                    },
                }
            )
            if i < len(filings) - 1:
                human_delay(1000, 2500)
    finally:
        close_browser()

    if not periods:
        raise ValueError(f"No filings could be scraped for {ticker}.")

    # Chronological order (oldest first) so YoY/QoQ growth math lines up.
    periods.sort(key=lambda p: p["report_date"])

    return {
        "ticker": ticker.upper(),
        "name": company_name or f"{ticker.upper()} Corporation",
        "periods": periods,
    }
