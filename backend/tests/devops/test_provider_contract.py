"""
DevOps Center — Phase 2 provider-contract regression suite.

Covers the Phase 2 bugs from DEVOPS_CENTER_PRODUCTION_AUDIT.md:

  BUG-007  cluster test-connection must not report success on failure
  BUG-008  GitOps delete must 404 when the row is absent (not a false 204)
  BUG-009  a Kubernetes outage must not render as an empty resource list
  BUG-011  pod metrics must carry restart_count
  BUG-012  usage percentages must derive from real usage / real capacity
  BUG-019  pipeline jobs must map provider failure to 502 INTEGRATION_ERROR

These are class C (unreachable-provider) assertions: the invariant under test
is that no endpoint reports success when the provider failed.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.core.exceptions import (
    IntegrationError,
    IntegrationUnavailableError,
    NotFoundError,
)


# ── BUG-009 — outage must not look like an empty cluster ──────────────────────

class TestResourceListingHonesty:
    """`KubernetesService.list_cluster_resource` — the BUG-009 seam."""

    @pytest.mark.asyncio
    async def test_unreachable_cluster_reports_unavailable_not_empty(self):
        from app.services.kubernetes_service import KubernetesService

        client = AsyncMock()
        client.check_reachable = AsyncMock(return_value=(False, "connection refused"))

        svc = KubernetesService(None)
        with patch.object(svc, "get_client_for_cluster", AsyncMock(return_value=client)):
            result = await svc.list_cluster_resource(
                "t1", lambda c, ns: c.list_deployments(ns), resource="deployments"
            )

        assert result["degraded"] is True
        assert result["source"] == "unavailable"
        assert result["items"] == []
        assert result["error_code"] == "KUBERNETES_UNAVAILABLE"
        # the reason is surfaced, not swallowed
        assert "connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_reachable_cluster_with_no_resources_is_genuinely_empty(self):
        """The counterpart case: empty here means empty, NOT degraded."""
        from app.services.kubernetes_service import KubernetesService

        client = AsyncMock()
        client.check_reachable = AsyncMock(return_value=(True, None))
        client.list_deployments = AsyncMock(return_value=[])

        svc = KubernetesService(None)
        with patch.object(svc, "get_client_for_cluster", AsyncMock(return_value=client)):
            result = await svc.list_cluster_resource(
                "t1", lambda c, ns: c.list_deployments(ns), resource="deployments"
            )

        assert result["degraded"] is False
        assert result["source"] == "kubernetes"
        assert result["items"] == []
        assert "error_code" not in result

    @pytest.mark.asyncio
    async def test_no_integration_reports_unavailable(self):
        from app.services.kubernetes_service import KubernetesService

        svc = KubernetesService(None)
        with patch.object(svc, "get_client_for_cluster", AsyncMock(return_value=None)):
            result = await svc.list_cluster_resource(
                "t1", lambda c, ns: c.list_deployments(ns), resource="deployments"
            )

        assert result["degraded"] is True
        assert result["source"] == "unavailable"

    @pytest.mark.asyncio
    async def test_unknown_cluster_id_still_raises_not_found(self):
        """Degradation must not swallow a routing error into an empty list."""
        from app.services.kubernetes_service import KubernetesService

        svc = KubernetesService(None)
        with patch.object(
            svc, "get_client_for_cluster",
            AsyncMock(side_effect=NotFoundError("cluster not found")),
        ):
            with pytest.raises(NotFoundError):
                await svc.list_cluster_resource(
                    "t1", lambda c, ns: c.list_deployments(ns), resource="deployments"
                )

    @pytest.mark.asyncio
    async def test_client_probe_reports_unreachable_on_exception(self):
        from app.integrations.kubernetes.client import KubernetesClient

        client = KubernetesClient({"kubeconfig_content": "not-a-kubeconfig"})
        with patch.object(client, "_get_client", side_effect=RuntimeError("boom")):
            ok, reason = await client.check_reachable()

        assert ok is False
        assert reason is not None

    @pytest.mark.asyncio
    async def test_client_probe_reports_unreachable_without_client(self):
        from app.integrations.kubernetes.client import KubernetesClient

        client = KubernetesClient({})
        with patch.object(client, "_get_client", return_value=None):
            ok, reason = await client.check_reachable()

        assert ok is False
        assert "unavailable" in (reason or "")


# ── BUG-007 — cluster test connection must be truthful ────────────────────────

class _FakeCluster:
    """Mimics the Cluster ORM fields test_connection reads/writes."""

    def __init__(self, status="disconnected", error_message=None):
        self.id = "c1"
        self.status = status
        self.error_message = error_message
        self.k8s_version = "1.29"
        self.node_count = 3
        self.last_health_check = None


class _FakeDB:
    """Minimal async session stub — commit/rollback only."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class TestClusterConnectionTruthfulness:
    """
    BUG-007. `test_connection(tenant_id, cluster_id)` delegates to
    `_run_health_check`, which records `status = "disconnected"` instead of
    raising when it cannot build a client. Success may only be claimed when
    the resolved status is really "connected".
    """

    def _svc(self, cluster):
        from app.services.cluster_service import ClusterService

        svc = ClusterService(_FakeDB())
        svc.get_cluster = AsyncMock(return_value=cluster)
        return svc

    @pytest.mark.asyncio
    async def test_health_check_that_leaves_cluster_disconnected_is_not_success(self):
        """The exact old defect: check ran, set 'disconnected', returned 200."""
        cluster = _FakeCluster(status="disconnected", error_message="unreachable")
        svc = self._svc(cluster)

        async def leaves_disconnected(c):
            c.status = "disconnected"
            c.error_message = "unreachable"

        with patch.object(svc, "_run_health_check", side_effect=leaves_disconnected):
            with pytest.raises(IntegrationUnavailableError):
                await svc.test_connection("t1", "c1")

    @pytest.mark.asyncio
    async def test_exception_during_check_does_not_claim_success(self):
        cluster = _FakeCluster()
        svc = self._svc(cluster)

        with patch.object(
            svc, "_run_health_check", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            with pytest.raises(IntegrationUnavailableError):
                await svc.test_connection("t1", "c1")

        assert cluster.status == "error"
        assert "boom" in cluster.error_message

    @pytest.mark.asyncio
    async def test_genuinely_connected_cluster_does_report_success(self):
        """Guard against over-correcting: a real connection must still succeed."""
        cluster = _FakeCluster()
        svc = self._svc(cluster)

        async def connects(c):
            c.status = "connected"
            c.error_message = None
            c.k8s_version = "1.29"
            c.node_count = 3

        with patch.object(svc, "_run_health_check", side_effect=connects):
            result = await svc.test_connection("t1", "c1")

        assert result["status"] == "connected"
        assert result["message"] == "Connection successful"

    @pytest.mark.asyncio
    async def test_error_status_is_not_success(self):
        cluster = _FakeCluster()
        svc = self._svc(cluster)

        async def errors(c):
            c.status = "error"
            c.error_message = "certificate expired"

        with patch.object(svc, "_run_health_check", side_effect=errors):
            with pytest.raises(IntegrationUnavailableError) as exc:
                await svc.test_connection("t1", "c1")

        assert "certificate expired" in exc.value.message


# ── BUG-008 — GitOps delete must 404, not silently 204 ────────────────────────

class TestGitOpsDeleteHonesty:

    def test_endpoint_raises_404_when_row_absent(self):
        """Source-level guard: the not-found branch must exist and be a 404."""
        import inspect
        from app.api.v1.endpoints import gitops

        src = inspect.getsource(gitops.delete_app)
        assert "status_code=404" in src
        # tenant isolation must have survived the fix
        assert "tenant_id" in src

    def test_tenant_filter_not_weakened(self):
        """Guard against "fixing" the 404 by dropping the tenant filter."""
        import inspect
        from app.api.v1.endpoints import gitops

        src = inspect.getsource(gitops.delete_app)
        assert "GitOpsApp.tenant_id" in src

    @pytest.mark.asyncio
    async def test_absent_row_raises_404_and_deletes_nothing(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.gitops import delete_app

        class FakeResult:
            def scalar_one_or_none(self):
                return None

        class FakeDB:
            def __init__(self):
                self.deleted = 0
                self.committed = 0

            async def execute(self, *a, **k):
                return FakeResult()

            async def delete(self, obj):
                self.deleted += 1

            async def commit(self):
                self.committed += 1

        db = FakeDB()
        with pytest.raises(HTTPException) as exc:
            await delete_app(
                app_id="missing", current_user=None, tenant_id="t1", db=db
            )

        assert exc.value.status_code == 404
        # the false-204 defect deleted and committed against nothing
        assert db.deleted == 0
        assert db.committed == 0


# ── BUG-011 — pod metrics must expose restart_count ───────────────────────────

class TestPodMetricsFields:

    def test_pod_metrics_payload_includes_restart_count(self):
        import inspect
        from app.api.v1.endpoints import observability

        src = inspect.getsource(observability.get_pod_metrics)
        assert '"restart_count"' in src

    def test_restart_count_never_fabricated_when_absent(self):
        """The schema default is 0 — an unknown count must not invent restarts."""
        from app.schemas.pod import PodResponse

        p = PodResponse(
            id="p1", tenant_id="t1", name="n", namespace="ns", status="Running",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        assert p.restart_count == 0


# ── BUG-012 — usage % must be real usage over real capacity ───────────────────

class TestUsagePercentageMath:

    @pytest.mark.asyncio
    async def test_percentage_derives_from_allocatable_capacity(self):
        import app.api.v1.endpoints.observability as obs

        class FakeClient:
            async def get_node_metrics(self):
                # 1.0 core used in total, 4.0 allocatable → 25%
                # 4GiB used in total, 8GiB allocatable → 50%
                return [
                    {"name": "n1", "cpu_usage": 0.5, "memory_usage": 2 * 1024**3},
                    {"name": "n2", "cpu_usage": 0.5, "memory_usage": 2 * 1024**3},
                ]

            async def get_node_capacity(self):
                return [
                    {"name": "n1", "cpu_allocatable": 2.0, "memory_allocatable": 4 * 1024**3},
                    {"name": "n2", "cpu_allocatable": 2.0, "memory_allocatable": 4 * 1024**3},
                ]

        class FakeSvc:
            async def get_k8s_client_for_tenant(self, tenant_id):
                return FakeClient()

        with patch.object(obs, "KubernetesService", lambda db: FakeSvc()):
            snap = await obs._live_cluster_snapshot("t1", None)

        assert snap["cpu_pct"] == 25.0
        assert snap["memory_pct"] == 50.0

    @pytest.mark.asyncio
    async def test_zero_capacity_yields_null_not_a_guessed_percentage(self):
        import app.api.v1.endpoints.observability as obs

        class FakeClient:
            async def get_node_metrics(self):
                return [{"name": "n1", "cpu_usage": 0.5, "memory_usage": 1024**3}]

            async def get_node_capacity(self):
                return [{"name": "n1", "cpu_allocatable": 0.0, "memory_allocatable": 0}]

        class FakeSvc:
            async def get_k8s_client_for_tenant(self, tenant_id):
                return FakeClient()

        with patch.object(obs, "KubernetesService", lambda db: FakeSvc()):
            snap = await obs._live_cluster_snapshot("t1", None)

        assert snap is None

    @pytest.mark.asyncio
    async def test_absolute_values_are_never_relabelled_as_percentages(self):
        """
        Regression guard for the original defect: cores*100 and bytes/1024**2
        were returned under *_pct keys. With 1.0 core of 4.0 allocatable the
        old math reported cpu_pct=100.0 and memory_pct=4096.0.
        """
        import app.api.v1.endpoints.observability as obs

        class FakeClient:
            async def get_node_metrics(self):
                return [{"name": "n1", "cpu_usage": 1.0, "memory_usage": 4 * 1024**3}]

            async def get_node_capacity(self):
                return [{"name": "n1", "cpu_allocatable": 4.0, "memory_allocatable": 8 * 1024**3}]

        class FakeSvc:
            async def get_k8s_client_for_tenant(self, tenant_id):
                return FakeClient()

        with patch.object(obs, "KubernetesService", lambda db: FakeSvc()):
            snap = await obs._live_cluster_snapshot("t1", None)

        assert snap["cpu_pct"] == 25.0        # was 100.0
        assert snap["memory_pct"] == 50.0     # was 4096.0

    def test_pod_stats_handles_zero_limits(self):
        """BUG-012 on the DB path: a zero limit must not divide-by-zero."""
        import inspect
        from app.services import kubernetes_service

        src = inspect.getsource(kubernetes_service.KubernetesService.get_stats)
        assert "cpu_l > 0" in src
        assert "mem_l > 0" in src


# ── ArgoCD reachability (BUG-007 class, found by the repo-wide sweep) ─────────

class TestArgoCDConnectivityHonesty:
    """
    `argocd_connected` used to be `bool(creds)` — true whenever credentials
    existed, regardless of whether ArgoCD answered. The UI renders that as a
    pulsing green "ArgoCD Live" pill, so a dead ArgoCD displayed as live.
    """

    @pytest.mark.asyncio
    async def test_no_credentials_is_not_connected(self):
        from app.api.v1.endpoints.gitops import _argocd_reachable

        assert await _argocd_reachable({}) is False
        assert await _argocd_reachable({"server": "", "token": "t"}) is False

    @pytest.mark.asyncio
    async def test_unreachable_server_is_not_connected(self):
        """Credentials present but the server refuses — must report False."""
        import httpx
        from unittest.mock import patch
        from app.api.v1.endpoints.gitops import _argocd_reachable

        creds = {"server": "https://argocd.invalid", "token": "tok"}

        def boom(*a, **k):
            raise httpx.ConnectError("connection refused")

        with patch.object(httpx, "AsyncClient", side_effect=boom):
            assert await _argocd_reachable(creds) is False

    @pytest.mark.asyncio
    async def test_answered_server_is_connected(self):
        import httpx
        from unittest.mock import patch, MagicMock
        from app.api.v1.endpoints.gitops import _argocd_reachable

        creds = {"server": "https://argocd.example", "token": "tok"}

        class FakeClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                r = MagicMock()
                r.status_code = 200
                return r

        with patch.object(httpx, "AsyncClient", FakeClient):
            assert await _argocd_reachable(creds) is True

    @pytest.mark.asyncio
    async def test_stats_reports_configured_but_unreachable_distinctly(self):
        """
        The UI must be able to tell "never configured" from "configured but
        down" — collapsing them is what made a dead ArgoCD look live.
        """
        from unittest.mock import AsyncMock, patch
        from app.api.v1.endpoints import gitops

        class FakeResult:
            def scalars(self): return self
            def all(self): return []

        class FakeDB:
            async def execute(self, *a, **k): return FakeResult()

        with patch.object(gitops, "_get_argocd_creds",
                          AsyncMock(return_value={"server": "https://a.invalid", "token": "t"})), \
             patch.object(gitops, "_argocd_reachable", AsyncMock(return_value=False)):
            resp = await gitops.get_stats(current_user=None, tenant_id="t1", db=FakeDB())

        data = resp.data
        assert data["argocd_configured"] is True
        assert data["argocd_connected"] is False

    @pytest.mark.asyncio
    async def test_stats_reports_neither_configured_nor_connected(self):
        from unittest.mock import AsyncMock, patch
        from app.api.v1.endpoints import gitops

        class FakeResult:
            def scalars(self): return self
            def all(self): return []

        class FakeDB:
            async def execute(self, *a, **k): return FakeResult()

        with patch.object(gitops, "_get_argocd_creds", AsyncMock(return_value=None)):
            resp = await gitops.get_stats(current_user=None, tenant_id="t1", db=FakeDB())

        data = resp.data
        assert data["argocd_configured"] is False
        assert data["argocd_connected"] is False


    @pytest.mark.asyncio
    async def test_reachability_probe_verifies_tls_by_default(self):
        """
        Regression guard: this probe was first written copying the module's
        pre-existing `verify=False` pattern, which would have made the ArgoCD
        security posture worse rather than better. It must verify TLS unless the
        tenant explicitly opted into `insecure`.
        """
        import httpx
        from unittest.mock import patch, MagicMock
        from app.api.v1.endpoints.gitops import _argocd_reachable

        seen = {}

        class CapturingClient:
            def __init__(self, *a, **kw):
                seen["verify"] = kw.get("verify", "NOT_PASSED")
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                r = MagicMock(); r.status_code = 200; return r

        with patch.object(httpx, "AsyncClient", CapturingClient):
            await _argocd_reachable({"server": "https://argocd.example", "token": "t"})
        assert seen["verify"] is True, (
            f"TLS verification must be ON by default, got verify={seen['verify']!r}"
        )

        # An explicit opt-out is still honoured.
        with patch.object(httpx, "AsyncClient", CapturingClient):
            await _argocd_reachable(
                {"server": "https://argocd.example", "token": "t", "insecure": True})
        assert seen["verify"] is False, "an explicit insecure opt-out must be honoured"


# ── BUG-019 — pipeline jobs must not leak an opaque 500 ───────────────────────

class TestPipelineJobsErrorContract:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider_status", [500, 502, 503])
    async def test_provider_failure_becomes_integration_error(self, provider_status):
        from app.services.pipeline_service import PipelineService
        from app.integrations.github.client import GitHubAPIError

        class FakePipeline:
            id = "p1"
            metadata_ = {}

        class FakeIntegration:
            type = "github"
            credentials = {}
            config = {}

        svc = PipelineService(None)
        svc._resolve = AsyncMock(return_value=(FakePipeline(), FakeIntegration()))

        with patch.object(
            PipelineService, "_github_get_jobs",
            AsyncMock(side_effect=GitHubAPIError(provider_status, "boom")),
        ):
            with pytest.raises(IntegrationError) as exc:
                await svc.get_jobs("p1", "t1")

        assert exc.value.status_code == 502
        assert exc.value.code == "INTEGRATION_ERROR"

    @pytest.mark.asyncio
    async def test_auth_failure_is_attributed_to_credentials(self):
        from app.services.pipeline_service import PipelineService
        from app.integrations.github.client import GitHubAPIError

        class FakePipeline:
            id = "p1"
            metadata_ = {}

        class FakeIntegration:
            type = "github"
            credentials = {}
            config = {}

        svc = PipelineService(None)
        svc._resolve = AsyncMock(return_value=(FakePipeline(), FakeIntegration()))

        with patch.object(
            PipelineService, "_github_get_jobs",
            AsyncMock(side_effect=GitHubAPIError(403, "forbidden")),
        ):
            with pytest.raises(IntegrationError) as exc:
                await svc.get_jobs("p1", "t1")

        assert "credentials" in exc.value.message

    @pytest.mark.asyncio
    async def test_gitlab_failure_uses_the_shared_exception_type(self):
        """
        The GitLab client re-raises GitHubAPIError by design. An earlier draft
        of this fix imported a non-existent GitLabAPIError, which would have
        failed at call time — this pins the real import path.
        """
        from app.services.pipeline_service import PipelineService
        from app.integrations.github.client import GitHubAPIError

        class FakePipeline:
            id = "p1"
            metadata_ = {"project_id": 7}

        class FakeIntegration:
            type = "gitlab"
            credentials = {}
            config = {}

        svc = PipelineService(None)
        svc._resolve = AsyncMock(return_value=(FakePipeline(), FakeIntegration()))

        with patch.object(
            PipelineService, "_gitlab_get_jobs",
            AsyncMock(side_effect=GitHubAPIError(500, "boom")),
        ):
            with pytest.raises(IntegrationError) as exc:
                await svc.get_jobs("p1", "t1")

        assert exc.value.status_code == 502

    def test_gitlab_client_reuses_github_exception_type(self):
        """Document the contract the fix above depends on."""
        from app.integrations.gitlab.client import GitHubAPIError  # noqa: F401
