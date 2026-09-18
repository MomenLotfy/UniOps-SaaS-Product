from __future__ import annotations
"""Kubernetes service — pod management, cluster health, and real cluster actions.

Security model:
  - EVERY operation that targets a single pod resolves it tenant-scoped
    (404 on cross-tenant access — never 403 leakage).
  - Cluster clients are built ONLY from the tenant's own integrations
    (with an explicit optional cluster filter) — never "first K8s
    integration in the whole table".
  - Pod exec runs the command argument list directly without a shell
    (no command injection), is audit-logged, and never logs secrets.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pod import Pod
from app.models.integration import Integration
from app.models.audit_log import AuditLog
from app.schemas.pod import PodResponse, PodStats, PodActionResult
from app.schemas.common import PaginatedResponse
from app.core.exceptions import (
    NotFoundError, ForbiddenError, IntegrationError, IntegrationUnavailableError,
)
from app.services.base import BaseService
from app.utils.logger import logger


def _decrypt_integration_creds(integration: Integration) -> dict:
    """Decrypt stored credentials, skip non-encrypted fields gracefully."""
    from app.utils.encryption import decrypt
    creds = {}
    for k, v in (integration.credentials or {}).items():
        try:
            creds[k] = decrypt(v)
        except Exception:
            creds[k] = v
    return creds


class KubernetesService(BaseService):

    # ── Read operations ───────────────────────────────────────────────────────

    async def list_pods(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pod).where(Pod.tenant_id == tenant_id)
        if namespace:
            query = query.where(Pod.namespace == namespace)
        if cluster:
            query = query.where(Pod.cluster == cluster)
        if status:
            query = query.where(Pod.status == status)

        total = await self._count(query)
        query = query.order_by(Pod.restart_count.desc(), Pod.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[PodResponse.model_validate(p) for p in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_pod(self, pod_id: str, tenant_id: str) -> PodResponse:
        pod = await self._get_by_id_tenant(Pod, pod_id, tenant_id)
        return PodResponse.model_validate(pod)

    async def get_stats(self, tenant_id: str) -> PodStats:
        result = await self.db.execute(
            select(Pod.status, Pod.cpu_usage, Pod.memory_usage,
                   Pod.cpu_limit, Pod.memory_limit, Pod.restart_count)
            .where(Pod.tenant_id == tenant_id)
        )
        rows = result.fetchall()
        stats = PodStats(total=len(rows))
        cpu_usages, mem_usages = [], []

        for status, cpu_u, mem_u, cpu_l, mem_l, restarts in rows:
            if status == "Running":   stats.running += 1
            elif status == "Pending": stats.pending += 1
            elif status in ("Failed", "Error", "CrashLoopBackOff"):
                stats.failed += 1
            if restarts and restarts > 5:
                stats.high_restart_count += 1
            if cpu_u is not None and cpu_l and cpu_l > 0:
                cpu_usages.append((cpu_u / cpu_l) * 100)
            if mem_u is not None and mem_l and mem_l > 0:
                mem_usages.append((mem_u / mem_l) * 100)

        if cpu_usages:
            stats.cpu_usage_pct = round(sum(cpu_usages) / len(cpu_usages), 1)
        if mem_usages:
            stats.memory_usage_pct = round(sum(mem_usages) / len(mem_usages), 1)

        return stats

    async def get_namespaces(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pod.namespace).where(Pod.tenant_id == tenant_id).distinct()
        )
        return sorted(row[0] for row in result.fetchall() if row[0])

    async def get_clusters(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pod.cluster).where(Pod.tenant_id == tenant_id).distinct()
        )
        return sorted(row[0] for row in result.fetchall() if row[0])

    async def get_pod_events(self, pod_id: str, tenant_id: str) -> list[dict]:
        """Fetch live K8s events for a pod (useful for debugging CrashLoops)."""
        pod = await self._get_by_id_tenant(Pod, pod_id, tenant_id)
        client = await self._get_k8s_client_for_pod(pod)
        return await client.get_pod_events(pod.name, pod.namespace)

    async def get_pod_logs(
        self, pod_id: str, tenant_id: str,
        tail: int = 200, container: str | None = None,
    ) -> str:
        """Fetch last N log lines from a pod via the Kubernetes API.

        Raises IntegrationUnavailableError when the K8s API is unreachable —
        callers must surface the honest error rather than show fake content.
        """
        pod = await self._get_by_id_tenant(Pod, pod_id, tenant_id)
        return await self.get_pod_logs_by_name(
            tenant_id, pod.name, pod.namespace, tail, container)

    async def get_pod_logs_by_name(
        self,
        tenant_id: str,
        pod_name: str,
        namespace: str,
        tail: int = 200,
        container: str | None = None,
    ) -> str:
        client = await self.get_k8s_client_for_tenant(tenant_id)
        if not client:
            raise IntegrationUnavailableError(
                "Kubernetes", "no Kubernetes integration connected for this tenant")
        try:
            k8s = client._get_client()
            if not k8s:
                raise IntegrationUnavailableError(
                    "Kubernetes", "could not build Kubernetes client from stored kubeconfig")
            v1 = k8s.CoreV1Api()
            kwargs: dict = {
                "name":       pod_name,
                "namespace":  namespace,
                "tail_lines": tail,
                "_request_timeout": 15,
            }
            if container:
                kwargs["container"] = container
            logs: str = v1.read_namespaced_pod_log(**kwargs)
            return logs or "(no output)"
        except (IntegrationUnavailableError,):
            raise
        except Exception as e:
            logger.warning(f"get_pod_logs failed ({namespace}/{pod_name}): {e}")
            raise IntegrationError("Kubernetes", f"could not fetch pod logs: {e}")

    # ── Write / Action operations ─────────────────────────────────────────────

    async def delete_pod(self, pod_id: str, tenant_id: str, deleted_by: str) -> PodActionResult:
        """
        Delete pod from Kubernetes cluster immediately (grace_period=0).
        After success, removes the pod record from our DB too.
        K8s controllers (Deployments etc.) will recreate the pod automatically.
        """
        pod, client = await self._resolve_pod_and_client(pod_id, tenant_id)

        result = await client.delete_pod(pod.name, pod.namespace)
        if not result["success"]:
            raise IntegrationError("Kubernetes", result.get("error", "Delete failed"))

        pod_name = pod.name
        pod_namespace = pod.namespace
        await self.db.delete(pod)

        await self._write_audit(
            tenant_id=pod.tenant_id,
            user_id=deleted_by,
            action="pod.delete",
            resource="pod",
            resource_id=pod_id,
            details={"name": pod_name, "namespace": pod_namespace},
        )

        logger.info(f"[audit] pod.delete {pod_namespace}/{pod_name} by {deleted_by}")
        return PodActionResult(
            success=True,
            action="delete",
            pod_name=pod_name,
            namespace=pod_namespace,
            message=f"Pod '{pod_name}' deleted from cluster",
        )

    async def restart_pod(self, pod_id: str, tenant_id: str, restarted_by: str) -> PodActionResult:
        """
        Graceful restart: deletes pod with grace_period=30s.
        The owning controller (Deployment/StatefulSet/DaemonSet) schedules
        a replacement immediately.
        """
        pod, client = await self._resolve_pod_and_client(pod_id, tenant_id)

        result = await client.restart_pod(pod.name, pod.namespace)
        if not result["success"]:
            raise IntegrationError("Kubernetes", result.get("error", "Restart failed"))

        pod.status = "Terminating"
        pod.updated_at = datetime.now(timezone.utc)

        await self._write_audit(
            tenant_id=pod.tenant_id,
            user_id=restarted_by,
            action="pod.restart",
            resource="pod",
            resource_id=pod_id,
            details={
                "name": pod.name,
                "namespace": pod.namespace,
                "has_controller": result.get("has_controller", False),
            },
        )

        logger.info(f"[audit] pod.restart {pod.namespace}/{pod.name} by {restarted_by}")
        return PodActionResult(
            success=True,
            action="restart",
            pod_name=pod.name,
            namespace=pod.namespace,
            message=result.get("message", f"Pod '{pod.name}' restart initiated"),
            has_controller=result.get("has_controller"),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _resolve_pod_and_client(self, pod_id: str, tenant_id: str):
        """Load pod tenant-scoped + its integration + build a live K8s client."""
        pod = await self._get_by_id_tenant(Pod, pod_id, tenant_id)
        client = await self._get_k8s_client_for_pod(pod)
        return pod, client

    async def _get_k8s_client_for_pod(self, pod: Pod):
        """Client built from the integration that owns this pod."""
        from app.integrations.kubernetes.client import KubernetesClient

        if not pod.integration_id:
            raise IntegrationUnavailableError(
                "Kubernetes", "pod is not linked to a Kubernetes integration")

        result = await self.db.execute(
            select(Integration).where(
                Integration.id == pod.integration_id,
                Integration.tenant_id == pod.tenant_id,
            )
        )
        integration = result.scalar_one_or_none()
        if not integration:
            raise IntegrationUnavailableError("Kubernetes", "integration record not found")
        if not integration.is_active or integration.status != "connected":
            raise IntegrationUnavailableError(
                "Kubernetes",
                f"integration '{integration.name}' is not connected (status={integration.status})",
            )

        creds  = _decrypt_integration_creds(integration)
        config = {**creds, **(integration.config or {})}
        return KubernetesClient(config)

    async def get_k8s_client_for_tenant(
        self, tenant_id: str, cluster: str | None = None
    ):
        """
        Public tenant-level client lookup.

        Prefers the integration whose config.name matches the cluster filter;
        otherwise returns the tenant's first connected Kubernetes integration.
        NEVER crosses tenants — returns None when the tenant has none.
        """
        query = select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.type == "kubernetes",
            Integration.is_active == True,
            Integration.status == "connected",
        )
        result = await self.db.execute(query)
        integrations = result.scalars().all()
        if not integrations:
            return None

        integration = None
        if cluster:
            for i in integrations:
                cfg = i.config or {}
                if cluster in (i.name, cfg.get("name"), cfg.get("cluster_name")):
                    integration = i
                    break
        if integration is None:
            integration = integrations[0]

        creds  = _decrypt_integration_creds(integration)
        config = {**creds, **(integration.config or {})}

        from app.integrations.kubernetes.client import KubernetesClient
        return KubernetesClient(config)

    async def _write_audit(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        resource_id: str,
        details: dict,
        status: str = "success",
    ) -> None:
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details,
                status=status,
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            # Audit failures must never block the main action
            logger.warning(f"Audit log write failed (non-fatal): {e}")

    # ── High-risk operations ──────────────────────────────────────────────────

    async def exec_pod(
        self,
        pod_id: str,
        tenant_id: str,
        command: str,
        container: str | None = None,
        executed_by: str = "",
    ) -> str:
        """
        Execute a command in a running pod and return combined stdout/stderr.

        Security: the command string is split with shlex and the argument
        vector is executed DIRECTLY in the container — there is NO shell
        involvement, so `;`, `|`, `>`, backticks etc. cannot be injected.
        Secrets-looking environment values are never logged. Every exec is
        audit-logged (with the command audited for accountability).
        """
        import shlex as _shlex

        pod, client = await self._resolve_pod_and_client(pod_id, tenant_id)

        try:
            argv = _shlex.split(command)
        except ValueError as e:
            raise IntegrationError("Kubernetes", f"invalid command syntax: {e}")
        if not argv or not argv[0]:
            raise IntegrationError("Kubernetes", "empty command")
        # Guard against pathological argument vectors
        if len(argv) > 64 or any(len(a) > 512 for a in argv):
            raise IntegrationError("Kubernetes", "command too long / too many arguments")

        output = await client.exec_pod(
            name=pod.name,
            namespace=pod.namespace,
            command_list=argv,
            container=container,
        )

        # Audit (command recorded for accountability; output is NOT logged
        # to avoid persisting potential secrets from the container)
        await self._write_audit(
            tenant_id=pod.tenant_id,
            user_id=executed_by or "unknown",
            action="pod.exec",
            resource="pod",
            resource_id=pod_id,
            details={
                "name":      pod.name,
                "namespace": pod.namespace,
                "command":   " ".join(argv)[:300],
                "container": container,
                # output deliberately omitted
            },
        )
        return output

    async def scale_deployment(
        self,
        tenant_id: str,
        deployment_name: str,
        namespace: str,
        replicas: int,
        triggered_by: str,
        cluster: str | None = None,
    ) -> dict:
        """Scale a Kubernetes Deployment — strictly within the caller's tenant."""
        client = await self.get_k8s_client_for_tenant(tenant_id, cluster=cluster)
        if not client:
            return {
                "success": False,
                "error": "No Kubernetes integration connected for this tenant",
                "connected": False,
            }

        result = await client.scale_deployment(
            name=deployment_name,
            namespace=namespace,
            replicas=replicas,
        )
        await self._write_audit(
            tenant_id=tenant_id,
            user_id=triggered_by,
            action="deployment.scale",
            resource="deployment",
            resource_id=f"{namespace}/{deployment_name}",
            details={
                "replicas": replicas,
                "namespace": namespace,
                "success": result.get("success", False),
            },
            status="success" if result.get("success") else "failed",
        )
        return result
