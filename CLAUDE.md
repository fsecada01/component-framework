# Component Framework - AI Development Context

This file provides context for AI assistants working on this project.

## Project Overview

**Component Framework** is a Python library for building server-side components with LiveView-style interactivity. It provides a framework-agnostic core with adapters for FastAPI and Django.

**Status:** Alpha (0.1.0-alpha)
**Language:** Python 3.11+
**License:** MIT

## Architecture

### Core Principles

1. **Framework Independence** - Core logic separated from web framework
2. **Component Lifecycle** - mount → hydrate → handle_event → render → dehydrate
3. **State Management** - Server-owned state with JSON serialization
4. **Event Routing** - Convention-based handlers (`on_<event>`)
5. **Pluggable Rendering** - Support for multiple template engines

### Key Components

```
component_framework/
├── core/              # Framework-agnostic
│   ├── component.py   # Base Component class
│   ├── form.py        # Form validation (Pydantic)
│   ├── websocket.py   # WebSocket manager
│   ├── registry.py    # Component registration
│   ├── renderer.py    # Renderer interface
│   └── state.py       # State storage
│
├── adapters/          # Framework-specific
│   ├── fastapi.py
│   ├── django_*.py
│   └── jinjax_renderer.py
│
└── templatetags/      # Django templates
```

## Development Guidelines

### Code Style

- **Formatter:** ruff format
- **Linter:** ruff check
- **Line length:** 100 characters
- **Type hints:** Required for public APIs
- **Docstrings:** Required for classes and public methods

### Testing

- Use pytest for tests
- Components are pure Python - test without HTTP
- Mock renderers for unit tests
- Integration tests in examples/

### Adding Features

When adding new features:

1. **Core first** - Add to core/ if framework-agnostic
2. **Adapters second** - Add framework-specific implementations
3. **Examples third** - Demonstrate in examples/
4. **Document** - Update docs/ and docstrings
5. **Test** - Add tests in tests/

### Component Design

Components should:
- Extend `Component` base class
- Use `@registry.register("name")` decorator
- Implement lifecycle methods (mount, on_events)
- Manage state via `self.state` dict
- Not contain domain logic (use models/services)

### Error Handling

- Raise `ComponentError` for component-specific errors
- Raise `EventNotFoundError` for missing handlers
- Log exceptions with `logging.exception()`
- Return user-friendly error messages

## Important Files

### Core Implementation

- `src/component_framework/core/component.py` - Base Component class (200 lines)
- `src/component_framework/core/form.py` - Form validation (200 lines)
- `src/component_framework/core/websocket.py` - WebSocket support (250 lines)

### Django Adapter

- `src/component_framework/adapters/django_views.py` - Views (FBV + CBV, 500 lines)
- `src/component_framework/adapters/django_model.py` - Model binding (200 lines)
- `src/component_framework/templatetags/components.py` - Template tags

### Examples

- `examples/fastapi_example.py` - FastAPI demo
- `examples/django_example/` - Complete Django app with 4 components

### Documentation

- `docs/server_component_spec.md` - Original specification
- `docs/BUILD_COMPLETE.md` - Implementation summary
- `docs/DJANGO_IMPLEMENTATION.md` - Django guide
- `docs/CBV_GUIDE.md` - Class-based views guide

## Common Tasks

### Adding a New Adapter

1. Create `adapters/your_framework.py`
2. Implement renderer class extending `Renderer`
3. Create endpoint handler
4. Add optional WebSocket support
5. Document in docs/
6. Add example in examples/

### Adding Component Features

1. Add method to `Component` base class
2. Update lifecycle documentation
3. Add tests
4. Update examples
5. Document in docstrings

### Fixing Bugs

1. Write failing test first
2. Fix bug
3. Ensure test passes
4. Check no regressions (run full test suite)
5. Update documentation if needed

## Known Limitations

- State must be JSON-serializable
- No automatic CSRF for WebSockets yet
- Component IDs generated client-side (could conflict)
- CacheMixin available but requires Django cache backend configuration
- Query optimization manual (not automatic)

## Future Enhancements

### Short Term
- Permission decorators
- Rate limiting (integrate django-ratelimit)
- Optimistic UI

### Long Term
- Component composition/nesting
- Automatic form generation
- Devtools/inspector
- Performance profiling
- Component marketplace

## Dependencies

### Core
- pydantic >= 2.0 (validation)
- No web framework required

### FastAPI
- fastapi >= 0.109
- uvicorn (server)
- jinjax >= 0.41 (rendering)

### Django
- django >= 4.2
- channels >= 4.0 (WebSocket)
- django-cotton >= 0.9 (optional)

### Development
- pytest >= 7.4
- pytest-asyncio >= 0.21
- httpx >= 0.26
- ruff >= 0.1
- prek (pre-commit hooks)
- just (task runner, cross-platform)

## Testing Strategy

### Unit Tests
- Test components in isolation
- Mock renderers
- Test lifecycle methods
- Test event routing
- Test state serialization

### Integration Tests
- Test with real frameworks
- Test HTTP endpoints
- Test WebSocket connections
- Test database interactions

### Examples as Tests
- FastAPI example should work
- Django example should work
- All components should render

## Performance Considerations

- Component dispatch: < 1ms (in-memory)
- State serialization: < 1ms (JSON)
- Full HTTP cycle: ~10-20ms (local)
- WebSocket latency: < 10ms (local)

Optimize:
- Query optimization (select_related, prefetch_related)
- State size (keep minimal)
- Template rendering (cache where possible)
- WebSocket broadcasting (use Redis channels)

## Security Considerations

- CSRF protection required for mutations
- Input validation (Pydantic schemas)
- State validation (don't trust client)
- Permission checks (use Django permissions/FastAPI dependencies)
- Rate limiting (for production)
- XSS prevention (escape output)

## Debugging Tips

### Component Not Rendering

1. Check component registered: `registry.list()`
2. Check renderer configured: `Component.renderer`
3. Check template exists
4. Check for exceptions in logs

### Events Not Working

1. Check handler exists: `hasattr(component, 'on_event')`
2. Check payload matches signature
3. Check state is being passed correctly
4. Check HTMX configuration

### WebSocket Issues

1. Check connection established
2. Check subscription active
3. Check message format
4. Check channel layer (Django)

## Code Examples

### Minimal Component

```python
@registry.register("hello")
class Hello(Component):
    template_name = "hello.html"

    def mount(self):
        self.state["message"] = "Hello World"
```

### Component with Form

```python
class MySchema(BaseModel):
    name: str
    email: EmailStr

@registry.register("my_form")
class MyForm(FormComponent):
    schema = MySchema

    def on_submit(self):
        # self.validated_data is type-safe
        save_data(self.validated_data)
```

### Model-Bound Component

```python
@registry.register("editor")
class Editor(DjangoModelComponent):
    model = MyModel
    state_fields = ["field1", "field2"]

    def on_save(self):
        self.update_instance_from_state()
        self.save_instance()
```

## Contributing

This is an alpha project. Breaking changes are expected.

When contributing:
1. Open issue first for major changes
2. Follow code style (ruff)
3. Add tests
4. Update docs
5. Keep PRs small and focused

## Questions?

- Check docs/ directory
- Look at examples/
- Read tests/
- Open a GitHub issue

## Project Goals

**Primary:**
- Framework-agnostic core
- Easy to use
- Easy to extend
- Good DX

**Non-Goals:**
- Replacing React/Vue
- Full ORM
- Specific template engine
- Client-side routing

## License

MIT - See LICENSE file
