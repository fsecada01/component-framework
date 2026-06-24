# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0b0] - 2026-06-24

### Added

- **Flask adapter** (`[flask]` optional extras group) — adds a `FlaskRenderer`
  (Jinja2-backed; share the app's `jinja_env` for consistent filters, globals,
  and extensions) and a synchronous component endpoint exposed as a Flask
  blueprint (`POST /components/<name>` via `register_component_routes(app)` or
  `create_component_blueprint()`). Parses JSON and HTMX form-encoded bodies and
  returns JSON `404`/`400`/`500` errors. The `[flask]` extra pulls only
  `flask>=3.0` — no FastAPI/Django/JinjaX. See `examples/flask_example.py`.
- **Optimistic UI patching in the client** — `component-client.js` now applies
  an optimistic patch synchronously before the request completes, reading
  `data-optimistic` JSON / `data-optimistic-toggle` from the trigger element and
  rolling back when the server response arrives. Ships an accompanying
  `component-framework.css` with `[data-loading]` / `[data-optimistic]` hooks
  (reduced-motion aware) and updated `component-client.d.ts` typings.
- **Sharing an existing JinjaX catalog** — documented and clarified that
  `JinjaxRenderer` should be constructed with the application's existing
  `Catalog` so component templates inherit host globals and filters, rather than
  a fresh, empty catalog.

### Changed

- `[all]` and `[dev]` extras groups now include the `flask` extra.

## [0.4.1b0] - 2026-06-23

### Fixed

- FastAPI and Litestar adapters now accept form-encoded (HTMX default)
  `POST` bodies in addition to JSON.
- CI: `ty`'s `invalid-method-override` diagnostic is treated as a warning to
  accommodate Django's CBV/consumer signature narrowing.

## [0.4.0b0] - 2026-03-01

### Added

- **Litestar adapter** (`[litestar]` optional extras group) — HTTP, WebSocket,
  and SSE support.
- **Async event handlers** — `async_dispatch()` / `async_handle_event()` for
  adapters running in an async context.
- **SSE streaming** — `StreamingComponent` with async-generator handlers for
  progressive rendering.
- **State size guard** — configurable warning at 64 KB and a hard limit at
  512 KB on serialised component state.

### Fixed

- JS double-serialisation fix in `component-client.js`.

## [0.3.0b0] - 2026-02-23

### Breaking Changes

- **`fastapi`, `uvicorn`, and `jinjax` are no longer installed by default.**
  These packages have been moved from mandatory core dependencies to the optional
  `[fastapi]` extras group. Existing FastAPI users must update their install command:

  ```bash
  # Before (0.2.x)
  pip install component-framework

  # After (0.3.0+)
  pip install "component-framework[fastapi]"
  ```

  **CI pipelines** that install the bare package without specifying an extras group
  will break silently after this upgrade. Update all install commands in CI
  configuration files (GitHub Actions, Dockerfile, tox.ini, Makefile, etc.).

  **Transitive dependents** — downstream projects that relied on `fastapi` or
  `jinjax` being pulled in transitively through this library will also be affected.
  Audit your dependency tree if you see unexpected ImportError messages after upgrading.

### Added

- `[fastapi]` optional extras group — installs `fastapi>=0.109.0`,
  `uvicorn[standard]>=0.27.0`, and `jinjax>=0.41`.
- `[dev-base]` optional extras group — test tooling without adapter extras,
  used by the CI isolation matrix.
- `[all]` convenience extras group — installs all runtime extras
  (`[fastapi,django,websockets]`).
- Actionable `ImportError` messages on all adapter modules — attempting to import
  an adapter without its extras group now raises a clear error naming the missing
  package and the install command needed to resolve it. Example:

  ```
  ImportError: 'fastapi' is not installed.
  Install the 'fastapi' extra: pip install 'component-framework[fastapi]'
  ```

- CI extras isolation matrix — each extras group (`base`, `fastapi`, `django`,
  `all`) is now tested in isolation to prevent cross-adapter contamination.
- `pytest.importorskip` guards on all adapter test modules — adapter tests skip
  cleanly instead of failing with `ImportError` when the relevant extras group is
  not installed.

### Changed

- `[dev]` extras group now self-references all runtime extras via
  `component-framework[dev-base,fastapi,django,websockets]`. Installing `.[dev]`
  continues to provide the full development environment.
- `pydantic>=2.0` is now the only mandatory runtime dependency.

## [0.2.0b0] - 2025-XX-XX

Initial Beta release. See README for full feature list.
