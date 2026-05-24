"""
Thin Redis caching helpers — used by Cost endpoints.

Usage:
    data = await cost_cache_get(tenant_id, "summary")
    if data is None:
        data = expensive_query()
        await cost_cache_set(tenant_id, "summary", data)
    return data
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Key schema: uniops:cost:{tenant_id}:{resource}
_PREFIX = "uniops:cost"
_DEFAULT_TTL = 300          # 5 min default
_SUMMARY_TTL  = 300         # 5 min
_BREAKDOWN_TTL = 300        # 5 min
_FORECAST_TTL  = 600        # 10 min (slower-changing)


def _key(tenant_id: str, resource: str) -> str:
    return f"{_PREFIX}:{tenant_id}:{resource}"


async def cost_cache_get(tenant_id: str, resource: str) -> Any | None:
    """Return parsed JSON from cache, or None on miss / Redis error."""
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        raw = await redis.get(_key(tenant_id, resource))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug(f"[cache] GET miss/error ({resource}): {exc}")
        return None


async def cost_cache_set(
    tenant_id: str,
    resource: str,
    data: Any,
    ttl: int | None = None,
) -> None:
    """Serialize data to JSON and store in Redis. Silently no-ops on error."""
    if ttl is None:
        ttl_map = {
            "summary":   _SUMMARY_TTL,
            "breakdown": _BREAKDOWN_TTL,
            "forecast":  _FORECAST_TTL,
        }
        ttl = ttl_map.get(resource, _DEFAULT_TTL)
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.set(_key(tenant_id, resource), json.dumps(data, default=str), ex=ttl)
    except Exception as exc:
        logger.debug(f"[cache] SET error ({resource}): {exc}")


async def cost_cache_invalidate(tenant_id: str) -> None:
    """Bust all cost cache keys for a tenant (call after cost sync)."""
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        pattern = f"{_PREFIX}:{tenant_id}:*"
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
        logger.debug(f"[cache] Invalidated cost cache for tenant {tenant_id}")
    except Exception as exc:
        logger.debug(f"[cache] Invalidate error: {exc}")
