"""Flask adapter for component endpoints.

Provides a Jinja2-backed :class:`FlaskRenderer` and a synchronous HTTP endpoint
(exposed as a Flask blueprint) that dispatches events to the component registry,
mirroring the protocol used by the FastAPI, Litestar, and Django adapters.

Install with the ``flask`` extra::

    pip install "component-framework[flask]"
"""

import json
import logging

try:
    from flask import Blueprint, jsonify, request
except ImportError as e:
    from . import _require_extra

    raise _require_extra("flask", "flask") from e

from ..core import Renderer, StateSerializer, registry

logger = logging.getLogger(__name__)


class FlaskRenderer(Renderer):
    """Renderer backed by a Jinja2 environment.

    Pass the Flask application (or its ``jinja_env``) so component templates
    inherit the app's configured filters, globals, and extensions rather than a
    fresh, empty environment::

        from flask import Flask
        from component_framework.adapters.flask import FlaskRenderer
        from component_framework.core.component import Component

        app = Flask(__name__)
        Component.renderer = FlaskRenderer(app)  # shares app.jinja_env
    """

    def __init__(self, app_or_env):
        """
        Initialize the renderer.

        Args:
            app_or_env: A Flask application (anything exposing a ``jinja_env``
                attribute) or a Jinja2 ``Environment`` directly. Sharing the
                app's environment keeps component templates consistent with the
                rest of the app.
        """
        self.env = getattr(app_or_env, "jinja_env", app_or_env)

    def render(self, template_name: str, context: dict) -> str:
        """Render ``template_name`` with ``context`` via the Jinja2 environment."""
        return self.env.get_template(template_name).render(**context)


def _parse_json_str(value, default: dict | None = None) -> dict | None:
    """Parse a value that may be a JSON string, a dict, or None."""
    if value is None:
        return default
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return default


def _parse_request_data() -> dict:
    """Parse the current Flask request body from JSON or form-encoded data.

    HTMX sends ``application/x-www-form-urlencoded`` by default; the bundled
    ``component-client.js`` sends ``application/json``. Both normalise into a
    dict carrying ``event``, ``payload``, ``state``, and ``params`` keys.

    Raises:
        ValueError: If a JSON content type is declared but the body is invalid.
    """
    if request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            raise ValueError("Invalid JSON body")
        return data
    return request.form.to_dict()


def _extract_params(data: dict) -> tuple[dict, str | None, dict, dict | None]:
    """Extract and normalise event, payload, state, and params from parsed data.

    Returns:
        A ``(params, event, payload, state)`` tuple ready for component dispatch.

    Raises:
        ValueError: If the supplied state cannot be deserialized.
    """
    params = _parse_json_str(data.get("params"), default={}) or {}
    event = data.get("event")
    payload = _parse_json_str(data.get("payload"), default={}) or {}
    state_raw = data.get("state")

    state = None
    if state_raw:
        try:
            state = (
                StateSerializer.deserialize(state_raw) if isinstance(state_raw, str) else state_raw
            )
        except Exception as e:
            raise ValueError(f"Invalid state: {e}")

    return params, event, payload, state


def component_view(name: str):
    """
    Generic component endpoint for Flask.

    POST /components/<name>
    Body (JSON or form-encoded)::

        {"event": "event_name", "payload": {...}, "state": "serialized_state"}

    Returns JSON::

        {"html": "...", "state": "...", "component_id": "...", "slots": {...}}

    Args:
        name: Registered component name from the URL.

    Returns:
        A Flask JSON response with the rendered component, or a JSON error with
        status 404 (unknown component), 400 (bad request), or 500.
    """
    component_cls = registry.get(name)
    if not component_cls:
        return jsonify({"error": f"Component '{name}' not found"}), 404

    try:
        data = _parse_request_data()
        params, event, payload, state = _extract_params(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        component = component_cls(**params)
        result = component.dispatch(event=event, payload=payload, state=state)
        result["state"] = StateSerializer.serialize(result["state"])
        return jsonify(result), 200
    except Exception:
        logger.exception(f"Error processing component '{name}'")
        return jsonify({"error": "Internal server error"}), 500


def create_component_blueprint(url_prefix: str = "/components") -> "Blueprint":
    """
    Build a Flask blueprint exposing the component endpoint.

    Args:
        url_prefix: URL prefix the blueprint is mounted under.

    Returns:
        A :class:`flask.Blueprint` with ``POST <url_prefix>/<name>`` wired to
        :func:`component_view`.

    Usage::

        from flask import Flask
        from component_framework.adapters.flask import create_component_blueprint

        app = Flask(__name__)
        app.register_blueprint(create_component_blueprint())
    """
    bp = Blueprint("components", __name__, url_prefix=url_prefix)
    bp.add_url_rule("/<name>", endpoint="component", view_func=component_view, methods=["POST"])
    return bp


def register_component_routes(app, url_prefix: str = "/components") -> None:
    """
    Register the component blueprint on a Flask application.

    Args:
        app: The Flask application.
        url_prefix: URL prefix to mount the component endpoint under.
    """
    app.register_blueprint(create_component_blueprint(url_prefix=url_prefix))
