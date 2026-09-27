from __future__ import annotations

import logging
from typing import Any

from src.ingestion.sec_client import SECClient, SECClientError

logger = logging.getLogger(__name__)


def discover_latest_filing(ticker: str, filing_type: str = "10-Q") -> dict[str, Any]:
    ticker = ticker.upper().strip()
    if not ticker:
        raise SECClientError("Ticker is required to discover a filing.")

    client = SECClient()
    filing = client.filing_metadata(ticker, filing_type)
    logger.info("Discovered filing for %s: %s", ticker, filing["filing_url"])
    return filing


def discover_recent_filings(ticker: str, filing_type: str = "10-Q", limit: int = 4) -> list[dict[str, Any]]:
    """Discovers up to `limit` recent filings (newest first) for historical backfill."""
    ticker = ticker.upper().strip()
    if not ticker:
        raise SECClientError("Ticker is required to discover filings.")

    client = SECClient()
    filings = client.filing_history(ticker, filing_type, limit=limit)
    logger.info("Discovered %d filing(s) for %s", len(filings), ticker)
    return filings
