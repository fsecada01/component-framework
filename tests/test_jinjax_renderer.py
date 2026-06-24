"""Tests for JinjaxRenderer, focused on sharing an existing Catalog (issue #13).

The documented guidance is that consumers should pass their *existing* JinjaX
``Catalog`` to ``JinjaxRenderer`` so component templates inherit the host app's
custom globals, filters, and extensions. These tests lock that behavior in.
"""

from __future__ import annotations

import pytest

pytest.importorskip("jinjax")

from jinjax import Catalog  # noqa: E402

from component_framework.adapters.jinjax_renderer import JinjaxRenderer  # noqa: E402


def _write_component(folder, name: str, body: str) -> None:
    (folder / f"{name}.jinja").write_text(body, encoding="utf-8")


def test_renderer_uses_shared_catalog_globals_and_filters(tmp_path):
    """A Catalog whose jinja_env carries custom globals/filters is honored by
    JinjaxRenderer — this is the 'share your existing catalog' pattern from the
    docs."""
    components = tmp_path / "components"
    components.mkdir()
    _write_component(
        components,
        "Greeting",
        "{# def name #}\n<p>{{ url_for('home') }} {{ name | shout }}</p>",
    )

    catalog = Catalog()
    catalog.jinja_env.globals["url_for"] = lambda route: f"/{route}/"
    catalog.jinja_env.filters["shout"] = lambda value: str(value).upper()
    catalog.add_folder(str(components))

    html = JinjaxRenderer(catalog).render("Greeting", {"name": "world"})

    assert "/home/" in html  # shared global reached the component
    assert "WORLD" in html  # shared filter reached the component


def test_fresh_catalog_does_not_inherit_host_globals():
    """Contrast: a fresh Catalog() (the README's old example) starts with an
    empty jinja_env, so it lacks the host app's globals — exactly the silent
    breakage issue #13 documents."""
    shared = Catalog()
    shared.jinja_env.globals["url_for"] = lambda route: f"/{route}/"

    fresh = Catalog()

    assert "url_for" in shared.jinja_env.globals
    assert "url_for" not in fresh.jinja_env.globals
