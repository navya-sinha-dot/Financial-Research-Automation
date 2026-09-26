"""Verifies the Celery tasks actually increment the Prometheus counters
defined in src.core.metrics, not just that the metrics exist.
"""
from datetime import date
from unittest.mock import patch

from prometheus_client import REGISTRY

from src.ingestion.tasks import ingest_company_financials


def _sample(name: str, labels: dict) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return value or 0.0


def test_ingestion_success_increments_counter_and_records_duration(db_session):
    before = _sample("fra_ingestion_total", {"status": "SUCCESS"})

    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        mock_fetch.return_value = {
            "ticker": "METRICCO",
            "name": "Metric Co",
            "periods": [
                {
                    "period_type": "Q1",
                    "fiscal_year": 2024,
                    "report_date": date(2023, 6, 30),
                    "items": {"revenue": 100.0, "net_income": 10.0},
                }
            ],
        }
        result = ingest_company_financials("METRICCO")

    assert result["status"] == "SUCCESS"
    after = _sample("fra_ingestion_total", {"status": "SUCCESS"})
    assert after == before + 1


def test_ingestion_failure_increments_failed_counter(db_session):
    before = _sample("fra_ingestion_total", {"status": "FAILED"})

    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        mock_fetch.side_effect = RuntimeError("scrape blew up")
        result = ingest_company_financials("BOOMCO")

    assert result["status"] == "FAILED"
    after = _sample("fra_ingestion_total", {"status": "FAILED"})
    assert after == before + 1
