"""Unit tests for ORM model __repr__ methods and the get_db session dependency."""

import contextlib
from datetime import date

from src.core.database import get_db
from src.models.company import Company
from src.models.financial import ComputedRatio, FinancialLineItem, FinancialPeriod
from src.models.report import ReportJob, ReportStatus


def test_company_repr(db_session):
    company = Company(ticker="MSFT", name="Microsoft Corporation")
    db_session.add(company)
    db_session.commit()

    text = repr(company)
    assert "Company" in text
    assert "MSFT" in text
    assert "Microsoft Corporation" in text


def test_financial_period_and_line_item_repr(db_session):
    company = Company(ticker="MSFT", name="Microsoft Corporation")
    db_session.add(company)
    db_session.flush()

    period = FinancialPeriod(company_id=company.id, period_type="Q1", fiscal_year=2025, report_date=date(2024, 9, 30))
    db_session.add(period)
    db_session.flush()

    line_item = FinancialLineItem(period_id=period.id, item_name="revenue", value=1234.5)
    ratio = ComputedRatio(period_id=period.id, ratio_name="net_margin", value=0.21)
    db_session.add_all([line_item, ratio])
    db_session.commit()

    assert "Q1 2025" in repr(period)
    assert "revenue" in repr(line_item)
    assert "1234.5" in repr(line_item)
    assert "net_margin" in repr(ratio)


def test_report_job_repr(db_session):
    company = Company(ticker="MSFT", name="Microsoft Corporation")
    db_session.add(company)
    db_session.flush()

    job = ReportJob(company_id=company.id, status=ReportStatus.PENDING)
    db_session.add(job)
    db_session.commit()

    text = repr(job)
    assert "ReportJob" in text
    assert "PENDING" in text


def test_get_db_yields_a_session_and_closes_it():
    generator = get_db()
    session = next(generator)
    assert session is not None

    # Exhausting the generator runs the `finally: db.close()` cleanup path.
    with contextlib.suppress(StopIteration):
        next(generator)
