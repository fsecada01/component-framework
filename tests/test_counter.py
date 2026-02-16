"""Tests for Counter component."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from component_framework.components.counter import Counter
from component_framework.core import Component, Renderer, StateSerializer


class MockRenderer(Renderer):
    """Mock renderer for testing."""

    def render(self, template_name: str, context: dict) -> str:
        return f"<div>Mock render: {template_name}</div>"


# Configure mock renderer globally for tests
Component.renderer = MockRenderer()


def test_counter_mount():
    """Test counter initialization."""
    counter = Counter(initial=5)
    result = counter.dispatch()

    assert result["state"]["count"] == 5
    assert "component_id" in result


def test_counter_increment():
    """Test counter increment."""
    counter = Counter()
    result = counter.dispatch()

    # Initial state
    assert result["state"]["count"] == 0

    # Increment
    state = result["state"]
    result = counter.dispatch(event="increment", payload={"amount": 1}, state=state)
    assert result["state"]["count"] == 1

    # Increment by 5
    state = result["state"]
    result = counter.dispatch(event="increment", payload={"amount": 5}, state=state)
    assert result["state"]["count"] == 6


def test_counter_decrement():
    """Test counter decrement."""
    counter = Counter(initial=10)
    result = counter.dispatch()

    state = result["state"]
    result = counter.dispatch(event="decrement", payload={"amount": 3}, state=state)
    assert result["state"]["count"] == 7


def test_counter_reset():
    """Test counter reset."""
    counter = Counter(initial=100)
    result = counter.dispatch()

    state = result["state"]
    result = counter.dispatch(event="reset", payload={}, state=state)
    assert result["state"]["count"] == 0


def test_state_serialization():
    """Test state serialization round-trip."""
    counter = Counter(initial=42)
    result = counter.dispatch()

    # Serialize
    state_str = StateSerializer.serialize(result["state"])
    assert isinstance(state_str, str)

    # Deserialize
    state = StateSerializer.deserialize(state_str)
    assert state["count"] == 42

    # Use deserialized state
    counter2 = Counter()
    result2 = counter2.dispatch(state=state)
    assert result2["state"]["count"] == 42


if __name__ == "__main__":
    # Run tests manually
    test_counter_mount()
    test_counter_increment()
    test_counter_decrement()
    test_counter_reset()
    test_state_serialization()
    print("All tests passed!")
