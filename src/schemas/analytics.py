from pydantic import BaseModel


class CompareRequest(BaseModel):
    company_ids: list[int]


class CompanyMetricSummary(BaseModel):
    company_id: int
    ticker: str
    name: str
    latest_revenue: float | None = None
    latest_net_income: float | None = None
    yoy_growth: float | None = None
    qoq_growth: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    current_ratio: float | None = None
    percentile_rankings: dict[str, float] = {}


class PeerCompareResponse(BaseModel):
    companies: list[CompanyMetricSummary]
    summary_stats: dict[str, dict[str, float]] = {}
