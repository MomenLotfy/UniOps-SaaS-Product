"""
Execution Evaluation Cache.

TTL-keyed cache: tenant_id + decision_id + context-hash → result.
Mirrors `DecisionStrategyCache` / `ApprovalCache`.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional, Tuple

from ..constants import EXECUTION_CACHE_TTL_SECONDS
from .execution_interfaces import (
    ExecutionEvaluationResult,
    IExecutionCache,
)


def _hash_context(context: Any) -> str:
    raw = getattr(context, "raw_data", None) or getattr(context, "__dict__", {})
    try:
        payload = json.dumps(raw, sort_keys=True, default=str)
    except TypeError:
        payload = repr(raw)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ExecutionCache(IExecutionCache):
    """In-memory TTL cache.  Not safe for multi-process deployments."""

    def __init__(self, ttl_seconds: int = EXECUTION_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: Dict[Tuple[str, str, str], Tuple[float, ExecutionEvaluationResult]] = {}
        self._lock = threading.RLock()

    def _key(self, tenant_id: str, decision_id: str, context: Any) -> Tuple[str, str, str]:
        return (tenant_id, decision_id, _hash_context(context))

    def get(self, tenant_id: str, decision_id: str, context: Any) -> Optional[ExecutionEvaluationResult]:
        from app.observability.metrics import observe_cache_hit, observe_cache_miss

        key = self._key(tenant_id, decision_id, context)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                observe_cache_miss(cache="execution")
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                observe_cache_miss(cache="execution")
                return None
            observe_cache_hit(cache="execution")
            return value

    def put(self, tenant_id: str, decision_id: str, context: Any,
            value: ExecutionEvaluationResult) -> None:
        with self._lock:
            self._store[self._key(tenant_id, decision_id, context)] = (
                time.monotonic() + self._ttl,
                value,
            )

    def invalidate(self, tenant_id: Optional[str] = None) -> int:
        """Backward-compatible.  Returns the number of entries removed."""
        with self._lock:
            if tenant_id is None:
                n = len(self._store)
                self._store.clear()
                return n
            keys = [k for k in self._store if k[0] == tenant_id]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)


__all__ = ["ExecutionCache"]