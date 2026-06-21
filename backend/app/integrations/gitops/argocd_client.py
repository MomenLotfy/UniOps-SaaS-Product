from __future__ import annotations
"""
ArgoCD Integration Layer — real sync engine for Epic 9.

Extends the core ArgoCDClient with:
  - Application diff (Git vs Cluster)
  - Rollback to a specific revision
  - Resource tree (full topology)
  - Multi-application status listing

Falls back gracefully when ArgoCD is not configured.
"""
from __future__ import annotations
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)


class ArgoCDSyncClient:
    """
    Enhanced ArgoCD REST API client for Epic 9.
    Covers sync status, diffs, rollback, and resource trees.
    """

    def __init__(self, server_url: str, token: str, insecure: bool = False):
        self.server_url = server_url.rstrip("/")
        self.token      = token
        self.insecure   = insecure
        self._headers   = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    # ── Low-level HTTP helpers ────────────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None) -> Optional[dict]:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, verify=not self.insecure
        ) as c:
            try:
                r = await c.get(
                    f"{self.server_url}{path}",
                    headers=self._headers,
                    params=params or {},
                )
                if r.status_code == 200:
                    return r.json()
                logger.warning(f"[argocd] GET {path} → {r.status_code}")
                return None
            except Exception as exc:
                logger.warning(f"[argocd] GET {path} error: {exc}")
                return None

    async def _post(self, path: str, body: dict | None = None) -> Optional[dict]:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, verify=not self.insecure
        ) as c:
            try:
                r = await c.post(
                    f"{self.server_url}{path}",
                    json=body or {},
                    headers=self._headers,
                )
                if r.status_code in (200, 201):
                    return r.json()
                logger.warning(f"[argocd] POST {path} → {r.status_code}: {r.text[:200]}")
                return None
            except Exception as exc:
                logger.warning(f"[argocd] POST {path} error: {exc}")
                return None

    # ── Core status ───────────────────────────────────────────────────────────

    async def health(self) -> bool:
        data = await self._get("/api/v1/settings")
        return data is not None

    async def get_application(self, app_name: str) -> Optional[dict]:
        """Fetch full ArgoCD Application object."""
        return await self._get(f"/api/v1/applications/{app_name}")

    async def get_application_status(self, app_name: str) -> dict:
        """
        Returns a structured status summary.
        Shape: {sync_status, health_status, diff, resources, last_synced_at, revision}
        """
        data = await self.get_application(app_name)
        if not data:
            return _unknown_status(app_name)

        status = data.get("status") or {}
        sync   = status.get("sync") or {}
        health = status.get("health") or {}

        resources = [
            {
                "group":     r.get("group", ""),
                "kind":      r.get("kind", ""),
                "namespace": r.get("namespace", ""),
                "name":      r.get("name", ""),
                "status":    r.get("status", "Unknown"),
                "health":    (r.get("health") or {}).get("status", "Unknown"),
            }
            for r in status.get("resources", [])
        ]

        diff = sync.get("comparedTo") or {}

        return {
            "app_name":      app_name,
            "sync_status":   sync.get("status", "Unknown"),
            "health_status": health.get("status", "Unknown"),
            "revision":      sync.get("revision", ""),
            "last_synced_at": (status.get("operationState") or {}).get(
                "finishedAt"
            ),
            "resources":     resources,
            "diff":          diff,
            "message":       health.get("message", ""),
        }

    # ── Diff ─────────────────────────────────────────────────────────────────

    async def get_app_diff(self, app_name: str) -> dict:
        """
        Fetch the diff between the desired (Git) and live (Cluster) state.
        Returns list of resource diffs when available.
        """
        data = await self._get(
            f"/api/v1/applications/{app_name}/resource-tree"
        )
        if not data:
            return {"available": False, "nodes": []}

        nodes = [
            {
                "group":           n.get("group", ""),
                "kind":            n.get("kind", ""),
                "namespace":       n.get("namespace", ""),
                "name":            n.get("name", ""),
                "version":         n.get("version", ""),
                "status":          n.get("status", "Unknown"),
                "health_status":   (n.get("health") or {}).get("status", "Unknown"),
                "created_at":      n.get("createdAt"),
            }
            for n in data.get("nodes", [])
        ]
        return {"available": True, "nodes": nodes}

    # ── Actions ───────────────────────────────────────────────────────────────

    async def sync_application(
        self, app_name: str, revision: str = "HEAD", prune: bool = False
    ) -> bool:
        """Trigger an ArgoCD sync for the application."""
        body = {
            "revision": revision,
            "prune":    prune,
            "dryRun":   False,
        }
        result = await self._post(
            f"/api/v1/applications/{app_name}/sync", body
        )
        return result is not None

    async def rollback_application(
        self, app_name: str, revision_id: int
    ) -> bool:
        """
        Roll back an application to a specific history ID.
        revision_id is the ArgoCD history entry ID (integer).
        """
        body = {"id": revision_id}
        result = await self._post(
            f"/api/v1/applications/{app_name}/rollback", body
        )
        return result is not None

    async def refresh_application(self, app_name: str) -> bool:
        """Force ArgoCD to refresh the application state from Git."""
        data = await self._get(
            f"/api/v1/applications/{app_name}",
            params={"refresh": "normal"},
        )
        return data is not None

    async def get_app_history(self, app_name: str) -> list[dict]:
        """Fetch deployment history (list of revisions with metadata)."""
        data = await self._get(
            f"/api/v1/applications/{app_name}/history"
        )
        if not data:
            return []
        return [
            {
                "id":         h.get("id"),
                "revision":   h.get("revision", ""),
                "deployed_at": h.get("deployedAt"),
                "source":     h.get("source") or {},
            }
            for h in (data.get("items") or [])
        ]

    async def list_applications(self) -> list[dict]:
        """List all ArgoCD applications (name + status only)."""
        data = await self._get("/api/v1/applications")
        if not data:
            return []
        return [
            {
                "name":         a.get("metadata", {}).get("name", ""),
                "namespace":    a.get("metadata", {}).get("namespace", ""),
                "sync_status":  (a.get("status", {}).get("sync") or {}).get("status", "Unknown"),
                "health_status":(a.get("status", {}).get("health") or {}).get("status", "Unknown"),
                "project":      a.get("spec", {}).get("project", "default"),
            }
            for a in (data.get("items") or [])
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unknown_status(app_name: str) -> dict:
    return {
        "app_name":      app_name,
        "sync_status":   "Unknown",
        "health_status": "Unknown",
        "revision":      "",
        "last_synced_at": None,
        "resources":     [],
        "diff":          {},
        "message":       "ArgoCD not reachable or application not found",
    }


def get_argocd_sync_client(integration: dict | None) -> Optional[ArgoCDSyncClient]:
    """
    Build an ArgoCDSyncClient from an integration record (from DB).
    Returns None when ArgoCD is not configured.
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
    return ArgoCDSyncClient(server, token, insecure=insecure)
