"""Tests for Django renderer implementations."""

from component_framework.adapters.django_renderer import DjangoCottonRenderer, DjangoRenderer

# ---------- DjangoRenderer ----------


class TestDjangoRenderer:
    def test_init_defaults(self):
        renderer = DjangoRenderer()
        assert renderer.use_cotton is False

    def test_init_with_cotton(self):
        renderer = DjangoRenderer(use_cotton=True)
        assert renderer.use_cotton is True


# ---------- DjangoCottonRenderer ----------


class TestDjangoCottonRenderer:
    def test_build_attrs_string_value(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"name": "test"})
        assert 'name="test"' in result

    def test_build_attrs_int_value(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"count": 42})
        assert 'count="42"' in result

    def test_build_attrs_bool_value(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"active": True})
        assert 'active="True"' in result

    def test_build_attrs_complex_value_uses_context_ref(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"items": [1, 2, 3]})
        assert ':items="items"' in result

    def test_build_attrs_empty_context(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({})
        assert result == ""

    def test_build_attrs_escapes_html(self):
        """Verify XSS prevention: HTML special chars are escaped."""
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"name": '<script>alert("xss")</script>'})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_build_attrs_escapes_quotes(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"name": 'value"with"quotes'})
        assert 'value"with"quotes' not in result
        assert "&quot;" in result

    def test_build_attrs_multiple_values(self):
        renderer = DjangoCottonRenderer()
        result = renderer._build_attrs({"a": "1", "b": "2"})
        assert 'a="1"' in result
        assert 'b="2"' in result
