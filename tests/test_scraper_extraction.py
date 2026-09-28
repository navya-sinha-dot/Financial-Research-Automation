"""Regression test for a real bug found scraping a live Apple 10-K filing:
extract_table() matched the filing's Table of Contents (which mentions the
statement heading in a sentence, inside its own <table>) instead of the
actual data table that follows the real, standalone heading element.
"""

from pathlib import Path

from src.ingestion.scraper import extract_financial_rows, extract_financial_value, extract_table

FIXTURE = Path("tests/fixtures/sec_filing_with_toc.html").read_text(encoding="utf-8")
MSFT_STYLE_FIXTURE = Path("tests/fixtures/sec_filing_msft_style.html").read_text(encoding="utf-8")
SPACER_COLUMNS_FIXTURE = Path("tests/fixtures/sec_filing_spacer_columns.html").read_text(encoding="utf-8")
DUPLICATE_LABELS_FIXTURE = Path("tests/fixtures/sec_filing_duplicate_labels_and_negatives.html").read_text(
    encoding="utf-8"
)
TRAILING_UNITS_NOTE_FIXTURE = Path("tests/fixtures/sec_filing_trailing_units_note.html").read_text(encoding="utf-8")

INCOME_STATEMENT_HINTS = [
    "CONSOLIDATED STATEMENTS OF OPERATIONS",
    "CONSOLIDATED STATEMENTS OF INCOME",
    "STATEMENTS OF OPERATIONS",
    "STATEMENTS OF INCOME",
    "INCOME STATEMENTS",
]
BALANCE_SHEET_HINTS = ["CONSOLIDATED BALANCE SHEETS", "BALANCE SHEETS", "STATEMENTS OF FINANCIAL POSITION"]
CASH_FLOW_HINTS = [
    "CONSOLIDATED STATEMENTS OF CASH FLOWS",
    "STATEMENTS OF CASH FLOWS",
    "CASH FLOWS STATEMENTS",
    "CASH FLOW STATEMENTS",
]


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


def test_extract_table_reconstructs_heading_split_across_adjacent_nodes():
    """Regression test for a real bug found on a live MSFT scrape: the
    heading was split across two adjacent DOM text nodes with no space
    between them ("...FINANCIAL STATEMENTSINCOME STATEMENTS"), so a
    single-node substring match never found it and fell back to the first
    table in the document -- the cover page's checkbox table.
    """
    page = _FakePage(MSFT_STYLE_FIXTURE)
    table = extract_table(page, INCOME_STATEMENT_HINTS)
    text = table.get_text(" ")
    assert "Total revenue" in text
    assert "Net income" in text
    assert "☐" not in text  # cover page checkbox glyphs must not appear
    assert "☑" not in text


def test_extract_table_does_not_confuse_income_statement_with_comprehensive_income():
    page = _FakePage(MSFT_STYLE_FIXTURE)
    table = extract_table(page, INCOME_STATEMENT_HINTS)
    text = table.get_text(" ")
    assert "Other comprehensive income" not in text


def test_extract_table_finds_balance_sheet_with_plain_heading_wording():
    page = _FakePage(MSFT_STYLE_FIXTURE)
    table = extract_table(page, BALANCE_SHEET_HINTS)
    assert "Total current assets" in table.get_text(" ")


def test_extract_table_finds_cash_flow_with_plain_heading_wording():
    page = _FakePage(MSFT_STYLE_FIXTURE)
    table = extract_table(page, CASH_FLOW_HINTS)
    assert "Net cash from operations" in table.get_text(" ")


def test_extract_financial_rows_with_msft_style_fragmented_heading():
    page = _FakePage(MSFT_STYLE_FIXTURE)
    rows = extract_financial_rows(page, INCOME_STATEMENT_HINTS)
    assert rows.get("Total revenue") == "$65,585"
    assert rows.get("Net income") == "$24,667"


def test_extract_financial_rows_skips_spacer_and_currency_symbol_cells():
    """Regression test for a real bug found on a live MSFT scrape: the
    table WAS found correctly, but every row still came back empty because
    extract_financial_rows hardcoded cells[1] as "the value" -- correct for
    Apple's clean 2-column rows, but Microsoft's real tables insert spacer
    (&nbsp;) and bare "$" cells between the label and the number for
    alignment, so cells[1] was always an empty spacer. All rows were
    silently dropped, which looked like extraction succeeding with zero
    data rather than a clear failure.
    """
    page = _FakePage(SPACER_COLUMNS_FIXTURE)
    rows = extract_financial_rows(page, INCOME_STATEMENT_HINTS)
    assert rows.get("Total revenue") == "65,585"
    assert rows.get("Net income") == "24,667"


def test_extract_financial_rows_drops_section_header_rows_with_no_real_value():
    page = _FakePage(SPACER_COLUMNS_FIXTURE)
    rows = extract_financial_rows(page, INCOME_STATEMENT_HINTS)
    assert "Cost of revenue:" not in rows


def test_extract_financial_rows_disambiguates_labels_repeated_under_different_sections():
    """Regression test for a real bug found on a live MSFT scrape: "Product"
    and "Service and other" each appear twice in the real income statement
    (once under Revenue, once under Cost of revenue) with different
    values. A plain label-keyed dict let the Cost of revenue occurrence
    silently overwrite the Revenue one, so the Line Items table displayed
    the wrong number under a correct-looking label with no error at all.
    """
    page = _FakePage(DUPLICATE_LABELS_FIXTURE)
    rows = extract_financial_rows(page, INCOME_STATEMENT_HINTS)

    assert rows.get("Product") == "15,922"
    assert rows.get("Service and other") == "61,751"
    assert rows.get("Cost of revenue - Product") == "2,922"
    assert rows.get("Cost of revenue - Service and other") == "21,121"
    assert rows.get("Total revenue") == "77,673"
    assert rows.get("Total cost of revenue") == "24,043"


def test_extract_financial_rows_reconstructs_negative_value_split_across_cells():
    """Regression test for a real bug found on a live MSFT scrape: a
    negative value's closing parenthesis sometimes sits in its own
    trailing cell, separate from the "(" + number cell. Without
    reattaching it, normalize_financial_value() never sees a matching
    "(...)" pair and silently returns a positive number instead of
    negative.
    """
    page = _FakePage(DUPLICATE_LABELS_FIXTURE)
    rows = extract_financial_rows(page, INCOME_STATEMENT_HINTS)

    raw_value = rows.get("Other expense, net")
    assert raw_value is not None
    assert "(" in raw_value and ")" in raw_value
    assert extract_financial_value(raw_value) == -3660.0


def test_extract_table_matches_heading_followed_by_a_trailing_units_note():
    """Regression test for a real bug found on a live GOOGL scrape: the
    exact heading was already in the hint list ("CONSOLIDATED STATEMENTS
    OF INCOME"), but it's immediately followed by a units/unaudited note
    -- "...OF INCOME(in millions, except per share amounts; unaudited)" --
    before the table starts. The trailing-match check required the
    heading to be (near) the very last thing before the table, so that
    note pushed it past the tolerance and extraction fell through to the
    filing's own Table of Contents (Part II item index) instead.
    """
    page = _FakePage(TRAILING_UNITS_NOTE_FIXTURE)
    table = extract_table(page, INCOME_STATEMENT_HINTS)
    text = table.get_text(" ")
    assert "Revenues" in text
    assert "Net income" in text
    assert "Other comprehensive income" not in text


def test_extract_table_with_trailing_units_note_finds_balance_sheet_and_cash_flow():
    page = _FakePage(TRAILING_UNITS_NOTE_FIXTURE)
    assert "Total current assets" in extract_table(page, BALANCE_SHEET_HINTS).get_text(" ")
    assert "Net cash from operations" in extract_table(page, CASH_FLOW_HINTS).get_text(" ")
