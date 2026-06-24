"""Tests for the Flask adapter (issue #5).

Constitution: adapter tests must guard the optional dependency with
``pytest.importorskip("flask")`` so the suite still runs without the extra.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("flask")

from flask import Flask  # noqa: E402
from jinja2 import DictLoader, Environment  # noqa: E402

from component_framework.adapters.flask import (  # noqa: E402
    FlaskRenderer,
    register_component_routes,
)
from component_framework.core import Component, Renderer  # noqa: E402
from component_framework.core.registry import ComponentRegistry  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    """Minimal renderer so dispatch tests need no real templates."""

    def render(self, template_name: str, context: dict) -> str:
        state = context.get("state", {})
        return f'<div id="{context.get("component_id", "")}">count={state.get("count", 0)}</div>'


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def fresh_registry(monkeypatch):
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.flask.registry", reg)
    return reg


@pytest.fixture
def counter_cls(fresh_registry):
    @fresh_registry.register("counter")
    class Counter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = self.params.get("initial", 0)

        def on_increment(self, amount: int = 1):
            self.state["count"] = self.state.get("count", 0) + amount

    return Counter


@pytest.fixture
def client(counter_cls):
    app = Flask(__name__)
    register_component_routes(app)
    return app.test_client()


# ---------------------------------------------------------------------------
# FlaskRenderer
# ---------------------------------------------------------------------------


class TestFlaskRenderer:
    def test_renders_via_jinja_environment(self):
        env = Environment(loader=DictLoader({"hello.html": "Hi {{ name }}"}))
        renderer = FlaskRenderer(env)
        assert renderer.render("hello.html", {"name": "world"}) == "Hi world"

    def test_accepts_flask_app_and_shares_its_env(self):
        app = Flask(__name__)
        app.jinja_env.loader = DictLoader({"g.html": "{{ greet }}"})
        app.jinja_env.globals["greet"] = "hello"
        renderer = FlaskRenderer(app)
        # The renderer uses the app's environment, so app globals are available.
        assert renderer.env is app.jinja_env
        assert renderer.render("g.html", {}) == "hello"


# ---------------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------------


class TestComponentEndpoint:
    def test_dispatch_increment_json(self, client):
        resp = client.post(
            "/components/counter",
            data=json.dumps(
                {"event": "increment", "payload": {"amount": 2}, "state": json.dumps({"count": 5})}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["component_id"]
        assert json.loads(data["state"])["count"] == 7
        assert "count=7" in data["html"]

    def test_mount_without_event(self, client):
        resp = client.post(
            "/components/counter",
            data=json.dumps({"params": {"initial": 3}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_json()["state"])["count"] == 3

    def test_form_encoded_dispatch(self, client):
        # HTMX-style form-encoded request.
        resp = client.post(
            "/components/counter",
            data={
                "event": "increment",
                "payload": json.dumps({"amount": 1}),
                "state": json.dumps({"count": 0}),
            },
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_json()["state"])["count"] == 1

    def test_trailing_slash_matches(self, client):
        # The bundled component-client.js posts to "/components/<name>/".
        resp = client.post(
            "/components/counter/",
            data=json.dumps({"event": "increment", "state": json.dumps({"count": 0})}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_json()["state"])["count"] == 1

    def test_unknown_component_404(self, client):
        resp = client.post("/components/nope", json={"event": "x"})
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"]

    def test_invalid_json_400(self, client):
        resp = client.post("/components/counter", data="{not json", content_type="application/json")
        assert resp.status_code == 400

    def test_handler_error_500(self, client):
        # 'decrement' has no handler -> EventNotFoundError -> 500.
        resp = client.post(
            "/components/counter",
            data=json.dumps({"event": "decrement", "state": json.dumps({"count": 0})}),
            content_type="application/json",
        )
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Internal server error"
