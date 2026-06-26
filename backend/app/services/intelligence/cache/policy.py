from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

class ExpirationType(str, Enum):
    ABSOLUTE = "absolute"
    SLIDING = "sliding"

class CachePolicy:
    """
    Defines the caching behavior for a specific type of intelligence data.
    """
    def __init__(
        self,
        ttl_seconds: int = 86400,
        expiration_type: ExpirationType = ExpirationType.ABSOLUTE,
        refresh_ahead_seconds: int = 3600,
        negative_cache_ttl: int = 300
    ):
        self.ttl_seconds = ttl_seconds
        self.expiration_type = expiration_type
        self.refresh_ahead_seconds = refresh_ahead_seconds
        self.negative_cache_ttl = negative_cache_ttl

class CachePolicyEngine:
    """
    Engine for evaluating cache expiration and refresh policies.
    """
    def __init__(self, default_policy: CachePolicy):
        self.default_policy = default_policy
        self.policies: Dict[str, CachePolicy] = {}

    def get_policy(self, key_type: str) -> CachePolicy:
        return self.policies.get(key_type, self.default_policy)

    def is_expired(self, created_at: datetime, last_accessed_at: datetime, policy: CachePolicy) -> bool:
        """
        Determines if a cache entry is expired based on its policy.
        """
        now = datetime.utcnow()

        if policy.expiration_type == ExpirationType.ABSOLUTE:
            return now > (created_at + timedelta(seconds=policy.ttl_seconds))

        if policy.expiration_type == ExpirationType.SLIDING:
            return now > (last_accessed_at + timedelta(seconds=policy.ttl_seconds))

        return False

    def should_refresh_ahead(self, created_at: datetime, policy: CachePolicy) -> bool:
        """
        Checks if the entry is within the 'refresh ahead' window.
        """
        now = datetime.utcnow()
        expiry = created_at + timedelta(seconds=policy.ttl_seconds)
        return now > (expiry - timedelta(seconds=policy.refresh_ahead_seconds))
