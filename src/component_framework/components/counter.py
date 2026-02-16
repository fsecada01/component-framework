"""Simple counter component example."""

from ..core import Component, registry


@registry.register("counter")
class Counter(Component):
    """A simple counter component."""

    template_name = "Counter"

    def mount(self):
        """Initialize counter to 0."""
        super().mount()
        self.state["count"] = self.params.get("initial", 0)

    def on_increment(self, amount: int = 1):
        """Increment counter by amount."""
        self.state["count"] = self.state.get("count", 0) + amount

    def on_decrement(self, amount: int = 1):
        """Decrement counter by amount."""
        self.state["count"] = self.state.get("count", 0) - amount

    def on_reset(self):
        """Reset counter to 0."""
        self.state["count"] = 0
