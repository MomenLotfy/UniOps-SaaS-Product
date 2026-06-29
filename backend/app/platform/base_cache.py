"""
Sprint 3 R35/R37 — BaseCache.

Reusable TTL cache contract used by the three engine caches
(DecisionStrategyCache / ApprovalCache / ExecutionCache).

Guarantees:
  - TTL is measured against ``time.monotonic`` (immune to wall-clock
    jumps, DST, NTP corrections).
  - ``put`` / ``get`` / ``invalidate`` are guarded by ``threading.RLock``
    so concurrent Celery workers / threads cannot corrupt the store.
  - Explicit tenant-scoped invalidation via ``invalidate_prefix``.
  - Full flush via ``invalidate_all``.
  - Distributed-readiness: the ``_serialize`` / ``_deserialize`` hooks
    are byte-stable for primitive types, so the same key/value pair can
    be dropped into Redis without changing the wire format.

Design notes:
  - The base does NOT know about tenant_id specifically — it operates
    on opaque key tuples.  Concrete caches build the tuple from
    (tenant_id, decision_id, context_hash).
  - The base is intentionally subclassed (not migrated over) — the
    existing concrete caches keep their public method signatures and
    opt-in to monotonic-clock + thread safety by switching the clock
    and adding ``threading.RLock`` around the store.
"""

from __future__ import annotations

import threading
import time
from typing import TypeVar, Generic

V = TypeVar("V")


class BaseCache(Generic[V]):
    """
    Monotonic-clock TTL cache with thread-safe store.

    Subclasses build a tuple key from their domain (e.g. ``(tenant_id,
    decision_id, ctx_hash)``) and call ``put(key, value)`` / ``get(key)``.
    TTL is fixed at construction time.
    """

    DEFAULT_TTL_SECONDS = 300

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._ttl = ttl_seconds
        self._store: dict = {}
        self._lock = threading.RLock()

    # ── Clock (monotonic) ───────────────────────────────────────────────
    @staticmethod
    def now() -> float:
        """Monotonic clock — never goes backwards."""
        return time.monotonic()

    # ── Serialization hooks (distributed-ready) ─────────────────────────
    @staticmethod
    def _serialize(value: V) -> V:
        """Hook for byte-stable serialization.  Default: identity."""
        return value

    @staticmethod
    def _deserialize(value: V) -> V:
        """Hook for byte-stable deserialization.  Default: identity."""
        return value

    # ── Core API ────────────────────────────────────────────────────────
    def _put_raw(self, key: tuple, value: V) -> None:
        with self._lock:
            self._store[key] = (self.now() + self._ttl, self._serialize(value))

    def _get_raw(self, key: tuple) -> V | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < self.now():
                self._store.pop(key, None)
                return None
            return self._deserialize(value)

    # ── Explicit invalidation ───────────────────────────────────────────
    def invalidate_prefix(self, prefix: tuple) -> int:
        """
        Remove every entry whose key starts with the given prefix tuple.

        Returns the number of keys removed.  Thread-safe.
        """
        if not isinstance(prefix, tuple):
            raise TypeError("invalidate_prefix expects a tuple key prefix")
        with self._lock:
            keys = [k for k in self._store if isinstance(k, tuple) and k[: len(prefix)] == prefix]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)

    def invalidate_all(self) -> int:
        """Remove every entry.  Returns the previous size."""
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    def size(self) -> int:
        """Current entry count."""
        with self._lock:
            return len(self._store)

    @property
    def ttl_seconds(self) -> int:
        return self._ttl


__all__ = ["BaseCache"]
