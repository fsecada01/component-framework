# Component Framework

> ⚠️ **ALPHA SOFTWARE** - This project is in early development. APIs may change without notice. Not recommended for production use.

Framework-agnostic server components with LiveView-style interactivity inspired by Phoenix LiveView and Laravel Livewire.

[![CI](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml)
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
- 🐍 [Django Implementation](docs/DJANGO_IMPLEMENTATION.md)
- 🎓 [Class-Based Views Guide](docs/CBV_GUIDE.md)

### Reports & Status

- 🚀 [Build Summary](docs/reports/BUILD_COMPLETE.md)
- 📊 [Prototype Status](docs/reports/PROTOTYPE_STATUS.md)

### AI / LLM Context

- 🤖 [Project Context](CLAUDE.md) — loaded automatically by Claude Code
- ⚙️ [Orchestration Workflow](prompts/WORKFLOW.md) — multi-agent routing, model selection, RTK

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
├── tests/                         # Test suite
│   ├── conftest.py                # Shared fixtures
│   ├── test_component.py          # Core component tests
│   ├── test_form.py               # Form validation tests
│   ├── test_registry.py           # Registry tests
│   ├── test_state.py              # State storage tests
│   ├── test_websocket.py          # WebSocket manager tests
│   ├── test_fastapi_adapter.py    # FastAPI adapter tests
│   ├── test_fastapi_websocket.py  # FastAPI WebSocket tests
│   ├── test_django_views.py       # Django views tests
│   ├── test_django_model.py       # Django model binding tests
│   ├── test_django_renderer.py    # Django renderer tests
│   ├── test_django_websocket.py   # Django Channels tests
│   └── test_templatetags.py       # Template tags tests
│
├── docs/                          # Documentation
├── justfile                       # Task runner commands
├── .pre-commit-config.yaml        # Pre-commit hooks
└── templates/                     # Component templates
```

---

## Testing

```bash
# Run full test suite
just test

# Run with verbose output
just test-verbose

# Run only core tests
just test-core

# Run only adapter tests
just test-adapters

# Or use pytest directly
pytest tests/ -q --tb=short
```

CI runs the test suite against Python 3.11, 3.12, 3.13, and 3.14 on every push and pull request.

---

## Development

### Setup

```bash
# Install all dependencies (requires just: https://github.com/casey/just)
just install

# Or install manually
uv pip install -e ".[dev,django,websockets]"

# Install pre-commit hooks
just pre-commit-install
```

### Common Commands

```bash
just format          # Format code with ruff
just lint            # Lint with ruff
just lint-fix        # Lint and auto-fix
just check           # Run lint + format check + tests
just pre-commit      # Run all pre-commit hooks
just clean           # Remove build artifacts
just build           # Build the package
```

### Claude Code Development

The justfile includes recipes for running [Claude Code](https://claude.ai/claude-code) with project-specific context:

```bash
just claude                          # Run Claude Code interactively
just claude-unsafe                   # Skip permission prompts (local/trusted only)
just claude-prompt                   # Append CLAUDE.md as system prompt
just claude-unsafe-prompt            # System prompt + skip permissions
just claude-orchestrate              # Full orchestration workflow (see WORKFLOW.md)

# Override the default system prompt file (CLAUDE.md)
just claude-prompt PROMPT_FILE=my_prompt.md
just claude-unsafe-prompt PROMPT_FILE=my_prompt.md
```

Two system prompt files are available:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project architecture, conventions, and development guidelines (default) |
| `prompts/WORKFLOW.md` | Multi-agent orchestration, model selection matrix, RTK token efficiency, and skill routing |

`CLAUDE.md` is the default for `claude-prompt`. `WORKFLOW.md` defines parallel agent patterns, model cost-routing (Haiku/Sonnet/Opus by task type), RTK integration for 60–99% token reduction, and skill-to-task mappings for this project. Use `just claude-orchestrate` to activate it.

The `--dangerously-skip-permissions` flag is only appropriate in trusted local environments.

### Code Quality

The project uses the following tools, enforced via CI and pre-commit hooks:

- **[ruff](https://docs.astral.sh/ruff/)** - Linting and formatting (line length: 100)
- **[ty](https://github.com/astral-sh/ty)** - Type checking (Astral's Rust-based type checker)
- **[pre-commit](https://pre-commit.com/)** - Git hooks for trailing whitespace, YAML checks, merge conflict detection, ruff, and ty

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
- [x] CI pipeline (GitHub Actions)
- [x] Pre-commit hooks (ruff + ty)
- [x] Comprehensive test suite

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
