# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-07-30

First release published to PyPI. No behavioural change from `0.6.0b0` — the
beta is promoted to a final release so that dependents can require a stable
version. `cf-ui` declares `component-framework>=0.4`, and a specifier without
a pre-release marker only resolves to a pre-release when no final release
exists; relying on that fallback would mean the resolution changed silently
the first time any stable version appeared.

The rest of this entry is what an audit of the built wheel turned up: the
package was installable, but not yet fit to *hand to someone*.

### Added

- Trusted publishing to PyPI via GitHub Actions OIDC on a `v*` tag (#47). No
  API token is stored in the repository. The build job also refuses to hand
  off a wheel missing the client assets or `py.typed` — those ship inside the
  package with no explicit include, so a packaging regression would produce a
  wheel that installs and imports cleanly and then serves no interactivity.
- **`py.typed` (#49).** The codebase is type-checked in CI and ships
  `component-client.d.ts` for the JS, but without the PEP 561 marker every
  Python consumer running mypy or pyright saw the whole package as untyped.
  The types existed; they were not advertised.
- **A `testing` extra (#49)** declaring pytest.
  `component_framework.testing` imports pytest at module scope — it ships
  fixtures and a pytest-style base class — but pytest was only reachable via
  `dev-base`, so following the README's testing sample after
  `pip install component-framework[fastapi]` raised `ModuleNotFoundError`.
- **Classifiers** for the license (which is what PyPI's sidebar reads), the
  frameworks the adapters target, and `Typing :: Typed`.

### Fixed — documentation that did not survive contact with the package (#49)

Found by building the wheel, installing it into a clean venv, and checking
every documented import against the *installed* package rather than the
source tree.

- **The README described an install nobody could perform.** Every instruction
  was `pip install -e ".[extra]"` — an editable install from a checkout — and
  the section opened with "Not on PyPI yet". The README *is* the PyPI landing
  page, so the one line a visitor arriving there needed was the one that was
  missing. It now leads with `pip install "component-framework[fastapi]"`,
  documents the quoting (bare brackets are glob syntax in zsh), shows the
  missing-extra `ImportError` a reader will actually meet, and demotes the
  editable install to a contributor note.
- **The README's composition example was invented.** It imported
  `SlotComponent` and `CompositeComponent` from `core.composition`, which
  exports neither, and set a `components = {...}` attribute nothing reads.
  The real API is a `Component` with a `slots` ClassVar, assembled with
  `compose()`.
- **The README's testing example used methods that do not exist**
  (`mount_component`, `dispatch_event`, and `assert_state` with a positional
  component argument), and omitted the required `component_class`.
- **`docs/LOCKED_FIELDS.md`** imported `Component` and `registry` from the
  top-level package, which exports only `CorruptStateError` and
  `StateSigner`.
- **`docs/CBV_GUIDE.md`** imported `RateLimitMixin` from
  `adapters.django_views`; it lives in `adapters.django_ratelimit`, as the
  README said all along.
- **Two `docs/examples/ecommerce.md` samples did not parse** — a bare `...`
  inside a list literal, and a method whose body was only a comment.

### Added — a test that reads the docs (#49)

`tests/test_docs_samples.py` parses every fenced `python` block in the
README, CONTRIBUTING, and `docs/`, and resolves every
`from component_framework… import …` against the real package. Nothing here
read the documentation before, which is why all six defects above shipped;
the guard goes red on every one of them when run against the previous text.
It also fails if the README ever again claims the package is not on PyPI.
Ported from cf-ui's `test_docs_samples.py`, which exists because
`ComponentCatalog` and `<CfCard>` sat in *that* README for two releases.

## [0.6.0b0] - 2026-07-20

### Added

- **Idiomorph-based DOM morphing (Epic B, B1 — #22)** —
  `component-client.js`'s `update()`/`rollback()` now reconcile the DOM via
  `Idiomorph.morph()` (v0.7.4, vendored unmodified at
  `static/component_framework/js/vendor/idiomorph.js`) instead of a full
  `innerHTML`/`outerHTML` replace. Nodes unaffected by a patch keep their
  identity — including already-bound event listeners — which is what makes
  the focus/scroll/input preservation and list-reconciliation-key features
  below possible.
- **Focus / scroll / in-flight input preservation across patches (Epic B,
  B2 — #22)** — `update()`/`rollback()` pass `ignoreActiveValue: true` to
  `Idiomorph.morph()` so a focused input's in-progress keystrokes survive a
  server patch (focus itself already survives via idiomorph's own
  `restoreFocus` default). Scroll position — which idiomorph has no concept
  of at all — is preserved via new `_captureScrollPositions()`/
  `_restoreScrollPositions()` bookkeeping around every morph call.
- **Stable list reconciliation key (Epic B, B3 — #22)** — template authors
  can mark reorderable list items with `data-key="<id>"` (e.g. `<li
  data-key="42">`). `component-client.js` bridges this onto a synthesized
  `id="cf-key-<id>"` (on both the live DOM and the incoming server render)
  immediately before every `Idiomorph.morph()` call, so idiomorph's
  id-based node matching reconciles reordered items by identity — preserving
  focus, scroll position, in-flight input, and running CSS animations within
  each item — instead of misattributing patches by position. See
  `docs/LIST_RECONCILIATION_KEY.md`.
- **`data-no-morph` escape hatch for JS-owned regions (Epic B, B4 — #22)** —
  component authors can mark any element `data-no-morph` to keep idiomorph
  from ever touching it (or its descendants) during a patch — for
  third-party widgets, manually-mounted JS library instances, canvases, and
  similar regions a component doesn't own. Implemented via
  `beforeNodeMorphed`/`beforeNodeRemoved` callbacks in the shared
  `Idiomorph.morph()` config; the element also survives being dropped
  outright if the server's HTML no longer renders a node at that position.
  See `docs/CLIENT_MORPHING.md`.
- **Litestar htmx content negotiation (#39, #42)** —
  `component_endpoint`/`stream_component_endpoint` now detect the
  `HX-Request` header and return the rendered HTML fragment directly
  instead of the JSON envelope, so plain htmx (`hx-post`/`hx-swap`, and
  the SSE extension) can drive components without `component-client.js`.
  The JSON envelope remains the default for backward compatibility.
- **`Component.resolve()` / `async_resolve()` state-only dispatch path
  (#40, #41)** — returns `dehydrate()`'s state dict without paying for a
  `render()`, for callers that only need resolved state to drive further
  server-side work (e.g. a DB re-query keyed on a new filter/page value).
  `dispatch()`/`async_dispatch()` behavior is unchanged.

### Fixed

- `docs/site-pages/litestar-guide.html` referenced a nonexistent
  `Jinja2Renderer` instead of the real `JinjaxRenderer(catalog)` API; also
  added `jinjax` to the `litestar` extras group so it's actually
  importable for Litestar consumers.

## [0.5.1b0] - 2026-07-01

### Added

- **HMAC-signed client state (Epic A, A1 — #21)** — new stdlib-only
  `core/signing.py` with `StateSigner` (HMAC-SHA256, versioned
  `cfs1.<payload>.<mac>` token format) and `CorruptStateError`. Enable via
  `StateSigner.configure(secret)` or the `STATE_SIGNING_KEY` environment
  variable; comma-separated / sequence values enable key rotation (first key
  signs, all keys verify). When enabled, all outbound state is signed and
  inbound state must be a valid token — tampered, unsigned, or raw-dict state
  is rejected with HTTP 400. When disabled, legacy plain-JSON behavior is
  preserved and a one-time warning is logged. See `docs/STATE_SIGNING.md`.
- **Locked server-trusted state fields (Epic A, A3 — #21)** — components can
  declare `locked_fields: ClassVar[frozenset[str]]` for top-level state keys
  the client must never influence (roles, user IDs, pricing). Locked fields
  are excluded from `dehydrate()` (they never round-trip through the client)
  and stripped in place from inbound state in `hydrate()` with a warning.
  Enforcement lives in the core lifecycle, so all adapters are covered
  without changes. Defaults to empty — existing components are unaffected.
  See `docs/LOCKED_FIELDS.md`.

### Security

- Closed the **dict bypass**: all adapters (FastAPI, Flask, Litestar, Django
  FBV/CBV, WebSocket) now route inbound state through
  `StateSerializer.load_untrusted()`, so a client can no longer submit state
  as a raw JSON object to skip deserialization/verification.
- Django `ComponentView.handle_error()` now maps client input errors
  (`ValueError`, including corrupt state) to `400` instead of `500`.
- Locked fields close the **replay/rollback gap** left by A1: even a
  validly-signed but stale state blob (or any state in signing-disabled
  deployments) can no longer roll back server-owned fields — inbound locked
  values are ignored and the server re-derives them each request.

### Documentation

- **CSRF/CSWSH coverage audit (Epic A, A4 — #21)** — new
  `docs/SECURITY_CSRF.md`: per-adapter CSRF enforcement table (Django-only
  today; FastAPI/Litestar/Flask require host-level integration), the
  form-encoded no-preflight CSRF vector, Cross-Site WebSocket Hijacking
  guidance for all WS adapters, and prioritized follow-up work.
- `docs/STATE_SIGNING.md` (A2) — per-adapter `STATE_SIGNING_KEY` setup and
  key-rotation procedure.
- `docs/LOCKED_FIELDS.md` (A3) — threat model and usage for server-trusted
  fields.

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
