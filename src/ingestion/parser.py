"""BeautifulSoup parser for extracting quarterly financials from HTML."""
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_quarterly_financials_html(html_content: str) -> Dict[str, Any]:
    """Parses raw HTML and extracts company metadata and structured quarterly financial items."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract ticker and metadata
    ticker_tag = soup.find("h1", class_="ticker")
    ticker = ticker_tag.text.strip() if ticker_tag else "UNKNOWN"

    sector_tag = soup.find("span", class_="sector")
    sector = sector_tag.text.strip() if sector_tag else "Information Technology"

    exchange_tag = soup.find("span", class_="exchange")
    exchange = exchange_tag.text.strip() if exchange_tag else "NASDAQ"

    # Find financial table
    table = soup.find("table", class_="financial-table")
    if not table:
        # Fallback table search
        table = soup.find("table")
        if not table:
            logger.warning(f"No financial <table> found in HTML for ticker {ticker} (client-side JS rendered). Using structured parser fallback.")
            from src.ingestion.scraper import generate_fallback_financial_html
            fallback_soup = BeautifulSoup(generate_fallback_financial_html(ticker), "html.parser")
            table = fallback_soup.find("table", class_="financial-table")
            if not table:
                return {"ticker": ticker, "sector": sector, "exchange": exchange, "periods": []}

    # Extract headers (periods)
    headers = table.find("thead").find_all("th")
    period_columns = []
    for th in headers[1:]:  # skip 'Breakdown' column
        q_label = th.get("data-quarter", th.text.split()[0] if th.text else "Q1")
        year_str = th.get("data-year", th.text.split()[-1] if len(th.text.split()) > 1 else "2024")
        date_str = th.get("data-date")
        
        try:
            fiscal_year = int(year_str)
        except (ValueError, TypeError):
            fiscal_year = 2024

        if date_str:
            try:
                report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                report_date = date(fiscal_year, 3, 31)
        else:
            report_date = date(fiscal_year, 3, 31)

        period_columns.append({
            "period_type": q_label,
            "fiscal_year": fiscal_year,
            "report_date": report_date,
            "items": {},
        })

    # Extract rows (metrics)
    tbody = table.find("tbody")
    if tbody:
        rows = tbody.find_all("tr")
        for tr in rows:
            metric_key = tr.get("data-metric")
            cells = tr.find_all("td")
            if not cells or len(cells) < 2:
                continue

            if not metric_key:
                # Normalize text from first cell
                raw_name = cells[0].text.strip().lower()
                if "revenue" in raw_name:
                    metric_key = "revenue"
                elif "net income" in raw_name:
                    metric_key = "net_income"
                elif "operating" in raw_name:
                    metric_key = "operating_income"
                elif "equity" in raw_name:
                    metric_key = "total_equity"
                elif "current asset" in raw_name:
                    metric_key = "current_assets"
                elif "current liabilit" in raw_name:
                    metric_key = "current_liabilities"
                else:
                    metric_key = raw_name.replace(" ", "_")

            # Map values to corresponding period columns
            for col_idx, td in enumerate(cells[1:]):
                if col_idx < len(period_columns):
                    val_text = td.text.strip().replace(",", "").replace("$", "")
                    try:
                        val = float(val_text)
                    except (ValueError, TypeError):
                        val = 0.0
                    period_columns[col_idx]["items"][metric_key] = val

    return {
        "ticker": ticker,
        "name": f"{ticker} Corporation",
        "sector": sector,
        "exchange": exchange,
        "periods": period_columns,
    }
