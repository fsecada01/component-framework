"""Tests for Django view adapters."""

import json

import pytest
from django.test import RequestFactory

from component_framework.adapters.django_views import (
    CacheMixin,
    ComponentView,
    SingleComponentView,
    component_view,
)
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
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.django_views.registry", reg)
    return reg


@pytest.fixture
def counter_component(fresh_registry):
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


# ---------- Function-Based View ----------


class TestComponentView:
    def test_mount_json_request(self, rf, counter_component):
        request = rf.post(
            "/components/counter/",
            data=json.dumps({"params": {"initial": 5}}),
            content_type="application/json",
        )
        response = component_view(request, "counter")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "html" in data
        assert "state" in data
        assert "component_id" in data

    def test_mount_form_encoded(self, rf, counter_component):
        request = rf.post(
            "/components/counter/",
            data={"params": json.dumps({"initial": 3})},
        )
        response = component_view(request, "counter")
        assert response.status_code == 200
        data = json.loads(response.content)
        deserialized = json.loads(data["state"])
        assert deserialized["count"] == 3

    def test_event_handling(self, rf, counter_component):
        # Mount
        request = rf.post(
            "/components/counter/",
            data=json.dumps({}),
            content_type="application/json",
        )
        r1 = component_view(request, "counter")
        state_str = json.loads(r1.content)["state"]

        # Event
        request2 = rf.post(
            "/components/counter/",
            data=json.dumps(
                {
                    "event": "increment",
                    "payload": {"amount": 5},
                    "state": state_str,
                }
            ),
            content_type="application/json",
        )
        r2 = component_view(request2, "counter")
        assert r2.status_code == 200
        data = json.loads(r2.content)
        deserialized = json.loads(data["state"])
        assert deserialized["count"] == 5

    def test_component_not_found(self, rf, fresh_registry):
        request = rf.post(
            "/components/nonexistent/",
            data=json.dumps({}),
            content_type="application/json",
        )
        response = component_view(request, "nonexistent")
        assert response.status_code == 404

    def test_invalid_json(self, rf, counter_component):
        request = rf.post(
            "/components/counter/",
            data=b"not-json",
            content_type="application/json",
        )
        response = component_view(request, "counter")
        assert response.status_code == 400
        assert "Invalid JSON" in json.loads(response.content)["error"]

    def test_invalid_payload_json(self, rf, counter_component):
        request = rf.post(
            "/components/counter/",
            data=json.dumps({"payload": "not-valid-json"}),
            content_type="application/json",
        )
        response = component_view(request, "counter")
        assert response.status_code == 400

    def test_invalid_state(self, rf, counter_component):
        request = rf.post(
            "/components/counter/",
            data=json.dumps({"state": "not-valid-json"}),
            content_type="application/json",
        )
        response = component_view(request, "counter")
        assert response.status_code == 400

    def test_get_method_not_allowed(self, rf, counter_component):
        request = rf.get("/components/counter/")
        response = component_view(request, "counter")
        assert response.status_code == 405


# ---------- Class-Based View ----------


class TestComponentViewCBV:
    def test_post_request(self, rf, counter_component, fresh_registry):
        monkeypatch_reg = fresh_registry
        view = ComponentView.as_view()
        request = rf.post(
            "/cbv/components/counter/",
            data=json.dumps({"params": {"initial": 10}}),
            content_type="application/json",
        )
        # Patch registry on the view's module
        import component_framework.adapters.django_views as views_mod

        old = views_mod.registry
        views_mod.registry = monkeypatch_reg
        try:
            response = view(request, name="counter")
            assert response.status_code == 200
            data = json.loads(response.content)
            assert "html" in data
        finally:
            views_mod.registry = old

    def test_parse_request_data_json(self, rf, counter_component):
        request = rf.post(
            "/test/",
            data=json.dumps({"event": "click"}),
            content_type="application/json",
        )
        view = ComponentView()
        data = view.parse_request_data(request)
        assert data["event"] == "click"

    def test_parse_request_data_form(self, rf, counter_component):
        request = rf.post("/test/", data={"event": "click"})
        view = ComponentView()
        data = view.parse_request_data(request)
        assert data["event"] == "click"

    def test_parse_payload_dict(self):
        view = ComponentView()
        assert view.parse_payload({"key": "val"}) == {"key": "val"}

    def test_parse_payload_string(self):
        view = ComponentView()
        assert view.parse_payload('{"key": "val"}') == {"key": "val"}

    def test_parse_payload_invalid_raises(self):
        view = ComponentView()
        with pytest.raises(ValueError, match="Invalid payload JSON"):
            view.parse_payload("not json")

    def test_parse_state_none(self):
        view = ComponentView()
        assert view.parse_state(None) is None

    def test_parse_state_empty_string(self):
        view = ComponentView()
        assert view.parse_state("") is None

    def test_parse_state_valid(self):
        view = ComponentView()
        result = view.parse_state('{"count": 5}')
        assert result == {"count": 5}

    def test_parse_params_dict(self):
        view = ComponentView()
        assert view.parse_params({"a": 1}) == {"a": 1}

    def test_parse_params_string(self):
        view = ComponentView()
        assert view.parse_params('{"a": 1}') == {"a": 1}

    def test_parse_params_invalid_raises(self):
        view = ComponentView()
        with pytest.raises(ValueError, match="Invalid params JSON"):
            view.parse_params("bad")

    def test_component_not_found(self):
        view = ComponentView()
        response = view.component_not_found("missing")
        assert response.status_code == 404

    def test_handle_error(self):
        view = ComponentView()
        response = view.handle_error(Exception("boom"), "test")
        assert response.status_code == 500


# ---------- SingleComponentView ----------


class TestSingleComponentView:
    def test_requires_component_name(self, rf):
        view = SingleComponentView()
        request = rf.post("/test/", data=json.dumps({}), content_type="application/json")
        with pytest.raises(ValueError, match="component_name must be set"):
            view.post(request)


# ---------- CacheMixin ----------


class TestCacheMixin:
    def test_get_cache_key_deterministic(self):
        mixin = CacheMixin()
        key1 = mixin.get_cache_key("comp", {"a": 1}, {"b": 2})
        key2 = mixin.get_cache_key("comp", {"a": 1}, {"b": 2})
        assert key1 == key2

    def test_get_cache_key_different_params(self):
        mixin = CacheMixin()
        key1 = mixin.get_cache_key("comp", {"a": 1}, None)
        key2 = mixin.get_cache_key("comp", {"a": 2}, None)
        assert key1 != key2

    def test_cache_key_format(self):
        mixin = CacheMixin()
        key = mixin.get_cache_key("test", {}, None)
        assert key.startswith("component:")
