from __future__ import annotations
"""
Core Event Bus — in-process async event bus for Epic 9.

Design goals:
  - Zero external dependencies (no Redis, no Celery)
  - Tenant-aware and cluster-aware routing
  - WebSocket bridge: events → ws_manager.send_to_tenant()
  - Typed event names matching the Epic 9 contract

Usage:
    from app.core.events.event_bus import event_bus

    # Emit
    await event_bus.emit("pod.failed", {"pod": "my-pod"}, tenant_id="t1", cluster_id="c1")

    # Subscribe
    unsub = await event_bus.subscribe("pod.failed", my_handler)
    ...
    unsub()  # stop listening
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Callable type: async fn(event_name, payload, tenant_id, cluster_id) → None
_Handler = Callable[..., Awaitable[None]]


class InProcessEventBus:
    """
    Lightweight asyncio-based pub/sub event bus.

    All handlers are called concurrently (gathered) so one slow handler
    cannot block others.  Exceptions in individual handlers are logged and
    suppressed to keep the bus running.
    """

    def __init__(self):
        self._handlers: dict[str, list[_Handler]] = defaultdict(list)
        self._wildcard: list[_Handler] = []

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(
        self,
        event: str | None,
        handler: _Handler,
    ) -> Callable[[], None]:
        """
        Subscribe to an event name (or None for all events / wildcard).

        Returns an unsubscribe callable.
        """
        if event is None:
            self._wildcard.append(handler)
            def unsub():
                try:
                    self._wildcard.remove(handler)
                except ValueError:
                    pass
        else:
            self._handlers[event].append(handler)
            def unsub():
                try:
                    self._handlers[event].remove(handler)
                except ValueError:
                    pass
        return unsub

    # ── Emit ─────────────────────────────────────────────────────────────────

    async def emit(
        self,
        event: str,
        payload: dict,
        tenant_id: str | None = None,
        cluster_id: str | None = None,
    ) -> None:
        """
        Publish an event.  Calls all matching + wildcard handlers concurrently.
        """
        handlers = list(self._handlers.get(event, [])) + list(self._wildcard)
        if not handlers:
            return

        async def _call(h: _Handler) -> None:
            try:
                await h(event, payload, tenant_id, cluster_id)
            except Exception as exc:
                logger.error(f"[event_bus] handler {h.__name__} error on '{event}': {exc}")

        await asyncio.gather(*[_call(h) for h in handlers], return_exceptions=True)

    # ── WebSocket bridge ──────────────────────────────────────────────────────

    async def _ws_bridge(
        self,
        event: str,
        payload: dict,
        tenant_id: str | None,
        cluster_id: str | None,
    ) -> None:
        """
        Forward every event to the WebSocket manager so connected clients
        receive real-time updates without polling.
        """
        try:
            from app.api.v1.websocket.manager import ws_manager

            message: dict[str, Any] = {
                "event": event,
                "data":  payload,
            }
            if cluster_id:
                message["cluster_id"] = cluster_id

            if tenant_id:
                await ws_manager.send_to_tenant(tenant_id, message)
            elif ws_manager.total_connections > 0:
                await ws_manager.broadcast(message)

        except Exception as exc:
            logger.warning(f"[event_bus] WS bridge error: {exc}")

    def enable_ws_bridge(self) -> None:
        """Register the WS bridge as a wildcard handler (call once at startup)."""
        self.subscribe(None, self._ws_bridge)
        logger.info("[event_bus] WebSocket bridge enabled")


# ── Singleton ─────────────────────────────────────────────────────────────────

event_bus = InProcessEventBus()


# ── Typed event emitters (convenience) ───────────────────────────────────────

async def emit_pod_event(
    event: str,
    pod_name: str,
    namespace: str,
    tenant_id: str,
    cluster_id: str | None = None,
    extra: dict | None = None,
) -> None:
    payload = {
        "pod":       pod_name,
        "namespace": namespace,
        **(extra or {}),
    }
    await event_bus.emit(event, payload, tenant_id=tenant_id, cluster_id=cluster_id)


async def emit_metric_event(
    tenant_id: str,
    cluster_id: str | None,
    metrics: dict,
) -> None:
    await event_bus.emit(
        "metric.updated",
        metrics,
        tenant_id=tenant_id,
        cluster_id=cluster_id,
    )


async def emit_log_event(
    tenant_id: str,
    cluster_id: str | None,
    pod_name: str,
    log_line: dict,
) -> None:
    await event_bus.emit(
        "log.stream",
        {"pod": pod_name, "log": log_line},
        tenant_id=tenant_id,
        cluster_id=cluster_id,
    )
