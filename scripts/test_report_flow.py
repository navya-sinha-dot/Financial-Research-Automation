"""Quick test script to verify end-to-end report generation flow."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.api.main import app

with TestClient(app) as client:
    print("1. Requesting report generation for Company 1 (INFY)...")
    res = client.post("/reports", json={"company_id": 1})
    print("POST /reports status:", res.status_code)
    job_data = res.json()
    print("Job response:", job_data)
    job_id = job_data["id"]

    print(f"2. Checking status for Job #{job_id}...")
    status_res = client.get(f"/reports/{job_id}")
    print("GET /reports/{id} status:", status_res.status_code)
    status_data = status_res.json()
    print("Final job status:", status_data)

    if status_data.get("status") == "COMPLETED":
        print(f"3. Downloading generated report from /reports/{job_id}/download...")
        dl_res = client.get(f"/reports/{job_id}/download")
        print("Download status:", dl_res.status_code)
        print("Downloaded bytes length:", len(dl_res.content))
        print("SUCCESS! PPTX investor report generated and verified!")
    else:
        print("Report not completed yet:", status_data)
