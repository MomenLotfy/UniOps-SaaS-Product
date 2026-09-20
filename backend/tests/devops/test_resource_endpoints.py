"""
BUG-009 — the nine Cluster Control Plane resource endpoints must not present a
provider outage as an empty cluster.

All nine endpoints previously did::

    client = await svc.get_k8s_client_for_tenant(tenant_id)
    if not client:
        return APIResponse(data=[])          # outage looks identical to "none"

They now return ``{items, source, degraded, message}``. These are real HTTP
round-trips through the ASGI app, covering both the no-integration case and
the integration-present-but-unreachable case.
"""
from __future__ import annotations

import jwt as pyjwt
import pytest
from unittest.mock import AsyncMock, patch

from app.services.kubernetes_service import KubernetesService


ENDPOINTS = [
    "/api/v1/kubernetes/pods/workloads/deployments",
    "/api/v1/kubernetes/pods/workloads/statefulsets",
    "/api/v1/kubernetes/pods/workloads/daemonsets",
    "/api/v1/kubernetes/pods/network/services",
    "/api/v1/kubernetes/pods/network/ingresses",
    "/api/v1/kubernetes/pods/batch/jobs",
    "/api/v1/kubernetes/pods/config/configmaps",
    "/api/v1/kubernetes/pods/config/secrets",
    "/api/v1/kubernetes/pods/autoscaling/hpa",
]


async def _register(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["data"]["access_token"]
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    return {"Authorization": f"Bearer {tok}"}, claims["tenant_id"]


@pytest.fixture
async def auth(client):
    headers, tenant_id = await _register(client, "rescplane@test.dev", "OrgResPlane")
    return client, headers, tenant_id


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_no_integration_reports_unavailable_not_empty_list(auth, path):
    """A tenant with no Kubernetes integration must not look like a clean cluster."""
    client, headers, _ = auth
    r = await client.get(path, headers=headers)
    assert r.status_code == 200, r.text

    payload = r.json()["data"]
    assert isinstance(payload, dict), f"{path} must return the degraded envelope"
    assert payload["degraded"] is True
    assert payload["source"] == "unavailable"
    assert payload["items"] == []
    assert payload["error_code"] == "KUBERNETES_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_unreachable_cluster_reports_unavailable_not_empty_list(auth, path):
    """Integration present, but the API server is down."""
    client, headers, _ = auth

    unreachable = AsyncMock()
    unreachable.check_reachable = AsyncMock(return_value=(False, "connection refused"))

    with patch.object(
        KubernetesService, "get_client_for_cluster",
        AsyncMock(return_value=unreachable),
    ):
        r = await client.get(path, headers=headers)

    assert r.status_code == 200, r.text
    payload = r.json()["data"]
    assert payload["degraded"] is True
    assert payload["source"] == "unavailable"
    assert "connection refused" in payload["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_reachable_empty_cluster_is_not_marked_degraded(auth, path):
    """The counterpart: genuinely empty must still read as empty, not broken."""
    client, headers, _ = auth

    reachable = AsyncMock()
    reachable.check_reachable = AsyncMock(return_value=(True, None))
    for m in ("list_deployments", "list_statefulsets", "list_daemonsets",
              "list_services", "list_ingresses", "list_jobs",
              "list_configmaps", "list_secrets_metadata", "list_hpa"):
        setattr(reachable, m, AsyncMock(return_value=[]))

    with patch.object(
        KubernetesService, "get_client_for_cluster",
        AsyncMock(return_value=reachable),
    ):
        r = await client.get(path, headers=headers)

    assert r.status_code == 200, r.text
    payload = r.json()["data"]
    assert payload["degraded"] is False
    assert payload["source"] == "kubernetes"
    assert payload["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_other_tenant_cluster_id_is_rejected_not_silently_swapped(auth, path):
    """
    Class E routing guard: a cluster_id owned by another tenant must not be
    resolved, and must not fall back to this tenant's default cluster.
    """
    client, headers, _ = auth
    _, other_tenant = await _register(client, "rescplane2@test.dev", "OrgResPlane2")

    r = await client.get(f"{path}?cluster_id=cluster-of-{other_tenant}", headers=headers)
    assert r.status_code in (200, 404), r.text

    if r.status_code == 200:
        payload = r.json()["data"]
        # It may degrade, but it must never claim to have read real resources.
        assert payload.get("source") != "kubernetes"


@pytest.mark.asyncio
async def test_secrets_endpoint_never_returns_values(auth):
    """Security invariant that must survive the envelope change."""
    client, headers, _ = auth

    reachable = AsyncMock()
    reachable.check_reachable = AsyncMock(return_value=(True, None))
    reachable.list_secrets_metadata = AsyncMock(return_value=[
        {"name": "db-creds", "namespace": "default", "type": "Opaque",
         "keys": ["password"], "age": "3d"},
    ])

    with patch.object(
        KubernetesService, "get_client_for_cluster",
        AsyncMock(return_value=reachable),
    ):
        r = await client.get("/api/v1/kubernetes/pods/config/secrets", headers=headers)

    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert "password" in items[0]["keys"]

    # The key NAME is metadata. A secret VALUE would arrive under a `data` or
    # `stringData` field, or as a value-bearing dict keyed by the key name.
    for forbidden in ("data", "stringData", "value", "values"):
        assert forbidden not in items[0], f"secret leaked a '{forbidden}' field"
    assert items[0].get("password") is None, "secret value exposed under its key name"


SUMMARY = "/api/v1/kubernetes/pods/cluster/summary"


@pytest.mark.asyncio
async def test_cluster_summary_is_not_connected_when_no_integration(auth):
    client, headers, _ = auth
    r = await client.get(SUMMARY, headers=headers)
    assert r.status_code == 200, r.text

    payload = r.json()["data"]
    assert payload["connected"] is False
    assert payload["degraded"] is True


@pytest.mark.asyncio
async def test_cluster_summary_does_not_claim_connected_when_api_server_down(auth):
    """
    The specific defect: `connected: True` was asserted merely because a client
    object could be built, then every count came back 0 — a healthy-looking
    empty cluster.
    """
    client, headers, _ = auth

    unreachable = AsyncMock()
    unreachable.check_reachable = AsyncMock(return_value=(False, "connection refused"))

    with patch.object(
        KubernetesService, "get_client_for_cluster",
        AsyncMock(return_value=unreachable),
    ):
        r = await client.get(SUMMARY, headers=headers)

    assert r.status_code == 200, r.text
    payload = r.json()["data"]

    assert payload["connected"] is False
    assert payload["degraded"] is True
    assert payload["error_code"] == "KUBERNETES_UNAVAILABLE"
    assert "connection refused" in payload["message"]
    # no fabricated zero-counts presented as a real cluster
    assert payload["counts"] == {}


@pytest.mark.asyncio
async def test_cluster_summary_reports_connected_only_on_a_reachable_cluster(auth):
    client, headers, _ = auth

    reachable = AsyncMock()
    reachable.check_reachable = AsyncMock(return_value=(True, None))
    for m in ("list_deployments", "list_statefulsets", "list_daemonsets",
              "list_services", "list_ingresses", "list_jobs",
              "list_configmaps", "list_hpa"):
        setattr(reachable, m, AsyncMock(return_value=[]))

    with patch.object(
        KubernetesService, "get_client_for_cluster",
        AsyncMock(return_value=reachable),
    ):
        r = await client.get(SUMMARY, headers=headers)

    assert r.status_code == 200, r.text
    payload = r.json()["data"]

    assert payload["connected"] is True
    assert payload["degraded"] is False
    assert payload["source"] == "kubernetes"
    assert payload["counts"]["deployments"] == 0


@pytest.mark.asyncio
async def test_all_nine_endpoints_share_one_degradation_contract(auth):
    """Guard against one endpoint drifting back to a bare array."""
    client, headers, _ = auth

    for path in ENDPOINTS:
        r = await client.get(path, headers=headers)
        assert r.status_code == 200, f"{path}: {r.text}"
        payload = r.json()["data"]
        assert isinstance(payload, dict), f"{path} regressed to a bare array"
        assert set(payload) >= {"items", "source", "degraded"}, path
