"""Django FBV decorators for component access control.

These decorators always return JSON responses (401/403), never redirects,
making them safe for HTMX/fetch consumers.
"""

import functools

try:
    from django.http import HttpRequest, JsonResponse
except ImportError as e:
    from . import _require_extra

    raise _require_extra("django", "django") from e


def login_required_component(view_func):
    """
    Decorator that requires the user to be authenticated.

    Returns a JSON 401 response (never a redirect) for unauthenticated requests.

    Usage::

        from component_framework.adapters.django_permissions import login_required_component

        urlpatterns = [
            path("components/<str:name>/", login_required_component(component_view)),
        ]
    """

    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapper


def permission_required_component(perm: str | list[str]):
    """
    Decorator factory that requires the user to hold specific Django permissions.

    Returns a JSON 403 response (never a redirect) if permission is denied.

    Args:
        perm: A permission string (e.g. ``"myapp.change_model"``) or list of
              permission strings. When a list is given, the user must hold *all*
              permissions.

    Usage::

        from component_framework.adapters.django_permissions import permission_required_component

        urlpatterns = [
            path(
                "components/<str:name>/",
                permission_required_component("myapp.change_model")(component_view),
            ),
        ]
    """
    perms: list[str] = [perm] if isinstance(perm, str) else list(perm)

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return JsonResponse({"error": "Authentication required"}, status=401)
            if not all(user.has_perm(p) for p in perms):
                return JsonResponse({"error": "Permission denied"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def staff_required_component(view_func):
    """
    Decorator that requires the user to be a staff member.

    Returns a JSON 403 response (never a redirect) for non-staff requests.

    Usage::

        from component_framework.adapters.django_permissions import staff_required_component

        urlpatterns = [
            path("components/<str:name>/", staff_required_component(component_view)),
        ]
    """

    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if not user.is_staff:
            return JsonResponse({"error": "Staff access required"}, status=403)
        return view_func(request, *args, **kwargs)

    return wrapper
