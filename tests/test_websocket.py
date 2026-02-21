"""Tests for WebSocket manager."""

import pytest

from component_framework.core.renderer import Renderer
from component_framework.core.websocket import (
    ComponentWebSocketManager,
    WebSocketConnection,
)


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}</div>"


class MockWebSocketConnection(WebSocketConnection):
    """In-memory WebSocket mock for testing."""

    def __init__(self):
        self.sent_messages: list[dict] = []
        self.closed = False

    async def send(self, data: dict):
        self.sent_messages.append(data)

    async def receive(self) -> dict:
        raise NotImplementedError

    async def close(self):
        self.closed = True


@pytest.fixture
def manager():
    return ComponentWebSocketManager()


@pytest.fixture
def connection():
    return MockWebSocketConnection()


# ---------- Connection Management ----------


class TestConnectionManagement:
    @pytest.mark.asyncio
    async def test_connect_registers_connection(self, manager, connection):
        await manager.connect(connection, "conn-1")
        assert "conn-1" in manager.connections
        assert connection in manager.connections["conn-1"]

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, connection):
        await manager.connect(connection, "conn-1")
        await manager.disconnect("conn-1")
        assert "conn-1" not in manager.connections

    @pytest.mark.asyncio
    async def test_disconnect_cleans_subscriptions(self, manager, connection):
        await manager.connect(connection, "conn-1")
        manager.subscribe("conn-1", "comp-1")
        await manager.disconnect("conn-1")
        assert "conn-1" not in manager.component_subscribers.get("comp-1", set())

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_no_error(self, manager):
        await manager.disconnect("nonexistent")  # Should not raise


# ---------- Subscriptions ----------


class TestSubscriptions:
    def test_subscribe(self, manager):
        manager.subscribe("conn-1", "comp-1")
        assert "conn-1" in manager.component_subscribers["comp-1"]

    def test_unsubscribe(self, manager):
        manager.subscribe("conn-1", "comp-1")
        manager.unsubscribe("conn-1", "comp-1")
        assert "conn-1" not in manager.component_subscribers.get("comp-1", set())

    def test_unsubscribe_nonexistent_no_error(self, manager):
        manager.unsubscribe("conn-1", "comp-1")  # Should not raise

    def test_multiple_subscribers(self, manager):
        manager.subscribe("conn-1", "comp-1")
        manager.subscribe("conn-2", "comp-1")
        assert len(manager.component_subscribers["comp-1"]) == 2


# ---------- Message Handling ----------


class TestMessageHandling:
    @pytest.mark.asyncio
    async def test_subscribe_message(self, manager, connection):
        await manager.connect(connection, "conn-1")
        await manager.handle_message(
            connection,
            "conn-1",
            {"type": "subscribe", "component_id": "comp-1"},
        )
        assert "conn-1" in manager.component_subscribers["comp-1"]
        assert connection.sent_messages[-1]["type"] == "subscribed"

    @pytest.mark.asyncio
    async def test_unsubscribe_message(self, manager, connection):
        await manager.connect(connection, "conn-1")
        manager.subscribe("conn-1", "comp-1")
        await manager.handle_message(
            connection,
            "conn-1",
            {"type": "unsubscribe", "component_id": "comp-1"},
        )
        assert "conn-1" not in manager.component_subscribers.get("comp-1", set())
        assert connection.sent_messages[-1]["type"] == "unsubscribed"

    @pytest.mark.asyncio
    async def test_unknown_message_type(self, manager, connection):
        await manager.connect(connection, "conn-1")
        # Should not raise, just log a warning
        await manager.handle_message(
            connection,
            "conn-1",
            {"type": "unknown_type"},
        )

    @pytest.mark.asyncio
    async def test_component_event_not_found(self, manager, connection):
        await manager.connect(connection, "conn-1")
        await manager.handle_message(
            connection,
            "conn-1",
            {
                "type": "component_event",
                "component": "nonexistent_component",
                "event": "click",
            },
        )
        last_msg = connection.sent_messages[-1]
        assert last_msg["type"] == "error"
        assert "not found" in last_msg["error"]


# ---------- Broadcasting ----------


class TestBroadcasting:
    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, manager):
        conn1 = MockWebSocketConnection()
        conn2 = MockWebSocketConnection()
        await manager.connect(conn1, "conn-1")
        await manager.connect(conn2, "conn-2")
        manager.subscribe("conn-1", "comp-1")
        manager.subscribe("conn-2", "comp-1")

        await manager.broadcast_update("comp-1", {"html": "<div>updated</div>"})
        assert len(conn1.sent_messages) == 1
        assert len(conn2.sent_messages) == 1
        assert conn1.sent_messages[0]["type"] == "component_update"

    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers(self, manager):
        # Should not raise
        await manager.broadcast_update("comp-1", {"html": "<div>test</div>"})

    @pytest.mark.asyncio
    async def test_push_update(self, manager):
        conn = MockWebSocketConnection()
        await manager.connect(conn, "conn-1")
        manager.subscribe("conn-1", "comp-1")

        await manager.push_update("comp-1", "<div>pushed</div>", {"count": 5})
        assert len(conn.sent_messages) == 1
        msg = conn.sent_messages[0]
        assert msg["type"] == "component_update"
        assert msg["html"] == "<div>pushed</div>"
