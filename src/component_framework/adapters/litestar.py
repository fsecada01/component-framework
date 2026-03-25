"""Litestar adapter for component endpoints."""

import json
import logging

try:
    from litestar import Request, post
    from litestar.exceptions import HTTPException
    from litestar.response import Response
except ImportError as e:
    from . import _require_extra

    raise _require_extra("litestar", "litestar") from e

from ..core import StateSerializer, registry

logger = logging.getLogger(__name__)


@post("/components/{name:str}")
async def component_endpoint(name: str, request: Request) -> Response:
    """
    Generic component endpoint for Litestar.

    POST /components/{name}
    Body: {
        "event": "event_name",
        "payload": {...},
        "state": "serialized_state"
    }

    Returns: {
        "html": "rendered_html",
        "state": "serialized_state",
        "component_id": "component-id"
    }
    """
    try:
        # Get component class
        component_cls = registry.get(name)
        if not component_cls:
            raise HTTPException(status_code=404, detail=f"Component '{name}' not found")

        # Parse request data
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

        # Extract parameters
        params = data.get("params", {})
        event = data.get("event")
        payload_raw = data.get("payload", {})
        state_str = data.get("state")

        # Guard against double-serialised payload from older client JS
        if isinstance(payload_raw, str):
            try:
                payload = json.loads(payload_raw)
            except (json.JSONDecodeError, ValueError):
                payload = {}
        else:
            payload = payload_raw

        # Deserialize state if provided
        state = None
        if state_str:
            try:
                state = StateSerializer.deserialize(state_str)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid state: {e}")

        # Create and dispatch component (async to support async on_* handlers)
        component = component_cls(**params)
        result = await component.async_dispatch(event=event, payload=payload, state=state)

        # Serialize state for response
        result["state"] = StateSerializer.serialize(result["state"])

        return Response(content=result, media_type="application/json", status_code=200)

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Error processing component '{name}'")
        raise HTTPException(status_code=500, detail="Internal server error")


def create_component_routes(app):
    """
    Register the component endpoint handler with a Litestar app.

    Usage:
        from litestar import Litestar
        from component_framework.adapters.litestar import create_component_routes

        app = Litestar(route_handlers=[])
        create_component_routes(app)

    Alternatively, pass the handler directly at app creation:
        from component_framework.adapters.litestar import component_endpoint

        app = Litestar(route_handlers=[component_endpoint])
    """
    app.register(component_endpoint)
