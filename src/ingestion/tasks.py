"""Celery ingestion tasks with failure isolation and structured logging."""

import logging
import time
from typing import Any

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.core.metrics import INGESTION_DURATION_SECONDS, INGESTION_TOTAL
from src.ingestion.scraper import fetch_company_financials
from src.models.company import Company
from src.models.financial import FinancialLineItem, FinancialPeriod

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="src.ingestion.tasks.ingest_company_financials")
def ingest_company_financials(self, ticker: str) -> dict[str, Any]:
    """Ingests quarterly financials for any publicly listed company into the database.

    1. Fetches live data from the SEC filing in a visible Chromium browser.
    2. Upserts Company, FinancialPeriod, and FinancialLineItem rows.
    3. Returns a summary status dict.
    """
    ticker_clean = ticker.upper().strip()
    logger.info(f"[Task {self.request.id}] Starting ingestion for ticker '{ticker_clean}'")
    _started_at = time.monotonic()

    try:
        # Step 1: Fetch structured financial data from SEC EDGAR.
        company_data = fetch_company_financials(ticker_clean)
        periods_data = company_data.get("periods", [])

        if not periods_data:
            logger.warning(f"No financial periods returned for {ticker_clean}")
            INGESTION_TOTAL.labels(status="NO_DATA").inc()
            INGESTION_DURATION_SECONDS.observe(time.monotonic() - _started_at)
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
                        session.query(FinancialLineItem).filter_by(period_id=period.id, item_name=item_name).first()
                    )
                    if not line_item:
                        line_item = FinancialLineItem(
                            period_id=period.id,
                            item_name=item_name,
                            value=val,
                            unit="USD (Millions)",
                            source="SEC filing",
                        )
                        session.add(line_item)
                    else:
                        # Always overwrite with the freshest value
                        line_item.value = val
                        line_item.source = "SEC filing"

                periods_count += 1

            session.commit()
            logger.info(
                f"[Task {self.request.id}] Ingested {periods_count} periods for " f"'{ticker_clean}' ({company.name})"
            )
            INGESTION_TOTAL.labels(status="SUCCESS").inc()
            INGESTION_DURATION_SECONDS.observe(time.monotonic() - _started_at)
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
        INGESTION_TOTAL.labels(status="FAILED").inc()
        INGESTION_DURATION_SECONDS.observe(time.monotonic() - _started_at)
        return {"ticker": ticker_clean, "status": "FAILED", "error": str(e)}


@celery_app.task(name="src.ingestion.tasks.ingest_batch_companies")
def ingest_batch_companies(tickers: list[str]) -> dict[str, Any]:
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
