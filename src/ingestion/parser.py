"""SEC EDGAR HTML parser for quarterly financial statements."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

from src.ingestion.normalizer import normalize_statement_rows

logger = logging.getLogger(__name__)


def _clean_cell_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _statement_target_for_row(label: str) -> str:
    label_l = label.lower()
    if any(
        term in label_l
        for term in [
            "revenue",
            "cost of revenue",
            "gross profit",
            "operating income",
            "net income",
            "basic eps",
            "diluted eps",
        ]
    ):
        return "income_statement"
    if any(
        term in label_l
        for term in [
            "cash and cash",
            "current assets",
            "total assets",
            "current liabilities",
            "total liabilities",
            "shareholders' equity",
            "total debt",
        ]
    ):
        return "balance_sheet"
    if any(
        term in label_l
        for term in [
            "operating cash flow",
            "capital expenditure",
            "investing cash flow",
            "financing cash flow",
            "free cash flow",
        ]
    ):
        return "cash_flow"
    return "income_statement"


def parse_financial_statements(html_content: str) -> dict[str, dict[str, Any]]:
    """Extract a normalized set of SEC financial statements from filing HTML."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html_content, flags=re.IGNORECASE | re.DOTALL)
    statements: dict[str, dict[str, Any]] = {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    for table_html in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
        for row_html in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
            if len(cells) < 2:
                continue
            label = _clean_cell_text(cells[0])
            value = _clean_cell_text(cells[1])
            if not label or not value:
                continue
            target = _statement_target_for_row(label)
            statements[target][label] = value

    normalized = {
        "income_statement": normalize_statement_rows(statements["income_statement"]),
        "balance_sheet": normalize_statement_rows(statements["balance_sheet"]),
        "cash_flow": normalize_statement_rows(statements["cash_flow"]),
    }
    return normalized


def parse_quarterly_financials_html(html_content: str) -> dict[str, Any]:
    """Compatibility wrapper for older ingestion callers."""
    return parse_financial_statements(html_content)
