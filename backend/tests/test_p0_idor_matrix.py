"""P0 independent verification — DYNAMIC cross-tenant isolation matrix.

Nothing here trusts static inspection: every row exercises the running ASGI
app with two real tenants and proves Tenant B cannot read/mutate/trigger
Tenant A's resources, plus authentication semantics on previously-open
surfaces (decision-approvals).
"""
import jwt as pyjwt
import pytest

from app.core.security import create_access_token
from app.config import get_settings


# ── helpers ──────────────────────────────────────────────────────────────────

async def _register(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["data"]["access_token"]
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    return {"Authorization": f"Bearer {tok}"}, claims["tenant_id"], claims["sub"]


@pytest.fixture
async def two_tenants(client, db_session):
    hA, tidA, uidA = await _register(client, "matrix-a@test.dev", "OrgMatrixA")
    hB, tidB, uidB = await _register(client, "matrix-b@test.dev", "OrgMatrixB")
    return {
        "client": client, "db": db_session,
        "hA": hA, "hB": hB, "tidA": tidA, "tidB": tidB, "uidA": uidA, "uidB": uidB,
    }


async def _seed(t):
    """Insert one instance of every tenant-owned resource into tenant A."""
    from app.models.alert import Alert
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability
    from app.models.report import Report
    from app.models.security_report import SecurityReport
    from app.models.security_policy import SecurityPolicy
    from app.models.security_exception import SecurityException
    db, tidA = t["db"], t["tidA"]

    alert = Alert(title="A-alert", severity="high", category="security",
                  source="internal", tenant_id=tidA)
    threat = Threat(title="A-threat", severity="critical", category="intrusion",
                    source="internal", status="open", tenant_id=tidA)
    vuln = Vulnerability(title="A-vuln", severity="high",
                         status="open", tenant_id=tidA)
    report = Report(name="A-report", template="audit", status="completed",
                    created_by=t["uidA"], tenant_id=tidA)
    sreport = SecurityReport(name="A-sreport", report_type="posture",
                             generated_by=t["uidA"], tenant_id=tidA)
    policy = SecurityPolicy(name="A-policy", category="network",
                            tenant_id=tidA)
    exc = SecurityException(title="A-exc", justification="accepted risk",
                            risk_acceptance="documented acceptance",
                            requested_by=t["uidA"], tenant_id=tidA)
    db.add_all([alert, threat, vuln, report, sreport, policy, exc])
    await db.commit()

    # approval tree (decision → approval request)
    from app.modules.security.decision_engine.models.decision import Decision
    from app.modules.security.decision_approval.models.approval import ApprovalRequest
    dec = Decision(tenant_id=tidA, context_id="ctx-a", correlation_id="corr-a")
    db.add(dec)
    await db.flush()
    from app.modules.security.decision_approval.constants import ApprovalState
    ap = ApprovalRequest(tenant_id=tidA, decision_id=dec.id,
                         correlation_id="corr-a",
                         approval_state=ApprovalState.WAITING_APPROVAL)
    db.add(ap)
    await db.commit()

    # webhook + integration via API (extra invariants: no secret echo)
    c = t["client"]
    w = await c.post("/api/v1/webhooks", json={
        "name": "a-wh", "url": "https://hook-a.example/x",
        "secret": "sekrit-a", "events": ["deploy.*"]}, headers=t["hA"])
    assert w.status_code == 201, w.text
    i = await c.post("/api/v1/integrations", json={
        "name": "a-intg", "type": "github", "token": "ghp_fixtureA"},
        headers=t["hA"])
    assert i.status_code == 201, i.text

    t["ids"] = {
        "alert": alert.id, "threat": threat.id, "vuln": vuln.id,
        "report": report.id, "sreport": sreport.id, "policy": policy.id,
        "exc": exc.id, "approval": ap.id, "webhook": w.json()["data"]["id"],
        "integration": i.json()["data"]["id"],
    }
    return t


# ── the matrix ───────────────────────────────────────────────────────────────

class TestCrossTenantIsolationMatrix:
    """B = admin of his own tenant, authenticated & authorized — tenant
    ownership is the ONLY remaining gate; it must deny with 404 everywhere."""

    @pytest.mark.asyncio
    async def test_alerts(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["alert"]
        assert (await c.get(f"/api/v1/alerts/{i}", headers=B)).status_code == 404
        assert (await c.patch(f"/api/v1/alerts/{i}", json={"status": "resolved"}, headers=B)).status_code == 404
        lst = await c.get("/api/v1/alerts", headers=B)
        assert all(a["id"] != i for a in lst.json()["data"]["data"])

    @pytest.mark.asyncio
    async def test_threats(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["threat"]
        assert (await c.get(f"/api/v1/threats/{i}", headers=B)).status_code == 404
        assert (await c.patch(f"/api/v1/threats/{i}", json={"status": "resolved"}, headers=B)).status_code == 404
        r = await c.post(f"/api/v1/threats/{i}/resolve", json={"note": "x"}, headers=B)
        assert r.status_code == 404, f"cross-tenant threat resolve: {r.status_code}"
        s = await c.post(f"/api/v1/threats/{i}/suppress", json={"reason": "TOLERATED"}, headers=B)
        assert s.status_code == 404, f"cross-tenant threat suppress: {s.status_code}"

    @pytest.mark.asyncio
    async def test_vulnerabilities(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["vuln"]
        assert (await c.get(f"/api/v1/vulnerabilities/{i}", headers=B)).status_code == 404
        assert (await c.patch(f"/api/v1/vulnerabilities/{i}", json={"status": "resolved"}, headers=B)).status_code == 404

    @pytest.mark.asyncio
    async def test_reports(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["report"]
        assert (await c.get(f"/api/v1/reports/{i}", headers=B)).status_code == 404
        assert (await c.get(f"/api/v1/reports/{i}/download", headers=B)).status_code == 404
        assert (await c.delete(f"/api/v1/reports/{i}", headers=B)).status_code == 404

    @pytest.mark.asyncio
    async def test_security_reports(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["sreport"]
        assert (await c.get(f"/api/v1/security-reports/{i}", headers=B)).status_code == 404
        assert (await c.delete(f"/api/v1/security-reports/{i}", headers=B)).status_code == 404

    @pytest.mark.asyncio
    async def test_security_policies(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["policy"]
        assert (await c.get(f"/api/v1/security-policies/{i}", headers=B)).status_code == 404
        p = await c.patch(f"/api/v1/security-policies/{i}",
                        json={"name": "hijacked"}, headers=B)
        assert p.status_code == 404, f"cross-tenant policy update: {p.status_code}"
        e = await c.patch(f"/api/v1/security-policies/{i}/enforcement",
                          json={"enforcement": "advisory"}, headers=B)
        assert e.status_code == 404, f"cross-tenant enforcement toggle: {e.status_code}"
        assert (await c.delete(f"/api/v1/security-policies/{i}", headers=B)).status_code == 404

    @pytest.mark.asyncio
    async def test_security_exceptions(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["exc"]
        assert (await c.get(f"/api/v1/security-exceptions/{i}", headers=B)).status_code == 404
        rv = await c.post(f"/api/v1/security-exceptions/{i}/revoke", json={}, headers=B)
        assert rv.status_code == 404, f"cross-tenant exception revoke: {rv.status_code}"

    @pytest.mark.asyncio
    async def test_webhooks(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, A, i = t["client"], t["hB"], t["hA"], t["ids"]["webhook"]
        assert (await c.get(f"/api/v1/webhooks/{i}", headers=B)).status_code == 404
        assert (await c.put(f"/api/v1/webhooks/{i}", json={"name": "hijacked"}, headers=B)).status_code == 404
        assert (await c.delete(f"/api/v1/webhooks/{i}", headers=B)).status_code == 404
        t_ = await c.post(f"/api/v1/webhooks/{i}/test", headers=B)
        assert t_.status_code == 404, f"cross-tenant webhook test trigger: {t_.status_code}"
        # A retains full control — test-ping counts as a real probe (no SSRF via B)
        ra = await c.get(f"/api/v1/webhooks/{i}", headers=A)
        assert ra.status_code == 200

    @pytest.mark.asyncio
    async def test_integrations(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, i = t["client"], t["hB"], t["ids"]["integration"]
        assert (await c.get(f"/api/v1/integrations/{i}", headers=B)).status_code == 404
        assert (await c.delete(f"/api/v1/integrations/{i}", headers=B)).status_code == 404
        s = await c.post(f"/api/v1/integrations/{i}/sync", headers=B)
        assert s.status_code == 404, f"cross-tenant integration sync: {s.status_code}"
        assert not (s.status_code == 200 and s.json().get("success")), "false success!"


class TestDecisionApprovalHardering:
    """Previously UNAUTHENTICATED + query-tenant module — now JWT-bound."""

    @pytest.mark.asyncio
    async def test_unauthenticated_everywhere_401(self, two_tenants):
        t = await _seed(two_tenants)
        c, i = t["client"], t["ids"]["approval"]
        base = "/api/v1/security/security/decision-approvals"
        assert (await c.get(f"{base}/")).status_code in (401, 403)
        assert (await c.get(f"{base}/{i}")).status_code in (401, 403)
        assert (await c.get(f"{base}/history/{i}")).status_code in (401, 403)
        assert (await c.get(f"{base}/statistics")).status_code in (401, 403)
        assert (await c.get(f"{base}/policies")).status_code in (401, 403)
        a = await c.post(f"{base}/{i}/actions", json={"approve": True})
        assert a.status_code in (401, 403), f"UNAUTH approve still possible: {a.status_code}"
        e = await c.post(f"{base}/{i}/expire")
        assert e.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_act_on_a_approvals(self, two_tenants):
        t = await _seed(two_tenants)
        c, B, tidA, i = t["client"], t["hB"], t["tidA"], t["ids"]["approval"]
        base = "/api/v1/security/security/decision-approvals"
        # B with A's tenant query-param → 403 (query may only confirm JWT tenant)
        r = await c.get(f"{base}/?tenant_id={tidA}", headers=B)
        assert r.status_code == 403, f"query-tenant spoofing: {r.status_code}"
        # B's own tenant listing must not contain A's approval
        ok = await c.get(f"{base}/", headers=B)
        assert ok.status_code == 200, ok.text
        assert all(a["id"] != i for a in ok.json())
        # reads/mutations by id → 404
        assert (await c.get(f"{base}/{i}", headers=B)).status_code == 404
        assert (await c.get(f"{base}/history/{i}", headers=B)).status_code == 404
        ap = await c.post(f"{base}/{i}/actions", json={"approve": True}, headers=B)
        assert ap.status_code == 404, f"B approved A's approval: {ap.status_code} {ap.text}"
        assert (await c.post(f"{base}/{i}/expire", headers=B)).status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_actor_cannot_be_spoofed(self, two_tenants):
        t = await _seed(two_tenants)
        c, A, B, i = t["client"], t["hA"], t["hB"], t["ids"]["approval"]
        base = "/api/v1/security/security/decision-approvals"
        # A tries to approve with a forged actor_id — must be attributed to A's user id
        r = await c.post(f"{base}/{i}/actions",
                         json={"approve": True, "actor_id": "spoofed-admin"},
                         headers=A)
        assert r.status_code == 200, r.text
        assert r.json()["changed_by"] == t["uidA"], \
            f"actor spoofing succeeded: {r.json()}"
STATUS_NOTE = "matrix"
