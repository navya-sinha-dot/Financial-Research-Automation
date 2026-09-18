from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.ingestion.tasks import ingest_company_financials

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])


class IngestRequest(BaseModel):
    ticker: str


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def trigger_ingestion(payload: IngestRequest):
    """Triggers an asynchronous scraping and ingestion task for a given ticker."""
    task = ingest_company_financials.delay(payload.ticker)
    return {
        "ticker": payload.ticker.upper(),
        "task_id": str(task.id),
        "status": "QUEUED",
        "message": f"Ingestion job for {payload.ticker.upper()} queued successfully.",
    }
