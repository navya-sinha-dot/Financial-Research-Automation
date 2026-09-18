"""Unit tests for the Analytics layer with known input/output pairs.

Validates:
- Growth rate calculations (YoY and QoQ)
- Profitability and solvency ratios (Net Margin, ROE, Current Ratio)
- Edge case handling (zero denominators, negative inputs, null values)
- Peer percentile ranking
"""
import pytest
from src.analytics.metrics import (
    compute_growth,
    compute_net_margin,
    compute_roe,
    compute_current_ratio,
    compute_period_ratios,
    compute_peer_percentiles,
)


def test_compute_growth_known_values():
    # 10% positive growth
    assert pytest.approx(compute_growth(110.0, 100.0), rel=1e-4) == 0.10
    # 15% negative growth
    assert pytest.approx(compute_growth(85.0, 100.0), rel=1e-4) == -0.15
    # Flat growth
    assert pytest.approx(compute_growth(50.0, 50.0), rel=1e-4) == 0.0
    # Negative base growth: from -50 to -40 is an increase of 10 / 50 = +0.20
    assert pytest.approx(compute_growth(-40.0, -50.0), rel=1e-4) == 0.20


def test_compute_growth_edge_cases():
    assert compute_growth(100.0, 0.0) is None
    assert compute_growth(None, 100.0) is None
    assert compute_growth(100.0, None) is None
    assert compute_growth(None, None) is None


def test_compute_net_margin():
    # 25% net profit margin
    assert pytest.approx(compute_net_margin(25.0, 100.0), rel=1e-4) == 0.25
    # Negative net profit margin
    assert pytest.approx(compute_net_margin(-15.0, 150.0), rel=1e-4) == -0.10
    # Zero or negative revenue
    assert compute_net_margin(20.0, 0.0) is None
    assert compute_net_margin(20.0, -100.0) is None
    assert compute_net_margin(None, 100.0) is None


def test_compute_roe():
    # 20% Return on Equity
    assert pytest.approx(compute_roe(200.0, 1000.0), rel=1e-4) == 0.20
    # Zero or negative equity
    assert compute_roe(100.0, 0.0) is None
    assert compute_roe(100.0, -500.0) is None
    assert compute_roe(None, 1000.0) is None


def test_compute_current_ratio():
    # Healthy liquidity ratio 2.5
    assert pytest.approx(compute_current_ratio(250.0, 100.0), rel=1e-4) == 2.50
    # Zero or negative liabilities
    assert compute_current_ratio(100.0, 0.0) is None
    assert compute_current_ratio(100.0, -20.0) is None
    assert compute_current_ratio(None, 50.0) is None


def test_compute_period_ratios_series():
    # Setup 5 quarters of data
    periods = [
        {
            "period_type": "Q1",
            "fiscal_year": 2023,
            "report_date": "2023-03-31",
            "items": {
                "revenue": 1000.0,
                "net_income": 200.0,
                "total_equity": 2000.0,
                "current_assets": 1500.0,
                "current_liabilities": 600.0,
            },
        },
        {
            "period_type": "Q2",
            "fiscal_year": 2023,
            "report_date": "2023-06-30",
            "items": {
                "revenue": 1100.0,
                "net_income": 220.0,
                "total_equity": 2100.0,
                "current_assets": 1600.0,
                "current_liabilities": 640.0,
            },
        },
        {
            "period_type": "Q3",
            "fiscal_year": 2023,
            "report_date": "2023-09-30",
            "items": {
                "revenue": 1150.0,
                "net_income": 240.0,
                "total_equity": 2200.0,
                "current_assets": 1700.0,
                "current_liabilities": 680.0,
            },
        },
        {
            "period_type": "Q4",
            "fiscal_year": 2023,
            "report_date": "2023-12-31",
            "items": {
                "revenue": 1200.0,
                "net_income": 260.0,
                "total_equity": 2300.0,
                "current_assets": 1800.0,
                "current_liabilities": 700.0,
            },
        },
        {
            "period_type": "Q1",
            "fiscal_year": 2024,
            "report_date": "2024-03-31",
            "items": {
                "revenue": 1250.0,
                "net_income": 275.0,
                "total_equity": 2400.0,
                "current_assets": 1900.0,
                "current_liabilities": 750.0,
            },
        },
    ]

    results = compute_period_ratios(periods)
    assert len(results) == 5

    # First quarter has no QoQ or YoY growth
    q1_ratios = results[0]["computed_ratios"]
    assert q1_ratios["qoq_growth"] is None
    assert q1_ratios["yoy_growth"] is None
    assert pytest.approx(q1_ratios["net_margin"], rel=1e-4) == 0.20
    assert pytest.approx(q1_ratios["roe"], rel=1e-4) == 0.10
    assert pytest.approx(q1_ratios["current_ratio"], rel=1e-4) == 2.50

    # Second quarter has QoQ: (1100 - 1000) / 1000 = 0.10
    q2_ratios = results[1]["computed_ratios"]
    assert pytest.approx(q2_ratios["qoq_growth"], rel=1e-4) == 0.10

    # Fifth quarter (Q1 2024) has YoY: (1250 - 1000) / 1000 = 0.25 (25%)
    q5_ratios = results[4]["computed_ratios"]
    assert pytest.approx(q5_ratios["yoy_growth"], rel=1e-4) == 0.25
    assert pytest.approx(q5_ratios["net_margin"], rel=1e-4) == 275.0 / 1250.0


def test_compute_peer_percentiles():
    companies = [
        {"company_id": 1, "ticker": "AAA", "net_margin": 0.10, "roe": 0.15},
        {"company_id": 2, "ticker": "BBB", "net_margin": 0.20, "roe": 0.25},
        {"company_id": 3, "ticker": "CCC", "net_margin": 0.30, "roe": 0.35},
    ]

    results = compute_peer_percentiles(companies, metric_keys=["net_margin", "roe"])
    assert len(results) == 3

    # Company 1 should have lowest percentile rank (~33.3%)
    assert results[0]["percentile_rankings"]["net_margin"] < results[1]["percentile_rankings"]["net_margin"]
    # Company 3 should have highest rank (100.0%)
    assert results[2]["percentile_rankings"]["net_margin"] == 100.0
    assert results[2]["percentile_rankings"]["roe"] == 100.0
