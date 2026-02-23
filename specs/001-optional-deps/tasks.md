---
description: "Task list for 001-optional-deps: Optional Framework Extras & Adapter Discovery"
---

# Tasks: Optional Framework Extras & Adapter Discovery

**Input**: Design documents from `specs/001-optional-deps/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**Tests**: Per **Constitution Principle III (Test-First)**, tests are MANDATORY.
Tests MUST be written and confirmed failing before implementation tasks begin.
A waiver is only valid if the feature specification contains an explicit,
reviewed rationale for why test-first cannot apply — omit test tasks only then.

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are absolute from repository root

## Path Conventions

- Single project: `src/`, `tests/` at repository root

---

## Phase 1: Setup

**Purpose**: Write tests first (Red phase — all must fail before Phase 2 begins).
Per Constitution Principle III, confirm tests fail before proceeding to Phase 2.

- [X] T001 Create `tests/test_optional_extras.py` with extras isolation tests and ImportError
      guard tests covering: (a) base install produces no web-framework imports, (b) importing
      a FastAPI adapter without the extra raises ImportError with correct message containing
      "component-framework[fastapi]", (c) importing a Django adapter without the extra raises
      ImportError with correct message. Use `subprocess` + `sys.executable` to simulate clean
      installs where needed, or mock `importlib` where subprocess is impractical.
      **Confirm all tests FAIL before proceeding.**

- [X] T002 [P] Add `pytest.importorskip("fastapi", reason="Install: pip install component-framework[fastapi]")`
      at module level (before other imports) in each FastAPI adapter test file in `tests/`
      (e.g. `tests/test_fastapi_adapter.py`, `tests/test_fastapi_websocket.py` — check which
      files import fastapi and add the guard to each)

- [X] T003 [P] Add `pytest.importorskip("django", reason="Install: pip install component-framework[django]")`
      at module level in each Django adapter test file that would fail without Django installed
      (check `tests/test_django_*.py`, `tests/test_permissions.py`, `tests/test_ratelimit.py`,
      `tests/test_caching.py`, `tests/test_templatetags.py`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core configuration changes that MUST be complete before any user story
implementation can be verified.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Update `pyproject.toml`: remove `fastapi>=0.109.0`, `uvicorn[standard]>=0.27.0`,
      `jinjax>=0.41` from `[project.dependencies]` (leaving only `pydantic>=2.0`); add
      `[project.optional-dependencies] fastapi = ["fastapi>=0.109.0",
      "uvicorn[standard]>=0.27.0", "jinjax>=0.41"]`; add `dev-base = [pytest, pytest-asyncio,
      pytest-django, httpx, ruff, ty]`; update `dev` to
      `["component-framework[dev-base,fastapi,django,websockets]", "pre-commit>=3.5.0",
      "pdoc>=14.0"]`; add `all = ["component-framework[fastapi,django,websockets]"]`

- [X] T005 Add `_require_extra(package: str, extra: str) -> None` helper to
      `src/component_framework/adapters/__init__.py`. This function MUST raise `ImportError`
      with the message: `"'{package}' is not installed. Install the '{extra}' extra:
      pip install 'component-framework[{extra}]'"`. It MUST NOT swallow the original
      exception — callers are responsible for chaining with `from e`.

**Checkpoint**: After T004 + T005, re-run `just test`. Tests in T001 for ImportError
message format should now PASS. Base-install isolation tests will pass after Phase 3.

---

## Phase 3: User Story 1 — Install Without Web Framework Bloat (Priority: P1) 🎯 MVP

**Goal**: Base and Django installs contain zero FastAPI/JinjaX packages. Importing any
adapter without its extras group installed raises a clear, actionable ImportError.

**Independent Test**: Run `just test` — T001 tests for ImportError message and import
isolation pass. Manually verify with quickstart.md Steps 1 and 4.

### Tests for User Story 1 *(Constitution Principle III — write first, confirm failing)*

Tests written in T001 (Phase 1). Re-confirm T001 tests are still failing before starting
implementation below.

### Implementation for User Story 1

- [X] T006 [P] [US1] Add ImportError guard to `src/component_framework/adapters/fastapi.py`:
      wrap `from fastapi import HTTPException, Request` and `from fastapi.responses import
      JSONResponse` in `try/except ImportError as e:` block; call `_require_extra("fastapi",
      "fastapi")` inside the except; re-raise with `raise ... from e` to preserve chain.

- [X] T007 [P] [US1] Add ImportError guard to `src/component_framework/adapters/fastapi_websocket.py`:
      wrap `from fastapi import WebSocket, WebSocketDisconnect` in try/except; call
      `_require_extra("fastapi", "fastapi")` and re-raise from e.

- [X] T008 [P] [US1] Add ImportError guard to `src/component_framework/adapters/jinjax_renderer.py`:
      wrap `from jinjax import Catalog` in try/except; call `_require_extra("jinjax",
      "fastapi")` (jinjax is part of the fastapi extra) and re-raise from e.

- [X] T009 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_views.py`:
      wrap the django imports block in try/except; call `_require_extra("django", "django")`
      and re-raise from e.

- [X] T010 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_model.py`:
      wrap django imports in try/except; call `_require_extra("django", "django")` and
      re-raise from e.

- [X] T011 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_websocket.py`:
      wrap django/channels imports in try/except; call `_require_extra("django", "django")`
      and re-raise from e.

- [X] T012 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_renderer.py`:
      wrap django imports in try/except; call `_require_extra("django", "django")` and
      re-raise from e.

- [X] T013 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_permissions.py`:
      wrap django imports in try/except; call `_require_extra("django", "django")` and
      re-raise from e.

- [X] T014 [P] [US1] Add ImportError guard to `src/component_framework/adapters/django_ratelimit.py`:
      wrap django imports in try/except; call `_require_extra("django", "django")` and
      re-raise from e.

- [X] T015 [US1] Run `just test` and confirm all T001 extras-isolation and ImportError
      tests pass. Fix any remaining failures before proceeding to Phase 4.

**Checkpoint**: At this point, User Story 1 is fully functional and independently testable.
Run quickstart.md Steps 1 and 4 to verify base install isolation and ImportError UX.

---

## Phase 4: User Story 2 — FastAPI Adopter Upgrades Without Breaking (Priority: P2)

**Goal**: A migration guide exists; CHANGELOG documents the breaking change; CI verifies
each extras group in isolation.

**Independent Test**: Run quickstart.md Steps 2, 3, and 5. Confirm FastAPI extra restores
full adapter behavior (SC-003), Django extra has no FastAPI (SC-002), and migration guide
is self-contained.

### Tests for User Story 2 *(Constitution Principle III — write first, confirm failing)*

No new test files needed — coverage comes from the adapter test files with
`pytest.importorskip` guards added in T002/T003, plus the CI matrix added in T018.
The CI matrix constitutes the "test" for this story: a failing matrix cell = test failure.

### Implementation for User Story 2

- [X] T016 [US2] Create `CHANGELOG.md` at repository root following Keep a Changelog
      format. Add an `[Unreleased]` section with a `### Breaking Changes` subsection
      documenting: "FastAPI, Uvicorn, and JinjaX are no longer installed by default.
      Existing FastAPI users must install the `[fastapi]` extra:
      `pip install 'component-framework[fastapi]'`. CI pipelines installing without extras
      must be updated." Also add `### Added` noting the new `fastapi`, `dev-base`, and
      `all` optional extras groups.

- [X] T017 [US2] Add a "Migrating from 0.2.x" section to `README.md` (place it near
      the top, after the status badge block). Include: (a) the before/after install command
      for FastAPI users, (b) an explicit warning that automated CI pipelines installing
      without extras will break, (c) a table of all extras groups with their purpose, and
      (d) a link to CHANGELOG.md for full details.

- [X] T018 [US2] Update `.github/workflows/ci.yml` test job: add a `strategy.matrix.extras`
      dimension with four variants — `{name: base, install: ".[dev-base]"}`,
      `{name: fastapi, install: ".[fastapi,dev-base]"}`,
      `{name: django, install: ".[django,dev-base]"}`,
      `{name: all, install: ".[dev]"}`. Update the install step to use
      `pip install -e "${{ matrix.extras.install }}"`. Keep the existing Python version
      matrix. The lint job should remain unchanged (uses `.[dev]` which pulls everything
      via self-reference). Add `fail-fast: false` to the test matrix.

**Checkpoint**: At this point, User Stories 1 AND 2 are independently functional.
Run quickstart.md Steps 2, 3, and 5.

---

## Phase 5: User Story 3 — Flask and Litestar Gaps Are Documented (Priority: P3)

**Goal**: A developer searching README for "Flask" or "Litestar" finds current support
status and GitHub issue links within 30 seconds.

**Independent Test**: Run `grep -n "Flask\|Litestar" README.md` — at least 4 matching
lines present (one per framework in the roadmap table, plus issue link references).

### Implementation for User Story 3

- [X] T019 [P] [US3] Create a GitHub issue titled "Add Flask adapter" with body describing:
      required components (Renderer subclass, WSGI endpoint handler, optional flask-sock
      WebSocket handler, `[flask]` optional extra, example in `examples/`), link to
      constitution Adapter Contract section, and reference to Issue #4 as parent.
      Record the new issue number.

- [X] T020 [P] [US3] Create a GitHub issue titled "Add Litestar adapter" with body
      describing: required components (Renderer subclass, ASGI endpoint handler following
      FastAPI adapter pattern, optional WebSocket handler, `[litestar]` optional extra,
      example), link to constitution Adapter Contract, reference to Issue #4. Record the
      new issue number.

- [X] T021 [US3] Add an "Adapter Support" section to `README.md` (after the Features
      section, before Installation). Include a table with columns: Framework | Status |
      Extra | Notes. Rows: FastAPI (Supported, `[fastapi]`, —), Django (Supported,
      `[django]`, —), Flask (Planned, —, link to issue from T019), Litestar (Planned, —,
      link to issue from T020). Update Issue #4 description to link to T019 and T020 issues.

**Checkpoint**: All three user stories independently functional. Run quickstart.md Step 6.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality gate across all stories.

- [X] T022 [P] Bump version in `pyproject.toml` from `0.2.0b0` to `0.3.0b0` (reflects
      minor breaking change per semantic versioning for a pre-1.0 library; update the
      `[Unreleased]` section header in `CHANGELOG.md` to `[0.3.0b0] - 2026-02-23`)

- [X] T023 [P] Run `just check` (ruff format + ruff check + ty check) across all modified
      files and fix any violations. Pay special attention to `adapters/__init__.py`
      (new `_require_extra` function needs type hint on return type: `-> None`) and
      `tests/test_optional_extras.py` (ruff UP/I rules for imports).

- [X] T024 Run complete test suite `just test` — confirm SC-004 (100% pre-change tests
      pass, no test modifications required beyond T002/T003 importorskip additions).

- [X] T025 [P] Run full quickstart.md validation (all 6 steps) in a clean virtual
      environment using `uv venv` to confirm each extras group installs correctly and
      the end-to-end success criteria (SC-001 through SC-007) are met.

- [X] T026 [P] Update version references in `README.md` status badge and any hardcoded
      version strings from `0.2.0-beta` to `0.3.0-beta`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — write tests immediately, confirm they FAIL
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 — guards implement what tests expect
- **User Story 2 (Phase 4)**: Depends on Phase 3 (full test suite must pass first)
- **User Story 3 (Phase 5)**: Independent of Phase 3/4 — only needs Phase 2 complete
  *(can run in parallel with Phase 3 if staffed)*
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 (pyproject.toml + helper) to be complete
- **US2 (P2)**: Requires US1 to be complete (migration guide references the working extras)
- **US3 (P3)**: Requires only Phase 2 — independent of US1 and US2

### Within Each User Story

- T006–T014 [US1] are fully parallel (9 different files, no cross-dependencies)
- T019–T020 [US3] are fully parallel (independent GitHub issues)
- T022–T023, T025–T026 in Polish are fully parallel

### Parallel Opportunities

```bash
# Phase 1 — T002 and T003 can run in parallel:
Task T002: Add importorskip to FastAPI test files
Task T003: Add importorskip to Django test files

# Phase 3 — all 9 guard tasks run in parallel:
Task T006: fastapi.py guard
Task T007: fastapi_websocket.py guard
Task T008: jinjax_renderer.py guard
Task T009: django_views.py guard
Task T010: django_model.py guard
Task T011: django_websocket.py guard
Task T012: django_renderer.py guard
Task T013: django_permissions.py guard
Task T014: django_ratelimit.py guard

# Phase 4 — T016, T017, T018 have soft ordering but can overlap:
Task T016: CHANGELOG.md (no dependencies)
Task T017: README.md migration section (no dependencies on T016)
Task T018: ci.yml matrix (depends on T004 for dev-base extra name)

# Phase 5 — T019 and T020 run in parallel:
Task T019: Flask GitHub issue
Task T020: Litestar GitHub issue
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (write tests, confirm failing)
2. Complete Phase 2: Foundational (pyproject.toml + helper)
3. Complete Phase 3: User Story 1 (9 guard tasks in parallel)
4. **STOP and VALIDATE**: `just test` passes, quickstart.md Steps 1 and 4 pass
5. Users can now install without FastAPI bloat — MVP shipped

### Incremental Delivery

1. Phase 1 + 2 → foundation ready
2. Phase 3 (US1) → base install clean, ImportError guards working → **MVP**
3. Phase 4 (US2) → migration guide + CI matrix → safe for existing users to upgrade
4. Phase 5 (US3) → Flask/Litestar documented → complete roadmap
5. Phase 6 → quality gate, version bump, release

### Parallel Team Strategy

With two developers:
- Dev A: T001 → T004 → T005 → T006–T014 (parallel batch) → T015
- Dev B: T002 → T003 → T016 → T017 → T018 → T019–T020 (parallel) → T021

---

## Notes

- [P] tasks touch different files and have no cross-task data dependencies
- [Story] labels map tasks to spec.md user stories for full traceability
- T006–T014 are the highest-value parallelization opportunity: 9 files, all independent
- The `_require_extra()` helper (T005) MUST be committed before any guard tasks (T006–T014)
  since guards import it — this is a hard sequential dependency
- Verify tests FAIL in Phase 1 before implementing in Phase 2+
- Commit after Phase 3 checkpoint to create a clean rollback point before documentation changes
- Do not modify any files under `src/component_framework/core/` — zero core changes permitted
  per Constitution Principle I
