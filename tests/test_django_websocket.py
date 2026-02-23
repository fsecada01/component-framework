"""Tests for Django Channels WebSocket adapter."""

import json
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("django", reason="Install: pip install component-framework[django]")

from component_framework.adapters.django_websocket import (
    ComponentConsumer,
    DjangoWebSocketConnection,
    broadcast_component_update,
)
from component_framework.core.websocket import ComponentWebSocketManager

# ---------- DjangoWebSocketConnection ----------


class TestDjangoWebSocketConnection:
    @pytest.mark.asyncio
    async def test_send(self):
        mock_consumer = AsyncMock()
        conn = DjangoWebSocketConnection(mock_consumer)
        await conn.send({"type": "test"})
        mock_consumer.send.assert_called_once_with(text_data=json.dumps({"type": "test"}))

    @pytest.mark.asyncio
    async def test_receive_not_implemented(self):
        mock_consumer = AsyncMock()
        conn = DjangoWebSocketConnection(mock_consumer)
        with pytest.raises(NotImplementedError):
            await conn.receive()

    @pytest.mark.asyncio
    async def test_close(self):
        mock_consumer = AsyncMock()
        conn = DjangoWebSocketConnection(mock_consumer)
        await conn.close()
        mock_consumer.close.assert_called_once()


# ---------- ComponentConsumer ----------


class TestComponentConsumer:
    def test_init_defaults(self):
        consumer = ComponentConsumer()
        assert consumer.connection_id is None
        assert consumer.connection is None

    @pytest.mark.asyncio
    async def test_connect(self, monkeypatch):
        consumer = ComponentConsumer()
        consumer.accept = AsyncMock()
        consumer.send = AsyncMock()

        manager = ComponentWebSocketManager()
        monkeypatch.setattr("component_framework.adapters.django_websocket.ws_manager", manager)

        await consumer.connect()
        consumer.accept.assert_called_once()
        assert consumer.connection_id is not None
        assert consumer.connection is not None
        assert consumer.connection_id in manager.connections

        # Check confirmation message was sent
        consumer.send.assert_called_once()
        sent_data = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent_data["type"] == "connected"

    @pytest.mark.asyncio
    async def test_disconnect(self, monkeypatch):
        consumer = ComponentConsumer()
        consumer.accept = AsyncMock()
        consumer.send = AsyncMock()

        manager = ComponentWebSocketManager()
        monkeypatch.setattr("component_framework.adapters.django_websocket.ws_manager", manager)

        await consumer.connect()
        conn_id = consumer.connection_id
        assert conn_id in manager.connections

        await consumer.disconnect(close_code=1000)
        assert conn_id not in manager.connections

    @pytest.mark.asyncio
    async def test_receive_valid_json(self, monkeypatch):
        consumer = ComponentConsumer()
        consumer.accept = AsyncMock()
        consumer.send = AsyncMock()

        manager = ComponentWebSocketManager()
        manager.handle_message = AsyncMock()
        monkeypatch.setattr("component_framework.adapters.django_websocket.ws_manager", manager)

        await consumer.connect()
        await consumer.receive(text_data=json.dumps({"type": "subscribe", "component_id": "c1"}))
        manager.handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_invalid_json(self, monkeypatch):
        consumer = ComponentConsumer()
        consumer.accept = AsyncMock()
        consumer.send = AsyncMock()

        manager = ComponentWebSocketManager()
        monkeypatch.setattr("component_framework.adapters.django_websocket.ws_manager", manager)

        await consumer.connect()
        consumer.send.reset_mock()
        await consumer.receive(text_data="not-json")
        # Should send error response
        sent_data = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent_data["type"] == "error"
        assert "Invalid JSON" in sent_data["error"]


# ---------- broadcast_component_update ----------


class TestBroadcastUpdate:
    @pytest.mark.asyncio
    async def test_broadcast(self, monkeypatch):
        manager = ComponentWebSocketManager()
        manager.push_update = AsyncMock()
        monkeypatch.setattr("component_framework.adapters.django_websocket.ws_manager", manager)

        await broadcast_component_update("comp-1", "<div>updated</div>", {"count": 5})
        manager.push_update.assert_called_once_with("comp-1", "<div>updated</div>", {"count": 5})
