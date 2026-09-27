"""Thin Redis cache-aside helper with graceful degradation.

If Redis is unreachable (not running locally, connection refused, timeout),
every call here logs at debug level and falls through as a cache miss --
callers never need to special-case "cache is down". This is a simple
TTL-based cache-aside, not invalidation-based: cached peer-comparison
results can be up to CACHE_TTL_SECONDS stale, which is an acceptable
trade-off for data that only changes when someone re-ingests a company.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from src.core.config import settings
from src.core.metrics import CACHE_HITS_TOTAL, CACHE_MISSES_TOTAL

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            decode_responses=True,
        )
    return _client


def cache_get(key: str, *, cache_type: str = "generic") -> Any | None:
    try:
        raw = get_redis_client().get(key)
    except Exception as exc:
        logger.debug("Cache unavailable, treating %s as a miss: %s", key, exc)
        return None

    if raw is None:
        CACHE_MISSES_TOTAL.labels(cache_type=cache_type).inc()
        return None

    CACHE_HITS_TOTAL.labels(cache_type=cache_type).inc()
    return json.loads(raw)


def cache_set(key: str, value: Any, ttl_seconds: int, *, cache_type: str = "generic") -> None:
    try:
        get_redis_client().set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as exc:
        logger.debug("Cache unavailable, skipping set for %s (%s): %s", key, cache_type, exc)
