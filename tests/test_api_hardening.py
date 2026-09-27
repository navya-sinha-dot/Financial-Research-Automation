"""Tests for the API-hardening features added in this branch: API-key auth
on mutating endpoints, the structured error envelope, and rate limiting.
"""

from unittest.mock import patch

from src.core.config import settings


def test_create_company_open_when_no_api_key_configured(client, db_session):
    # Default settings.API_KEY == "" means auth is disabled.
    resp = client.post("/companies", json={"ticker": "OPEN", "name": "Open Co"})
    assert resp.status_code == 201


def test_create_company_requires_api_key_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr("src.api.security.settings.API_KEY", "secret123")

    unauthorized = client.post("/companies", json={"ticker": "NOAUTH", "name": "No Auth Co"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/companies",
        json={"ticker": "WITHAUTH", "name": "With Auth Co"},
        headers={"X-API-Key": "secret123"},
    )
    assert authorized.status_code == 201


def test_create_company_rejects_wrong_api_key(client, db_session, monkeypatch):
    monkeypatch.setattr("src.api.security.settings.API_KEY", "secret123")

    resp = client.post(
        "/companies",
        json={"ticker": "WRONGKEY", "name": "Wrong Key Co"},
        headers={"X-API-Key": "not-the-right-key"},
    )
    assert resp.status_code == 401


def test_404_error_envelope_shape(client, db_session):
    resp = client.get("/companies/999999/financials")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["status_code"] == 404
    assert "message" in body["error"]
    assert body["error"]["path"] == "/companies/999999/financials"


def test_422_validation_error_envelope_includes_details(client):
    resp = client.post("/companies", json={"ticker": "MISSING_NAME"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["status_code"] == 422
    assert "details" in body["error"]
    assert isinstance(body["error"]["details"], list)


def test_ingest_endpoint_is_rate_limited(client):
    limit_count = int(settings.RATE_LIMIT_INGEST.split("/")[0])

    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        mock_fetch.side_effect = lambda ticker: {"ticker": ticker, "name": f"{ticker} Co", "periods": []}
        statuses = [client.post("/ingest", json={"ticker": "RLTEST"}).status_code for _ in range(limit_count + 1)]

    assert 429 in statuses
