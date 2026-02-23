"""FastAPI WebSocket adapter."""

import logging
from uuid import uuid4

try:
    from fastapi import WebSocket, WebSocketDisconnect
except ImportError as e:
    from . import _require_extra

    raise _require_extra("fastapi", "fastapi") from e

from ..core.websocket import WebSocketConnection, ws_manager

logger = logging.getLogger(__name__)


class FastAPIWebSocketConnection(WebSocketConnection):
    """FastAPI WebSocket connection wrapper."""

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


async def component_websocket_endpoint(websocket: WebSocket):
    """
    FastAPI WebSocket endpoint for components.

    Usage in FastAPI app:
        from fastapi import FastAPI
        from component_framework.adapters.fastapi_websocket import component_websocket_endpoint

        app = FastAPI()

        @app.websocket("/ws")
        async def websocket_route(websocket: WebSocket):
            await component_websocket_endpoint(websocket)
    """
    # Accept connection
    await websocket.accept()

    # Generate connection ID
    connection_id = str(uuid4())
    connection = FastAPIWebSocketConnection(websocket)

    # Register with manager
    await ws_manager.connect(connection, connection_id)

    try:
        # Send connection confirmation
        await connection.send({"type": "connected", "connection_id": connection_id})

        # Message loop
        while True:
            # Receive message
            data = await connection.receive()

            # Handle message
            await ws_manager.handle_message(connection, connection_id, data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(connection_id)


def create_websocket_route(app):
    """
    Add WebSocket route to FastAPI app.

    Usage:
        from fastapi import FastAPI
        app = FastAPI()
        create_websocket_route(app)
    """

    @app.websocket("/ws")
    async def websocket_route(websocket: WebSocket):
        await component_websocket_endpoint(websocket)
