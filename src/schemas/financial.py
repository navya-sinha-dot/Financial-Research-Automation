from datetime import date
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict


class LineItemResponse(BaseModel):
    id: int
    item_name: str
    value: float
    unit: Optional[str] = "USD"
    source: Optional[str] = "scraper"

    model_config = ConfigDict(from_attributes=True)


class ComputedRatioResponse(BaseModel):
    id: int
    ratio_name: str
    value: float

    model_config = ConfigDict(from_attributes=True)


class FinancialPeriodResponse(BaseModel):
    id: int
    company_id: int
    period_type: str
    fiscal_year: int
    report_date: date
    line_items: List[LineItemResponse] = []
    computed_ratios: List[ComputedRatioResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CompanyFinancialsResponse(BaseModel):
    company_id: int
    ticker: str
    name: str
    periods: List[FinancialPeriodResponse]

    model_config = ConfigDict(from_attributes=True)
