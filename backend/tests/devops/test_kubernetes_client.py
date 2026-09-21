"""BUG-002 / BUG-003 — Kubernetes client regression tests.

BUG-002: ``delete_pod`` and ``restart_pod`` called ``k8s.V1DeleteOptions(...)``
on the ``_K8sApis`` shim, which only exposes API classes. Both raised
AttributeError. ``V1DeleteOptions`` is now imported from ``kubernetes.client``.

BUG-003: ``list_all_pods`` returned ``[]`` on any failure, so the sync deleted
every pod row when the API server was unreachable. ``list_all_pods_checked``
now reports ``ok=False`` for "state unknown".

CoreV1Api is mocked throughout — no cluster required.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.integrations.kubernetes.client import (
    KubernetesClient,
    KubernetesClientUnavailable,
    KubernetesProviderError,
    PodListResult,
    _K8sApis,
)


# ── BUG-002: the shim genuinely lacks the model class ───────────────────────

def test_k8s_apis_shim_does_not_expose_model_classes():
    """Documents WHY the model must be imported directly."""
    shim = _K8sApis(None)
    assert not hasattr(shim, "V1DeleteOptions")
    assert callable(shim.CoreV1Api)


def test_v1_delete_options_is_imported_from_kubernetes_client():
    import app.integrations.kubernetes.client as mod
    from kubernetes.client import V1DeleteOptions as Real
    assert mod.V1DeleteOptions is Real


# ── BUG-002: force delete builds valid options and calls the right API ──────

@pytest.mark.asyncio
async def test_force_delete_builds_valid_delete_options_and_calls_api():
    client = KubernetesClient({"kubeconfig": "x"})

    fake_v1 = MagicMock()
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    result = await client.delete_pod("web-1", "prod")

    assert result["success"] is True
    fake_v1.delete_namespaced_pod.assert_called_once()
    kwargs = fake_v1.delete_namespaced_pod.call_args.kwargs
    assert kwargs["name"] == "web-1"
    assert kwargs["namespace"] == "prod"

    opts = kwargs["body"]
    # A real kubernetes model instance, not an AttributeError and not a dict
    from kubernetes.client import V1DeleteOptions
    assert isinstance(opts, V1DeleteOptions)
    assert opts.grace_period_seconds == 0, "force delete must use grace period 0"


@pytest.mark.asyncio
async def test_restart_uses_graceful_delete_options():
    client = KubernetesClient({"kubeconfig": "x"})

    pod_obj = MagicMock()
    owner = MagicMock()
    owner.controller = True
    pod_obj.metadata.owner_references = [owner]

    fake_v1 = MagicMock()
    fake_v1.read_namespaced_pod.return_value = pod_obj
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    result = await client.restart_pod("web-1", "prod")

    assert result["success"] is True
    kwargs = fake_v1.delete_namespaced_pod.call_args.kwargs
    from kubernetes.client import V1DeleteOptions
    assert isinstance(kwargs["body"], V1DeleteOptions)
    assert kwargs["body"].grace_period_seconds == 30, \
        "restart must be graceful (30s), not a force delete"


@pytest.mark.asyncio
async def test_restart_reports_missing_pod_without_crashing():
    client = KubernetesClient({"kubeconfig": "x"})
    fake_v1 = MagicMock()
    fake_v1.read_namespaced_pod.side_effect = Exception("not found")
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    result = await client.restart_pod("gone", "prod")
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_delete_provider_failure_maps_to_success_false():
    client = KubernetesClient({"kubeconfig": "x"})
    fake_v1 = MagicMock()
    fake_v1.delete_namespaced_pod.side_effect = Exception("Connection refused")
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    result = await client.delete_pod("web-1", "prod")
    assert result["success"] is False
    assert result["error"]


@pytest.mark.asyncio
async def test_delete_without_a_client_reports_unavailable_not_crash():
    client = KubernetesClient({})
    client._k8s_client = None
    # force _get_client to fail to build
    client.config = {}
    result = await client.delete_pod("web-1", "prod")
    assert result["success"] is False


# ── BUG-003: reconciliation safety ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_checked_listing_reports_ok_on_success():
    client = KubernetesClient({})

    async def fake_raw():
        return [{"name": "a", "namespace": "default"}]

    client._list_all_pods_raw = fake_raw
    res = await client.list_all_pods_checked()

    assert isinstance(res, PodListResult)
    assert res.ok is True
    assert len(res.pods) == 1
    assert res.error is None


@pytest.mark.asyncio
async def test_checked_listing_reports_unknown_when_provider_fails():
    """The core invariant: failure must NOT look like an empty cluster."""
    client = KubernetesClient({})

    async def fake_raw():
        raise KubernetesProviderError("Connection refused")

    client._list_all_pods_raw = fake_raw
    res = await client.list_all_pods_checked()

    assert res.ok is False, "provider failure must be reported as unknown state"
    assert res.pods == []
    assert res.error


@pytest.mark.asyncio
async def test_checked_listing_reports_ok_for_a_genuinely_empty_cluster():
    """An empty cluster is a legitimate result and must be distinguishable."""
    client = KubernetesClient({})

    async def fake_raw():
        return []

    client._list_all_pods_raw = fake_raw
    res = await client.list_all_pods_checked()

    assert res.ok is True
    assert res.pods == []


@pytest.mark.asyncio
async def test_raw_listing_raises_instead_of_returning_empty():
    client = KubernetesClient({})
    client._k8s_client = None
    client.config = {}
    with pytest.raises(KubernetesProviderError):
        await client._list_all_pods_raw()


@pytest.mark.asyncio
async def test_legacy_listing_still_returns_empty_for_backwards_compat():
    client = KubernetesClient({})
    client._k8s_client = None
    client.config = {}
    assert await client.list_all_pods() == []


# ── BUG-004: exec must not encode failures as output ────────────────────────

@pytest.mark.asyncio
async def test_exec_returns_output_on_success():
    client = KubernetesClient({})
    fake_v1 = MagicMock()
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    import app.integrations.kubernetes.client as mod
    original = mod.k8s_stream
    mod.k8s_stream = lambda *a, **k: "hello world\n"
    try:
        out = await client.exec_pod("web-1", "prod", command_list=["echo", "hi"])
    finally:
        mod.k8s_stream = original

    assert out == "hello world\n"


@pytest.mark.asyncio
async def test_exec_failure_raises_rather_than_returning_fake_output():
    """BUG-004: a transport failure must not be returned as command output."""
    client = KubernetesClient({})
    fake_v1 = MagicMock()
    shim = MagicMock()
    shim.CoreV1Api.return_value = fake_v1
    client._k8s_client = shim

    import app.integrations.kubernetes.client as mod
    original = mod.k8s_stream

    def boom(*a, **k):
        raise Exception("Connection refused")

    mod.k8s_stream = boom
    try:
        with pytest.raises(KubernetesProviderError):
            await client.exec_pod("web-1", "prod", command_list=["ls"])
    finally:
        mod.k8s_stream = original
