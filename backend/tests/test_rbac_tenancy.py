"""P0 production hardening: canonical RBAC normalization + tenant isolation.

Covers:
  1. Legacy role aliases (devops/security/finops) normalized to canonical
     names at EVERY boundary (JWT parse, invite validation, updates).
  2. Authorized-can / unauthorized-403 for a devops-mutation endpoint.
  3. Invitation listing/revoke is strictly tenant-scoped (no IDOR).
  4. Unknown roles are rejected — new data is ALWAYS canonical.
"""
import pytest

from app.core.security import create_access_token
from app.constants.roles import (
    normalize_role, normalize_roles, is_valid_role, LEGACY_ROLE_ALIASES, ROLES,
)
from app.schemas.user import UserInvite


# ── 1. Normalization layer (unit) ────────────────────────────────────────────

class TestLegacyRoleNormalization:
    def test_alias_map_matches_contract(self):
        assert LEGACY_ROLE_ALIASES == {
            "devops": "devops_engineer",
            "security": "security_engineer",
            "finops": "cost_analyst",
        }

    def test_normalize_legacy_roles(self):
        assert normalize_role("devops") == "devops_engineer"
        assert normalize_role("security") == "security_engineer"
        assert normalize_role("finops") == "cost_analyst"

    def test_canonical_roles_pass_through(self):
        for r in ("admin", "devops_engineer", "security_engineer", "cost_analyst", "viewer"):
            assert normalize_role(r) == r

    def test_normalize_roles_dedups_and_merges(self):
        # A user migrated mid-session may hold both the legacy alias and the
        # canonical target — they must collapse to one canonical entry.
        assert normalize_roles(["devops", "devops_engineer", "viewer"])[:2] == ["devops_engineer", "viewer"]

    def test_unknown_role_is_invalid(self):
        assert not is_valid_role("ceo")
        assert not is_valid_role("superuser")
        assert is_valid_role("admin")

    def test_every_canonical_role_registered(self):
        for r in ROLES:
            assert is_valid_role(r)


class TestInviteSchemaRoleValidation:
    def test_legacy_invite_role_normalized_to_canonical(self):
        inv = UserInvite(email="a@b.co", role="devops", full_name="Legacy Person")
        assert inv.role == "devops_engineer"
        inv2 = UserInvite(email="b@b.co", role="finops", full_name="Fin Ops")
        assert inv2.role == "cost_analyst"

    def test_unknown_invite_role_rejected(self):
        with pytest.raises(Exception):
            UserInvite(email="x@b.co", role="god_mode", full_name="Nope")

    def test_default_role_is_viewer(self):
        assert UserInvite(email="c@b.co", full_name="Default").role == "viewer"

    def test_canonical_roles_accepted(self):
        for r in ("admin", "devops_engineer", "security_engineer", "cost_analyst", "viewer"):
            assert UserInvite(email="d@b.co", role=r, full_name="Ok").role == r


# ── 2. JWT parse normalization (e2e through the dependency) ──────────────────

class TestJwtRoleNormalizationE2E:
    """get_current_user must normalize legacy roles → require_devops sees
    ONLY canonical names; authorized-can / unauthorized-403."""

    def _tok(self, roles, tenant="tenant-rbac-1"):
        token = create_access_token(
            user_id="user-rbac-1", email="rbac@test.dev",
            tenant_id=tenant, roles=roles,
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_legacy_devops_role_allowed_for_mutation(self, client):
        # Legacy alias must still authorize (normalized at JWT parse). The
        # call proceeds past RBAC and fails only because no real cluster
        # exists — never 403 for an authorized role.
        r = await client.post("/api/v1/clusters", json={
            "name": "rbac-probe", "provider": "on-prem",
        }, headers=self._tok(["devops"]))
        assert r.status_code != 403, f"legacy alias wrongly forbidden: {r.text}"

    @pytest.mark.asyncio
    async def test_canonical_devops_engineer_allowed(self, client):
        r = await client.post("/api/v1/clusters", json={
            "name": "rbac-probe", "provider": "on-prem",
        }, headers=self._tok(["devops_engineer"]))
        assert r.status_code != 403

    @pytest.mark.asyncio
    async def test_viewer_forbidden_from_mutation(self, client):
        r = await client.post("/api/v1/clusters", json={
            "name": "rbac-probe", "provider": "on-prem",
        }, headers=self._tok(["viewer"]))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_role_forbidden(self, client):
        r = await client.post("/api/v1/clusters", json={
            "name": "rbac-probe", "provider": "on-prem",
        }, headers=self._tok(["root"]))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allowed(self, client):
        r = await client.post("/api/v1/clusters", json={
            "name": "rbac-probe", "provider": "on-prem",
        }, headers=self._tok(["admin"]))
        assert r.status_code != 403


# ── 3. Invitations: real Redis-backed list/revoke, tenant-scoped ─────────────

async def _admin_client(client, email: str, org: str):
    username = email.split("@")[0].replace(".", "_").replace("-", "_")
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass", "company_name": org,
    })
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestInvitationsTenancy:
    @pytest.mark.asyncio
    async def test_invite_happy_path_and_list(self, client):
        h = await _admin_client(client, "invadmin-a@test.dev", "OrgAlpha")
        r = await client.post("/api/v1/users/invite", json={
            "email": "newbie-a@test.dev", "role": "devops",  # legacy → canonical
            "full_name": "New Person",
        }, headers=h)
        assert r.status_code == 201, r.text

        lst = await client.get("/api/v1/users/invitations", headers=h)
        assert lst.status_code == 200
        invites = lst.json()["data"]
        rows = [i for i in invites if i["email"] == "newbie-a@test.dev"]
        assert rows, f"invite missing from tenant listing: {invites}"
        assert rows[0]["role"] == "devops_engineer"  # canonical on the wire
        assert rows[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_or_revoke_tenant_a_invites(self, client):
        hA = await _admin_client(client, "invadmin-a2@test.dev", "OrgAlpha2")
        hB = await _admin_client(client, "invadmin-b2@test.dev", "OrgBeta2")

        r = await client.post("/api/v1/users/invite", json={
            "email": "victim-a@test.dev", "role": "viewer", "full_name": "Victim A",
        }, headers=hA)
        assert r.status_code == 201, r.text

        lstA = await client.get("/api/v1/users/invitations", headers=hA)
        row = next((i for i in lstA.json()["data"] if i["email"] == "victim-a@test.dev"), None)
        assert row, "Tenant A should see its own invite"

        lstB = await client.get("/api/v1/users/invitations", headers=hB)
        assert all(i["email"] != "victim-a@test.dev" for i in lstB.json()["data"]), \
            "TENANT ISOLATION VIOLATION: B can see A's invitations"

        # B guessing A's invite id must get 404 — never an indication of existence
        rb = await client.delete(f"/api/v1/users/invitations/{row['id']}", headers=hB)
        assert rb.status_code == 404, f"B must not revoke A's invitation: {rb.status_code}"

        # A can still revoke its own
        ra = await client.delete(f"/api/v1/users/invitations/{row['id']}", headers=hA)
        assert ra.status_code == 200, ra.text
        lstA2 = await client.get("/api/v1/users/invitations", headers=hA)
        assert all(i["email"] != "victim-a@test.dev" for i in lstA2.json()["data"])

    @pytest.mark.asyncio
    async def test_non_admin_cannot_invite(self, client):
        h = {"Authorization": "Bearer " + create_access_token(
            user_id="u-view", email="view@test.dev", tenant_id="tenant-noinvite",
            roles=["viewer"])}
        r = await client.post("/api/v1/users/invite", json={
            "email": "ghost@test.dev", "role": "viewer", "full_name": "Ghost",
        }, headers=h)
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_invite_unknown_role_422(self, client):
        h = await _admin_client(client, "invadmin-a3@test.dev", "OrgAlpha3")
        r = await client.post("/api/v1/users/invite", json={
            "email": "bad-role@test.dev", "role": "overlord", "full_name": "Bad Role",
        }, headers=h)
        assert r.status_code == 422, r.text


# ── 4. Cross-tenant resource isolation (clusters — the tenant-owned root) ────

class TestClusterTenantIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_update_delete_tenant_a_cluster(self, client):
        hA = await _admin_client(client, "clusteradmin-a@test.dev", "OrgAClusters")
        hB = await _admin_client(client, "clusteradmin-b@test.dev", "OrgBClusters")

        # A registers a cluster
        r = await client.post("/api/v1/clusters", json={
            "name": "cluster-a-private", "provider": "on-prem", "region": "me-central",
        }, headers=hA)
        assert r.status_code == 201, r.text
        cluster_id = r.json()["data"]["id"]

        # B must not see it in listings
        lstB = await client.get("/api/v1/clusters", headers=hB)
        assert all(c["id"] != cluster_id for c in lstB.json()["data"]), \
            "TENANT ISOLATION VIOLATION: B listed A's cluster"

        # B must not read / update / delete it — 404, never existence leak
        for method in ("get", "patch", "delete"):
            kwargs = {} if method != "patch" else {"json": {"region": "hijacked"}}
            resp = await getattr(client, method)(f"/api/v1/clusters/{cluster_id}", headers=hB, **kwargs)
            assert resp.status_code == 404, \
                f"TENANT ISOLATION VIOLATION: B {method.upper()} A's cluster → {resp.status_code}"

        # A still can read its own
        rA = await client.get(f"/api/v1/clusters/{cluster_id}", headers=hA)
        assert rA.status_code == 200, rA.text

    @pytest.mark.asyncio
    async def test_tenant_id_from_body_is_ignored(self, client):
        """Mandate: never trust tenant_id from request body/query — the JWT
        tenant must win even if a caller tries to smuggle another tenant id."""
        hA = await _admin_client(client, "spoof-a@test.dev", "OrgSpoofA")
        hB = await _admin_client(client, "spoof-b@test.dev", "OrgSpoofB")

        # B creates a cluster; A tries to create one *for B's tenant* by
        # stuffing tenant_id in the body — the row must land in A's tenant.
        rB = await client.post("/api/v1/clusters", json={
            "name": "cluster-b", "provider": "eks",
        }, headers=hB)
        assert rB.status_code == 201, rB.text
        tenant_b = rB.json()["data"].get("tenant_id")

        rA = await client.post("/api/v1/clusters", json={
            "name": "cluster-a-attack", "provider": "eks",
            "tenant_id": tenant_b,  # smuggling attempt — must be ignored
        }, headers=hA)
        assert rA.status_code == 201, rA.text
        row = rA.json()["data"]
        assert row.get("tenant_id") != tenant_b or row.get("tenant_id") is None, \
            f"BODY-SMUGGLING ACCEPTED: row landed in victim tenant {row.get('tenant_id')}"


# ── 5. Webhooks: cross-tenant IDOR regression + secret redaction ─────────────

class TestWebhookTenantIsolation:
    @pytest.mark.asyncio
    async def test_tenant_b_cannot_read_update_delete_a_webhook(self, client):
        hA = await _admin_client(client, "whadmin-a@test.dev", "OrgWhA")
        hB = await _admin_client(client, "whadmin-b@test.dev", "OrgWhB")

        r = await client.post("/api/v1/webhooks", json={
            "name": "a-webhook", "url": "https://hooks-a.example/evt",
            "secret": "supersecret-a", "events": ["deploy.*"],
        }, headers=hA)
        assert r.status_code == 201, r.text
        wid = r.json()["data"]["id"]

        # Secret must never leave the API surface — including the create echo
        assert "secret" not in r.json()["data"], "webhook secret leaked in create response"
        assert r.json()["data"]["has_secret"] is True

        # List responses redact the secret too
        lst = await client.get("/api/v1/webhooks", headers=hA)
        assert all("secret" not in w for w in lst.json()["data"]["data"])

        # Cross-tenant: read/update/delete must all 404
        for method, kwargs in [("get", {}), ("put", {"json": {"name": "hijacked"}}), ("delete", {})]:
            resp = await getattr(client, method)(f"/api/v1/webhooks/{wid}", headers=hB, **kwargs)
            assert resp.status_code == 404, \
                f"IDOR: B {method.upper()} A's webhook → {resp.status_code}"

        # A's webhook untouched
        g = await client.get(f"/api/v1/webhooks/{wid}", headers=hA)
        assert g.status_code == 200 and g.json()["data"]["name"] == "a-webhook"


# ── 6. Service-layer IDOR guards: users + integrations (mutations, sync) ─────

class TestUserAndIntegrationIsolation:
    @pytest.mark.asyncio
    async def test_admin_b_cannot_read_or_deactivate_tenant_a_user(self, client):
        hA = await _admin_client(client, "useradmin-a@test.dev", "OrgUsersA")
        hB = await _admin_client(client, "useradmin-b@test.dev", "OrgUsersB")

        lstA = await client.get("/api/v1/users", headers=hA)
        assert lstA.status_code == 200, lstA.text
        rows = lstA.json()["data"]
        # PaginatedResponse uses data["data"] for the items list
        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("data") or []
        user_a_id = rows[0]["id"]

        g = await client.get(f"/api/v1/users/{user_a_id}", headers=hB)
        assert g.status_code == 404, f"cross-tenant PII read: {g.status_code}"

        d = await client.delete(f"/api/v1/users/{user_a_id}", headers=hB)
        assert d.status_code == 404, f"cross-tenant deactivate: {d.status_code}"

        # A can still read its own user
        gA = await client.get(f"/api/v1/users/{user_a_id}", headers=hA)
        assert gA.status_code == 200, gA.text

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_use_tenant_a_integration(self, client):
        hA = await _admin_client(client, "intgadmin-a@test.dev", "OrgIntgA")
        hB = await _admin_client(client, "intgadmin-b@test.dev", "OrgIntgB")

        r = await client.post("/api/v1/integrations", json={
            "name": "a-github", "type": "github", "token": "ghp_test_fixture_0001",
        }, headers=hA)
        assert r.status_code == 201, r.text
        intg_id = r.json()["data"]["id"]

        # read / update / delete / sync endpoints must all 404 for B
        g = await client.get(f"/api/v1/integrations/{intg_id}", headers=hB)
        assert g.status_code == 404, f"B read A's integration → {g.status_code}"
        d = await client.delete(f"/api/v1/integrations/{intg_id}", headers=hB)
        assert d.status_code == 404, f"B delete A's integration → {d.status_code}"
        s = await client.post(f"/api/v1/integrations/{intg_id}/sync", headers=hB)
        assert s.status_code in (404, 403), f"B sync A's integration → {s.status_code}"
        if s.status_code != 404:
            # RBAC-only stop is acceptable, but an undesirable false-success is not
            assert not s.json().get("success"), "cross-tenant sync started!"

        # A's integration still visible to A
        gA = await client.get(f"/api/v1/integrations/{intg_id}", headers=hA)
        assert gA.status_code == 200, gA.text
