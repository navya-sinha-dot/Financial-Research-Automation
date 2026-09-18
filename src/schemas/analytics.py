from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class CompareRequest(BaseModel):
    company_ids: List[int]


class CompanyMetricSummary(BaseModel):
    company_id: int
    ticker: str
    name: str
    latest_revenue: Optional[float] = None
    latest_net_income: Optional[float] = None
    yoy_growth: Optional[float] = None
    qoq_growth: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    current_ratio: Optional[float] = None
    percentile_rankings: Dict[str, float] = {}


class PeerCompareResponse(BaseModel):
    companies: List[CompanyMetricSummary]
    summary_stats: Dict[str, Dict[str, float]] = {}
