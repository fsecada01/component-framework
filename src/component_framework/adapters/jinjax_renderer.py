"""Jinjax renderer implementation."""

try:
    from jinjax import Catalog
except ImportError as e:
    from . import _require_extra

    raise _require_extra("jinjax", "fastapi") from e

from ..core import Renderer


class JinjaxRenderer(Renderer):
    """Renderer using the JinjaX component system."""

    def __init__(self, catalog: Catalog):
        """
        Initialize the JinjaX renderer.

        Pass the ``Catalog`` your application already configured rather than a
        fresh one. The renderer renders through this catalog's Jinja
        environment, so it inherits every custom filter, global (e.g.
        ``url_for``), and extension registered on it. A brand-new ``Catalog()``
        has its own empty environment, so component templates would silently
        lose that context. When sharing with ``Jinja2Templates``, build the
        catalog from the same env, e.g. ``Catalog(jinja_env=templates.env)``.

        Args:
            catalog: The JinjaX ``Catalog`` instance to render through —
                ideally the one shared with the rest of your app.
        """
        self.catalog = catalog

    def render(self, template_name: str, context: dict) -> str:
        """Render Jinjax component."""
        return self.catalog.render(template_name, **context)
