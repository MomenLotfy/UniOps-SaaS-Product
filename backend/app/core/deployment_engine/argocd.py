"""
ArgoCD Integration — creates, syncs, and monitors ArgoCD Applications.

Supports two modes:
  1. Direct API mode: calls ArgoCD server REST API when an argocd integration is configured.
  2. Manifest mode: generates the Application YAML and pushes it to the GitOps repo.

Both modes are graceful — failures are logged and surfaced as status strings rather than exceptions.
"""
from __future__ import annotations
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)


class ArgoCDClient:
    """Async client for the ArgoCD REST API."""

    def __init__(self, server_url: str, token: str, insecure: bool = False):
        self.server_url = server_url.rstrip("/")
        self.token      = token
        self.insecure   = insecure
        self._headers   = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _get(self, path: str) -> Optional[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=not self.insecure) as c:
            try:
                r = await c.get(f"{self.server_url}{path}", headers=self._headers)
                return r.json() if r.status_code == 200 else None
            except Exception as exc:
                logger.warning(f"[argocd] GET {path} error: {exc}")
                return None

    async def _post(self, path: str, body: dict) -> Optional[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=not self.insecure) as c:
            try:
                r = await c.post(f"{self.server_url}{path}", json=body, headers=self._headers)
                if r.status_code in (200, 201):
                    return r.json()
                logger.warning(f"[argocd] POST {path} → {r.status_code}: {r.text[:200]}")
                return None
            except Exception as exc:
                logger.warning(f"[argocd] POST {path} error: {exc}")
                return None

    async def health(self) -> bool:
        data = await self._get("/api/v1/settings")
        return data is not None

    async def create_application(
        self,
        app_name:       str,
        repo_url:       str,
        helm_path:      str,
        namespace:      str,
        cluster_server: str = "https://kubernetes.default.svc",
        project:        str = "default",
    ) -> Optional[dict]:
        body = {
            "metadata": {
                "name":      app_name,
                "namespace": "argocd",
                "labels":    {"managed-by": "uniops"},
            },
            "spec": {
                "project": project,
                "source": {
                    "repoURL":         repo_url,
                    "targetRevision":  "main",
                    "path":            helm_path,
                },
                "destination": {
                    "server":    cluster_server,
                    "namespace": namespace,
                },
                "syncPolicy": {
                    "automated": {"prune": True, "selfHeal": True},
                    "syncOptions": ["CreateNamespace=true", "ApplyOutOfSyncOnly=true"],
                },
            },
        }
        return await self._post("/api/v1/applications", body)

    async def sync_application(self, app_name: str) -> bool:
        result = await self._post(f"/api/v1/applications/{app_name}/sync", {})
        return result is not None

    async def get_application(self, app_name: str) -> Optional[dict]:
        return await self._get(f"/api/v1/applications/{app_name}")

    async def get_sync_status(self, app_name: str) -> str:
        """Returns sync status string: Synced | OutOfSync | Unknown."""
        data = await self.get_application(app_name)
        if not data:
            return "Unknown"
        return (data.get("status") or {}).get("sync", {}).get("status", "Unknown")

    async def get_health_status(self, app_name: str) -> str:
        """Returns health status string: Healthy | Degraded | Progressing | Unknown."""
        data = await self.get_application(app_name)
        if not data:
            return "Unknown"
        return (data.get("status") or {}).get("health", {}).get("status", "Unknown")


def get_argocd_client(integration: dict) -> Optional[ArgoCDClient]:
    """
    Build an ArgoCDClient from an integration record (from DB).
    Returns None if no ArgoCD integration is configured.
    """
    if not integration:
        return None
    creds    = integration.get("credentials") or {}
    token    = creds.get("token") or creds.get("argocd_token") or ""
    cfg      = integration.get("config") or {}
    server   = cfg.get("server_url") or cfg.get("url") or ""
    insecure = cfg.get("insecure", False)

    if not (token and server):
        return None
    return ArgoCDClient(server, token, insecure=insecure)
