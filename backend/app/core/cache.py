"""
Redis-backed cache utility.

Usage:
    from app.core.cache import cache

    data = cache.get("my_key")
    if data is None:
        data = expensive_query()
        cache.set("my_key", data, ttl=120)

    cache.delete("my_key")
    cache.delete_prefix("stats:")
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.core.config import settings

log = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


class Cache:
    def get(self, key: str) -> Any | None:
        try:
            raw = _get_client().get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            log.warning("Cache GET error for '%s': %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        try:
            _get_client().setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            log.warning("Cache SET error for '%s': %s", key, exc)

    def delete(self, key: str) -> None:
        try:
            _get_client().delete(key)
        except Exception as exc:
            log.warning("Cache DELETE error for '%s': %s", key, exc)

    def delete_prefix(self, prefix: str) -> None:
        """Delete all keys matching `prefix*`. Uses SCAN — safe for production."""
        try:
            client = _get_client()
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            log.warning("Cache DELETE_PREFIX error for '%s': %s", prefix, exc)


cache = Cache()
