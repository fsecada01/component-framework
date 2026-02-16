"""Renderer interface for template engines."""

from abc import ABC, abstractmethod


class Renderer(ABC):
    """Abstract base class for template renderers."""

    @abstractmethod
    def render(self, template_name: str, context: dict) -> str:
        """
        Render template with context.

        Args:
            template_name: Name/path of template
            context: Template variables

        Returns:
            Rendered HTML string
        """
        raise NotImplementedError
