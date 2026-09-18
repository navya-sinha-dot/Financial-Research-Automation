"""Unit tests for FastAPI endpoints: companies, financials, ratios, compare, reports."""
import pytest
from fastapi.testclient import TestClient
from src.models.report import ReportJob, ReportStatus


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_companies(client: TestClient, seeded_db):
    response = client.get("/companies")
    assert response.status_code == 200
    companies = response.json()
    assert len(companies) >= 1
    assert companies[0]["ticker"] == "INFY"


def test_create_company(client: TestClient, db_session):
    payload = {
        "ticker": "WIPRO",
        "name": "Wipro Limited",
        "sector": "Information Technology",
        "exchange": "NYSE",
    }
    response = client.post("/companies", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["ticker"] == "WIPRO"
    assert created["id"] is not None

    # Test duplicate prevention
    dup_res = client.post("/companies", json=payload)
    assert dup_res.status_code == 409


def test_get_company_financials(client: TestClient, seeded_db):
    # INFY is seeded with ID 1
    response = client.get("/companies/1/financials")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "INFY"
    assert len(data["periods"]) == 2
    
    # Verify line items in Q1
    q1 = data["periods"][0]
    line_item_map = {item["item_name"]: item["value"] for item in q1["line_items"]}
    assert line_item_map["revenue"] == 4617.0
    assert line_item_map["net_income"] == 724.0


def test_get_company_ratios(client: TestClient, seeded_db):
    response = client.get("/companies/1/ratios")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "INFY"
    assert "ratios_by_period" in data
    assert len(data["ratios_by_period"]) == 2

    # Check that computed ratios exist
    q1_ratios = data["ratios_by_period"][0]["computed_ratios"]
    assert "net_margin" in q1_ratios
    assert pytest.approx(q1_ratios["net_margin"], rel=1e-4) == 724.0 / 4617.0
    assert "roe" in q1_ratios
    assert "current_ratio" in q1_ratios


def test_compare_endpoint(client: TestClient, seeded_db):
    # Add a second company to compare
    comp2 = client.post(
        "/companies",
        json={"ticker": "ACN", "name": "Accenture", "sector": "Information Technology"},
    ).json()

    response = client.post("/compare", json={"company_ids": [1, comp2["id"]]})
    assert response.status_code == 200
    data = response.json()
    assert "companies" in data
    assert len(data["companies"]) == 2
    assert "summary_stats" in data


def test_report_lifecycle(client: TestClient, seeded_db):
    # 1. Request report generation
    create_res = client.post("/reports", json={"company_id": 1})
    assert create_res.status_code == 202
    job = create_res.json()
    job_id = job["id"]
    assert job_id is not None
    assert job["status"] in ("PENDING", "PROCESSING", "COMPLETED")

    # 2. Query status
    status_res = client.get(f"/reports/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["id"] == job_id
