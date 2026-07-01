"""Tests for locked server-trusted state fields (Epic A, task A3)."""

import logging
from typing import ClassVar

import pytest

from component_framework.core.component import Component, StateSerializer
from component_framework.core.form import FormComponent
from component_framework.core.renderer import Renderer
from component_framework.core.signing import StateSigner


@pytest.fixture(autouse=True)
def _reset_signer(monkeypatch):
    """Isolate signer configuration per test (env + class state)."""
    monkeypatch.delenv("STATE_SIGNING_KEY", raising=False)
    StateSigner.reset()
    yield
    StateSigner.reset()


class MockRenderer(Renderer):
    """Mock renderer for testing."""

    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}: {context}</div>"


class LockedComponent(Component):
    """Component with a locked server-trusted field."""

    template_name = "locked.html"
    locked_fields: ClassVar[frozenset[str]] = frozenset({"is_admin", "user_id"})

    def mount(self):
        super().mount()
        self.state["is_admin"] = False
        self.state["user_id"] = 42
        self.state["count"] = 0

    def before_render(self):
        # Server re-derives locked values on every request (documented pattern).
        self.state.setdefault("is_admin", False)
        self.state.setdefault("user_id", 42)

    def on_increment(self):
        self.state["count"] = self.state.get("count", 0) + 1


class ListDeclaredComponent(Component):
    """Component declaring locked_fields as a list (normalization check)."""

    template_name = "listy.html"
    locked_fields: ClassVar[list[str]] = ["secret_flag"]


class PlainComponent(Component):
    """Component with the default (empty) locked_fields."""

    template_name = "plain.html"


@pytest.fixture(autouse=True)
def _renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


# ---------- Declaration ----------


class TestDeclaration:
    def test_default_is_empty(self):
        assert frozenset(Component.locked_fields) == frozenset()
        assert frozenset(PlainComponent.locked_fields) == frozenset()

    def test_frozenset_declaration(self):
        assert LockedComponent._locked_field_set() == {"is_admin", "user_id"}

    def test_list_declaration_normalized(self):
        assert ListDeclaredComponent._locked_field_set() == frozenset({"secret_flag"})
        assert isinstance(ListDeclaredComponent._locked_field_set(), frozenset)


# ---------- Hydrate stripping ----------


class TestHydrateStripping:
    def test_locked_field_stripped_on_hydrate(self):
        component = LockedComponent()
        component.hydrate({"count": 5, "is_admin": True})
        assert "is_admin" not in component.state
        assert component.state["count"] == 5

    def test_multiple_locked_fields_stripped(self):
        component = LockedComponent()
        component.hydrate({"is_admin": True, "user_id": 999, "count": 1})
        assert "is_admin" not in component.state
        assert "user_id" not in component.state
        assert component.state["count"] == 1

    def test_unlocked_fields_pass_through(self):
        component = LockedComponent()
        component.hydrate({"count": 7, "other": "ok"})
        assert component.state == {"count": 7, "other": "ok"}

    def test_inbound_dict_sanitized_in_place(self):
        """Stripping mutates the inbound dict so hydrate() overrides that
        read the raw argument after super().hydrate() cannot see locked
        values either (e.g. DjangoModelMixin.hydrate reads state["pk"])."""
        component = LockedComponent()
        inbound = {"count": 1, "is_admin": True}
        component.hydrate(inbound)
        assert "is_admin" not in inbound

    def test_warning_emitted_for_stripped_fields(self, caplog):
        component = LockedComponent()
        with caplog.at_level(logging.WARNING, logger="component_framework.core.component"):
            component.hydrate({"is_admin": True, "count": 1})
        assert any(
            "is_admin" in record.getMessage() and "LockedComponent" in record.getMessage()
            for record in caplog.records
        )

    def test_no_warning_when_no_locked_fields_inbound(self, caplog):
        component = LockedComponent()
        with caplog.at_level(logging.WARNING, logger="component_framework.core.component"):
            component.hydrate({"count": 1})
        assert not caplog.records

    def test_empty_default_is_noop(self, caplog):
        component = PlainComponent()
        with caplog.at_level(logging.WARNING, logger="component_framework.core.component"):
            component.hydrate({"anything": "goes", "is_admin": True})
        assert component.state == {"anything": "goes", "is_admin": True}
        assert not caplog.records


# ---------- Dehydrate exclusion ----------


class TestDehydrateExclusion:
    def test_locked_fields_excluded_from_dehydrate(self):
        component = LockedComponent()
        component.mount()
        serialized = component.dehydrate()
        assert "is_admin" not in serialized
        assert "user_id" not in serialized
        assert serialized["count"] == 0

    def test_locked_fields_remain_in_server_state(self):
        component = LockedComponent()
        component.mount()
        component.dehydrate()
        assert component.state["is_admin"] is False
        assert component.state["user_id"] == 42

    def test_dispatch_response_state_excludes_locked_fields(self):
        result = LockedComponent().dispatch()
        assert "is_admin" not in result["state"]
        assert "user_id" not in result["state"]

    def test_empty_default_dehydrate_unchanged(self):
        component = PlainComponent()
        component.hydrate({"a": 1})
        assert component.dehydrate() == {"a": 1}


# ---------- Full round trip: signing disabled ----------


class TestUnsignedRoundTrip:
    def test_tampered_locked_field_does_not_stick(self):
        # Initial mount on the server.
        first = LockedComponent().dispatch()
        assert "is_admin" not in first["state"]

        # Client tampers with (or injects) the locked field and echoes back.
        tampered = dict(first["state"])
        tampered["is_admin"] = True

        second = LockedComponent(component_id=first["component_id"]).dispatch(
            event="increment", state=tampered
        )
        # Server-derived value wins; the injected value never sticks.
        assert "is_admin" not in second["state"]
        assert second["state"]["count"] == 1

    def test_async_dispatch_strips_locked_fields(self):
        import asyncio

        result = asyncio.run(LockedComponent().async_dispatch(state={"is_admin": True, "count": 3}))
        assert "is_admin" not in result["state"]
        assert result["state"]["count"] == 3


# ---------- Full round trip: signing enabled ----------


class TestSignedRoundTrip:
    def test_signed_round_trip_strips_locked_fields(self):
        StateSigner.configure("secret-key")
        first = LockedComponent().dispatch()
        token = StateSerializer.serialize(first["state"])
        assert token.startswith("cfs1.")

        inbound = StateSerializer.load_untrusted(token)
        assert inbound is not None
        # Even a validly signed blob cannot smuggle a locked field.
        inbound["is_admin"] = True
        second = LockedComponent().dispatch(event="increment", state=inbound)
        assert "is_admin" not in second["state"]

    def test_replay_of_stale_signed_state_does_not_roll_back_locked_field(self):
        """Replay scenario: an OLD validly-signed blob (captured before the
        field was locked / before a server-side change) must not roll a
        locked field back to its stale value."""
        StateSigner.configure("secret-key")

        # Stale-but-validly-signed blob containing a locked field, e.g.
        # captured from an older deployment where the field round-tripped.
        stale_token = StateSerializer.serialize({"count": 0, "is_admin": True, "user_id": 1})

        inbound = StateSerializer.load_untrusted(stale_token)
        result = LockedComponent().dispatch(state=inbound)

        # before_render() re-derives the server-trusted values.
        assert result["state"].get("is_admin") is None  # never serialized out
        component = LockedComponent()
        component.hydrate({"count": 0, "is_admin": True, "user_id": 1})
        component.before_render()
        assert component.state["is_admin"] is False
        assert component.state["user_id"] == 42


# ---------- FormComponent interaction ----------


class LockedForm(FormComponent):
    """Form with a locked owner field."""

    template_name = "locked_form.html"
    locked_fields: ClassVar[frozenset[str]] = frozenset({"owner_id"})

    def mount(self):
        super().mount()
        self.state["owner_id"] = 7


class TestFormComponentInteraction:
    def test_form_locked_field_stripped_on_hydrate(self):
        form = LockedForm()
        form.hydrate({"form_data": {"name": "x"}, "owner_id": 999})
        assert "owner_id" not in form.state
        assert form.state["form_data"] == {"name": "x"}

    def test_form_locked_field_excluded_from_dehydrate(self):
        form = LockedForm()
        form.mount()
        serialized = form.dehydrate()
        assert "owner_id" not in serialized
        assert "form_data" in serialized

    def test_form_submit_flow_unaffected(self):
        result = LockedForm().dispatch(
            event="submit",
            payload={"form_data": {"name": "widget"}},
            state={"form_data": {}, "submitted": False, "is_valid": False, "owner_id": 999},
        )
        assert result["state"]["submitted"] is True
        assert result["state"]["is_valid"] is True
        assert result["state"]["form_data"] == {"name": "widget"}
        assert "owner_id" not in result["state"]
