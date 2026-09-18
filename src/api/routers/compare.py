from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from src.core.database import get_db
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem
from src.schemas.analytics import CompareRequest, PeerCompareResponse, CompanyMetricSummary
from src.analytics.metrics import compute_period_ratios, compute_peer_percentiles

router = APIRouter(prefix="/compare", tags=["Peer Comparison"])


@router.post("", response_model=PeerCompareResponse)
def compare_companies(payload: CompareRequest, db: Session = Depends(get_db)):
    """Accepts a list of company IDs and returns cross-company metric comparisons and peer percentile rankings."""
    if not payload.company_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one company_id to compare.")

    companies = db.query(Company).filter(Company.id.in_(payload.company_ids)).all()
    if not companies:
        raise HTTPException(status_code=404, detail="No matching companies found.")

    company_summaries = []
    for comp in companies:
        periods = (
            db.query(FinancialPeriod)
            .filter_by(company_id=comp.id)
            .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.report_date.asc())
            .all()
        )
        if not periods:
            company_summaries.append({
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
            })
            continue

        # Format periods data for analytics calculation
        periods_data = []
        for p in periods:
            items_dict = {item.item_name: item.value for item in p.line_items}
            periods_data.append({
                "period_type": p.period_type,
                "fiscal_year": p.fiscal_year,
                "report_date": p.report_date,
                "items": items_dict,
            })

        enriched_periods = compute_period_ratios(periods_data)
        latest_period = enriched_periods[-1]
        latest_items = latest_period.get("items", {})
        latest_ratios = latest_period.get("computed_ratios", {})

        company_summaries.append({
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
        })

    # Compute peer percentiles across selected companies
    ranked_summaries = compute_peer_percentiles(company_summaries)

    # Calculate summary stats (mean, min, max) for numeric fields
    df_metrics = pd.DataFrame(ranked_summaries)
    summary_stats: Dict[str, Dict[str, float]] = {}
    numeric_cols = ["latest_revenue", "net_margin", "roe", "current_ratio", "yoy_growth"]
    for col in numeric_cols:
        if col in df_metrics.columns and df_metrics[col].dropna().count() > 0:
            summary_stats[col] = {
                "mean": round(float(df_metrics[col].mean()), 4),
                "min": round(float(df_metrics[col].min()), 4),
                "max": round(float(df_metrics[col].max()), 4),
            }

    typed_summaries = [CompanyMetricSummary(**item) for item in ranked_summaries]
    return PeerCompareResponse(companies=typed_summaries, summary_stats=summary_stats)
