"""Jinjax renderer implementation."""

try:
    from jinjax import Catalog
except ImportError as e:
    from . import _require_extra

    raise _require_extra("jinjax", "fastapi") from e

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
