"""FastAPI adapter for component endpoints."""

import logging

try:
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
except ImportError as e:
    from . import _require_extra

    raise _require_extra("fastapi", "fastapi") from e

from ..core import StateSerializer, registry

logger = logging.getLogger(__name__)


async def component_endpoint(name: str, request: Request) -> JSONResponse:
    """
    Generic component endpoint for FastAPI.

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
        payload = data.get("payload", {})
        state_str = data.get("state")

        # Deserialize state if provided
        state = None
        if state_str:
            try:
                state = StateSerializer.deserialize(state_str)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid state: {e}")

        # Create and dispatch component
        component = component_cls(**params)
        result = component.dispatch(event=event, payload=payload, state=state)

        # Serialize state for response
        result["state"] = StateSerializer.serialize(result["state"])

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Error processing component '{name}'")
        raise HTTPException(status_code=500, detail="Internal server error")


def create_component_routes(app):
    """
    Add component endpoint to FastAPI app.

    Usage:
        from fastapi import FastAPI
        app = FastAPI()
        create_component_routes(app)
    """
    app.add_api_route(
        "/components/{name}",
        component_endpoint,
        methods=["POST"],
        name="component_endpoint",
    )
