# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
