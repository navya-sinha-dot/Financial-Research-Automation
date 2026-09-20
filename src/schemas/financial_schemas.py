from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class FinancialValue(BaseModel):
    raw_value: Optional[str] = None
    normalized_value: Optional[float] = None
    unit: str = "units"
    source: str = "SEC filing"


class NormalizedQuarterSchema(BaseModel):
    company: str
    ticker: str
    cik: Optional[str] = None
    filing_type: str = "10-Q"
    filing_date: Optional[str] = None
    period: Optional[str] = None
    filing_url: Optional[str] = None
    income_statement: Dict[str, Any] = Field(default_factory=dict)
    balance_sheet: Dict[str, Any] = Field(default_factory=dict)
    cash_flow: Dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
