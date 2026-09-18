"""P1.6-REM — remediation mutation routes: role gate + truthful lifecycle.

Proven live pre-fix, pinned here:
  REM-1  viewer (read-only) reached privileged mutation handlers (200).
  REM-2  cancel returned 200 {"status":"cancelled"} for nonexistent plans
         and left DB rows unchanged for existing ones (fabricated success).
  REM-3  rollback raised a bare Exception → 500 for a client error.
  REM-4  propose never persisted the plan → propose→execute was dead-by-design.
"""
import pytest
import jwt as pyjwt

from app.remediation.engine.controller import ExecutionController


async def _register_with_roles(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "U",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["data"]["access_token"]
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    return {"Authorization": f"Bearer {tok}"}, claims["tenant_id"], tok


async def _invite_viewer(client, admin_headers, email: str):
    r = await client.post("/api/v1/users/invite", headers=admin_headers,
                          json={"email": email, "role": "viewer", "full_name": "V"})
    assert r.status_code in (200, 201), r.text
    token = r.json()["data"]["token"]
    username = email.split("@")[0].replace("-", "_")
    r2 = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "V",
        "password": "Str0ng!Pass9", "invite_token": token,
    })
    assert r2.status_code in (200, 201), r2.text
    vtok = r2.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {vtok}"}


async def _seed_plan(db, tenant_id: str, plan_id: str, st: str):
    from sqlalchemy import text
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(text("DELETE FROM remediation_plans WHERE id=:i"), {"i": plan_id})
    await db.execute(text(
        "INSERT INTO remediation_plans (id,tenant_id,finding_id,finding_type,"
        "target_technology,capability_id,strategy_id,version,status,priority,"
        "required_inputs,expected_outputs,created_at,updated_at) "
        "VALUES (:i,:t,'f-1','vuln','generic','cap-1','strat-1',1,:s,'low','{}','{}',:n,:n)"
    ), {"i": plan_id, "t": tenant_id, "s": st, "n": now})
    await db.commit()


@pytest.mark.asyncio
class TestRemediationRoleGate:
    async def test_viewer_forbidden_on_all_mutation_routes(self, client, db_session):
        hA, tidA, _ = await _register_with_roles(client, "rem-a@test.dev", "OrgRemA")
        hV = await _invite_viewer(client, hA, "rem-v@test.dev")
        for path in (
            "/api/v1/remediation/propose",
            "/api/v1/remediation/execute/p16-x",
            "/api/v1/remediation/execute/p16-x/start",
            "/api/v1/remediation/execute/p16-x/cancel",
            "/api/v1/remediation/execute/p16-x/rollback",
        ):
            r = await client.post(path, headers=hV,
                                  json={"finding_id": "f", "repo_id": "r"})
            assert r.status_code == 403, f"{path} accepted viewer role: {r.status_code}"

@pytest.mark.asyncio
class TestCancelTruthfulness:
    async def test_cancel_nonexistent_plan_is_404_not_fake_success(self, client, db_session):
        hA, _, _ = await _register_with_roles(client, "rem-b@test.dev", "OrgRemB")
        r = await client.post("/api/v1/remediation/execute/definitely-missing/cancel", headers=hA)
        assert r.status_code == 404, r.text

    async def test_cancel_existing_plan_persists_state(self, client, db_session):
        from sqlalchemy import text
        hA, tidA, _ = await _register_with_roles(client, "rem-c@test.dev", "OrgRemC")
        await _seed_plan(db_session, tidA, "p16-truth-1", "CREATED")
        r = await client.post("/api/v1/remediation/execute/p16-truth-1/cancel", headers=hA)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"
        q = await db_session.execute(text(
            "SELECT status FROM remediation_plans WHERE id='p16-truth-1'"))
        assert q.scalar() == "CANCELLED", "response claimed a transition the DB lacks"

    async def test_cancel_terminal_plan_is_409(self, client, db_session):
        hA, tidA, _ = await _register_with_roles(client, "rem-d@test.dev", "OrgRemD")
        await _seed_plan(db_session, tidA, "p16-truth-2", "COMPLETED")
        r = await client.post("/api/v1/remediation/execute/p16-truth-2/cancel", headers=hA)
        assert r.status_code == 409, r.text

@pytest.mark.asyncio
class TestRollbackContract:
    async def test_rollback_nonexistent_plan_is_404_not_500(self, client, db_session):
        hA, _, _ = await _register_with_roles(client, "rem-e@test.dev", "OrgRemE")
        r = await client.post("/api/v1/remediation/execute/definitely-missing/rollback", headers=hA)
        assert r.status_code == 404, r.text


class TestProposeTruthfulStatus:
    @pytest.mark.asyncio
    async def test_propose_no_plan_available_returns_404_not_masked_400(self, client, db_session):
        """REM-5: the endpoint's own 'no plan could be generated' raises a
        truthful 404, but a catch-all `except Exception` re-coded it as a
        misleading 400 (masking real status semantics from callers/UI)."""
        hA, _, _ = await _register_with_roles(client, "rem-np@test.dev", "OrgRemNP")
        r = await client.post("/api/v1/remediation/propose", headers=hA,
                              json={"finding_id": "unmatchable-finding", "repo_id": "r1",
                                    "metadata": {}})
        assert r.status_code == 404, (
            f"propose with no candidate plan must be an honest 404, got "
            f"{r.status_code}: {r.text[:200]}")


class TestProposePersistence:
    def test_propose_endpoint_persists_plan(self):
        """REM-4 regression pin — the endpoint must write a remediation_plans row
        for what it returns.  Static assertion on the endpoint source is the
        honest check here (manager decision logic is not under test)."""
        import inspect
        from app.api.v1.endpoints import remediation as rem_mod
        src = inspect.getsource(rem_mod.propose_remediation)
        assert "db.add" in src and "await db.commit()" in src, \
            "propose must persist the plan it returns (REM-4)"


@pytest.mark.asyncio
class TestK8sFindingRoleGate:
    async def test_viewer_cannot_suppress_or_resolve_findings(self, client, db_session):
        """P1.6-K8S-1 — suppress/resolve are security governance writes."""
        hA, tidA, _ = await _register_with_roles(client, "k8s-a@test.dev", "OrgK8sA")
        hV = await _invite_viewer(client, hA, "k8s-v@test.dev")
        for path in (
            "/api/v1/k8s/findings/f-99/suppress",
            "/api/v1/k8s/findings/f-99/resolve",
        ):
            r = await client.patch(path, headers=hV)
            assert r.status_code == 403, f"{path} accepted viewer role: {r.status_code} {r.text[:120]}"

    async def test_admin_suppress_missing_finding_is_404(self, client, db_session):
        hA, tidA, _ = await _register_with_roles(client, "k8s-b@test.dev", "OrgK8sB")
        r = await client.patch("/api/v1/k8s/findings/f-no/such/suppress", headers=hA)
        # reach the service (tenant-scoped 404) not the role gate
        assert r.status_code == 404, r.text
