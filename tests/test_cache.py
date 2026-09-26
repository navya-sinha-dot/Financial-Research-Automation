"""Unit tests for the Redis cache-aside helper: round trip via fakeredis,
and graceful degradation when Redis is unreachable.
"""
import fakeredis
import pytest

from src.core import cache as cache_module
from src.core.cache import cache_get, cache_set


@pytest.fixture(autouse=True)
def fake_redis_client(monkeypatch):
    """Swap the real Redis client for an in-memory fake for every test here."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_module, "_client", fake)
    yield fake
    fake.flushall()


def test_cache_set_then_get_round_trip():
    cache_set("mykey", {"hello": "world", "n": 42}, ttl_seconds=30)
    assert cache_get("mykey") == {"hello": "world", "n": 42}


def test_cache_get_miss_returns_none():
    assert cache_get("does-not-exist") is None


def test_cache_respects_ttl_expiry(fake_redis_client):
    cache_set("expiring", {"a": 1}, ttl_seconds=1)
    assert cache_get("expiring") == {"a": 1}
    fake_redis_client.pexpire("expiring", 0)  # force immediate expiry
    assert cache_get("expiring") is None


def test_cache_get_degrades_gracefully_when_redis_is_down(monkeypatch):
    def boom():
        raise ConnectionError("redis is unreachable")

    monkeypatch.setattr(cache_module, "get_redis_client", boom)
    assert cache_get("anything") is None  # must not raise


def test_cache_set_degrades_gracefully_when_redis_is_down(monkeypatch):
    def boom():
        raise ConnectionError("redis is unreachable")

    monkeypatch.setattr(cache_module, "get_redis_client", boom)
    cache_set("anything", {"x": 1}, ttl_seconds=10)  # must not raise
