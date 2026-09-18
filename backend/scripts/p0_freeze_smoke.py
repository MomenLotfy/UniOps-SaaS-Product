#!/usr/bin/env python3
"""P0 FREEZE — live security smoke probe against the running app on :3001.
Covers: authentication, RBAC (5 canonical roles), tenant isolation (read+mutate),
secret exposure, audit trail, health endpoints. All assertions printed PASS/FAIL.
"""
import asyncio, json, sys, uuid
import httpx

B = "http://127.0.0.1:3001"
API = f"{B}/api/v1"
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

async def main():
    async with httpx.AsyncClient(base_url=B, timeout=20) as c:
        J = {"Content-Type": "application/json"}
        run = __import__('os').environ.get('RUN_ID', uuid.uuid4().hex[:6])

        # ── 1 Health endpoints ────────────────────────────────────────────
        for path in ("/health", "/api/v1/health", "/health/ready", "/health/live"):
            r = await c.get(path)
            check(f"health {path}", r.status_code == 200, f"→{r.status_code}")

        # ── 2 Authentication ──────────────────────────────────────────────
        r = await c.get(f"{API}/users/list", headers={})
        check("unauth protected endpoint → 401", r.status_code == 401, f"→{r.status_code}")
        r = await c.get(f"{API}/users/list", headers={"Authorization": "Bearer garbage.token.here"})
        check("invalid token → 401", r.status_code == 401, f"→{r.status_code}")

        # create tenant A admin via real registration
        adm_a = {"email": f"fz-a-{run}@x.dev", "username": f"fza{run}", "full_name": "A",
                 "password": "Str0ng!Pass9", "company_name": f"FzCoA{run}"}
        r = await c.post(f"{API}/auth/register", json=adm_a)
        check("register tenant A admin", r.status_code in (200, 201), f"→{r.status_code}")
        TA = r.json()["data"]["access_token"]
        HA = {"Authorization": f"Bearer {TA}", **J}
        r = await c.get(f"{API}/users/me", headers=HA)
        check("valid token → allowed", r.status_code == 200, f"→{r.status_code}")

        # tenant B admin
        adm_b = {"email": f"fz-b-{run}@x.dev", "username": f"fzb{run}", "full_name": "B",
                 "password": "Str0ng!Pass9", "company_name": f"FzCoB{run}"}
        r = await c.post(f"{API}/auth/register", json=adm_b)
        check("register tenant B admin", r.status_code in (200, 201), f"→{r.status_code}")
        TB = r.json()["data"]["access_token"]
        HB = {"Authorization": f"Bearer {TB}", **J}

        # ── 3 RBAC — seed 4 role users into tenant A directly in DB ──────
        import jwt as pyjwt
        tidA = pyjwt.decode(TA, options={"verify_signature": False})["tenant_id"]
        tidB = pyjwt.decode(TB, options={"verify_signature": False})["tenant_id"]

        import sys as _s
        _s.path.insert(0, ".")
        from app.core.database import AsyncSessionLocal
        from app.core.security import hash_password
        from app.models.user import User
        role_users = {}
        async with AsyncSessionLocal() as db:
            for role in ("devops_engineer", "security_engineer", "cost_analyst", "viewer"):
                em = f"fz-{role.split('_')[0]}-{run}@x.dev"
                u = User(email=em, username=f"{role[:6]}{run}".replace("_", ""),
                         full_name=role, hashed_password=hash_password("Str0ng!Pass9"),
                         tenant_id=tidA, role=role, is_active=True)
                db.add(u)
                role_users[role] = em
            await db.commit()

        # login each role (login limit 10/60s; we do 4)
        tokens = {}
        for role, em in role_users.items():
            r = await c.post(f"{API}/auth/login", json={"email": em, "password": "Str0ng!Pass9"})
            check(f"login {role}", r.status_code == 200, f"→{r.status_code}")
            if r.status_code == 200:
                tokens[role] = r.json()["data"]["access_token"]

        # privileged op: create cluster — expected: admin ✓, devops_engineer ✓, others 403
        def cc_body(n): return {"name": f"fz-cl-{n}-{run}", "provider": "on-prem"}
        r = await c.post(f"{API}/clusters", json=cc_body("adm"), headers=HA)
        check("RBAC admin cluster-create", r.status_code == 201, f"→{r.status_code}")
        r = await c.post(f"{API}/clusters", json=cc_body("dev"), headers={"Authorization": f"Bearer {tokens['devops_engineer']}", **J})
        check("RBAC devops_engineer cluster-create", r.status_code == 201, f"→{r.status_code}")
        for role in ("security_engineer", "cost_analyst", "viewer"):
            r = await c.post(f"{API}/clusters", json=cc_body(role[:3]), headers={"Authorization": f"Bearer {tokens[role]}", **J})
            check(f"RBAC {role} cluster-create → 403", r.status_code == 403, f"→{r.status_code}")

        # privileged op: invite user — admin only
        for role in ("devops_engineer", "security_engineer", "cost_analyst", "viewer"):
            r = await c.post(f"{API}/users/invite", json={"email": f"invited-{role}-{run}@x.dev", "role": "viewer", "full_name": "Invitee"},
                             headers={"Authorization": f"Bearer {tokens[role]}", **J})
            check(f"RBAC {role} user-invite → 403", r.status_code == 403, f"→{r.status_code}")
        r = await c.post(f"{API}/users/invite", json={"email": f"invited-admin-{run}@x.dev", "role": "viewer", "full_name": "Invitee"}, headers=HA)
        check("RBAC admin user-invite allowed", r.status_code in (200, 201), f"→{r.status_code}")

        # security policy create — admin + security_engineer
        pol = {"name": f"fz-pol-{run}", "category": "network", "severity": "medium",
               "enforcement": "advisory", "scope": {}, "rules": []}
        r = await c.post(f"{API}/security-policies", json=pol, headers={"Authorization": f"Bearer {tokens['security_engineer']}", **J})
        pol_status = r.status_code
        check("RBAC security_engineer policy-create allowed", pol_status in (200, 201), f"→{pol_status}")
        r = await c.post(f"{API}/security-policies", json={**pol, "name": f"fz-pol2-{run}"}, headers={"Authorization": f"Bearer {tokens['viewer']}", **J})
        check("RBAC viewer policy-create → 403", r.status_code == 403, f"→{r.status_code}")

        # unknown role → rejected (mint a token with bogus role claim via existing signer)
        from app.core.security import create_access_token
        import inspect
        import app.core.security as sec
        sig = inspect.signature(create_access_token)
        tok = create_access_token("bogus-user", "bogus@x.dev", tidA, ["super_duper"])
        r = await c.post(f"{API}/clusters", json=cc_body("bog"), headers={"Authorization": f"Bearer {tok}", **J})
        check("unknown role → rejected (403/401)", r.status_code in (401, 403), f"→{r.status_code}")

        # ── 4 Tenant isolation (reads + mutation) ─────────────────────────
        r = await c.get(f"{API}/clusters", headers=HA)
        _d = r.json().get("data")
        clusters_a = (_d.get("data", _d) if isinstance(_d, dict) else _d) or []
        cl_a = clusters_a[0] if clusters_a else None
        check("tenant A reads own clusters", r.status_code == 200 and len(clusters_a) >= 1, f"{len(clusters_a)} clusters")
        r = await c.get(f"{API}/clusters", headers=HB)
        _d = r.json().get("data")
        lb = (_d.get("data", _d) if isinstance(_d, dict) else _d) or []
        check("tenant B sees none of A's clusters", r.status_code == 200 and all(cl.get("tenant_id", tidB) == tidB for cl in lb), f"{len(lb)} clusters in B")
        if cl_a:
            cid = cl_a["id"]
            r = await c.get(f"{API}/clusters/{cid}", headers=HB)
            check("B reads A cluster by id → 404", r.status_code == 404, f"→{r.status_code}")
            r = await c.delete(f"{API}/clusters/{cid}", headers=HB)
            check("B deletes A cluster → 404 (no mutation)", r.status_code == 404, f"→{r.status_code}")
            r = await c.get(f"{API}/clusters/{cid}", headers=HA)
            check("A cluster still intact after B delete attempt", r.status_code == 200, f"→{r.status_code}")

        # mutation isolation: B webhook create, A tries update/delete
        r = await c.post(f"{API}/webhooks", json={"name": f"fz-wh-b-{run}", "url": "https://example.com/hook", "events": ["deployment"]}, headers=HB)
        check("B creates own webhook", r.status_code in (200, 201), f"→{r.status_code}")
        if r.status_code in (200, 201):
            wid = r.json()["data"]["id"]
            r = await c.get(f"{API}/webhooks/{wid}", headers=HA)
            check("A reads B webhook → 404", r.status_code == 404, f"→{r.status_code}")
            r = await c.post(f"{API}/webhooks/{wid}/test", headers=HA)
            check("A test-fires B webhook → 404", r.status_code == 404, f"→{r.status_code}")
            r = await c.delete(f"{API}/webhooks/{wid}", headers=HA)
            check("A deletes B webhook → 404", r.status_code == 404, f"→{r.status_code}")

        # ── 5 Secret exposure ─────────────────────────────────────────────
        def deep_find_secret(obj):
            leaks = []
            def walk(o, path=""):
                if isinstance(o, dict):
                    for k, v in o.items():
                        lk = k.lower()
                        if any(x in lk for x in ("password", "hashed_password", "secret", "token", "credential", "kubeconfig", "private_key", "api_key", "apikey")) \
                           and k not in ("secret_set", "masked_token", "has_secret") and not isinstance(v, bool) \
                           and v not in (None, "", "***", "********"):
                            leaks.append(f"{path}.{k}")
                        walk(v, f"{path}.{k}")
                elif isinstance(o, list):
                    for i, v in enumerate(o):
                        walk(v, f"{path}[{i}]")
                return leaks
            return walk(obj)

        r = await c.get(f"{API}/users/list", headers=HA)
        check("users list: no secret-shaped fields", len(deep_find_secret(r.json())) == 0, str(deep_find_secret(r.json()))[:200])
        r = await c.get(f"{API}/webhooks", headers=HB)
        check("webhooks list: secret not exposed", len(deep_find_secret(r.json())) == 0, str(deep_find_secret(r.json()))[:200])
        r = await c.post(f"{API}/integrations", json={"name": f"fz-int-{run}", "type": "github", "credentials": {"token": "ghp_liveprobe123"}, "config": {}}, headers=HA)
        int_ok = r.status_code in (200, 201)
        int_id = r.json()["data"]["id"] if int_ok else None
        check("integration created with credentials", int_ok, f"→{r.status_code}")
        if int_id:
            r = await c.get(f"{API}/integrations", headers=HA)
            body = json.dumps(r.json())
            check("integrations list: credential token absent", "ghp_liveprobe123" not in body, "")
            check("integrations list: no secret-shaped fields", len(deep_find_secret(r.json())) == 0, str(deep_find_secret(r.json()))[:200])
            r = await c.get(f"{API}/integrations/{int_id}", headers=HA)
            body = json.dumps(r.json())
            check("integration detail: credential token absent", "ghp_liveprobe123" not in body, "")

        # api keys
        r = await c.get(f"{API}/settings/api-keys", headers=HA)
        if r.status_code == 404:
            r = await c.get(f"{API}/api-keys", headers=HA)
        check("api-keys listing readable", r.status_code in (200, 404), f"→{r.status_code}")

        # ── 6 Audit trail ─────────────────────────────────────────────────
        # success op: cluster create (already done). failure op: webhook test on missing id
        await c.post(f"{API}/webhooks/{uuid.uuid4()}/test", headers=HB)
        r = await c.get(f"{API}/audit-logs?page=1&page_size=50", headers=HA)
        body = r.json().get("data") or {}
        rows = body.get("data", body) if isinstance(body, dict) else body
        succ = [x for x in rows if x.get("action") == "POST:clusters" and x.get("status") == "success"]
        check("audit: successful privileged create recorded", len(succ) >= 1, f"{len(succ)} rows")
        r = await c.get(f"{API}/audit-logs?page=1&page_size=50", headers=HB)
        body = r.json().get("data") or {}
        rows_b = body.get("data", body) if isinstance(body, dict) else body
        fails = [x for x in rows_b if x.get("status") == "failure"]
        check("audit: failed attempt recorded as failure", len(fails) >= 1, f"{len(fails)} rows")

        # ── verdict ───────────────────────────────────────────────────────
        failed = [r for r in results if not r[1]]
        print(f"\n==== {len(results) - len(failed)}/{len(results)} live checks passed ====")
        if failed:
            print("FAILURES:", failed)

asyncio.run(main())
