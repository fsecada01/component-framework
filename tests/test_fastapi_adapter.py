"""Tests for FastAPI adapter endpoints."""

import json

import pytest

pytest.importorskip("fastapi", reason="Install: pip install component-framework[fastapi]")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from component_framework.adapters.fastapi import create_component_routes
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
    monkeypatch.setattr("component_framework.adapters.fastapi.registry", reg)
    return reg


@pytest.fixture
def app(fresh_registry):
    """Create a FastAPI test app with component routes."""
    app = FastAPI()
    create_component_routes(app)

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
    return TestClient(app)


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


# ---------- create_component_routes ----------


class TestCreateComponentRoutes:
    def test_routes_added(self, app):
        routes = [r.path for r in app.routes]
        assert "/components/{name}" in routes

    def test_post_method_only(self, client):
        response = client.get("/components/test_counter")
        assert response.status_code == 405
