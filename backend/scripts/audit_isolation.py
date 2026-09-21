"""DevOps Center — rigorous tenant-isolation proof.

Earlier probes reused a pod UUID that no longer existed, so their 404s proved
nothing.  This script:

  1. inserts a pod row that genuinely belongs to tenant B,
  2. attacks it as tenant A's admin over the real HTTP API,
  3. re-reads the DB to confirm whether the row survived,
  4. does the same for the GitOps DELETE that previously returned 204
     cross-tenant, and for a same-tenant delete as a control.

Run: cd backend && .venv/bin/python scripts/audit_isolation.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx  # noqa: E402

from app.core.security import create_access_token  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "audit.db")
IDS = json.load(open(os.path.join(HERE, ".audit_ids.json")))
BASE = "http://127.0.0.1:8000/api/v1"

TA, TB = IDS["tenant_a"], IDS["tenant_b"]
OK, BAD = "\u2713", "\u2717"


def hdr(user, tenant, roles):
    return {"Authorization": "Bearer " + create_access_token(
        user, f"{user}@audit.dev", tenant, roles)}


def q(sql, args=()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def seed_b_pod() -> str:
    pid = str(uuid.uuid4())
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT INTO pods (id, tenant_id, integration_id, cluster, name, namespace, "
        "status, phase, node, restart_count, containers, labels, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,0,'[]','{}',datetime('now'),datetime('now'))",
        (pid, TB, IDS.get("k8s_id_b") or IDS.get("k8s_id_a"), "audit-cluster-b",
         "tenant-b-secret-pod", "confidential", "Running", "Running", "node-b-1"),
    )
    con.commit()
    con.close()
    return pid


def seed_b_app() -> str:
    """Clone an existing tenant-B gitops row under a fresh id."""
    aid = str(uuid.uuid4())
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    src = con.execute(
        "SELECT * FROM gitops_apps WHERE tenant_id=? LIMIT 1", (TB,)).fetchone()
    if src is None:
        con.close()
        raise SystemExit(f"no tenant-B gitops row to clone (tenant {TB})")
    row = {k: src[k] for k in src.keys()}
    row["id"] = aid
    row["name"] = "tenant-b-secret-app"
    cols = ", ".join(row)
    con.execute(f"INSERT INTO gitops_apps ({cols}) VALUES ({','.join('?' * len(row))})",
                tuple(row.values()))
    con.commit()
    con.close()
    return aid


async def main():
    A = hdr("admin_a", TA, ["admin"])
    B = hdr("admin_b", TB, ["admin"])

    b_pod = seed_b_pod()
    b_app = seed_b_app()
    print(f"seeded tenant-B pod {b_pod} (namespace=confidential)")
    print(f"seeded tenant-B gitops app {b_app}")

    async with httpx.AsyncClient(timeout=90) as c:

        print("\n" + "=" * 100)
        print("A. TENANT A ATTACKS A REAL TENANT-B POD")
        print("=" * 100)
        attacks = [
            ("GET    /kubernetes/pods/{id}",          "get",    f"/kubernetes/pods/{b_pod}"),
            ("GET    /kubernetes/pods/{id}/logs",     "get",    f"/kubernetes/pods/{b_pod}/logs"),
            ("GET    /kubernetes/pods/{id}/events",   "get",    f"/kubernetes/pods/{b_pod}/events"),
            ("POST   /kubernetes/pods/{id}/restart",  "post",   f"/kubernetes/pods/{b_pod}/restart"),
            ("POST   /kubernetes/pods/{id}/exec",     "post",   f"/kubernetes/pods/{b_pod}/exec"),
            ("DELETE /kubernetes/pods/{id}",          "delete", f"/kubernetes/pods/{b_pod}"),
        ]
        for label, verb, path in attacks:
            body = {"command": "ls -la"} if "exec" in path else {}
            kw = {"json": body} if verb == "post" else {}
            r = await getattr(c, verb)(BASE + path, headers=A, **kw)
            still = q("SELECT id FROM pods WHERE id=?", (b_pod,))
            print(f"  [{OK if r.status_code == 404 else BAD}] {label:42} -> HTTP {r.status_code:3} "
                  f"| row still in DB: {bool(still)}")

        # control: same tenant can read it?  (no - it's B's, A must never see it)
        r = await c.get(f"{BASE}/kubernetes/pods?page_size=200", headers=A)
        names = [p["name"] for p in ((r.json().get("data") or {}).get("data") or [])]
        mark = OK if 'tenant-b-secret-pod' not in names else BAD
        print(f"  [{mark}] A's pod list does NOT contain B's pod  (names={names})")

        print("\n" + "=" * 100)
        print("B. B (the owner) CAN read its own pod  [control that the row is real]")
        print("=" * 100)
        r = await c.get(f"{BASE}/kubernetes/pods/{b_pod}", headers=B)
        print(f"  [{OK if r.status_code == 200 else BAD}] GET as owner -> HTTP {r.status_code}")

        print("\n" + "=" * 100)
        print("C. GitOps DELETE — the endpoint that returned 204 cross-tenant")
        print("=" * 100)
        r = await c.delete(f"{BASE}/gitops/{b_app}", headers=A)
        still = q("SELECT id FROM gitops_apps WHERE id=?", (b_app,))
        mark = OK if r.status_code == 404 else BAD
        print(f"  [{mark}] A DELETEs B's app -> HTTP {r.status_code} | row still in DB: {bool(still)}")
        print(f"     -> {'safe (rejected)' if r.status_code == 404 else 'returns 204 SUCCESS while the row survives'}")

        # control: owner deletes its own app
        r = await c.delete(f"{BASE}/gitops/{b_app}", headers=B)
        still = q("SELECT id FROM gitops_apps WHERE id=?", (b_app,))
        print(f"  [control] B DELETEs its OWN app -> HTTP {r.status_code} | "
              f"row still in DB: {bool(still)}  (expected 204 + gone)")

        print("\n" + "=" * 100)
        print("D. GitOps DELETE on a completely NON-EXISTENT id")
        print("=" * 100)
        r = await c.delete(f"{BASE}/gitops/{uuid.uuid4()}", headers=A)
        print(f"  A DELETEs a random UUID -> HTTP {r.status_code} "
              f"(expected 404; 204 means the endpoint never verifies the row)")

        print("\n" + "=" * 100)
        print("E. Pipeline / cluster cross-tenant against REAL rows")
        print("=" * 100)
        bp = q("SELECT id FROM pipelines WHERE tenant_id=?", (TB,))
        bc = q("SELECT id FROM clusters WHERE tenant_id=?", (TB,))
        if bp:
            pid = bp[0]["id"]
            for verb, path in (("get", f"/pipelines/{pid}"),
                               ("post", f"/pipelines/{pid}/cancel"),
                               ("post", f"/pipelines/{pid}/rerun")):
                kw = {"json": {}} if verb == "post" else {}
                r = await getattr(c, verb)(BASE + path, headers=A, **kw)
                print(f"  [{OK if r.status_code == 404 else BAD}] {verb.upper():6} {path:44} -> {r.status_code}")
        else:
            print("  (no tenant-B pipeline row to attack)")
        if bc:
            cid = bc[0]["id"]
            for verb, path in (("get", f"/clusters/{cid}"),
                               ("post", f"/clusters/{cid}/test"),
                               ("patch", f"/clusters/{cid}"),
                               ("delete", f"/clusters/{cid}")):
                kw = ({"json": {"region": "pwned"}} if verb == "patch"
                      else ({"json": {}} if verb == "post" else {}))
                r = await getattr(c, verb)(BASE + path, headers=A, **kw)
                alive = q("SELECT id FROM clusters WHERE id=?", (cid,))
                print(f"  [{OK if r.status_code == 404 else BAD}] {verb.upper():6} {path:44} -> {r.status_code}"
                      f" | row alive: {bool(alive)}")


if __name__ == "__main__":
    asyncio.run(main())
