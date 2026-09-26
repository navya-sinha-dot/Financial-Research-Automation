"""Unit tests for scraping stealth helpers that don't require launching a real browser."""
from src.ingestion.browser import human_delay


def test_human_delay_respects_configured_bounds(monkeypatch):
    captured = {}

    def fake_sleep(seconds):
        captured["seconds"] = seconds

    monkeypatch.setattr("src.ingestion.browser.time.sleep", fake_sleep)

    human_delay(min_ms=100, max_ms=200)

    assert "seconds" in captured
    assert 0.1 <= captured["seconds"] <= 0.2


def test_human_delay_is_noop_when_max_is_zero(monkeypatch):
    called = {"count": 0}

    def fake_sleep(seconds):
        called["count"] += 1

    monkeypatch.setattr("src.ingestion.browser.time.sleep", fake_sleep)

    human_delay(min_ms=0, max_ms=0)

    assert called["count"] == 0
