"""WebSocket support for real-time component updates."""

import asyncio
import logging
from abc import ABC, abstractmethod

from .component import StateSerializer
from .registry import registry

logger = logging.getLogger(__name__)


class WebSocketConnection(ABC):
    """Abstract WebSocket connection."""

    @abstractmethod
    async def send(self, data: dict):
        """Send data to client."""
        raise NotImplementedError

    @abstractmethod
    async def receive(self) -> dict:
        """Receive data from client."""
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        """Close connection."""
        raise NotImplementedError


class ComponentWebSocketManager:
    """
    Manages WebSocket connections for components.

    Handles:
    - Connection lifecycle
    - Message routing
    - Component updates
    - Broadcasting
    """

    def __init__(self):
        self.connections: dict[str, list[WebSocketConnection]] = {}
        self.component_subscribers: dict[str, set[str]] = {}

    async def connect(self, connection: WebSocketConnection, connection_id: str):
        """Register new WebSocket connection."""
        if connection_id not in self.connections:
            self.connections[connection_id] = []
        self.connections[connection_id].append(connection)
        logger.info(f"WebSocket connected: {connection_id}")

    async def disconnect(self, connection_id: str):
        """Remove WebSocket connection."""
        if connection_id in self.connections:
            del self.connections[connection_id]

        # Clean up subscriptions
        for component_id, subscribers in self.component_subscribers.items():
            subscribers.discard(connection_id)

        logger.info(f"WebSocket disconnected: {connection_id}")

    def subscribe(self, connection_id: str, component_id: str):
        """Subscribe connection to component updates."""
        if component_id not in self.component_subscribers:
            self.component_subscribers[component_id] = set()
        self.component_subscribers[component_id].add(connection_id)
        logger.debug(f"Subscribed {connection_id} to component {component_id}")

    def unsubscribe(self, connection_id: str, component_id: str):
        """Unsubscribe connection from component updates."""
        if component_id in self.component_subscribers:
            self.component_subscribers[component_id].discard(connection_id)

    async def handle_message(
        self, connection: WebSocketConnection, connection_id: str, message: dict
    ):
        """
        Handle incoming WebSocket message.

        Message format:
        {
            "type": "component_event",
            "component": "component_name",
            "component_id": "component-123",
            "event": "event_name",
            "payload": {...},
            "state": "serialized_state"
        }
        """
        msg_type = message.get("type")

        if msg_type == "component_event":
            await self._handle_component_event(connection, connection_id, message)
        elif msg_type == "subscribe":
            component_id = message.get("component_id")
            if component_id:
                self.subscribe(connection_id, component_id)
                await connection.send({"type": "subscribed", "component_id": component_id})
        elif msg_type == "unsubscribe":
            component_id = message.get("component_id")
            if component_id:
                self.unsubscribe(connection_id, component_id)
                await connection.send({"type": "unsubscribed", "component_id": component_id})
        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_component_event(
        self, connection: WebSocketConnection, connection_id: str, message: dict
    ):
        """Handle component event from WebSocket."""
        try:
            component_name: str = message.get("component", "")
            component_id: str | None = message.get("component_id")
            event: str | None = message.get("event")
            payload: dict = message.get("payload", {})
            state_str: str | None = message.get("state")

            # Get component class
            component_cls = registry.get(component_name)
            if not component_cls:
                await connection.send(
                    {
                        "type": "error",
                        "error": f"Component '{component_name}' not found",
                    }
                )
                return

            # Deserialize state
            state = None
            if state_str:
                state = StateSerializer.deserialize(state_str)

            # Create and dispatch component (async to support async on_* handlers)
            params = {"component_id": component_id}
            component = component_cls(**params)
            result = await component.async_dispatch(event=event, payload=payload, state=state)

            # Serialize state
            result["state"] = StateSerializer.serialize(result["state"])

            # Send update to requesting connection
            await connection.send({"type": "component_update", **result})

            # Broadcast to subscribers (optional)
            if message.get("broadcast", False) and component_id:
                await self.broadcast_update(component_id, result)

        except Exception as e:
            logger.exception("Error handling component event")
            await connection.send({"type": "error", "error": str(e)})

    async def broadcast_update(self, component_id: str, update: dict):
        """
        Broadcast component update to all subscribers.

        Args:
            component_id: Component to broadcast update for
            update: Update data (html, state, etc.)
        """
        if component_id not in self.component_subscribers:
            return

        subscribers = self.component_subscribers[component_id]
        message = {"type": "component_update", **update}

        # Send to all subscribers
        tasks = []
        for connection_id in subscribers:
            if connection_id in self.connections:
                for conn in self.connections[connection_id]:
                    tasks.append(conn.send(message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Broadcasted update for {component_id} to {len(tasks)} connections")

    async def push_update(self, component_id: str, html: str, state: dict):
        """
        Push server-initiated update to component subscribers.

        Useful for external events (model updates, background jobs, etc.)
        """
        serialized_state = StateSerializer.serialize(state)
        update = {
            "component_id": component_id,
            "html": html,
            "state": serialized_state,
        }
        await self.broadcast_update(component_id, update)


# Global manager instance
ws_manager = ComponentWebSocketManager()
