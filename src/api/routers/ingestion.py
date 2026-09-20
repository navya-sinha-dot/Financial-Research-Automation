from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.core.config import settings
from src.ingestion.tasks import ingest_company_financials

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])


class IngestRequest(BaseModel):
    ticker: str


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def trigger_ingestion(payload: IngestRequest):
    """Trigger scraping and ingestion, synchronously in local demo mode."""
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
