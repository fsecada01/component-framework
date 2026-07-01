"""FastAPI adapter for component endpoints."""

import json
import logging

try:
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    from starlette.responses import StreamingResponse
except ImportError as e:
    from . import _require_extra

    raise _require_extra("fastapi", "fastapi") from e

from ..core import StateSerializer, registry
from ..core.streaming import StreamingComponent, format_sse_frame

logger = logging.getLogger(__name__)


def _parse_json_str(value: str | dict | None, default: dict | None = None) -> dict | None:
    """Parse a value that may be a JSON string, a dict, or None."""
    if value is None:
        return default
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return default


async def _parse_request_data(request: Request) -> dict:
    """Parse request body from JSON or form-encoded data.

    HTMX sends ``application/x-www-form-urlencoded`` by default; the JS
    ``component-client.js`` sends ``application/json``.  This helper
    normalises both into a dict with ``event``, ``payload``, ``state``,
    and ``params`` keys.
    """
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    else:
        # Form-encoded (HTMX default) — hx-vals are merged into form fields
        form = await request.form()
        data = dict(form)

    return data


def _extract_params(data: dict) -> tuple[dict, str | None, dict, dict | None]:
    """Extract and normalise event, payload, state, and params from parsed data.

    Returns:
        (params, event, payload, state) tuple ready for component dispatch.
    """
    params = _parse_json_str(data.get("params"), default={}) or {}
    event = data.get("event")
    payload = _parse_json_str(data.get("payload"), default={}) or {}
    try:
        state = StateSerializer.load_untrusted(data.get("state"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid state: {e}")

    return params, event, payload, state


async def component_endpoint(name: str, request: Request) -> JSONResponse:
    """
    Generic component endpoint for FastAPI.

    POST /components/{name}
    Body (JSON or form-encoded): {
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
        component_cls = registry.get(name)
        if not component_cls:
            raise HTTPException(status_code=404, detail=f"Component '{name}' not found")

        data = await _parse_request_data(request)
        params, event, payload, state = _extract_params(data)

        component = component_cls(**params)
        result = await component.async_dispatch(event=event, payload=payload, state=state)

        result["state"] = StateSerializer.serialize(result["state"])

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Error processing component '{name}'")
        raise HTTPException(status_code=500, detail="Internal server error")


async def stream_component_endpoint(name: str, request: Request) -> StreamingResponse:
    """
    SSE streaming endpoint for long-running component operations.

    POST /components/{name}/stream
    Body (JSON or form-encoded): same as component_endpoint

    Returns: text/event-stream with one ``data:`` frame per intermediate render.
    """
    try:
        component_cls = registry.get(name)
        if not component_cls:
            raise HTTPException(status_code=404, detail=f"Component '{name}' not found")

        if not issubclass(component_cls, StreamingComponent):
            raise HTTPException(
                status_code=400,
                detail=f"Component '{name}' does not support streaming",
            )

        data = await _parse_request_data(request)
        params, event, payload, state = _extract_params(data)

        component = component_cls(**params)

        async def event_generator():
            async for frame in component.async_stream_dispatch(
                event=event, payload=payload, state=state
            ):
                frame["state"] = StateSerializer.serialize(frame["state"])
                yield format_sse_frame(frame)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Error processing streaming component '{name}'")
        raise HTTPException(status_code=500, detail="Internal server error")


def create_component_routes(app):
    """
    Add component endpoints to FastAPI app.

    Registers both the standard POST endpoint and the SSE streaming endpoint.

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
    app.add_api_route(
        "/components/{name}/stream",
        stream_component_endpoint,
        methods=["POST"],
        name="stream_component_endpoint",
    )
