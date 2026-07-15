# Component Framework

> **Beta** — the core lifecycle, permissions, composition, and testing utilities are stable, but the public API can still change before 1.0. Not yet published to PyPI (see [Installation](#installation)).

Server-driven UI components for Python web frameworks, in the style of Phoenix LiveView and Laravel Livewire: state and event handling live on the server, and [HTMX](https://htmx.org/) handles the client-side wiring instead of a JavaScript framework.

[![CI](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/fsecada01/component-framework/actions/workflows/ci.yml)
[![Docs](https://github.com/fsecada01/component-framework/actions/workflows/docs.yml/badge.svg)](https://github.com/fsecada01/component-framework/actions/workflows/docs.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The problem this solves

Adding interactivity to a server-rendered Python app usually means one of two paths: hand-roll a pile of endpoint-specific JavaScript, or bring in a separate SPA framework (React, Vue) and split your app into a Python API plus a JS frontend. Both add real cost — a second toolchain and build pipeline for the SPA route, or a growing pile of bespoke `fetch`/DOM-patching code for the hand-rolled route.

Component Framework gives you a third option, closer to how Phoenix LiveView, Rails Hotwire, and Laravel Livewire work: your component's Python class owns state and event handlers, the server renders HTML (via Jinja2, JinjaX, or Django templates), and a single ~500-line vanilla JS client (no build step, no bundler) sends events and swaps the returned markup into the page. There's no client-side state store to keep in sync with the server.

It's aimed at teams already building on FastAPI, Django, Litestar, or Flask who want LiveView-style interactive widgets — dashboards, forms, admin panels, real-time counters/carts — without adding a second frontend stack.

---

## How it works

```
Browser (HTMX + component-client.js)
        |  fetch POST /components/<name>  (event + payload)
Framework Adapter  (FastAPI / Django / Litestar / Flask)
        |
Component Framework Core
  - Lifecycle:  mount → hydrate → handle_event → render → dehydrate
  - Event routing:   on_<event> methods, resolved by convention (sync + async)
  - State:           server-owned JSON, round-tripped to the client each request
  - Renderer:         pluggable (JinjaX, Django templates, Jinja2, or custom)
        |
Backend (database / services)
```

Each request round-trip re-hydrates the component from the state the previous response sent down, dispatches the event to an `on_<event>` (or `async def on_<event>`) handler, re-renders, and returns HTML plus the new state. The client (`component-client.js`, in `src/component_framework/static/`) has no framework dependency — it reads `data-component`/`data-event`/`data-payload` attributes, POSTs the event, and swaps in the response. Today that swap is a full re-render of the component's markup (`innerHTML`); DOM morphing that preserves focus/scroll/in-flight input is on the [near-term roadmap](#roadmap), not implemented yet.

Because state round-trips through the client by default, the framework includes:
- **State size guards** — a 64 KB warning and a 512 KB hard limit on serialized state (`core/component.py`).
- **Optional HMAC state signing** — sign outbound state and reject tampered/unsigned state on the way back in ([`docs/STATE_SIGNING.md`](docs/STATE_SIGNING.md)).
- **Locked fields** — declare state keys (roles, prices, user IDs) that the client can never influence; they're stripped from what's sent to the client and re-derived server-side on every request ([`docs/LOCKED_FIELDS.md`](docs/LOCKED_FIELDS.md)).

---

## Framework support

| Framework | HTTP dispatch | WebSocket | SSE streaming | Renderer | Install extra |
|---|---|---|---|---|---|
| **FastAPI** | Yes | Yes (`fastapi_websocket.py`) | Yes | JinjaX | `[fastapi]` |
| **Django** | Yes (FBV + CBV) | Yes (Channels) | Yes | Django templates, `django-cotton` | `[django]` |
| **Litestar** | Yes | Yes (`litestar_websocket.py`) | Yes | Jinja2 | `[litestar]` |
| **Flask** | Yes | Not yet (planned) | Not yet (planned) | Flask's Jinja2 environment | `[flask]` |

A few things are Django-only today even though the underlying hook is framework-agnostic in `core/`:
- **CSRF protection** — enforced via Django's `CsrfViewMiddleware`. FastAPI, Litestar, and Flask have **no CSRF enforcement** in the adapter itself; see [`docs/SECURITY_CSRF.md`](docs/SECURITY_CSRF.md) for the full per-adapter audit and integration guidance before putting cookie/session auth in front of those adapters.
- **`RateLimitMixin`** and **`CacheMixin`** — both wrap Django's cache framework (`adapters/django_ratelimit.py`, `adapters/django_views.py`); no FastAPI/Litestar/Flask equivalent exists yet.
- **Server-confirmed optimistic patches** — `Component.get_optimistic_patch()` is defined on the framework-agnostic base class, but only the Django adapter currently surfaces it in the response payload. Client-side optimistic prediction (`data-optimistic` attributes in `component-client.js`) works with every adapter, since it's pure client-side JS talking to any of them over HTTP.

---

## Installation

**Not on PyPI yet** — install from source:

```bash
git clone https://github.com/fsecada01/component-framework.git
cd component-framework

# uv (recommended)
uv pip install -e ".[fastapi]"   # or [django] / [litestar] / [flask] / [all]

# or with pip
pip install -e ".[fastapi]"
```

`pydantic>=2.0` is the only mandatory dependency; everything else — FastAPI, Django, Litestar, Flask, JinjaX, Channels — is an optional extra so you only pull in what you use.

```bash
pip install -e ".[fastapi]"                        # single adapter
pip install -e ".[fastapi,django,litestar,flask]"   # several
pip install -e ".[all]"                             # everything, including dev-adjacent websockets extra
```

> Extras were made optional in 0.3.0 — if you're on an older checkout that assumed `fastapi`/`uvicorn`/`jinjax` installed by default, see [CHANGELOG.md](CHANGELOG.md).

---

## Quick start

### FastAPI

```bash
python examples/fastapi_example.py
# http://localhost:8000
```

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

Wiring an existing JinjaX `Catalog` (most FastAPI + JinjaX apps already have one, often sharing its Jinja environment with `Jinja2Templates`) — pass that catalog in rather than creating a fresh one, or component templates silently lose your app's filters/globals/extensions:

```python
from component_framework.adapters.jinjax_renderer import JinjaxRenderer
from component_framework.core.component import Component

Component.renderer = JinjaxRenderer(catalog)   # the catalog your app already built
```

### Django

```bash
cd examples/django_example
python manage.py migrate
python manage.py runserver
# http://localhost:8000
```

### Litestar

```bash
python examples/litestar_example.py
# http://localhost:8000
```

### Flask

```bash
python examples/flask_example.py
# http://localhost:5000
```

```python
from flask import Flask
from component_framework.adapters.flask import FlaskRenderer, register_component_routes
from component_framework.core.component import Component

app = Flask(__name__)
Component.renderer = FlaskRenderer(app)   # shares app.jinja_env
register_component_routes(app)            # POST /components/<name>
```

---

## Features

**Core** (framework-agnostic, `core/`)
- Component lifecycle with `mount` / `hydrate` / `handle_event` / `render` / `dehydrate`
- Async event handlers — `async def on_*`, dispatched via `async_dispatch()`
- Pluggable renderers — JinjaX, Django templates, Jinja2, or a custom `Renderer`
- `FormComponent` — Pydantic-validated forms with field-level errors, state kept in sync
- `SlotComponent` / `CompositeComponent` — named slots and composing components from named children, with context propagation
- `StreamingComponent` — SSE endpoints for long-running operations with intermediate renders (FastAPI, Litestar, Django)
- Permission classes — `AllowAny`, `IsAuthenticated`, `IsStaff`, `IsSuperuser`, `DjangoModelPermission`; checked automatically wherever a component declares `permission_classes`
- `ComponentTestCase` — mount components and dispatch events in tests without a running server; `dispatch_event()`, `mount_component()`, `assert_state()`, `assert_rendered()`

**Security**
- Optional HMAC-SHA256 state signing (`core/signing.py`, `StateSigner`) — versioned `cfs1.<payload>.<mac>` tokens, key rotation via comma-separated keys, tampered/raw-dict state rejected with HTTP 400
- `locked_fields` — server-trusted state keys stripped from outbound state and re-derived on every inbound request
- 64 KB warn / 512 KB hard limit on serialized state size
- CSRF: enforced on Django only today — see [`docs/SECURITY_CSRF.md`](docs/SECURITY_CSRF.md)

**Django-specific**
- Model binding (`DjangoModelComponent`) with `select_related`/`prefetch_related` and transactional saves
- Class-based views with auth/permission handling and JSON (not redirect) error responses
- `django-cotton` template support
- Django Channels WebSocket consumer with broadcast/subscribe
- `RateLimitMixin` (sliding-window, per-component/per-user, JSON 429s) and `CacheMixin` (render caching via Django's cache framework)

---

## More examples

```python
# Pydantic-validated form
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

```python
# Composition: slots + a composite parent
from component_framework.core.composition import SlotComponent, CompositeComponent

@registry.register("card")
class Card(SlotComponent):
    template_name = "card.html"
    slots = ["header", "body", "footer"]

@registry.register("product_page")
class ProductPage(CompositeComponent):
    components = {"card": Card, "cart": CartComponent}
```

```python
# Django model-bound component
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

```python
# Testing a component without an HTTP server
from component_framework.testing import ComponentTestCase

class TestCounter(ComponentTestCase):
    def test_increment(self):
        component = self.mount_component("counter")
        self.assert_state(component, count=0)
        self.dispatch_event(component, "increment", amount=5)
        self.assert_state(component, count=5)
```

More worked examples: [`docs/examples/ecommerce.md`](docs/examples/ecommerce.md) (real-time cart), [`docs/examples/wizard.md`](docs/examples/wizard.md) (multi-step FastAPI wizard), and the runnable apps under [`examples/`](examples/).

---

## Documentation

Full docs (generated from docstrings via [pdoc](https://pdoc.dev/), versioned per release): **[fsecada01.github.io/component-framework](https://fsecada01.github.io/component-framework/)**

| Guide | Covers |
|---|---|
| [Architecture spec](docs/server_component_spec.md) | Core design goals and component lifecycle |
| [Django implementation](docs/DJANGO_IMPLEMENTATION.md) | Django adapter setup and patterns |
| [Class-based views](docs/CBV_GUIDE.md) | Django CBV auth/permission patterns |
| [State signing](docs/STATE_SIGNING.md) | HMAC state setup per adapter, key rotation |
| [Locked fields](docs/LOCKED_FIELDS.md) | Server-trusted state fields, threat model |
| [CSRF & CSWSH guide](docs/SECURITY_CSRF.md) | Per-adapter CSRF audit, WebSocket hijacking guidance |
| [E-commerce example](docs/examples/ecommerce.md) | Real-time cart + product walkthrough |
| [Multi-step wizard](docs/examples/wizard.md) | FastAPI wizard recipe |

---

## Project layout

```
component-framework/
├── src/component_framework/
│   ├── core/            # Framework-agnostic: component, form, state, streaming,
│   │                     #   registry, renderer, permissions, composition, signing
│   ├── adapters/         # fastapi[.py|_websocket.py], litestar[.py|_websocket.py],
│   │                     #   flask.py, django_*.py, jinjax_renderer.py
│   ├── testing.py        # ComponentTestCase + pytest fixtures
│   ├── static/            # component-client.js (vanilla JS, no build step) + CSS
│   └── templatetags/     # Django template tags
├── examples/              # fastapi_example.py, fastapi_form_example.py,
│                          #   fastapi_wizard_example.py, litestar_example.py,
│                          #   flask_example.py, django_example/ (full app)
├── tests/                 # 28 modules, 477 tests (pytest -q)
├── docs/                  # Guides (Markdown) + pdoc-generated API site
└── pyproject.toml
```

---

## Testing

```bash
pytest tests/ -q --tb=short

# or via the justfile
just test              # full suite
just test-core         # core/ only
just test-adapters     # adapters/ only
```

CI (`.github/workflows/ci.yml`) runs the suite on Python 3.11, 3.12, 3.13, and 3.14, plus `ruff` and [`ty`](https://github.com/astral-sh/ty) (Astral's type checker), on every push and pull request.

---

## Development

```bash
just install                # install with the dev extra (uv pip install -e ".[dev]")
just pre-commit-install     # ruff + ty pre-commit hooks

just format / just lint / just lint-fix / just check
just docs-build / just docs-serve   # pdoc, http://localhost:8000
```

Contributions: open an issue for anything non-trivial before starting; small fixes can go straight to a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Known limitations

- CSRF is enforced on Django only; FastAPI, Litestar, and Flask have no CSRF protection in the adapter — read [`docs/SECURITY_CSRF.md`](docs/SECURITY_CSRF.md) before putting cookie/session auth in front of them.
- No origin check or handshake token on any WebSocket adapter (Cross-Site WebSocket Hijacking exposure) — see the same doc.
- `RateLimitMixin` and `CacheMixin` are Django-only.
- Flask has no WebSocket or SSE support yet.
- The client does a full markup replace on each update, not a DOM morph — in-flight input, focus, and scroll position aren't preserved across a re-render.
- Component state must be JSON-serializable, capped at 512 KB serialized.
- WebSocket fan-out across multiple server processes requires a Redis-backed channel layer (Django Channels).

---

## Roadmap

Beta features through 0.5.1 (permissions, rate limiting, caching, composition, testing utilities, the Litestar and Flask adapters, optional HMAC state signing, locked fields) are shipped. What's next, in order, is scoped in [CHANGELOG.md](CHANGELOG.md) and tracked via [GitHub milestones](https://github.com/fsecada01/component-framework/milestones):

- **0.6.0b — hardening**: DOM morphing (preserve focus/scroll/input), CSRF coverage for FastAPI/Litestar/Flask, 422 re-render on form validation failure.
- **0.7.0b — table stakes**: SPA-style navigation (history, back button), file uploads, WebSocket reconnection/resync, Flask WebSocket/SSE parity.
- **0.8.0b — mindshare**: telemetry/observability hooks, published benchmarks (none exist yet — no performance numbers are claimed anywhere else in this README), a JS interop/optimistic-command DSL.
- **1.0.0**: frozen public API, a full narrative guide, a deployment guide, PyPI publishing.

---

## Requirements

- Python 3.11+
- `pydantic>=2.0` (only mandatory runtime dependency)

Optional extras: `[fastapi]` (FastAPI 0.109+, Uvicorn, JinjaX 0.41+), `[django]` (Django 4.2+, Channels 4.0+, channels-redis 4.1+, django-cotton 0.9+), `[litestar]` (Litestar 2.0+, Jinja2 3.1+), `[flask]` (Flask 3.0+), `[websockets]` (websockets 12.0+), `[all]`.

---

## License

MIT — see [LICENSE](LICENSE).

Inspired by [Phoenix LiveView](https://hexdocs.pm/phoenix_live_view/), [Laravel Livewire](https://laravel-livewire.com/), [Hotwire/Turbo](https://turbo.hotwired.dev/), and [HTMX](https://htmx.org/).

- Issues: [github.com/fsecada01/component-framework/issues](https://github.com/fsecada01/component-framework/issues)
- Discussions: [github.com/fsecada01/component-framework/discussions](https://github.com/fsecada01/component-framework/discussions)
