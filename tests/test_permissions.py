"""Tests for permission classes and access control decorators."""

import json

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from component_framework.adapters.django_permissions import (
    login_required_component,
    permission_required_component,
    staff_required_component,
)
from component_framework.adapters.django_views import (
    AuthenticatedComponentView,
    ComponentView,
    PermissionComponentView,
    component_view,
)
from component_framework.core import Component, Renderer
from component_framework.core.permissions import (
    AllowAny,
    DjangoModelPermission,
    IsAuthenticated,
    IsStaff,
    IsSuperuser,
)
from component_framework.core.registry import ComponentRegistry

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = Component.renderer
    Component.renderer = MockRenderer()
    yield
    Component.renderer = old


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def fresh_registry(monkeypatch):
    reg = ComponentRegistry()
    monkeypatch.setattr("component_framework.adapters.django_views.registry", reg)
    return reg


@pytest.fixture
def simple_component(fresh_registry):
    @fresh_registry.register("simple")
    class SimpleComponent(Component):
        template_name = "simple.html"

        def mount(self):
            super().mount()
            self.state["ok"] = True

    return SimpleComponent


class _MockUser:
    """Lightweight mock user compatible with Django permission checks."""

    def __init__(self, *, authenticated=True, is_staff=False, is_superuser=False, perms=()):
        self.id = 1
        self.is_authenticated = authenticated
        self.is_staff = is_staff
        self.is_superuser = is_superuser
        self._perms = set(perms)

    def has_perm(self, perm: str) -> bool:
        return perm in self._perms

    def has_perms(self, perms) -> bool:
        return all(p in self._perms for p in perms)


def _make_user(*, authenticated=True, is_staff=False, is_superuser=False, perms=()):
    """Build a lightweight mock user compatible with permission checks."""
    return _MockUser(
        authenticated=authenticated, is_staff=is_staff, is_superuser=is_superuser, perms=perms
    )


def _post(rf, name, *, user=None, data=None):
    """Helper to build a POST request with optional user."""
    body = json.dumps(data or {})
    request = rf.post(f"/components/{name}/", data=body, content_type="application/json")
    if user is not None:
        request.user = user
    return request


# ===========================================================================
# Unit tests: permission classes (no Django views)
# ===========================================================================


class TestBasePermission:
    def test_allow_any_always_true(self):
        perm = AllowAny()
        assert perm.has_permission(None, Component) is True

    def test_allow_any_unauthenticated(self):
        perm = AllowAny()
        user = AnonymousUser()
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is True


class TestIsAuthenticated:
    def test_grants_authenticated(self):
        perm = IsAuthenticated()
        user = _make_user(authenticated=True)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is True

    def test_denies_anonymous(self):
        perm = IsAuthenticated()
        request = type("R", (), {"user": AnonymousUser()})()
        assert perm.has_permission(request, Component) is False

    def test_denies_no_user_attr(self):
        perm = IsAuthenticated()
        request = object()
        assert perm.has_permission(request, Component) is False


class TestIsStaff:
    def test_grants_staff(self):
        perm = IsStaff()
        user = _make_user(authenticated=True, is_staff=True)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is True

    def test_denies_non_staff(self):
        perm = IsStaff()
        user = _make_user(authenticated=True, is_staff=False)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is False

    def test_denies_anonymous(self):
        perm = IsStaff()
        request = type("R", (), {"user": AnonymousUser()})()
        assert perm.has_permission(request, Component) is False


class TestIsSuperuser:
    def test_grants_superuser(self):
        perm = IsSuperuser()
        user = _make_user(authenticated=True, is_superuser=True)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is True

    def test_denies_regular_user(self):
        perm = IsSuperuser()
        user = _make_user(authenticated=True, is_superuser=False)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, Component) is False


class TestDjangoModelPermission:
    def test_grants_when_user_has_perm(self):
        class MyComponent(Component):
            template_name = "t.html"
            permission_required = "myapp.change_thing"

        perm = DjangoModelPermission()
        user = _make_user(authenticated=True, perms={"myapp.change_thing"})
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, MyComponent) is True

    def test_denies_when_user_lacks_perm(self):
        class MyComponent(Component):
            template_name = "t.html"
            permission_required = "myapp.change_thing"

        perm = DjangoModelPermission()
        user = _make_user(authenticated=True, perms=set())
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, MyComponent) is False

    def test_grants_when_permission_required_empty(self):
        class MyComponent(Component):
            template_name = "t.html"

        perm = DjangoModelPermission()
        user = _make_user(authenticated=True)
        request = type("R", (), {"user": user})()
        assert perm.has_permission(request, MyComponent) is True

    def test_list_of_perms_all_required(self):
        class MyComponent(Component):
            template_name = "t.html"
            permission_required = ["myapp.view_thing", "myapp.change_thing"]

        perm = DjangoModelPermission()

        user_all = _make_user(authenticated=True, perms={"myapp.view_thing", "myapp.change_thing"})
        request_all = type("R", (), {"user": user_all})()
        assert perm.has_permission(request_all, MyComponent) is True

        user_partial = _make_user(authenticated=True, perms={"myapp.view_thing"})
        request_partial = type("R", (), {"user": user_partial})()
        assert perm.has_permission(request_partial, MyComponent) is False


# ===========================================================================
# FBV: component_view with component-level permission_classes
# ===========================================================================


class TestFBVComponentPermissions:
    def test_allow_any_permits_anonymous(self, rf, fresh_registry):
        @fresh_registry.register("public")
        class PublicComponent(Component):
            template_name = "pub.html"
            permission_classes = [AllowAny]

            def mount(self):
                super().mount()
                self.state["x"] = 1

        request = _post(rf, "public", user=AnonymousUser())
        response = component_view(request, "public")
        assert response.status_code == 200

    def test_is_authenticated_denies_anonymous(self, rf, fresh_registry):
        @fresh_registry.register("protected")
        class ProtectedComponent(Component):
            template_name = "prot.html"
            permission_classes = [IsAuthenticated]

            def mount(self):
                super().mount()

        request = _post(rf, "protected", user=AnonymousUser())
        response = component_view(request, "protected")
        assert response.status_code == 403
        assert json.loads(response.content)["error"] == "Permission denied"

    def test_is_authenticated_grants_authenticated_user(self, rf, fresh_registry):
        @fresh_registry.register("protected2")
        class ProtectedComponent2(Component):
            template_name = "prot2.html"
            permission_classes = [IsAuthenticated]

            def mount(self):
                super().mount()
                self.state["y"] = 2

        request = _post(rf, "protected2", user=_make_user(authenticated=True))
        response = component_view(request, "protected2")
        assert response.status_code == 200

    def test_is_staff_denies_non_staff(self, rf, fresh_registry):
        @fresh_registry.register("staff_comp")
        class StaffComponent(Component):
            template_name = "staff.html"
            permission_classes = [IsStaff]

            def mount(self):
                super().mount()

        request = _post(rf, "staff_comp", user=_make_user(authenticated=True, is_staff=False))
        response = component_view(request, "staff_comp")
        assert response.status_code == 403

    def test_empty_permission_classes_defaults_to_allow_any(self, rf, simple_component):
        # simple_component has permission_classes = [] (inherited default)
        request = _post(rf, "simple", user=AnonymousUser())
        response = component_view(request, "simple")
        assert response.status_code == 200


# ===========================================================================
# FBV decorators
# ===========================================================================


class TestLoginRequiredComponentDecorator:
    def test_unauthenticated_returns_401(self, rf, simple_component):
        decorated = login_required_component(component_view)
        request = _post(rf, "simple", user=AnonymousUser())
        response = decorated(request, "simple")
        assert response.status_code == 401
        assert json.loads(response.content)["error"] == "Authentication required"

    def test_authenticated_passes_through(self, rf, simple_component):
        decorated = login_required_component(component_view)
        request = _post(rf, "simple", user=_make_user(authenticated=True))
        response = decorated(request, "simple")
        assert response.status_code == 200

    def test_no_user_attr_returns_401(self, rf, simple_component):
        decorated = login_required_component(component_view)
        request = _post(rf, "simple")  # no user set
        response = decorated(request, "simple")
        assert response.status_code == 401


class TestPermissionRequiredComponentDecorator:
    def test_unauthenticated_returns_401(self, rf, simple_component):
        decorated = permission_required_component("myapp.change_thing")(component_view)
        request = _post(rf, "simple", user=AnonymousUser())
        response = decorated(request, "simple")
        assert response.status_code == 401

    def test_missing_perm_returns_403(self, rf, simple_component):
        decorated = permission_required_component("myapp.change_thing")(component_view)
        request = _post(rf, "simple", user=_make_user(authenticated=True, perms=set()))
        response = decorated(request, "simple")
        assert response.status_code == 403
        assert json.loads(response.content)["error"] == "Permission denied"

    def test_has_perm_passes_through(self, rf, simple_component):
        decorated = permission_required_component("myapp.change_thing")(component_view)
        user = _make_user(authenticated=True, perms={"myapp.change_thing"})
        request = _post(rf, "simple", user=user)
        response = decorated(request, "simple")
        assert response.status_code == 200

    def test_list_of_perms_all_required(self, rf, simple_component):
        perms = ["myapp.view_thing", "myapp.change_thing"]
        decorated = permission_required_component(perms)(component_view)
        user_partial = _make_user(authenticated=True, perms={"myapp.view_thing"})
        request = _post(rf, "simple", user=user_partial)
        response = decorated(request, "simple")
        assert response.status_code == 403

        user_full = _make_user(authenticated=True, perms={"myapp.view_thing", "myapp.change_thing"})
        request2 = _post(rf, "simple", user=user_full)
        response2 = decorated(request2, "simple")
        assert response2.status_code == 200


class TestStaffRequiredComponentDecorator:
    def test_unauthenticated_returns_401(self, rf, simple_component):
        decorated = staff_required_component(component_view)
        request = _post(rf, "simple", user=AnonymousUser())
        response = decorated(request, "simple")
        assert response.status_code == 401

    def test_non_staff_returns_403(self, rf, simple_component):
        decorated = staff_required_component(component_view)
        request = _post(rf, "simple", user=_make_user(authenticated=True, is_staff=False))
        response = decorated(request, "simple")
        assert response.status_code == 403
        assert json.loads(response.content)["error"] == "Staff access required"

    def test_staff_passes_through(self, rf, simple_component):
        decorated = staff_required_component(component_view)
        request = _post(rf, "simple", user=_make_user(authenticated=True, is_staff=True))
        response = decorated(request, "simple")
        assert response.status_code == 200


# ===========================================================================
# CBV: AuthenticatedComponentView — JSON 401, not redirect
# ===========================================================================


class TestAuthenticatedComponentView:
    def _dispatch(self, rf, name, user, registry_override):
        import component_framework.adapters.django_views as views_mod

        old = views_mod.registry
        views_mod.registry = registry_override
        try:
            view = AuthenticatedComponentView.as_view()
            request = _post(rf, name, user=user)
            return view(request, name=name)
        finally:
            views_mod.registry = old

    def test_anonymous_returns_json_401(self, rf, fresh_registry, simple_component):
        response = self._dispatch(rf, "simple", AnonymousUser(), fresh_registry)
        assert response.status_code == 401
        data = json.loads(response.content)
        assert data["error"] == "Authentication required"
        # Must be JSON, not a redirect
        assert response["Content-Type"].startswith("application/json")

    def test_authenticated_user_returns_200(self, rf, fresh_registry, simple_component):
        user = _make_user(authenticated=True)
        response = self._dispatch(rf, "simple", user, fresh_registry)
        assert response.status_code == 200


# ===========================================================================
# CBV: PermissionComponentView — JSON 403, not redirect
# ===========================================================================


class TestPermissionComponentView:
    def _dispatch(self, rf, name, user, registry_override, permission_required):
        import component_framework.adapters.django_views as views_mod

        old = views_mod.registry
        views_mod.registry = registry_override
        try:

            class TestPermView(PermissionComponentView):
                pass

            TestPermView.permission_required = permission_required

            view = TestPermView.as_view()
            request = _post(rf, name, user=user)
            return view(request, name=name)
        finally:
            views_mod.registry = old

    def test_no_permission_returns_json_403(self, rf, fresh_registry, simple_component):
        user = _make_user(authenticated=True, perms=set())
        response = self._dispatch(rf, "simple", user, fresh_registry, "myapp.change_thing")
        assert response.status_code == 403
        data = json.loads(response.content)
        assert data["error"] == "Permission denied"
        assert response["Content-Type"].startswith("application/json")

    def test_has_permission_returns_200(self, rf, fresh_registry, simple_component):
        user = _make_user(authenticated=True, perms={"myapp.change_thing"})
        response = self._dispatch(rf, "simple", user, fresh_registry, "myapp.change_thing")
        assert response.status_code == 200


# ===========================================================================
# CBV ComponentView.check_component_permissions
# ===========================================================================


class TestCBVCheckComponentPermissions:
    def test_returns_none_when_allowed(self, rf):
        view = ComponentView()
        request = _post(rf, "any")
        request.user = _make_user(authenticated=True)

        class AnyComp(Component):
            template_name = "t.html"
            permission_classes = [AllowAny]

        result = view.check_component_permissions(request, AnyComp)
        assert result is None

    def test_returns_403_when_denied(self, rf):
        view = ComponentView()
        request = _post(rf, "any")
        request.user = AnonymousUser()

        class ProtComp(Component):
            template_name = "t.html"
            permission_classes = [IsAuthenticated]

        response = view.check_component_permissions(request, ProtComp)
        assert response is not None
        assert response.status_code == 403

    def test_empty_permission_classes_defaults_to_allow_any(self, rf):
        view = ComponentView()
        request = _post(rf, "any")
        request.user = AnonymousUser()

        class DefaultComp(Component):
            template_name = "t.html"
            # permission_classes not set — uses inherited []

        result = view.check_component_permissions(request, DefaultComp)
        assert result is None
