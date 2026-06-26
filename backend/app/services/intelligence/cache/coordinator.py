from __future__ import annotations
from typing import Any, Optional, Dict, List
from datetime import datetime
import json
from app.core.redis_client import cache_get, cache_set, cache_delete
from app.services.intelligence.cache.policy import CachePolicy, CachePolicyEngine, ExpirationType
from app.utils.logger import logger

class CacheCoordinator:
    """
    Coordinates the movement of data between L1 (Memory), L2 (Redis), and L3 (Database).
    """
    def __init__(self, db_session: Any):
        self.db = db_session
        self._l1_cache: Dict[str, Any] = {} # Simple in-memory store

    async def get(self, key: str) -> Optional[Any]:
        # 1. Try L1
        if key in self._l1_cache:
            logger.debug(f"[CacheCoordinator] L1 Hit: {key}")
            return self._l1_cache[key]

        # 2. Try L2 (Redis)
        try:
            val = await cache_get(key)
            if val:
                logger.debug(f"[CacheCoordinator] L2 Hit: {key}")
                data = json.loads(val)
                self._l1_cache[key] = data # Populate L1
                return data
        except Exception as e:
            logger.error(f"[CacheCoordinator] L2 Read Error: {e}")

        # 3. Try L3 (DB)
        # Implementation would query the IntelligenceCacheEntry table
        return None

    async def set(self, key: str, value: Any, ttl: int):
        # Populate L1
        self._l1_cache[key] = value

        # Populate L2
        try:
            await cache_set(key, json.dumps(value), ttl=ttl)
        except Exception as e:
            logger.error(f"[CacheCoordinator] L2 Write Error: {e}")

        # Populate L3 (DB) would happen here via a background task or direct call

    async def delete(self, key: str):
        self._l1_cache.pop(key, None)
        try:
            await cache_delete(key)
        except Exception as e:
            logger.error(f"[CacheCoordinator] L2 Delete Error: {e}")
