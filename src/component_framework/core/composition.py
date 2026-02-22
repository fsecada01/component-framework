"""Utilities for component composition and slot management."""

from __future__ import annotations

from typing import Any

from .component import Component


def compose(
    parent_cls: type[Component],
    *,
    params: dict[str, Any] | None = None,
    **slot_components: Component,
) -> Component:
    """
    Convenience function: instantiate a parent component and fill its slots in one call.

    Keyword arguments whose values are ``Component`` instances are treated as
    slot assignments; everything else is forwarded to the parent constructor
    via *params*.

    Args:
        parent_cls: The component class to instantiate.
        params: Explicit keyword arguments forwarded to the parent constructor.
        **slot_components: Mapping of slot names to child ``Component`` instances.

    Returns:
        The fully-assembled parent component (not yet dispatched).

    Raises:
        ComponentError: If a slot name is not accepted by the parent.

    Example::

        card = compose(
            CardComponent,
            params={"title": "My Card"},
            header=HeaderComponent(text="Title"),
            body=BodyComponent(items=[1, 2, 3]),
        )
        result = card.dispatch()
    """
    parent = parent_cls(**(params or {}))
    for slot_name, child in slot_components.items():
        parent.fill_slot(slot_name, child)
    return parent


class SlotRenderer:
    """
    Mixin for renderers that support slot injection into templates.

    Subclass your concrete ``Renderer`` together with this mixin to gain a
    ``render_with_slots`` helper that merges pre-rendered slot HTML into the
    template context before rendering.

    Example::

        class MyRenderer(SlotRenderer, Renderer):
            def render(self, template_name, context):
                ...

            def render_with_slots(self, template_name, context, slots):
                ctx = self.merge_slot_context(context, slots)
                return self.render(template_name, ctx)
    """

    @staticmethod
    def merge_slot_context(
        context: dict[str, Any],
        slots: dict[str, str],
    ) -> dict[str, Any]:
        """
        Return a *new* context dict with ``slots`` merged in.

        If the context already contains a ``slots`` key it will be overwritten
        with the provided *slots* mapping.

        Args:
            context: Original template context.
            slots: Mapping of slot names to rendered HTML.

        Returns:
            A new dict combining *context* and the slot HTML.
        """
        merged = {**context, "slots": slots}
        return merged

    def render_with_slots(
        self,
        template_name: str,
        context: dict[str, Any],
        slots: dict[str, str],
    ) -> str:
        """
        Render a template with slot HTML injected into the context.

        The default implementation merges the slots into the context and
        delegates to ``self.render()``.  Override for custom behaviour.

        Args:
            template_name: Name/path of the template.
            context: Template variables.
            slots: Pre-rendered slot HTML keyed by slot name.

        Returns:
            Rendered HTML string.
        """
        merged = self.merge_slot_context(context, slots)
        # Delegate to the concrete Renderer.render() provided by the subclass.
        return self.render(template_name, merged)  # type: ignore[attr-defined]
