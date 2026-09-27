"""SEC EDGAR HTML parser for quarterly financial statements."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.ingestion.normalizer import normalize_statement_rows

logger = logging.getLogger(__name__)


def _clean_cell_text(value: str) -> str:
    return " ".join(value.split())


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
    soup = BeautifulSoup(html_content, "lxml")
    statements: dict[str, dict[str, Any]] = {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = _clean_cell_text(cells[0].get_text(" "))
            value = _clean_cell_text(cells[1].get_text(" "))
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
