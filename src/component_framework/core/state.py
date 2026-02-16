"""State storage interfaces for component state persistence."""

from abc import ABC, abstractmethod


class StateStore(ABC):
    """Abstract base class for state persistence."""

    @abstractmethod
    def save(self, component_id: str, state: dict):
        """
        Save component state.

        Args:
            component_id: Unique component identifier
            state: Component state to persist
        """
        raise NotImplementedError

    @abstractmethod
    def load(self, component_id: str) -> dict | None:
        """
        Load component state.

        Args:
            component_id: Unique component identifier

        Returns:
            Component state or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, component_id: str):
        """Delete component state."""
        raise NotImplementedError


class InMemoryStateStore(StateStore):
    """Simple in-memory state storage for development."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, component_id: str, state: dict):
        self._store[component_id] = state.copy()

    def load(self, component_id: str) -> dict | None:
        return self._store.get(component_id)

    def delete(self, component_id: str):
        self._store.pop(component_id, None)

    def clear(self):
        """Clear all stored state (useful for testing)."""
        self._store.clear()
