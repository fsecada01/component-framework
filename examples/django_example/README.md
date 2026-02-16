# Django Component Framework Example

Complete Django application demonstrating the component framework with forms, models, and WebSockets.

## Features Demonstrated

### 1. Form Components with Validation
- **ContactForm**: Pydantic validation
- Live error feedback
- Server-side validation
- Field-level error messages

### 2. Model-Bound Components
- **OrderEditor**: Django ORM integration
- Automatic state synchronization
- Query optimization (select_related)
- Transaction support

### 3. WebSocket Real-Time Updates
- **LiveCounter**: Real-time updates
- Django Channels integration
- Broadcasting to multiple clients
- Automatic reconnection

### 4. Django-Cotton Integration
- Template tags for components
- Cotton component rendering
- Seamless integration

## Setup

### 1. Install dependencies

```bash
# Install with Django support
uv pip install -e ".[django,websockets,dev]"
```

### 2. Run migrations

```bash
cd examples/django_example
python manage.py migrate
```

### 3. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 4. Run development server

```bash
# HTTP server
python manage.py runserver

# Or with Channels/WebSocket support
daphne -b 127.0.0.1 -p 8000 django_example.asgi:application
```

### 5. Open in browser

```
http://localhost:8000
```

## Project Structure

```
django_example/
├── settings.py          # Django settings
├── urls.py              # URL configuration
├── asgi.py              # ASGI config (WebSockets)
├── wsgi.py              # WSGI config
├── manage.py            # Django management script
│
├── demo_app/
│   ├── models.py        # Customer, Order models
│   ├── views.py         # Django views
│   ├── components.py    # Component definitions
│   ├── admin.py         # Django admin
│   └── apps.py          # App config
│
└── templates/
    ├── base.html        # Base template with HTMX
    ├── index.html       # Homepage
    ├── form_demo.html   # Form demo page
    ├── model_demo.html  # Model demo page
    ├── websocket_demo.html  # WebSocket demo
    │
    └── components/
        ├── contact_form.html    # Contact form template
        ├── order_editor.html    # Order editor template
        └── live_counter.html    # Live counter template
```

## Components

### ContactForm

```python
@registry.register("contact_form")
class ContactForm(FormComponent):
    schema = ContactFormSchema  # Pydantic validation
    template_name = "components/contact_form.html"
```

Usage:
```django
{% load components %}
{% live_component "contact_form" %}
```

### OrderEditor

```python
@registry.register("order_editor")
class OrderEditor(DjangoModelComponent):
    model = Order
    select_related = ["customer"]
    state_fields = ["status", "notes", "total"]
```

Usage:
```django
{% live_component "order_editor" pk=order.pk %}
```

### LiveCounter

```python
@registry.register("live_counter")
class LiveCounter(Component):
    template_name = "components/live_counter.html"
```

Usage with WebSocket:
```django
{% live_component "live_counter" initial=0 broadcast=True %}
```

## Running with WebSockets

For WebSocket support, use Daphne:

```bash
# Install daphne
uv pip install daphne

# Run with WebSocket support
daphne -b 127.0.0.1 -p 8000 django_example.asgi:application
```

Or use the development server (limited WebSocket support):

```bash
python manage.py runserver
```

## Admin Interface

Access Django admin at `http://localhost:8000/admin/`

Create customers and orders through the admin or they will be created automatically.

## Key Concepts

### 1. Component Registration

```python
from component_framework.core import Component, registry

@registry.register("my_component")
class MyComponent(Component):
    template_name = "components/my_component.html"
```

### 2. Model Binding

```python
from component_framework.adapters.django_model import DjangoModelComponent

class MyModelComponent(DjangoModelComponent):
    model = MyModel
    state_fields = ["field1", "field2"]
    select_related = ["relation"]
```

### 3. Form Validation

```python
from pydantic import BaseModel
from component_framework.core import FormComponent

class MySchema(BaseModel):
    field: str

class MyForm(FormComponent):
    schema = MySchema
```

### 4. WebSocket Updates

```python
from component_framework.adapters.django_websocket import broadcast_component_update

await broadcast_component_update(
    component_id="my-component-id",
    html=rendered_html,
    state={"count": 1}
)
```

## Testing

The component framework makes testing easy:

```python
def test_contact_form():
    form = ContactForm()
    result = form.dispatch(
        event="submit",
        payload={"form_data": {"name": "John", "email": "john@example.com", "message": "Hello!"}}
    )
    assert result["state"]["is_valid"] == True
```

## Production Considerations

1. **CSRF Protection**: The example disables CSRF for demo purposes. Enable it in production.
2. **Channel Layers**: Use Redis for channel layers in production
3. **Static Files**: Configure proper static file serving
4. **Database**: Use PostgreSQL or MySQL instead of SQLite
5. **WebSocket Scaling**: Use Redis channel layer for multi-process WebSocket support

## Troubleshooting

### WebSockets not working

Make sure you're using Daphne or another ASGI server:

```bash
daphne django_example.asgi:application
```

### Components not rendering

Check that components are imported in `apps.py`:

```python
def ready(self):
    from . import components  # noqa
```

### Templates not found

Ensure template directories are configured in `settings.py`.

## Next Steps

- Add authentication to components
- Implement permission checks
- Add more complex form validations
- Build real-time chat component
- Add optimistic UI updates
