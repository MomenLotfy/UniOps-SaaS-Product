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


# NOTE: Live Kubernetes events (pod.created/updated/failed/deleted and
# k8s.events) are produced by the background cluster watchers
# (app/core/events/k8s_watcher.py) which run the real Kubernetes Watch API
# via app/integrations/kubernetes/watcher.py and publish into the event bus.
# The event bus WS bridge (event_bus._ws_bridge) forwards those to subscribed
# tenants — there is intentionally no per-connection polling loop here.
