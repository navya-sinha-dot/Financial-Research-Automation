"""Celery report generation task communicating with the database EXCLUSIVELY via the FastAPI API."""

import contextlib
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from src.core.celery_app import celery_app
from src.core.config import settings
from src.core.metrics import REPORT_GENERATION_DURATION_SECONDS, REPORT_GENERATION_TOTAL
from src.reporting.charts import (
    generate_margins_chart,
    generate_peer_comparison_chart,
    generate_revenue_trend_chart,
)
from src.reporting.pptx_builder import create_investor_report_presentation

logger = logging.getLogger(__name__)


def _api_key_headers() -> dict[str, str]:
    """Auth header for calling back into the API-key-gated write endpoints.

    Empty when settings.API_KEY is unset, matching the API's own opt-in auth.
    """
    return {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}


def _is_eager() -> bool:
    return settings.CELERY_TASK_ALWAYS_EAGER or os.environ.get("CELERY_TASK_ALWAYS_EAGER") == "true"


def _call_api(method: str, endpoint: str, json_data: dict[str, Any] | None = None, *, client: Any = None) -> Any:
    """Helper to communicate with FastAPI.

    Returns whatever shape the endpoint's JSON body is -- a dict for most
    resource endpoints, a list for `/companies`. Callers narrow as needed.

    Pass `client` to reuse a client across several calls in the same task
    run (see `generate_report_task`) -- creating a fresh one per call is
    expensive in eager mode, since `TestClient(app)` triggers a full
    FastAPI startup/shutdown every time. Without one, falls back to the
    original per-call behavior: in-process TestClient under eager mode
    (or if a real HTTP call fails), to strictly adhere to 'No direct DB
    access from the report generator - API only'.
    """
    headers = _api_key_headers()

    if client is not None:
        resp = client.request(method, endpoint, json=json_data, headers=headers)
        resp.raise_for_status()
        return resp.json()

    if _is_eager():
        from fastapi.testclient import TestClient

        from src.api.main import app

        with TestClient(app) as test_client:
            resp = test_client.request(method, endpoint, json=json_data, headers=headers)
            resp.raise_for_status()
            return resp.json()

    url = f"{settings.API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=5.0) as http_client:
            resp = http_client.request(method, url, json=json_data, headers=headers)
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
            resp = test_client.request(method, endpoint, json=json_data, headers=headers)
            resp.raise_for_status()
            return resp.json()


@celery_app.task(bind=True, name="src.reporting.tasks.generate_report_task")
def generate_report_task(self, job_id: int, company_id: int) -> dict[str, Any]:
    """Asynchronous Celery task that generates PPTX report for a company.

    Talks to the database ONLY via FastAPI endpoints.
    """
    logger.info(f"[Task {self.request.id}] Starting PPTX report generation for Job #{job_id}, Company #{company_id}")
    _started_at = time.monotonic()

    # One client shared across every call this task makes, instead of a
    # fresh one per call: in eager mode, TestClient(app) triggers a full
    # FastAPI startup/shutdown on every use, and this task makes six calls
    # -- six full app startups was most of why report generation routinely
    # took ~20s and blew past the dashboard's request timeout.
    shared_client = None
    if _is_eager():
        from fastapi.testclient import TestClient

        from src.api.main import app

        shared_client = TestClient(app)

    try:
        with shared_client if shared_client is not None else contextlib.nullcontext():
            # Step 1: Update job status to PROCESSING via API
            _call_api("PATCH", f"/reports/{job_id}/status", {"status": "PROCESSING"}, client=shared_client)

            # Step 2: Fetch company financials via API
            financials_data = _call_api("GET", f"/companies/{company_id}/financials", client=shared_client)
            ticker = financials_data.get("ticker", "TICKER")
            periods = financials_data.get("periods", [])

            if not periods:
                raise ValueError(f"No financial periods available for company {ticker} to generate report.")

            # Step 3: Fetch computed ratios via API
            ratios_data = _call_api("GET", f"/companies/{company_id}/ratios", client=shared_client)
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
            all_companies_page = _call_api("GET", "/companies?limit=200", client=shared_client)
            all_companies = all_companies_page.get("items", [])
            peer_ids = [c["id"] for c in all_companies if c["id"] != company_id][:4]
            compare_ids = [company_id] + peer_ids
            peer_data = _call_api("POST", "/compare", {"company_ids": compare_ids}, client=shared_client)

            # Step 5: Generate Charts
            settings.ensure_directories()
            temp_dir = settings.DATA_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

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
                client=shared_client,
            )
            logger.info(
                f"[Task {self.request.id}] Successfully completed report generation "
                f"for Job #{job_id}: {output_pptx_path}"
            )

        # Clean up temporary chart images
        for p in chart_paths.values():
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        REPORT_GENERATION_TOTAL.labels(status="COMPLETED").inc()
        REPORT_GENERATION_DURATION_SECONDS.observe(time.monotonic() - _started_at)
        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "output_path": str(output_pptx_path),
        }

    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Error generating report for Job #{job_id}: {exc}", exc_info=True)
        with contextlib.suppress(Exception):
            _call_api(
                "PATCH",
                f"/reports/{job_id}/status",
                {
                    "status": "FAILED",
                    "error_message": str(exc),
                },
            )
        REPORT_GENERATION_TOTAL.labels(status="FAILED").inc()
        REPORT_GENERATION_DURATION_SECONDS.observe(time.monotonic() - _started_at)
        return {"job_id": job_id, "status": "FAILED", "error": str(exc)}
