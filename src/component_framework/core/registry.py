"""Component registry for registration and lookup."""

from .component import Component


class ComponentRegistry:
    """Registry for component classes."""

    def __init__(self):
        self._registry: dict[str, type[Component]] = {}

    def register(self, name: str):
        """
        Decorator to register a component class.

        Usage:
            @registry.register("counter")
            class Counter(Component):
                ...
        """

        def decorator(cls: type[Component]):
            if name in self._registry:
                raise ValueError(f"Component '{name}' already registered")
            self._registry[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[Component] | None:
        """Get component class by name."""
        return self._registry.get(name)

    def __getitem__(self, name: str) -> type[Component]:
        """Get component class by name, raises KeyError if not found."""
        return self._registry[name]

    def list(self) -> list[str]:
        """List all registered component names."""
        return list(self._registry.keys())


# Global registry instance
registry = ComponentRegistry()
