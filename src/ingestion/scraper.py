"""SEC filing scraper built around Playwright and Chromium."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, Iterable

from src.core.config import settings
from src.core.constants import DEBUG_DIR
from src.ingestion.browser import create_page, save_debug_html, save_debug_screenshot, close_browser
from src.ingestion.captcha_handler import handle_captcha
from src.ingestion.filing_discovery import discover_latest_filing
from src.ingestion.normalizer import normalize_financial_value
from src.ingestion.parser import parse_financial_statements

logger = logging.getLogger(__name__)


def open_filing(url: str):
    page = create_page()
    page.goto(url, wait_until="domcontentloaded", timeout=int(getattr(settings, "SCRAPER_TIMEOUT", 30000)))
    logger.info("[BROWSER] goto(%s)", url)
    save_debug_screenshot("01_sec_page.png", page)
    return page


def wait_for_filing(page, *, timeout: int = 30000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout)
    if handle_captcha(page, is_demo=str(getattr(settings, "SCRAPER_HEADLESS", "false")).lower() == "false"):
        logger.info("[BROWSER] challenge cleared")
    logger.info("[BROWSER] page loaded")
    save_debug_screenshot("02_filing_loaded.png", page)


def locate_income_statement(page):
    locator = page.locator("text=CONSOLIDATED STATEMENTS OF OPERATIONS")
    if locator.count() > 0:
        logger.info("[BROWSER] searching for \"CONSOLIDATED STATEMENTS OF OPERATIONS\"")
        return True
    return False


def locate_balance_sheet(page):
    return page.locator("text=CONSOLIDATED BALANCE SHEETS").count() > 0 or page.locator("text=BALANCE SHEET").count() > 0


def locate_cash_flow_statement(page):
    return page.locator("text=CONSOLIDATED STATEMENTS OF CASH FLOWS").count() > 0 or page.locator("text=CASH FLOW").count() > 0


def extract_table(page, table_text_hint: str):
    html = page.content()
    matches = re.findall(r"<table[^>]*>(.*?)</table>", html, flags=re.IGNORECASE | re.DOTALL)
    for table in matches:
        if table_text_hint.lower() in table.lower():
            return table
    if matches:
        return matches[0]
    raise ValueError(f"Could not locate table for {table_text_hint}.")


def extract_financial_rows(page, table_text_hint: str) -> Dict[str, Any]:
    table_html = extract_table(page, table_text_hint)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    result: Dict[str, Any] = {}
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 2:
            continue
        label = re.sub(r"<.*?>", "", cells[0])
        value = re.sub(r"<.*?>", "", cells[1])
        label = re.sub(r"\s+", " ", label).strip()
        value = re.sub(r"\s+", " ", value).strip()
        if label and value:
            result[label] = value
    return result


def extract_financial_value(raw_text: str) -> float | None:
    return normalize_financial_value(raw_text)


def scrape_filing(ticker: str, filing_url: str, *, demo: bool = False) -> Dict[str, Any]:
    logger.info("[1/10] Resolving company")
    info = discover_latest_filing(ticker)
    logger.info("[OK] %s", info["company_name"])

    logger.info("[2/10] Finding latest 10-Q")
    logger.info("[OK] %s found", info["filing_type"])

    logger.info("[3/10] Launching Chromium")
    page = open_filing(filing_url)
    logger.info("[OK] Browser started")

    logger.info("[4/10] Opening filing")
    wait_for_filing(page)
    logger.info("[OK] Filing loaded")

    statements: Dict[str, Dict[str, Any]] = {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    for step_name, hint, key in [
        ("[5/10] Scraping Income Statement", "CONSOLIDATED STATEMENTS OF OPERATIONS", "income_statement"),
        ("[6/10] Scraping Balance Sheet", "CONSOLIDATED BALANCE SHEETS", "balance_sheet"),
        ("[7/10] Scraping Cash Flow", "CONSOLIDATED STATEMENTS OF CASH FLOWS", "cash_flow"),
    ]:
        logger.info(step_name)
        raw_rows = extract_financial_rows(page, hint)
        if not raw_rows:
            raise ValueError(f"Could not locate the {key} in the filing.")
        for label, raw in raw_rows.items():
            normalized = extract_financial_value(raw)
            if normalized is not None:
                statements[key][label] = normalized
        logger.info("[OK] %s extracted", key.replace("_", " ").title())
        save_debug_screenshot(f"{key}.png" if key in {"income_statement", "balance_sheet", "cash_flow"} else "debug.png", page)

    html = page.content()
    save_debug_html("filing_content.html", html)
    close_browser()
    logger.info("[10/10] Closing browser")
    return {
        "company": info["company_name"],
        "ticker": ticker.upper(),
        "cik": info["cik"],
        "filing": info,
        "statements": {**statements},
    }


def _infer_period(period_of_report: str) -> tuple[str, int]:
    """Derive a calendar (period_type, fiscal_year) pair from a filing's report date."""
    report_date = date.fromisoformat(period_of_report)
    quarter = (report_date.month - 1) // 3 + 1
    return f"Q{quarter}", report_date.year


def fetch_company_financials(ticker: str) -> Dict[str, Any]:
    """Compatibility wrapper for the old ingestion API.

    Scrapes the company's latest SEC filing and returns it in the shape the
    ingestion task expects. Raises if the filing cannot be found or parsed —
    there is no synthetic fallback data.
    """
    filing = discover_latest_filing(ticker)
    result = scrape_filing(ticker, filing["filing_url"], demo=False)
    period_type, fiscal_year = _infer_period(filing["period_of_report"])
    return {
        "ticker": ticker.upper(),
        "name": filing["company_name"],
        "periods": [{
            "period_type": period_type,
            "fiscal_year": fiscal_year,
            "report_date": filing["period_of_report"],
            "items": {
                **result["statements"].get("income_statement", {}),
                **result["statements"].get("balance_sheet", {}),
                **result["statements"].get("cash_flow", {}),
            },
        }],
    }
