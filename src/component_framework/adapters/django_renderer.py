"""Django template renderer implementation."""

from django.template import Context, Template
from django.template.loader import render_to_string

from ..core import Renderer


class DjangoRenderer(Renderer):
    """Renderer using Django template system."""

    def __init__(self, use_cotton: bool = False):
        """
        Initialize Django renderer.

        Args:
            use_cotton: Whether to use django-cotton for component rendering
        """
        self.use_cotton = use_cotton

    def render(self, template_name: str, context: dict) -> str:
        """
        Render Django template.

        Args:
            template_name: Template path (e.g., 'components/counter.html')
            context: Template context variables

        Returns:
            Rendered HTML string
        """
        return render_to_string(template_name, context)


class DjangoCottonRenderer(Renderer):
    """Renderer using django-cotton components."""

    def render(self, template_name: str, context: dict) -> str:
        """
        Render django-cotton component.

        Args:
            template_name: Cotton component name (e.g., 'counter')
            context: Component props/context

        Returns:
            Rendered HTML string
        """
        # Cotton components are referenced with 'c-' prefix
        # e.g., 'counter' becomes <c-counter ... />
        # We use Django's template system to render the cotton component
        cotton_template = f"{{% load cotton %}}<c-{template_name} {self._build_attrs(context)} />"
        template = Template(cotton_template)
        return template.render(Context(context))

    def _build_attrs(self, context: dict) -> str:
        """Build cotton component attributes from context."""
        attrs = []
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                attrs.append(f'{key}="{value}"')
            else:
                # For complex objects, pass through context
                attrs.append(f':{key}="{key}"')
        return " ".join(attrs)
