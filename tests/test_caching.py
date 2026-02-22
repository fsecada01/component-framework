"""Comprehensive integration tests for CacheMixin."""

import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import RequestFactory

from component_framework.adapters.django_views import CacheMixin, ComponentView
from component_framework.core import Component, Renderer
from component_framework.core.registry import ComponentRegistry

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}: {context.get('state', {})}</div>"


class CachedView(CacheMixin, ComponentView):
    """Standard cached view used across most tests."""

    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_renderer():
    """Install MockRenderer for every test, then restore original."""
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cache before and after every test to avoid bleed."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fresh_registry(monkeypatch):
    """Provide a fresh ComponentRegistry, monkeypatched into the views module."""
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.django_views.registry", reg)
    return reg


@pytest.fixture
def counter_component(fresh_registry):
    """Register a simple counter component with the fresh registry."""

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
def rf():
    return RequestFactory()


# ---------------------------------------------------------------------------
# Helper: build POST request bodies
# ---------------------------------------------------------------------------


def _mount_request(rf: RequestFactory, params: dict | None = None) -> object:
    """Build a JSON POST request that mounts a component (no event)."""
    body: dict = {}
    if params:
        body["params"] = params
    return rf.post(
        "/components/counter/",
        data=json.dumps(body),
        content_type="application/json",
    )


def _event_request(
    rf: RequestFactory,
    event: str,
    state_str: str,
    payload: dict | None = None,
    params: dict | None = None,
) -> object:
    """Build a JSON POST request that fires an event."""
    body: dict = {"event": event, "state": state_str, "payload": payload or {}}
    if params:
        body["params"] = params
    return rf.post(
        "/components/counter/",
        data=json.dumps(body),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# 1. Cache hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Second identical mount request is served from cache."""

    def test_cache_hit_returns_same_response(self, rf, counter_component):
        view = CachedView.as_view()

        req1 = _mount_request(rf, params={"initial": 7})
        resp1 = view(req1, name="counter")
        assert resp1.status_code == 200
        data1 = json.loads(resp1.content)

        req2 = _mount_request(rf, params={"initial": 7})
        resp2 = view(req2, name="counter")
        assert resp2.status_code == 200
        data2 = json.loads(resp2.content)

        # Both responses carry the same payload
        assert data1["html"] == data2["html"]
        assert data1["state"] == data2["state"]

    def test_cache_hit_skips_dispatch(self, rf, counter_component):
        """dispatch() must not be called on a cache hit."""
        view = CachedView.as_view()

        req1 = _mount_request(rf)
        view(req1, name="counter")  # warm cache

        with patch.object(Component, "dispatch", wraps=Component.dispatch) as mock_dispatch:
            req2 = _mount_request(rf)
            resp2 = view(req2, name="counter")
            assert resp2.status_code == 200
            mock_dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Cache miss — different params
# ---------------------------------------------------------------------------


class TestCacheMissDifferentParams:
    """Different params produce independent cache entries."""

    def test_different_params_each_get_own_entry(self, rf, counter_component):
        view = CachedView.as_view()

        req_a = _mount_request(rf, params={"initial": 1})
        req_b = _mount_request(rf, params={"initial": 99})

        # Warm cache for both param sets
        resp_a = view(req_a, name="counter")
        view(req_b, name="counter")  # warm cache for req_b

        data_a = json.loads(resp_a.content)
        # Third call — served from req_b's own cache entry (not req_a's)
        data_b_cached = json.loads(view(req_b, name="counter").content)

        state_a = json.loads(data_a["state"])
        state_b = json.loads(data_b_cached["state"])

        assert state_a["count"] == 1
        assert state_b["count"] == 99


# ---------------------------------------------------------------------------
# 3. Cache miss / bypass — event requests
# ---------------------------------------------------------------------------


class TestEventRequestsBypassCache:
    """Requests carrying an event field must never read from or write to cache."""

    def test_event_request_not_served_from_cache(self, rf, counter_component):
        view = CachedView.as_view()

        # Mount → warm cache
        req_mount = _mount_request(rf)
        resp_mount = view(req_mount, name="counter")
        state_str = json.loads(resp_mount.content)["state"]

        # Fire increment event — should NOT return the cached mount response
        req_event = _event_request(rf, "increment", state_str, payload={"amount": 3})
        resp_event = view(req_event, name="counter")

        assert resp_event.status_code == 200
        data_event = json.loads(resp_event.content)
        state_after = json.loads(data_event["state"])
        # Count should be 0 + 3 = 3, not 0 (which the cached mount would give)
        assert state_after["count"] == 3

    def test_event_response_not_written_to_cache(self, rf, counter_component):
        """Firing an event must not pollute the mount cache slot."""
        view = CachedView.as_view()

        # Mount once to get a state string
        req_mount = _mount_request(rf)
        resp_mount = view(req_mount, name="counter")
        state_str = json.loads(resp_mount.content)["state"]

        # Clear cache so we know there's nothing in it
        cache.clear()

        # Fire event — result must NOT be cached
        req_event = _event_request(rf, "increment", state_str, payload={"amount": 5})
        view(req_event, name="counter")

        # Now make a mount request — it must dispatch (not find an event response)
        with patch.object(Component, "dispatch", wraps=Component.dispatch) as mock_dispatch:
            req_mount2 = _mount_request(rf)
            view(req_mount2, name="counter")
            mock_dispatch.assert_called_once()

    def test_repeated_events_are_not_cached(self, rf, counter_component):
        """Firing the same event twice must both go through dispatch."""
        view = CachedView.as_view()

        req_mount = _mount_request(rf)
        resp_mount = view(req_mount, name="counter")
        state_str = json.loads(resp_mount.content)["state"]

        req_ev1 = _event_request(rf, "increment", state_str, payload={"amount": 1})
        resp_ev1 = view(req_ev1, name="counter")
        state_str2 = json.loads(resp_ev1.content)["state"]

        req_ev2 = _event_request(rf, "increment", state_str2, payload={"amount": 1})
        resp_ev2 = view(req_ev2, name="counter")

        count2 = json.loads(json.loads(resp_ev2.content)["state"])["count"]
        assert count2 == 2


# ---------------------------------------------------------------------------
# 4. Cache timeout
# ---------------------------------------------------------------------------


class TestCacheTimeout:
    """cache_timeout attribute is forwarded to the backend."""

    def test_custom_timeout_is_passed_to_cache_set(self, rf, counter_component):
        class ShortCachedView(CacheMixin, ComponentView):
            cache_timeout = 5  # 5-second TTL

        view = ShortCachedView.as_view()

        with patch("django.core.cache.cache.set", wraps=cache.set) as mock_set:
            req = _mount_request(rf)
            view(req, name="counter")
            # cache.set must have been called with timeout=5
            assert mock_set.called
            _, _, timeout = mock_set.call_args[0]
            assert timeout == 5

    def test_default_timeout_is_60(self, rf, counter_component):
        view = CachedView.as_view()

        with patch("django.core.cache.cache.set", wraps=cache.set) as mock_set:
            req = _mount_request(rf)
            view(req, name="counter")
            assert mock_set.called
            _, _, timeout = mock_set.call_args[0]
            assert timeout == 60


# ---------------------------------------------------------------------------
# 5. Custom cache key
# ---------------------------------------------------------------------------


class TestCustomCacheKey:
    """Subclasses can override get_cache_key to supply bespoke keys."""

    def test_custom_key_is_used(self, rf, counter_component):
        class CustomKeyView(CacheMixin, ComponentView):
            def get_cache_key(self, name: str, params: dict, state: dict | None) -> str:
                return f"custom:{name}:fixed"

        view = CustomKeyView.as_view()

        req1 = _mount_request(rf, params={"initial": 1})
        view(req1, name="counter")

        # The fixed key means a totally different params set hits the same cache entry
        req2 = _mount_request(rf, params={"initial": 999})
        with patch.object(Component, "dispatch", wraps=Component.dispatch) as mock_dispatch:
            view(req2, name="counter")
            mock_dispatch.assert_not_called()

    def test_custom_key_result_stored_under_custom_key(self, rf, counter_component):
        class CustomKeyView(CacheMixin, ComponentView):
            def get_cache_key(self, name: str, params: dict, state: dict | None) -> str:
                return "my-special-key"

        view = CustomKeyView.as_view()
        req = _mount_request(rf)
        resp = view(req, name="counter")

        cached = cache.get("my-special-key")
        assert cached is not None
        assert cached["html"] == json.loads(resp.content)["html"]


# ---------------------------------------------------------------------------
# 6. Non-200 responses are not cached
# ---------------------------------------------------------------------------


class TestNon200NotCached:
    """Error and 404 responses must never be stored in the cache."""

    def test_404_not_cached(self, rf, fresh_registry):
        view = CachedView.as_view()

        req = _mount_request(rf)
        resp = view(req, name="nonexistent")
        assert resp.status_code == 404

        # Nothing should have been written to cache
        # (use the default cache key to confirm)
        mixin = CacheMixin()
        key = mixin.get_cache_key("nonexistent", {}, None)
        assert cache.get(key) is None

    def test_500_not_cached(self, rf, counter_component):
        view = CachedView.as_view()

        # Force an internal error by making dispatch raise
        with patch.object(Component, "dispatch", side_effect=RuntimeError("boom")):
            req = _mount_request(rf)
            resp = view(req, name="counter")
            assert resp.status_code == 500

        mixin = CacheMixin()
        key = mixin.get_cache_key("counter", {}, None)
        assert cache.get(key) is None

    def test_200_is_cached(self, rf, counter_component):
        view = CachedView.as_view()
        req = _mount_request(rf)
        resp = view(req, name="counter")
        assert resp.status_code == 200

        mixin = CacheMixin()
        key = mixin.get_cache_key("counter", {}, None)
        assert cache.get(key) is not None


# ---------------------------------------------------------------------------
# 7. MRO — CacheMixin + ComponentView composition
# ---------------------------------------------------------------------------


class TestMROComposition:
    """CacheMixin(CacheMixin, ComponentView) MRO wires up correctly."""

    def test_mro_order(self):
        assert CachedView.__mro__.index(CacheMixin) < CachedView.__mro__.index(ComponentView)

    def test_cached_view_inherits_component_view_methods(self):
        view = CachedView()
        assert hasattr(view, "parse_request_data")
        assert hasattr(view, "parse_params")
        assert hasattr(view, "parse_state")
        assert hasattr(view, "dispatch_component")

    def test_full_request_cycle_with_cache(self, rf, counter_component):
        """End-to-end: mount → cache hit → event (bypass) → fresh result."""
        view = CachedView.as_view()

        # First mount
        req1 = _mount_request(rf, params={"initial": 10})
        resp1 = view(req1, name="counter")
        assert resp1.status_code == 200
        state_str = json.loads(resp1.content)["state"]

        # Second mount (cache hit)
        req2 = _mount_request(rf, params={"initial": 10})
        with patch.object(Component, "dispatch", wraps=Component.dispatch) as mock_dispatch:
            resp2 = view(req2, name="counter")
            assert resp2.status_code == 200
            mock_dispatch.assert_not_called()

        # Event (bypass)
        req_ev = _event_request(rf, "increment", state_str, payload={"amount": 5})
        resp_ev = view(req_ev, name="counter")
        assert resp_ev.status_code == 200
        state_after = json.loads(json.loads(resp_ev.content)["state"])
        assert state_after["count"] == 15
