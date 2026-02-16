"""
Class-Based View examples for components.

This module demonstrates various ways to use CBVs with the component framework.
"""

from django.contrib.auth.mixins import UserPassesTestMixin

from component_framework.adapters.django_views import (
    AuthenticatedComponentView,
    CacheMixin,
    ComponentPageView,
    ComponentView,
    PermissionComponentView,
    SingleComponentView,
)


# ==================== Basic Usage ====================


class BasicComponentView(ComponentView):
    """
    Basic component view - handles all components.

    Usage in urls.py:
        path("components/<str:name>/", BasicComponentView.as_view()),
    """

    pass


# ==================== Authenticated Components ====================


class AuthComponentView(AuthenticatedComponentView):
    """
    Requires user authentication.

    Automatically adds user and user_id to component params.

    Usage:
        path("auth-components/<str:name>/", AuthComponentView.as_view()),
    """

    def get_component_params(self, request, **kwargs):
        """Add extra context for authenticated users."""
        params = super().get_component_params(request, **kwargs)
        params["username"] = request.user.username
        params["is_staff"] = request.user.is_staff
        return params


# ==================== Permission-Based Components ====================


class AdminComponentView(PermissionComponentView):
    """
    Requires specific permissions.

    Usage:
        path("admin-components/<str:name>/", AdminComponentView.as_view()),
    """

    permission_required = "demo_app.change_order"


class DynamicPermissionView(ComponentView, UserPassesTestMixin):
    """
    Dynamic permission checking based on component name.

    Usage:
        path("secure/<str:name>/", DynamicPermissionView.as_view()),
    """

    def test_func(self):
        """Check if user has permission for this component."""
        component_name = self.kwargs.get("name")
        # Check component-specific permission
        return self.request.user.has_perm(f"demo_app.use_{component_name}")


# ==================== Single Component Views ====================


class CounterView(SingleComponentView):
    """
    Dedicated view for counter component.

    Usage:
        path("counter/", CounterView.as_view()),
    """

    component_name = "live_counter"

    def get_component_params(self, request, **kwargs):
        """Set initial counter value."""
        params = super().get_component_params(request, **kwargs)
        params["initial"] = int(request.GET.get("initial", 0))
        return params


class OrderEditorView(SingleComponentView):
    """
    Dedicated view for order editor.

    Usage:
        path("orders/<int:order_id>/edit/", OrderEditorView.as_view()),
    """

    component_name = "order_editor"

    def get_component_params(self, request, **kwargs):
        """Add order PK from URL."""
        params = super().get_component_params(request, **kwargs)
        params["pk"] = kwargs.get("order_id")
        return params


# ==================== Cached Components ====================


class CachedComponentView(CacheMixin, ComponentView):
    """
    Component view with caching.

    Usage:
        path("cached/<str:name>/", CachedComponentView.as_view()),
    """

    cache_timeout = 300  # 5 minutes

    def get_cache_key(self, name, params, state):
        """Custom cache key generation."""
        # Cache per component + user
        user_id = self.request.user.id if self.request.user.is_authenticated else "anon"
        pk = params.get("pk", "none")
        return f"component:{name}:{user_id}:{pk}"


# ==================== Page Views with Components ====================


class DashboardView(ComponentPageView):
    """
    Dashboard page with multiple components.

    Usage:
        path("dashboard/", DashboardView.as_view()),
    """

    template_name = "dashboard.html"

    def get_components(self):
        """Define components to render."""
        return {
            "customer_list": {},
            "live_counter": {"initial": 100, "broadcast": True},
        }


class OrderDetailView(ComponentPageView):
    """
    Order detail page with order editor component.

    Usage:
        path("orders/<int:pk>/", OrderDetailView.as_view()),
    """

    template_name = "order_detail.html"

    def get_components(self):
        """Load order editor for specific order."""
        order_id = self.kwargs.get("pk")
        return {
            "order_editor": {"pk": order_id},
        }

    def get_context_data(self, **kwargs):
        """Add order to context."""
        context = super().get_context_data(**kwargs)

        from .models import Order

        context["order"] = Order.objects.get(pk=self.kwargs["pk"])
        return context


# ==================== Custom Processing ====================


class LoggingComponentView(ComponentView):
    """
    Logs all component interactions.

    Usage:
        path("logged/<str:name>/", LoggingComponentView.as_view()),
    """

    def dispatch_component(self, component, event, payload, state):
        """Log before dispatching."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Component: {component.__class__.__name__}, "
            f"Event: {event}, "
            f"User: {self.request.user}"
        )

        result = super().dispatch_component(component, event, payload, state)

        logger.info(f"Result: {result.get('component_id')}")
        return result


class AuditTrailView(ComponentView):
    """
    Creates audit trail for component changes.

    Usage:
        path("audited/<str:name>/", AuditTrailView.as_view()),
    """

    def post_process_result(self, result, component):
        """Save audit record."""
        if hasattr(component, "instance") and component.instance:
            # Create audit log entry
            # AuditLog.objects.create(
            #     user=self.request.user,
            #     model_type=component.model.__name__,
            #     object_id=component.instance.pk,
            #     action="component_update",
            #     changes=result["state"],
            # )
            pass

        return super().post_process_result(result, component)


# ==================== API-Style View ====================


class APIComponentView(ComponentView):
    """
    API-style component view with additional metadata.

    Usage:
        path("api/v1/components/<str:name>/", APIComponentView.as_view()),
    """

    def render_response(self, result):
        """Add API metadata to response."""
        response_data = {
            "success": True,
            "data": result,
            "meta": {
                "version": "1.0",
                "timestamp": self.get_timestamp(),
            },
        }
        return super().render_response(response_data)

    def get_timestamp(self):
        """Get current timestamp."""
        from django.utils import timezone

        return timezone.now().isoformat()

    def handle_error(self, error, name):
        """Format errors consistently."""
        return self.render_response(
            {
                "success": False,
                "error": {
                    "message": str(error),
                    "component": name,
                },
                "data": None,
            }
        )
