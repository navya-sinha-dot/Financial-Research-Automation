"""Regression test for a real bug found on a live scrape: the dashboard's KPI
cards and analytics/metrics.py's ratio math both read fixed keys like
items["revenue"] and items["net_income"], but a real SEC filing never uses
those exact words -- Apple's own 10-Q labels are "Total net sales", "Net
income", "Total shareholders' equity", etc. Every existing ingestion test
built its own fixture data using the canonical keys directly, so none of
them caught that the real scraper output never matched what the dashboard
was reading -- that's exactly how this bug shipped unnoticed.
"""

from src.ingestion.normalizer import derive_canonical_line_items


def test_derives_revenue_from_total_net_sales_not_from_sub_line_items():
    items = {
        "Products": 194116.0,
        "Services": 26844.0,
        "Total net sales": 416161.0,
        "Total cost of sales": 220960.0,
        "Gross margin": 195201.0,
    }
    canonical = derive_canonical_line_items(items)
    assert canonical["revenue"] == 416161.0


def test_derives_net_income_and_skips_per_share_rows():
    items = {
        "Net income": 25000.0,
        "Net income per share Basic": 1.5,
        "Net income per share Diluted": 1.49,
    }
    canonical = derive_canonical_line_items(items)
    assert canonical["net_income"] == 25000.0


def test_derives_operating_income():
    items = {"Operating income": 30000.0, "Other income": 500.0}
    canonical = derive_canonical_line_items(items)
    assert canonical["operating_income"] == 30000.0


def test_derives_total_equity_handles_curly_apostrophe():
    items = {"Total shareholders’ equity": 62000.0}
    canonical = derive_canonical_line_items(items)
    assert canonical["total_equity"] == 62000.0


def test_derives_current_assets_and_current_liabilities():
    items = {
        "Total current assets": 152000.0,
        "Total current liabilities": 133000.0,
        "Total assets": 365000.0,
        "Total liabilities": 290000.0,
    }
    canonical = derive_canonical_line_items(items)
    assert canonical["current_assets"] == 152000.0
    assert canonical["current_liabilities"] == 133000.0


def test_ignores_none_values_and_missing_metrics():
    items = {"Some unrelated label": None}
    canonical = derive_canonical_line_items(items)
    assert canonical == {}


def test_falls_back_to_plain_revenue_label_when_no_total_variant_present():
    items = {"Revenue": 94036.0, "Cost of revenue": 40000.0}
    canonical = derive_canonical_line_items(items)
    assert canonical["revenue"] == 94036.0
