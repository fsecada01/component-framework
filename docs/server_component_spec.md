# Server Components Architecture Spec
Framework-Agnostic Core with Django and FastAPI/Litestar Adapters

## Overview

This document specifies a server-driven component architecture inspired by LiveView-style systems while remaining framework-agnostic.

The architecture enables:

- Server-owned UI state
- Declarative model bindings
- Reactive UI updates via HTMX/WebSockets/SSE
- Minimal frontend JavaScript
- Reusable component logic across frameworks
- Integration with multiple templating systems (Jinjax, Django templates, etc.)

The system is composed of:

```
Core (framework agnostic)
    ↓
Adapters
    ├─ FastAPI / Litestar + Jinjax
    └─ Django + Django-Cotton (+ Jinjax optional)
```

---

## Goals

### Primary Goals

- Framework independence
- Clean separation of concerns
- Declarative configuration
- Extensibility via adapters
- Minimal coupling to ORM or transport
- LiveView-like developer experience

### Non-Goals

- Replacing frontend frameworks entirely
- Providing a full ORM
- Forcing a specific templating engine

---

## Architectural Principles

### 1. Component Owns Interaction

Components manage:

- UI state
- Event handling
- Rendering orchestration

### 2. Models Own Domain Logic

ORM models manage:

- Business rules
- Validation
- Persistence logic
- Invariants

Components must not contain domain logic.

### 3. Renderer is Pluggable

Rendering must be independent of:

- Jinja
- Jinjax
- Django templates
- Other engines

### 4. Transport Agnostic

Components must work with:

- HTMX
- Fetch/AJAX
- WebSockets
- SSE
- CLI
- Tests

---

## Core Concepts

### Component Lifecycle

```
instantiate →
    mount() or hydrate()
    handle_event()
    render()
    dehydrate()
return response
```

Lifecycle methods:

| Method | Purpose |
|--------|---------|
| mount() | First initialization |
| hydrate(state) | Restore state |
| handle_event() | Event routing |
| render() | Produce HTML |
| dehydrate() | Persist state |

---

## Core Implementation

### Component Base Class

```python
class Component:

    template_name: str | None = None
    renderer = None

    def __init__(self, **params):
        self.params = params
        self.state = {}
        self.errors = {}
        self.id = params.get("component_id")

    # ---------- Lifecycle ----------

    def mount(self):
        pass

    def hydrate(self, state: dict):
        self.state.update(state)

    def dehydrate(self) -> dict:
        return self.state

    # ---------- Events ----------

    def handle_event(self, event: str, payload: dict):
        handler = getattr(self, f"on_{event}", None)
        if handler:
            handler(**payload)

    # ---------- Rendering ----------

    def get_context(self):
        return {
            "component": self,
            "state": self.state,
            "errors": self.errors,
        }

    def render(self):
        return self.renderer.render(
            self.template_name,
            self.get_context(),
        )

    # ---------- Dispatch ----------

    def dispatch(self, event=None, payload=None, state=None):

        if state:
            self.hydrate(state)
        else:
            self.mount()

        if event:
            self.handle_event(event, payload or {})

        html = self.render()

        return {
            "html": html,
            "state": self.dehydrate(),
        }
```

---

## Renderer Interface

```python
class Renderer:
    def render(self, template_name: str, context: dict) -> str:
        raise NotImplementedError
```

---

## Registry System

```python
registry = {}

def register(name):
    def decorator(cls):
        registry[name] = cls
        return cls
    return decorator
```

---

## Model Binding (Optional Core Mixin)

```python
class ModelMixin:

    model = None

    def get_instance(self):
        raise NotImplementedError

    def save_instance(self):
        raise NotImplementedError
```

---

## Stateful Component Support (Optional)

```python
class StateStore:

    def save(self, component_id: str, state: dict):
        raise NotImplementedError

    def load(self, component_id: str) -> dict | None:
        raise NotImplementedError
```

---

# FastAPI / Litestar Adapter

## Jinjax Renderer

```python
from jinjax import Environment

class JinjaxRenderer(Renderer):

    def __init__(self, env: Environment):
        self.env = env

    def render(self, template_name, context):
        component = self.env.get_component(template_name)
        return component(**context)
```

---

## Example Component

```python
@register("counter")
class Counter(Component):

    template_name = "counter"

    def mount(self):
        self.state["count"] = 0

    def on_increment(self):
        self.state["count"] += 1
```

---

## FastAPI Endpoint

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/components/{name}")
async def component_endpoint(name: str, request: Request):

    data = await request.json()

    component_cls = registry[name]

    component = component_cls(**data.get("params", {}))

    result = component.dispatch(
        event=data.get("event"),
        payload=data.get("payload"),
        state=data.get("state"),
    )

    return result
```

---

## HTMX Example

```html
<div
    hx-post="/components/counter"
    hx-trigger="click"
    hx-target="#counter"
    hx-swap="outerHTML">
</div>
```

---

# Django Adapter

## Renderer Using Django Templates

```python
from django.template.loader import render_to_string

class DjangoRenderer(Renderer):

    def render(self, template_name, context):
        return render_to_string(template_name, context)
```

---

## Django Model Mixin

```python
class DjangoModelMixin(ModelMixin):

    def get_instance(self):
        pk = self.params.get("pk")
        if pk:
            return self.model.objects.get(pk=pk)
        return self.model()

    def save_instance(self):
        self.instance.save()
```

---

## Example Component

```python
@register("order_editor")
class OrderEditor(DjangoModelMixin, Component):

    model = Order
    template_name = "components/order_editor.html"

    def mount(self):
        self.instance = self.get_instance()
        self.state["status"] = self.instance.status

    def on_save(self):
        self.instance.status = self.state["status"]
        self.save_instance()
```

---

## Django View Endpoint

```python
from django.http import JsonResponse

def component_endpoint(request, name):

    component_cls = registry[name]

    component = component_cls(**request.POST.dict())

    result = component.dispatch(
        event=request.POST.get("event"),
        payload=request.POST.dict(),
        state=request.POST.get("state"),
    )

    return JsonResponse(result)
```

---

# Django-Cotton Integration

## Template Tag

```python
@register.simple_tag(takes_context=True)
def live_component(context, name, **params):

    component_cls = registry[name]

    component = component_cls(**params)

    result = component.dispatch()

    return mark_safe(result["html"])
```

Usage:

```html
{% live_component "order_editor" pk=order.id %}
```

---

# Jinjax Integration

## Template Example

```jinja
<div id="counter">
    <button
        hx-post="/components/counter"
        hx-vals='{"event": "increment"}'
        hx-target="#counter"
        hx-swap="outerHTML">
        Count: {{ state.count }}
    </button>
</div>
```

---

# Event Routing Convention

Event methods use naming:

```
on_<event_name>()
```

Example:

```python
def on_save(self):
    ...
```

---

# Declarative Model Binding (Recommended Future Feature)

Example API:

```python
class OrderComponent(ModelComponent):

    model = Order
    fields = ["status", "customer"]
    readonly = ["total"]
    exclude = []
```

---

# Dirty State Tracking (Optional)

```python
self.changed_fields = set()
```

Useful for:

- Optimistic UI
- Partial updates
- Field highlighting

---

# Real-Time Extensions (Optional)

## WebSockets / SSE Flow

```
Model updated →
    publish event →
        components subscribed →
            re-render →
                push HTML →
                    HTMX swap
```

---

# Suggested Project Structure

```
core/
    component.py
    renderer.py
    registry.py
    state.py
    model.py

adapters/
    fastapi.py
    litestar.py
    django.py
    jinjax.py

components/
    counter.py
    order_editor.py

templates/
    components/

templatetags/
    live_components.py
```

---

# Testing Strategy

Components are pure Python objects.

```python
component = Counter()
result = component.dispatch(event="increment")
assert result["state"]["count"] == 1
```

No HTTP required.

---

# Future Enhancements

- Automatic form generation from model metadata
- DOM morphing integration
- WebSocket adapter layer
- Component diffing
- Devtools inspector
- Permission system
- Dependency injection
- Optimistic UI engine

---

# Summary

This architecture provides:

- LiveView-like server interactivity
- Minimal JavaScript
- Framework independence
- Django and FastAPI compatibility
- Clean OOP boundaries
- Extensible rendering system

The system treats:

```
Models = domain engine
Components = interaction engine
Templates = presentation
Transport = delivery
```

---

# End of Spec

