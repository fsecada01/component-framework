"""Tests for FastAPI WebSocket adapter."""

import pytest

pytest.importorskip("fastapi", reason="Install: pip install component-framework[fastapi]")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from component_framework.adapters.fastapi_websocket import (
    create_websocket_route,
)
from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry
from component_framework.core.websocket import ComponentWebSocketManager


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def fresh_registry(monkeypatch):
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.core.websocket.registry", reg)
    return reg


@pytest.fixture
def fresh_manager(monkeypatch):
    manager = ComponentWebSocketManager()
    monkeypatch.setattr("component_framework.adapters.fastapi_websocket.ws_manager", manager)
    monkeypatch.setattr("component_framework.core.websocket.ws_manager", manager)
    return manager


@pytest.fixture
def app(fresh_registry, fresh_manager):
    app = FastAPI()
    create_websocket_route(app)

    @fresh_registry.register("ws_counter")
    class WSCounter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = 0

        def on_increment(self):
            self.state["count"] = self.state.get("count", 0) + 1

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestWebSocketConnection:
    def test_connect_and_receive_confirmation(self, client):
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "connection_id" in data

    def test_subscribe_to_component(self, client):
        with client.websocket_connect("/ws") as ws:
            # Skip connection confirmation
            ws.receive_json()

            ws.send_json({"type": "subscribe", "component_id": "comp-1"})
            response = ws.receive_json()
            assert response["type"] == "subscribed"
            assert response["component_id"] == "comp-1"

    def test_unsubscribe_from_component(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()

            ws.send_json({"type": "subscribe", "component_id": "comp-1"})
            ws.receive_json()  # subscribed

            ws.send_json({"type": "unsubscribe", "component_id": "comp-1"})
            response = ws.receive_json()
            assert response["type"] == "unsubscribed"

    def test_component_event(self, client, fresh_registry):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connected

            ws.send_json(
                {
                    "type": "component_event",
                    "component": "ws_counter",
                    "component_id": "counter-1",
                    "event": "increment",
                    "payload": {},
                }
            )
            response = ws.receive_json()
            assert response["type"] == "component_update"
            assert "html" in response

    def test_component_event_not_found(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()

            ws.send_json(
                {
                    "type": "component_event",
                    "component": "nonexistent",
                    "event": "click",
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "not found" in response["error"]

    def test_unknown_message_type(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "unknown_type"})
            # Server logs warning but connection stays open; no response expected


class TestCreateWebSocketRoute:
    def test_route_added(self, app):
        ws_routes = [r.path for r in app.routes if hasattr(r, "path") and "ws" in r.path]
        assert "/ws" in ws_routes
