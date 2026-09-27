import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.analytics.metrics import compute_peer_percentiles, compute_period_ratios
from src.core.cache import cache_get, cache_set
from src.core.config import settings
from src.core.database import get_async_db
from src.models.company import Company
from src.models.financial import FinancialPeriod
from src.schemas.analytics import CompanyMetricSummary, CompareRequest, PeerCompareResponse

router = APIRouter(prefix="/compare", tags=["Peer Comparison"])


def _cache_key(company_ids: list[int]) -> str:
    return "compare:" + ",".join(str(i) for i in sorted(set(company_ids)))


@router.post("", response_model=PeerCompareResponse)
async def compare_companies(payload: CompareRequest, db: AsyncSession = Depends(get_async_db)):
    """Accepts a list of company IDs and returns cross-company metric comparisons and peer percentile rankings.

    Cached for CACHE_TTL_SECONDS since peer percentile ranking recomputes
    ratios for every selected company on each call; results are only ever
    up to CACHE_TTL_SECONDS stale (cache-aside, not invalidation-based).
    """
    if not payload.company_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one company_id to compare.")

    cache_key = _cache_key(payload.company_ids)
    cached = cache_get(cache_key, cache_type="compare")
    if cached is not None:
        return PeerCompareResponse(**cached)

    companies = (await db.execute(select(Company).filter(Company.id.in_(payload.company_ids)))).scalars().all()
    if not companies:
        raise HTTPException(status_code=404, detail="No matching companies found.")

    company_summaries = []
    for comp in companies:
        periods = (
            (
                await db.execute(
                    select(FinancialPeriod)
                    .filter_by(company_id=comp.id)
                    .options(selectinload(FinancialPeriod.line_items))
                    .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.report_date.asc())
                )
            )
            .scalars()
            .all()
        )
        if not periods:
            company_summaries.append(
                {
                    "company_id": comp.id,
                    "ticker": comp.ticker,
                    "name": comp.name,
                    "latest_revenue": None,
                    "latest_net_income": None,
                    "yoy_growth": None,
                    "qoq_growth": None,
                    "net_margin": None,
                    "roe": None,
                    "current_ratio": None,
                }
            )
            continue

        # Format periods data for analytics calculation
        periods_data = []
        for p in periods:
            items_dict = {item.item_name: item.value for item in p.line_items}
            periods_data.append(
                {
                    "period_type": p.period_type,
                    "fiscal_year": p.fiscal_year,
                    "report_date": p.report_date,
                    "items": items_dict,
                }
            )

        enriched_periods = compute_period_ratios(periods_data)
        latest_period = enriched_periods[-1]
        latest_items = latest_period.get("items", {})
        latest_ratios = latest_period.get("computed_ratios", {})

        company_summaries.append(
            {
                "company_id": comp.id,
                "ticker": comp.ticker,
                "name": comp.name,
                "latest_revenue": latest_items.get("revenue"),
                "latest_net_income": latest_items.get("net_income"),
                "yoy_growth": latest_ratios.get("yoy_growth"),
                "qoq_growth": latest_ratios.get("qoq_growth"),
                "net_margin": latest_ratios.get("net_margin"),
                "roe": latest_ratios.get("roe"),
                "current_ratio": latest_ratios.get("current_ratio"),
            }
        )

    # Compute peer percentiles across selected companies
    ranked_summaries = compute_peer_percentiles(company_summaries)

    # Calculate summary stats (mean, min, max) for numeric fields
    df_metrics = pd.DataFrame(ranked_summaries)
    summary_stats: dict[str, dict[str, float]] = {}
    numeric_cols = ["latest_revenue", "net_margin", "roe", "current_ratio", "yoy_growth"]
    for col in numeric_cols:
        if col in df_metrics.columns and df_metrics[col].dropna().count() > 0:
            summary_stats[col] = {
                "mean": round(float(df_metrics[col].mean()), 4),
                "min": round(float(df_metrics[col].min()), 4),
                "max": round(float(df_metrics[col].max()), 4),
            }

    typed_summaries = [CompanyMetricSummary(**item) for item in ranked_summaries]
    response = PeerCompareResponse(companies=typed_summaries, summary_stats=summary_stats)

    cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_SECONDS, cache_type="compare")
    return response
