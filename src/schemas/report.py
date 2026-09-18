from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from src.models.report import ReportStatus


class ReportCreateRequest(BaseModel):
    company_id: int


class ReportStatusUpdateRequest(BaseModel):
    status: ReportStatus
    output_path: Optional[str] = None
    error_message: Optional[str] = None


class ReportJobResponse(BaseModel):
    id: int
    company_id: int
    status: ReportStatus
    requested_at: datetime
    completed_at: Optional[datetime] = None
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
