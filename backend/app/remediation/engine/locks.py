from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Set
import asyncio
import time
from app.utils.logger import logger

class ILockProvider(ABC):
    """
    Abstraction for distributed locking.
    Allows switching between In-Memory, Redis, or ZooKeeper locks.
    """
    @abstractmethod
    async def acquire(self, lock_id: str, ttl_seconds: int = 60) -> bool:
        """Acquires a lock for the given ID. Returns True if successful."""
        pass

    @abstractmethod
    async def release(self, lock_id: str) -> None:
        """Releases the lock."""
        pass

    @abstractmethod
    async def is_locked(self, lock_id: str) -> bool:
        """Checks if a lock is currently held."""
        pass

class InMemoryLockProvider(ILockProvider):
    """
    Single-process lock provider.
    Suitable for development or single-node deployments.
    """
    def __init__(self):
        self._locks: Dict[str, float] = {} # lock_id -> expiration_timestamp
        self._lock = asyncio.Lock()

    async def acquire(self, lock_id: str, ttl_seconds: int = 60) -> bool:
        async with self._lock:
            now = time.time()
            if lock_id in self._locks and self._locks[lock_id] > now:
                return False

            self._locks[lock_id] = now + ttl_seconds
            return True

    async def release(self, lock_id: str) -> None:
        async with self._lock:
            self._locks.pop(lock_id, None)

    async def is_locked(self, lock_id: str) -> bool:
        async with self._lock:
            now = time.time()
            return lock_id in self._locks and self._locks[lock_id] > now

class LockManager:
    """
    Coordinates various types of locks to prevent concurrent remediations.
    Supports Repository-level, Finding-level, and Tenant-level locks.
    """
    def __init__(self, provider: ILockProvider):
        self.provider = provider

    async def acquire_execution_locks(self, tenant_id: str, repo_id: str, finding_id: str) -> List[str]:
        """
        Acquires all necessary locks for a specific remediation execution.
        Returns a list of acquired lock IDs if successful, otherwise raises an exception.
        """
        locks = [
            f"lock:tenant:{tenant_id}",
            f"lock:repo:{repo_id}",
            f"lock:finding:{finding_id}"
        ]

        acquired = []
        try:
            for lock_id in locks:
                if await self.provider.acquire(lock_id):
                    acquired.append(lock_id)
                else:
                    raise Exception(f"Resource locked: {lock_id}")
        except Exception as e:
            # Release all acquired locks on failure (atomic)
            for lock_id in acquired:
                await self.provider.release(lock_id)
            raise e

        return acquired

    async def release_execution_locks(self, lock_ids: List[str]) -> None:
        """Releases a set of acquired locks."""
        for lock_id in lock_ids:
            await self.provider.release(lock_id)
