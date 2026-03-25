"""Tests for Litestar SSE streaming endpoint."""

import json

import pytest

pytest.importorskip("litestar", reason="Install: pip install component-framework[litestar]")

from litestar import Litestar
from litestar.testing import TestClient

from component_framework.adapters.litestar import component_endpoint, stream_component_endpoint
from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry
from component_framework.core.streaming import StreamingComponent


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
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.litestar.registry", reg)
    return reg


@pytest.fixture
def app(fresh_registry):
    app = Litestar(route_handlers=[component_endpoint, stream_component_endpoint])

    @fresh_registry.register("stream_counter")
    class StreamCounter(StreamingComponent):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = 0

        async def on_count_up(self, steps: int = 3):
            for i in range(1, steps + 1):
                self.state["count"] = i
                yield
            self.state["done"] = True

    @fresh_registry.register("regular_counter")
    class RegularCounter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = 0

    return app


@pytest.fixture
def client(app):
    with TestClient(app) as tc:
        yield tc


class TestStreamEndpoint:
    def test_stream_returns_sse_content_type(self, client):
        response = client.post(
            "/components/stream_counter/stream",
            json={"event": "count_up", "payload": {"steps": 2}},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_yields_multiple_frames(self, client):
        response = client.post(
            "/components/stream_counter/stream",
            json={"event": "count_up", "payload": {"steps": 3}},
        )
        lines = [ln for ln in response.text.strip().split("\n") if ln.startswith("data: ")]
        assert len(lines) == 4  # 3 intermediate + 1 final
        frames = [json.loads(ln.removeprefix("data: ")) for ln in lines]
        assert frames[-1]["stream_done"] is True
        final_state = json.loads(frames[-1]["state"])
        assert final_state["done"] is True

    def test_stream_component_not_found(self, client):
        response = client.post("/components/nonexistent/stream", json={})
        assert response.status_code == 404

    def test_stream_non_streaming_component(self, client):
        response = client.post(
            "/components/regular_counter/stream",
            json={"event": "count_up"},
        )
        assert response.status_code == 400
