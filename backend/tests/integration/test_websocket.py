"""Integration tests for WebSocket connections and message handling."""
import pytest
import json
from unittest.mock import AsyncMock, patch


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_connect_disconnect_lifecycle(self):
        from app.api.v1.websocket.manager import ConnectionManager
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await manager.connect(mock_ws, "tenant-abc")
        assert manager.get_tenant_connection_count("tenant-abc") == 1
        assert manager.total_connections == 1

        await manager.disconnect(mock_ws, "tenant-abc")
        assert manager.get_tenant_connection_count("tenant-abc") == 0

    @pytest.mark.asyncio
    async def test_send_to_tenant(self):
        from app.api.v1.websocket.manager import ConnectionManager
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        await manager.connect(mock_ws, "tenant-123")
        count = await manager.send_to_tenant("tenant-123", {"event": "test", "data": {}})
        assert count == 1
        mock_ws.send_json.assert_called_once_with({"event": "test", "data": {}})

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_tenant_returns_zero(self):
        from app.api.v1.websocket.manager import ConnectionManager
        manager = ConnectionManager()
        count = await manager.send_to_tenant("nonexistent-tenant", {"event": "test"})
        assert count == 0

    @pytest.mark.asyncio
    async def test_dead_connections_cleaned_up(self):
        from app.api.v1.websocket.manager import ConnectionManager
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(mock_ws, "tenant-dead")
        count = await manager.send_to_tenant("tenant-dead", {"event": "test"})
        assert count == 0
        assert manager.get_tenant_connection_count("tenant-dead") == 0

    @pytest.mark.asyncio
    async def test_multiple_tenants_isolated(self):
        from app.api.v1.websocket.manager import ConnectionManager
        manager = ConnectionManager()
        ws1, ws2 = AsyncMock(), AsyncMock()
        ws1.accept = AsyncMock()
        ws2.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "tenant-A")
        await manager.connect(ws2, "tenant-B")

        await manager.send_to_tenant("tenant-A", {"event": "a"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()


class TestWSHandlers:
    @pytest.mark.asyncio
    async def test_ping_returns_pong(self):
        from app.api.v1.websocket.handlers import handle_ws_message
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        await handle_ws_message(mock_ws, "tenant-abc", json.dumps({"event": "ping", "data": {}}))
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["event"] == "pong"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self):
        from app.api.v1.websocket.handlers import handle_ws_message
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        await handle_ws_message(mock_ws, "tenant-abc", "NOT JSON {{{")
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["event"] == "error"

    @pytest.mark.asyncio
    async def test_subscribe_event_confirmed(self):
        from app.api.v1.websocket.handlers import handle_ws_message
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        await handle_ws_message(
            mock_ws, "tenant-abc",
            json.dumps({"event": "subscribe", "data": {"channels": ["alerts", "pipelines"]}})
        )
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["event"] == "subscribed"
