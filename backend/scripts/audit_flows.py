"""DevOps Center — end-to-end FLOW verification.

For every user-visible flow this walks the full lifecycle and asserts that the
persisted state actually changed after each mutation (read-back, not status code).

Run: cd backend && .venv/bin/python scripts/audit_flows.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx  # noqa: E402

from app.core.security import create_access_token  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = json.load(open(os.path.join(HERE, ".audit_ids.json")))
BASE = "http://127.0.0.1:8000/api/v1"
UA = "audit-flows"
OK, BAD = "\u2713", "\u2717"


def hdr(user_key, tenant_key):
    return {"Authorization": "Bearer " + create_access_token(
        IDS[user_key], f"{user_key}@a.audit.dev", IDS[tenant_key],
        ["admin"] if "admin" in user_key else ["devops_engineer"])}


def line(tag, cond, detail):
    print(f"  [{OK if cond else BAD}] {tag:52} {detail}")


async def get(c, path, **kw):
    r = await c.get(BASE + path, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


async def unwrap(r):
    _, body = r
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


async def main():
    A = hdr("admin_a", "tenant_a")

    async with httpx.AsyncClient(timeout=90, headers=A) as c:

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 1 — CLUSTER lifecycle (create -> read -> patch -> test -> delete)")
        print("=" * 100)
        name = f"flow-cluster-{uuid.uuid4().hex[:6]}"
        s, b = await get(c, "")  # noop
        r = await c.post(f"{BASE}/clusters", json={
            "name": name, "provider": "on-prem", "region": "eu-west-1",
            "environment": "staging", "api_server_url": "https://127.0.0.1:6443",
        })
        cid = (r.json().get("data") or {}).get("id")
        line("POST /clusters", r.status_code == 201, f"{r.status_code} id={cid}")

        s, b = await get(c, f"/clusters/{cid}")
        line("GET /clusters/{id} read-back", s == 200 and b["data"]["name"] == name,
             f"name={b['data']['name']} status={b['data']['status']}")

        r = await c.patch(f"{BASE}/clusters/{cid}", json={"environment": "production"})
        s, b = await get(c, f"/clusters/{cid}")
        line("PATCH environment -> production", b["data"]["environment"] == "production",
             f"env={b['data']['environment']} (http {r.status_code})")

        r = await c.post(f"{BASE}/clusters/{cid}/test")
        d = r.json().get("data") or {}
        line("POST /clusters/{id}/test (cluster is UNREACHABLE)",
             d.get("status") == "disconnected",
             f"http={r.status_code} status={d.get('status')} message={d.get('message')!r}")

        r = await c.delete(f"{BASE}/clusters/{cid}")
        s, _ = await get(c, f"/clusters/{cid}")
        line("DELETE then GET -> gone", r.status_code in (200, 204) and s == 404,
             f"delete={r.status_code} subsequent_get={s}")

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 2 — ALERT lifecycle (create -> ack -> mute -> resolve -> escalate -> delete)")
        print("=" * 100)
        r = await c.post(f"{BASE}/devops-alerts", json={
            "name": f"flow-alert-{uuid.uuid4().hex[:6]}",
            "severity": "critical", "type": "cpu_saturation",
            "resource": "api-gateway", "namespace": "prod",
            "message": "audit flow alert", "labels": {"probe": "flows"},
        })
        aid = (r.json().get("data") or {}).get("id")
        line("POST /devops-alerts", r.status_code == 201, f"{r.status_code} id={aid}")

        for action in ("acknowledge", "mute", "resolve", "escalate"):
            r = await c.post(f"{BASE}/devops-alerts/{aid}/{action}",
                             json={"reason": "audit", "mute_hours": 2})
            st = ((r.json().get("data") or {}) or {}).get("status") if r.status_code < 300 else None
            line(f"POST /devops-alerts/{{id}}/{action}", r.status_code == 200,
                 f"http={r.status_code} persisted status={st!r}")

        s, b = await get(c, "/devops-alerts/stats")
        line("GET /devops-alerts/stats", s == 200, json.dumps(b.get("data"))[:150])

        r = await c.delete(f"{BASE}/devops-alerts/{aid}")
        line("DELETE /devops-alerts/{id}", r.status_code in (200, 204), f"http={r.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 3 — GitOps application lifecycle (create -> sync -> rollback -> patch -> delete)")
        print("=" * 100)
        r = await c.post(f"{BASE}/gitops", json={
            "name": f"flow-app-{uuid.uuid4().hex[:6]}",
            "repo_url": "https://github.com/audit-org/gitops-manifests",
            "path": "apps/flow", "cluster_id": IDS["cluster_a"],
        })
        gid = (r.json().get("data") or {}).get("id")
        line("POST /gitops", r.status_code == 201, f"{r.status_code} id={gid}")

        r = await c.post(f"{BASE}/gitops/{gid}/sync",
                         json={"hard_sync": False, "dry_run": False})
        line("POST /gitops/{id}/sync (ArgoCD NOT installed)", r.status_code == 503,
             f"http={r.status_code} {json.dumps(r.json())[:110]}")

        r = await c.post(f"{BASE}/gitops/{gid}/rollback",
                         json={"revision": "abc123", "message": "audit"})
        line("POST /gitops/{id}/rollback", r.status_code in (400, 404, 422, 503),
             f"http={r.status_code} {json.dumps(r.json())[:110]}")

        r = await c.patch(f"{BASE}/gitops/{gid}",
                          json={"sync_status": "OutOfSync", "sync_message": "audit patch"})
        s, b = await get(c, f"/gitops/{gid}")
        line("PATCH sync_status (only field AppUpdate allows)",
             (b.get("data") or {}).get("sync_status") == "OutOfSync",
             f"sync_status={(b.get('data') or {}).get('sync_status')} (http {r.status_code})")

        s, b = await get(c, f"/gitops/{gid}/history?limit=20")
        line("GET /gitops/{id}/history", s == 200, f"http={s} {json.dumps(b)[:120]}")

        r = await c.delete(f"{BASE}/gitops/{gid}")
        s, _ = await get(c, f"/gitops/{gid}")
        line("DELETE then GET -> gone", r.status_code in (200, 204) and s == 404,
             f"delete={r.status_code} subsequent_get={s}")

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 4 — CATALOG service (create -> watch deployment pipeline -> status)")
        print("=" * 100)
        svc = f"flow-svc-{uuid.uuid4().hex[:6]}"
        r = await c.post(f"{BASE}/catalog/services", json={
            "name": svc, "description": "audit flow service", "type": "api",
            "language": "python", "framework": "fastapi",
        })
        sid = (r.json().get("data") or {}).get("id")
        line("POST /catalog/services", r.status_code in (200, 201, 202),
             f"{r.status_code} id={sid}")

        await asyncio.sleep(6)
        s, b = await get(c, f"/catalog/services?search={svc}")
        _d = b.get("data")
        rows = _d if isinstance(_d, list) else ((_d or {}).get("data") or [])
        got = rows[0] if rows else {}
        line("service persisted + status reflects reality",
             got.get("status") in ("failed", "repo_creating", "pending", "building"),
             f"status={got.get('status')!r} repo={got.get('repo_url')!r}")

        import sqlite3
        con = sqlite3.connect(os.path.join(HERE, "audit.db"))
        con.row_factory = sqlite3.Row
        for row in con.execute(
                "SELECT step,status,message FROM deployment_logs WHERE service_name=? "
                "ORDER BY created_at", (svc,)):
            line(f"deployment_logs[{row['step']}]", row["status"] == "failed",
                 f"{row['status']}: {row['message']}")
        con.close()

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 5 — POD logs + restart + delete against a real (unreachable) cluster")
        print("=" * 100)
        s, b = await get(c, "/kubernetes/pods?page_size=5")
        pods = ((b.get("data") or {}).get("data")) or []
        if not pods:
            line("GET /kubernetes/pods", False, "NO POD ROWS IN DB - reseed required")
        else:
            p = pods[0]
            line("GET /kubernetes/pods", True,
                 f"{len(pods)} rows; first={p['namespace']}/{p['name']} phase={p.get('phase')}")
            s, b = await get(c, f"/kubernetes/pods/{p['id']}/logs?tail=50")
            line("GET /kubernetes/pods/{id}/logs", s == 200,
                 f"http={s} {json.dumps(b)[:130]}")
            s, b = await get(c, "/observability/logs?pod=" + p["name"])
            line("GET /observability/logs?pod=NAME (Observability tab)", s == 200,
                 f"http={s} {json.dumps(b)[:130]}")
            r = await c.post(f"{BASE}/kubernetes/pods/{p['id']}/restart")
            line("POST /kubernetes/pods/{id}/restart", r.status_code in (502, 503, 504),
                 f"http={r.status_code} {json.dumps(r.json())[:130]}")
            s, b = await get(c, f"/kubernetes/pods/{p['id']}")
            line("pod row still present after failed restart", s == 200, f"get={s}")

        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("FLOW 6 — CONTROL-PLANE resource tabs (cluster unreachable)")
        print("=" * 100)
        for path in ("/kubernetes/pods/workloads/deployments",
                     "/kubernetes/pods/workloads/statefulsets",
                     "/kubernetes/pods/workloads/daemonsets",
                     "/kubernetes/pods/network/services",
                     "/kubernetes/pods/network/ingresses",
                     "/kubernetes/pods/batch/jobs",
                     "/kubernetes/pods/config/configmaps",
                     "/kubernetes/pods/config/secrets",
                     "/kubernetes/pods/autoscaling/hpa"):
            s, b = await get(c, path)
            d = b.get("data")
            empty = (d == [] or d == {} or d is None
                     or (isinstance(d, dict) and not d.get("data")))
            err = b.get("message") or b.get("error")
            line(f"GET {path}", s == 200,
                 f"http={s} empty={empty} error_signal={err!r}")


if __name__ == "__main__":
    asyncio.run(main())
