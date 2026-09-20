from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class FinancialStatement:
    name: str
    rows: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedQuarter:
    company: str
    ticker: str
    cik: Optional[str] = None
    filing_type: str = "10-Q"
    filing_date: Optional[str] = None
    period: Optional[str] = None
    filing_url: Optional[str] = None
    income_statement: Dict[str, Any] = field(default_factory=dict)
    balance_sheet: Dict[str, Any] = field(default_factory=dict)
    cash_flow: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
