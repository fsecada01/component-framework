# Component Framework

> ⚠️ **ALPHA SOFTWARE** - This project is in early development. APIs may change without notice. Not recommended for production use.

Framework-agnostic server components with LiveView-style interactivity inspired by Phoenix LiveView and Laravel Livewire.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/fsecada01/component-framework)

---

## 🚧 Development Status

**Current Version:** 0.1.0-alpha

This is an **experimental** framework. We're actively developing and testing core features. Expect:
- Breaking changes between versions
- Incomplete documentation
- Bugs and rough edges
- API instability

**Use at your own risk!** We welcome feedback, bug reports, and contributions.

---

## Features

### Core
- 🎯 **Framework-agnostic** - Works with FastAPI, Django, and more
- 🔄 **Server-driven UI** - State lives on the server, not the client
- ⚡ **Minimal JavaScript** - HTMX handles frontend interactions
- 🧩 **Reusable components** - Clean OOP boundaries with lifecycle hooks
- 🔌 **Pluggable renderers** - Jinjax, Django templates, or your own

### Forms & Validation
- ✅ **Pydantic validation** - Type-safe form handling
- 📝 **Field-level errors** - Live error feedback
- 🔄 **Automatic state sync** - Form ↔ component state

### Django Integration
- 🗃️ **Model binding** - Direct ORM integration
- ⚡ **Query optimization** - select_related, prefetch_related
- 🔒 **Transaction support** - Safe database updates
- 🎨 **Django templates** - Native template rendering
- 🧵 **Cotton support** - django-cotton integration
- 🔐 **CBVs** - Class-based views with auth/permissions

### Real-Time Updates
- 🌐 **WebSocket support** - Real-time component updates
- 📡 **Broadcasting** - Multi-client synchronization
- 🔌 **Django Channels** - Full Channels integration
- ⚡ **FastAPI WebSocket** - Native FastAPI support

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/fsecada01/component-framework.git
cd component-framework

# Install with uv (recommended)
uv pip install -e .

# With all features
uv pip install -e ".[django,websockets,dev]"
```

### FastAPI Example

```bash
python examples/fastapi_example.py
# Open http://localhost:8000
```

### Django Example

```bash
cd examples/django_example
python manage.py migrate
python manage.py runserver
# Open http://localhost:8000
```

---

## Documentation

- 📖 [Architecture Overview](docs/server_component_spec.md)
- 🚀 [Getting Started Guide](docs/BUILD_COMPLETE.md)
- 🐍 [Django Implementation](docs/DJANGO_IMPLEMENTATION.md)
- 🎓 [Class-Based Views Guide](docs/CBV_GUIDE.md)
- 📊 [Prototype Status](docs/PROTOTYPE_STATUS.md)

---

## Example Component

### Simple Counter

```python
from component_framework.core import Component, registry

@registry.register("counter")
class Counter(Component):
    template_name = "counter.html"

    def mount(self):
        self.state["count"] = 0

    def on_increment(self, amount: int = 1):
        self.state["count"] += amount
```

### Form with Validation

```python
from pydantic import BaseModel, EmailStr
from component_framework.core import FormComponent

class ContactSchema(BaseModel):
    name: str
    email: EmailStr
    message: str

@registry.register("contact_form")
class ContactForm(FormComponent):
    schema = ContactSchema

    def on_submit(self):
        # self.validated_data contains clean data
        send_email(self.validated_data)
```

### Django Model Component

```python
from component_framework.adapters.django_model import DjangoModelComponent

@registry.register("order_editor")
class OrderEditor(DjangoModelComponent):
    model = Order
    state_fields = ["status", "notes", "total"]
    select_related = ["customer"]

    def on_update_status(self, status: str):
        self.instance.status = status
        self.save_instance()
```

---

## Architecture

```
┌─────────────────────────────────┐
│   Browser (HTMX/WebSocket)      │
└─────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────┐
│   Framework Adapter             │
│   • FastAPI/Django              │
│   • HTTP + WebSocket            │
└─────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────┐
│   Component Framework Core      │
│   • Component lifecycle         │
│   • Event routing               │
│   • State management            │
│   • Validation                  │
└─────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────┐
│   Backend (Database/Services)   │
└─────────────────────────────────┘
```

### Component Lifecycle

```
instantiate → mount/hydrate → handle_event → render → dehydrate
```

---

## Project Structure

```
component-framework/
├── src/component_framework/
│   ├── core/                    # Framework-agnostic core
│   │   ├── component.py         # Base Component class
│   │   ├── form.py              # Form validation
│   │   ├── websocket.py         # WebSocket manager
│   │   ├── registry.py          # Component registration
│   │   ├── renderer.py          # Renderer interface
│   │   └── state.py             # State storage
│   │
│   ├── adapters/                # Framework adapters
│   │   ├── fastapi.py           # FastAPI integration
│   │   ├── fastapi_websocket.py # FastAPI WebSocket
│   │   ├── django_views.py      # Django views (FBV + CBV)
│   │   ├── django_model.py      # Django model binding
│   │   ├── django_renderer.py   # Django templates
│   │   ├── django_websocket.py  # Django Channels
│   │   └── jinjax_renderer.py   # Jinjax rendering
│   │
│   ├── components/              # Example components
│   │   └── counter.py
│   │
│   └── templatetags/            # Django template tags
│       └── components.py
│
├── examples/
│   ├── fastapi_example.py       # FastAPI demo
│   └── django_example/          # Complete Django app
│
├── tests/
│   └── test_counter.py
│
├── docs/                        # Documentation
└── templates/                   # Component templates
```

---

## Testing

```bash
# Core tests
pytest tests/

# Manual test
python tests/test_counter.py

# Django tests
cd examples/django_example
python manage.py test
```

---

## Development

### Setup

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Format code
ruff format .

# Lint
ruff check .
```

### Contributing

We welcome contributions! This is an alpha project, so:

1. **Open an issue first** to discuss major changes
2. Follow existing code style (ruff)
3. Add tests for new features
4. Update documentation
5. Keep PRs focused and small

See [CONTRIBUTING.md](CONTRIBUTING.md) for details (coming soon).

---

## Roadmap

### Alpha (Current)
- [x] Core component framework
- [x] FastAPI adapter
- [x] Django adapter
- [x] Form validation
- [x] Model binding
- [x] WebSocket support
- [x] Class-based views

### Beta (Planned)
- [ ] Authentication & permissions
- [ ] Rate limiting
- [ ] Component caching
- [ ] Optimistic UI
- [ ] Component composition
- [ ] Testing utilities

### 1.0 (Future)
- [ ] Stable API
- [ ] Full documentation
- [ ] Performance optimization
- [ ] Component marketplace
- [ ] Devtools/inspector

---

## Performance

Current benchmarks (local development):
- Component dispatch: < 1ms
- State serialization: < 1ms
- Full HTTP cycle: ~10-20ms
- WebSocket latency: < 10ms

*Note: These are preliminary benchmarks. Performance optimization is ongoing.*

---

## Requirements

- Python 3.11+
- FastAPI 0.109+ (for FastAPI adapter)
- Django 4.2+ (for Django adapter)
- Pydantic 2.0+

Optional:
- Django Channels 4.0+ (for WebSocket)
- django-cotton 0.9+ (for Cotton integration)
- Jinjax 0.41+ (for Jinjax rendering)

---

## Known Issues

- WebSocket scaling requires Redis channel layer
- State size limits not enforced
- CSRF handling needs improvement
- Documentation incomplete
- Test coverage needs improvement

See [Issues](https://github.com/fsecada01/component-framework/issues) for full list.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Inspired by:
- [Phoenix LiveView](https://hexdocs.pm/phoenix_live_view/)
- [Laravel Livewire](https://laravel-livewire.com/)
- [Hotwire/Turbo](https://turbo.hotwired.dev/)
- [HTMX](https://htmx.org/)

---

## Support

- 📧 Issues: [GitHub Issues](https://github.com/fsecada01/component-framework/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/fsecada01/component-framework/discussions)
- 📖 Docs: [Documentation](docs/)

---

**Remember: This is alpha software. Use in production at your own risk!**
