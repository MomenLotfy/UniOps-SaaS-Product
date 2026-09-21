"""Audit logging must survive the remediation.

The remediation converted several provider failures from "return a dict" into
"raise an exception". That is the correct behaviour, but it introduces a real
risk: if the audit write sat *after* the point where the exception is raised,
every failed mutation would silently stop being audited — losing exactly the
record that matters most (who attempted what, and that it failed).

These tests run the real service methods against the real database with the
provider layer stubbed, and assert an AuditLog row exists with status="failed".
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.exceptions import IntegrationError, IntegrationUnavailableError
from app.models.audit_log import AuditLog
from app.models.integration import Integration


@pytest_asyncio.fixture
async def tenant_with_integration(db_session):
    from app.models.tenant import Tenant

    tenant = Tenant(name="Audit Tenant", slug="audit-tenant")
    db_session.add(tenant)
    await db_session.flush()

    integration = Integration(
        tenant_id=tenant.id,
        name="audit-cluster",
        type="kubernetes",
        status="connected",
        is_active=True,
        credentials={},
        config={"name": "audit-cluster"},
    )
    db_session.add(integration)
    await db_session.flush()
    return tenant, integration


async def _audit_rows(db, action: str) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).where(AuditLog.action == action)
    )
    return list(result.scalars().all())


# ── BUG-006 — scale ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failed_scale_is_audited_before_raising(db_session, tenant_with_integration):
    """
    The critical ordering assertion: `raise_for_provider_failure` must come
    AFTER the audit write, or failed scales stop being recorded.
    """
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, _ = tenant_with_integration
    svc = KubernetesService(db_session)

    failing = AsyncMock()
    failing.scale_deployment = AsyncMock(
        return_value={"success": False, "error": "quota exceeded for this namespace"}
    )

    with patch.object(svc, "get_k8s_client_for_tenant", AsyncMock(return_value=failing)):
        with pytest.raises(IntegrationError):
            await svc.scale_deployment(
                tenant_id=tenant.id,
                deployment_name="web",
                namespace="default",
                replicas=3,
                triggered_by="user-1",
            )

    rows = await _audit_rows(db_session, "deployment.scale")
    assert len(rows) == 1, "failed scale must still produce an audit row"
    assert rows[0].status == "failed"
    assert rows[0].tenant_id == tenant.id
    assert rows[0].user_id == "user-1"
    assert rows[0].resource == "deployment"
    assert rows[0].resource_id == "default/web"
    assert rows[0].details["success"] is False


@pytest.mark.asyncio
async def test_successful_scale_is_audited_as_success(db_session, tenant_with_integration):
    """Guard against over-correcting: success must still audit as success."""
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, _ = tenant_with_integration
    svc = KubernetesService(db_session)

    ok = AsyncMock()
    ok.scale_deployment = AsyncMock(return_value={"success": True, "replicas": 3})

    with patch.object(svc, "get_k8s_client_for_tenant", AsyncMock(return_value=ok)):
        result = await svc.scale_deployment(
            tenant_id=tenant.id,
            deployment_name="web",
            namespace="default",
            replicas=3,
            triggered_by="user-1",
        )

    assert result["success"] is True
    rows = await _audit_rows(db_session, "deployment.scale")
    assert len(rows) == 1
    assert rows[0].status == "success"


@pytest.mark.asyncio
async def test_audit_row_contains_no_secrets(db_session, tenant_with_integration):
    """Standing requirement: audit logs must never carry tokens or secrets."""
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, _ = tenant_with_integration
    svc = KubernetesService(db_session)

    ok = AsyncMock()
    ok.scale_deployment = AsyncMock(return_value={"success": True, "replicas": 2})

    with patch.object(svc, "get_k8s_client_for_tenant", AsyncMock(return_value=ok)):
        await svc.scale_deployment(
            tenant_id=tenant.id, deployment_name="api", namespace="prod",
            replicas=2, triggered_by="user-2",
        )

    rows = await _audit_rows(db_session, "deployment.scale")
    blob = repr(rows[0].details).lower()
    for forbidden in ("token", "secret", "password", "kubeconfig", "authorization"):
        assert forbidden not in blob, f"audit details leaked '{forbidden}'"


# ── delete / restart ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def linked_pod(db_session, tenant_with_integration):
    from app.models.pod import Pod

    tenant, integration = tenant_with_integration
    pod = Pod(
        tenant_id=tenant.id, name="web-9", namespace="default",
        cluster="audit-cluster", status="Running",
        integration_id=integration.id,
    )
    db_session.add(pod)
    await db_session.flush()
    return tenant, pod


@pytest.mark.asyncio
async def test_failed_pod_delete_is_audited(db_session, linked_pod):
    """
    Same class of defect as exec: the audit row used to be written only after a
    successful call, so a failed delete left no trace.
    """
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, pod = linked_pod
    svc = KubernetesService(db_session)

    failing = AsyncMock()
    failing.delete_pod = AsyncMock(return_value={"success": False, "error": "forbidden"})

    with patch.object(svc, "_get_k8s_client_for_pod", AsyncMock(return_value=failing)):
        with pytest.raises(IntegrationError):
            await svc.delete_pod(pod.id, tenant.id, "user-4")

    rows = await _audit_rows(db_session, "pod.delete")
    assert len(rows) == 1, "failed delete must still produce an audit row"
    assert rows[0].status == "failed"
    assert rows[0].user_id == "user-4"
    assert rows[0].details["error"] == "forbidden"


@pytest.mark.asyncio
async def test_failed_pod_restart_is_audited(db_session, linked_pod):
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, pod = linked_pod
    svc = KubernetesService(db_session)

    failing = AsyncMock()
    failing.restart_pod = AsyncMock(return_value={"success": False, "error": "timeout"})

    with patch.object(svc, "_get_k8s_client_for_pod", AsyncMock(return_value=failing)):
        with pytest.raises(IntegrationError):
            await svc.restart_pod(pod.id, tenant.id, "user-5")

    rows = await _audit_rows(db_session, "pod.restart")
    assert len(rows) == 1, "failed restart must still produce an audit row"
    assert rows[0].status == "failed"
    assert rows[0].user_id == "user-5"


@pytest.mark.asyncio
async def test_successful_pod_delete_is_audited_as_success(db_session, linked_pod):
    """Guard against over-correcting: the success path must be unchanged."""
    from unittest.mock import AsyncMock, patch
    from app.services.kubernetes_service import KubernetesService

    tenant, pod = linked_pod
    svc = KubernetesService(db_session)

    ok = AsyncMock()
    ok.delete_pod = AsyncMock(return_value={"success": True})

    with patch.object(svc, "_get_k8s_client_for_pod", AsyncMock(return_value=ok)):
        result = await svc.delete_pod(pod.id, tenant.id, "user-6")

    assert result.success is True
    rows = await _audit_rows(db_session, "pod.delete")
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert "error" not in rows[0].details


# ── exec — BUG-004 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exec_audits_before_provider_call(db_session, tenant_with_integration):
    """
    exec_pod audits *before* invoking the provider (output is not available
    beforehand). A provider failure therefore still leaves an audit record.
    """
    from unittest.mock import AsyncMock, patch
    from app.models.pod import Pod
    from app.services.kubernetes_service import KubernetesService

    tenant, integration = tenant_with_integration
    # exec_pod resolves the client from the integration that OWNS the pod
    # (_get_k8s_client_for_pod), not from the tenant default — so the pod must
    # be linked to an integration for the exec path to be reached at all.
    pod = Pod(
        tenant_id=tenant.id, name="web-1", namespace="default",
        cluster="audit-cluster", status="Running",
        integration_id=integration.id,
    )
    db_session.add(pod)
    await db_session.flush()

    svc = KubernetesService(db_session)

    failing = AsyncMock()
    failing._get_client = lambda: object()
    failing.exec_pod = AsyncMock(side_effect=RuntimeError("stream failed"))

    with patch.object(svc, "_get_k8s_client_for_pod", AsyncMock(return_value=failing)):
        with pytest.raises(IntegrationError):
            await svc.exec_pod(
                pod_id=pod.id, tenant_id=tenant.id, command="ls",
                executed_by="user-3",
            )

    rows = await _audit_rows(db_session, "pod.exec")
    assert len(rows) == 1, "failed exec must still produce an audit row"
    assert rows[0].user_id == "user-3"
    assert rows[0].tenant_id == tenant.id
