import os
import pytest
from datetime import date
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///./data/test_fra.db"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

from src.core.database import Base, engine, SessionLocal, get_db
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem, ComputedRatio
from src.models.report import ReportJob, ReportStatus
from src.api.main import app


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
            try:
                session.execute(table.delete())
            except Exception:
                pass
        session.commit()
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient configured with the overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
