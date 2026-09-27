from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.report import ReportStatus


class ReportCreateRequest(BaseModel):
    company_id: int


class ReportStatusUpdateRequest(BaseModel):
    status: ReportStatus
    output_path: str | None = None
    error_message: str | None = None


class ReportJobResponse(BaseModel):
    id: int
    company_id: int
    status: ReportStatus
    requested_at: datetime
    completed_at: datetime | None = None
    output_path: str | None = None
    download_url: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)
