# Contributing to Component Framework

Thank you for your interest in contributing! 🎉

## ⚠️ Alpha Status

This project is in **alpha**. We're actively developing core features and APIs may change significantly. Your contributions are welcome, but please understand:

- Breaking changes may occur without notice
- Your code may need updates as APIs evolve
- Documentation is still incomplete
- Features may be redesigned

## How to Contribute

### 1. Open an Issue First

For major changes:
1. Open an issue describing the change
2. Discuss the approach with maintainers
3. Wait for approval before starting work

For small fixes (typos, bugs, small improvements), feel free to submit a PR directly.

### 2. Development Setup

```bash
# Clone repository
git clone https://github.com/fsecada01/component-framework.git
cd component-framework

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest tests/
```

### 3. Code Standards

- **Python 3.11+** required
- **Formatter:** `ruff format .`
- **Linter:** `ruff check .`
- **Type hints:** Required for public APIs
- **Docstrings:** Required for classes and public methods
- **Tests:** Required for new features

### 4. Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Format code: `ruff format .`
6. Commit: `git commit -m "feat: add my feature"`
7. Push: `git push origin feature/my-feature`
8. Open a Pull Request

### 5. Commit Messages

Use conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Maintenance

Examples:
- `feat: add caching mixin for Django CBVs`
- `fix: handle missing component gracefully`
- `docs: update CBV guide with examples`

### 6. Pull Request Guidelines

- Keep PRs small and focused
- Include tests for new features
- Update documentation
- Ensure CI passes
- Request review from maintainers

## What to Contribute

### High Priority

- Bug fixes
- Documentation improvements
- Example applications
- Test coverage
- Performance optimizations

### Medium Priority

- New adapters (Flask, Litestar, etc.)
- Additional mixins
- Component utilities
- Developer tools

### Low Priority (Need Discussion)

- Major API changes
- New core features
- Breaking changes

## Code Structure

```
component-framework/
├── src/component_framework/
│   ├── core/          # Framework-agnostic (careful with changes!)
│   ├── adapters/      # Framework-specific (easier to change)
│   └── components/    # Examples (feel free to add!)
├── examples/          # Working examples (add more!)
├── tests/             # Tests (always add for features!)
└── docs/              # Documentation (needs improvement!)
```

## Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_counter.py

# Run with coverage
pytest --cov=component_framework
```

## Documentation

Update these as needed:
- `README.md` - Main documentation
- `CLAUDE.md` - AI assistant context
- `docs/` - Detailed guides

## Questions?

- Open an issue
- Check existing issues
- Read the docs

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Every contribution helps make this project better. We appreciate your time and effort! 🙏
