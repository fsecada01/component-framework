"""Tests for the core Component class and StateSerializer."""

import pytest

from component_framework.core.component import (
    Component,
    ComponentError,
    EventNotFoundError,
    StateSerializer,
)
from component_framework.core.renderer import Renderer


class MockRenderer(Renderer):
    """Mock renderer for testing."""

    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}: {context}</div>"


class SampleComponent(Component):
    """Test component with event handlers."""

    template_name = "sample.html"

    def mount(self):
        super().mount()
        self.state["value"] = self.params.get("initial", 0)

    def on_update(self, value: int):
        self.state["value"] = value

    def on_failing_event(self):
        raise ValueError("intentional error")

    def before_render(self):
        self.state["doubled"] = self.state.get("value", 0) * 2


# ---------- Component Lifecycle ----------


class TestComponentInit:
    def test_default_id_generated(self):
        comp = Component()
        assert comp.id.startswith("component-")
        assert len(comp.id) == len("component-") + 8

    def test_custom_id_from_params(self):
        comp = Component(component_id="my-id")
        assert comp.id == "my-id"

    def test_initial_state_empty(self):
        comp = Component()
        assert comp.state == {}
        assert comp.errors == {}
        assert comp._mounted is False

    def test_params_stored(self):
        comp = Component(foo="bar", num=42)
        assert comp.params == {"foo": "bar", "num": 42}


class TestComponentMount:
    def test_mount_sets_mounted_flag(self):
        comp = Component()
        comp.mount()
        assert comp._mounted is True

    def test_subclass_mount_initializes_state(self):
        comp = SampleComponent(initial=10)
        comp.mount()
        assert comp.state["value"] == 10
        assert comp._mounted is True


class TestComponentHydrate:
    def test_hydrate_restores_state(self):
        comp = Component()
        comp.hydrate({"count": 5, "name": "test"})
        assert comp.state == {"count": 5, "name": "test"}
        assert comp._mounted is True

    def test_hydrate_merges_with_existing_state(self):
        comp = Component()
        comp.state["existing"] = True
        comp.hydrate({"new_key": "value"})
        assert comp.state["existing"] is True
        assert comp.state["new_key"] == "value"


class TestComponentDehydrate:
    def test_dehydrate_returns_state_copy(self):
        comp = Component()
        comp.state = {"count": 42}
        result = comp.dehydrate()
        assert result == {"count": 42}
        # Verify it's a copy, not the same reference
        result["count"] = 0
        assert comp.state["count"] == 42


# ---------- Event Handling ----------


class TestComponentEvents:
    def test_handle_event_routes_to_handler(self):
        Component.renderer = MockRenderer()
        comp = SampleComponent()
        comp.mount()
        comp.handle_event("update", {"value": 99})
        assert comp.state["value"] == 99

    def test_handle_event_missing_handler_raises(self):
        comp = SampleComponent()
        with pytest.raises(EventNotFoundError, match="No handler for event: nonexistent"):
            comp.handle_event("nonexistent", {})

    def test_handle_event_invalid_payload_raises(self):
        comp = SampleComponent()
        comp.mount()
        with pytest.raises(ComponentError, match="Invalid payload for update"):
            comp.handle_event("update", {"wrong_param": 1})

    def test_handle_event_handler_exception_wrapped(self):
        comp = SampleComponent()
        comp.mount()
        with pytest.raises(ComponentError, match="Error handling failing_event"):
            comp.handle_event("failing_event", {})


# ---------- Rendering ----------


class TestComponentRendering:
    def setup_method(self):
        Component.renderer = MockRenderer()

    def test_render_calls_renderer(self):
        comp = SampleComponent()
        comp.mount()
        html = comp.render()
        assert "sample.html" in html

    def test_render_no_renderer_raises(self):
        old = Component.renderer
        Component.renderer = None
        try:
            comp = SampleComponent()
            with pytest.raises(ComponentError, match="No renderer configured"):
                comp.render()
        finally:
            Component.renderer = old

    def test_render_no_template_raises(self):
        comp = Component()  # No template_name
        with pytest.raises(ComponentError, match="No template_name specified"):
            comp.render()

    def test_before_render_called(self):
        comp = SampleComponent(initial=5)
        comp.mount()
        comp.render()
        assert comp.state["doubled"] == 10

    def test_get_context_contents(self):
        comp = Component(component_id="test-123")
        comp.state = {"key": "val"}
        comp.errors = {"field": "err"}
        ctx = comp.get_context()
        assert ctx["state"] == {"key": "val"}
        assert ctx["errors"] == {"field": "err"}
        assert ctx["component_id"] == "test-123"


# ---------- Dispatch ----------


class TestComponentDispatch:
    def setup_method(self):
        Component.renderer = MockRenderer()

    def test_dispatch_mount_path(self):
        comp = SampleComponent(initial=7)
        result = comp.dispatch()
        assert result["state"]["value"] == 7
        assert result["state"]["doubled"] == 14
        assert "html" in result
        assert "component_id" in result

    def test_dispatch_hydrate_path(self):
        comp = SampleComponent()
        result = comp.dispatch(state={"value": 20})
        assert result["state"]["value"] == 20

    def test_dispatch_with_event(self):
        comp = SampleComponent()
        result = comp.dispatch(event="update", payload={"value": 50}, state={"value": 0})
        assert result["state"]["value"] == 50

    def test_dispatch_event_error_propagates(self):
        comp = SampleComponent()
        with pytest.raises(ComponentError):
            comp.dispatch(event="nonexistent", state={"value": 0})


# ---------- StateSerializer ----------


class TestStateSerializer:
    def test_serialize_basic(self):
        result = StateSerializer.serialize({"count": 1, "name": "test"})
        assert '"count": 1' in result
        assert '"name": "test"' in result

    def test_deserialize_basic(self):
        result = StateSerializer.deserialize('{"count": 1}')
        assert result == {"count": 1}

    def test_deserialize_empty_string(self):
        assert StateSerializer.deserialize("") == {}

    def test_roundtrip(self):
        original = {"count": 42, "items": [1, 2, 3], "nested": {"a": True}}
        serialized = StateSerializer.serialize(original)
        deserialized = StateSerializer.deserialize(serialized)
        assert deserialized == original

    def test_serialize_non_json_types_uses_str(self):
        from datetime import datetime

        dt = datetime(2026, 1, 1, 12, 0, 0)
        result = StateSerializer.serialize({"date": dt})
        assert "2026-01-01" in result

    def test_deserialize_invalid_json_raises(self):
        with pytest.raises(Exception):
            StateSerializer.deserialize("not json")
