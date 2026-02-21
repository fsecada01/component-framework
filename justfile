# Component Framework - Development Commands
# Install just: https://github.com/casey/just

# Default recipe: show available commands
default:
    @just --list

# Install all dependencies (core + dev + django + websockets)
install:
    pip install -e ".[dev,django,websockets]"

# Install core dependencies only
install-core:
    pip install -e "."

# Run full test suite
test *ARGS:
    pytest tests/ {{ ARGS }}

# Run tests with verbose output
test-verbose:
    pytest tests/ -v --tb=short

# Run only core tests (no adapter tests)
test-core:
    pytest tests/test_component.py tests/test_form.py tests/test_registry.py tests/test_state.py tests/test_websocket.py -v

# Run only adapter tests
test-adapters:
    pytest tests/test_fastapi_adapter.py tests/test_fastapi_websocket.py tests/test_django_views.py tests/test_django_model.py tests/test_django_renderer.py tests/test_django_websocket.py tests/test_templatetags.py -v

# Lint with ruff
lint:
    ruff check .

# Lint and fix auto-fixable issues
lint-fix:
    ruff check --fix .

# Format code with ruff
format:
    ruff format .

# Check formatting without making changes
format-check:
    ruff format --check .

# Run all checks (lint + format check + tests)
check: lint format-check test

# Run pre-commit hooks on all files (requires prek or pre-commit)
pre-commit:
    prek --all-files

# Install pre-commit hooks
pre-commit-install:
    prek install

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .ruff_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Build the package
build: clean
    pip install build
    python -m build
