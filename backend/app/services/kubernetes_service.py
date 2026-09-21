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
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.integrations.kubernetes.client import KubernetesClient

from app.models.pod import Pod
from app.models.integration import Integration
from app.models.cluster import Cluster
from app.models.audit_log import AuditLog
from app.schemas.pod import PodResponse, PodStats, PodActionResult
from app.schemas.common import PaginatedResponse
from app.core.exceptions import (
    NotFoundError, ForbiddenError, IntegrationError, IntegrationUnavailableError,
)
from app.integrations.base import raise_for_provider_failure
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

    async def cluster_pod_scope(self, tenant_id: str, cluster_id: str) -> set[str]:
        """
        BUG-010: the set of ``Pod.cluster`` values that belong to ``cluster_id``.

        ``Pod.cluster`` is written by the sync job as the provider-reported
        cluster name or, failing that, the *integration* name
        (``sync_pods.py``: ``pod.cluster = data.get("cluster") or
        integration.name``). There is no foreign key between ``clusters`` and
        ``integrations``, so a cluster is identified here by the same convention
        ``get_client_for_cluster`` already uses: its own name, or the name of
        the integration that explicitly names it.

        Safety properties, all deliberate:

        * resolves through ``resolve_cluster``, so an unknown or other-tenant
          ``cluster_id`` raises ``NotFoundError`` -> HTTP 404. No silent
          substitution of a different cluster.
        * the returned set only ever contains names belonging to the resolved
          cluster, so scoping by it cannot leak another cluster's pods.
        * a cluster whose pods were synced under a different label simply yields
          an empty list — which is a true statement about that cluster, not a
          fallback to an arbitrary one.
        """
        cluster = await self.resolve_cluster(tenant_id, cluster_id)
        names: set[str] = {cluster.name}
        integrations = await self._list_tenant_k8s_integrations(tenant_id)
        integration = self._match_integration(
            integrations, cluster_id
        ) or self._match_integration(integrations, cluster.name)
        if integration is not None:
            names.add(integration.name)
        return names

    async def list_pods(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None,
        status: Optional[str] = None,
        cluster_id: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pod).where(Pod.tenant_id == tenant_id)
        if namespace:
            query = query.where(Pod.namespace == namespace)
        if cluster:
            query = query.where(Pod.cluster == cluster)
        if cluster_id:
            # BUG-010: the DevOps Center cluster selector sends the cluster's
            # *id*; resolution is tenant-scoped and 404s on an unknown or
            # foreign id rather than quietly serving another cluster.
            query = query.where(
                Pod.cluster.in_(await self.cluster_pod_scope(tenant_id, cluster_id))
            )
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

    async def get_stats(
        self, tenant_id: str, cluster_id: Optional[str] = None
    ) -> PodStats:
        query = (
            select(Pod.status, Pod.cpu_usage, Pod.memory_usage,
                   Pod.cpu_limit, Pod.memory_limit, Pod.restart_count)
            .where(Pod.tenant_id == tenant_id)
        )
        if cluster_id:
            # BUG-010: the summary tiles must describe the selected cluster,
            # not the whole tenant, when a cluster is selected. Same
            # tenant-scoped resolution as list_pods — 404 on a foreign id.
            query = query.where(
                Pod.cluster.in_(await self.cluster_pod_scope(tenant_id, cluster_id))
            )
        result = await self.db.execute(query)
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
            # A failed delete must still be audited. The audit row used to be
            # written only after a successful call, so every failure — the case
            # an operator most needs a record of — was missing from the trail.
            await self._write_audit(
                tenant_id=pod.tenant_id,
                user_id=deleted_by,
                action="pod.delete",
                resource="pod",
                resource_id=pod_id,
                details={
                    "name": pod.name,
                    "namespace": pod.namespace,
                    "error": str(result.get("error", ""))[:300],
                },
                status="failed",
            )
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
            # See delete_pod: a failed restart must still leave an audit record.
            await self._write_audit(
                tenant_id=pod.tenant_id,
                user_id=restarted_by,
                action="pod.restart",
                resource="pod",
                resource_id=pod_id,
                details={
                    "name": pod.name,
                    "namespace": pod.namespace,
                    "error": str(result.get("error", ""))[:300],
                },
                status="failed",
            )
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

        Resolution rules:

        * ``cluster`` omitted -> the tenant's default connected Kubernetes
          integration. This is the only implicit selection permitted.
        * ``cluster`` given -> the integration that matches that cluster, or
          ``None`` when the tenant has no such integration.

        It NEVER falls back to a different cluster: a caller that asked for a
        specific cluster must not silently receive another cluster's client.
        NEVER crosses tenants — returns None when the tenant has none.
        """
        integrations = await self._list_tenant_k8s_integrations(tenant_id)
        if not integrations:
            return None

        if cluster:
            integration = self._match_integration(integrations, cluster)
            if integration is None:
                # Explicitly requested cluster is not present for this tenant.
                # Returning integrations[0] here would route the operation —
                # including destructive ones — to an unrelated cluster.
                logger.warning(
                    f"cluster '{cluster}' not found among tenant {tenant_id}'s "
                    f"{len(integrations)} kubernetes integration(s) — refusing to "
                    f"fall back to a different cluster"
                )
                return None
        else:
            integration = integrations[0]

        return self._client_from_integration(integration)

    async def _list_tenant_k8s_integrations(self, tenant_id: str) -> list[Integration]:
        query = select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.type == "kubernetes",
            Integration.is_active == True,
            Integration.status == "connected",
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _match_integration(
        integrations: list[Integration], cluster: str
    ) -> Integration | None:
        """Match a cluster identifier against the tenant's integrations."""
        for i in integrations:
            cfg = i.config or {}
            if cluster in (
                i.name, i.id, cfg.get("name"), cfg.get("cluster_name"),
                cfg.get("cluster_id"),
            ):
                return i
        return None

    @staticmethod
    def _client_from_integration(integration: Integration) -> KubernetesClient:
        creds  = _decrypt_integration_creds(integration)
        config = {**creds, **(integration.config or {})}

        from app.integrations.kubernetes.client import KubernetesClient
        return KubernetesClient(config)

    async def list_cluster_resource(
        self,
        tenant_id: str,
        fetch: Callable[[KubernetesClient, str | None], Awaitable[list]],
        namespace: str | None = None,
        cluster_id: str | None = None,
        resource: str = "resources",
    ) -> dict:
        """
        BUG-009: cluster-scoped listing that never presents a provider outage
        as an empty cluster.

        Returns the project's degraded payload shape::

            {"items": [...], "source": "kubernetes", "degraded": False}
            {"items": [],    "source": "unavailable", "degraded": True,
             "error_code": "KUBERNETES_UNAVAILABLE", "message": "..."}

        ``source: "unavailable"`` mirrors the convention already used by the
        observability endpoints, so this is not a second envelope convention.
        """
        try:
            client = await self.get_client_for_cluster(tenant_id, cluster_id)
        except NotFoundError:
            raise
        except IntegrationUnavailableError as e:
            return self._degraded_resource(str(e.message))

        if client is None:
            return self._degraded_resource(
                "No Kubernetes integration connected for this tenant"
            )

        reachable, reason = await client.check_reachable()
        if not reachable:
            logger.warning(
                f"kubernetes unreachable while listing {resource} for tenant "
                f"{tenant_id}: {reason}"
            )
            return self._degraded_resource(reason or "Kubernetes API server unreachable")

        items = await fetch(client, namespace)
        return {
            "items":    items or [],
            "source":   "kubernetes",
            "degraded": False,
        }

    @staticmethod
    def _degraded_resource(reason: str) -> dict:
        return {
            "items":      [],
            "source":     "unavailable",
            "degraded":   True,
            "error_code": "KUBERNETES_UNAVAILABLE",
            "message":    f"Kubernetes unavailable: {reason}",
        }

    async def resolve_cluster(self, tenant_id: str, cluster_id: str) -> Cluster:
        """
        Resolve a cluster by id, strictly within the tenant.

        Raises NotFoundError when the cluster does not exist or belongs to
        another tenant — the two cases are deliberately indistinguishable to
        the caller so cluster existence is not leaked across tenants.
        """
        result = await self.db.execute(
            select(Cluster).where(
                Cluster.id == cluster_id,
                Cluster.tenant_id == tenant_id,
            )
        )
        cluster = result.scalar_one_or_none()
        if cluster is None:
            raise NotFoundError(f"Cluster {cluster_id} not found")
        return cluster

    async def get_client_for_cluster(
        self, tenant_id: str, cluster_id: str | None
    ) -> KubernetesClient | None:
        """
        Cluster-scoped client resolution used by the DevOps Center selector.

        * ``cluster_id`` given -> resolve that exact cluster (404 if absent or
          owned by another tenant), then build a client from that cluster's own
          credentials. No fallback to any other cluster or integration.
        * ``cluster_id`` omitted -> the tenant's default connected integration.
        """
        if not cluster_id:
            return await self.get_k8s_client_for_tenant(tenant_id)

        cluster = await self.resolve_cluster(tenant_id, cluster_id)

        from app.integrations.kubernetes.client import KubernetesClient

        kubeconfig = None
        if cluster.kubeconfig_encrypted:
            try:
                import base64
                kubeconfig = base64.b64decode(cluster.kubeconfig_encrypted).decode()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"could not decode kubeconfig for cluster {cluster_id}: {e}")

        if kubeconfig:
            return KubernetesClient({"kubeconfig": kubeconfig, "name": cluster.name})

        # No cluster-specific kubeconfig: use the integration that explicitly
        # names this cluster. Still no silent fallback to an unrelated one.
        integrations = await self._list_tenant_k8s_integrations(tenant_id)
        integration = self._match_integration(
            integrations, cluster_id) or self._match_integration(
            integrations, cluster.name)
        if integration is None:
            raise IntegrationUnavailableError(
                "Kubernetes",
                f"cluster '{cluster.name}' has no kubeconfig and no matching "
                f"Kubernetes integration",
            )
        return self._client_from_integration(integration)

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

        # BUG-004: map provider failures onto the project's integration-error
        # contract (502 / success=false) instead of letting an error string be
        # returned as if it were command output.
        from app.integrations.kubernetes.client import (
            KubernetesClientUnavailable, KubernetesProviderError,
        )

        base_details = {
            "name":      pod.name,
            "namespace": pod.namespace,
            "command":   " ".join(argv)[:300],
            "container": container,
            # output deliberately omitted — it may contain container secrets
        }

        async def _audit(status: str, error: str | None = None) -> None:
            """
            Record this exec. Written on BOTH outcomes: a failed exec is the
            one an operator most needs a record of, and the audit row used to
            be written only after a successful call, so every failure was
            invisible in the audit trail.
            """
            details = dict(base_details)
            if error:
                details["error"] = error[:300]
            await self._write_audit(
                tenant_id=pod.tenant_id,
                user_id=executed_by or "unknown",
                action="pod.exec",
                resource="pod",
                resource_id=pod_id,
                details=details,
                status=status,
            )

        try:
            output = await client.exec_pod(
                name=pod.name,
                namespace=pod.namespace,
                command_list=argv,
                container=container,
            )
        except KubernetesClientUnavailable as e:
            await _audit("failed", str(e))
            raise IntegrationUnavailableError("Kubernetes", str(e))
        except KubernetesProviderError as e:
            await _audit("failed", str(e))
            raise IntegrationError("Kubernetes", str(e))
        except ValueError as e:
            await _audit("failed", str(e))
            raise IntegrationError("Kubernetes", f"invalid command: {e}")
        except Exception as e:
            # Any other provider failure (e.g. a raw error raised from the
            # kubernetes stream layer) must be classified, not leaked as an
            # opaque HTTP 500.
            await _audit("failed", str(e))
            raise IntegrationError("Kubernetes", f"exec failed: {e}")

        await _audit("success")
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
            # Never a silent 200: an unavailable provider is a 503-class error.
            raise IntegrationUnavailableError(
                "Kubernetes", "No Kubernetes integration connected for this tenant"
            )

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
        # BUG-006: a failed provider mutation must never be returned as a
        # 200/success envelope. Translate it into the project's established
        # exception contract instead.
        return raise_for_provider_failure(result, "Kubernetes")
