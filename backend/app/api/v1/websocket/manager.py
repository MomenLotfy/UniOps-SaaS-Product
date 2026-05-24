"""WebSocket Connection Manager — manages per-tenant connections with broadcasting."""
import asyncio
from typing import Optional
from fastapi import WebSocket
from app.utils.logger import logger


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            if tenant_id not in self._connections:
                self._connections[tenant_id] = []
            self._connections[tenant_id].append(websocket)
        logger.info(f"WS connected: tenant={tenant_id}, connections={len(self._connections.get(tenant_id, []))}")

    async def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        async with self._lock:
            connections = self._connections.get(tenant_id, [])
            try:
                connections.remove(websocket)
            except ValueError:
                pass
            if not connections and tenant_id in self._connections:
                del self._connections[tenant_id]
        logger.info(f"WS disconnected: tenant={tenant_id}")

    async def send_to_tenant(self, tenant_id: str, message: dict) -> int:
        connections = list(self._connections.get(tenant_id, []))
        dead = []
        sent = 0
        for ws in connections:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, tenant_id)
        return sent

    async def send_to_user(self, tenant_id: str, user_id: str, message: dict) -> None:
        message_with_user = {**message, "_target_user": user_id}
        await self.send_to_tenant(tenant_id, message_with_user)

    async def broadcast(self, message: dict) -> int:
        total = 0
        for tenant_id in list(self._connections.keys()):
            total += await self.send_to_tenant(tenant_id, message)
        return total

    def get_tenant_connection_count(self, tenant_id: str) -> int:
        return len(self._connections.get(tenant_id, []))

    @property
    def total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())

    @property
    def connected_tenants(self) -> list[str]:
        return list(self._connections.keys())


ws_manager = ConnectionManager()
