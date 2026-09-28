from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from src.core.config import settings
from src.core.constants import CACHE_DIR, DEFAULT_SEC_USER_AGENT

logger = logging.getLogger(__name__)


class SECClientError(RuntimeError):
    pass


class SECRequestError(SECClientError):
    """Raised on a transient HTTP failure; retried with backoff before giving up."""


class SECClient:
    def __init__(self, user_agent: str | None = None):
        self.user_agent: str = user_agent or str(getattr(settings, "SEC_USER_AGENT", DEFAULT_SEC_USER_AGENT))
        self.base_url = "https://www.sec.gov"
        self._last_request: float = 0.0
        self._cache_dir = CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _throttle(self) -> None:
        """Politeness delay with random jitter so requests don't land on a fixed cadence."""
        delay = float(getattr(settings, "SEC_REQUEST_DELAY", 1.0))
        jitter = float(getattr(settings, "SEC_REQUEST_JITTER", 0.0))
        target = delay + (random.uniform(0, jitter) if jitter > 0 else 0.0)
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last_request = time.monotonic()

    @retry(
        retry=retry_if_exception_type(SECRequestError),
        stop=stop_after_attempt(getattr(settings, "SEC_MAX_RETRIES", 4)),
        wait=wait_exponential_jitter(initial=1, max=15),
        reraise=True,
    )
    def _request(self, url: str, *, timeout: int = 30) -> httpx.Response:
        self._throttle()
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        }
        try:
            response = httpx.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise SECRequestError(f"Transient network error requesting {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503, 504):
                raise SECRequestError(f"Retryable HTTP {exc.response.status_code} for {url}") from exc
            raise

    def _cache_key(self, url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _read_cache(self, url: str) -> Any | None:
        cache_file = self._cache_dir / self._cache_key(url)
        if not cache_file.exists():
            return None
        try:
            envelope = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_at = envelope.get("cached_at", 0.0)
            ttl = float(getattr(settings, "SEC_CACHE_TTL_SECONDS", 86400))
            if ttl > 0 and (time.time() - cached_at) > ttl:
                logger.info("Cache expired for %s (age > %ss)", url, ttl)
                return None
            logger.info("Using cached SEC response for %s", url)
            return envelope.get("payload")
        except Exception:
            return None

    def _write_cache(self, url: str, payload: Any) -> None:
        cache_file = self._cache_dir / self._cache_key(url)
        envelope = {"cached_at": time.time(), "payload": payload}
        cache_file.write_text(json.dumps(envelope, default=str), encoding="utf-8")

    def company_search(self, ticker: str) -> dict[str, Any]:
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

    def _build_filing(self, payload: dict[str, Any], ticker: str, cik: str, index: int, form: str) -> dict[str, Any]:
        recent = payload["filings"]["recent"]
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

    def filing_history(self, ticker: str, filing_type: str = "10-Q", limit: int = 4) -> list[dict[str, Any]]:
        """Returns up to `limit` of the most recent 10-Q/10-K filings, newest first.

        Powers multi-quarter historical backfill so YoY/QoQ analytics have real
        data to work with instead of a single snapshot period.
        """
        cik = self.cik_lookup(ticker)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        cached = self._read_cache(url)
        payload = cached or self._request(url).json()
        if cached is None:
            self._write_cache(url, payload)

        recent = payload.get("filings", {}).get("recent", {})
        filings = []
        for index, form in enumerate(recent.get("form", [])):
            if form not in {filing_type, "10-K"}:
                continue
            filings.append(self._build_filing(payload, ticker, cik, index, form))
            if len(filings) >= limit:
                break

        if not filings:
            forms_seen = set(recent.get("form", []))
            if forms_seen & {"20-F", "40-F", "6-K"}:
                raise SECClientError(
                    f"{ticker.upper()} is a foreign private issuer -- it files Form 20-F/40-F "
                    "(annual) and 6-K instead of 10-Q/10-K. This scraper only supports the "
                    "10-Q/10-K statement layout used by US domestic filers."
                )
            raise SECClientError(f"No recent {filing_type} or 10-K filing found for {ticker.upper()}.")
        return filings

    def filing_metadata(self, ticker: str, filing_type: str = "10-Q") -> dict[str, Any]:
        """Returns the single most recent filing. Kept for backward compatibility."""
        return self.filing_history(ticker, filing_type=filing_type, limit=1)[0]
