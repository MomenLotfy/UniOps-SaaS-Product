"""
In-process TTL cache for StrategyEvaluation results.

Production hint: caches the in-memory `StrategyEvaluationResult` for a
short TTL keyed by `(tenant_id, decision_id, context_hash)`.  Within the
TTL window repeated calls return the cached object — same deterministic
output, no recomputation.

Sprint 3 R37: TTL uses ``time.monotonic`` (immune to wall-clock jumps).
Sprint 3 R35: inherits from ``app.platform.base_cache.BaseCache`` for
the monotonic-clock + thread-safe store + explicit invalidation API.

Distributed readiness: the key/value shape is byte-stable for primitive
types, so a future Redis swap needs only a small adapter.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from app.platform.base_cache import BaseCache

from ..constants import STRATEGY_CACHE_TTL_SECONDS
from .strategy_interfaces import StrategyEvaluationResult


class DecisionStrategyCache(BaseCache["StrategyEvaluationResult"]):
    """
    Monotonic-clock TTL cache for strategy evaluation results.

    Public API is unchanged from the original implementation:
      ``get(tenant_id, decision_id, context)``
      ``put(tenant_id, decision_id, context, value)``
      ``invalidate(tenant_id)``
    plus three new explicit-invalidation methods inherited from
    ``BaseCache``: ``invalidate_prefix``, ``invalidate_all``, ``size``.
    """

    def __init__(self, ttl_seconds: int = STRATEGY_CACHE_TTL_SECONDS) -> None:
        super().__init__(ttl_seconds=ttl_seconds)
        # Use a string key for tenant-scoping (decision_id may collide
        # across tenants in pathological cases; the cache key keeps
        # them isolated).
        self._store: Dict[str, Tuple[float, StrategyEvaluationResult]] = {}

    @staticmethod
    def _key(tenant_id: str, decision_id: str, context: Any) -> str:
        ctx_hash = ""
        if context is not None:
            raw = getattr(context, "raw_data", None) or context
            try:
                ctx_hash = hashlib.sha256(
                    json.dumps(raw, sort_keys=True, default=str).encode()
                ).hexdigest()
            except Exception:  # pragma: no cover
                ctx_hash = "unhashable"
        return f"{tenant_id}:{decision_id}:{ctx_hash}"

    def get(self, tenant_id: str, decision_id: str, context: Any) -> Optional[StrategyEvaluationResult]:
        from app.observability.metrics import observe_cache_hit, observe_cache_miss

        key = self._key(tenant_id, decision_id, context)
        entry = self._store.get(key)
        if entry is None:
            observe_cache_miss(cache="strategy")
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            observe_cache_miss(cache="strategy")
            return None
        observe_cache_hit(cache="strategy")
        return value

    def put(self, tenant_id: str, decision_id: str, context: Any,
            value: StrategyEvaluationResult) -> None:
        self._store[self._key(tenant_id, decision_id, context)] = (
            time.monotonic() + self._ttl,
            value,
        )

    def invalidate(self, tenant_id: Optional[str] = None) -> int:
        """Backward-compatible invalidation.  Returns the count removed."""
        if tenant_id is None:
            return self.invalidate_all()
        # The cache key is a string ``{tenant}:{decision}:{ctx_hash}``;
        # match by string prefix.
        prefix = f"{tenant_id}:"
        with self._lock:
            keys = [k for k in self._store if isinstance(k, str) and k.startswith(prefix)]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)
