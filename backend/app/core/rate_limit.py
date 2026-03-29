"""
Per-client API rate limiting using slowapi + Redis storage.

Limits are applied per authenticated account (by account ID extracted from
the Bearer token) or per IP address for unauthenticated requests.
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

log = logging.getLogger(__name__)


def _client_key(request: Request) -> str:
    """
    Rate-limit key: account ID (JWT sub) > API key hash > IP.
    Degrades gracefully if token parsing fails.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            sub = payload.get("sub")
            if sub:
                return f"account:{sub}"
        except Exception:
            pass
        # API key path — hash the key so it's safe to use as a Redis key
        return f"apikey:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.redis_url,
    default_limits=[settings.rate_limit_default] if settings.rate_limit_enabled else [],
)
