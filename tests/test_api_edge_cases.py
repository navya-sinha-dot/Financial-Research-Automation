"""Edge-case coverage for the ingestion and reports routers: 404s, status
transitions, and download failure modes that the happy-path tests don't hit.
"""

from datetime import date
from unittest.mock import patch


def _mock_company_data(ticker: str):
    return {
        "ticker": ticker,
        "name": f"{ticker} Corporation",
        "periods": [
            {
                "period_type": "Q1",
                "fiscal_year": 2024,
                "report_date": date(2023, 6, 30),
                "items": {"revenue": 5000.0, "net_income": 900.0},
            }
        ],
    }


def test_trigger_ingestion_returns_task_result(client):
    with patch("src.ingestion.tasks.fetch_company_financials") as mock_fetch:
        mock_fetch.side_effect = _mock_company_data

        response = client.post("/ingest", json={"ticker": "aapl"})
        assert response.status_code == 202
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["status"] == "SUCCESS"
        assert data["result"]["periods_ingested"] >= 1


def test_get_report_job_status_404_when_missing(client):
    response = client.get("/reports/999999")
    assert response.status_code == 404


def test_download_report_404_when_job_missing(client):
    response = client.get("/reports/999999/download")
    assert response.status_code == 404


def test_download_report_400_when_not_completed(client, seeded_db):
    from src.models.report import ReportJob, ReportStatus

    # Insert the job directly rather than via POST /reports: under
    # CELERY_TASK_ALWAYS_EAGER the report task runs synchronously and would
    # already be COMPLETED by the time the endpoint responds.
    job = ReportJob(company_id=1, status=ReportStatus.PROCESSING)
    seeded_db.add(job)
    seeded_db.commit()

    response = client.get(f"/reports/{job.id}/download")
    assert response.status_code == 400


def test_download_report_404_when_completed_but_file_missing(client, seeded_db):
    create_res = client.post("/reports", json={"company_id": 1})
    job_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/reports/{job_id}/status",
        json={"status": "COMPLETED", "output_path": "/tmp/does-not-exist-report.pptx"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "COMPLETED"

    response = client.get(f"/reports/{job_id}/download")
    assert response.status_code == 404


def test_update_report_job_status_404_when_missing(client):
    response = client.patch("/reports/999999/status", json={"status": "FAILED", "error_message": "boom"})
    assert response.status_code == 404


def test_request_report_404_when_company_missing(client, db_session):
    response = client.post("/reports", json={"company_id": 999999})
    assert response.status_code == 404


def test_get_company_financials_404_when_missing(client, db_session):
    response = client.get("/companies/999999/financials")
    assert response.status_code == 404


def test_get_company_ratios_404_when_missing(client, db_session):
    response = client.get("/companies/999999/ratios")
    assert response.status_code == 404


def test_compare_endpoint_requires_at_least_one_id(client, db_session):
    response = client.post("/compare", json={"company_ids": []})
    assert response.status_code == 400


def test_compare_endpoint_404_when_no_matches(client, db_session):
    response = client.post("/compare", json={"company_ids": [999999]})
    assert response.status_code == 404
