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
from src.ingestion.normalizer import derive_canonical_line_items, normalize_financial_value

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


def _compact(text: str) -> str:
    return "".join(text.lower().split())


def _text_before_table(table, max_chars: int = 400) -> str:
    """Concatenates the raw text immediately preceding `table`, stopping the
    moment a node belongs to an earlier <table> (which structurally rules
    out Table of Contents entries -- they always sit inside their own
    table). Nodes are joined with NO separator, matching how they actually
    render: real filings often split a statement's heading across several
    adjacent DOM text nodes (e.g. inline XBRL tagging) instead of one clean
    element, and inserting a space would break the reconstructed phrase.
    """
    parts: list[str] = []
    total = 0
    for node in table.find_all_previous(string=True):
        if node.find_parent("table") is not None:
            break
        text = str(node)
        parts.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "".join(reversed(parts))


# Heading variant -> other variants that must NOT also be present nearby.
# Guards against e.g. "INCOME STATEMENTS" matching inside the heading for
# the *comprehensive* income statement, a different table entirely.
_HEADING_EXCLUSIONS: dict[str, list[str]] = {
    "incomestatements": ["comprehensiveincomestatements"],
}


def _hint_is_trailing(hint: str, preceding: str, *, tail_slack: int = 8) -> bool:
    """True if `hint` is (essentially) the last thing said before the
    table, not just mentioned somewhere earlier in a longer, unrelated
    sentence (e.g. a disclosure paragraph that happens to reference the
    statement's name in passing). `tail_slack` allows a few stray trailing
    characters (odd punctuation, stray entities) without requiring an exact
    suffix match.
    """
    idx = preceding.rfind(hint)
    if idx == -1:
        return False
    return len(preceding) - (idx + len(hint)) <= tail_slack


def extract_table(page, table_text_hint: str | list[str]):
    """Finds the data table for a statement heading.

    Real filings use different wording for the same statement -- Apple
    titles it "CONSOLIDATED STATEMENTS OF OPERATIONS", Microsoft just
    "INCOME STATEMENTS" -- so `table_text_hint` may be a single string or a
    list of known variants, checked in order against the text immediately
    preceding each table (see `_text_before_table`). The match must land at
    the end of that preceding text (see `_hint_is_trailing`) so a long,
    unrelated sentence that merely mentions the heading in passing -- e.g.
    right before a Table of Contents table -- isn't mistaken for it.
    """
    hints = [table_text_hint] if isinstance(table_text_hint, str) else list(table_text_hint)
    compact_hints = [_compact(h) for h in hints]

    soup = BeautifulSoup(page.content(), "lxml")
    for table in soup.find_all("table"):
        preceding = _compact(_text_before_table(table))
        for hint in compact_hints:
            if not _hint_is_trailing(hint, preceding):
                continue
            if any(excluded in preceding for excluded in _HEADING_EXCLUSIONS.get(hint, [])):
                continue
            return table

    # Fallback for filings where no heading variant matches at all: search
    # inside every table directly.
    tables = soup.find_all("table")
    for table in tables:
        table_text = _compact(table.get_text(" "))
        if any(hint in table_text for hint in compact_hints):
            return table
    if tables:
        return tables[0]
    raise ValueError(f"Could not locate table for {hints[0]}.")


def extract_financial_rows(page, table_text_hint: str | list[str]) -> dict[str, Any]:
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

    for step_name, hints, key in [
        (
            "[5/10] Scraping Income Statement",
            [
                "CONSOLIDATED STATEMENTS OF OPERATIONS",
                "CONSOLIDATED STATEMENTS OF INCOME",
                "STATEMENTS OF OPERATIONS",
                "STATEMENTS OF INCOME",
                "INCOME STATEMENTS",
            ],
            "income_statement",
        ),
        (
            "[6/10] Scraping Balance Sheet",
            ["CONSOLIDATED BALANCE SHEETS", "BALANCE SHEETS", "STATEMENTS OF FINANCIAL POSITION"],
            "balance_sheet",
        ),
        (
            "[7/10] Scraping Cash Flow",
            [
                "CONSOLIDATED STATEMENTS OF CASH FLOWS",
                "STATEMENTS OF CASH FLOWS",
                "CASH FLOWS STATEMENTS",
                "CASH FLOW STATEMENTS",
            ],
            "cash_flow",
        ),
    ]:
        logger.info(step_name)
        raw_rows = extract_financial_rows(active_page, hints)
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


def _infer_period(period_of_report: str) -> tuple[str, int, date]:
    """Derive a calendar (period_type, fiscal_year, report_date) triple from a filing's report date.

    Returns a real `date` object, not the raw ISO string -- SQLite's driver
    (unlike Postgres') refuses to store a plain string into a Date column.
    """
    report_date = date.fromisoformat(period_of_report)
    quarter = (report_date.month - 1) // 3 + 1
    return f"Q{quarter}", report_date.year, report_date


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

            period_type, fiscal_year, report_date = _infer_period(filing["period_of_report"])
            raw_items = {
                **result["statements"].get("income_statement", {}),
                **result["statements"].get("balance_sheet", {}),
                **result["statements"].get("cash_flow", {}),
            }
            periods.append(
                {
                    "period_type": period_type,
                    "fiscal_year": fiscal_year,
                    "report_date": report_date,
                    # Raw filing labels are kept as-is (for the Financial
                    # Statements table); canonical keys are added alongside
                    # them so KPI cards and ratio math have something to read.
                    "items": {**raw_items, **derive_canonical_line_items(raw_items)},
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
