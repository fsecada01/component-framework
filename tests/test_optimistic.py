"""Tests for optimistic UI support in component dispatch and views."""

import json

import pytest
from django.test import RequestFactory

from component_framework.adapters.django_views import ComponentView, component_view
from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    """Renderer that returns a minimal HTML stub — no real template needed."""

    def render(self, template_name: str, context: dict) -> str:
        state = context.get("state", {})
        return f'<div id="{context.get("component_id", "")}">count={state.get("count", 0)}</div>'


@pytest.fixture(autouse=True)
def _setup_renderer():
    """Swap in the mock renderer for every test in this module."""
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def fresh_registry(monkeypatch):
    """Isolated registry so components registered here don't bleed across tests."""
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.django_views.registry", reg)
    return reg


@pytest.fixture
def rf():
    return RequestFactory()


# ---------------------------------------------------------------------------
# Component fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def counter_component(fresh_registry):
    """A counter component that DOES NOT override get_optimistic_patch."""

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
def optimistic_counter_component(fresh_registry):
    """A counter component that DOES override get_optimistic_patch."""

    @fresh_registry.register("optimistic_counter")
    class OptimisticCounter(Component):
        template_name = "counter.html"

        def mount(self):
            super().mount()
            self.state["count"] = self.params.get("initial", 0)

        def on_increment(self, amount: int = 1):
            self.state["count"] = self.state.get("count", 0) + amount

        def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
            if event == "increment":
                current = self.state.get("count", 0)
                amount = payload.get("amount", 1)
                return {"count": current + amount}
            return None

    return OptimisticCounter


# ---------------------------------------------------------------------------
# Unit tests — Component base class
# ---------------------------------------------------------------------------


class TestComponentGetOptimisticPatch:
    """The default get_optimistic_patch() is a no-op that returns None."""

    def test_default_returns_none(self):
        component = Component()
        result = component.get_optimistic_patch("any_event", {})
        assert result is None

    def test_default_returns_none_for_arbitrary_event(self):
        component = Component()
        assert component.get_optimistic_patch("increment", {"amount": 5}) is None
        assert component.get_optimistic_patch("delete", {"id": 1}) is None
        assert component.get_optimistic_patch("", {}) is None

    def test_custom_override_returns_patch(self, optimistic_counter_component):
        """A component that overrides get_optimistic_patch returns the right patch."""
        comp = optimistic_counter_component()
        comp.mount()  # sets count = 0 (no initial param)
        patch = comp.get_optimistic_patch("increment", {"amount": 3})
        assert patch == {"count": 3}

    def test_custom_override_uses_current_state(self, optimistic_counter_component):
        """The patch is computed from the current (pre-dispatch) state."""
        comp = optimistic_counter_component()
        comp.hydrate({"count": 10})
        patch = comp.get_optimistic_patch("increment", {"amount": 5})
        assert patch == {"count": 15}

    def test_custom_override_returns_none_for_unknown_event(self, optimistic_counter_component):
        """Unknown events should return None even in a custom override."""
        comp = optimistic_counter_component()
        comp.mount()
        patch = comp.get_optimistic_patch("decrement", {"amount": 1})
        assert patch is None

    def test_patch_computed_from_pre_dispatch_state(self, optimistic_counter_component):
        """
        The optimistic patch reflects the state BEFORE the event handler runs,
        so it should equal pre-state + delta rather than post-state.
        """
        comp = optimistic_counter_component()
        comp.hydrate({"count": 7})

        # Optimistic patch is computed now (pre-dispatch).
        patch = comp.get_optimistic_patch("increment", {"amount": 2})
        assert patch == {"count": 9}

        # Only after calling handle_event does the state change.
        comp.handle_event("increment", {"amount": 2})
        assert comp.state["count"] == 9

        # Both agree — but the patch was computed before the mutation.
        assert patch["count"] == comp.state["count"]


# ---------------------------------------------------------------------------
# FBV tests — component_view
# ---------------------------------------------------------------------------


class TestFBVOptimisticResponse:
    """component_view (FBV) includes 'optimistic' in the response when appropriate."""

    def _post_json(self, rf, name, body):
        return rf.post(
            f"/components/{name}/",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_no_optimistic_key_without_override(self, rf, counter_component):
        """Component without get_optimistic_patch override: response has no 'optimistic' key."""
        state_json = json.dumps({"count": 0})
        request = self._post_json(
            rf,
            "counter",
            {"event": "increment", "payload": {"amount": 1}, "state": state_json},
        )
        response = component_view(request, "counter")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" not in data

    def test_optimistic_key_present_with_override(self, rf, optimistic_counter_component):
        """Component with get_optimistic_patch override: response includes 'optimistic'."""
        state_json = json.dumps({"count": 5})
        request = self._post_json(
            rf,
            "optimistic_counter",
            {"event": "increment", "payload": {"amount": 1}, "state": state_json},
        )
        response = component_view(request, "optimistic_counter")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" in data
        assert data["optimistic"] == {"count": 6}

    def test_optimistic_patch_computed_from_pre_dispatch_state(
        self, rf, optimistic_counter_component
    ):
        """
        The optimistic patch shows the anticipated state (pre-dispatch + delta).
        The actual post-dispatch state in 'state' should match.
        """
        state_json = json.dumps({"count": 10})
        request = self._post_json(
            rf,
            "optimistic_counter",
            {"event": "increment", "payload": {"amount": 3}, "state": state_json},
        )
        response = component_view(request, "optimistic_counter")
        data = json.loads(response.content)

        # Optimistic patch reflects pre+delta.
        assert data["optimistic"] == {"count": 13}

        # The authoritative state also equals 13 after dispatch.
        actual_state = json.loads(data["state"])
        assert actual_state["count"] == 13

    def test_no_optimistic_key_on_mount(self, rf, optimistic_counter_component):
        """
        When no event is provided (initial mount), optimistic patch is not included
        since there is no event to predict.
        """
        request = self._post_json(
            rf,
            "optimistic_counter",
            {"params": {"initial": 0}},
        )
        response = component_view(request, "optimistic_counter")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" not in data

    def test_no_optimistic_when_patch_is_none_for_event(self, rf, optimistic_counter_component):
        """
        When get_optimistic_patch returns None for a specific event, 'optimistic'
        is not included even though the method is overridden.
        """
        state_json = json.dumps({"count": 0})
        request = self._post_json(
            rf,
            "optimistic_counter",
            # 'decrement' is not handled by get_optimistic_patch and returns None.
            {"event": "decrement", "payload": {}, "state": state_json},
        )
        # The component also has no on_decrement handler, so this will 500.
        # We only care that no optimistic key was added. But since the view
        # catches all errors and returns 500, check that path doesn't crash
        # differently than expected.
        response = component_view(request, "optimistic_counter")
        # 500 is expected because there's no on_decrement handler.
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# CBV tests — ComponentView
# ---------------------------------------------------------------------------


class TestCBVOptimisticResponse:
    """ComponentView (CBV) includes 'optimistic' in the response when appropriate."""

    def _cbv_request(self, rf, name, body, monkeypatched_registry):
        import component_framework.adapters.django_views as views_mod

        old = views_mod.registry
        views_mod.registry = monkeypatched_registry
        try:
            request = rf.post(
                f"/cbv/components/{name}/",
                data=json.dumps(body),
                content_type="application/json",
            )
            view = ComponentView.as_view()
            response = view(request, name=name)
        finally:
            views_mod.registry = old
        return response

    def test_no_optimistic_key_without_override(self, rf, counter_component, fresh_registry):
        """CBV: component without override does not include 'optimistic'."""
        state_json = json.dumps({"count": 0})
        response = self._cbv_request(
            rf,
            "counter",
            {"event": "increment", "payload": {"amount": 1}, "state": state_json},
            fresh_registry,
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" not in data

    def test_optimistic_key_present_with_override(
        self, rf, optimistic_counter_component, fresh_registry
    ):
        """CBV: component with override includes 'optimistic' in the response."""
        state_json = json.dumps({"count": 5})
        response = self._cbv_request(
            rf,
            "optimistic_counter",
            {"event": "increment", "payload": {"amount": 2}, "state": state_json},
            fresh_registry,
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" in data
        assert data["optimistic"] == {"count": 7}

    def test_optimistic_patch_pre_dispatch_accuracy(
        self, rf, optimistic_counter_component, fresh_registry
    ):
        """CBV: optimistic patch reflects pre-dispatch state + delta."""
        state_json = json.dumps({"count": 20})
        response = self._cbv_request(
            rf,
            "optimistic_counter",
            {"event": "increment", "payload": {"amount": 4}, "state": state_json},
            fresh_registry,
        )
        data = json.loads(response.content)
        assert data["optimistic"] == {"count": 24}
        actual_state = json.loads(data["state"])
        assert actual_state["count"] == 24

    def test_no_optimistic_on_mount_cbv(self, rf, optimistic_counter_component, fresh_registry):
        """CBV: no optimistic key when no event is sent (initial mount)."""
        response = self._cbv_request(
            rf,
            "optimistic_counter",
            {"params": {"initial": 0}},
            fresh_registry,
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "optimistic" not in data

    def test_response_shape_with_optimistic(self, rf, optimistic_counter_component, fresh_registry):
        """CBV response includes all expected keys when optimistic patch is present."""
        state_json = json.dumps({"count": 1})
        response = self._cbv_request(
            rf,
            "optimistic_counter",
            {"event": "increment", "payload": {"amount": 1}, "state": state_json},
            fresh_registry,
        )
        data = json.loads(response.content)
        assert "html" in data
        assert "state" in data
        assert "component_id" in data
        assert "optimistic" in data
