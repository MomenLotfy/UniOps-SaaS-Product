from __future__ import annotations
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import json
from app.core.redis_client import cache_set, cache_get, cache_delete
from app.utils.logger import logger

class IntelligenceCache:
    """
    Tiered cache for security intelligence data.
    L1: Local in-memory fallback (fastest).
    L2: Redis distributed cache (shared).
    """
    def __init__(self, default_ttl: int = 86400): # 24 hours
        self.default_ttl = default_ttl
        self._l1_cache: Dict[str, tuple[datetime, Any]] = {}

    def _get_key(self, intel_id: str) -> str:
        return f"intel:cache:{intel_id}"

    async def get(self, intel_id: str) -> Optional[Any]:
        """Retrieves item from L1 or L2 cache."""
        # 1. Check L1 (In-Memory)
        if intel_id in self._l1_cache:
            expiry, data = self._l1_cache[intel_id]
            if datetime.utcnow() < expiry:
                return data
            else:
                del self._l1_cache[intel_id]

        # 2. Check L2 (Redis)
        try:
            cached_val = await cache_get(self._get_key(intel_id))
            if cached_val:
                data = json.loads(cached_val)
                # Populate L1 for next time (shorter TTL for L1)
                self._l1_cache[intel_id] = (
                    datetime.utcnow() + timedelta(minutes=15),
                    data
                )
                return data
        except Exception as e:
            logger.error(f"[IntelligenceCache] Redis read failed: {e}")

        return None

    async def set(self, intel_id: str, data: Any, ttl: Optional[int] = None) -> None:
        """Stores item in both L1 and L2 cache."""
        actual_ttl = ttl or self.default_ttl

        # Update L1
        self._l1_cache[intel_id] = (
            datetime.utcnow() + timedelta(minutes=15),
            data
        )

        # Update L2 (Redis)
        try:
            await cache_set(
                self._get_key(intel_id),
                json.dumps(data),
                ex=actual_ttl
            )
        except Exception as e:
            logger.error(f"[IntelligenceCache] Redis write failed: {e}")

    async def invalidate(self, intel_id: str) -> None:
        """Removes item from all cache levels."""
        self._l1_cache.pop(intel_id, None)
        try:
            await redis_client.delete(self._get_key(intel_id))
        except Exception as e:
            logger.error(f"[IntelligenceCache] Redis delete failed: {e}")
