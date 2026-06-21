from __future__ import annotations
"""
Kubernetes Client Factory — Epic 9 Multi-Cluster Isolation.

Responsibilities:
  - Load kubeconfig per cluster from the DB (decrypted at runtime)
  - Cache live clients per cluster_id (LRU-style, 5-minute TTL)
  - Enforce tenant_id + cluster_id isolation
  - Reject requests when cluster does not belong to the requesting tenant

Usage:
    factory = KubernetesClientFactory()
    client = await factory.get_client(cluster_id, tenant_id, db)
    # client is a KubernetesClient or None
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Cache TTL in seconds
_CACHE_TTL = 300


class _CacheEntry:
    def __init__(self, client, expires_at: float):
        self.client     = client
        self.expires_at = expires_at

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


class KubernetesClientFactory:
    """
    Thread-safe, per-cluster Kubernetes client factory with TTL cache.

    The cache avoids re-decrypting kubeconfig on every request while
    ensuring credential rotations propagate within the TTL window.
    """

    def __init__(self):
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get_client(
        self,
        cluster_id: str,
        tenant_id: str,
        db=None,
    ):
        """
        Return a KubernetesClient for (cluster_id, tenant_id).

        - Enforces tenant isolation (raises PermissionError on mismatch)
        - Returns None if cluster has no kubeconfig / not reachable
        - db session is optional; when None, creates a short-lived session
        """
        async with self._lock:
            cache_key = f"{tenant_id}:{cluster_id}"
            entry     = self._cache.get(cache_key)
            if entry and not entry.expired:
                return entry.client

        client = await self._build_client(cluster_id, tenant_id, db)

        async with self._lock:
            self._cache[cache_key] = _CacheEntry(
                client,
                time.monotonic() + _CACHE_TTL,
            )

        return client

    async def _build_client(
        self,
        cluster_id: str,
        tenant_id: str,
        db=None,
    ):
        """Load the cluster record and build a KubernetesClient."""
        cluster = await self._load_cluster(cluster_id, db)
        if not cluster:
            logger.warning(f"[client_factory] cluster {cluster_id} not found")
            return None

        # ── Tenant isolation enforcement ──────────────────────────────────────
        if str(cluster.tenant_id) != str(tenant_id):
            logger.error(
                f"[client_factory] SECURITY: tenant {tenant_id} attempted to "
                f"access cluster {cluster_id} owned by {cluster.tenant_id}"
            )
            raise PermissionError(
                f"Cluster {cluster_id} does not belong to tenant {tenant_id}"
            )

        # ── Decode kubeconfig ─────────────────────────────────────────────────
        kubeconfig_content = None
        if cluster.kubeconfig_encrypted:
            try:
                from app.utils.encryption import decrypt
                kubeconfig_content = decrypt(cluster.kubeconfig_encrypted)
            except Exception as exc:
                logger.warning(
                    f"[client_factory] kubeconfig decrypt failed for "
                    f"cluster {cluster_id}: {exc}"
                )
                try:
                    import base64
                    kubeconfig_content = base64.b64decode(
                        cluster.kubeconfig_encrypted
                    ).decode("utf-8")
                except Exception:
                    kubeconfig_content = cluster.kubeconfig_encrypted

        # ── Build client ──────────────────────────────────────────────────────
        try:
            from app.integrations.kubernetes.client import KubernetesClient

            config: dict = {}
            if kubeconfig_content:
                config["kubeconfig_content"] = kubeconfig_content
            elif cluster.api_server_url:
                config["api_server_url"] = cluster.api_server_url

            if not config:
                logger.info(
                    f"[client_factory] cluster {cluster_id} has no credentials — "
                    "trying in-cluster config"
                )

            client = KubernetesClient(config)
            return client

        except Exception as exc:
            logger.warning(
                f"[client_factory] build KubernetesClient failed for "
                f"cluster {cluster_id}: {exc}"
            )
            return None

    @staticmethod
    async def _load_cluster(cluster_id: str, db=None):
        """Load the Cluster model from DB (creates session if needed)."""
        try:
            from app.models.cluster import Cluster
            from sqlalchemy import select

            async def _fetch(session):
                result = await session.execute(
                    select(Cluster).where(Cluster.id == cluster_id)
                )
                return result.scalar_one_or_none()

            if db is not None:
                return await _fetch(db)

            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                return await _fetch(session)

        except Exception as exc:
            logger.warning(f"[client_factory] _load_cluster error: {exc}")
            return None

    def invalidate(self, cluster_id: str, tenant_id: str) -> None:
        """Evict the cached client for a cluster (e.g. after credential rotation)."""
        key = f"{tenant_id}:{cluster_id}"
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        self._cache.clear()


# ── Module-level singleton ─────────────────────────────────────────────────────

_factory: Optional[KubernetesClientFactory] = None


def get_client_factory() -> KubernetesClientFactory:
    global _factory
    if _factory is None:
        _factory = KubernetesClientFactory()
    return _factory
