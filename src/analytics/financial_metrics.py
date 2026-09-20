from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def revenue_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    return safe_divide((current or 0) - (previous or 0), previous) if previous not in (None, 0) else None


def gross_margin(gross_profit: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return safe_divide(gross_profit, revenue)


def operating_margin(operating_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return safe_divide(operating_income, revenue)


def net_margin(net_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return safe_divide(net_income, revenue)


def eps_growth(current_eps: Optional[float], previous_eps: Optional[float]) -> Optional[float]:
    return safe_divide((current_eps or 0) - (previous_eps or 0), previous_eps) if previous_eps not in (None, 0) else None


def current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    return safe_divide(current_assets, current_liabilities)


def debt_to_equity(total_debt: Optional[float], equity: Optional[float]) -> Optional[float]:
    return safe_divide(total_debt, equity) if equity not in (None, 0) else None


def operating_cash_flow_margin(operating_cash_flow: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return safe_divide(operating_cash_flow, revenue)


def free_cash_flow_growth(current_fcf: Optional[float], previous_fcf: Optional[float]) -> Optional[float]:
    return safe_divide((current_fcf or 0) - (previous_fcf or 0), previous_fcf) if previous_fcf not in (None, 0) else None


def summarize_metrics(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    result = {}
    records = list(records)
    if not records:
        return result
    latest = records[-1]
    result["revenue"] = latest.get("income_statement", {}).get("Revenue")
    result["net_income"] = latest.get("income_statement", {}).get("Net Income")
    result["operating_income"] = latest.get("income_statement", {}).get("Operating Income")
    result["gross_margin"] = gross_margin(latest.get("income_statement", {}).get("Gross Profit"), latest.get("income_statement", {}).get("Revenue"))
    result["operating_margin"] = operating_margin(latest.get("income_statement", {}).get("Operating Income"), latest.get("income_statement", {}).get("Revenue"))
    result["net_margin"] = net_margin(latest.get("income_statement", {}).get("Net Income"), latest.get("income_statement", {}).get("Revenue"))
    result["operating_cash_flow"] = latest.get("cash_flow", {}).get("Operating Cash Flow")
    result["free_cash_flow"] = latest.get("cash_flow", {}).get("Free Cash Flow")
    result["eps"] = latest.get("income_statement", {}).get("Basic EPS") or latest.get("income_statement", {}).get("Diluted EPS")
    return result
