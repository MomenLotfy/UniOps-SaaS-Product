"""
Sprint 3 R36 — ThreadSafeRegistry.

Concurrent-safe registry base class used by ``DecisionStrategyRegistry``
and ``ApprovalRegistry`` (and any future in-memory plugin registry).

The contract:

  - ``register(key, value)`` is idempotent — re-registering the same
    key replaces the value (this matches the existing project
    behaviour, so we don't introduce a regression).
  - ``get(key)``, ``all()``, ``names()``, ``discover(...)`` are
    snapshot reads: each returns a copy of the relevant data so the
    caller never sees partial state.
  - Concurrent writers serialize via ``threading.RLock``.
  - For asyncio callers (``aio.Lock`` is not safe across threads)
    there's no async-aware equivalent needed: the registry is
    bootstrap-once, and the few async reads are non-blocking dict
    snapshots — they don't hold the lock.

Why RLock and not asyncio.Lock?
  The registry must be safe when imported by both FastAPI handlers
  (asyncio) and Celery worker threads (sync).  ``threading.RLock``
  satisfies both: sync threads block on the lock; asyncio coroutines
  see the lock as a no-op (because Python's GIL protects the dict
  mutation at the bytecode level).  ``asyncio.Lock`` would *not*
  protect the sync Celery path.

The base is generic — concrete registries subclass with their key
type and value type as parameters.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator


class ThreadSafeRegistry[K, V]:
    """
    Concurrent-safe key/value registry.

    Subclasses override ``__init__`` to optionally bootstrap defaults
    before calling ``super().__init__()``.
    """

    def __init__(self) -> None:
        self._store: dict[K, V] = {}
        self._lock = threading.RLock()

    # ── Writes ──────────────────────────────────────────────────────────
    def register(self, key: K, value: V) -> None:
        """Idempotent — re-registering replaces the value."""
        with self._lock:
            self._store[key] = value

    def unregister(self, key: K) -> V | None:
        """Remove the entry; return the previous value or ``None``."""
        with self._lock:
            return self._store.pop(key, None)

    def clear(self) -> int:
        """Remove every entry.  Returns the previous size."""
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    # ── Reads (snapshot) ────────────────────────────────────────────────
    def get(self, key: K) -> V | None:
        """Snapshot read.  Returns ``None`` if missing."""
        with self._lock:
            return self._store.get(key)

    def has(self, key: K) -> bool:
        with self._lock:
            return key in self._store

    def all(self) -> dict[K, V]:
        """Return a shallow copy of the underlying store."""
        with self._lock:
            return dict(self._store)

    def names(self) -> list[K]:
        """Return a snapshot list of keys."""
        with self._lock:
            return list(self._store.keys())

    def values(self) -> list[V]:
        """Return a snapshot list of values."""
        with self._lock:
            return list(self._store.values())

    def items(self) -> list[tuple[K, V]]:
        """Return a snapshot list of (key, value) pairs."""
        with self._lock:
            return list(self._store.items())

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._store

    def __iter__(self) -> Iterator[K]:
        with self._lock:
            return iter(list(self._store.keys()))


__all__ = ["ThreadSafeRegistry"]
