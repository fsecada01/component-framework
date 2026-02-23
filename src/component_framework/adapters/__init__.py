"""Adapter helpers for optional framework extras."""


def _require_extra(package: str, extra: str) -> ImportError:
    """Return an ImportError with an actionable install hint for a missing optional extra.

    Call this inside an ``except ImportError`` block and raise the result with ``from e``
    to preserve the original exception chain::

        try:
            from fastapi import Request
        except ImportError as e:
            from . import _require_extra
            raise _require_extra("fastapi", "fastapi") from e

    Args:
        package: The missing package name (e.g. ``"fastapi"``).
        extra: The extras group that installs it (e.g. ``"fastapi"``).

    Returns:
        ImportError: Always, with an actionable pip install hint.
    """
    return ImportError(
        f"'{package}' is not installed. "
        f"Install the '{extra}' extra: pip install 'component-framework[{extra}]'"
    )
