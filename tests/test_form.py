"""Tests for FormComponent and ModelFormComponent."""

from pydantic import BaseModel, Field

from component_framework.core.component import Component
from component_framework.core.form import FormComponent
from component_framework.core.renderer import Renderer


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}</div>"


class UserSchema(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)


class UserForm(FormComponent):
    schema = UserSchema
    template_name = "user_form.html"

    def on_submit(self):
        self.state["saved"] = True


class NoSchemaForm(FormComponent):
    template_name = "no_schema_form.html"


# ---------- Validation ----------


class TestFormValidation:
    def test_validate_valid_data(self):
        form = UserForm()
        form.mount()
        assert form.validate({"name": "Alice", "age": 30}) is True
        assert form.validated_data == {"name": "Alice", "age": 30}
        assert form.errors == {}
        assert form.field_errors == {}

    def test_validate_invalid_data(self):
        form = UserForm()
        form.mount()
        assert form.validate({"name": "Alice", "age": -1}) is False
        assert form.validated_data is None
        assert "form" in form.errors
        assert "age" in form.field_errors

    def test_validate_missing_fields(self):
        form = UserForm()
        form.mount()
        assert form.validate({}) is False
        assert "name" in form.field_errors

    def test_validate_no_schema_passes_through(self):
        form = NoSchemaForm()
        form.mount()
        data = {"anything": "goes"}
        assert form.validate(data) is True
        assert form.validated_data == data

    def test_get_field_errors(self):
        form = UserForm()
        form.mount()
        form.validate({"name": "Alice", "age": -1})
        errors = form.get_field_errors("age")
        assert len(errors) > 0
        assert form.get_field_errors("name") == []

    def test_has_field_error(self):
        form = UserForm()
        form.mount()
        form.validate({"name": "Alice", "age": -1})
        assert form.has_field_error("age") is True
        assert form.has_field_error("name") is False


# ---------- Form State ----------


class TestFormState:
    def test_mount_initializes_form_state(self):
        form = UserForm()
        form.mount()
        assert form.state["form_data"] == {}
        assert form.state["submitted"] is False
        assert form.state["is_valid"] is False

    def test_set_and_get_field_value(self):
        form = UserForm()
        form.mount()
        form.set_field_value("name", "Bob")
        assert form.get_field_value("name") == "Bob"

    def test_get_field_value_default(self):
        form = UserForm()
        form.mount()
        assert form.get_field_value("missing", "default") == "default"

    def test_set_field_value_creates_form_data(self):
        form = UserForm()
        # Don't call mount - no form_data key
        form.set_field_value("name", "Test")
        assert form.state["form_data"]["name"] == "Test"


# ---------- Event Handling ----------


class TestFormEventHandling:
    def setup_method(self):
        Component.renderer = MockRenderer()

    def test_submit_valid_data(self):
        form = UserForm()
        form.mount()
        form.handle_event("submit", {"form_data": {"name": "Alice", "age": 30}})
        assert form.state["submitted"] is True
        assert form.state["is_valid"] is True
        assert form.state["saved"] is True  # on_submit was called

    def test_submit_invalid_data(self):
        form = UserForm()
        form.mount()
        form.handle_event("submit", {"form_data": {"name": "Alice", "age": -1}})
        assert form.state["submitted"] is True
        assert form.state["is_valid"] is False
        assert form.state.get("saved") is None  # on_submit NOT called

    def test_submit_uses_existing_form_data_if_no_payload(self):
        form = UserForm()
        form.mount()
        form.set_field_value("name", "Bob")
        form.set_field_value("age", 25)
        form.handle_event("submit", {})
        assert form.state["form_data"]["name"] == "Bob"

    def test_field_change_event(self):
        form = UserForm()
        form.mount()
        form.handle_event("field_change", {"field": "name", "value": "Charlie"})
        assert form.get_field_value("name") == "Charlie"

    def test_field_change_clears_field_error(self):
        form = UserForm()
        form.mount()
        form.field_errors["name"] = ["Required"]
        form.handle_event("field_change", {"field": "name", "value": "Alice"})
        assert "name" not in form.field_errors


# ---------- Context ----------


class TestFormContext:
    def test_form_context_includes_form_fields(self):
        Component.renderer = MockRenderer()
        form = UserForm()
        form.mount()
        form.set_field_value("name", "Test")
        ctx = form.get_context()
        assert "form_data" in ctx
        assert "field_errors" in ctx
        assert "is_valid" in ctx
        assert "submitted" in ctx
        assert ctx["form_data"]["name"] == "Test"


# ---------- Dispatch Integration ----------


class TestFormDispatch:
    def setup_method(self):
        Component.renderer = MockRenderer()

    def test_full_dispatch_mount_and_submit(self):
        form = UserForm()
        # Initial mount
        result = form.dispatch()
        assert result["state"]["submitted"] is False

        # Submit with valid data
        form2 = UserForm()
        result2 = form2.dispatch(
            event="submit",
            payload={"form_data": {"name": "Alice", "age": 30}},
            state=result["state"],
        )
        assert result2["state"]["is_valid"] is True
        assert result2["state"]["saved"] is True
