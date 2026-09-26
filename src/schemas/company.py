from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    ticker: str
    name: str
    sector: str | None = "Information Technology"
    exchange: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyResponse(CompanyBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
