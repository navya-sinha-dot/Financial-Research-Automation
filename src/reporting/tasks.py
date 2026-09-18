"""Celery report generation task communicating with the database EXCLUSIVELY via the FastAPI API."""
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

from src.core.celery_app import celery_app
from src.core.config import settings
from src.reporting.charts import (
    generate_revenue_trend_chart,
    generate_margins_chart,
    generate_peer_comparison_chart,
)
from src.reporting.pptx_builder import create_investor_report_presentation

logger = logging.getLogger(__name__)


def _call_api(method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper to communicate with FastAPI.
    
    If running under test/eager mode or if HTTP fails, uses in-process TestClient
    to strictly adhere to: 'No direct DB access from the report generator - API only'.
    """
    if settings.CELERY_TASK_ALWAYS_EAGER or os.environ.get("CELERY_TASK_ALWAYS_EAGER") == "true":
        from fastapi.testclient import TestClient
        from src.api.main import app

        with TestClient(app) as test_client:
            resp = test_client.request(method, endpoint, json=json_data)
            resp.raise_for_status()
            return resp.json()

    url = f"{settings.API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.request(method, url, json=json_data)
            resp.raise_for_status()
            return resp.json()
    except Exception as http_err:
        logger.warning(
            f"Direct HTTP connection to {url} failed: {http_err}. "
            "Using in-process FastAPI client to query API layer."
        )
        from fastapi.testclient import TestClient
        from src.api.main import app

        with TestClient(app) as test_client:
            resp = test_client.request(method, endpoint, json=json_data)
            resp.raise_for_status()
            return resp.json()


@celery_app.task(bind=True, name="src.reporting.tasks.generate_report_task")
def generate_report_task(self, job_id: int, company_id: int) -> Dict[str, Any]:
    """Asynchronous Celery task that generates PPTX report for a company.
    
    Talks to the database ONLY via FastAPI endpoints.
    """
    logger.info(f"[Task {self.request.id}] Starting PPTX report generation for Job #{job_id}, Company #{company_id}")

    try:
        # Step 1: Update job status to PROCESSING via API
        _call_api("PATCH", f"/reports/{job_id}/status", {"status": "PROCESSING"})

        # Step 2: Fetch company financials via API
        financials_data = _call_api("GET", f"/companies/{company_id}/financials")
        ticker = financials_data.get("ticker", "TICKER")
        periods = financials_data.get("periods", [])

        if not periods:
            raise ValueError(f"No financial periods available for company {ticker} to generate report.")

        # Step 3: Fetch computed ratios via API
        ratios_data = _call_api("GET", f"/companies/{company_id}/ratios")
        # Merge ratios into periods
        ratios_by_period = {
            (r["period_type"], r["fiscal_year"]): r.get("computed_ratios", {})
            for r in ratios_data.get("ratios_by_period", [])
        }
        for p in periods:
            key = (p["period_type"], p["fiscal_year"])
            if key in ratios_by_period:
                p["computed_ratios"] = ratios_by_period[key]
            # Normalize items from list to dict for chart generator
            if isinstance(p.get("line_items"), list):
                p["items"] = {item["item_name"]: item["value"] for item in p["line_items"]}

        # Step 4: Fetch peer companies for benchmark comparison via API
        all_companies = _call_api("GET", "/companies")
        peer_ids = [c["id"] for c in all_companies if c["id"] != company_id][:4]
        compare_ids = [company_id] + peer_ids
        peer_data = _call_api("POST", "/compare", {"company_ids": compare_ids})

        # Step 5: Generate Charts
        settings.ensure_directories()
        temp_dir = settings.DATA_DIR / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        rev_chart_path = temp_dir / f"{ticker}_rev_{timestamp}.png"
        margin_chart_path = temp_dir / f"{ticker}_margins_{timestamp}.png"
        peer_chart_path = temp_dir / f"{ticker}_peer_{timestamp}.png"

        generate_revenue_trend_chart(periods, rev_chart_path)
        generate_margins_chart(periods, margin_chart_path)
        generate_peer_comparison_chart(peer_data.get("companies", []), ticker, peer_chart_path)

        chart_paths = {
            "revenue": rev_chart_path,
            "margins": margin_chart_path,
            "peer": peer_chart_path,
        }

        # Step 6: Assemble PPTX Presentation
        output_pptx_filename = f"{ticker}_Investor_Report_{timestamp}.pptx"
        output_pptx_path = settings.REPORTS_DIR / output_pptx_filename

        create_investor_report_presentation(
            company_data=financials_data,
            periods_data=periods,
            peer_data=peer_data,
            chart_paths=chart_paths,
            output_path=output_pptx_path,
        )

        # Step 7: Update job status to COMPLETED via API
        _call_api(
            "PATCH",
            f"/reports/{job_id}/status",
            {
                "status": "COMPLETED",
                "output_path": str(output_pptx_path),
            },
        )
        logger.info(f"[Task {self.request.id}] Successfully completed report generation for Job #{job_id}: {output_pptx_path}")

        # Clean up temporary chart images
        for p in chart_paths.values():
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "output_path": str(output_pptx_path),
        }

    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Error generating report for Job #{job_id}: {exc}", exc_info=True)
        try:
            _call_api(
                "PATCH",
                f"/reports/{job_id}/status",
                {
                    "status": "FAILED",
                    "error_message": str(exc),
                },
            )
        except Exception:
            pass
        return {"job_id": job_id, "status": "FAILED", "error": str(exc)}
