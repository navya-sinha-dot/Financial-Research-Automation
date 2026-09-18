"""Database seeding script for FRA sample companies and quarterly financial metrics."""
import os
import sys
import logging
from datetime import date

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.database import SessionLocal, engine, Base
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_COMPANIES = [
    {
        "ticker": "INFY",
        "name": "Infosys Limited",
        "sector": "Information Technology",
        "exchange": "NYSE",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024, "report_date": date(2023, 6, 30),
                "items": {"revenue": 4617.0, "net_income": 724.0, "operating_income": 961.0,
                          "total_equity": 9120.0, "current_assets": 7450.0, "current_liabilities": 2980.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024, "report_date": date(2023, 9, 30),
                "items": {"revenue": 4718.0, "net_income": 750.0, "operating_income": 998.0,
                          "total_equity": 9280.0, "current_assets": 7620.0, "current_liabilities": 3050.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024, "report_date": date(2023, 12, 31),
                "items": {"revenue": 4663.0, "net_income": 732.0, "operating_income": 956.0,
                          "total_equity": 9350.0, "current_assets": 7580.0, "current_liabilities": 3020.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024, "report_date": date(2024, 3, 31),
                "items": {"revenue": 4564.0, "net_income": 958.0, "operating_income": 917.0,
                          "total_equity": 9850.0, "current_assets": 7910.0, "current_liabilities": 3100.0},
            },
        ],
    },
    {
        "ticker": "TCS",
        "name": "Tata Consultancy Services",
        "sector": "Information Technology",
        "exchange": "NSE",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024, "report_date": date(2023, 6, 30),
                "items": {"revenue": 7220.0, "net_income": 1350.0, "operating_income": 1675.0,
                          "total_equity": 11200.0, "current_assets": 10500.0, "current_liabilities": 3900.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024, "report_date": date(2023, 9, 30),
                "items": {"revenue": 7210.0, "net_income": 1362.0, "operating_income": 1750.0,
                          "total_equity": 11450.0, "current_assets": 10750.0, "current_liabilities": 3980.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024, "report_date": date(2023, 12, 31),
                "items": {"revenue": 7280.0, "net_income": 1335.0, "operating_income": 1820.0,
                          "total_equity": 11600.0, "current_assets": 10900.0, "current_liabilities": 4020.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024, "report_date": date(2024, 3, 31),
                "items": {"revenue": 7360.0, "net_income": 1490.0, "operating_income": 1910.0,
                          "total_equity": 11980.0, "current_assets": 11200.0, "current_liabilities": 4100.0},
            },
        ],
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "sector": "Information Technology",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024, "report_date": date(2023, 9, 30),
                "items": {"revenue": 56517.0, "net_income": 22291.0, "operating_income": 26895.0,
                          "total_equity": 220557.0, "current_assets": 143682.0, "current_liabilities": 104107.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024, "report_date": date(2023, 12, 31),
                "items": {"revenue": 62020.0, "net_income": 21870.0, "operating_income": 27032.0,
                          "total_equity": 238274.0, "current_assets": 151240.0, "current_liabilities": 107450.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024, "report_date": date(2024, 3, 31),
                "items": {"revenue": 61858.0, "net_income": 21939.0, "operating_income": 27581.0,
                          "total_equity": 253152.0, "current_assets": 156320.0, "current_liabilities": 109800.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024, "report_date": date(2024, 6, 30),
                "items": {"revenue": 64727.0, "net_income": 22036.0, "operating_income": 27925.0,
                          "total_equity": 268480.0, "current_assets": 161450.0, "current_liabilities": 112340.0},
            },
        ],
    },
    # --- GOOGL: Added with real Alphabet quarterly data (FY2024) ---
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "sector": "Information Technology",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024, "report_date": date(2024, 3, 31),
                "items": {"revenue": 80539.0, "net_income": 23662.0, "operating_income": 25472.0,
                          "total_equity": 306695.0, "current_assets": 152199.0, "current_liabilities": 74235.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024, "report_date": date(2024, 6, 30),
                "items": {"revenue": 84742.0, "net_income": 23619.0, "operating_income": 27425.0,
                          "total_equity": 314119.0, "current_assets": 160924.0, "current_liabilities": 77591.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024, "report_date": date(2024, 9, 30),
                "items": {"revenue": 88268.0, "net_income": 26301.0, "operating_income": 28521.0,
                          "total_equity": 325083.0, "current_assets": 168530.0, "current_liabilities": 79865.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024, "report_date": date(2024, 12, 31),
                "items": {"revenue": 96469.0, "net_income": 26542.0, "operating_income": 30972.0,
                          "total_equity": 338860.0, "current_assets": 179405.0, "current_liabilities": 83620.0},
            },
        ],
    },
    # --- AAPL: Added with real Apple quarterly data (FY2024) ---
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Information Technology",
        "exchange": "NASDAQ",
        "periods": [
            {
                "period_type": "Q1", "fiscal_year": 2024, "report_date": date(2023, 12, 31),
                "items": {"revenue": 119575.0, "net_income": 33916.0, "operating_income": 40374.0,
                          "total_equity": 74100.0, "current_assets": 143566.0, "current_liabilities": 145308.0},
            },
            {
                "period_type": "Q2", "fiscal_year": 2024, "report_date": date(2024, 3, 31),
                "items": {"revenue": 90753.0, "net_income": 23636.0, "operating_income": 27901.0,
                          "total_equity": 68960.0, "current_assets": 128292.0, "current_liabilities": 124521.0},
            },
            {
                "period_type": "Q3", "fiscal_year": 2024, "report_date": date(2024, 6, 30),
                "items": {"revenue": 85777.0, "net_income": 21448.0, "operating_income": 25880.0,
                          "total_equity": 66708.0, "current_assets": 120740.0, "current_liabilities": 116070.0},
            },
            {
                "period_type": "Q4", "fiscal_year": 2024, "report_date": date(2024, 9, 30),
                "items": {"revenue": 94930.0, "net_income": 14736.0, "operating_income": 17599.0,
                          "total_equity": 56950.0, "current_assets": 152987.0, "current_liabilities": 176392.0},
            },
        ],
    },
]


def seed_database() -> None:
    """Seeds the database with companies and quarterly financial metrics."""
    logger.info("Starting database seeding...")
    session = SessionLocal()
    try:
        for comp_data in SAMPLE_COMPANIES:
            company = session.query(Company).filter_by(ticker=comp_data["ticker"]).first()
            if not company:
                company = Company(
                    ticker=comp_data["ticker"],
                    name=comp_data["name"],
                    sector=comp_data["sector"],
                    exchange=comp_data["exchange"],
                )
                session.add(company)
                session.flush()
                logger.info(f"Created company: {company.ticker} - {company.name}")
            else:
                # Update name/exchange in case stale data was stored from a bad ingestion run
                company.name = comp_data["name"]
                company.exchange = comp_data["exchange"]
                logger.info(f"Company already exists, updating metadata: {company.ticker}")

            for p_data in comp_data["periods"]:
                period = (
                    session.query(FinancialPeriod)
                    .filter_by(
                        company_id=company.id,
                        period_type=p_data["period_type"],
                        fiscal_year=p_data["fiscal_year"],
                    )
                    .first()
                )
                if not period:
                    period = FinancialPeriod(
                        company_id=company.id,
                        period_type=p_data["period_type"],
                        fiscal_year=p_data["fiscal_year"],
                        report_date=p_data["report_date"],
                    )
                    session.add(period)
                    session.flush()

                for item_name, val in p_data["items"].items():
                    line_item = (
                        session.query(FinancialLineItem)
                        .filter_by(period_id=period.id, item_name=item_name)
                        .first()
                    )
                    if not line_item:
                        line_item = FinancialLineItem(
                            period_id=period.id,
                            item_name=item_name,
                            value=val,
                            unit="USD (Millions)",
                            source="seed_fixture",
                        )
                        session.add(line_item)
                    else:
                        # Overwrite stale/zero values from broken ingestion runs
                        line_item.value = val
                        line_item.source = "seed_fixture"

        session.commit()
        logger.info("Database seeding completed successfully!")
    except Exception as e:
        session.rollback()
        logger.error(f"Error during seeding: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
