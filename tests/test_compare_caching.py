"""Integration test: POST /compare caches its response so a second call
with the same company_ids is served from Redis instead of recomputing.
"""

import fakeredis
import pytest

from src.core import cache as cache_module


@pytest.fixture(autouse=True)
def fake_redis_client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_module, "_client", fake)
    yield fake
    fake.flushall()


def test_compare_endpoint_caches_response(client, seeded_db, fake_redis_client):
    first = client.post("/compare", json={"company_ids": [1]})
    assert first.status_code == 200

    cache_key = "compare:1"
    assert fake_redis_client.get(cache_key) is not None  # populated by the first call

    second = client.post("/compare", json={"company_ids": [1]})
    assert second.status_code == 200
    assert second.json() == first.json()


def test_compare_cache_key_is_order_independent(client, seeded_db):
    comp2 = client.post("/companies", json={"ticker": "ACN", "name": "Accenture"}).json()

    a = client.post("/compare", json={"company_ids": [1, comp2["id"]]})
    b = client.post("/compare", json={"company_ids": [comp2["id"], 1]})

    assert a.status_code == 200 and b.status_code == 200
    assert a.json() == b.json()
