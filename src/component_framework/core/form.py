"""Form component with validation support."""

from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from .component import Component


class FormComponent(Component):
    """
    Form component with Pydantic validation.

    Usage:
        class UserFormSchema(BaseModel):
            name: str
            email: EmailStr
            age: int = Field(ge=0, le=120)

        @registry.register("user_form")
        class UserForm(FormComponent):
            schema = UserFormSchema
            template_name = "user_form"

            def on_submit(self):
                # Validation happens automatically
                # Access validated data in self.validated_data
                pass
    """

    # Pydantic model for validation
    schema: ClassVar[type[BaseModel] | None] = None

    def __init__(self, **params):
        super().__init__(**params)
        self.validated_data: dict[str, Any] | None = None
        self.field_errors: dict[str, list[str]] = {}

    # ---------- Validation ----------

    def validate(self, data: dict) -> bool:
        """
        Validate data against schema.

        Args:
            data: Form data to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.schema:
            # No schema, skip validation
            self.validated_data = data
            return True

        try:
            validated = self.schema(**data)
            self.validated_data = validated.model_dump()
            self.errors = {}
            self.field_errors = {}
            return True
        except ValidationError as e:
            self.validated_data = None
            self.errors["form"] = "Validation failed"

            # Convert Pydantic errors to field errors
            self.field_errors = {}
            for error in e.errors():
                field = str(error["loc"][0]) if error["loc"] else "form"
                message = error["msg"]

                if field not in self.field_errors:
                    self.field_errors[field] = []
                self.field_errors[field].append(message)

            return False

    def get_field_errors(self, field_name: str) -> list[str]:
        """Get validation errors for a specific field."""
        return self.field_errors.get(field_name, [])

    def has_field_error(self, field_name: str) -> bool:
        """Check if field has validation errors."""
        return field_name in self.field_errors

    # ---------- Form State ----------

    def mount(self):
        """Initialize form state."""
        super().mount()
        self.state["form_data"] = {}
        self.state["submitted"] = False
        self.state["is_valid"] = False

    def get_field_value(self, field_name: str, default: Any = "") -> Any:
        """Get current value of form field."""
        return self.state.get("form_data", {}).get(field_name, default)

    def set_field_value(self, field_name: str, value: Any):
        """Set value of form field."""
        if "form_data" not in self.state:
            self.state["form_data"] = {}
        self.state["form_data"][field_name] = value

    # ---------- Event Handlers ----------

    def on_submit(self):
        """
        Handle form submission.

        Override in subclasses to add custom logic.
        Validation happens automatically before this is called.
        """
        pass

    def on_field_change(self, field: str, value: Any):
        """Handle field value change."""
        self.set_field_value(field, value)

        # Clear field error on change
        if field in self.field_errors:
            del self.field_errors[field]

    def handle_event(self, event: str, payload: dict):
        """Handle events with automatic validation for submit."""
        if event == "submit":
            # Extract form data
            form_data = payload.get("form_data", self.state.get("form_data", {}))
            self.state["form_data"] = form_data
            self.state["submitted"] = True

            # Validate
            is_valid = self.validate(form_data)
            self.state["is_valid"] = is_valid

            if is_valid:
                # Call submit handler
                self.on_submit()
        else:
            # Regular event handling
            super().handle_event(event, payload)

    # ---------- Context ----------

    def get_context(self) -> dict:
        """Add form-specific context."""
        context = super().get_context()
        context.update(
            {
                "form_data": self.state.get("form_data", {}),
                "field_errors": self.field_errors,
                "is_valid": self.state.get("is_valid", False),
                "submitted": self.state.get("submitted", False),
            }
        )
        return context


class ModelFormComponent(FormComponent):
    """
    Form component with model instance support.

    Combines FormComponent validation with model persistence.
    Works with DjangoModelMixin or similar patterns.
    """

    def mount(self):
        """Initialize form with instance data."""
        super().mount()

        # Populate form from instance if available
        if hasattr(self, "instance") and self.instance:
            self.populate_form_from_instance()

    def populate_form_from_instance(self):
        """Populate form data from model instance."""
        if not hasattr(self, "state_fields"):
            return

        form_data = {}
        for field_name in self.state_fields:
            value = getattr(self.instance, field_name, None)
            form_data[field_name] = value

        self.state["form_data"] = form_data

    def on_submit(self):
        """Save validated data to model instance."""
        if not self.validated_data:
            return

        # Update instance from validated data
        for field_name, value in self.validated_data.items():
            if hasattr(self.instance, field_name):
                setattr(self.instance, field_name, value)

        # Save instance (if method exists)
        if hasattr(self, "save_instance"):
            self.save_instance()
