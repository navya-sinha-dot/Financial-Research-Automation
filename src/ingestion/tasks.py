"""Celery ingestion tasks with failure isolation and structured logging."""
import logging
from typing import Dict, Any, List

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem
from src.ingestion.scraper import fetch_company_financials

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="src.ingestion.tasks.ingest_company_financials")
def ingest_company_financials(self, ticker: str) -> Dict[str, Any]:
    """Ingests quarterly financials for any publicly listed company into the database.

    1. Fetches live data via yfinance (real data for any valid ticker).
    2. Upserts Company, FinancialPeriod, and FinancialLineItem rows.
    3. Returns a summary status dict.
    """
    ticker_clean = ticker.upper().strip()
    logger.info(f"[Task {self.request.id}] Starting ingestion for ticker '{ticker_clean}'")

    try:
        # Step 1: Fetch structured financial data (yfinance → fallback fixture)
        company_data = fetch_company_financials(ticker_clean)
        periods_data = company_data.get("periods", [])

        if not periods_data:
            logger.warning(f"No financial periods returned for {ticker_clean}")
            return {"ticker": ticker_clean, "status": "NO_DATA", "periods_ingested": 0}

        # Step 2: Upsert into database
        session = SessionLocal()
        try:
            # -- Company row --
            company = session.query(Company).filter_by(ticker=ticker_clean).first()
            if not company:
                company = Company(
                    ticker=ticker_clean,
                    name=company_data.get("name", f"{ticker_clean} Corp"),
                    sector=company_data.get("sector", "Information Technology"),
                    exchange=company_data.get("exchange", "NASDAQ"),
                )
                session.add(company)
                session.flush()
            else:
                # Update metadata in case it changed (e.g. was previously a bad ingestion)
                company.name = company_data.get("name", company.name)
                company.sector = company_data.get("sector", company.sector)
                company.exchange = company_data.get("exchange", company.exchange)

            # -- Period + line item rows --
            periods_count = 0
            for p_dict in periods_data:
                period = (
                    session.query(FinancialPeriod)
                    .filter_by(
                        company_id=company.id,
                        period_type=p_dict["period_type"],
                        fiscal_year=p_dict["fiscal_year"],
                    )
                    .first()
                )
                if not period:
                    period = FinancialPeriod(
                        company_id=company.id,
                        period_type=p_dict["period_type"],
                        fiscal_year=p_dict["fiscal_year"],
                        report_date=p_dict["report_date"],
                    )
                    session.add(period)
                    session.flush()

                for item_name, val in p_dict.get("items", {}).items():
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
                            source="yfinance",
                        )
                        session.add(line_item)
                    else:
                        # Always overwrite with the freshest value
                        line_item.value = val
                        line_item.source = "yfinance"

                periods_count += 1

            session.commit()
            logger.info(
                f"[Task {self.request.id}] Ingested {periods_count} periods for "
                f"'{ticker_clean}' ({company.name})"
            )
            return {
                "ticker": ticker_clean,
                "company_id": company.id,
                "company_name": company.name,
                "status": "SUCCESS",
                "periods_ingested": periods_count,
            }

        except Exception as db_err:
            session.rollback()
            logger.error(
                f"Database error during ingestion for {ticker_clean}: {db_err}",
                exc_info=True,
            )
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Ingestion failed for '{ticker_clean}': {e}", exc_info=True)
        return {"ticker": ticker_clean, "status": "FAILED", "error": str(e)}


@celery_app.task(name="src.ingestion.tasks.ingest_batch_companies")
def ingest_batch_companies(tickers: List[str]) -> Dict[str, Any]:
    """Batch ingestion with failure isolation.

    A failure on any single ticker does NOT stop the rest of the batch.
    """
    logger.info(f"Starting batch ingestion for {len(tickers)} tickers: {tickers}")
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = ingest_company_financials(ticker)
        except Exception as e:
            logger.error(f"Batch item failed for '{ticker}': {e}", exc_info=True)
            results[ticker] = {"ticker": ticker, "status": "FAILED", "error": str(e)}

    return {"total": len(tickers), "results": results}
