from __future__ import annotations

import re
from typing import Any


def normalize_financial_value(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    negative = False
    if "(" in value and ")" in value:
        negative = True
        value = value.replace("(", "").replace(")", "").strip()
    elif value.startswith("-"):
        negative = True
        value = value[1:].strip()

    value = value.replace("$", "").replace(",", "")
    value = value.replace("%", "")

    unit_match = re.search(r"\b(thousand|thousands|million|millions|billion|billions)\b|\b[kmb]\b", value.lower())
    if unit_match:
        unit = unit_match.group(0).lower()
        if unit in {"thousand", "thousands", "k"}:
            value = re.sub(rf"\b{re.escape(unit)}\b", "", value, flags=re.IGNORECASE)
            multiplier = 1000.0
        elif unit in {"million", "millions", "m"}:
            value = re.sub(rf"\b{re.escape(unit)}\b", "", value, flags=re.IGNORECASE)
            multiplier = 1_000_000.0
        elif unit in {"billion", "billions", "b"}:
            value = re.sub(rf"\b{re.escape(unit)}\b", "", value, flags=re.IGNORECASE)
            multiplier = 1_000_000_000.0
        else:
            multiplier = 1.0
    else:
        multiplier = 1.0

    value = value.strip()
    numeric = re.search(r"[-+]?\d+(?:\.\d+)?", value)
    if numeric is None:
        return None

    result = float(numeric.group(0)) * multiplier
    return -result if negative else result


def normalize_statement_rows(rows: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for label, raw in rows.items():
        normalized_value = normalize_financial_value(raw)
        normalized[label] = normalized_value
    return normalized


def _clean_label(label: str) -> str:
    return " ".join(label.replace("’", "'").replace("'", "").lower().split())


# (canonical key, label substrings to match in priority order, substrings that disqualify a match)
_CANONICAL_RULES: list[tuple[str, list[str], list[str]]] = [
    ("revenue", ["total net sales", "total revenue", "total revenues", "net sales", "total sales"], ["cost of"]),
    ("revenue", ["revenue", "revenues", "net revenue"], ["cost of", "per share", "growth"]),
    ("net_income", ["net income"], ["per share", "attributable to noncontrolling", "basic", "diluted"]),
    ("operating_income", ["operating income", "income from operations"], ["per share"]),
    ("total_equity", ["total shareholders equity", "total stockholders equity", "total equity"], []),
    ("current_assets", ["total current assets"], []),
    ("current_liabilities", ["total current liabilities"], []),
]


def derive_canonical_line_items(items: dict[str, float | None]) -> dict[str, float]:
    """Maps a filing's own line-item wording (e.g. "Total net sales", "Net
    income", "Total shareholders' equity") onto the fixed keys
    analytics/metrics.py and the dashboard read ("revenue", "net_income",
    "operating_income", "total_equity", "current_assets",
    "current_liabilities").

    Real SEC filings never use those exact key names -- only hand-built
    demo/test data did -- so without this mapping every KPI card and ratio
    silently reads None from a real scrape even though the raw line items
    were extracted correctly. Returns only the canonical keys it could
    confidently match; callers merge this into the raw `items` dict so the
    filing's own wording is still kept for display.
    """
    canonical: dict[str, float] = {}
    for key, must_contain_any, exclude in _CANONICAL_RULES:
        if key in canonical:
            continue
        for label, value in items.items():
            if value is None:
                continue
            cleaned = _clean_label(label)
            if any(term in cleaned for term in exclude):
                continue
            if any(term in cleaned for term in must_contain_any):
                canonical[key] = value
                break
    return canonical
