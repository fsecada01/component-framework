"""Litestar WebSocket adapter."""

import logging
from uuid import uuid4

try:
    from litestar import WebSocket
    from litestar.exceptions import WebSocketDisconnect
except ImportError as e:
    from . import _require_extra

    raise _require_extra("litestar", "litestar") from e

from ..core.websocket import WebSocketConnection, ws_manager

logger = logging.getLogger(__name__)


class LitestarWebSocketConnection(WebSocketConnection):
    """Litestar WebSocket connection wrapper."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def send(self, data: dict):
        """Send JSON data to client."""
        await self.websocket.send_json(data)

    async def receive(self) -> dict:
        """Receive JSON data from client."""
        return await self.websocket.receive_json()

    async def close(self):
        """Close WebSocket connection."""
        await self.websocket.close()


async def component_websocket_endpoint(websocket: WebSocket) -> None:
    """
    Litestar WebSocket endpoint for components.

    Usage in a Litestar app:
        from litestar import Litestar, websocket_listener
        from component_framework.adapters.litestar_websocket import (
            component_websocket_endpoint,
        )

        @websocket_listener("/ws")
        async def ws_handler(websocket: WebSocket) -> None:
            await component_websocket_endpoint(websocket)

        app = Litestar(route_handlers=[ws_handler])
    """
    # Accept connection
    await websocket.accept()

    # Generate connection ID
    connection_id = str(uuid4())
    connection = LitestarWebSocketConnection(websocket)

    # Register with manager
    await ws_manager.connect(connection, connection_id)

    try:
        # Send connection confirmation
        await connection.send({"type": "connected", "connection_id": connection_id})

        # Message loop
        while True:
            data = await connection.receive()
            await ws_manager.handle_message(connection, connection_id, data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(connection_id)
