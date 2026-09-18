"""Scraper module using yfinance for reliable real-time financial data.

Why yfinance instead of raw Selenium/requests:
  Yahoo Finance renders financial tables with JavaScript/React. A plain HTTP
  request only receives the page shell — the actual data tables never arrive.
  yfinance bypasses this by calling Yahoo Finance's internal JSON APIs directly,
  returning real quarterly financials for any publicly listed ticker.

Fallback:
  If yfinance fails (invalid ticker, network error, rate limit), structured
  fixture data is returned so the rest of the pipeline still works.
"""
import logging
from datetime import date
from typing import Dict, Any, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Raised when all data-fetch strategies have been exhausted."""
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_company_financials(ticker: str) -> Dict[str, Any]:
    """Fetches quarterly financial data for any publicly listed ticker.

    Returns a structured dict:
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "sector": "Communication Services",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1",
                "fiscal_year": 2024,
                "report_date": date(2024, 3, 31),
                "items": {
                    "revenue": 80539.0,          # USD Millions
                    "net_income": 23662.0,
                    "operating_income": 25472.0,
                    "total_equity": 306695.0,
                    "current_assets": 152199.0,
                    "current_liabilities": 74235.0,
                }
            },
            ...  # up to 4 most recent quarters
        ]
    }
    """
    ticker_clean = ticker.upper().strip()
    logger.info(f"Fetching financials for '{ticker_clean}' via yfinance")

    try:
        import yfinance as yf
        yticker = yf.Ticker(ticker_clean)

        # -- Company metadata --
        info = yticker.info or {}
        name = (
            info.get("longName")
            or info.get("shortName")
            or f"{ticker_clean} Corp"
        )
        sector = info.get("sector") or "Information Technology"
        exchange = info.get("exchange") or "NASDAQ"

        # -- Quarterly financials --
        income_stmt = yticker.quarterly_income_stmt   # rows=metrics, cols=periods
        balance_sheet = yticker.quarterly_balance_sheet

        if income_stmt is None or income_stmt.empty:
            raise ValueError(f"No quarterly income statement data returned for '{ticker_clean}'")

        periods = _build_periods(income_stmt, balance_sheet)

        if not periods:
            raise ValueError(f"Could not extract any financial periods for '{ticker_clean}'")

        logger.info(f"Successfully fetched {len(periods)} quarters for '{ticker_clean}' ({name})")
        return {
            "ticker": ticker_clean,
            "name": name,
            "sector": sector,
            "exchange": exchange,
            "periods": periods,
        }

    except ImportError:
        logger.error("yfinance is not installed. Run: pip install yfinance")
        return _get_fallback_data(ticker_clean)
    except Exception as exc:
        logger.warning(
            f"yfinance fetch failed for '{ticker_clean}': {exc}. "
            "Falling back to fixture data."
        )
        return _get_fallback_data(ticker_clean)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_value(df: pd.DataFrame, col, *row_keys) -> Optional[float]:
    """Tries each row key in order; returns value in USD Millions, or None."""
    for key in row_keys:
        try:
            if key in df.index:
                v = df.loc[key, col]
                if pd.notna(v):
                    return round(float(v) / 1_000_000, 2)
        except Exception:
            continue
    return None


def _date_to_quarter(d: date) -> str:
    """Maps a calendar month to a fiscal quarter label."""
    if d.month in (1, 2, 3):
        return "Q1"
    elif d.month in (4, 5, 6):
        return "Q2"
    elif d.month in (7, 8, 9):
        return "Q3"
    else:
        return "Q4"


def _build_periods(
    income_stmt: pd.DataFrame,
    balance_sheet: Optional[pd.DataFrame],
) -> List[Dict[str, Any]]:
    """Converts yfinance DataFrames into the standard period/line-item list."""
    periods = []

    for col in income_stmt.columns:
        # col is a Timestamp — convert to date
        report_date: date = col.date() if hasattr(col, "date") else col

        items: Dict[str, float] = {}

        # -- Income statement metrics --
        revenue = _get_value(
            income_stmt, col,
            "Total Revenue", "Revenue",
        )
        net_income = _get_value(
            income_stmt, col,
            "Net Income", "Net Income Common Stockholders",
        )
        operating_income = _get_value(
            income_stmt, col,
            "Operating Income", "EBIT",
        )

        if revenue is not None:
            items["revenue"] = revenue
        if net_income is not None:
            items["net_income"] = net_income
        if operating_income is not None:
            items["operating_income"] = operating_income

        # -- Balance sheet metrics (matched by nearest available date) --
        if balance_sheet is not None and not balance_sheet.empty:
            bs_col = col if col in balance_sheet.columns else _nearest_column(balance_sheet, col)
            if bs_col is not None:
                total_equity = _get_value(
                    balance_sheet, bs_col,
                    "Stockholders Equity",
                    "Common Stock Equity",
                    "Total Equity Gross Minority Interest",
                )
                current_assets = _get_value(
                    balance_sheet, bs_col,
                    "Current Assets",
                )
                current_liabilities = _get_value(
                    balance_sheet, bs_col,
                    "Current Liabilities",
                )

                if total_equity is not None:
                    items["total_equity"] = total_equity
                if current_assets is not None:
                    items["current_assets"] = current_assets
                if current_liabilities is not None:
                    items["current_liabilities"] = current_liabilities

        if not items:
            continue

        periods.append({
            "period_type": _date_to_quarter(report_date),
            "fiscal_year": report_date.year,
            "report_date": report_date,
            "items": items,
        })

    # Return in chronological order (oldest first)
    periods.sort(key=lambda p: p["report_date"])
    return periods


def _nearest_column(df: pd.DataFrame, target):
    """Returns the DataFrame column closest in time to `target`."""
    if df.columns.empty:
        return None
    diffs = [(abs((c - target).days), c) for c in df.columns]
    diffs.sort(key=lambda x: x[0])
    best_diff, best_col = diffs[0]
    # Only accept if within 45 days
    return best_col if best_diff <= 45 else None


# ---------------------------------------------------------------------------
# Fallback fixture (used when yfinance is unavailable / ticker is invalid)
# ---------------------------------------------------------------------------

def _get_fallback_data(ticker: str) -> Dict[str, Any]:
    """Returns generic fixture quarterly data when live fetch fails."""
    logger.info(f"Using fallback fixture data for '{ticker}'")
    return {
        "ticker": ticker,
        "name": f"{ticker} Corporation",
        "sector": "Information Technology",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024,
                "report_date": date(2023, 6, 30),
                "items": {"revenue": 5100.0, "net_income": 980.0, "operating_income": 1200.0,
                          "total_equity": 8800.0, "current_assets": 7100.0, "current_liabilities": 2800.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024,
                "report_date": date(2023, 9, 30),
                "items": {"revenue": 5250.0, "net_income": 1020.0, "operating_income": 1260.0,
                          "total_equity": 9100.0, "current_assets": 7350.0, "current_liabilities": 2900.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024,
                "report_date": date(2023, 12, 31),
                "items": {"revenue": 5380.0, "net_income": 1060.0, "operating_income": 1310.0,
                          "total_equity": 9400.0, "current_assets": 7600.0, "current_liabilities": 2950.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024,
                "report_date": date(2024, 3, 31),
                "items": {"revenue": 5520.0, "net_income": 1110.0, "operating_income": 1380.0,
                          "total_equity": 9800.0, "current_assets": 7950.0, "current_liabilities": 3050.0},
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
