from __future__ import annotations

import hashlib
import json
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from src.core.config import settings
from src.core.constants import CACHE_DIR, DEFAULT_SEC_USER_AGENT

logger = logging.getLogger(__name__)


class SECClientError(RuntimeError):
    pass


class SECClient:
    def __init__(self, user_agent: str | None = None):
        self.user_agent = user_agent or getattr(settings, "SEC_USER_AGENT", DEFAULT_SEC_USER_AGENT)
        self.base_url = "https://www.sec.gov"
        self._last_request: float = 0.0
        self._cache_dir = CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _throttle(self) -> None:
        delay = float(getattr(settings, "SEC_REQUEST_DELAY", 1.0))
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.monotonic()

    def _request(self, url: str, *, timeout: int = 30) -> httpx.Response:
        self._throttle()
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def _cache_key(self, url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _read_cache(self, url: str) -> Optional[Dict[str, Any]]:
        cache_file = self._cache_dir / self._cache_key(url)
        if not cache_file.exists():
            return None
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            logger.info("Using cached SEC response for %s", url)
            return payload
        except Exception:
            return None

    def _write_cache(self, url: str, payload: Dict[str, Any]) -> None:
        cache_file = self._cache_dir / self._cache_key(url)
        cache_file.write_text(json.dumps(payload, default=str), encoding="utf-8")

    def company_search(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        cache_key = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&owner=exclude&action=getcompany&match=&start=0&count=20"
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        try:
            response = self._request(cache_key)
            payload = {"ticker": ticker, "html": response.text}
            self._write_cache(cache_key, payload)
            return payload
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("SEC company search failed for %s: %s", ticker, exc)
            raise SECClientError(f"Could not resolve company for {ticker}: {exc}") from exc

    def cik_lookup(self, ticker: str) -> str:
        ticker = ticker.upper().strip()
        if not ticker:
            raise SECClientError("Ticker is required for CIK lookup.")
        url = "https://www.sec.gov/files/company_tickers.json"
        cached = self._read_cache(url)
        payload = cached or self._request(url).json()
        if cached is None:
            self._write_cache(url, payload)

        for company in payload.values():
            if company.get("ticker", "").upper() == ticker:
                return f"{int(company['cik_str']):010d}"
        raise SECClientError(f"Could not find SEC CIK for ticker {ticker}.")

    def filing_metadata(self, ticker: str, filing_type: str = "10-Q") -> Dict[str, Any]:
        cik = self.cik_lookup(ticker)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        cached = self._read_cache(url)
        payload = cached or self._request(url).json()
        if cached is None:
            self._write_cache(url, payload)

        recent = payload.get("filings", {}).get("recent", {})
        for index, form in enumerate(recent.get("form", [])):
            if form not in {filing_type, "10-K"}:
                continue
            accession = recent["accessionNumber"][index]
            accession_path = accession.replace("-", "")
            document = recent["primaryDocument"][index]
            return {
                "ticker": ticker.upper(),
                "company_name": payload.get("name", f"{ticker.upper()} Inc."),
                "cik": cik,
                "filing_type": form,
                "filing_date": recent["filingDate"][index],
                "period_of_report": recent["reportDate"][index],
                "accession_number": accession,
                "filing_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{document}",
            }
        raise SECClientError(f"No recent {filing_type} or 10-K filing found for {ticker.upper()}.")
