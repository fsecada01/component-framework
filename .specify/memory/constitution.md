<!--
SYNC IMPACT REPORT
==================
Version change: n/a → 1.0.0 (initial ratification — first fill of template)

Modified principles: n/a (all new)

Added sections:
  - I. Framework Independence
  - II. Component Lifecycle Discipline
  - III. Test-First Development
  - IV. Minimal Footprint / YAGNI
  - V. Security by Default
  - Development Standards
  - Adapter Contract
  - Governance

Removed sections: n/a

Template propagation:
  ✅ .specify/templates/tasks-template.md — updated "Tests are OPTIONAL" note
     to reflect Principle III (test-first is mandatory; waiver requires explicit
     documented rationale in the feature spec)
  ✅ .specify/templates/plan-template.md — Constitution Check stub updated to
     enumerate the five principle gates explicitly
  ✅ .specify/templates/spec-template.md — no structural changes required;
     existing mandatory sections already align with constitution requirements

Follow-up TODOs:
  - TODO(RATIFICATION_DATE): Using 2026-02-22 (first session this constitution
    was authored). Confirm this is acceptable or update to formal project date.
-->

# Component Framework Constitution

## Core Principles

### I. Framework Independence

The `component_framework/core/` package MUST NOT import from any web framework
(`fastapi`, `django`, `flask`, `litestar`, `jinjax`, `uvicorn`, or any adapter
module). All framework-specific code belongs exclusively in `adapters/`.

Every web framework adapter MUST be declared as an optional extras group in
`pyproject.toml`. The only mandatory runtime dependency is `pydantic`. No user
who installs the base package should receive framework code they did not
explicitly request.

No adapter module MAY import from another adapter module.

**Rationale**: A Django developer must not receive FastAPI as a transitive
dependency, and vice versa. Strict layering keeps the core independently
testable, auditable, and portable to frameworks not yet written.

### II. Component Lifecycle Discipline

All components MUST:
- Extend the `Component` base class.
- Be registered via `@registry.register("name")`.
- Manage state exclusively through `self.state` (a JSON-serializable `dict`).
- Follow the canonical lifecycle: `mount → hydrate → handle_event → render → dehydrate`.
- Name event handlers with the `on_<event>` convention.

Components MUST NOT contain domain logic. Business rules belong in models and
service classes; components are thin orchestration shells.

**Rationale**: Consistent lifecycle ordering guarantees predictable state
transitions across frameworks and prevents subtle rendering or state-corruption
bugs caused by out-of-order hook execution.

### III. Test-First Development (NON-NEGOTIABLE)

Tests MUST be written and confirmed to fail before implementation begins.
The Red-Green-Refactor cycle is mandatory.

Components MUST be testable as pure Python — no live HTTP server, no real
renderer, no database — using mock renderers and `ComponentTestCase`.

The full test suite (`just test`) MUST pass before any PR is merged. No
exceptions without a documented, reviewed waiver in the PR description.

**Rationale**: Pure-Python testability is a direct consequence of Principle I.
Enforcing it as a hard gate ensures the lifecycle interface and adapter
boundaries remain clean and that regressions are caught immediately.

### IV. Minimal Footprint / YAGNI

New features MUST follow this layering order:
`core/` → `adapters/` → `examples/` → `docs/` → `tests/`

No abstraction layer, helper utility, or shared module may be introduced
without at least two concrete, present use-cases in the codebase. The default
answer to "should we add this?" is **no** until a second real need appears.

Complexity deviating from this principle MUST be explicitly justified in a
"Complexity Tracking" table in the feature's `plan.md`.

**Rationale**: The library is embedded in downstream stacks. Every byte of
unnecessary complexity compounds across every project that depends on it.

### V. Security by Default

The following controls are NON-NEGOTIABLE:

- **CSRF**: All state-mutating endpoints MUST be CSRF-protected at the adapter
  layer. WebSocket connections require manual token validation (noted as a
  known limitation until automated).
- **Input validation**: ALL user input MUST pass through a Pydantic schema
  before touching component state. Raw request data MUST NOT be placed into
  `self.state` directly.
- **Client state**: State received from the client MUST be treated as
  untrusted. Re-validate on the server before acting.
- **Permissions**: Every mutable endpoint MUST apply a permission check via
  `permission_classes` (CBV) or an FBV decorator. Unauthenticated access MUST
  return JSON 401/403 — never a redirect.
- **Output escaping**: The renderer MUST escape output by default. Components
  MUST NOT produce raw HTML strings that bypass the renderer.
- **Rate limiting**: Production deployments SHOULD apply `RateLimitMixin` to
  components that trigger side effects.

**Rationale**: Components manage server-side state shared across requests. A
compromised component can affect all users sharing that process, making
defense-in-depth a hard requirement rather than a best-effort concern.

## Development Standards

These rules apply to all code in this repository regardless of feature or
adapter:

- **Formatter**: `ruff format` — line length 100, `quote-style = "double"`
- **Linter**: `ruff check` — rule sets E, F, I, N, W, UP; no ignores without
  an inline comment explaining the rationale
- **Type checker**: `ty` — public APIs MUST carry type hints; `ty` warnings
  are treated as errors in CI
- **Docstrings**: REQUIRED for all public classes and public methods; OPTIONAL
  for private helpers
- **Pre-commit gate**: `just check` (ruff + ty) MUST pass; enforced by
  pre-commit hooks via `prek`
- **Commit discipline**: Each commit SHOULD represent one logical unit of work
  and pass `just check` independently

## Adapter Contract

A conforming adapter MUST provide:

1. A `Renderer` subclass in `adapters/<framework>.py` implementing the
   `Renderer` interface from `core/renderer.py`
2. An HTTP endpoint handler that dispatches events to the component registry
3. (Optional) A WebSocket handler following the same event protocol as the
   HTTP handler
4. An optional extras group in `pyproject.toml`
   (e.g., `[project.optional-dependencies] flask = [...]`)
5. At least one working example in `examples/`
6. pdoc-compatible docstrings on all public symbols

No adapter MAY import from another adapter's module.

## Governance

This constitution supersedes all informal practices, README guidance, and
prior conventions. Any amendment requires:

1. A GitHub issue describing the proposed change and its rationale, opened
   before implementation begins.
2. A version bump following semantic versioning:
   - **MAJOR**: Backward-incompatible governance change, principle removal, or
     redefinition that breaks existing compliant code.
   - **MINOR**: New principle or section added; materially expanded guidance.
   - **PATCH**: Clarifications, wording improvements, typo fixes, or
     non-semantic refinements.
3. Updates to all dependent templates in `.specify/templates/` included in the
   same PR as the constitution change.
4. A compliance review verifying no existing test, example, or core module
   violates the amended principles.

All feature plans MUST include a Constitution Check section confirming
compliance with Principles I–V before Phase 0 research begins, and again after
Phase 1 design.

**Version**: 1.0.0 | **Ratified**: 2026-02-22 | **Last Amended**: 2026-02-22
