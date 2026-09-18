"""Tests for the ingestion layer: scraping, parsing, and failure isolation."""
import pytest
from unittest.mock import patch

from src.ingestion.scraper import generate_fallback_financial_html
from src.ingestion.parser import parse_quarterly_financials_html
from src.ingestion.tasks import ingest_company_financials, ingest_batch_companies
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem


def test_parse_quarterly_financials_html():
    html = generate_fallback_financial_html("TEST")
    parsed = parse_quarterly_financials_html(html)

    assert parsed["ticker"] == "TEST"
    assert len(parsed["periods"]) == 4

    q1 = parsed["periods"][0]
    assert q1["period_type"] == "Q1"
    assert q1["fiscal_year"] == 2024
    assert q1["items"]["revenue"] == 5100.0
    assert q1["items"]["net_income"] == 980.0
    assert q1["items"]["current_assets"] == 7100.0


def test_ingest_company_financials_task(db_session):
    # Run ingestion task
    res = ingest_company_financials("AAPL")
    assert res["status"] == "SUCCESS"
    assert res["periods_ingested"] >= 4

    # Verify rows in DB
    company = db_session.query(Company).filter_by(ticker="AAPL").first()
    assert company is not None
    assert len(company.periods) >= 4

    # Check line items
    p1 = company.periods[0]
    line_item_names = {li.item_name for li in p1.line_items}
    assert "revenue" in line_item_names
    assert "net_income" in line_item_names


def test_batch_ingestion_failure_isolation(db_session):
    """Verify that if one ticker fails, batch ingestion continues and returns results for all."""
    with patch("src.ingestion.tasks.fetch_company_financials_html") as mock_fetch:
        def side_effect(ticker):
            if ticker == "FAIL":
                raise RuntimeError("Simulated network timeout")
            return generate_fallback_financial_html(ticker)

        mock_fetch.side_effect = side_effect

        batch_res = ingest_batch_companies(["GOOD1", "FAIL", "GOOD2"])
        assert batch_res["total"] == 3
        assert batch_res["results"]["GOOD1"]["status"] == "SUCCESS"
        assert batch_res["results"]["FAIL"]["status"] == "FAILED"
        assert batch_res["results"]["GOOD2"]["status"] == "SUCCESS"
