"""Tests for Django template tags."""

import json

import pytest

pytest.importorskip("django", reason="Install: pip install component-framework[django]")

from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry
from component_framework.templatetags.components import (
    component_attrs,
    component_errors,
    component_js,
    component_state,
    cotton_component,
    live_component,
)


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div id='{context.get('component_id', '')}'>{template_name}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def fresh_registry(monkeypatch):
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.templatetags.components.registry", reg)
    return reg


@pytest.fixture
def counter_component(fresh_registry):
    @fresh_registry.register("counter")
    class Counter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = self.params.get("initial", 0)

    return Counter


# ---------- live_component ----------


class TestLiveComponent:
    def test_renders_component(self, counter_component):
        result = live_component({}, "counter", initial=5)
        assert "counter.html" in str(result)

    def test_not_found_returns_comment(self, fresh_registry):
        result = live_component({}, "nonexistent")
        assert "not found" in result

    def test_passes_params(self, counter_component):
        result = live_component({}, "counter", initial=10)
        assert isinstance(result, str)


# ---------- component_state ----------


class TestComponentState:
    def test_serializes_state(self):
        result = component_state({"count": 42})
        deserialized = json.loads(result)
        assert deserialized["count"] == 42

    def test_empty_state(self):
        result = component_state({})
        assert result == "{}"


# ---------- htmx_component ----------

# htmx_component requires an actual template file, so we test it indirectly
# through the live_component which shares similar logic.


# ---------- component_errors ----------


class TestComponentErrors:
    def test_get_errors_for_field(self):
        errors = {"email": ["Required"], "name": ["Too short"]}
        assert component_errors(errors, "email") == ["Required"]

    def test_get_errors_missing_field(self):
        errors = {"email": ["Required"]}
        assert component_errors(errors, "name") == []

    def test_non_dict_returns_empty(self):
        assert component_errors(None, "field") == []
        assert component_errors("string", "field") == []


# ---------- component_js ----------


class TestComponentJs:
    def test_generates_script_tag(self):
        result = component_js("comp-123")
        assert "<script>" in str(result)
        assert "comp-123" in str(result)
        assert "WebSocket" in str(result)

    def test_escapes_component_id(self):
        """Verify XSS prevention: component_id is safely JSON-encoded."""
        # Test with double quotes that could break out of a JS string
        result = component_js('test"; alert("xss"); "')
        result_str = str(result)
        # json.dumps escapes internal double quotes, preventing JS breakout
        assert 'alert(\\"xss\\")' in result_str
        # The value is embedded as a JSON-encoded string
        assert "const componentId = " in result_str

    def test_includes_subscribe_logic(self):
        result = component_js("my-comp")
        assert "subscribe" in str(result)


# ---------- cotton_component ----------


class TestCottonComponent:
    def test_renders_component(self, counter_component):
        result = cotton_component({}, "counter", initial=5)
        assert "counter.html" in str(result)

    def test_not_found_returns_comment(self, fresh_registry):
        result = cotton_component({}, "nonexistent")
        assert "not found" in result


# ---------- component_attrs ----------


class TestComponentAttrs:
    def test_generates_htmx_attrs(self):
        result = component_attrs("comp-1", {"count": 5})
        assert 'hx-target="#comp-1"' in str(result)
        assert 'hx-swap="outerHTML"' in str(result)

    def test_extra_attrs(self):
        result = component_attrs("comp-1", {}, **{"hx-post": "/api/"})
        assert 'hx-post="/api/"' in str(result)

    def test_escapes_html_in_attrs(self):
        """Verify XSS prevention in attribute values."""
        result = component_attrs('<script>alert("xss")</script>', {})
        assert "<script>" not in str(result)
        assert "&lt;script&gt;" in str(result)
