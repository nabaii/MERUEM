"""
Redis-backed proxy and browser session pool manager.
Nigerian mobile proxies (MTN, Airtel, Glo, 9mobile) with health tracking and LRU rotation.
"""

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Optional

import redis

from app.core.config import settings

log = logging.getLogger(__name__)

PROXY_POOL_KEY = "meruem:proxy_pool"
SESSION_POOL_KEY = "meruem:session_pool"


@dataclass
class ProxyEntry:
    id: str
    url: str            # e.g. socks5://user:pass@host:port or http://user:pass@host:port
    carrier: str        # mtn | airtel | glo | 9mobile | residential | datacenter
    proxy_type: str     # mobile | residential | datacenter
    country: str = "NG"
    last_used: float = 0.0
    failure_count: int = 0
    is_active: bool = True


@dataclass
class SessionEntry:
    id: str
    platform: str       # tiktok | linkedin | instagram | facebook | twitter
    cookies: str        # JSON-serialized cookie list from Playwright context.cookies()
    user_agent: str
    proxy_id: Optional[str] = None
    last_used: float = 0.0
    is_active: bool = True
    account_age_days: int = 0   # Estimated age for "identity durability" scoring


class ProxyPool:
    """
    Redis-backed proxy and browser session pool.
    Supports LRU rotation, failure tracking, per-carrier filtering, and session injection.
    """

    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    # ── Proxy management ─────────────────────────────────────────────────────

    def add_proxy(self, entry: ProxyEntry) -> None:
        """Add or update a proxy in the pool."""
        self._redis.hset(PROXY_POOL_KEY, entry.id, json.dumps(asdict(entry)))
        log.info("Proxy registered: %s (%s / %s)", entry.id, entry.carrier, entry.proxy_type)

    def add_proxy_from_url(
        self,
        url: str,
        carrier: str = "other",
        proxy_type: str = "mobile",
    ) -> ProxyEntry:
        """Convenience helper — generate an ID and register a proxy by URL."""
        entry = ProxyEntry(
            id=str(uuid.uuid4()),
            url=url,
            carrier=carrier,
            proxy_type=proxy_type,
        )
        self.add_proxy(entry)
        return entry

    def get_proxy(
        self,
        carrier: Optional[str] = None,
        proxy_type: Optional[str] = "mobile",
    ) -> Optional[ProxyEntry]:
        """
        Return the least-recently-used active proxy, optionally filtered by carrier/type.
        Falls back to any active proxy if the filtered pool is empty.
        Returns None if the pool is completely empty.
        """
        max_failures = settings.proxy_max_failures
        all_raw = self._redis.hvals(PROXY_POOL_KEY)
        if not all_raw:
            return None

        entries = [ProxyEntry(**json.loads(r)) for r in all_raw]

        def _is_healthy(e: ProxyEntry) -> bool:
            return e.is_active and e.failure_count < max_failures

        candidates = [
            e for e in entries
            if _is_healthy(e)
            and (carrier is None or e.carrier == carrier)
            and (proxy_type is None or e.proxy_type == proxy_type)
        ]

        if not candidates:
            # Relax filters and pick any healthy proxy
            candidates = [e for e in entries if _is_healthy(e)]

        if not candidates:
            log.warning("No active proxies available — scraping without proxy")
            return None

        chosen = min(candidates, key=lambda e: e.last_used)
        chosen.last_used = time.time()
        self._redis.hset(PROXY_POOL_KEY, chosen.id, json.dumps(asdict(chosen)))
        return chosen

    def mark_proxy_failed(self, proxy_id: str) -> None:
        """Increment failure count; deactivate proxy if threshold is reached."""
        raw = self._redis.hget(PROXY_POOL_KEY, proxy_id)
        if not raw:
            return
        entry = ProxyEntry(**json.loads(raw))
        entry.failure_count += 1
        if entry.failure_count >= settings.proxy_max_failures:
            entry.is_active = False
            log.warning("Proxy %s deactivated after %d failures", proxy_id, entry.failure_count)
        self._redis.hset(PROXY_POOL_KEY, proxy_id, json.dumps(asdict(entry)))

    def reset_proxy(self, proxy_id: str) -> None:
        """Reset failure count and reactivate a proxy (after maintenance/rotation)."""
        raw = self._redis.hget(PROXY_POOL_KEY, proxy_id)
        if not raw:
            return
        entry = ProxyEntry(**json.loads(raw))
        entry.failure_count = 0
        entry.is_active = True
        self._redis.hset(PROXY_POOL_KEY, proxy_id, json.dumps(asdict(entry)))
        log.info("Proxy %s reset and reactivated", proxy_id)

    def remove_proxy(self, proxy_id: str) -> None:
        self._redis.hdel(PROXY_POOL_KEY, proxy_id)

    def list_proxies(self) -> list[ProxyEntry]:
        return [ProxyEntry(**json.loads(r)) for r in self._redis.hvals(PROXY_POOL_KEY)]

    def pool_stats(self) -> dict:
        entries = self.list_proxies()
        by_carrier: dict[str, int] = {}
        for e in entries:
            if e.is_active:
                by_carrier[e.carrier] = by_carrier.get(e.carrier, 0) + 1
        return {
            "total": len(entries),
            "active": sum(1 for e in entries if e.is_active),
            "failed": sum(1 for e in entries if not e.is_active),
            "by_carrier": by_carrier,
        }

    # ── Session management ────────────────────────────────────────────────────

    def add_session(self, entry: SessionEntry) -> None:
        """Register a pre-authenticated browser session (cookies from a logged-in page)."""
        self._redis.hset(SESSION_POOL_KEY, entry.id, json.dumps(asdict(entry)))
        log.info("Session registered: %s (%s)", entry.id, entry.platform)

    def save_page_session(
        self,
        platform: str,
        cookies: list[dict],
        user_agent: str,
        proxy_id: Optional[str] = None,
        account_age_days: int = 0,
    ) -> SessionEntry:
        """Convenience helper — serialise and store cookies from a Playwright page."""
        entry = SessionEntry(
            id=str(uuid.uuid4()),
            platform=platform,
            cookies=json.dumps(cookies),
            user_agent=user_agent,
            proxy_id=proxy_id,
            account_age_days=account_age_days,
        )
        self.add_session(entry)
        return entry

    def get_session(self, platform: str) -> Optional[SessionEntry]:
        """Return the least-recently-used active session for the given platform."""
        all_raw = self._redis.hvals(SESSION_POOL_KEY)
        entries = [SessionEntry(**json.loads(r)) for r in all_raw]
        candidates = [e for e in entries if e.is_active and e.platform == platform]
        if not candidates:
            return None
        chosen = min(candidates, key=lambda e: e.last_used)
        chosen.last_used = time.time()
        self._redis.hset(SESSION_POOL_KEY, chosen.id, json.dumps(asdict(chosen)))
        return chosen

    def invalidate_session(self, session_id: str) -> None:
        """Mark a session as inactive (e.g., after a login challenge or CAPTCHA)."""
        raw = self._redis.hget(SESSION_POOL_KEY, session_id)
        if not raw:
            return
        entry = SessionEntry(**json.loads(raw))
        entry.is_active = False
        self._redis.hset(SESSION_POOL_KEY, session_id, json.dumps(asdict(entry)))
        log.warning("Session %s invalidated (login challenge or ban)", session_id)

    def list_sessions(self, platform: Optional[str] = None) -> list[SessionEntry]:
        all_raw = self._redis.hvals(SESSION_POOL_KEY)
        entries = [SessionEntry(**json.loads(r)) for r in all_raw]
        if platform:
            return [e for e in entries if e.platform == platform]
        return entries

    def session_stats(self) -> dict:
        entries = self.list_sessions()
        by_platform: dict[str, int] = {}
        for e in entries:
            if e.is_active:
                by_platform[e.platform] = by_platform.get(e.platform, 0) + 1
        return {
            "total": len(entries),
            "active": sum(1 for e in entries if e.is_active),
            "by_platform": by_platform,
        }


# Module-level singleton shared across all collectors in the same process
proxy_pool = ProxyPool()
