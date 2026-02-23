"""Tests for Django model integration mixin."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("django", reason="Install: pip install component-framework[django]")

from component_framework.adapters.django_model import DjangoModelMixin
from component_framework.core import Component, Renderer


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


class MockModel:
    """Mock Django model for testing without database."""

    DoesNotExist = type("DoesNotExist", (Exception,), {})
    __name__ = "MockModel"

    def __init__(self, pk=None, **kwargs):
        self.pk = pk
        for k, v in kwargs.items():
            setattr(self, k, v)

    def save(self):
        if not self.pk:
            self.pk = 1

    class objects:  # noqa: N801
        @staticmethod
        def all():
            return MockQuerySet()


class MockQuerySet:
    """Mock Django QuerySet."""

    _data = {}

    def select_related(self, *fields):
        return self

    def prefetch_related(self, *fields):
        return self

    def get(self, pk=None):
        if pk in MockQuerySet._data:
            return MockQuerySet._data[pk]
        raise MockModel.DoesNotExist(f"pk={pk}")


class SampleModelComponent(DjangoModelMixin, Component):
    """Test component with model mixin."""

    model = MockModel
    template_name = "test.html"
    state_fields = ["name", "status"]
    select_related = ["related"]
    prefetch_related = ["items"]


# ---------- Instance Management ----------


class TestGetQueryset:
    def test_requires_model(self):
        class NoModelComp(DjangoModelMixin, Component):
            model = None
            template_name = "test.html"

        comp = NoModelComp()
        with pytest.raises(ValueError, match="model attribute is required"):
            comp.get_queryset()

    def test_returns_queryset(self):
        comp = SampleModelComponent()
        qs = comp.get_queryset()
        assert isinstance(qs, MockQuerySet)


class TestGetInstance:
    def test_new_instance_when_no_pk(self):
        comp = SampleModelComponent()
        instance = comp.get_instance()
        assert isinstance(instance, MockModel)
        assert instance.pk is None

    def test_load_by_pk(self):
        saved = MockModel(pk=42, name="Test")
        MockQuerySet._data[42] = saved
        try:
            comp = SampleModelComponent(pk=42)
            instance = comp.get_instance()
            assert instance.pk == 42
            assert instance.name == "Test"
        finally:
            MockQuerySet._data.clear()

    def test_load_by_id(self):
        saved = MockModel(pk=7, name="IDTest")
        MockQuerySet._data[7] = saved
        try:
            comp = SampleModelComponent(id=7)
            instance = comp.get_instance()
            assert instance.pk == 7
        finally:
            MockQuerySet._data.clear()

    def test_not_found_raises(self):
        comp = SampleModelComponent(pk=999)
        with pytest.raises(ValueError, match="pk=999 not found"):
            comp.get_instance()


class TestSaveInstance:
    def test_save_no_instance_raises(self):
        comp = SampleModelComponent()
        comp.instance = None
        with pytest.raises(ValueError, match="No instance to save"):
            comp.save_instance()

    @patch("component_framework.adapters.django_model.transaction")
    def test_save_with_commit(self, mock_txn):
        mock_txn.atomic.return_value.__enter__ = MagicMock()
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        comp = SampleModelComponent()
        instance = MockModel(name="Test")
        comp.instance = instance
        result = comp.save_instance(commit=True)
        assert result.pk is not None

    def test_save_without_commit(self):
        comp = SampleModelComponent()
        instance = MockModel(name="Test")
        comp.instance = instance
        result = comp.save_instance(commit=False)
        assert result.pk is None


# ---------- Form Integration ----------


class TestFormIntegration:
    def test_get_form_class_default_none(self):
        comp = SampleModelComponent()
        assert comp.get_form_class() is None

    @patch("component_framework.adapters.django_model.transaction")
    def test_validate_and_save_no_form(self, mock_txn):
        mock_txn.atomic.return_value.__enter__ = MagicMock()
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        comp = SampleModelComponent()
        comp.instance = MockModel(pk=1, name="Old", status="draft")
        success, errors = comp.validate_and_save({"name": "New", "status": "published"})
        assert success is True
        assert errors == {}
        assert comp.instance.name == "New"
        assert comp.instance.status == "published"


# ---------- State Population ----------


class TestPopulateState:
    def test_populate_from_saved_instance(self):
        comp = SampleModelComponent()
        comp.state = {}
        comp.instance = MockModel(pk=5, name="Alice", status="active")
        comp.populate_state_from_instance()
        assert comp.state["pk"] == 5
        assert comp.state["name"] == "Alice"
        assert comp.state["status"] == "active"

    def test_populate_from_unsaved_instance(self):
        comp = SampleModelComponent()
        comp.state = {}
        comp.instance = MockModel(name="Bob", status="pending")
        comp.populate_state_from_instance()
        assert "pk" not in comp.state
        assert comp.state["name"] == "Bob"

    def test_populate_no_instance(self):
        comp = SampleModelComponent()
        comp.state = {}
        comp.instance = None
        comp.populate_state_from_instance()
        assert comp.state == {}


class TestUpdateInstanceFromState:
    def test_update_fields(self):
        comp = SampleModelComponent()
        comp.instance = MockModel(pk=1, name="Old", status="draft")
        comp.state = {"name": "New", "status": "published"}
        comp.update_instance_from_state()
        assert comp.instance.name == "New"
        assert comp.instance.status == "published"

    def test_update_no_instance(self):
        comp = SampleModelComponent()
        comp.instance = None
        comp.state = {"name": "Test"}
        comp.update_instance_from_state()  # Should not raise

    def test_update_ignores_missing_state_fields(self):
        comp = SampleModelComponent()
        comp.instance = MockModel(pk=1, name="Old", status="draft")
        comp.state = {"name": "New"}  # No status key
        comp.update_instance_from_state()
        assert comp.instance.name == "New"
        assert comp.instance.status == "draft"  # Unchanged


# ---------- Lifecycle ----------


class TestLifecycle:
    def test_hydrate_reloads_instance_from_pk(self):
        saved = MockModel(pk=10, name="Hydrated")
        MockQuerySet._data[10] = saved
        try:
            comp = SampleModelComponent()
            comp.instance = None
            comp.hydrate({"pk": 10})
            assert comp.instance.pk == 10
            assert comp.instance.name == "Hydrated"
        finally:
            MockQuerySet._data.clear()

    def test_hydrate_without_pk(self):
        comp = SampleModelComponent()
        comp.hydrate({"count": 5})
        assert comp.state["count"] == 5
