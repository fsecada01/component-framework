"""Tests for optional extras dependency isolation and ImportError guards.

Constitution Principle III: These tests are written first and must FAIL
before pyproject.toml and adapter guards are implemented.

Tests verify:
  (a) _require_extra() raises ImportError with the correct message format
  (b) FastAPI adapter modules raise actionable ImportError when fastapi is absent
  (c) Django adapter modules raise actionable ImportError when django is absent
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block_import(blocked_name: str, real_modules: dict[str, ModuleType | None]):
    """
    Context manager that makes `import <blocked_name>` raise ImportError
    by temporarily setting sys.modules[blocked_name] = None.

    Also removes any already-imported descendant modules so re-import is forced.
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        to_remove = [
            k for k in sys.modules if k == blocked_name or k.startswith(f"{blocked_name}.")
        ]
        saved = {k: sys.modules.pop(k) for k in to_remove}
        sys.modules[blocked_name] = None  # type: ignore[assignment]
        try:
            yield
        finally:
            del sys.modules[blocked_name]
            sys.modules.update(saved)

    return _ctx()


def _reload_adapter(module_path: str, blocked_package: str):
    """
    Temporarily remove the adapter module from sys.modules, block `blocked_package`,
    attempt re-import (expected to fail with ImportError), then restore the ORIGINAL
    module objects so subsequent tests see consistent module references.

    Restoring the originals (not re-importing) matters because test modules hold
    class references bound to the original module's globals at collection time.
    A fresh import would create new module objects, breaking monkeypatch and
    module-attribute patching done by other fixtures.
    """
    # Save original adapter module(s) before evicting them
    saved = {
        k: v for k, v in sys.modules.items() if k == module_path or k.startswith(f"{module_path}.")
    }

    # Evict so the import machinery re-executes the module body
    for key in saved:
        del sys.modules[key]

    with _block_import(blocked_package, {}):
        with pytest.raises(ImportError) as exc_info:
            importlib.import_module(module_path)

    # Clean up any partial state left by the failed import, then restore originals
    for key in list(sys.modules):
        if key == module_path or key.startswith(f"{module_path}."):
            del sys.modules[key]
    sys.modules.update(saved)

    return exc_info.value


# ---------------------------------------------------------------------------
# T001a — _require_extra() helper
# ---------------------------------------------------------------------------


class TestRequireExtra:
    """Tests for the _require_extra helper in adapters/__init__.py."""

    def test_raises_import_error(self):
        from component_framework.adapters import _require_extra

        err = _require_extra("somepkg", "someextra")
        assert isinstance(err, ImportError)

    def test_message_contains_package_name(self):
        from component_framework.adapters import _require_extra

        err = _require_extra("somepkg", "someextra")
        assert "somepkg" in str(err)

    def test_message_contains_extra_name(self):
        from component_framework.adapters import _require_extra

        err = _require_extra("somepkg", "someextra")
        assert "someextra" in str(err)

    def test_message_contains_install_command(self):
        from component_framework.adapters import _require_extra

        err = _require_extra("somepkg", "someextra")
        assert "component-framework[someextra]" in str(err)


# ---------------------------------------------------------------------------
# T001b — FastAPI adapter ImportError guards
# ---------------------------------------------------------------------------


class TestFastapiAdapterGuard:
    """Verify adapters/fastapi.py raises actionable ImportError when fastapi absent."""

    def test_fastapi_adapter_raises_on_missing_fastapi(self):
        err = _reload_adapter("component_framework.adapters.fastapi", "fastapi")
        assert "fastapi" in str(err).lower()
        assert "component-framework[fastapi]" in str(err)

    def test_fastapi_websocket_raises_on_missing_fastapi(self):
        err = _reload_adapter("component_framework.adapters.fastapi_websocket", "fastapi")
        assert "fastapi" in str(err).lower()
        assert "component-framework[fastapi]" in str(err)

    def test_jinjax_renderer_raises_on_missing_jinjax(self):
        err = _reload_adapter("component_framework.adapters.jinjax_renderer", "jinjax")
        assert "component-framework[fastapi]" in str(err)


# ---------------------------------------------------------------------------
# T001d — Flask adapter ImportError guard
# ---------------------------------------------------------------------------


class TestFlaskAdapterGuard:
    """Verify adapters/flask.py raises an actionable ImportError when flask absent."""

    def test_flask_adapter_raises_on_missing_flask(self):
        err = _reload_adapter("component_framework.adapters.flask", "flask")
        assert "flask" in str(err).lower()
        assert "component-framework[flask]" in str(err)


# ---------------------------------------------------------------------------
# T001c — Django adapter ImportError guards
# ---------------------------------------------------------------------------


class TestDjangoAdapterGuard:
    """Verify django adapter modules raise actionable ImportError when django absent."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "component_framework.adapters.django_views",
            "component_framework.adapters.django_model",
            "component_framework.adapters.django_renderer",
            "component_framework.adapters.django_permissions",
            "component_framework.adapters.django_ratelimit",
        ],
    )
    def test_django_adapter_raises_on_missing_django(self, module_path: str):
        err = _reload_adapter(module_path, "django")
        assert "django" in str(err).lower()
        assert "component-framework[django]" in str(err)

    def test_django_websocket_raises_on_missing_channels(self):
        # django_websocket.py imports from channels, not django directly
        err = _reload_adapter("component_framework.adapters.django_websocket", "channels")
        assert "component-framework[django]" in str(err)
