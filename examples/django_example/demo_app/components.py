"""Component definitions for Django demo."""

from pydantic import BaseModel, EmailStr, Field

from component_framework.adapters.django_model import DjangoModelComponent
from component_framework.adapters.django_renderer import DjangoRenderer
from component_framework.core import Component, FormComponent, registry

from .models import Customer, Order

# Configure Django renderer for all components
renderer = DjangoRenderer()
Component.renderer = renderer


# ==================== Contact Form ====================


class ContactFormSchema(BaseModel):
    """Validation schema for contact form."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    message: str = Field(min_length=10, max_length=1000)


@registry.register("contact_form")
class ContactForm(FormComponent):
    """Contact form with Pydantic validation."""

    schema = ContactFormSchema
    template_name = "components/contact_form.html"

    def on_submit(self):
        """Handle form submission."""
        # In real app, send email, save to database, etc.
        self.state["success_message"] = "Thank you! We'll be in touch soon."


# ==================== Order Editor ====================


@registry.register("order_editor")
class OrderEditor(DjangoModelComponent):
    """Order editor with Django model binding."""

    model = Order
    select_related = ["customer"]
    state_fields = ["status", "notes", "total"]
    template_name = "components/order_editor.html"

    def mount(self):
        """Initialize order editor."""
        super().mount()
        # Add customer info to state
        if self.instance and self.instance.pk:
            self.state["customer_name"] = self.instance.customer.name
            self.state["order_id"] = self.instance.pk

    def on_update_status(self, status: str):
        """Update order status."""
        if status in dict(Order.STATUS_CHOICES):
            self.state["status"] = status
            self.instance.status = status
            self.save_instance()
            self.state["success"] = True

    def on_add_note(self, note: str):
        """Add note to order."""
        if note:
            current_notes = self.state.get("notes", "")
            self.state["notes"] = f"{current_notes}\n{note}".strip()
            self.instance.notes = self.state["notes"]
            self.save_instance()


# ==================== Customer List ====================


@registry.register("customer_list")
class CustomerList(Component):
    """Live customer list."""

    template_name = "components/customer_list.html"

    def mount(self):
        """Load customers."""
        super().mount()
        self.load_customers()

    def load_customers(self):
        """Load customer data into state."""
        customers = Customer.objects.all()[:10]
        self.state["customers"] = [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "order_count": c.orders.count(),
            }
            for c in customers
        ]

    def on_refresh(self):
        """Refresh customer list."""
        self.load_customers()


# ==================== Real-Time Counter ====================


@registry.register("live_counter")
class LiveCounter(Component):
    """Counter with WebSocket updates."""

    template_name = "components/live_counter.html"

    def mount(self):
        """Initialize counter."""
        super().mount()
        self.state["count"] = self.params.get("initial", 0)
        self.state["broadcast"] = self.params.get("broadcast", False)

    def on_increment(self, amount: int = 1):
        """Increment counter."""
        self.state["count"] = self.state.get("count", 0) + amount

    def on_decrement(self, amount: int = 1):
        """Decrement counter."""
        self.state["count"] = self.state.get("count", 0) - amount

    def on_reset(self):
        """Reset counter."""
        self.state["count"] = 0
