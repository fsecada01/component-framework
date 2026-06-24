# Component Framework - Development Commands
# Install just: https://github.com/casey/just


set shell := ["cmd.exe", "/c"]

# Default recipe: show available commands
default:
    @just --list

# Install all dependencies (core + dev + django + websockets)
install:
    uv pip install -e .[dev,django,websockets]

# Install core dependencies only
install-core:
    uv pip install -e .

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

# Run the client-side JavaScript tests (requires Node 21+ for glob support)
test-js:
    node --test "tests/js/**/*.test.mjs"

# Run both Python and JavaScript test suites
test-all: test test-js

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
    uv build

# ─── Docs ───────────────────────────────────────────────────────────────────

# Build API docs with pdoc -> docs/site/
docs-build:
    python docs/make.py

# Start pdoc dev server (live reload at localhost:8000)
docs-serve:
    python docs/make.py --serve

# Verify pdoc is available and print config
docs-check:
    python docs/make.py --check

# Clean generated docs
docs-clean:
    rm -rf docs/site/

# ─── Claude Code ────────────────────────────────────────────────────────────

# Default system prompt file appended to Claude's context (override per-call)
CLAUDE_PROMPT_FILE := "CLAUDE.md"

# Run Claude Code interactively (pass extra args with: just claude -- --flag)
claude *ARGS:
    claude {{ ARGS }}

# Run Claude Code skipping all permission prompts (local/trusted environments only)
claude-unsafe *ARGS:
    claude --dangerously-skip-permissions {{ ARGS }}

# Run Claude Code with an appended system prompt from a file
claude-prompt PROMPT_FILE=CLAUDE_PROMPT_FILE *ARGS:
    claude --append-system-prompt-file {{ PROMPT_FILE }} {{ ARGS }}

# Run Claude Code with system prompt file + skip permissions
claude-unsafe-prompt PROMPT_FILE=CLAUDE_PROMPT_FILE *ARGS:
    claude --dangerously-skip-permissions --append-system-prompt-file {{ PROMPT_FILE }} {{ ARGS }}

# Run Claude Code with full orchestration workflow (multi-agent, model routing, RTK)
claude-orchestrate *ARGS:
    claude --dangerously-skip-permissions --append-system-prompt-file prompts/WORKFLOW.md {{ ARGS }}
