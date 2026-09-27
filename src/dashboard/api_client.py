"""HTTP API client for Streamlit dashboard to communicate with FastAPI backend.

Strictly adheres to architectural constraint:
Frontend NEVER accesses the database directly.
"""

import logging
from typing import Any

import requests

from src.core.config import settings

logger = logging.getLogger(__name__)


class FRAApiClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")

    def get_companies(self) -> list[dict[str, Any]]:
        """Fetch list of all tracked companies."""
        try:
            resp = requests.get(f"{self.base_url}/companies", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch companies from API: {e}")
            return []

    def get_financials(self, company_id: int) -> dict[str, Any] | None:
        """Fetch quarterly financial periods and line items for a company."""
        try:
            resp = requests.get(f"{self.base_url}/companies/{company_id}/financials", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch financials for company #{company_id}: {e}")
            return None

    def get_ratios(self, company_id: int) -> dict[str, Any] | None:
        """Fetch calculated financial ratios for a company."""
        try:
            resp = requests.get(f"{self.base_url}/companies/{company_id}/ratios", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch ratios for company #{company_id}: {e}")
            return None

    def compare_companies(self, company_ids: list[int]) -> dict[str, Any] | None:
        """Fetch cross-company comparative analytics and peer percentile rankings."""
        try:
            resp = requests.post(
                f"{self.base_url}/compare",
                json={"company_ids": company_ids},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to compare companies {company_ids}: {e}")
            return None

    def request_report(self, company_id: int) -> dict[str, Any] | None:
        """Request asynchronous report generation for a company."""
        try:
            resp = requests.post(
                f"{self.base_url}/reports",
                json={"company_id": company_id},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to request report for company #{company_id}: {e}")
            return None

    def get_report_job_status(self, job_id: int) -> dict[str, Any] | None:
        """Poll status of an existing report generation job."""
        try:
            resp = requests.get(f"{self.base_url}/reports/{job_id}", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to poll status for report job #{job_id}: {e}")
            return None

    def download_report_bytes(self, job_id: int) -> bytes | None:
        """Download PPTX presentation bytes from API."""
        try:
            resp = requests.get(f"{self.base_url}/reports/{job_id}/download", timeout=30)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            logger.error(f"Failed to download report #{job_id}: {e}")
            return None

    def trigger_ingestion(self, ticker: str) -> dict[str, Any] | None:
        """Trigger asynchronous data scraping for a ticker."""
        try:
            resp = requests.post(
                f"{self.base_url}/ingest",
                json={"ticker": ticker},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to trigger ingestion for {ticker}: {e}")
            return None
