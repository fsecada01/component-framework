# Component Framework

> **BETA SOFTWARE** — APIs are stabilising. Core features are complete and test-covered. Minor breaking changes may still occur before 1.0.

Framework-agnostic server components with LiveView-style interactivity inspired by Phoenix LiveView and Laravel Livewire.

[![CI](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml)
[![Docs](https://github.com/fsecada01/component-framework/actions/workflows/docs.yml/badge.svg)](https://github.com/fsecada01/component-framework/actions/workflows/docs.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Beta](https://img.shields.io/badge/status-beta-blue.svg)](https://fsecada01.github.io/component-framework/)

---

## Development Status

**Current Version:** 0.2.0-beta
**API Documentation:** [fsecada01.github.io/component-framework](https://fsecada01.github.io/component-framework/)

The framework has a complete, tested feature set covering the full Beta roadmap. APIs are solidifying — the core lifecycle, permissions, composition, and testing utilities are stable. We welcome feedback before the 1.0 release.

---

## Features

### Core
- **Framework-agnostic** — Works with FastAPI, Django, and more
- **Server-driven UI** — State lives on the server, not the client
- **Minimal JavaScript** — HTMX handles frontend interactions
- **Reusable components** — Clean OOP boundaries with lifecycle hooks
- **Pluggable renderers** — Jinjax, Django templates, or your own

### Forms & Validation
- **Pydantic validation** — Type-safe form handling
- **Field-level errors** — Live error feedback
- **Automatic state sync** — Form state synchronised with component state

### Access Control
- **Permission classes** — `AllowAny`, `IsAuthenticated`, `IsStaff`, `IsSuperuser`, `DjangoModelPermission`
- **FBV decorators** — `login_required_component`, `permission_required_component`, `staff_required_component` returning JSON 401/403
- **Component-level control** — `permission_classes` attribute checked by both FBV and CBV automatically
- **JSON-only responses** — No login redirects for API/HTMX consumers

### Rate Limiting
- **`RateLimitMixin`** — Per-component, per-user sliding-window rate limiting
- **Configurable** — Custom limits and windows per component class
- **429 responses** — Consistent JSON `{"error": "Rate limit exceeded"}` on breach

### Component Composition
- **`SlotComponent`** — Named and default slot support
- **`CompositeComponent`** — Compose components from named child components
- **Context propagation** — Parent context flows to child components

### Optimistic UI
- **`OptimisticMixin`** — `get_optimistic_patch()` for instant client-side feedback before server confirmation
- **Rollback support** — Revert on error

### Django Integration
- **Model binding** — Direct ORM integration
- **Query optimisation** — `select_related`, `prefetch_related`
- **Transaction support** — Safe database updates
- **Django templates** — Native template rendering
- **Cotton support** — `django-cotton` integration
- **CBVs** — Class-based views with auth/permissions, JSON error responses

### Real-Time Updates
- **WebSocket support** — Real-time component updates
- **Broadcasting** — Multi-client synchronisation
- **Django Channels** — Full Channels integration
- **FastAPI WebSocket** — Native FastAPI support

### Caching
- **`CacheMixin`** — Configurable per-component render caching
- **Cache invalidation** — Manual and event-driven invalidation
- **Django cache backend** — Works with any Django cache backend

### Testing Utilities
- **`ComponentTestCase`** — Test components without HTTP, without a running server
- **Event simulation** — `dispatch_event()`, `mount_component()`
- **State assertions** — `assert_state()`, `assert_rendered()`
- **pytest fixtures** — Ready-to-use fixtures for common patterns

---

## Quick Start

### Installation

```bash
git clone https://github.com/fsecada01/component-framework.git
cd component-framework

# Install with uv (recommended)
uv pip install -e ".[dev,django,websockets]"
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

**API Reference:** [fsecada01.github.io/component-framework](https://fsecada01.github.io/component-framework/)

Generated from docstrings by pdoc and deployed to GitHub Pages on every push to `master` and on every `v*` release tag.

| Guide | Description |
|-------|-------------|
| [Architecture Overview](docs/server_component_spec.md) | Core design and component lifecycle |
| [Django Implementation](docs/DJANGO_IMPLEMENTATION.md) | Django adapter setup and patterns |
| [Class-Based Views](docs/CBV_GUIDE.md) | CBV auth/permission patterns |
| [E-Commerce Example](docs/examples/ecommerce.md) | Real-time cart + product demo |

### AI / LLM Context

- [Project Context](CLAUDE.md) — loaded automatically by Claude Code
- [Orchestration Workflow](prompts/WORKFLOW.md) — multi-agent routing, model selection, RTK

---

## Example Components

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
        send_email(self.validated_data)
```

### Component with Permissions & Rate Limiting

```python
from component_framework.core.permissions import IsAuthenticated
from component_framework.adapters.django_ratelimit import RateLimitMixin

@registry.register("order_actions")
class OrderActions(RateLimitMixin, Component):
    permission_classes = [IsAuthenticated]
    rate_limit = 10          # requests
    rate_limit_window = 60   # seconds

    def on_submit_order(self):
        ...
```

### Component Composition

```python
from component_framework.core.composition import SlotComponent, CompositeComponent

@registry.register("card")
class Card(SlotComponent):
    template_name = "card.html"
    slots = ["header", "body", "footer"]

@registry.register("product_page")
class ProductPage(CompositeComponent):
    components = {
        "card": Card,
        "cart": CartComponent,
    }
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

### Testing with ComponentTestCase

```python
from component_framework.testing import ComponentTestCase

class TestCounter(ComponentTestCase):
    def test_increment(self):
        component = self.mount_component("counter")
        self.assert_state(component, count=0)
        self.dispatch_event(component, "increment", amount=5)
        self.assert_state(component, count=5)
```

---

## Architecture

```
Browser (HTMX/WebSocket)
        |
Framework Adapter  (FastAPI / Django)
        |
Component Framework Core
  - Component lifecycle  (mount → hydrate → handle_event → render → dehydrate)
  - Event routing        (convention-based on_<event> handlers)
  - State management     (server-owned JSON state)
  - Permissions          (per-component permission_classes)
  - Composition          (SlotComponent, CompositeComponent)
        |
Backend (Database / Services)
```

---

## Project Structure

```
component-framework/
├── src/component_framework/
│   ├── core/                        # Framework-agnostic core
│   │   ├── component.py             # Base Component class + lifecycle
│   │   ├── form.py                  # Pydantic form validation
│   │   ├── websocket.py             # WebSocket manager
│   │   ├── registry.py              # Component registration
│   │   ├── renderer.py              # Renderer interface
│   │   ├── state.py                 # State storage
│   │   ├── permissions.py           # Permission classes (Beta)
│   │   └── composition.py           # Slot + composite components (Beta)
│   │
│   ├── adapters/                    # Framework adapters
│   │   ├── fastapi.py               # FastAPI integration
│   │   ├── fastapi_websocket.py     # FastAPI WebSocket
│   │   ├── django_views.py          # Django views (FBV + CBV)
│   │   ├── django_model.py          # Django model binding
│   │   ├── django_renderer.py       # Django template rendering
│   │   ├── django_websocket.py      # Django Channels
│   │   ├── django_permissions.py    # FBV permission decorators (Beta)
│   │   ├── django_ratelimit.py      # Rate limiting mixin (Beta)
│   │   └── jinjax_renderer.py       # Jinjax rendering
│   │
│   ├── testing.py                   # ComponentTestCase + fixtures (Beta)
│   ├── components/                  # Example components
│   └── templatetags/components.py   # Django template tags
│
├── examples/
│   ├── fastapi_example.py           # FastAPI demo
│   └── django_example/              # Complete Django app
│
├── tests/                           # 19 test modules
│   ├── test_component.py            # Core component tests
│   ├── test_form.py                 # Form validation tests
│   ├── test_registry.py             # Registry tests
│   ├── test_state.py                # State storage tests
│   ├── test_websocket.py            # WebSocket manager tests
│   ├── test_fastapi_adapter.py      # FastAPI adapter tests
│   ├── test_fastapi_websocket.py    # FastAPI WebSocket tests
│   ├── test_django_views.py         # Django views tests
│   ├── test_django_model.py         # Django model binding tests
│   ├── test_django_renderer.py      # Django renderer tests
│   ├── test_django_websocket.py     # Django Channels tests
│   ├── test_templatetags.py         # Template tags tests
│   ├── test_permissions.py          # Permission class tests (Beta)
│   ├── test_composition.py          # Composition tests (Beta)
│   ├── test_testing_utils.py        # Testing utility tests (Beta)
│   ├── test_caching.py              # Cache mixin tests (Beta)
│   ├── test_ratelimit.py            # Rate limit tests (Beta)
│   └── test_optimistic.py           # Optimistic UI tests (Beta)
│
├── docs/                            # Documentation
│   ├── make.py                      # pdoc build script
│   ├── docs_settings.py             # Minimal Django settings for pdoc
│   ├── pdoc_templates/              # Custom pdoc templates (terminal brutalism)
│   ├── update_gh_pages.py           # CI helper: versions.json + root index
│   └── examples/ecommerce.md        # Real-time e-commerce walkthrough
│
├── .github/workflows/
│   ├── ci.yml                       # Tests, lint, type check (Python 3.11–3.14)
│   └── docs.yml                     # pdoc build + versioned GitHub Pages deploy
│
├── justfile                         # Task runner
├── .pre-commit-config.yaml          # ruff + ty hooks
└── pyproject.toml
```

---

## Testing

```bash
# Run full test suite
just test

# Verbose output
just test-verbose

# Core tests only
just test-core

# Adapter tests only
just test-adapters

# Or pytest directly
pytest tests/ -q --tb=short
```

CI runs against Python 3.11, 3.12, 3.13, and 3.14 on every push and pull request.

---

## Development

### Setup

```bash
just install                # Install all deps (just: https://github.com/casey/just)

# Or manually
uv pip install -e ".[dev,django,websockets]"

just pre-commit-install     # Install ruff + ty pre-commit hooks
```

### Common Commands

```bash
just format          # Format code with ruff
just lint            # Lint with ruff
just lint-fix        # Lint and auto-fix
just check           # lint + format-check + tests

just docs-build      # Build API docs -> docs/site/
just docs-serve      # Start pdoc dev server (localhost:8000)
just docs-check      # Verify pdoc is installed and show config
just docs-clean      # Remove docs/site/

just clean           # Remove build artifacts
just build           # Build the package
```

### Claude Code Development

```bash
just claude                          # Interactive Claude Code
just claude-unsafe                   # Skip permission prompts (trusted env only)
just claude-prompt                   # Append CLAUDE.md as system prompt
just claude-unsafe-prompt            # System prompt + skip permissions
just claude-orchestrate              # Full orchestration workflow

# Override prompt file
just claude-prompt PROMPT_FILE=prompts/WORKFLOW.md
```

| Prompt file | Purpose |
|------------|---------|
| `CLAUDE.md` | Project architecture, conventions, guidelines (default) |
| `prompts/WORKFLOW.md` | Multi-agent orchestration, model selection, RTK token efficiency |

### Code Quality

- **[ruff](https://docs.astral.sh/ruff/)** — Linting and formatting (line length: 100)
- **[ty](https://github.com/astral-sh/ty)** — Type checking (Astral's Rust-based)
- **pre-commit** — Git hooks: trailing whitespace, YAML, merge conflicts, ruff, ty

### Contributing

1. Open an issue first to discuss major changes
2. Follow existing code style (ruff)
3. Add tests for new features
4. Update docstrings (used for API docs)
5. Keep PRs focused and small

---

## Roadmap

### Alpha (Complete)
- [x] Core component framework
- [x] FastAPI adapter
- [x] Django adapter
- [x] Form validation
- [x] Model binding
- [x] WebSocket support
- [x] Class-based views
- [x] CI pipeline (GitHub Actions)
- [x] Pre-commit hooks (ruff + ty)
- [x] Comprehensive test suite

### Beta (Complete)
- [x] Permission classes and FBV decorators
- [x] Rate limiting (`RateLimitMixin`)
- [x] Component caching (`CacheMixin`)
- [x] Optimistic UI (`OptimisticMixin`)
- [x] Component composition (slots, composite)
- [x] Testing utilities (`ComponentTestCase`)
- [x] Versioned API documentation (GitHub Pages + pdoc)

### 1.0 (Planned)
- [ ] Stable, frozen public API
- [ ] Performance benchmarks and optimisation
- [ ] Devtools / inspector
- [ ] Component marketplace / registry
- [ ] Full user guide and tutorials

---

## Performance

Current benchmarks (local development):
- Component dispatch: < 1ms
- State serialisation: < 1ms
- Full HTTP cycle: ~10–20ms
- WebSocket latency: < 10ms

---

## Requirements

- Python 3.11+
- FastAPI 0.109+ (FastAPI adapter)
- Django 4.2+ (Django adapter)
- Pydantic 2.0+

Optional:
- Django Channels 4.0+ (WebSocket)
- channels-redis 4.1+ (WebSocket scaling)
- django-cotton 0.9+ (Cotton integration)
- Jinjax 0.41+ (Jinjax rendering)

---

## Known Limitations

- State must be JSON-serialisable
- WebSocket scaling requires a Redis channel layer
- CSRF handling for WebSockets is manual
- State size limits not enforced (keep state minimal)

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Inspired by:
- [Phoenix LiveView](https://hexdocs.pm/phoenix_live_view/)
- [Laravel Livewire](https://laravel-livewire.com/)
- [Hotwire/Turbo](https://turbo.hotwired.dev/)
- [HTMX](https://htmx.org/)

---

## Support

- Issues: [GitHub Issues](https://github.com/fsecada01/component-framework/issues)
- Discussions: [GitHub Discussions](https://github.com/fsecada01/component-framework/discussions)
- Docs: [fsecada01.github.io/component-framework](https://fsecada01.github.io/component-framework/)
