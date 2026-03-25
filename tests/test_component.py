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


class AsyncSampleComponent(Component):
    """Test component with async event handlers."""

    template_name = "async_sample.html"

    def mount(self):
        super().mount()
        self.state["value"] = self.params.get("initial", 0)

    async def on_update(self, value: int):
        self.state["value"] = value

    async def on_failing_event(self):
        raise ValueError("intentional async error")

    def on_sync_event(self, value: int = 0):
        self.state["value"] = value

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


# ---------- State Size Guard ----------


class TestStateSizeGuard:
    def setup_method(self):
        self._orig_warn = StateSerializer.warn_bytes
        self._orig_max = StateSerializer.max_bytes

    def teardown_method(self):
        StateSerializer.warn_bytes = self._orig_warn
        StateSerializer.max_bytes = self._orig_max

    def test_warning_on_large_state(self, caplog):
        StateSerializer.warn_bytes = 50
        StateSerializer.max_bytes = 0  # disable hard limit
        big_state = {"data": "x" * 100}
        import logging

        with caplog.at_level(logging.WARNING):
            StateSerializer.serialize(big_state)
        assert "Component state is" in caplog.text
        assert "threshold" in caplog.text

    def test_no_warning_under_threshold(self, caplog):
        StateSerializer.warn_bytes = 100_000
        StateSerializer.max_bytes = 0
        import logging

        with caplog.at_level(logging.WARNING):
            StateSerializer.serialize({"small": True})
        assert "Component state is" not in caplog.text

    def test_error_on_exceeding_hard_limit(self):
        StateSerializer.max_bytes = 50
        big_state = {"data": "x" * 100}
        with pytest.raises(ComponentError, match="hard limit"):
            StateSerializer.serialize(big_state)

    def test_no_error_under_hard_limit(self):
        StateSerializer.max_bytes = 100_000
        result = StateSerializer.serialize({"small": True})
        assert result  # no exception

    def test_guards_disabled_when_zero(self, caplog):
        StateSerializer.warn_bytes = 0
        StateSerializer.max_bytes = 0
        big_state = {"data": "x" * 10_000}
        import logging

        with caplog.at_level(logging.WARNING):
            result = StateSerializer.serialize(big_state)
        assert result
        assert "Component state is" not in caplog.text


# ---------- Async Event Handling ----------


class TestAsyncHandleEvent:
    @pytest.mark.asyncio
    async def test_async_handle_event_routes_to_async_handler(self):
        Component.renderer = MockRenderer()
        comp = AsyncSampleComponent()
        comp.mount()
        await comp.async_handle_event("update", {"value": 99})
        assert comp.state["value"] == 99

    @pytest.mark.asyncio
    async def test_async_handle_event_works_with_sync_handler(self):
        Component.renderer = MockRenderer()
        comp = AsyncSampleComponent()
        comp.mount()
        await comp.async_handle_event("sync_event", {"value": 42})
        assert comp.state["value"] == 42

    @pytest.mark.asyncio
    async def test_async_handle_event_missing_handler_raises(self):
        comp = AsyncSampleComponent()
        with pytest.raises(EventNotFoundError, match="No handler for event: nonexistent"):
            await comp.async_handle_event("nonexistent", {})

    @pytest.mark.asyncio
    async def test_async_handle_event_invalid_payload_raises(self):
        comp = AsyncSampleComponent()
        comp.mount()
        with pytest.raises(ComponentError, match="Invalid payload for update"):
            await comp.async_handle_event("update", {"wrong_param": 1})

    @pytest.mark.asyncio
    async def test_async_handle_event_handler_exception_wrapped(self):
        comp = AsyncSampleComponent()
        comp.mount()
        with pytest.raises(ComponentError, match="Error handling failing_event"):
            await comp.async_handle_event("failing_event", {})

    def test_sync_handle_event_rejects_async_handler(self):
        comp = AsyncSampleComponent()
        comp.mount()
        with pytest.raises(ComponentError, match="is async"):
            comp.handle_event("update", {"value": 1})


# ---------- Async Dispatch ----------


class TestAsyncDispatch:
    def setup_method(self):
        Component.renderer = MockRenderer()

    @pytest.mark.asyncio
    async def test_async_dispatch_mount_path(self):
        comp = AsyncSampleComponent(initial=7)
        result = await comp.async_dispatch()
        assert result["state"]["value"] == 7
        assert result["state"]["doubled"] == 14
        assert "html" in result
        assert "component_id" in result

    @pytest.mark.asyncio
    async def test_async_dispatch_hydrate_path(self):
        comp = AsyncSampleComponent()
        result = await comp.async_dispatch(state={"value": 20})
        assert result["state"]["value"] == 20

    @pytest.mark.asyncio
    async def test_async_dispatch_with_async_event(self):
        comp = AsyncSampleComponent()
        result = await comp.async_dispatch(
            event="update", payload={"value": 50}, state={"value": 0}
        )
        assert result["state"]["value"] == 50

    @pytest.mark.asyncio
    async def test_async_dispatch_with_sync_event(self):
        comp = AsyncSampleComponent()
        result = await comp.async_dispatch(
            event="sync_event", payload={"value": 77}, state={"value": 0}
        )
        assert result["state"]["value"] == 77

    @pytest.mark.asyncio
    async def test_async_dispatch_event_error_propagates(self):
        comp = AsyncSampleComponent()
        with pytest.raises(ComponentError):
            await comp.async_dispatch(event="nonexistent", state={"value": 0})
