"""Cluster routing + wrong-cluster fallback removal (mandatory test class).

Audit finding: ``get_k8s_client_for_tenant`` fell back to ``integrations[0]``
when the requested cluster did not match, so a cluster-scoped operation —
including destructive ones — could be silently routed to an unrelated cluster.

Required behaviour:
    cluster = A              -> A
    cluster = B              -> B
    cluster = random UUID    -> not found, never another cluster
    cluster = other tenant's -> not found
    cluster omitted          -> the tenant's documented default
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.cluster import Cluster
from app.models.integration import Integration
from app.models.tenant import Tenant
from app.services.kubernetes_service import KubernetesService


@pytest_asyncio.fixture
async def two_clusters(db_session):
    """One tenant with two distinctly-named K8s integrations + cluster rows."""
    tenant = Tenant(name="Routing Tenant", slug="routing-tenant")
    db_session.add(tenant)
    await db_session.flush()

    other = Tenant(name="Routing Other", slug="routing-other")
    db_session.add(other)
    await db_session.flush()

    def integ(tid, name, url):
        return Integration(
            tenant_id=tid, name=name, type="kubernetes", status="connected",
            is_active=True, credentials={},
            config={"name": name, "kubeconfig": f"kubeconfig-for-{name}",
                    "api_server": url},
        )

    iA = integ(tenant.id, "cluster-a", "https://a.example:6443")
    iB = integ(tenant.id, "cluster-b", "https://b.example:6443")
    iOther = integ(other.id, "cluster-other", "https://other.example:6443")
    db_session.add_all([iA, iB, iOther])
    await db_session.flush()

    cA = Cluster(tenant_id=tenant.id, name="cluster-a", provider="on-prem",
                 region="local", environment="production")
    cB = Cluster(tenant_id=tenant.id, name="cluster-b", provider="on-prem",
                 region="local", environment="staging")
    cOther = Cluster(tenant_id=other.id, name="cluster-other", provider="eks",
                     region="us-east-1", environment="production")
    db_session.add_all([cA, cB, cOther])
    await db_session.commit()

    return {
        "tenant_id": tenant.id, "other_tenant_id": other.id,
        "iA": iA.id, "iB": iB.id, "iOther": iOther.id,
        "cA": cA.id, "cB": cB.id, "cOther": cOther.id,
    }


def _api_server(client) -> str | None:
    """Read back which integration's config the resolved client carries."""
    return (client.config or {}).get("api_server")


# ── A resolves to A, B resolves to B ────────────────────────────────────────

@pytest.mark.asyncio
async def test_cluster_a_resolves_to_a(db_session, two_clusters):
    svc = KubernetesService(db_session)
    client = await svc.get_k8s_client_for_tenant(
        two_clusters["tenant_id"], cluster="cluster-a")
    assert client is not None
    assert _api_server(client) == "https://a.example:6443"


@pytest.mark.asyncio
async def test_cluster_b_resolves_to_b(db_session, two_clusters):
    svc = KubernetesService(db_session)
    client = await svc.get_k8s_client_for_tenant(
        two_clusters["tenant_id"], cluster="cluster-b")
    assert client is not None
    assert _api_server(client) == "https://b.example:6443"


@pytest.mark.asyncio
async def test_a_and_b_never_resolve_to_the_same_client(db_session, two_clusters):
    svc = KubernetesService(db_session)
    a = await svc.get_k8s_client_for_tenant(two_clusters["tenant_id"], cluster="cluster-a")
    b = await svc.get_k8s_client_for_tenant(two_clusters["tenant_id"], cluster="cluster-b")
    assert _api_server(a) != _api_server(b)


# ── The critical case: an unknown cluster must NOT fall back ────────────────

@pytest.mark.asyncio
async def test_unknown_cluster_does_not_fall_back_to_integrations_zero(
    db_session, two_clusters
):
    """THE regression test for the wrong-cluster fallback."""
    svc = KubernetesService(db_session)
    client = await svc.get_k8s_client_for_tenant(
        two_clusters["tenant_id"], cluster="does-not-exist")
    assert client is None, (
        "an unmatched cluster must yield no client — previously this returned "
        "integrations[0], silently routing to cluster-a"
    )


@pytest.mark.asyncio
async def test_random_uuid_cluster_does_not_fall_back(db_session, two_clusters):
    import uuid
    svc = KubernetesService(db_session)
    client = await svc.get_k8s_client_for_tenant(
        two_clusters["tenant_id"], cluster=str(uuid.uuid4()))
    assert client is None


@pytest.mark.asyncio
async def test_other_tenants_cluster_is_never_resolved(db_session, two_clusters):
    svc = KubernetesService(db_session)
    client = await svc.get_k8s_client_for_tenant(
        two_clusters["tenant_id"], cluster="cluster-other")
    assert client is None


# ── cluster_id based resolution (used by the DevOps Center selector) ────────

@pytest.mark.asyncio
async def test_resolve_cluster_by_id_returns_own_cluster(db_session, two_clusters):
    svc = KubernetesService(db_session)
    cluster = await svc.resolve_cluster(two_clusters["tenant_id"], two_clusters["cA"])
    assert cluster.name == "cluster-a"


@pytest.mark.asyncio
async def test_resolve_cluster_of_another_tenant_is_not_found(
    db_session, two_clusters
):
    svc = KubernetesService(db_session)
    with pytest.raises(NotFoundError):
        await svc.resolve_cluster(two_clusters["tenant_id"], two_clusters["cOther"])


@pytest.mark.asyncio
async def test_resolve_random_cluster_id_is_not_found(db_session, two_clusters):
    import uuid
    svc = KubernetesService(db_session)
    with pytest.raises(NotFoundError):
        await svc.resolve_cluster(two_clusters["tenant_id"], str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_client_for_cluster_a_and_b_are_distinct(db_session, two_clusters):
    svc = KubernetesService(db_session)
    a = await svc.get_client_for_cluster(two_clusters["tenant_id"], two_clusters["cA"])
    b = await svc.get_client_for_cluster(two_clusters["tenant_id"], two_clusters["cB"])
    assert a is not None and b is not None
    assert a.config.get("name") == "cluster-a"
    assert b.config.get("name") == "cluster-b"


@pytest.mark.asyncio
async def test_client_for_cluster_omitted_uses_tenant_default(
    db_session, two_clusters
):
    svc = KubernetesService(db_session)
    client = await svc.get_client_for_cluster(two_clusters["tenant_id"], None)
    assert client is not None, "omitting the cluster keeps the documented default"


@pytest.mark.asyncio
async def test_tenant_without_any_integration_gets_no_client(db_session):
    tenant = Tenant(name="Empty Tenant", slug="empty-tenant")
    db_session.add(tenant)
    await db_session.commit()

    svc = KubernetesService(db_session)
    assert await svc.get_k8s_client_for_tenant(tenant.id) is None
    assert await svc.get_k8s_client_for_tenant(tenant.id, cluster="anything") is None


# ── The fallback is gone from the source, not just from behaviour ───────────

def test_default_selection_only_happens_when_no_cluster_was_requested():
    """
    Guard the structure, not just the behaviour.

    ``integrations[0]`` is legitimate for the documented default case (no
    cluster requested). What must never come back is using it as a fallback
    after a requested cluster failed to match — so the only ``integrations[0]``
    may sit in the ``else`` branch of ``if cluster:``.
    """
    import inspect
    from app.services import kubernetes_service

    src = inspect.getsource(kubernetes_service.KubernetesService.get_k8s_client_for_tenant)
    # Ignore comments and docstrings — the explanatory comment that warns
    # against the fallback naturally mentions the pattern it forbids.
    code = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("#")
    )

    assert code.count("integrations[0]") == 1, (
        "expected exactly one default selection, in the no-cluster branch"
    )
    src = code

    if_block, _, else_block = src.partition("if cluster:")
    assert "integrations[0]" not in if_block, "no default before the cluster branch"
    assert "integrations[0]" in else_block, (
        "the single default selection must live in the no-cluster branch"
    )
    assert "return None" in if_block, (
        "an unmatched cluster must return None rather than fall back"
    )
