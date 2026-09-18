"""Celery ingestion tasks with failure isolation and structured logging."""
import logging
from typing import Dict, Any, List
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem
from src.ingestion.scraper import fetch_company_financials_html
from src.ingestion.parser import parse_quarterly_financials_html

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="src.ingestion.tasks.ingest_company_financials")
def ingest_company_financials(self, ticker: str) -> Dict[str, Any]:
    """Ingests quarterly financials for a company into the database.

    1. Fetches raw HTML (with retry and exponential backoff).
    2. Parses structured periods and line items from the HTML (in-memory).
    3. Upserts Company, FinancialPeriod, and FinancialLineItem rows.
    4. Returns summary status dict.
    """
    ticker_clean = ticker.upper().strip()
    logger.info(f"[Task {self.request.id}] Starting ingestion for ticker '{ticker_clean}'")

    try:
        # 1: Fetch HTML (in-memory, no disk write)
        html_content = fetch_company_financials_html(ticker_clean)

        # 2: Parse HTML
        parsed_data = parse_quarterly_financials_html(html_content)
        periods_data = parsed_data.get("periods", [])

        if not periods_data:
            logger.warning(f"No financial periods parsed for {ticker_clean}")
            return {"ticker": ticker_clean, "status": "NO_DATA", "periods_ingested": 0}

        # 3: Store in database
        session = SessionLocal()
        try:
            company = session.query(Company).filter_by(ticker=ticker_clean).first()
            if not company:
                company = Company(
                    ticker=ticker_clean,
                    name=parsed_data.get("name", f"{ticker_clean} Corp"),
                    sector=parsed_data.get("sector", "Information Technology"),
                    exchange=parsed_data.get("exchange", "NASDAQ"),
                )
                session.add(company)
                session.flush()

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
                            source="scraper:live",
                        )
                        session.add(line_item)
                    else:
                        line_item.value = val

                periods_count += 1

            session.commit()
            logger.info(
                f"[Task {self.request.id}] Successfully ingested {periods_count} periods for {ticker_clean}"
            )
            return {
                "ticker": ticker_clean,
                "company_id": company.id,
                "status": "SUCCESS",
                "periods_ingested": periods_count,
            }
        except Exception as db_err:
            session.rollback()
            logger.error(f"Database error during ingestion for {ticker_clean}: {db_err}", exc_info=True)
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failure during ingestion for {ticker_clean}: {e}", exc_info=True)
        return {
            "ticker": ticker_clean,
            "status": "FAILED",
            "error": str(e),
        }


@celery_app.task(name="src.ingestion.tasks.ingest_batch_companies")
def ingest_batch_companies(tickers: List[str]) -> Dict[str, Any]:
    """Batch ingestion task with failure isolation.

    A failure on any single company does NOT crash or stop the batch run.
    """
    logger.info(f"Starting batch ingestion for {len(tickers)} companies: {tickers}")
    results = {}
    for ticker in tickers:
        try:
            # Failure isolation: Each company's ingestion runs safely inside try/except
            res = ingest_company_financials(ticker)
            results[ticker] = res
        except Exception as e:
            logger.error(f"Batch ingestion item failed for {ticker}: {e}", exc_info=True)
            results[ticker] = {"ticker": ticker, "status": "FAILED", "error": str(e)}

    return {"total": len(tickers), "results": results}
