"""Tests for RequestIdMiddleware: it should echo a caller-supplied request
ID, generate one when absent, and expose /metrics.
"""


def test_health_echoes_caller_supplied_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-id-1"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id-1"


def test_health_generates_a_request_id_when_absent(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]  # non-empty


def test_two_requests_without_explicit_ids_get_different_request_ids(client):
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]
    assert first != second


def test_metrics_endpoint_exposes_prometheus_text_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "fra_ingestion_total" in body
    assert "fra_report_generation_total" in body
    assert "fra_cache_hits_total" in body
