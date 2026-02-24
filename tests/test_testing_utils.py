"""Tests for the component_framework.testing utilities module."""

from __future__ import annotations

import sys

import pytest

from component_framework.core.component import Component, ComponentError, EventNotFoundError
from component_framework.core.registry import ComponentRegistry
from component_framework.testing import (
    ComponentTestCase,
    IsolatedRegistry,
    MockRenderer,
    isolated_registry,  # noqa: F401  (pytest fixture — must be at module level)
    make_component,
    mock_renderer,  # noqa: F401  (pytest fixture — must be at module level)
    register_test_component,
)


def _registry_module():
    """Return the real component_framework.core.registry module via sys.modules."""
    return sys.modules["component_framework.core.registry"]


# ---------------------------------------------------------------------------
# Shared test components
# ---------------------------------------------------------------------------


class _CounterComponent(Component):
    """Simple counter component used across multiple test cases."""

    template_name = "counter.html"

    def mount(self) -> None:
        super().mount()
        self.state["count"] = self.params.get("initial", 0)

    def on_increment(self, amount: int = 1) -> None:
        self.state["count"] = self.state.get("count", 0) + amount

    def on_decrement(self, amount: int = 1) -> None:
        self.state["count"] = self.state.get("count", 0) - amount

    def on_failing(self) -> None:
        raise ValueError("intentional failure")


# ---------------------------------------------------------------------------
# MockRenderer tests
# ---------------------------------------------------------------------------


class TestMockRenderer:
    """Tests for MockRenderer."""

    def test_render_returns_string(self) -> None:
        """render() must return a string."""
        renderer = MockRenderer()
        result = renderer.render("my.html", {"state": {}})
        assert isinstance(result, str)

    def test_render_contains_template_name(self) -> None:
        """Rendered output embeds the template name."""
        renderer = MockRenderer()
        result = renderer.render("counter.html", {"state": {"count": 0}})
        assert "counter.html" in result

    def test_render_contains_state(self) -> None:
        """Rendered output embeds the JSON-serialised context."""
        renderer = MockRenderer()
        result = renderer.render("t.html", {"state": {"count": 42}})
        assert '"count": 42' in result

    def test_render_format(self) -> None:
        """Rendered output uses the expected <mock> wrapper format."""
        renderer = MockRenderer()
        result = renderer.render("widget.html", {})
        assert result.startswith('<mock template="widget.html">')
        assert result.endswith("</mock>")

    def test_render_empty_context(self) -> None:
        """render() works when context is an empty dict."""
        renderer = MockRenderer()
        result = renderer.render("empty.html", {})
        assert "empty.html" in result

    def test_render_non_json_serialisable_uses_str(self) -> None:
        """render() falls back to str() for non-JSON-serialisable values."""
        from datetime import datetime

        renderer = MockRenderer()
        dt = datetime(2026, 1, 1, 12, 0, 0)
        # Should not raise
        result = renderer.render("t.html", {"ts": dt})
        assert "2026-01-01" in result


# ---------------------------------------------------------------------------
# make_component tests
# ---------------------------------------------------------------------------


class TestMakeComponent:
    """Tests for the make_component() factory."""

    def setup_method(self) -> None:
        Component.renderer = MockRenderer()

    def teardown_method(self) -> None:
        Component.renderer = None

    def test_returns_component_subclass(self) -> None:
        """make_component() returns a Component subclass."""
        cls = make_component("widget")
        assert issubclass(cls, Component)

    def test_template_name_derived_from_name(self) -> None:
        """template_name is <name>.html."""
        cls = make_component("counter")
        assert cls.template_name == "counter.html"

    def test_template_name_anonymous_when_no_name(self) -> None:
        """template_name defaults to anonymous.html when name is None."""
        cls = make_component()
        assert cls.template_name == "anonymous.html"

    def test_state_defaults_populated_on_mount(self) -> None:
        """State defaults are set during mount()."""
        cls = make_component("counter", count=0, label="hits")
        comp = cls()
        comp.mount()
        assert comp.state["count"] == 0
        assert comp.state["label"] == "hits"

    def test_dispatch_returns_expected_keys(self) -> None:
        """dispatch() on a make_component result returns html/state/component_id."""
        cls = make_component("counter", count=5)
        comp = cls()
        result = comp.dispatch()
        assert "html" in result
        assert "state" in result
        assert "component_id" in result

    def test_dispatch_state_reflects_defaults(self) -> None:
        """dispatch() state contains the state_defaults."""
        cls = make_component("counter", count=7)
        comp = cls()
        result = comp.dispatch()
        assert result["state"]["count"] == 7

    def test_multiple_calls_independent(self) -> None:
        """Each make_component() call produces an independent class."""
        cls_a = make_component("widget", x=1)
        cls_b = make_component("widget", x=99)
        a = cls_a()
        a.mount()
        b = cls_b()
        b.mount()
        assert a.state["x"] == 1
        assert b.state["x"] == 99


# ---------------------------------------------------------------------------
# register_test_component tests
# ---------------------------------------------------------------------------


class TestRegisterTestComponent:
    """Tests for register_test_component()."""

    def test_registers_and_returns_class(self) -> None:
        """register_test_component() registers and returns the same class."""
        reg = ComponentRegistry()
        cls = make_component("widget")
        returned = register_test_component(reg, "widget", cls)
        assert returned is cls
        assert reg.get("widget") is cls

    def test_retrievable_by_name(self) -> None:
        """Registered component is accessible via registry.get()."""
        reg = ComponentRegistry()
        cls = make_component("btn")
        register_test_component(reg, "btn", cls)
        assert reg.get("btn") is cls

    def test_duplicate_name_different_class_raises(self) -> None:
        """Registering a different class under the same name raises ValueError."""
        reg = ComponentRegistry()
        cls1 = make_component("dup")
        cls2 = make_component("dup")
        register_test_component(reg, "dup", cls1)
        with pytest.raises(ValueError, match="already registered by a different class"):
            register_test_component(reg, "dup", cls2)

    def test_duplicate_name_same_class_idempotent(self) -> None:
        """Registering the same class under the same name is a no-op."""
        reg = ComponentRegistry()
        cls = make_component("dup")
        register_test_component(reg, "dup", cls)
        register_test_component(reg, "dup", cls)  # must not raise
        assert reg.get("dup") is cls


# ---------------------------------------------------------------------------
# IsolatedRegistry tests
# ---------------------------------------------------------------------------


class TestIsolatedRegistry:
    """Tests for IsolatedRegistry context manager."""

    def test_yields_fresh_registry(self) -> None:
        """Context manager yields a new, empty ComponentRegistry."""
        with IsolatedRegistry() as reg:
            assert isinstance(reg, ComponentRegistry)
            assert reg.list() == []

    def test_global_registry_replaced_inside(self) -> None:
        """Inside the context, the global registry is the fresh one."""
        with IsolatedRegistry() as reg:
            assert _registry_module().registry is reg

    def test_global_registry_restored_after(self) -> None:
        """After the context exits, the original global registry is restored."""
        original = _registry_module().registry
        with IsolatedRegistry():
            pass
        assert _registry_module().registry is original

    def test_global_registry_restored_on_exception(self) -> None:
        """The original registry is restored even if an exception is raised."""
        original = _registry_module().registry
        try:
            with IsolatedRegistry():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert _registry_module().registry is original

    def test_components_registered_inside_not_visible_outside(self) -> None:
        """Components registered inside the context are not in the original."""
        cls = make_component("temp")
        with IsolatedRegistry() as reg:
            reg.register("temp")(cls)
            assert "temp" in reg.list()

        assert "temp" not in _registry_module().registry.list()

    def test_can_register_and_retrieve_components(self) -> None:
        """Components registered inside the context are retrievable."""
        cls = make_component("inner")
        with IsolatedRegistry() as reg:
            reg.register("inner")(cls)
            assert reg.get("inner") is cls


# ---------------------------------------------------------------------------
# ComponentTestCase tests
# ---------------------------------------------------------------------------


class TestComponentTestCaseMountDispatch:
    """Behavioural tests exercising ComponentTestCase via a concrete subclass."""

    # Build a concrete subclass used by all tests in this class
    class _TC(ComponentTestCase):
        component_class = _CounterComponent

    def setup_method(self) -> None:
        self.tc = self._TC()
        self.tc.setup_method()

    def teardown_method(self) -> None:
        self.tc.teardown_method()

    # --- mount ---

    def test_mount_returns_dict_with_required_keys(self) -> None:
        """mount() returns html, state, component_id."""
        result = self.tc.mount()
        assert "html" in result
        assert "state" in result
        assert "component_id" in result

    def test_mount_initialises_state(self) -> None:
        """mount() result reflects component's initial state."""
        result = self.tc.mount(initial=5)
        assert result["state"]["count"] == 5

    def test_mount_default_initial_value(self) -> None:
        """mount() with no params gives count == 0."""
        result = self.tc.mount()
        assert result["state"]["count"] == 0

    def test_mount_html_contains_template_name(self) -> None:
        """mount() HTML output contains the template name (via MockRenderer)."""
        result = self.tc.mount()
        assert "counter.html" in result["html"]

    # --- dispatch ---

    def test_dispatch_routes_event(self) -> None:
        """dispatch() calls the correct on_<event> handler."""
        self.tc.mount()
        result = self.tc.dispatch("increment", {"amount": 3})
        assert result["state"]["count"] == 3

    def test_dispatch_chains_state_automatically(self) -> None:
        """dispatch() reuses the previous result's state when state=None."""
        self.tc.mount(initial=10)
        self.tc.dispatch("increment", {"amount": 5})
        result = self.tc.dispatch("increment", {"amount": 2})
        assert result["state"]["count"] == 17

    def test_dispatch_explicit_state_overrides_chaining(self) -> None:
        """dispatch() respects an explicitly provided state."""
        self.tc.mount(initial=10)
        result = self.tc.dispatch("increment", {"amount": 1}, state={"count": 0})
        assert result["state"]["count"] == 1

    def test_dispatch_unknown_event_raises(self) -> None:
        """dispatch() re-raises EventNotFoundError for unknown events."""
        self.tc.mount()
        with pytest.raises(EventNotFoundError):
            self.tc.dispatch("nonexistent")

    def test_dispatch_failing_handler_raises_component_error(self) -> None:
        """dispatch() re-raises ComponentError from failing handlers."""
        self.tc.mount()
        with pytest.raises(ComponentError):
            self.tc.dispatch("failing")

    # --- assert_state ---

    def test_assert_state_passes_when_correct(self) -> None:
        """assert_state() passes silently when all expectations match."""
        self.tc.mount(initial=0)
        self.tc.assert_state(count=0)  # should not raise

    def test_assert_state_fails_wrong_value(self) -> None:
        """assert_state() raises AssertionError when a value does not match."""
        self.tc.mount(initial=0)
        with pytest.raises(AssertionError):
            self.tc.assert_state(count=99)

    def test_assert_state_fails_missing_key(self) -> None:
        """assert_state() raises AssertionError when a key is absent."""
        self.tc.mount()
        with pytest.raises(AssertionError):
            self.tc.assert_state(nonexistent_key=True)

    def test_assert_state_before_any_dispatch_raises_runtime_error(self) -> None:
        """assert_state() raises RuntimeError when no dispatch has occurred."""
        fresh = self._TC()
        fresh.setup_method()
        with pytest.raises(RuntimeError, match="mount\\(\\)"):
            fresh.assert_state(count=0)
        fresh.teardown_method()

    # --- assert_renders ---

    def test_assert_renders_passes_for_present_substring(self) -> None:
        """assert_renders() passes when the substring is in the HTML."""
        self.tc.mount()
        self.tc.assert_renders("counter.html")

    def test_assert_renders_fails_for_absent_substring(self) -> None:
        """assert_renders() raises AssertionError when the substring is absent."""
        self.tc.mount()
        with pytest.raises(AssertionError):
            self.tc.assert_renders("this-string-cannot-be-in-output-xyz")

    def test_assert_renders_before_any_dispatch_raises_runtime_error(self) -> None:
        """assert_renders() raises RuntimeError when no dispatch has occurred."""
        fresh = self._TC()
        fresh.setup_method()
        with pytest.raises(RuntimeError, match="mount\\(\\)"):
            fresh.assert_renders("anything")
        fresh.teardown_method()

    # --- renderer lifecycle ---

    def test_renderer_installed_on_setup(self) -> None:
        """setup_method() installs a renderer on Component."""
        assert Component.renderer is not None
        assert isinstance(Component.renderer, MockRenderer)

    def test_renderer_restored_on_teardown(self) -> None:
        """teardown_method() restores the previous renderer."""
        saved = Component.renderer
        fresh = self._TC()
        fresh.setup_method()
        fresh.teardown_method()
        assert Component.renderer is saved


# ---------------------------------------------------------------------------
# isolated_registry fixture tests
# ---------------------------------------------------------------------------


class TestIsolatedRegistryFixture:
    """Tests using the isolated_registry pytest fixture."""

    def test_fixture_yields_registry(self, isolated_registry: ComponentRegistry) -> None:  # noqa: F811
        """isolated_registry yields a ComponentRegistry instance."""
        assert isinstance(isolated_registry, ComponentRegistry)

    def test_fixture_is_empty(self, isolated_registry: ComponentRegistry) -> None:  # noqa: F811
        """isolated_registry starts empty."""
        assert isolated_registry.list() == []

    def test_fixture_registration_works(self, isolated_registry: ComponentRegistry) -> None:  # noqa: F811
        """Components can be registered with the fixture registry."""
        cls = make_component("fx_widget")
        isolated_registry.register("fx_widget")(cls)
        assert isolated_registry.get("fx_widget") is cls

    def test_global_registry_is_fresh(self, isolated_registry: ComponentRegistry) -> None:  # noqa: F811
        """The global registry inside the test is the fixture's registry."""
        assert _registry_module().registry is isolated_registry


# ---------------------------------------------------------------------------
# mock_renderer fixture tests
# ---------------------------------------------------------------------------


class TestMockRendererFixture:
    """Tests using the mock_renderer pytest fixture."""

    def test_fixture_installs_renderer(self, mock_renderer: MockRenderer) -> None:  # noqa: F811
        """mock_renderer installs a MockRenderer on Component."""
        assert Component.renderer is mock_renderer

    def test_fixture_renderer_is_mock_renderer(self, mock_renderer: MockRenderer) -> None:  # noqa: F811
        """The installed renderer is an instance of MockRenderer."""
        assert isinstance(mock_renderer, MockRenderer)

    def test_component_can_render_with_fixture(self, mock_renderer: MockRenderer) -> None:  # noqa: F811
        """A component with template_name can render using the fixture renderer."""
        cls = make_component("fixture_test", value=42)
        comp = cls()
        comp.mount()
        html = comp.render()
        assert "fixture_test.html" in html
        assert "42" in html
