"""Django rate limiting utilities for component endpoints.

Provides a token-bucket rate limiter backed by Django's cache framework
(falls back to in-memory) plus a CBV mixin and an FBV decorator.

All over-limit responses are JSON (never redirects), making them safe for
HTMX/fetch consumers.
"""

from __future__ import annotations

import functools
import math
import threading
import time
from collections.abc import Callable

try:
    from django.http import HttpRequest, JsonResponse
except ImportError as e:
    from . import _require_extra

    raise _require_extra("django", "django") from e

# ---------------------------------------------------------------------------
# Rate-limit parse helpers
# ---------------------------------------------------------------------------

_PERIOD_SECONDS: dict[str, int] = {
    "sec": 1,
    "second": 1,
    "min": 60,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


def _parse_rate(rate: str) -> tuple[int, int]:
    """Parse a rate string like ``"60/min"`` into ``(limit, period_seconds)``.

    Args:
        rate: A string in the format ``"N/period"`` where period is one of
              ``sec``, ``min``, ``hour``, or ``day``.

    Returns:
        A ``(limit, period_seconds)`` tuple.

    Raises:
        ValueError: If the rate string is malformed or the period is unknown.
    """
    try:
        count_str, period_str = rate.split("/", 1)
        count = int(count_str.strip())
        period = period_str.strip().lower()
        period_secs = _PERIOD_SECONDS.get(period)
        if period_secs is None:
            raise ValueError(f"Unknown period '{period}'. Use: {list(_PERIOD_SECONDS)}")
        return count, period_secs
    except (AttributeError, ValueError) as exc:
        raise ValueError(
            f"Invalid rate '{rate}'. Expected format: 'N/period' (e.g. '60/min')."
        ) from exc


# ---------------------------------------------------------------------------
# In-memory token-bucket implementation (fallback)
# ---------------------------------------------------------------------------


class _BucketState:
    """Internal state for a single token-bucket entry."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self, tokens: float, last_refill: float) -> None:
        self.tokens = tokens
        self.last_refill = last_refill


class RateLimiter:
    """Thread-safe in-memory token bucket rate limiter.

    This implementation is used as a fallback when Django's cache is
    unavailable or raises an exception.  For production use with multiple
    processes, prefer the Django cache backend (``LocMemCache``,
    ``RedisCache``, etc.).

    Args:
        limit: Maximum number of tokens (requests) allowed per period.
        period: Length of the refill period in seconds.
    """

    def __init__(self, limit: int, period: int) -> None:
        self._limit = limit
        self._period = period
        self._buckets: dict[str, _BucketState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check whether *key* is within the rate limit.

        Returns:
            A ``(allowed, retry_after)`` tuple where ``retry_after`` is the
            number of whole seconds until the next token becomes available
            (only meaningful when ``allowed`` is ``False``).
        """
        now = time.monotonic()
        with self._lock:
            state = self._buckets.get(key)
            if state is None:
                state = _BucketState(tokens=float(self._limit), last_refill=now)
                self._buckets[key] = state

            # Refill tokens proportional to elapsed time
            elapsed = now - state.last_refill
            refill = elapsed * (self._limit / self._period)
            state.tokens = min(float(self._limit), state.tokens + refill)
            state.last_refill = now

            if state.tokens >= 1.0:
                state.tokens -= 1.0
                return True, 0
            else:
                # Seconds until the next whole token arrives
                needed = 1.0 - state.tokens
                retry_after = math.ceil(needed * self._period / self._limit)
                return False, retry_after


# ---------------------------------------------------------------------------
# Django-cache-backed bucket helpers
# ---------------------------------------------------------------------------

# Module-level in-memory fallback (one per (limit, period) pair).
_in_memory_limiters: dict[tuple[int, int], RateLimiter] = {}
_in_memory_lock = threading.Lock()


def _get_memory_limiter(limit: int, period: int) -> RateLimiter:
    """Return (or create) the shared in-memory limiter for these parameters."""
    key = (limit, period)
    with _in_memory_lock:
        if key not in _in_memory_limiters:
            _in_memory_limiters[key] = RateLimiter(limit, period)
        return _in_memory_limiters[key]


def _check_rate_cache(cache_key: str, limit: int, period: int) -> tuple[bool, int]:
    """Token-bucket check using Django's cache backend.

    Stores ``(tokens, last_refill)`` in the cache.  Falls back to the
    in-memory ``RateLimiter`` if the cache raises any exception.

    Returns:
        ``(allowed, retry_after)`` — same semantics as ``RateLimiter.is_allowed``.
    """
    try:
        from django.core.cache import cache

        now = time.time()
        bucket_cache_key = f"ratelimit:{cache_key}"
        state = cache.get(bucket_cache_key)

        if state is None:
            tokens: float = float(limit)
            last_refill: float = now
        else:
            tokens, last_refill = state

        # Refill
        elapsed = now - last_refill
        refill = elapsed * (limit / period)
        tokens = min(float(limit), tokens + refill)
        last_refill = now

        if tokens >= 1.0:
            tokens -= 1.0
            cache.set(bucket_cache_key, (tokens, last_refill), timeout=period * 2)
            return True, 0
        else:
            needed = 1.0 - tokens
            retry_after = math.ceil(needed * period / limit)
            cache.set(bucket_cache_key, (tokens, last_refill), timeout=period * 2)
            return False, retry_after

    except Exception:
        # Cache unavailable — fall back to in-memory limiter
        limiter = _get_memory_limiter(limit, period)
        return limiter.is_allowed(cache_key)


# ---------------------------------------------------------------------------
# Key-building helpers
# ---------------------------------------------------------------------------


def _default_key(request: HttpRequest) -> str:
    """Return a cache key based on user ID (auth) or IP address (anon)."""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user:{user.id}"
    # Best-effort IP extraction
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


# ---------------------------------------------------------------------------
# CBV mixin
# ---------------------------------------------------------------------------


class RateLimitMixin:
    """CBV mixin that applies token-bucket rate limiting to POST requests.

    Attributes:
        throttle_rate: Rate in ``"N/period"`` format (default ``"60/min"``).

    Usage::

        class MyComponentView(RateLimitMixin, ComponentView):
            throttle_rate = "30/min"

            def get_throttle_key(self, request):
                # Optional: override to customise the bucket key
                return f"endpoint:{request.path}:{super().get_throttle_key(request)}"
    """

    throttle_rate: str = "60/min"

    def get_throttle_key(self, request: HttpRequest) -> str:
        """Return the cache key used for this request's rate-limit bucket.

        Defaults to ``user:<id>`` for authenticated requests and ``ip:<addr>``
        for anonymous ones.  Override to implement custom partitioning.
        """
        return _default_key(request)

    def check_throttle(self, request: HttpRequest) -> JsonResponse | None:
        """Check whether the current request exceeds the configured rate limit.

        Returns:
            A 429 ``JsonResponse`` with ``{"error": ..., "retry_after": N}``
            if the limit is exceeded, or ``None`` if the request is allowed.
        """
        limit, period = _parse_rate(self.throttle_rate)
        key = self.get_throttle_key(request)
        allowed, retry_after = _check_rate_cache(key, limit, period)
        if not allowed:
            response = JsonResponse(
                {"error": "Rate limit exceeded", "retry_after": retry_after},
                status=429,
            )
            response["Retry-After"] = str(retry_after)
            return response
        return None

    def post(self, request: HttpRequest, *args, **kwargs):
        """Intercept POST to apply throttle check before normal dispatch."""
        throttle_response = self.check_throttle(request)
        if throttle_response is not None:
            return throttle_response
        return super().post(request, *args, **kwargs)  # type: ignore[unresolved-attribute]


# ---------------------------------------------------------------------------
# FBV decorator
# ---------------------------------------------------------------------------


def rate_limit_component(
    rate: str,
    key_func: Callable[[HttpRequest], str] | None = None,
):
    """Decorator factory that rate-limits a component view function.

    Args:
        rate: Allowed request rate in ``"N/period"`` format
              (e.g. ``"60/min"``, ``"100/hour"``).
        key_func: Optional callable ``(request) -> str`` that returns the
                  bucket key.  Defaults to user ID for authenticated requests
                  and client IP for anonymous ones.

    Returns:
        A decorator that wraps the view function.

    Usage::

        @rate_limit_component("30/min")
        def my_view(request, name):
            ...

        # With a custom key:
        @rate_limit_component("30/min", key_func=lambda r: r.session.session_key or "anon")
        def my_view(request, name):
            ...
    """
    limit, period = _parse_rate(rate)
    resolve_key: Callable[[HttpRequest], str] = key_func or _default_key

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            key = resolve_key(request)
            allowed, retry_after = _check_rate_cache(key, limit, period)
            if not allowed:
                response = JsonResponse(
                    {"error": "Rate limit exceeded", "retry_after": retry_after},
                    status=429,
                )
                response["Retry-After"] = str(retry_after)
                return response
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
