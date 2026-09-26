"""Unit tests for SECClient resilience features: TTL cache, retry/backoff, and
multi-filing history discovery -- all exercised without any real network call.
"""
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from src.ingestion.sec_client import SECClient, SECClientError, SECRequestError


@pytest.fixture
def client(tmp_path, monkeypatch):
    c = SECClient(user_agent="TestAgent/1.0 test@example.com")
    monkeypatch.setattr(c, "_cache_dir", tmp_path)
    return c


def test_cache_round_trip(client):
    url = "https://example.test/some-endpoint"
    client._write_cache(url, {"hello": "world"})
    assert client._read_cache(url) == {"hello": "world"}


def test_cache_expires_after_ttl(client, monkeypatch):
    monkeypatch.setattr("src.ingestion.sec_client.settings.SEC_CACHE_TTL_SECONDS", 1)
    url = "https://example.test/expiring-endpoint"
    client._write_cache(url, {"hello": "world"})

    cache_file = client._cache_dir / client._cache_key(url)
    envelope = json.loads(cache_file.read_text())
    envelope["cached_at"] = time.time() - 10  # force it to look stale
    cache_file.write_text(json.dumps(envelope))

    assert client._read_cache(url) is None


def test_request_retries_transient_failures_then_succeeds(client, monkeypatch):
    calls = {"count": 0}

    def flaky_get(url, headers=None, timeout=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ConnectTimeout("simulated timeout")
        return httpx.Response(200, request=httpx.Request("GET", url), json={"ok": True})

    monkeypatch.setattr("src.ingestion.sec_client.httpx.get", flaky_get)
    monkeypatch.setattr(client, "_throttle", lambda: None)  # skip real sleeping in the test

    response = client._request("https://example.test/flaky")
    assert response.json() == {"ok": True}
    assert calls["count"] == 3


def test_request_does_not_retry_permanent_client_errors(client, monkeypatch):
    def not_found(url, headers=None, timeout=None):
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr("src.ingestion.sec_client.httpx.get", not_found)
    monkeypatch.setattr(client, "_throttle", lambda: None)

    with pytest.raises(httpx.HTTPStatusError):
        client._request("https://example.test/missing")


def test_throttle_enforces_minimum_spacing_with_jitter(client, monkeypatch):
    monkeypatch.setattr("src.ingestion.sec_client.settings.SEC_REQUEST_DELAY", 0.05)
    monkeypatch.setattr("src.ingestion.sec_client.settings.SEC_REQUEST_JITTER", 0.02)

    start = time.monotonic()
    client._throttle()
    client._throttle()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05  # at least the base delay was respected


def _fake_submissions_payload(forms):
    """Builds a minimal SEC submissions.json-shaped payload for `forms`."""
    return {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "form": [f for f, _ in forms],
                "filingDate": [d for _, d in forms],
                "reportDate": [d for _, d in forms],
                "accessionNumber": [f"000{i}-00-00000{i}" for i in range(len(forms))],
                "primaryDocument": [f"doc{i}.htm" for i in range(len(forms))],
            }
        },
    }


def test_filing_history_returns_most_recent_n_filings_in_order(client, monkeypatch):
    payload = _fake_submissions_payload([
        ("10-Q", "2024-01-30"),
        ("8-K", "2023-12-01"),  # not a target form type, must be skipped
        ("10-Q", "2023-10-30"),
        ("10-K", "2023-08-15"),
        ("10-Q", "2023-04-30"),
    ])

    monkeypatch.setattr(client, "cik_lookup", lambda ticker: "0000320193")
    monkeypatch.setattr(client, "_read_cache", lambda url: None)
    monkeypatch.setattr(client, "_write_cache", lambda url, payload: None)
    monkeypatch.setattr(client, "_request", lambda url: SimpleNamespace(json=lambda: payload))

    filings = client.filing_history("AAPL", filing_type="10-Q", limit=3)

    assert len(filings) == 3
    assert [f["filing_date"] for f in filings] == ["2024-01-30", "2023-10-30", "2023-08-15"]
    assert all(f["ticker"] == "AAPL" for f in filings)


def test_filing_history_raises_when_no_matching_filings(client, monkeypatch):
    payload = _fake_submissions_payload([("8-K", "2023-12-01")])

    monkeypatch.setattr(client, "cik_lookup", lambda ticker: "0000320193")
    monkeypatch.setattr(client, "_read_cache", lambda url: None)
    monkeypatch.setattr(client, "_write_cache", lambda url, payload: None)
    monkeypatch.setattr(client, "_request", lambda url: SimpleNamespace(json=lambda: payload))

    with pytest.raises(SECClientError):
        client.filing_history("AAPL", filing_type="10-Q", limit=3)
