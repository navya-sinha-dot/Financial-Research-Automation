from __future__ import annotations

import re
from typing import Any, Dict, Optional


def normalize_financial_value(raw_value: Any) -> Optional[float]:
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


def normalize_statement_rows(rows: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for label, raw in rows.items():
        normalized_value = normalize_financial_value(raw)
        normalized[label] = normalized_value
    return normalized
