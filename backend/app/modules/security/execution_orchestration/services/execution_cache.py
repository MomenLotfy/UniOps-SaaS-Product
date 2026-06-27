"""
Execution Evaluation Cache.

TTL-keyed cache: tenant_id + decision_id + context-hash → result.
Mirrors `DecisionStrategyCache` / `ApprovalCache`.
"""
from __future__ import annotations

import hashlib
import json
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

    def _key(self, tenant_id: str, decision_id: str, context: Any) -> Tuple[str, str, str]:
        return (tenant_id, decision_id, _hash_context(context))

    def get(self, tenant_id: str, decision_id: str, context: Any) -> Optional[ExecutionEvaluationResult]:
        key = self._key(tenant_id, decision_id, context)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    def put(self, tenant_id: str, decision_id: str, context: Any,
            value: ExecutionEvaluationResult) -> None:
        self._store[self._key(tenant_id, decision_id, context)] = (
            time.monotonic() + self._ttl,
            value,
        )

    def invalidate(self, tenant_id: Optional[str] = None) -> None:
        if tenant_id is None:
            self._store.clear()
            return
        for key in list(self._store.keys()):
            if key[0] == tenant_id:
                self._store.pop(key, None)


__all__ = ["ExecutionCache"]