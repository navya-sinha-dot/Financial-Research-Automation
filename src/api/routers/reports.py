from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.company import Company
from src.models.report import ReportJob, ReportStatus
from src.schemas.report import ReportCreateRequest, ReportJobResponse, ReportStatusUpdateRequest
from src.core.config import settings

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ReportJobResponse, status_code=status.HTTP_202_ACCEPTED)
def request_report_generation(payload: ReportCreateRequest, db: Session = Depends(get_db)):
    """Enqueues an asynchronous report generation job for a company."""
    company = db.query(Company).filter_by(id=payload.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {payload.company_id} does not exist.",
        )

    # Create job in database
    job = ReportJob(
        company_id=payload.company_id,
        status=ReportStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue Celery async task
    try:
        from src.reporting.tasks import generate_report_task
        generate_report_task.delay(job_id=job.id, company_id=company.id)
    except Exception as exc:
        # If celery broker is unavailable or running synchronously
        job.error_message = f"Failed to enqueue task: {str(exc)}"
        db.commit()

    return _build_job_response(job)


@router.get("/{job_id}", response_model=ReportJobResponse)
def get_report_job_status(job_id: int, db: Session = Depends(get_db)):
    """Check the status and download link of a report generation job."""
    job = db.query(ReportJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job with ID {job_id} not found.",
        )
    return _build_job_response(job)


@router.get("/{job_id}/download")
def download_report(job_id: int, db: Session = Depends(get_db)):
    """Download the generated PowerPoint (.pptx) presentation."""
    job = db.query(ReportJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Report job not found.")

    if job.status != ReportStatus.COMPLETED or not job.output_path:
        raise HTTPException(
            status_code=400,
            detail=f"Report is not ready yet. Current status: {job.status}",
        )

    file_path = Path(job.output_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Generated report file was not found on disk.")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@router.patch("/{job_id}/status", response_model=ReportJobResponse)
def update_report_job_status(
    job_id: int,
    payload: ReportStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Endpoint used by the report generator worker to update job status without direct DB access."""
    job = db.query(ReportJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Report job not found.")

    job.status = payload.status
    if payload.output_path:
        job.output_path = payload.output_path
    if payload.error_message:
        job.error_message = payload.error_message
    if payload.status in (ReportStatus.COMPLETED, ReportStatus.FAILED):
        job.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(job)
    return _build_job_response(job)


def _build_job_response(job: ReportJob) -> ReportJobResponse:
    download_url = None
    if job.status == ReportStatus.COMPLETED and job.output_path:
        download_url = f"{settings.API_BASE_URL}/reports/{job.id}/download"

    return ReportJobResponse(
        id=job.id,
        company_id=job.company_id,
        status=job.status,
        requested_at=job.requested_at,
        completed_at=job.completed_at,
        output_path=job.output_path,
        download_url=download_url,
        error_message=job.error_message,
    )
