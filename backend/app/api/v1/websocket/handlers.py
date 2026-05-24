"""WebSocket message handlers — process inbound WS messages from clients."""
import json
from fastapi import WebSocket
from app.api.v1.websocket.manager import ws_manager
from app.api.v1.websocket.events import WSEventType
from app.utils.logger import logger


async def handle_ws_message(websocket: WebSocket, tenant_id: str, raw: str) -> None:
    try:
        data = json.loads(raw)
        event = data.get("event")
        payload = data.get("data", {})

        if event == WSEventType.PING:
            await websocket.send_json({"event": WSEventType.PONG, "data": {"time": _now_iso()}})
            return

        if event == "subscribe":
            channels = payload.get("channels", [])
            logger.debug(f"Tenant {tenant_id} subscribing to: {channels}")
            await websocket.send_json({
                "event": "subscribed",
                "data": {"channels": channels, "status": "ok"},
            })
            return

        if event == "unsubscribe":
            channels = payload.get("channels", [])
            await websocket.send_json({
                "event": "unsubscribed",
                "data": {"channels": channels},
            })
            return

        if event == "broadcast" and payload.get("system"):
            await ws_manager.send_to_tenant(tenant_id, {"event": "system.message", "data": payload})
            return

        logger.debug(f"Unknown WS event '{event}' from tenant {tenant_id}")
        await websocket.send_json({
            "event": "error",
            "data": {"message": f"Unknown event type: {event}"},
        })

    except json.JSONDecodeError:
        logger.warning(f"Invalid WS message (not JSON) from tenant {tenant_id}")
        await websocket.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
    except Exception as e:
        logger.error(f"WS handler error for tenant {tenant_id}: {e}")


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def start_k8s_watch(
    websocket,
    tenant_id: str,
    namespace: str | None = None,
    db=None,
):
    """
    Real-time Kubernetes cluster events via WebSocket.
    Watches cluster events and pushes them to the connected client.

    Flow:
      Client sends: {"event": "k8s.watch.start", "data": {"namespace": "default"}}
      Server pushes: {"event": "k8s.events", "data": [...events]}  every ~5s
      Client sends: {"event": "k8s.watch.stop"} to stop
    """
    import asyncio
    from app.services.kubernetes_service import KubernetesService

    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        await websocket.send_json({
            "event": "k8s.error",
            "data": {"message": "No Kubernetes integration connected"},
        })
        return

    await websocket.send_json({
        "event": "k8s.watch.started",
        "data": {"namespace": namespace or "all", "message": "Watching cluster events..."},
    })

    # Poll every 5 seconds — collect events in short windows
    while True:
        try:
            events = await asyncio.wait_for(
                client.watch_cluster_events(namespace=namespace, timeout=5),
                timeout=8,
            )
            if events:
                await websocket.send_json({"event": "k8s.events", "data": events})

            # Also push live resource counts every poll
            counts = await _get_live_counts(client, namespace)
            if counts:
                await websocket.send_json({"event": "k8s.counts", "data": counts})

            await asyncio.sleep(5)

        except Exception as e:
            await websocket.send_json({
                "event": "k8s.error",
                "data": {"message": str(e)},
            })
            break


async def _get_live_counts(client, namespace: str | None) -> dict:
    """Fast cluster resource counts for live dashboard badges."""
    import asyncio
    try:
        pods, deps, svcs = await asyncio.gather(
            client.list_all_pods() if not namespace else client.list_pods(namespace),
            client.list_deployments(namespace),
            client.list_services(namespace),
            return_exceptions=True,
        )
        return {
            "pods":        len(pods) if isinstance(pods, list) else 0,
            "deployments": len(deps) if isinstance(deps, list) else 0,
            "services":    len(svcs) if isinstance(svcs, list) else 0,
        }
    except Exception:
        return {}
