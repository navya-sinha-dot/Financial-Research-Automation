import contextlib
import os
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///./data/test_fra.db"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

from src.api.main import app
from src.core.database import Base, SessionLocal, engine
from src.models.company import Company
from src.models.financial import FinancialLineItem, FinancialPeriod


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provides a clean database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            with contextlib.suppress(Exception):
                session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient hitting the real app.

    Routes use the async DB engine (get_async_db), which -- like the sync
    engine `db_session` uses for test setup -- points at the same
    DATABASE_URL test file, so writes made through `db_session`/`seeded_db`
    are visible to the API without needing a dependency override.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_db(db_session: Session) -> Session:
    """Populates db with sample company and financial metrics."""
    comp = Company(ticker="INFY", name="Infosys Limited", sector="Information Technology", exchange="NYSE")
    db_session.add(comp)
    db_session.flush()

    # Add 2 periods
    p1 = FinancialPeriod(company_id=comp.id, period_type="Q1", fiscal_year=2024, report_date=date(2023, 6, 30))
    p2 = FinancialPeriod(company_id=comp.id, period_type="Q2", fiscal_year=2024, report_date=date(2023, 9, 30))
    db_session.add_all([p1, p2])
    db_session.flush()

    # Add items
    items_p1 = [
        FinancialLineItem(period_id=p1.id, item_name="revenue", value=4617.0),
        FinancialLineItem(period_id=p1.id, item_name="net_income", value=724.0),
        FinancialLineItem(period_id=p1.id, item_name="total_equity", value=9120.0),
        FinancialLineItem(period_id=p1.id, item_name="current_assets", value=7450.0),
        FinancialLineItem(period_id=p1.id, item_name="current_liabilities", value=2980.0),
    ]
    items_p2 = [
        FinancialLineItem(period_id=p2.id, item_name="revenue", value=4718.0),
        FinancialLineItem(period_id=p2.id, item_name="net_income", value=750.0),
        FinancialLineItem(period_id=p2.id, item_name="total_equity", value=9280.0),
        FinancialLineItem(period_id=p2.id, item_name="current_assets", value=7620.0),
        FinancialLineItem(period_id=p2.id, item_name="current_liabilities", value=3050.0),
    ]
    db_session.add_all(items_p1 + items_p2)
    db_session.commit()
    return db_session
