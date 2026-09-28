"""Regression test for a real bug found on a live scrape: fetch_company_financials
stored the filing's report date as a raw ISO string instead of a Python
`date` object. Postgres' driver silently coerces a string into a Date
column; SQLite's does not and raises `TypeError: SQLite Date type only
accepts Python date objects as input.` at insert time.

Every existing ingestion test patches `fetch_company_financials` itself
(with hand-built fixture data that already used real `date` objects), so
none of them exercised this real code path -- that's exactly how this bug
shipped unnoticed.
"""

from datetime import date
from unittest.mock import MagicMock, patch

from src.ingestion.scraper import _infer_period, fetch_company_financials
from src.models.company import Company
from src.models.financial import FinancialPeriod


def test_infer_period_returns_a_real_date_object_not_a_string():
    period_type, fiscal_year, report_date = _infer_period("2025-09-27")

    assert period_type == "Q3"
    assert fiscal_year == 2025
    assert report_date == date(2025, 9, 27)
    assert isinstance(report_date, date)


def test_infer_period_quarter_boundaries():
    assert _infer_period("2024-01-15")[0] == "Q1"
    assert _infer_period("2024-04-15")[0] == "Q2"
    assert _infer_period("2024-07-15")[0] == "Q3"
    assert _infer_period("2024-10-15")[0] == "Q4"


def test_fetch_company_financials_report_date_is_actually_insertable(db_session):
    """End-to-end version of the same bug: build a period the way the real
    scraper does, and actually insert it into the database. This exact
    insert raised `TypeError: SQLite Date type only accepts Python date
    objects as input.` before the fix.
    """
    fake_filing = {
        "company_name": "Apple Inc.",
        "filing_url": "https://example.test/filing.htm",
        "period_of_report": "2025-09-27",
        "accession_number": "0000320193-25-000079",
    }
    fake_scrape_result = {
        "ticker": "AAPL",
        "statements": {
            "income_statement": {"Revenue": 100.0},
            "balance_sheet": {},
            "cash_flow": {},
        },
    }

    with (
        patch("src.ingestion.scraper.discover_recent_filings", return_value=[fake_filing]),
        patch("src.ingestion.scraper.create_page", return_value=MagicMock()),
        patch("src.ingestion.scraper.close_browser"),
        patch("src.ingestion.scraper.scrape_filing", return_value=fake_scrape_result),
    ):
        result = fetch_company_financials("AAPL")

    period = result["periods"][0]
    assert isinstance(period["report_date"], date)

    company = Company(ticker="FETCHTEST", name="Apple Inc.")
    db_session.add(company)
    db_session.flush()
    db_session.add(
        FinancialPeriod(
            company_id=company.id,
            period_type=period["period_type"],
            fiscal_year=period["fiscal_year"],
            report_date=period["report_date"],
        )
    )
    db_session.commit()  # would raise TypeError before the fix
