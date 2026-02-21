"""Django model integration mixin."""

from typing import ClassVar

from django.db import transaction
from django.db.models import Model, QuerySet


class DjangoModelMixin:
    """
    Mixin for Django model integration with components.

    Provides:
    - Instance loading with query optimization
    - Save with transaction support
    - Validation integration
    - Related object prefetching
    """

    # Django model class
    model: ClassVar[type[Model]] = None

    # Query optimization
    select_related: ClassVar[list[str]] = []
    prefetch_related: ClassVar[list[str]] = []

    # Form/validation
    form_class: ClassVar[type] = None

    def __init__(self, **params):
        super().__init__(**params)
        self.instance: Model | None = None

    # ---------- Instance Management ----------

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with optimizations.

        Override to add filters, annotations, etc.
        """
        if not self.model:
            raise ValueError("model attribute is required")

        qs = self.model.objects.all()

        if self.select_related:
            qs = qs.select_related(*self.select_related)

        if self.prefetch_related:
            qs = qs.prefetch_related(*self.prefetch_related)

        return qs

    def get_instance(self) -> Model:
        """
        Load model instance.

        Looks for 'pk' or 'id' in params.
        Returns new instance if not found.
        """
        pk = self.params.get("pk") or self.params.get("id")

        if pk:
            try:
                return self.get_queryset().get(pk=pk)
            except self.model.DoesNotExist:
                raise ValueError(f"{self.model.__name__} with pk={pk} not found")

        return self.model()

    def save_instance(self, commit: bool = True) -> Model:
        """
        Save model instance.

        Args:
            commit: Whether to save to database

        Returns:
            Saved or unsaved model instance
        """
        if not self.instance:
            raise ValueError("No instance to save")

        if commit:
            with transaction.atomic():
                self.instance.save()

        return self.instance

    # ---------- Form Integration ----------

    def get_form_class(self) -> type | None:
        """Get form class for validation."""
        return self.form_class

    def validate_and_save(self, data: dict) -> tuple[bool, dict]:
        """
        Validate data and save instance.

        Args:
            data: Form data to validate

        Returns:
            Tuple of (success, errors_dict)
        """
        form_class = self.get_form_class()
        if not form_class:
            # No form validation, update instance directly
            for key, value in data.items():
                if hasattr(self.instance, key):
                    setattr(self.instance, key, value)
            self.save_instance()
            return True, {}

        # Use Django form for validation
        form = form_class(data, instance=self.instance)
        if form.is_valid():
            self.instance = form.save()
            return True, {}
        else:
            return False, form.errors.as_dict()

    # ---------- Lifecycle Integration ----------

    def mount(self):
        """Load instance on mount."""
        super().mount()
        self.instance = self.get_instance()
        self.populate_state_from_instance()

    def hydrate(self, state: dict):
        """Load instance on hydrate."""
        super().hydrate(state)
        # Reload instance if PK in state
        if "pk" in state:
            self.params["pk"] = state["pk"]
            self.instance = self.get_instance()

    def populate_state_from_instance(self) -> None:
        """
        Populate component state from model instance.

        Override to customize which fields are included.
        """
        if not self.instance:
            return

        # Add PK if instance is saved
        if self.instance.pk:
            self.state["pk"] = self.instance.pk

        # Add fields defined in state_fields
        if hasattr(self, "state_fields"):
            for field_name in self.state_fields:
                value = getattr(self.instance, field_name, None)
                self.state[field_name] = value

    def update_instance_from_state(self) -> None:
        """
        Update model instance from component state.

        Override to customize field mapping.
        """
        if not self.instance:
            return

        if hasattr(self, "state_fields"):
            for field_name in self.state_fields:
                if field_name in self.state:
                    setattr(self.instance, field_name, self.state[field_name])


class DjangoModelComponent(DjangoModelMixin):
    """
    Complete model-bound component.

    Usage:
        @registry.register("order_form")
        class OrderForm(DjangoModelComponent):
            model = Order
            state_fields = ["status", "customer", "total"]
            select_related = ["customer"]
            template_name = "components/order_form.html"

            def on_save(self):
                self.update_instance_from_state()
                self.save_instance()
    """

    state_fields: ClassVar[list[str]] = []
