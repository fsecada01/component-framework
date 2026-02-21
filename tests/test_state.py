"""Tests for state storage implementations."""

from component_framework.core.state import InMemoryStateStore


class TestInMemoryStateStore:
    def setup_method(self):
        self.store = InMemoryStateStore()

    def test_save_and_load(self):
        self.store.save("comp-1", {"count": 10})
        result = self.store.load("comp-1")
        assert result == {"count": 10}

    def test_load_nonexistent_returns_none(self):
        assert self.store.load("nonexistent") is None

    def test_save_overwrites_existing(self):
        self.store.save("comp-1", {"count": 1})
        self.store.save("comp-1", {"count": 2})
        assert self.store.load("comp-1") == {"count": 2}

    def test_save_stores_copy(self):
        original = {"count": 5}
        self.store.save("comp-1", original)
        original["count"] = 999
        assert self.store.load("comp-1") == {"count": 5}

    def test_delete_removes_state(self):
        self.store.save("comp-1", {"count": 1})
        self.store.delete("comp-1")
        assert self.store.load("comp-1") is None

    def test_delete_nonexistent_no_error(self):
        self.store.delete("nonexistent")  # Should not raise

    def test_clear_removes_all(self):
        self.store.save("comp-1", {"a": 1})
        self.store.save("comp-2", {"b": 2})
        self.store.clear()
        assert self.store.load("comp-1") is None
        assert self.store.load("comp-2") is None

    def test_multiple_components_independent(self):
        self.store.save("comp-1", {"count": 1})
        self.store.save("comp-2", {"count": 2})
        assert self.store.load("comp-1") == {"count": 1}
        assert self.store.load("comp-2") == {"count": 2}
