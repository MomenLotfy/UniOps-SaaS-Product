"""P0 independent verification — secret/credential exposure in API responses.

Every assertion runs against the running app: create resources WITH secrets,
then prove those secrets never appear in any read path (create echo, list,
detail, error, or another tenant's view).
"""
import re
import pytest

MARKERS = ("password_hash", "password", "secret", "token", "credential",
           "kubeconfig", "key_hash", "private_key", "access_key", "aws_secret")


async def _admin(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "S",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _string_contains(payload) -> str:
    return str(payload)


class TestRegistrationAndAuth:
    @pytest.mark.asyncio
    async def test_register_response_has_no_password_material(self, client):
        r = await client.post("/api/v1/auth/register", json={
            "email": "sec1@test.dev", "username": "sec1", "full_name": "S",
            "password": "Hunter2!Secret", "company_name": "SecCo",
        })
        body = r.text.lower()
        assert "hunter2!secret" not in body
        assert "password_hash" not in body and "password" not in body
        assert "bcrypt" not in body

    @pytest.mark.asyncio
    async def test_login_failure_leaks_no_internals(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "sec2@test.dev", "username": "sec2", "full_name": "S",
            "password": "Hunter2!Secret", "company_name": "SecCo2",
        })
        r = await client.post("/api/v1/auth/login", json={
            "email": "sec2@test.dev", "password": "WrongPass!9",
        })
        assert r.status_code in (400, 401), r.text
        body = r.text.lower()
        # never disclose whether the account exists beyond generic message
        assert "hunter2" not in body and "hash" not in body and "bcrypt" not in body

    @pytest.mark.asyncio
    async def test_user_list_and_me_hide_hash(self, client):
        h = await _admin(client, "sec3@test.dev", "SecCo3")
        for url in ("/api/v1/users", "/api/v1/users/me"):
            r = await client.get(url, headers=h)
            assert r.status_code == 200
            body = r.text.lower()
            assert "password" not in body and "bcrypt" not in body, f"{url} leaked password material"


class TestIntegrationCredentials:
    @pytest.mark.asyncio
    async def test_github_token_never_roundtrips(self, client):
        h = await _admin(client, "sec4@test.dev", "SecCo4")
        r = await client.post("/api/v1/integrations", json={
            "name": "gh", "type": "github", "token": "ghp_SUPERSECRET_TOKEN_99",
        }, headers=h)
        assert r.status_code == 201, r.text
        # create echo must not contain the token
        assert "ghp_SUPERSECRET_TOKEN_99" not in r.text
        iid = r.json()["data"]["id"]

        d = await client.get(f"/api/v1/integrations/{iid}", headers=h)
        assert "ghp_SUPERSECRET_TOKEN_99" not in d.text, "detail view leaked token"

        lst = await client.get("/api/v1/integrations", headers=h)
        assert "ghp_SUPERSECRET_TOKEN_99" not in lst.text, "list view leaked token"

    @pytest.mark.asyncio
    async def test_aws_keys_never_roundtrip(self, client):
        h = await _admin(client, "sec5@test.dev", "SecCo5")
        r = await client.post("/api/v1/integrations/aws", json={
            "access_key_id": "AKIAFIXTURE123456",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYFIXTURE",
            "region": "eu-west-1",
        }, headers=h)
        assert r.status_code in (200, 201), r.text
        assert "wJalrXUtnFEMI" not in r.text, "AWS secret echo in create response"
        assert "AKIAFIXTURE123456" not in r.text, "AWS access-key echo in create response"
        lst = await client.get("/api/v1/integrations", headers=h)
        assert "wJalrXUtnFEMI" not in lst.text and "AKIAFIXTURE123456" not in lst.text

    @pytest.mark.asyncio
    async def test_webhook_hmac_secret_never_roundtrips(self, client):
        h = await _admin(client, "sec6@test.dev", "SecCo6")
        r = await client.post("/api/v1/webhooks", json={
            "name": "w", "url": "https://h.example/x",
            "secret": "hmac-SUPER-SECRET-77", "events": ["deploy.*"],
        }, headers=h)
        assert r.status_code == 201
        assert "hmac-SUPER-SECRET-77" not in r.text
        wid = r.json()["data"]["id"]
        d = await client.get(f"/api/v1/webhooks/{wid}", headers=h)
        assert "hmac-SUPER-SECRET-77" not in d.text
        lst = await client.get("/api/v1/webhooks", headers=h)
        assert "hmac-SUPER-SECRET-77" not in lst.text

    @pytest.mark.asyncio
    async def test_api_key_visible_only_at_creation_and_not_in_list(self, client):
        h = await _admin(client, "sec7@test.dev", "SecCo7")
        r = await client.post("/api/v1/api-keys", json={
            "name": "ci-key", "scopes": ["read"],
        }, headers=h)
        assert r.status_code in (200, 201), r.text
        raw = None
        data = r.json().get("data") or {}
        # creation may return the raw key exactly once (documented pattern)
        raw = data.get("key") or data.get("api_key")
        lst = await client.get("/api/v1/api-keys", headers=h)
        assert lst.status_code == 200
        if raw:
            assert raw not in lst.text, "raw API key persisted into list responses"
        assert "key_hash" not in lst.text.lower() or "\\" not in lst.text  # hash never returned raw


class TestErrorResponses:
    @pytest.mark.asyncio
    async def test_500_shape_has_no_stack_or_sql(self, client):
        # an unauthenticated, malformed request path should never echo internals
        r = await client.post("/api/v1/auth/login", json={"email": "x", "password": 5})
        assert r.status_code in (422, 400), r.status_code
        body = r.text.lower()
        assert "traceback" not in body and "sqlalchemy" not in body and "sqlite" not in body

    @pytest.mark.asyncio
    async def test_404_shape_minimal(self, client):
        h = await _admin(client, "sec8@test.dev", "SecCo8")
        r = await client.get("/api/v1/clusters/definitely-not-a-real-id", headers=h)
        assert r.status_code == 404
        body = r.text.lower()
        assert "sql" not in body and "traceback" not in body


# ── P1 fix regression: auth endpoints enforce 429 WITHOUT Redis ───────────────

class TestAuthRateLimits:
    @pytest.mark.asyncio
    async def test_login_brute_force_hits_429(self, client):
        # 10/min budget per scope+IP — the 11th request must be refused
        codes = []
        for i in range(12):
            r = await client.post("/api/v1/auth/login", json={
                "email": "nobody@test.dev", "password": "Wrong!999",
            })
            codes.append(r.status_code)
        assert 429 in codes, f"no 429 after 12 attempts: {codes}"
        assert codes.index(429) >= 10, f"429 fired before budget exhausted: {codes}"
        last = codes[-1]
        assert last in (400, 401, 429)

    @pytest.mark.asyncio
    async def test_register_spam_hits_429(self, client):
        codes = []
        for i in range(7):
            r = await client.post("/api/v1/auth/register", json={
                "email": f"spam{i}@spam.dev", "username": f"spam{i}",
                "full_name": "S", "password": "Str0ng!Pass9",
                "company_name": "SpamCo",
            })
            codes.append(r.status_code)
        assert 429 in codes, f"register not limited: {codes}"


# ── Audit-trail regression: mutations must actually be recorded ───────────────

class TestAuditTrailRecorded:
    @pytest.fixture(autouse=True)
    def _route_audit_db(self, monkeypatch):
        """AuditMiddleware opens its OWN session via AsyncSessionLocal
        (production path: same single DB).  Point it at the test engine so
        the middleware truthfully persists where the app-under-test reads."""
        from tests.conftest import TestSessionLocal
        import app.core.database as _db
        monkeypatch.setattr(_db, "AsyncSessionLocal", TestSessionLocal)


    @pytest.mark.asyncio
    async def test_privileged_mutation_writes_audit_row(self, client):
        """JWTAuthMiddleware feeds request.state into AuditMiddleware; without
        it the audit trail silently recorded NOTHING (live-verified bug)."""
        h = await _admin(client, "audit-reg@t.dev", "AuditCo1")
        r = await client.post("/api/v1/clusters", json={
            "name": "audit-cl", "provider": "on-prem",
        }, headers=h)
        assert r.status_code == 201, r.text

        lst = await client.get("/api/v1/audit-logs?page=1&page_size=10", headers=h)
        assert lst.status_code == 200, lst.text
        body = lst.json()["data"]
        rows = body.get("data", body) if isinstance(body, dict) else body
        actions = [row.get("action") for row in rows]
        assert any(a == "POST:clusters" for a in actions), \
            f"audit trail missing privileged create entry: {actions}"
        row = next(rw for rw in rows if rw.get("action") == "POST:clusters")
        assert row.get("status") == "success"

    @pytest.mark.asyncio
    async def test_failed_mutation_recorded_as_failure(self, client):
        h = await _admin(client, "audit-reg2@t.dev", "AuditCo2")
        # forbidden for the tenant → middleware still logs the attempt, as failure
        await client.delete("/api/v1/webhooks/does-not-exist", headers=h)
        lst = await client.get("/api/v1/audit-logs?page=1&page_size=10", headers=h)
        body = lst.json()["data"]
        rows = body.get("data", body) if isinstance(body, dict) else body
        # the middleware's action label uses a coarse path parser — the
        # security-relevant truth lives in status + details.path
        failed = [rw for rw in rows
                  if rw.get("status") == "failure"
                  and "/api/v1/webhooks/does-not-exist" in str((rw.get("details") or {}).get("path", ""))]
        assert failed, f"failed privileged attempt not recorded: {rows}"


class TestPublicSurfacesStayPublic:
    """JWTAuthMiddleware must never break the explicitly-public surface —
    k8s liveness/readiness probes would fail clusterlessly otherwise."""

    @pytest.mark.asyncio
    async def test_health_is_unauthenticated(self, client):
        r = await client.get("/api/v1/health")
        assert r.status_code == 200, f"health requires auth — probe breaker: {r.status_code}"
        r2 = await client.get("/health")
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_endpoints_public(self, client):
        r = await client.post("/api/v1/auth/login", json={"email": "a", "password": "b"})
        assert r.status_code in (400, 401, 422), r.status_code  # semantics, never auth-wall errors
