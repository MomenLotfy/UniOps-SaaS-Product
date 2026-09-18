"""P0 independent verification — canonical RBAC grid across privileged ops.

For every privileged operation we prove, dynamically:
  - authorized canonical role → NOT 403 (the request reaches the service —
    infra may legitimately fail afterwards with 4xx/5xx; 403 is RBAC denial)
  - every other canonical role → 403
  - unknown role → 403
  - legacy alias → NOT 403 (temporary normalization layer)
"""
import pytest

from app.core.security import create_access_token


def hdr(roles, tenant="t-grid", uid="u-grid"):
    return {"Authorization": "Bearer " + create_access_token(
        user_id=uid, email=f"{uid[:6]}@grid.dev", tenant_id=tenant, roles=roles)}


CANONICAL = ["admin", "devops_engineer", "security_engineer", "cost_analyst", "viewer"]

# (method, url, json_body, allowed_roles)
GRID = [
    ("post", "/api/v1/clusters",
     {"name": "grid-cluster", "provider": "on-prem"},
     {"admin", "devops_engineer"}),
    ("post", "/api/v1/users/invite",
     {"email": "grid-inv@test.dev", "role": "viewer", "full_name": "Grid V"},
     {"admin"}),
    ("post", "/api/v1/webhooks",
     {"name": "grid-wh", "url": "https://grid.example/hook", "events": ["deploy.*"]},
     {"admin"}),
    ("post", "/api/v1/security-policies",
     {"name": "grid-pol", "category": "network", "description": "grid", "rules": []},
     {"admin", "security_engineer"}),
    ("post", "/api/v1/catalog/services",
     {"name": "grid-svc", "type": "Microservice", "tech_stack": "Python",
      "git_repo": "https://git.example/a/b.git", "cluster": "c", "namespace": "default"},
     {"admin", "devops_engineer", "developer"}),
]


class TestCanonicalRbacGrid:
    @pytest.mark.parametrize("method,url,body,allowed", GRID)
    @pytest.mark.asyncio
    async def test_grid(self, client, method, url, body, allowed):
        for role in CANONICAL:
            r = await getattr(client, method)(url, json=body, headers=hdr([role]))
            if role in allowed:
                assert r.status_code != 403, \
                    f"{role} should be authorized for {method.upper()} {url}, got 403"
            else:
                assert r.status_code == 403, \
                    f"TENANT/RBAC ESCALATION: {role} got {r.status_code} on {method.upper()} {url}"
        # unknown role never passes
        r = await getattr(client, method)(url, json=body, headers=hdr(["supreme_root"]))
        assert r.status_code == 403, f"unknown role not rejected on {url}: {r.status_code}"


class TestLegacyNormalization:
    @pytest.mark.asyncio
    async def test_legacy_devops_normalized_for_devops_gate(self, client):
        r = await client.post("/api/v1/clusters", json={
            "name": "lg1", "provider": "on-prem"}, headers=hdr(["devops"]))
        assert r.status_code != 403, "legacy 'devops' rejected — normalization broken"

    @pytest.mark.asyncio
    async def test_legacy_security_normalized_for_security_gate(self, client):
        r = await client.post("/api/v1/security-policies", json={
            "name": "lg-pol", "category": "network", "description": "x", "rules": [],
        }, headers=hdr(["security"]))
        assert r.status_code != 403, "legacy 'security' rejected — normalization broken"

    @pytest.mark.asyncio
    async def test_legacy_alias_does_not_gain_admin_scope(self, client):
        # legacy devops must NOT inherit admin-only privileges
        r = await client.post("/api/v1/users/invite", json={
            "email": "lgx@test.dev", "role": "viewer", "full_name": "L",
        }, headers=hdr(["devops"]))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_auth_still_401(self, client):
        for method, url, body, _ in GRID:
            r = await getattr(client, method)(url, json=body)
            assert r.status_code == 401, f"{url}: unauthenticated → {r.status_code}"

class TestPrivilegedOpsGates:
    """Negative-only probes: these ops must deny insufficient roles with 403
    BEFORE touching any infra (404/200 reachable only for authorized roles)."""

    PRIV = [
        ("post", "/api/v1/pipelines/x-id/rerun", None),
        ("post", "/api/v1/pipelines/x-id/cancel", None),
        ("post", "/api/v1/gitops/no-such-app/sync", {}),
        ("post", "/api/v1/gitops/no-such-app/rollback", {}),
    ]

    @pytest.mark.asyncio
    async def test_non_devops_roles_forbidden_everywhere(self, client):
        for method, url, body in self.PRIV:
            for role in ("viewer", "cost_analyst", "security_engineer"):
                kwargs = {"json": body} if body else {}
                r = await getattr(client, method)(url, headers=hdr([role]), **kwargs)
                assert r.status_code == 403,                     f"RBAC BYPASS: {role} on {url} → {r.status_code}"
            r401 = await getattr(client, method)(url, json=body or {})
            assert r401.status_code == 401

    @pytest.mark.asyncio
    async def test_devops_engineer_passes_rbac_these_ops(self, client):
        # RBAC must allow (then the service legitimately 404s: no such pipeline)
        for method, url, body in [
            ("post", "/api/v1/pipelines/no-such-id/rerun", None),
            ("post", "/api/v1/pipelines/no-such-id/cancel", None),
        ]:
            r = await getattr(client, method)(url, headers=hdr(["devops_engineer"]))
            assert r.status_code in (404, 400, 409),                 f"unexpected code for authorized role: {r.status_code} {r.text[:150]}"
            assert r.status_code != 403
