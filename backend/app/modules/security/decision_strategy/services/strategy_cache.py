"""
In-process TTL cache for StrategyEvaluation results.

Production hint: caches the in-memory `StrategyEvaluationResult` for a
short TTL keyed by `(tenant_id, decision_id, context_hash)`.  Within the
TTL window repeated calls return the cached object — same deterministic
output, no recomputation.

This is an optimisation layer — never load-bearing for correctness.
The pipeline runs identically with the cache disabled.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from ..constants import STRATEGY_CACHE_TTL_SECONDS
from .strategy_interfaces import StrategyEvaluationResult


class DecisionStrategyCache:
    """
    Simple TTL cache.  Thread-safe enough for asyncio (single-thread).
    For multi-process deployments, swap with Redis — the interface is
    intentionally narrow.
    """

    def __init__(self, ttl_seconds: int = STRATEGY_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
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
        key = self._key(tenant_id, decision_id, context)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def put(self, tenant_id: str, decision_id: str, context: Any,
            value: StrategyEvaluationResult) -> None:
        key = self._key(tenant_id, decision_id, context)
        self._store[key] = (time.time() + self._ttl, value)

    def invalidate(self, tenant_id: Optional[str] = None) -> int:
        if tenant_id is None:
            n = len(self._store)
            self._store.clear()
            return n
        prefix = f"{tenant_id}:"
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)
        return len(keys)
