"""Django Channels WebSocket adapter."""

import json
import logging
from uuid import uuid4

from channels.generic.websocket import AsyncWebsocketConsumer

from ..core.websocket import WebSocketConnection, ws_manager

logger = logging.getLogger(__name__)


class DjangoWebSocketConnection(WebSocketConnection):
    """Django Channels WebSocket connection wrapper."""

    def __init__(self, consumer: "ComponentConsumer"):
        self.consumer = consumer

    async def send(self, data: dict):
        """Send JSON data to client."""
        await self.consumer.send(text_data=json.dumps(data))

    async def receive(self) -> dict:
        """Receive is handled by consumer, not used directly."""
        raise NotImplementedError("Receive handled by consumer")

    async def close(self):
        """Close WebSocket connection."""
        await self.consumer.close()


class ComponentConsumer(AsyncWebsocketConsumer):
    """
    Django Channels consumer for component WebSocket.

    Usage in routing.py:
        from channels.routing import ProtocolTypeRouter, URLRouter
        from django.urls import path
        from component_framework.adapters.django_websocket import ComponentConsumer

        application = ProtocolTypeRouter({
            "websocket": URLRouter([
                path("ws/", ComponentConsumer.as_asgi()),
            ]),
        })
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_id = None
        self.connection = None

    async def connect(self):
        """Handle WebSocket connection."""
        # Accept connection
        await self.accept()

        # Generate connection ID
        self.connection_id = str(uuid4())
        self.connection = DjangoWebSocketConnection(self)

        # Register with manager
        await ws_manager.connect(self.connection, self.connection_id)

        # Send connection confirmation
        await self.send(
            text_data=json.dumps({"type": "connected", "connection_id": self.connection_id})
        )

        logger.info(f"WebSocket connected: {self.connection_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.connection_id:
            await ws_manager.disconnect(self.connection_id)
        logger.info(f"WebSocket disconnected: {self.connection_id}")

    async def receive(self, text_data):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text_data)
            await ws_manager.handle_message(self.connection, self.connection_id, data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "error": "Invalid JSON"}))
        except Exception as e:
            logger.exception("Error handling WebSocket message")
            await self.send(text_data=json.dumps({"type": "error", "error": str(e)}))


# Channel layer helper for broadcasting
async def broadcast_component_update(component_id: str, html: str, state: dict):
    """
    Broadcast component update via WebSocket manager.

    Can be called from anywhere (views, signals, tasks, etc.)

    Usage:
        from component_framework.adapters.django_websocket import broadcast_component_update

        # In a view or signal handler
        await broadcast_component_update(
            component_id="order-123",
            html=rendered_html,
            state={"status": "completed"}
        )
    """
    await ws_manager.push_update(component_id, html, state)
