"""Standalone, testable financial analytics module.

Contains pure mathematical and statistical computations for financial metrics:
- YoY growth
- QoQ growth
- Net margin
- Return on Equity (ROE)
- Current ratio
- Peer percentile ranking

Contains NO database or UI dependencies.
"""
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd


def compute_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Computes growth rate between two values.
    
    Returns (current - previous) / abs(previous), or None if previous is invalid or zero.
    """
    if current is None or previous is None:
        return None
    try:
        current_val = float(current)
        prev_val = float(previous)
        if prev_val == 0:
            return None
        return (current_val - prev_val) / abs(prev_val)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def compute_net_margin(net_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    """Computes Net Profit Margin: Net Income / Revenue."""
    if net_income is None or revenue is None:
        return None
    try:
        ni = float(net_income)
        rev = float(revenue)
        if rev <= 0:
            return None
        return ni / rev
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def compute_roe(net_income: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    """Computes Return on Equity (ROE): Net Income / Total Stockholders' Equity."""
    if net_income is None or total_equity is None:
        return None
    try:
        ni = float(net_income)
        eq = float(total_equity)
        if eq <= 0:
            return None
        return ni / eq
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def compute_current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """Computes Current Ratio: Current Assets / Current Liabilities."""
    if current_assets is None or current_liabilities is None:
        return None
    try:
        ca = float(current_assets)
        cl = float(current_liabilities)
        if cl <= 0:
            return None
        return ca / cl
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def compute_period_ratios(
    periods_records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Takes a chronological list of financial period dictionaries for a single company.
    
    Each dictionary is expected to have:
    - 'fiscal_year': int
    - 'period_type': str (e.g. 'Q1', 'Q2', 'Q3', 'Q4')
    - 'report_date': date or str
    - 'items': Dict[str, float] containing line items like 'revenue', 'net_income', etc.
    
    Returns a new list of records enriched with computed ratios:
    - yoy_growth
    - qoq_growth
    - net_margin
    - roe
    - current_ratio
    """
    if not periods_records:
        return []

    # Convert to DataFrame for deterministic time-series alignment
    rows = []
    for idx, p in enumerate(periods_records):
        items = p.get("items", {})
        row = {
            "period_index": idx,
            "period_type": p.get("period_type"),
            "fiscal_year": p.get("fiscal_year"),
            "report_date": str(p.get("report_date")),
            "revenue": items.get("revenue"),
            "net_income": items.get("net_income"),
            "operating_income": items.get("operating_income"),
            "total_equity": items.get("total_equity"),
            "current_assets": items.get("current_assets"),
            "current_liabilities": items.get("current_liabilities"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort deterministically by date or year + period
    if "report_date" in df.columns:
        df = df.sort_values(by=["report_date", "fiscal_year"]).reset_index(drop=True)

    # Compute QoQ growth on revenue (1 step lag)
    df["qoq_growth"] = df["revenue"].pct_change(periods=1)

    # Compute YoY growth on revenue (4 quarters lag if quarterly data)
    # If 4 or more periods exist, look back 4 periods; otherwise fallback to previous year's matching period
    df["yoy_growth"] = df["revenue"].pct_change(periods=4)

    # Compute static ratios
    df["net_margin"] = df.apply(
        lambda r: compute_net_margin(r["net_income"], r["revenue"]), axis=1
    )
    df["roe"] = df.apply(
        lambda r: compute_roe(r["net_income"], r["total_equity"]), axis=1
    )
    df["current_ratio"] = df.apply(
        lambda r: compute_current_ratio(r["current_assets"], r["current_liabilities"]), axis=1
    )

    # Reconstruct output
    enriched_results = []
    for _, row in df.iterrows():
        p_idx = int(row["period_index"])
        orig_p = dict(periods_records[p_idx])
        
        computed = {
            "yoy_growth": float(row["yoy_growth"]) if pd.notnull(row["yoy_growth"]) else None,
            "qoq_growth": float(row["qoq_growth"]) if pd.notnull(row["qoq_growth"]) else None,
            "net_margin": float(row["net_margin"]) if pd.notnull(row["net_margin"]) else None,
            "roe": float(row["roe"]) if pd.notnull(row["roe"]) else None,
            "current_ratio": float(row["current_ratio"]) if pd.notnull(row["current_ratio"]) else None,
        }
        orig_p["computed_ratios"] = computed
        enriched_results.append(orig_p)

    return enriched_results


def compute_peer_percentiles(
    companies_data: List[Dict[str, Any]],
    metric_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Calculates peer percentile rankings for a set of companies across given metrics.
    
    Each company dict should contain:
    - 'company_id': int
    - 'ticker': str
    - metrics like 'net_margin', 'roe', 'current_ratio', 'yoy_growth'
    
    Returns the list enriched with 'percentile_rankings': Dict[str, float] (0.0 to 100.0).
    """
    if not companies_data:
        return []

    if metric_keys is None:
        metric_keys = ["net_margin", "roe", "current_ratio", "yoy_growth", "latest_revenue"]

    df = pd.DataFrame(companies_data)
    
    # Calculate percentile rank (0 to 100) for each metric
    rank_df = pd.DataFrame(index=df.index)
    for m in metric_keys:
        if m in df.columns and df[m].dropna().count() > 0:
            # pct=True returns 0 to 1, multiply by 100 and round to 1 decimal
            rank_df[m] = (df[m].rank(pct=True, ascending=True, method="average") * 100.0).round(1)
        else:
            rank_df[m] = np.nan

    results = []
    for idx, row in df.iterrows():
        comp_dict = dict(row)
        percentiles = {}
        for m in metric_keys:
            val = rank_df.loc[idx, m]
            if pd.notnull(val):
                percentiles[m] = float(val)
        comp_dict["percentile_rankings"] = percentiles
        results.append(comp_dict)

    return results
