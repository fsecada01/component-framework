"""Jinjax renderer implementation."""

from jinjax import Catalog

from ..core import Renderer


class JinjaxRenderer(Renderer):
    """Renderer using Jinjax component system."""

    def __init__(self, catalog: Catalog):
        """
        Initialize Jinjax renderer.

        Args:
            catalog: Jinjax Catalog instance
        """
        self.catalog = catalog

    def render(self, template_name: str, context: dict) -> str:
        """Render Jinjax component."""
        return self.catalog.render(template_name, **context)
