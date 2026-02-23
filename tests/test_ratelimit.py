"""Tests for the django_ratelimit module."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("django", reason="Install: pip install component-framework[django]")

from django.test import RequestFactory

from component_framework.adapters.django_ratelimit import (
    RateLimiter,
    RateLimitMixin,
    _parse_rate,
    rate_limit_component,
)

# ---------------------------------------------------------------------------
# Shared helpers (mirror pattern from test_permissions.py)
# ---------------------------------------------------------------------------


class _MockUser:
    """Lightweight mock user compatible with Django auth checks."""

    def __init__(self, *, authenticated: bool = True, user_id: int = 1) -> None:
        self.id = user_id
        self.is_authenticated = authenticated

    def has_perm(self, perm: str) -> bool:
        return False

    def has_perms(self, perms) -> bool:
        return False


@pytest.fixture
def rf():
    return RequestFactory()


def _make_auth_request(rf: RequestFactory, user_id: int = 1) -> object:
    """Return a POST request with an authenticated user."""
    request = rf.post("/components/test/", data="{}", content_type="application/json")
    request.user = _MockUser(authenticated=True, user_id=user_id)
    return request


def _make_anon_request(rf: RequestFactory, ip: str = "1.2.3.4") -> object:
    """Return a POST request with an anonymous user and a given IP."""
    request = rf.post(
        "/components/test/",
        data="{}",
        content_type="application/json",
        REMOTE_ADDR=ip,
    )

    class _AnonUser:
        is_authenticated = False
        id = None

    request.user = _AnonUser()
    return request


# ---------------------------------------------------------------------------
# Unit tests: _parse_rate
# ---------------------------------------------------------------------------


class TestParseRate:
    def test_per_min(self):
        limit, period = _parse_rate("60/min")
        assert limit == 60
        assert period == 60

    def test_per_sec(self):
        limit, period = _parse_rate("10/sec")
        assert limit == 10
        assert period == 1

    def test_per_hour(self):
        limit, period = _parse_rate("1000/hour")
        assert limit == 1000
        assert period == 3600

    def test_per_day(self):
        limit, period = _parse_rate("5000/day")
        assert limit == 5000
        assert period == 86400

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_rate("bad")

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            _parse_rate("10/week")


# ---------------------------------------------------------------------------
# Unit tests: RateLimiter (in-memory)
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_first_requests_pass(self):
        limiter = RateLimiter(limit=3, period=60)
        for _ in range(3):
            allowed, _ = limiter.is_allowed("key1")
            assert allowed is True

    def test_exceeding_limit_blocked(self):
        limiter = RateLimiter(limit=3, period=60)
        for _ in range(3):
            limiter.is_allowed("key2")
        allowed, retry_after = limiter.is_allowed("key2")
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_are_independent(self):
        limiter = RateLimiter(limit=1, period=60)
        allowed_a, _ = limiter.is_allowed("keyA")
        assert allowed_a is True
        blocked_a, _ = limiter.is_allowed("keyA")
        assert blocked_a is False

        # keyB is still fresh
        allowed_b, _ = limiter.is_allowed("keyB")
        assert allowed_b is True

    def test_retry_after_is_positive_integer(self):
        limiter = RateLimiter(limit=1, period=60)
        limiter.is_allowed("key3")
        allowed, retry_after = limiter.is_allowed("key3")
        assert allowed is False
        assert isinstance(retry_after, int)
        assert retry_after >= 1


# ---------------------------------------------------------------------------
# FBV decorator tests
# ---------------------------------------------------------------------------


def _simple_view(request, *args, **kwargs):
    """Trivial view that always succeeds."""
    return type("FakeResponse", (), {"status_code": 200})()


class TestRateLimitDecoratorPass:
    def test_first_n_requests_pass(self, rf):
        decorated = rate_limit_component("3/min")(_simple_view)
        request = _make_auth_request(rf, user_id=10)
        for _ in range(3):
            response = decorated(request)
            assert response.status_code == 200

    def test_n_plus_one_returns_429(self, rf):
        decorated = rate_limit_component("3/min")(_simple_view)
        request = _make_auth_request(rf, user_id=11)
        for _ in range(3):
            decorated(request)
        response = decorated(request)
        assert response.status_code == 429

    def test_429_body_contains_retry_after(self, rf):
        decorated = rate_limit_component("1/min")(_simple_view)
        request = _make_auth_request(rf, user_id=12)
        decorated(request)  # consume the one token
        response = decorated(request)
        assert response.status_code == 429
        data = json.loads(response.content)
        assert "retry_after" in data
        assert data["retry_after"] > 0
        assert data["error"] == "Rate limit exceeded"

    def test_retry_after_header_present(self, rf):
        decorated = rate_limit_component("1/min")(_simple_view)
        request = _make_auth_request(rf, user_id=13)
        decorated(request)
        response = decorated(request)
        assert response.status_code == 429
        assert "Retry-After" in response
        assert int(response["Retry-After"]) > 0


class TestRateLimitDecoratorKeys:
    def test_unauthenticated_uses_ip_key(self, rf):
        """Anonymous requests from the same IP share a bucket."""
        decorated = rate_limit_component("2/min")(_simple_view)
        r1 = _make_anon_request(rf, ip="9.9.9.1")
        r2 = _make_anon_request(rf, ip="9.9.9.1")

        decorated(r1)
        decorated(r2)
        # Third request from same IP should be blocked
        r3 = _make_anon_request(rf, ip="9.9.9.1")
        response = decorated(r3)
        assert response.status_code == 429

    def test_authenticated_uses_user_id_key(self, rf):
        """Two different authenticated users have independent buckets."""
        decorated = rate_limit_component("1/min")(_simple_view)

        req_user_20 = _make_auth_request(rf, user_id=20)
        req_user_21 = _make_auth_request(rf, user_id=21)

        # Use up user 20's token
        decorated(req_user_20)
        blocked = decorated(req_user_20)
        assert blocked.status_code == 429

        # user 21 still has a fresh bucket
        allowed = decorated(req_user_21)
        assert allowed.status_code == 200

    def test_custom_key_func(self, rf):
        """Custom key_func overrides the default key derivation."""
        always_same_key = lambda req: "shared_bucket"  # noqa: E731
        decorated = rate_limit_component("1/min", key_func=always_same_key)(_simple_view)

        req_a = _make_auth_request(rf, user_id=30)
        req_b = _make_auth_request(rf, user_id=31)

        decorated(req_a)  # consumes the shared token
        response = decorated(req_b)  # different user, same key — blocked
        assert response.status_code == 429

    def test_different_ips_independent(self, rf):
        """Different anonymous IPs are independent rate limit buckets."""
        decorated = rate_limit_component("1/min")(_simple_view)
        req_ip_a = _make_anon_request(rf, ip="10.0.0.1")
        req_ip_b = _make_anon_request(rf, ip="10.0.0.2")

        decorated(req_ip_a)  # use up ip_a's bucket
        blocked = decorated(req_ip_a)
        assert blocked.status_code == 429

        allowed = decorated(req_ip_b)
        assert allowed.status_code == 200


# ---------------------------------------------------------------------------
# CBV RateLimitMixin tests
# ---------------------------------------------------------------------------


class _MockComponentView:
    """Minimal stand-in for ComponentView that records calls."""

    post_called: bool = False

    def post(self, request, *args, **kwargs):
        _MockComponentView.post_called = True
        return type("FakeResponse", (), {"status_code": 200})()


class _ThrottledView(RateLimitMixin, _MockComponentView):
    throttle_rate = "3/min"


class TestRateLimitMixin:
    def setup_method(self):
        _MockComponentView.post_called = False

    def test_first_n_requests_pass(self, rf):
        request = _make_auth_request(rf, user_id=40)
        view = _ThrottledView()
        for _ in range(3):
            response = view.post(request)
            assert response.status_code == 200

    def test_n_plus_one_returns_429(self, rf):
        request = _make_auth_request(rf, user_id=41)
        view = _ThrottledView()
        for _ in range(3):
            view.post(request)
        response = view.post(request)
        assert response.status_code == 429

    def test_429_body_structure(self, rf):
        request = _make_auth_request(rf, user_id=42)
        view = _ThrottledView()
        view.post(request)
        view.post(request)
        view.post(request)
        response = view.post(request)
        data = json.loads(response.content)
        assert data["error"] == "Rate limit exceeded"
        assert isinstance(data["retry_after"], int)
        assert data["retry_after"] > 0

    def test_retry_after_header(self, rf):
        class _TightView(RateLimitMixin, _MockComponentView):
            throttle_rate = "1/min"

        request = _make_auth_request(rf, user_id=43)
        view = _TightView()
        view.post(request)
        response = view.post(request)
        assert response.status_code == 429
        assert "Retry-After" in response
        assert int(response["Retry-After"]) > 0

    def test_custom_throttle_key(self, rf):
        """get_throttle_key override changes the bucket used."""

        class _CustomKeyView(RateLimitMixin, _MockComponentView):
            throttle_rate = "1/min"

            def get_throttle_key(self, request):
                # Use a constant key so every user shares the same bucket
                return "global_bucket_for_custom_key_test"

        view = _CustomKeyView()
        req_a = _make_auth_request(rf, user_id=50)
        req_b = _make_auth_request(rf, user_id=51)

        view.post(req_a)  # consume the single global token
        response = view.post(req_b)  # different user, same custom key — blocked
        assert response.status_code == 429

    def test_different_users_independent_buckets(self, rf):
        """Two different authenticated users don't share buckets."""

        class _TightView(RateLimitMixin, _MockComponentView):
            throttle_rate = "1/min"

        view = _TightView()
        req_user_60 = _make_auth_request(rf, user_id=60)
        req_user_61 = _make_auth_request(rf, user_id=61)

        view.post(req_user_60)
        blocked = view.post(req_user_60)
        assert blocked.status_code == 429

        # User 61 has an independent bucket
        allowed = view.post(req_user_61)
        assert allowed.status_code == 200

    def test_super_post_called_when_allowed(self, rf):
        """When under the limit, the parent view's post() is called."""
        request = _make_auth_request(rf, user_id=70)
        view = _ThrottledView()
        _MockComponentView.post_called = False
        view.post(request)
        assert _MockComponentView.post_called is True

    def test_super_post_not_called_when_blocked(self, rf):
        """When over the limit, the parent view's post() is NOT called."""

        class _TightView(RateLimitMixin, _MockComponentView):
            throttle_rate = "1/min"

        request = _make_auth_request(rf, user_id=71)
        view = _TightView()
        _MockComponentView.post_called = False
        view.post(request)  # allowed — sets post_called = True
        _MockComponentView.post_called = False
        view.post(request)  # blocked — must NOT call super
        assert _MockComponentView.post_called is False
