from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from src.api.rate_limit import limiter
from src.api.security import require_api_key
from src.core.config import settings
from src.ingestion.tasks import ingest_company_financials

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])


class IngestRequest(BaseModel):
    ticker: str


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
@limiter.limit(settings.RATE_LIMIT_INGEST)
def trigger_ingestion(request: Request, payload: IngestRequest):
    """Trigger scraping and ingestion, synchronously in local demo mode.

    Rate-limited and API-key-gated: this kicks off a real browser scrape,
    which is the most expensive operation the API exposes.
    """
    task = ingest_company_financials.delay(payload.ticker)
    result = task.get(propagate=False) if settings.CELERY_TASK_ALWAYS_EAGER else None
    task_status = result.get("status", "QUEUED") if isinstance(result, dict) else "QUEUED"
    return {
        "ticker": payload.ticker.upper(),
        "task_id": str(task.id),
        "status": task_status,
        "result": result,
        "message": f"Ingestion job for {payload.ticker.upper()} {task_status.lower()}.",
    }
