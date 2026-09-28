"""Regression test for a real bug found scraping a live Apple 10-K filing:
extract_table() matched the filing's Table of Contents (which mentions the
statement heading in a sentence, inside its own <table>) instead of the
actual data table that follows the real, standalone heading element.
"""

from pathlib import Path

from src.ingestion.scraper import extract_financial_rows, extract_table

FIXTURE = Path("tests/fixtures/sec_filing_with_toc.html").read_text(encoding="utf-8")


class _FakePage:
    """Stands in for a Playwright Page: only `.content()` is used by extract_table."""

    def __init__(self, html: str):
        self._html = html

    def content(self) -> str:
        return self._html


def test_extract_table_skips_table_of_contents_entry():
    page = _FakePage(FIXTURE)
    table = extract_table(page, "CONSOLIDATED STATEMENTS OF OPERATIONS")
    text = table.get_text(" ")
    assert "Revenue" in text
    assert "Net Income" in text
    assert "Index to Consolidated Financial Statements" not in text


def test_extract_table_ignores_unrelated_long_sentence_mentioning_the_heading():
    page = _FakePage(FIXTURE)
    table = extract_table(page, "CONSOLIDATED STATEMENTS OF OPERATIONS")
    text = table.get_text(" ")
    assert "accounting standards update" not in text


def test_extract_financial_rows_returns_real_line_items_not_toc_rows():
    page = _FakePage(FIXTURE)
    rows = extract_financial_rows(page, "CONSOLIDATED STATEMENTS OF OPERATIONS")
    assert rows.get("Revenue") == "$94,036"
    assert rows.get("Net Income") == "$(2,345)"
    assert "Consolidated Statements of Operations for the years ended" not in rows


def test_extract_table_finds_balance_sheet_after_income_statement():
    page = _FakePage(FIXTURE)
    table = extract_table(page, "CONSOLIDATED BALANCE SHEETS")
    text = table.get_text(" ")
    assert "Total Assets" in text
