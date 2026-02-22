"""
Batteries-included testing toolkit for component-framework.

Provides helpers for testing components without HTTP, including:
- ComponentTestCase: pytest-compatible base class
- MockRenderer: simple renderer returning deterministic HTML
- make_component: factory for anonymous test components
- register_test_component: register components with a test registry
- IsolatedRegistry: context manager for per-test registry isolation
- isolated_registry / mock_renderer: pytest fixtures

Usage::

    from component_framework.testing import ComponentTestCase, make_component

    Counter = make_component("counter", count=0)

    class TestCounter(ComponentTestCase):
        component_class = Counter

        def test_initial_state(self):
            result = self.mount()
            assert result["state"]["count"] == 0
"""

from __future__ import annotations

import json
import sys
from collections.abc import Generator
from typing import Any  # noqa: UP035

import pytest

from component_framework.core.component import Component
from component_framework.core.registry import ComponentRegistry
from component_framework.core.renderer import Renderer

# ---------------------------------------------------------------------------
# MockRenderer
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    """
    Simple renderer for tests.

    Returns a predictable string that embeds the template name and a JSON
    representation of the full context so tests can inspect rendered output
    without needing a real template engine.

    Format::

        <mock template="<template_name>"><json context></mock>
    """

    def render(self, template_name: str, context: dict) -> str:
        """
        Render *template_name* with *context* to a deterministic HTML string.

        Args:
            template_name: The component's ``template_name`` attribute.
            context: The dict returned by ``Component.get_context()``.

        Returns:
            An HTML-like string of the form
            ``<mock template="name">{"state": ...}</mock>``.
        """
        payload = json.dumps(context, default=str)
        return f'<mock template="{template_name}">{payload}</mock>'


# ---------------------------------------------------------------------------
# make_component
# ---------------------------------------------------------------------------


def make_component(name: str | None = None, **state_defaults: Any) -> type[Component]:
    """
    Factory that creates a minimal anonymous :class:`~component_framework.core.component.Component`
    subclass suitable for unit tests.

    The returned class:

    * has ``template_name`` set to ``"<name>.html"`` (or ``"anonymous.html"``
      when *name* is ``None``).
    * initialises ``self.state`` with *state_defaults* in its ``mount()``
      method so tests can inspect defaults immediately after mounting.

    Args:
        name: Optional logical name used to derive ``template_name``.
        **state_defaults: Initial state key/value pairs populated in
            ``mount()``.

    Returns:
        A new :class:`~component_framework.core.component.Component` subclass.

    Example::

        Counter = make_component("counter", count=0)
        comp = Counter()
        comp.renderer = MockRenderer()
        result = comp.dispatch()
        assert result["state"]["count"] == 0
    """
    template = f"{name}.html" if name else "anonymous.html"
    defaults = dict(state_defaults)

    # Capture in a closure so the generated class does not share mutable state
    # across multiple calls to make_component.
    def _mount(self: Component) -> None:
        super(type(self), self).mount()  # type: ignore[misc]
        self.state.update(defaults)

    component_cls: type[Component] = type(
        name.capitalize() if name else "AnonymousComponent",
        (Component,),
        {
            "template_name": template,
            "mount": _mount,
        },
    )
    return component_cls


# ---------------------------------------------------------------------------
# register_test_component
# ---------------------------------------------------------------------------


def register_test_component(
    reg: ComponentRegistry,
    name: str,
    component_cls: type[Component],
) -> type[Component]:
    """
    Register *component_cls* under *name* in *reg* and return the class.

    This is a thin convenience wrapper around
    :meth:`~component_framework.core.registry.ComponentRegistry.register` for
    use in test helpers where the decorator syntax is inconvenient.

    Args:
        reg: The :class:`~component_framework.core.registry.ComponentRegistry`
            to register into.
        name: Name to register the component under.
        component_cls: The component class to register.

    Returns:
        The same *component_cls*, unchanged.
    """
    reg.register(name)(component_cls)
    return component_cls


# ---------------------------------------------------------------------------
# IsolatedRegistry
# ---------------------------------------------------------------------------


class IsolatedRegistry:
    """
    Context manager that gives each test a fresh
    :class:`~component_framework.core.registry.ComponentRegistry` and restores
    the original global registry on exit.

    The fresh registry is also accessible as an attribute so it can be used
    directly::

        with IsolatedRegistry() as reg:
            reg.register("foo")(MyComponent)
            assert reg.get("foo") is MyComponent

    It can also be used as a pytest fixture (see :func:`isolated_registry`).

    Attributes:
        registry: The temporary :class:`~component_framework.core.registry.ComponentRegistry`
            created on entry.
    """

    def __init__(self) -> None:
        self.registry: ComponentRegistry = ComponentRegistry()
        self._original_registry: ComponentRegistry | None = None

    @staticmethod
    def _registry_module():  # type: ignore[return]
        """
        Return the actual ``component_framework.core.registry`` module object.

        We must go through ``sys.modules`` rather than a bare
        ``import component_framework.core.registry`` because the parent
        package's ``__init__.py`` imports the *instance* named ``registry``
        and stores it as an attribute of the ``core`` package, which shadows
        the sub-module when accessed via dotted attribute lookup after the
        package has been imported.
        """
        return sys.modules["component_framework.core.registry"]

    def __enter__(self) -> ComponentRegistry:
        """
        Swap the global ``registry`` with a fresh instance and return it.

        Returns:
            A new, empty :class:`~component_framework.core.registry.ComponentRegistry`.
        """
        _reg_mod = self._registry_module()
        self._original_registry = _reg_mod.registry
        _reg_mod.registry = self.registry
        return self.registry

    def __exit__(self, *_: object) -> None:
        """Restore the original global registry regardless of exceptions."""
        _reg_mod = self._registry_module()
        if self._original_registry is not None:
            _reg_mod.registry = self._original_registry
            self._original_registry = None


# ---------------------------------------------------------------------------
# ComponentTestCase
# ---------------------------------------------------------------------------


class ComponentTestCase:
    """
    pytest-compatible base helper for testing components without HTTP.

    Subclasses must set :attr:`component_class`.  Optionally override
    :attr:`renderer_class` to use a different renderer.

    A :class:`MockRenderer` is installed on :attr:`component_class` during
    :meth:`setup_method` and removed (restored) in :meth:`teardown_method`.

    Attributes:
        component_class: The :class:`~component_framework.core.component.Component`
            subclass under test.  **Must** be set by the subclass.
        renderer_class: Renderer class to install before each test.
            Defaults to :class:`MockRenderer`.

    Example::

        class TestCounter(ComponentTestCase):
            component_class = CounterComponent

            def test_initial_state(self):
                result = self.mount()
                assert result["state"]["count"] == 0

            def test_increment(self):
                result = self.dispatch("increment", {"amount": 1})
                assert result["state"]["count"] == 1
    """

    component_class: type[Component]
    renderer_class: type[Renderer] = MockRenderer

    # The last dispatch result, kept so assert_state / assert_renders work
    # without callers needing to thread the result through.
    _last_result: dict[str, Any] | None = None

    def setup_method(self) -> None:
        """
        Install the renderer and reset per-test state.

        Called automatically by pytest before each test method.
        """
        self._old_renderer = Component.renderer
        Component.renderer = self.renderer_class()
        self._last_result = None

    def teardown_method(self) -> None:
        """
        Restore the original renderer after each test method.

        Called automatically by pytest after each test method.
        """
        Component.renderer = self._old_renderer

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def mount(self, **params: Any) -> dict:
        """
        Instantiate :attr:`component_class` with *params* and call
        ``dispatch()`` without an event (mount path).

        Args:
            **params: Keyword arguments forwarded to the component constructor.

        Returns:
            The dict returned by
            :meth:`~component_framework.core.component.Component.dispatch`
            (keys: ``html``, ``state``, ``component_id``).
        """
        comp = self.component_class(**params)
        self._last_result = comp.dispatch()
        return self._last_result

    def dispatch(
        self,
        event: str,
        payload: dict | None = None,
        state: dict | None = None,
        **params: Any,
    ) -> dict:
        """
        Instantiate :attr:`component_class` with *params*, optionally hydrate
        with *state*, then dispatch *event* with *payload*.

        If *state* is not supplied and a previous call to :meth:`mount` or
        :meth:`dispatch` was made in this test, its result's state is reused
        automatically so tests can chain calls naturally.

        Args:
            event: Event name (e.g. ``"increment"``).
            payload: Event payload dict.  Defaults to ``{}``.
            state: State to hydrate with before dispatching.  If ``None`` and
                a previous result exists, that result's state is used.
            **params: Keyword arguments forwarded to the component constructor.

        Returns:
            The dict returned by
            :meth:`~component_framework.core.component.Component.dispatch`.
        """
        if state is None and self._last_result is not None:
            state = self._last_result.get("state")

        comp = self.component_class(**params)
        self._last_result = comp.dispatch(event=event, payload=payload or {}, state=state)
        return self._last_result

    def assert_state(self, **expected: Any) -> None:
        """
        Assert that the last dispatch result's ``state`` contains all
        *expected* key/value pairs.

        Args:
            **expected: Expected state keys and values.

        Raises:
            AssertionError: If any key is missing or has an unexpected value.
            RuntimeError: If :meth:`mount` or :meth:`dispatch` has not been
                called yet.
        """
        if self._last_result is None:
            raise RuntimeError("Call mount() or dispatch() before assert_state()")

        state = self._last_result.get("state", {})
        for key, value in expected.items():
            assert key in state, f"Key {key!r} not found in state {state!r}"
            assert state[key] == value, f"State[{key!r}]: expected {value!r}, got {state[key]!r}"

    def assert_renders(self, substring: str) -> None:
        """
        Assert that the last dispatch result's ``html`` output contains
        *substring*.

        Args:
            substring: The string to look for in the rendered HTML.

        Raises:
            AssertionError: If *substring* is not found in the HTML.
            RuntimeError: If :meth:`mount` or :meth:`dispatch` has not been
                called yet.
        """
        if self._last_result is None:
            raise RuntimeError("Call mount() or dispatch() before assert_renders()")

        html = self._last_result.get("html", "")
        assert substring in html, f"{substring!r} not found in HTML:\n{html}"


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_registry() -> Generator[ComponentRegistry, None, None]:
    """
    Pytest fixture that yields a fresh
    :class:`~component_framework.core.registry.ComponentRegistry` for the
    duration of a test, then restores the original global registry.

    Usage::

        def test_something(isolated_registry):
            isolated_registry.register("foo")(MyComponent)
            assert "foo" in isolated_registry.list()
    """
    with IsolatedRegistry() as reg:
        yield reg


@pytest.fixture
def mock_renderer() -> Generator[MockRenderer, None, None]:
    """
    Pytest fixture that installs a :class:`MockRenderer` on
    :class:`~component_framework.core.component.Component` for the duration of
    a test, then restores the original renderer.

    Usage::

        def test_render(mock_renderer):
            comp = MyComponent()
            comp.mount()
            html = comp.render()
            assert "my_template.html" in html
    """
    old = Component.renderer
    renderer = MockRenderer()
    Component.renderer = renderer
    yield renderer
    Component.renderer = old
