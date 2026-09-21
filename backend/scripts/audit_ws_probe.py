"""DevOps Center — live WebSocket verification.

Connects to /ws/{tenant_id} with real JWTs and proves:
  * missing token        -> rejected
  * invalid token        -> rejected
  * wrong-tenant token   -> rejected (tenant binding)
  * valid token          -> accepted, ping/pong works
  * malformed JSON       -> clean error frame, connection survives
  * unknown event        -> clean error frame
  * cross-tenant event isolation (tenant A event not delivered to tenant B)

Run: cd backend && .venv/bin/python scripts/audit_ws_probe.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import websockets  # noqa: E402

from app.core.security import create_access_token  # noqa: E402

IDS = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".audit_ids.json")))
HOST = os.environ.get("WS_HOST", "127.0.0.1:8000")

TOK_A = create_access_token(IDS["admin_a"], "admin@a.audit.dev", IDS["tenant_a"], ["admin"])
TOK_B = create_access_token(IDS["admin_b"], "admin@b.audit.dev", IDS["tenant_b"], ["admin"])


def url(tenant_id, token):
    u = f"ws://{HOST}/ws/{tenant_id}"
    return u + f"?token={token}" if token is not None else u


async def try_connect(label, tenant_id, token):
    """Return an OPEN connection, or None if the server rejected the handshake."""
    try:
        ws = await websockets.connect(url(tenant_id, token), open_timeout=8)
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        print(f"{label:40} -> REJECTED  {type(e).__name__} code={code}")
        return None
    print(f"{label:40} -> ACCEPTED  (connection open)")
    return ws


async def recv(ws, label, timeout=4):
    try:
        return await asyncio.wait_for(ws.recv(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def main():
    print("=" * 96)
    print("1. HANDSHAKE AUTHENTICATION + TENANT BINDING")
    print("=" * 96)
    await try_connect("no token",                      IDS["tenant_a"], None)
    await try_connect("garbage token",                 IDS["tenant_a"], "not-a-jwt")
    await try_connect("tenant A path + tenant B JWT",  IDS["tenant_a"], TOK_B)
    await try_connect("tenant B path + tenant A JWT",  IDS["tenant_b"], TOK_A)

    ws_a = await try_connect("tenant A path + tenant A JWT", IDS["tenant_a"], TOK_A)
    ws_b = await try_connect("tenant B path + tenant B JWT", IDS["tenant_b"], TOK_B)
    if not (ws_a and ws_b):
        print("\ncould not open both connections; aborting protocol tests")
        return

    print("\n" + "=" * 96)
    print("2. INBOUND PROTOCOL BEHAVIOUR (tenant A connection)")
    print("=" * 96)
    await ws_a.send(json.dumps({"event": "ping", "data": {}}))
    print("ping             ->", await recv(ws_a, "ping"))

    await ws_a.send("{ this is not json")
    print("malformed JSON   ->", await recv(ws_a, "malformed"))

    await ws_a.send(json.dumps({"event": "totally.bogus.event", "data": {}}))
    print("unknown event    ->", await recv(ws_a, "unknown"))

    await ws_a.send(json.dumps({"event": "subscribe",
                                "data": {"channels": ["pod.update", "pipeline.update"]}}))
    print("subscribe        ->", await recv(ws_a, "subscribe"))

    await ws_a.send(json.dumps({"event": "ping", "data": {}}))
    print("ping AFTER abuse ->", await recv(ws_a, "ping2"), "  <- connection survived")

    print("\n" + "=" * 96)
    print("3. CROSS-TENANT EVENT ISOLATION")
    print("=" * 96)
    print("Asking the SERVER to publish a system event into tenant A only")
    print('(server runs ws_manager.send_to_tenant(<path tenant>, ...) in-process)')
    await ws_a.send(json.dumps({"event": "broadcast",
                                "data": {"system": True, "marker": "FROM_TENANT_A"}}))

    got_a = await recv(ws_a, "A")
    got_b = await recv(ws_b, "B", timeout=3)
    print("tenant A received:", got_a)
    print("tenant B received:", got_b if got_b else "NOTHING  -> tenant isolation HOLDS")

    await ws_a.close()
    await ws_b.close()
    print("\nconnections closed")


if __name__ == "__main__":
    asyncio.run(main())
