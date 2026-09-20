from pathlib import Path

from src.ingestion.normalizer import normalize_financial_value
from src.ingestion.parser import parse_financial_statements


def test_normalize_financial_value_handles_negative_and_units():
    assert normalize_financial_value("$(2,345)") == -2345.0
    assert normalize_financial_value("$94,036") == 94036.0
    assert normalize_financial_value("$2.5 billion") == 2500000000.0
    assert normalize_financial_value("94,036 million") == 94036000000.0


def test_parse_financial_statements_extracts_expected_rows():
    html = Path("tests/fixtures/sec_filing_mock.html").read_text(encoding="utf-8")
    statements = parse_financial_statements(html)

    assert "income_statement" in statements
    assert "balance_sheet" in statements
    assert "cash_flow" in statements
    assert statements["income_statement"]["Revenue"] == 94036.0
    assert statements["income_statement"]["Net Income"] == -2345.0
    assert statements["balance_sheet"]["Total Assets"] == 365000.0
    assert statements["cash_flow"]["Operating Cash Flow"] == 60000.0
