"""Django view adapters for component endpoints."""

import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from ..core import Component, StateSerializer, registry

logger = logging.getLogger(__name__)


@require_POST
def component_view(request: HttpRequest, name: str) -> JsonResponse:
    """
    Django view for component endpoints.

    POST /components/{name}/
    Body (JSON or form-data):
        - event: Event name
        - payload: Event data (JSON string)
        - state: Serialized state (JSON string)
        - params: Component parameters (JSON string)

    Returns:
        JSON response with html, state, and component_id
    """
    try:
        # Get component class
        component_cls = registry.get(name)
        if not component_cls:
            return JsonResponse({"error": f"Component '{name}' not found"}, status=404)

        # Parse request data (supports both JSON and form-encoded)
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)
        else:
            data = {
                "event": request.POST.get("event"),
                "payload": request.POST.get("payload", "{}"),
                "state": request.POST.get("state"),
                "params": request.POST.get("params", "{}"),
            }

        # Extract parameters
        event = data.get("event")
        payload_str = data.get("payload", "{}")
        state_str = data.get("state")
        params_str = data.get("params", "{}")

        # Parse JSON strings
        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            params = json.loads(params_str) if isinstance(params_str, str) else params_str
        except json.JSONDecodeError as e:
            return JsonResponse({"error": f"Invalid JSON in payload/params: {e}"}, status=400)

        # Deserialize state
        state = None
        if state_str:
            try:
                state = StateSerializer.deserialize(state_str)
            except Exception as e:
                return JsonResponse({"error": f"Invalid state: {e}"}, status=400)

        # Create and dispatch component
        component = component_cls(**params)
        result = component.dispatch(event=event, payload=payload, state=state)

        # Serialize state for response
        result["state"] = StateSerializer.serialize(result["state"])

        return JsonResponse(result)

    except Exception:
        logger.exception(f"Error processing component '{name}'")
        return JsonResponse({"error": "Internal server error"}, status=500)


# CSRF-exempt version for HTMX requests (use with caution)
component_view_no_csrf = csrf_exempt(component_view)


def create_component_url_pattern():
    """
    Create URL pattern for component endpoint.

    Usage in urls.py:
        from component_framework.adapters.django_views import create_component_url_pattern

        urlpatterns = [
            create_component_url_pattern(),
        ]
    """
    from django.urls import path

    return path("components/<str:name>/", component_view, name="component_endpoint")


# ==================== Class-Based Views ====================


class ComponentView(View):
    """
    Class-based view for component endpoints.

    Usage:
        # urls.py
        from component_framework.adapters.django_views import ComponentView

        urlpatterns = [
            path("components/<str:name>/", ComponentView.as_view()),
        ]

    Or with custom configuration:
        class MyComponentView(ComponentView):
            http_method_names = ['post', 'get']  # Allow GET too

            def get_component_params(self, request, **kwargs):
                # Custom param extraction
                params = super().get_component_params(request, **kwargs)
                params['user_id'] = request.user.id
                return params
    """

    http_method_names = ["post"]

    def post(self, request: HttpRequest, name: str, **kwargs) -> JsonResponse:
        """Handle POST request for component."""
        try:
            # Get component class
            component_cls = self.get_component_class(name)
            if not component_cls:
                return self.component_not_found(name)

            # Parse request data
            data = self.parse_request_data(request)

            # Extract component parameters
            event = data.get("event")
            payload = self.parse_payload(data.get("payload", "{}"))
            state = self.parse_state(data.get("state"))
            params = self.parse_params(data.get("params", "{}"))

            # Add custom params
            params.update(self.get_component_params(request, **kwargs))

            # Create and dispatch component
            component = self.create_component(component_cls, params)
            result = self.dispatch_component(component, event, payload, state)

            # Post-process result
            result = self.post_process_result(result, component)

            return self.render_response(result)

        except Exception as e:
            return self.handle_error(e, name)

    def get_component_class(self, name: str) -> type[Component] | None:
        """Get component class from registry."""
        return registry.get(name)

    def parse_request_data(self, request: HttpRequest) -> dict:
        """Parse request data (JSON or form-encoded)."""
        if request.content_type == "application/json":
            try:
                return json.loads(request.body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
        else:
            return {
                "event": request.POST.get("event"),
                "payload": request.POST.get("payload", "{}"),
                "state": request.POST.get("state"),
                "params": request.POST.get("params", "{}"),
            }

    def parse_payload(self, payload_str: str | dict) -> dict:
        """Parse payload JSON string."""
        if isinstance(payload_str, dict):
            return payload_str
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid payload JSON: {e}")

    def parse_state(self, state_str: str | None) -> dict | None:
        """Parse state JSON string."""
        if not state_str:
            return None
        try:
            return StateSerializer.deserialize(state_str)
        except Exception as e:
            raise ValueError(f"Invalid state: {e}")

    def parse_params(self, params_str: str | dict) -> dict:
        """Parse params JSON string."""
        if isinstance(params_str, dict):
            return params_str
        try:
            return json.loads(params_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid params JSON: {e}")

    def get_component_params(self, request: HttpRequest, **kwargs) -> dict:
        """
        Get additional component parameters.

        Override to inject custom parameters (user, session data, etc.)
        """
        return {}

    def create_component(self, component_cls: type[Component], params: dict) -> Component:
        """Create component instance."""
        return component_cls(**params)

    def dispatch_component(
        self, component: Component, event: str | None, payload: dict, state: dict | None
    ) -> dict:
        """Dispatch component with event."""
        return component.dispatch(event=event, payload=payload, state=state)

    def post_process_result(self, result: dict, component: Component) -> dict:
        """Post-process component result. Override to add custom data."""
        result["state"] = StateSerializer.serialize(result["state"])
        return result

    def render_response(self, result: dict) -> JsonResponse:
        """Render JSON response."""
        return JsonResponse(result)

    def component_not_found(self, name: str) -> JsonResponse:
        """Handle component not found."""
        return JsonResponse({"error": f"Component '{name}' not found"}, status=404)

    def handle_error(self, error: Exception, name: str) -> JsonResponse:
        """Handle errors."""
        logger.exception(f"Error processing component '{name}'")
        return JsonResponse({"error": "Internal server error"}, status=500)


class AuthenticatedComponentView(LoginRequiredMixin, ComponentView):
    """
    Component view that requires authentication.

    Usage:
        urlpatterns = [
            path("components/<str:name>/", AuthenticatedComponentView.as_view()),
        ]
    """

    def get_component_params(self, request: HttpRequest, **kwargs) -> dict:
        """Add user to component params."""
        params = super().get_component_params(request, **kwargs)
        params["user"] = request.user
        params["user_id"] = request.user.id
        return params


class PermissionComponentView(PermissionRequiredMixin, ComponentView):
    """
    Component view with permission checking.

    Usage:
        class MyComponentView(PermissionComponentView):
            permission_required = 'app.change_model'

        # Or dynamic permissions:
        class MyComponentView(PermissionComponentView):
            def get_permission_required(self):
                # Check component-specific permissions
                component_name = self.kwargs.get('name')
                return f'app.use_{component_name}'
    """

    pass


@method_decorator(csrf_exempt, name="dispatch")
class CSRFExemptComponentView(ComponentView):
    """
    Component view with CSRF exemption.

    Use with caution! Only for HTMX/AJAX requests with alternative CSRF protection.

    Usage:
        urlpatterns = [
            path("api/components/<str:name>/", CSRFExemptComponentView.as_view()),
        ]
    """

    pass


class SingleComponentView(ComponentView):
    """
    View for a single, specific component.

    Usage:
        class CounterView(SingleComponentView):
            component_name = "counter"

        urlpatterns = [
            path("counter/", CounterView.as_view()),
        ]
    """

    component_name: str = None

    def post(self, request: HttpRequest, **kwargs) -> JsonResponse:
        """Override to use fixed component name."""
        if not self.component_name:
            raise ValueError("component_name must be set")
        return super().post(request, self.component_name, **kwargs)


class ComponentPageView(TemplateView):
    """
    Template view that renders a page with components.

    Usage:
        class MyPageView(ComponentPageView):
            template_name = "my_page.html"
            components = {
                "counter": {"initial": 5},
                "form": {"user_id": 123},
            }

            def get_component_params(self, component_name):
                # Override to add dynamic params
                params = super().get_component_params(component_name)
                if component_name == "form":
                    params["user_id"] = self.request.user.id
                return params
    """

    components: dict[str, dict] = {}

    def get_context_data(self, **kwargs):
        """Add component rendering to context."""
        context = super().get_context_data(**kwargs)
        context["components"] = {}

        for component_name, params in self.get_components().items():
            component_cls = registry.get(component_name)
            if component_cls:
                # Add custom params
                params = self.get_component_params(component_name, params)

                # Render component
                component = component_cls(**params)
                result = component.dispatch()
                context["components"][component_name] = result

        return context

    def get_components(self) -> dict[str, dict]:
        """Get components to render. Override for dynamic components."""
        return self.components

    def get_component_params(self, component_name: str, params: dict) -> dict:
        """Get parameters for a specific component. Override to add custom params."""
        return params.copy()


# ==================== Mixins ====================


class RateLimitMixin:
    """
    Mixin to add rate limiting to component views.

    **Status: Not yet implemented.** This mixin currently passes through to the
    parent dispatch without applying any rate limiting. A future version will
    integrate with django-ratelimit or a similar library.

    Usage (once implemented):
        class MyComponentView(RateLimitMixin, ComponentView):
            rate_limit_key = "component"
            rate_limit_rate = "10/m"  # 10 per minute
    """

    rate_limit_key: str = "component"
    rate_limit_rate: str = "60/m"

    def dispatch(self, request, *args, **kwargs):
        """Check rate limit before dispatching. (Not yet implemented.)"""
        # TODO: Integrate with django-ratelimit or similar library.
        return super().dispatch(request, *args, **kwargs)


class CacheMixin:
    """
    Mixin to add caching to component responses.

    Usage:
        class MyComponentView(CacheMixin, ComponentView):
            cache_timeout = 60  # seconds

            def get_cache_key(self, name, params, state):
                return f"component:{name}:{params.get('id')}"
    """

    cache_timeout: int = 60

    def get_cache_key(self, name: str, params: dict, state: dict | None) -> str:
        """Generate cache key. Override for custom keys."""
        import hashlib

        params_json = json.dumps(params, sort_keys=True)
        state_json = json.dumps(state or {}, sort_keys=True)
        key_data = f"{name}:{params_json}:{state_json}"
        return f"component:{hashlib.md5(key_data.encode()).hexdigest()}"

    def post(self, request: HttpRequest, name: str, **kwargs) -> JsonResponse:
        """Check cache before processing."""
        from django.core.cache import cache

        # Try to get from cache
        data = self.parse_request_data(request)
        params = self.parse_params(data.get("params", "{}"))
        state = self.parse_state(data.get("state"))

        cache_key = self.get_cache_key(name, params, state)
        cached_result = cache.get(cache_key)

        if cached_result:
            return JsonResponse(cached_result)

        # Process normally
        response = super().post(request, name, **kwargs)

        # Cache the result
        if response.status_code == 200:
            cache.set(cache_key, json.loads(response.content), self.cache_timeout)

        return response
