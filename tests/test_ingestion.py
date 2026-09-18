"""Tests for the ingestion layer: yfinance fetch, parsing, and failure isolation."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from src.ingestion.scraper import fetch_company_financials, _get_fallback_data
from src.ingestion.tasks import ingest_company_financials, ingest_batch_companies
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem


def _mock_company_data(ticker: str):
    """Returns a realistic structured data dict for testing without hitting yfinance."""
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


def test_fallback_data_structure():
    """Fallback data must always have 4 periods with required metric keys."""
    data = _get_fallback_data("TEST")
    assert data["ticker"] == "TEST"
    assert len(data["periods"]) == 4
    for period in data["periods"]:
        assert "revenue" in period["items"]
        assert "net_income" in period["items"]
        assert period["period_type"] in ("Q1", "Q2", "Q3", "Q4")


def test_ingest_company_financials_task(db_session):
    """Full ingestion pipeline stores company + periods + line items correctly."""
    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        mock_fetch.side_effect = _mock_company_data

        res = ingest_company_financials("AAPL")
        assert res["status"] == "SUCCESS"
        assert res["periods_ingested"] >= 4

        # Verify DB rows
        company = db_session.query(Company).filter_by(ticker="AAPL").first()
        assert company is not None
        assert len(company.periods) >= 4

        p1 = company.periods[0]
        line_item_names = {li.item_name for li in p1.line_items}
        assert "revenue" in line_item_names
        assert "net_income" in line_item_names


def test_batch_ingestion_failure_isolation(db_session):
    """A failure on one ticker must not stop the rest of the batch."""
    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        def side_effect(ticker):
            if ticker == "FAIL":
                raise RuntimeError("Simulated network timeout")
            return _mock_company_data(ticker)

        mock_fetch.side_effect = side_effect

        batch_res = ingest_batch_companies(["GOOD1", "FAIL", "GOOD2"])
        assert batch_res["total"] == 3
        assert batch_res["results"]["GOOD1"]["status"] == "SUCCESS"
        assert batch_res["results"]["FAIL"]["status"] == "FAILED"
        assert batch_res["results"]["GOOD2"]["status"] == "SUCCESS"
