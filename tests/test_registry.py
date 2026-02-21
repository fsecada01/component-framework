"""Tests for the ComponentRegistry."""

import pytest

from component_framework.core.component import Component
from component_framework.core.registry import ComponentRegistry


class TestComponentRegistry:
    def setup_method(self):
        self.reg = ComponentRegistry()

    def test_register_and_get(self):
        @self.reg.register("test_comp")
        class TestComp(Component):
            pass

        assert self.reg.get("test_comp") is TestComp

    def test_register_duplicate_raises(self):
        @self.reg.register("dup")
        class First(Component):
            pass

        with pytest.raises(ValueError, match="Component 'dup' already registered"):

            @self.reg.register("dup")
            class Second(Component):
                pass

    def test_get_missing_returns_none(self):
        assert self.reg.get("nonexistent") is None

    def test_getitem_works(self):
        @self.reg.register("item")
        class ItemComp(Component):
            pass

        assert self.reg["item"] is ItemComp

    def test_getitem_missing_raises_keyerror(self):
        with pytest.raises(KeyError):
            self.reg["missing"]

    def test_list_returns_registered_names(self):
        @self.reg.register("alpha")
        class Alpha(Component):
            pass

        @self.reg.register("beta")
        class Beta(Component):
            pass

        names = self.reg.list()
        assert "alpha" in names
        assert "beta" in names
        assert len(names) == 2

    def test_list_empty_registry(self):
        assert self.reg.list() == []

    def test_decorator_returns_original_class(self):
        @self.reg.register("preserved")
        class MyComp(Component):
            custom_attr = True

        assert MyComp.custom_attr is True
        assert MyComp.__name__ == "MyComp"
