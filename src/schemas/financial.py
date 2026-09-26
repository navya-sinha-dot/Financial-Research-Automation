from datetime import date

from pydantic import BaseModel, ConfigDict


class LineItemResponse(BaseModel):
    id: int
    item_name: str
    value: float
    unit: str | None = "USD"
    source: str | None = "scraper"

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
    line_items: list[LineItemResponse] = []
    computed_ratios: list[ComputedRatioResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CompanyFinancialsResponse(BaseModel):
    company_id: int
    ticker: str
    name: str
    periods: list[FinancialPeriodResponse]

    model_config = ConfigDict(from_attributes=True)
