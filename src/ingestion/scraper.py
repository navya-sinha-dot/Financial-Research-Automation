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


def fetch_company_financials(ticker: str) -> Dict[str, Any]:
    """Compatibility wrapper for the old ingestion API."""
    filing = discover_latest_filing(ticker)
    result = scrape_filing(ticker, filing["filing_url"], demo=False)
    return {
        "ticker": ticker.upper(),
        "name": filing["company_name"],
        "periods": [{
            "period_type": "Q1",
            "fiscal_year": 2026,
            "report_date": filing["filing_date"],
            "items": {
                **result["statements"].get("income_statement", {}),
                **result["statements"].get("balance_sheet", {}),
                **result["statements"].get("cash_flow", {}),
            },
        }],
    }


def _get_fallback_data(ticker: str) -> Dict[str, Any]:
    """Return deterministic quarterly data for offline ingestion failures."""
    return {
        "ticker": ticker,
        "name": f"{ticker} Corporation",
        "sector": "Information Technology",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024,
                "report_date": date(2023, 6, 30),
                "items": {
                    "revenue": 5100.0, "net_income": 980.0, "operating_income": 1200.0,
                    "total_equity": 8800.0, "current_assets": 7100.0, "current_liabilities": 2800.0,
                },
            },
            {
                "period_type": "Q2", "fiscal_year": 2024,
                "report_date": date(2023, 9, 30),
                "items": {
                    "revenue": 5250.0, "net_income": 1020.0, "operating_income": 1260.0,
                    "total_equity": 9100.0, "current_assets": 7350.0, "current_liabilities": 2900.0,
                },
            },
            {
                "period_type": "Q3", "fiscal_year": 2024,
                "report_date": date(2023, 12, 31),
                "items": {
                    "revenue": 5380.0, "net_income": 1060.0, "operating_income": 1310.0,
                    "total_equity": 9400.0, "current_assets": 7600.0, "current_liabilities": 2950.0,
                },
            },
            {
                "period_type": "Q4", "fiscal_year": 2024,
                "report_date": date(2024, 3, 31),
                "items": {
                    "revenue": 5520.0, "net_income": 1110.0, "operating_income": 1380.0,
                    "total_equity": 9800.0, "current_assets": 7950.0, "current_liabilities": 3050.0,
                },
            },
        ],
    }



# ---------------------------------------------------------------------------
# Legacy HTML helpers (kept for parser.py fallback path only)
# ---------------------------------------------------------------------------

def generate_fallback_financial_html(ticker: str) -> str:
    """Generates a minimal financial HTML table — used only by parser.py fallback."""
    d = _get_fallback_data(ticker)
    rows = {
        "revenue": "Total Revenue",
        "net_income": "Net Income",
        "operating_income": "Operating Income",
        "total_equity": "Total Stockholders' Equity",
        "current_assets": "Current Assets",
        "current_liabilities": "Current Liabilities",
    }
    header_ths = "".join(
        f'<th data-date="{p["report_date"]}" data-quarter="{p["period_type"]}" '
        f'data-year="{p["fiscal_year"]}">{p["period_type"]} {p["fiscal_year"]}</th>'
        for p in d["periods"]
    )
    body_rows = ""
    for key, label in rows.items():
        tds = "".join(
            f'<td>{p["items"].get(key, 0.0)}</td>' for p in d["periods"]
        )
        body_rows += f'<tr data-metric="{key}"><td>{label}</td>{tds}</tr>\n'

    return f"""<!DOCTYPE html>
<html>
<head><title>Financial Statements for {ticker}</title></head>
<body>
    <div id="company-header">
        <h1 class="ticker">{ticker}</h1>
        <span class="sector">Information Technology</span>
        <span class="exchange">NASDAQ</span>
    </div>
    <table class="financial-table quarterly" data-ticker="{ticker}">
        <thead><tr><th>Breakdown</th>{header_ths}</tr></thead>
        <tbody>{body_rows}</tbody>
    </table>
</body>
</html>"""
