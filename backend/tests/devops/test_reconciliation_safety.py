"""BUG-003 — reconciliation safety (mandatory test class).

The invariant under test:

    provider success + []  ->  legitimate: stale rows may be deleted
    provider failure       ->  state UNKNOWN: nothing may be deleted

Before the fix, ``list_all_pods`` returned ``[]`` on any exception, so an
unreachable API server was indistinguishable from an empty cluster and
``_sync_pods`` deleted every pod row in the database.

These tests run the real ``_sync_pods`` against the real database with the
Kubernetes client stubbed — no cluster required.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.integrations.kubernetes.client import (
    KubernetesProviderError,
    PodListResult,
)
from app.models.integration import Integration
from app.models.pod import Pod


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded(db_session):
    """One tenant, one connected K8s integration, four pod rows."""
    from app.models.tenant import Tenant

    tenant = Tenant(name="Recon Tenant", slug="recon-tenant")
    db_session.add(tenant)
    await db_session.flush()

    integration = Integration(
        tenant_id=tenant.id,
        name="recon-cluster",
        type="kubernetes",
        status="connected",
        is_active=True,
        credentials={},
        config={"name": "recon-cluster"},
    )
    db_session.add(integration)
    await db_session.flush()

    pods = []
    for i in range(4):
        pods.append(Pod(
            tenant_id=tenant.id,
            integration_id=integration.id,
            name=f"web-{i}",
            namespace="prod",
            cluster="recon-cluster",
            status="Running",
            phase="Running",
            restart_count=0,
            containers=[],
            labels={},
        ))
    db_session.add_all(pods)
    await db_session.commit()

    return {"tenant_id": tenant.id, "integration_id": integration.id}


async def _pod_count(db, tenant_id: str) -> int:
    result = await db.execute(
        select(Pod).where(Pod.tenant_id == tenant_id)
    )
    return len(result.scalars().all())


def _stub_client(monkeypatch, listing: PodListResult):
    """Replace KubernetesClient.list_all_pods_checked with a canned result."""
    import app.integrations.kubernetes.client as k8s_mod

    async def fake_checked(self):
        return listing

    async def fake_metrics(self):
        return {}

    monkeypatch.setattr(k8s_mod.KubernetesClient, "list_all_pods_checked", fake_checked)
    monkeypatch.setattr(k8s_mod.KubernetesClient, "get_pod_metrics", fake_metrics)


# ── 1. provider failure -> NO deletion (the core invariant) ─────────────────

@pytest.mark.asyncio
async def test_provider_failure_deletes_nothing(db_session, seeded, monkeypatch):
    from app.tasks.sync_pods import _sync_pods
    import app.tasks.sync_pods as mod

    _stub_client(monkeypatch, PodListResult(ok=False, pods=[], error="Connection refused"))

    # Point the task at the test database session factory
    from tests.conftest import TestSessionLocal
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    assert await _pod_count(db_session, seeded["tenant_id"]) == 4

    summary = await _sync_pods(seeded["tenant_id"])

    remaining = await _pod_count(db_session, seeded["tenant_id"])
    assert remaining == 4, (
        f"provider failure must not delete pod rows — {4 - remaining} were deleted"
    )
    assert summary["pods_deleted"] == 0
    assert summary["integrations_failed"] == 1
    assert summary["integrations"] == 0, "a failed integration must not count as synced"
    assert summary["errors"], "the failure must be reported, not swallowed"


@pytest.mark.asyncio
async def test_provider_timeout_deletes_nothing(db_session, seeded, monkeypatch):
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    _stub_client(monkeypatch, PodListResult(ok=False, pods=[], error="timed out"))
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    summary = await _sync_pods(seeded["tenant_id"])
    assert await _pod_count(db_session, seeded["tenant_id"]) == 4
    assert summary["pods_deleted"] == 0


@pytest.mark.asyncio
async def test_malformed_provider_response_deletes_nothing(db_session, seeded, monkeypatch):
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    _stub_client(monkeypatch, PodListResult(
        ok=False, pods=[], error="'NoneType' object has no attribute 'items'"))
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    summary = await _sync_pods(seeded["tenant_id"])
    assert await _pod_count(db_session, seeded["tenant_id"]) == 4
    assert summary["pods_deleted"] == 0


@pytest.mark.asyncio
async def test_unhandled_exception_during_sync_deletes_nothing(
    db_session, seeded, monkeypatch
):
    """A raw raise (not a PodListResult) must also be non-destructive."""
    import app.integrations.kubernetes.client as k8s_mod
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    async def boom(self):
        raise KubernetesProviderError("connection reset by peer")

    monkeypatch.setattr(k8s_mod.KubernetesClient, "list_all_pods_checked", boom)
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    summary = await _sync_pods(seeded["tenant_id"])
    assert await _pod_count(db_session, seeded["tenant_id"]) == 4
    assert summary["pods_deleted"] == 0
    assert summary["integrations_failed"] == 1


# ── 2. provider success + empty -> legitimate deletion ──────────────────────

@pytest.mark.asyncio
async def test_confirmed_empty_cluster_does_delete_stale_rows(
    db_session, seeded, monkeypatch
):
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    _stub_client(monkeypatch, PodListResult(ok=True, pods=[], error=None))
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    summary = await _sync_pods(seeded["tenant_id"])

    assert await _pod_count(db_session, seeded["tenant_id"]) == 0
    assert summary["pods_deleted"] == 4
    assert summary["integrations"] == 1
    assert summary["integrations_failed"] == 0


# ── 3. provider success + partial -> only genuinely-absent rows deleted ─────

@pytest.mark.asyncio
async def test_partial_listing_deletes_only_absent_pods(db_session, seeded, monkeypatch):
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    _stub_client(monkeypatch, PodListResult(ok=True, pods=[
        {"name": "web-0", "namespace": "prod", "status": "Running", "phase": "Running"},
        {"name": "web-1", "namespace": "prod", "status": "Running", "phase": "Running"},
    ], error=None))
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    summary = await _sync_pods(seeded["tenant_id"])

    assert await _pod_count(db_session, seeded["tenant_id"]) == 2
    assert summary["pods_deleted"] == 2
    assert summary["pods_synced"] == 2


# ── 4. cross-tenant: one tenant's failure must not touch another's rows ─────

@pytest.mark.asyncio
async def test_failure_is_scoped_to_the_failing_integration(
    db_session, seeded, monkeypatch
):
    from app.models.tenant import Tenant
    from app.tasks.sync_pods import _sync_pods
    from tests.conftest import TestSessionLocal

    other = Tenant(name="Other Tenant", slug="other-tenant")
    db_session.add(other)
    await db_session.flush()
    other_integration = Integration(
        tenant_id=other.id, name="other-cluster", type="kubernetes",
        status="connected", is_active=True, credentials={},
        config={"name": "other-cluster"},
    )
    db_session.add(other_integration)
    await db_session.flush()
    db_session.add(Pod(
        tenant_id=other.id, integration_id=other_integration.id,
        name="other-web", namespace="prod", cluster="other-cluster",
        status="Running", phase="Running", restart_count=0,
        containers=[], labels={},
    ))
    await db_session.commit()

    _stub_client(monkeypatch, PodListResult(ok=False, pods=[], error="refused"))
    monkeypatch.setattr("app.core.database.CelerySessionLocal", TestSessionLocal)

    await _sync_pods()  # all tenants

    assert await _pod_count(db_session, seeded["tenant_id"]) == 4
    assert await _pod_count(db_session, other.id) == 1
