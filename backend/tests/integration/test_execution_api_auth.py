"""
Sprint 1 R8 — auth wiring for the Execution Orchestration API.

Every endpoint must:
  1. require an authenticated user (Bearer token), and
  2. read the tenant from the JWT, NOT from a raw query parameter.

The test below uses FastAPI's TestClient with a stubbed
``get_current_active_user`` and ``get_tenant_id`` to assert both
invariants.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user, get_tenant_id
from app.modules.security.execution_orchestration.api.routes import router


def _build_app(user=None, tenant=None) -> FastAPI:
    """Build a FastAPI app with the execution router + overridden auth deps."""
    app = FastAPI()
    app.include_router(router)

    async def _user():
        return user or {
            "user_id": "u-1",
            "tenant_id": tenant or "tenant-1",
            "roles": ["security_engineer"],
        }

    async def _tenant():
        return tenant or "tenant-1"

    app.dependency_overrides[get_current_active_user] = _user
    app.dependency_overrides[get_tenant_id] = _tenant
    return app


# ─────────────────────────────────────────────────────────────────────
# R8 — endpoints must require an authenticated user
# ─────────────────────────────────────────────────────────────────────
def test_r8_list_packages_requires_authentication():
    """
    Without the auth override, hitting the endpoint must 401 — the
    raw ``tenant_id`` query parameter is no longer accepted.
    """
    app = FastAPI()
    app.include_router(router)
    # Intentionally do NOT override get_current_active_user.

    with TestClient(app) as client:
        resp = client.get("/security/execution-packages/?tenant_id=tenant-1")
        assert resp.status_code == 401, (
            "endpoint must reject unauthenticated callers"
        )


def test_r8_list_packages_uses_jwt_tenant_not_query_string():
    """
    Even if the caller passes ``?tenant_id=other-tenant``, the
    authenticated user's tenant (from the JWT) is what the
    repository sees.  The query parameter must NOT leak cross-tenant.
    """
    from app.modules.security.execution_orchestration.services.execution_service import ExecutionService

    app = _build_app(tenant="jwt-tenant")
    captured: dict = {}

    async def _fake_list_packages(self, tenant_id, **_kwargs):
        captured["tenant_id"] = tenant_id
        return []

    with TestClient(app) as client:
        # Stub the service method to capture the tenant it actually sees.
        original = ExecutionService.list_packages
        ExecutionService.list_packages = _fake_list_packages
        try:
            resp = client.get(
                "/security/execution-packages/?tenant_id=other-tenant",
            )
            assert resp.status_code == 200
        finally:
            ExecutionService.list_packages = original

    # The repository saw the JWT tenant, NOT the query-string tenant.
    assert captured.get("tenant_id") == "jwt-tenant"


def test_r8_get_package_requires_tenant_in_token():
    """
    If the JWT lacks a tenant_id, the auth dependency itself must
    refuse — a 401, not a 200 with leaked data.
    """
    app = FastAPI()
    app.include_router(router)

    async def _user():
        # Tenant deliberately omitted from the JWT.
        return {"user_id": "u-1", "roles": ["security_engineer"]}

    async def _tenant():
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError("Tenant context not found in token")

    app.dependency_overrides[get_current_active_user] = _user
    app.dependency_overrides[get_tenant_id] = _tenant

    with TestClient(app) as client:
        resp = client.get("/security/execution-packages/?tenant_id=t1")
        assert resp.status_code == 401, (
            "missing tenant in token must be rejected at auth boundary"
        )
