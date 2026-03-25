"""Tests for Litestar adapter endpoints."""

import json

import pytest

pytest.importorskip("litestar", reason="Install: pip install component-framework[litestar]")

from litestar import Litestar
from litestar.testing import TestClient

from component_framework.adapters.litestar import component_endpoint
from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}: {context.get('state', {})}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def fresh_registry(monkeypatch):
    """Provide a fresh registry and patch the global one."""
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.litestar.registry", reg)
    return reg


@pytest.fixture
def app(fresh_registry):
    """Create a Litestar test app with component routes."""
    app = Litestar(route_handlers=[component_endpoint])

    @fresh_registry.register("test_counter")
    class TestCounter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = self.params.get("initial", 0)

        def on_increment(self, amount: int = 1):
            self.state["count"] = self.state.get("count", 0) + amount

    return app


@pytest.fixture
def client(app):
    with TestClient(app) as tc:
        yield tc


# ---------- component_endpoint ----------


class TestComponentEndpoint:
    def test_mount_component(self, client):
        response = client.post(
            "/components/test_counter",
            json={"params": {"initial": 5}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "html" in data
        assert "state" in data
        assert "component_id" in data

    def test_handle_event(self, client):
        # Mount first
        r1 = client.post("/components/test_counter", json={})
        state = r1.json()["state"]

        # Fire event
        r2 = client.post(
            "/components/test_counter",
            json={"event": "increment", "payload": {"amount": 3}, "state": state},
        )
        assert r2.status_code == 200
        deserialized = json.loads(r2.json()["state"])
        assert deserialized["count"] == 3

    def test_component_not_found(self, client):
        response = client.post("/components/nonexistent", json={})
        assert response.status_code == 404

    def test_invalid_json_body(self, client):
        response = client.post(
            "/components/test_counter",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_invalid_state(self, client):
        response = client.post(
            "/components/test_counter",
            json={"state": "not-valid-json"},
        )
        assert response.status_code == 400

    def test_mount_with_no_params(self, client):
        response = client.post("/components/test_counter", json={})
        assert response.status_code == 200
        data = response.json()
        deserialized = json.loads(data["state"])
        assert deserialized["count"] == 0

    def test_form_encoded_mount(self, client):
        """HTMX sends form-encoded by default — adapter must accept it."""
        response = client.post(
            "/components/test_counter",
            data={"params": '{"initial": 5}'},
        )
        assert response.status_code == 200
        data = response.json()
        deserialized = json.loads(data["state"])
        assert deserialized["count"] == 5

    def test_form_encoded_event(self, client):
        """HTMX hx-vals are merged into form fields."""
        # Mount first (JSON)
        r1 = client.post("/components/test_counter", json={})
        state = r1.json()["state"]

        # Fire event via form-encoded (HTMX style)
        r2 = client.post(
            "/components/test_counter",
            data={
                "event": "increment",
                "payload": '{"amount": 7}',
                "state": state,
            },
        )
        assert r2.status_code == 200
        deserialized = json.loads(r2.json()["state"])
        assert deserialized["count"] == 7


# ---------- route registration ----------


class TestRouteRegistration:
    def test_routes_added(self, app):
        route_paths = [r.path for r in app.routes]
        assert "/components/{name:str}" in route_paths

    def test_post_method_only(self, client):
        response = client.get("/components/test_counter")
        assert response.status_code == 405
