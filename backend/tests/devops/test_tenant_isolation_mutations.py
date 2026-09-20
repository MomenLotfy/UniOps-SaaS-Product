"""
Tenant isolation for MUTATIONS, and server-side RBAC.

Why this file exists: the original proof of these guarantees lived in
``scripts/audit_isolation.py``, which needs a live server plus fixtures
(``audit.db`` / ``.audit_ids.json``) that are not in version control. That made
the evidence unreproducible — the report could cite it, but nobody could re-run
it. These tests port the same guarantees into the committed suite.

The invariant under test is stronger than "returns 404". A cross-tenant mutation
must ALSO leave the victim's row untouched, so every destructive case re-reads
the database afterwards. A 404 that quietly deleted something would pass the
status assertion and fail the survival assertion.

Reads were already covered in ``test_api_contract_matrix.py``; this file covers
the mutations, which are where isolation failures actually cost data.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.cluster import Cluster
from app.models.pod import Pod


TENANT_A = "t-iso-a"
TENANT_B = "t-iso-b"


def _hdr(tenant: str, roles: list[str], uid: str = "u") -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        user_id=uid, email=f"{uid}@iso.dev", tenant_id=tenant, roles=roles,
    )}


def _admin(tenant: str = TENANT_A) -> dict:
    return _hdr(tenant, ["admin"], "admin-a")


def _viewer(tenant: str = TENANT_A) -> dict:
    return _hdr(tenant, ["viewer"], "viewer-a")


def _devops(tenant: str = TENANT_A) -> dict:
    return _hdr(tenant, ["devops_engineer"], "devops-a")


@pytest.fixture
async def tenant_b_pod(client, db_session):
    """A pod row that genuinely belongs to tenant B."""
    pod = Pod(tenant_id=TENANT_B, name="b-pod", namespace="default",
              cluster="b-cluster", status="Running", restart_count=3)
    db_session.add(pod)
    await db_session.commit()
    return pod


@pytest.fixture
async def tenant_b_cluster(client, db_session):
    row = Cluster(tenant_id=TENANT_B, name="b-cluster", provider="self-hosted",
                  kubeconfig_encrypted="secret-material")
    db_session.add(row)
    await db_session.commit()
    return row


# ── pod mutations ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_suffix,body", [
    ("post", "/restart", None),
    ("delete", "", None),
    ("post", "/exec", {"command": "whoami"}),
])
async def test_cross_tenant_pod_mutation_is_404_and_row_survives(
    client, db_session, tenant_b_pod, method, path_suffix, body
):
    """Tenant A's admin attacks tenant B's pod: 404 and the row must survive."""
    pod = tenant_b_pod
    path = f"/api/v1/kubernetes/pods/{pod.id}{path_suffix}"
    kwargs = {"headers": _admin()}
    if body is not None:
        kwargs["json"] = body

    r = await getattr(client, method)(path, **kwargs)
    assert r.status_code == 404, (
        f"{method.upper()} {path} returned {r.status_code} for another tenant's pod"
    )

    still = await db_session.get(Pod, pod.id)
    assert still is not None, "cross-tenant mutation destroyed the victim's row"
    assert still.tenant_id == TENANT_B
    assert still.restart_count == 3


@pytest.mark.asyncio
async def test_same_tenant_pod_delete_is_not_404(client, db_session):
    """
    Control: the 404 above must come from the tenant filter, not from the
    endpoint always returning 404. Owner reaches the handler.
    """
    pod = Pod(tenant_id=TENANT_A, name="a-pod", namespace="default",
              cluster="a-cluster", status="Running")
    db_session.add(pod)
    await db_session.commit()

    r = await client.delete(f"/api/v1/kubernetes/pods/{pod.id}",
                            headers=_admin())
    # Not 404 — the tenant filter let it through. The provider is absent in this
    # environment, so a 5xx/404-from-provider is acceptable; 404-from-tenant is not.
    assert r.status_code != 404 or "not found" not in r.text.lower()


# ── cluster mutations ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_suffix,body", [
    ("get", "", None),
    ("post", "/test", {}),
    ("patch", "", {"name": "hijacked"}),
    ("delete", "", None),
])
async def test_cross_tenant_cluster_mutation_is_404_and_row_survives(
    client, db_session, tenant_b_cluster, method, path_suffix, body
):
    row = tenant_b_cluster
    path = f"/api/v1/clusters/{row.id}{path_suffix}"
    kwargs = {"headers": _admin()}
    if body is not None:
        kwargs["json"] = body

    r = await getattr(client, method)(path, **kwargs)
    assert r.status_code == 404, f"{method.upper()} {path} -> {r.status_code}"

    still = await db_session.get(Cluster, row.id)
    assert still is not None, "cross-tenant cluster mutation destroyed the row"
    assert still.name == "b-cluster", "cross-tenant PATCH mutated the victim's row"


# ── pipeline mutations ────────────────────────────────────────────────────────

@pytest.fixture
async def tenant_b_pipeline(client, db_session):
    from app.models.pipeline import Pipeline

    p = Pipeline(tenant_id=TENANT_B, external_id="gh-1", name="b-pipeline",
                 repository="acme/b", branch="main", status="queued")
    db_session.add(p)
    await db_session.commit()
    return p


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_suffix,body", [
    ("get", "", None),
    ("post", "/cancel", {}),
    ("post", "/rerun", {}),
])
async def test_cross_tenant_pipeline_is_404_and_row_survives(
    client, db_session, tenant_b_pipeline, method, path_suffix, body
):
    from app.models.pipeline import Pipeline

    p = tenant_b_pipeline
    path = f"/api/v1/pipelines/{p.id}{path_suffix}"
    kwargs = {"headers": _admin()}
    if body is not None:
        kwargs["json"] = body

    r = await getattr(client, method)(path, **kwargs)
    assert r.status_code == 404, f"{method.upper()} {path} -> {r.status_code}"

    still = await db_session.get(Pipeline, p.id)
    assert still is not None
    assert still.status == "queued", "cross-tenant mutation changed pipeline state"


# ── server-side RBAC ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/v1/clusters", {"name": "c", "provider": "self-hosted"}),
    ("post", "/api/v1/gitops", {"name": "a", "repo_url": "https://g/x",
                                "path": ".", "namespace": "d"}),
    ("post", "/api/v1/devops-alerts", {"type": "t", "message": "m",
                                       "severity": "warning"}),
])
async def test_viewer_is_refused_on_devops_mutations(client, method, path, body):
    """RBAC is enforced server-side, not merely hidden in the UI."""
    r = await getattr(client, method)(path, json=body, headers=_viewer())
    assert r.status_code == 403, f"{method.upper()} {path} -> {r.status_code}"


@pytest.mark.asyncio
async def test_viewer_cannot_restart_or_delete_pods(client, db_session):
    pod = Pod(tenant_id=TENANT_A, name="rbac-pod", namespace="default",
              cluster="a-cluster", status="Running")
    db_session.add(pod)
    await db_session.commit()

    for method, suffix, body in (("post", "/restart", None),
                                 ("delete", "", None)):
        kwargs = {"headers": _viewer()}
        if body is not None:
            kwargs["json"] = body
        r = await getattr(client, method)(
            f"/api/v1/kubernetes/pods/{pod.id}{suffix}", **kwargs)
        assert r.status_code == 403, f"{method} {suffix} -> {r.status_code}"

    still = await db_session.get(Pod, pod.id)
    assert still is not None


@pytest.mark.asyncio
async def test_devops_engineer_reaches_the_handler(client):
    """A permitted role is not blocked — otherwise the 403s prove nothing."""
    r = await client.post("/api/v1/clusters",
                          json={"name": "ok-cluster", "provider": "self-hosted"},
                          headers=_devops())
    assert r.status_code != 403, "devops_engineer must be permitted to create clusters"


@pytest.mark.asyncio
async def test_forged_role_claim_from_another_tenant_is_refused(client, db_session):
    """
    A token minted for tenant A claiming admin must not reach tenant B's data.
    This is the escalation the 404s above guard against from the other direction.
    """
    row = Cluster(tenant_id=TENANT_B, name="victim", provider="self-hosted",
                  kubeconfig_encrypted="secret")
    db_session.add(row)
    await db_session.commit()

    r = await client.delete(f"/api/v1/clusters/{row.id}",
                            headers=_admin(TENANT_A))
    assert r.status_code == 404

    still = await db_session.get(Cluster, row.id)
    assert still is not None
