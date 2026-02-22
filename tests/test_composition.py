"""Tests for component composition and slot management."""

import pytest

from component_framework.core.component import Component, ComponentError
from component_framework.core.composition import SlotRenderer, compose
from component_framework.core.renderer import Renderer

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    """Simple renderer that echoes the template name and state."""

    def render(self, template_name: str, context: dict) -> str:
        state = context.get("state", {})
        return f"<div data-template='{template_name}'>{state}</div>"


class HeaderComponent(Component):
    """Child component used to fill a header slot."""

    template_name = "header.html"

    def mount(self):
        super().mount()
        self.state["text"] = self.params.get("text", "Default Header")


class BodyComponent(Component):
    """Child component used to fill a body slot."""

    template_name = "body.html"

    def mount(self):
        super().mount()
        self.state["items"] = self.params.get("items", [])


class FooterComponent(Component):
    """Child component used to fill a footer slot."""

    template_name = "footer.html"

    def mount(self):
        super().mount()
        self.state["year"] = self.params.get("year", 2026)


class CardComponent(Component):
    """Parent component that declares named slots."""

    template_name = "card.html"
    slots = ["header", "body", "footer"]

    def mount(self):
        super().mount()
        self.state["title"] = self.params.get("title", "")


class PermissiveComponent(Component):
    """Component with *no* declared slots -- accepts any slot name."""

    template_name = "permissive.html"

    def mount(self):
        super().mount()
        self.state["label"] = self.params.get("label", "open")


class OuterComponent(Component):
    """Outer component for nesting tests -- declares an 'inner' slot."""

    template_name = "outer.html"
    slots = ["inner"]

    def mount(self):
        super().mount()
        self.state["level"] = "outer"


class InnerComponent(Component):
    """Inner component that itself has slots -- for nested slot tests."""

    template_name = "inner.html"
    slots = ["deep"]

    def mount(self):
        super().mount()
        self.state["level"] = "inner"


class DeepComponent(Component):
    """Leaf component filling the deepest slot."""

    template_name = "deep.html"

    def mount(self):
        super().mount()
        self.state["level"] = "deep"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_renderer():
    """Ensure all components share the mock renderer during tests."""
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


# ---------------------------------------------------------------------------
# Tests: slots declaration
# ---------------------------------------------------------------------------


class TestSlotsDeclaration:
    def test_default_slots_empty(self):
        """Base Component has no declared slots."""
        assert Component.slots == []

    def test_declared_slots_on_subclass(self):
        """CardComponent declares header, body, footer."""
        assert CardComponent.slots == ["header", "body", "footer"]

    def test_permissive_component_has_empty_slots(self):
        """PermissiveComponent leaves slots as the default empty list."""
        assert PermissiveComponent.slots == []


# ---------------------------------------------------------------------------
# Tests: fill_slot
# ---------------------------------------------------------------------------


class TestFillSlot:
    def test_fill_valid_slot(self):
        card = CardComponent(title="Test")
        header = HeaderComponent(text="Hello")
        card.fill_slot("header", header)
        assert card._slot_components["header"] is header

    def test_fill_invalid_slot_raises(self):
        card = CardComponent(title="Test")
        with pytest.raises(ComponentError, match="Unknown slot 'sidebar'"):
            card.fill_slot("sidebar", HeaderComponent())

    def test_error_message_lists_available_slots(self):
        card = CardComponent()
        with pytest.raises(ComponentError, match="Available: \\['header', 'body', 'footer'\\]"):
            card.fill_slot("bad", HeaderComponent())

    def test_fill_slot_permissive_mode(self):
        """When slots is empty, any name is accepted."""
        comp = PermissiveComponent(label="anything")
        child = HeaderComponent(text="arbitrary")
        comp.fill_slot("arbitrary_name", child)
        assert comp._slot_components["arbitrary_name"] is child

    def test_fill_slot_replaces_previous(self):
        """Filling the same slot again replaces the previous child."""
        card = CardComponent()
        first = HeaderComponent(text="first")
        second = HeaderComponent(text="second")
        card.fill_slot("header", first)
        card.fill_slot("header", second)
        assert card._slot_components["header"] is second


# ---------------------------------------------------------------------------
# Tests: render_slots
# ---------------------------------------------------------------------------


class TestRenderSlots:
    def test_render_slots_renders_children(self):
        card = CardComponent(title="Test")
        card.mount()

        header = HeaderComponent(text="H")
        header.mount()
        card.fill_slot("header", header)

        rendered = card.render_slots()
        assert "header.html" in rendered["header"]
        assert "H" in rendered["header"]

    def test_render_slots_empty_when_no_children(self):
        card = CardComponent(title="Test")
        card.mount()
        assert card.render_slots() == {}

    def test_render_slots_multiple_children(self):
        card = CardComponent(title="Multi")
        card.mount()

        header = HeaderComponent(text="Head")
        header.mount()
        body = BodyComponent(items=[1, 2])
        body.mount()

        card.fill_slot("header", header)
        card.fill_slot("body", body)

        rendered = card.render_slots()
        assert "header" in rendered
        assert "body" in rendered
        assert "header.html" in rendered["header"]
        assert "body.html" in rendered["body"]


# ---------------------------------------------------------------------------
# Tests: get_context includes slots
# ---------------------------------------------------------------------------


class TestGetContextSlots:
    def test_get_context_includes_slots_key(self):
        card = CardComponent(title="ctx")
        card.mount()
        ctx = card.get_context()
        assert "slots" in ctx
        assert ctx["slots"] == {}

    def test_get_context_slots_contains_rendered_html(self):
        card = CardComponent(title="ctx")
        card.mount()

        footer = FooterComponent(year=2025)
        footer.mount()
        card.fill_slot("footer", footer)

        ctx = card.get_context()
        assert "footer" in ctx["slots"]
        assert "footer.html" in ctx["slots"]["footer"]


# ---------------------------------------------------------------------------
# Tests: dispatch includes slots
# ---------------------------------------------------------------------------


class TestDispatchSlots:
    def test_dispatch_result_has_slots_key(self):
        card = CardComponent(title="dispatch")
        result = card.dispatch()
        assert "slots" in result
        assert isinstance(result["slots"], dict)

    def test_dispatch_result_slots_contain_rendered_html(self):
        card = CardComponent(title="dispatch")

        header = HeaderComponent(text="Dispatched")
        header.mount()
        card.fill_slot("header", header)

        result = card.dispatch()
        assert "header" in result["slots"]
        assert "header.html" in result["slots"]["header"]

    def test_dispatch_with_event_still_includes_slots(self):
        """Slots should be present even when an event is handled."""

        class ClickableCard(Component):
            template_name = "clickable.html"
            slots = ["content"]

            def mount(self):
                super().mount()
                self.state["clicked"] = False

            def on_click(self):
                self.state["clicked"] = True

        child = HeaderComponent(text="content")
        child.mount()

        card = ClickableCard()
        card.fill_slot("content", child)

        result = card.dispatch(event="click", payload={})
        assert result["state"]["clicked"] is True
        assert "content" in result["slots"]


# ---------------------------------------------------------------------------
# Tests: compose() convenience function
# ---------------------------------------------------------------------------


class TestCompose:
    def test_compose_creates_parent_with_slots(self):
        header = HeaderComponent(text="composed")
        header.mount()

        card = compose(CardComponent, params={"title": "Composed"}, header=header)
        assert isinstance(card, CardComponent)
        assert card._slot_components["header"] is header

    def test_compose_dispatch(self):
        header = HeaderComponent(text="go")
        header.mount()

        card = compose(CardComponent, params={"title": "Go"}, header=header)
        result = card.dispatch()
        assert result["state"]["title"] == "Go"
        assert "header" in result["slots"]

    def test_compose_no_slots(self):
        card = compose(CardComponent, params={"title": "No Slots"})
        result = card.dispatch()
        assert result["slots"] == {}

    def test_compose_invalid_slot_raises(self):
        with pytest.raises(ComponentError, match="Unknown slot 'sidebar'"):
            compose(CardComponent, sidebar=HeaderComponent())

    def test_compose_permissive(self):
        child = HeaderComponent(text="any")
        child.mount()
        comp = compose(PermissiveComponent, params={"label": "ok"}, wildcard=child)
        assert comp._slot_components["wildcard"] is child


# ---------------------------------------------------------------------------
# Tests: nested slots
# ---------------------------------------------------------------------------


class TestNestedSlots:
    def test_child_with_own_slots(self):
        """A child component can itself have filled slots (nested composition)."""
        deep = DeepComponent()
        deep.mount()

        inner = InnerComponent()
        inner.mount()
        inner.fill_slot("deep", deep)

        outer = OuterComponent()
        outer.fill_slot("inner", inner)

        result = outer.dispatch()
        # Outer should render with inner slot
        assert "inner" in result["slots"]
        inner_html = result["slots"]["inner"]
        assert "inner.html" in inner_html

    def test_nested_compose(self):
        deep = DeepComponent()
        deep.mount()

        inner = compose(InnerComponent, deep=deep)
        inner.mount()

        outer = compose(OuterComponent, inner=inner)
        result = outer.dispatch()
        assert "inner" in result["slots"]


# ---------------------------------------------------------------------------
# Tests: empty / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_slots_dict_when_no_children(self):
        comp = Component(component_id="edge")
        comp.template_name = "edge.html"
        comp.mount()
        assert comp.render_slots() == {}

    def test_slot_components_isolated_per_instance(self):
        """Each component instance has its own _slot_components dict."""
        a = CardComponent()
        b = CardComponent()
        child = HeaderComponent()
        a.fill_slot("header", child)
        assert "header" in a._slot_components
        assert "header" not in b._slot_components


# ---------------------------------------------------------------------------
# Tests: SlotRenderer mixin
# ---------------------------------------------------------------------------


class TestSlotRenderer:
    def test_merge_slot_context(self):
        context = {"state": {"x": 1}, "component_id": "test"}
        slots = {"header": "<h1>Hi</h1>"}
        merged = SlotRenderer.merge_slot_context(context, slots)
        assert merged["slots"] == slots
        assert merged["state"] == {"x": 1}
        # Original context is not mutated.
        assert "slots" not in context

    def test_render_with_slots(self):
        class TestRenderer(SlotRenderer, Renderer):
            def render(self, template_name: str, context: dict) -> str:
                header = context.get("slots", {}).get("header", "")
                return f"<div>{header}</div>"

        renderer = TestRenderer()
        html = renderer.render_with_slots(
            "card.html",
            {"state": {}},
            {"header": "<h1>Title</h1>"},
        )
        assert "<h1>Title</h1>" in html
