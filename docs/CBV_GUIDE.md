# Class-Based Views Guide

Comprehensive guide to using Class-Based Views (CBVs) with the component framework.

---

## Table of Contents

- [Basic Usage](#basic-usage)
- [Built-in CBVs](#built-in-cbvs)
- [Authentication & Permissions](#authentication--permissions)
- [Single Component Views](#single-component-views)
- [Page Views](#page-views)
- [Mixins](#mixins)
- [Customization](#customization)
- [Examples](#examples)

---

## Basic Usage

### Simple Component View

```python
from component_framework.adapters.django_views import ComponentView

# urls.py
urlpatterns = [
    path("components/<str:name>/", ComponentView.as_view()),
]
```

This handles ALL components through a single endpoint.

### Function-Based vs Class-Based

**Function-Based (FBV):**
```python
from component_framework.adapters.django_views import component_view

urlpatterns = [
    path("components/<str:name>/", component_view),
]
```

**Class-Based (CBV):**
```python
from component_framework.adapters.django_views import ComponentView

urlpatterns = [
    path("components/<str:name>/", ComponentView.as_view()),
]
```

CBVs provide better customization and reusability.

---

## Built-in CBVs

### ComponentView

Base class for all component views.

```python
from component_framework.adapters.django_views import ComponentView

class MyComponentView(ComponentView):
    http_method_names = ['post']  # Only POST allowed

    def get_component_params(self, request, **kwargs):
        """Add custom parameters to components."""
        params = super().get_component_params(request, **kwargs)
        params['custom_data'] = 'value'
        return params
```

### AuthenticatedComponentView

Requires user authentication.

```python
from component_framework.adapters.django_views import AuthenticatedComponentView

urlpatterns = [
    path("components/<str:name>/", AuthenticatedComponentView.as_view()),
]
```

Automatically adds `user` and `user_id` to component params.

### PermissionComponentView

Requires specific permissions.

```python
from component_framework.adapters.django_views import PermissionComponentView

class AdminComponentView(PermissionComponentView):
    permission_required = 'app.change_model'

urlpatterns = [
    path("admin/components/<str:name>/", AdminComponentView.as_view()),
]
```

### CSRFExemptComponentView

Disables CSRF protection (use with caution).

```python
from component_framework.adapters.django_views import CSRFExemptComponentView

urlpatterns = [
    # For HTMX/API endpoints with alternative security
    path("api/components/<str:name>/", CSRFExemptComponentView.as_view()),
]
```

### SingleComponentView

View for a specific component only.

```python
from component_framework.adapters.django_views import SingleComponentView

class CounterView(SingleComponentView):
    component_name = "counter"

urlpatterns = [
    path("counter/", CounterView.as_view()),
]
```

### ComponentPageView

Full page view with component rendering.

```python
from component_framework.adapters.django_views import ComponentPageView

class DashboardView(ComponentPageView):
    template_name = "dashboard.html"
    components = {
        "counter": {"initial": 5},
        "form": {},
    }

urlpatterns = [
    path("dashboard/", DashboardView.as_view()),
]
```

Template usage:
```django
<!-- dashboard.html -->
<div>{{ components.counter.html|safe }}</div>
<div>{{ components.form.html|safe }}</div>
```

---

## Authentication & Permissions

### Require Login

```python
from component_framework.adapters.django_views import AuthenticatedComponentView

class UserComponentView(AuthenticatedComponentView):
    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['username'] = request.user.username
        return params
```

### Check Permissions

```python
from component_framework.adapters.django_views import PermissionComponentView

class SecureView(PermissionComponentView):
    permission_required = 'app.use_component'
```

### Dynamic Permissions

```python
from django.contrib.auth.mixins import UserPassesTestMixin
from component_framework.adapters.django_views import ComponentView

class DynamicPermView(ComponentView, UserPassesTestMixin):
    def test_func(self):
        component_name = self.kwargs['name']
        return self.request.user.has_perm(f'app.use_{component_name}')
```

### Staff Only

```python
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

@method_decorator(staff_member_required, name='dispatch')
class StaffComponentView(ComponentView):
    pass
```

---

## Single Component Views

### Dedicated Endpoint

```python
class OrderEditorView(SingleComponentView):
    component_name = "order_editor"

    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['pk'] = kwargs.get('order_id')
        return params

# urls.py
path("orders/<int:order_id>/edit/", OrderEditorView.as_view()),
```

### With Query Parameters

```python
class FilteredListView(SingleComponentView):
    component_name = "customer_list"

    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['filter'] = request.GET.get('filter', 'all')
        params['page'] = int(request.GET.get('page', 1))
        return params
```

---

## Page Views

### Dashboard with Multiple Components

```python
class DashboardView(ComponentPageView):
    template_name = "dashboard.html"

    def get_components(self):
        return {
            "stats": {},
            "recent_orders": {"limit": 10},
            "alerts": {"user_id": self.request.user.id},
        }
```

### Dynamic Components

```python
class CustomDashboard(ComponentPageView):
    template_name = "dashboard.html"

    def get_components(self):
        # Load user preferences
        widgets = self.request.user.preferences.get('dashboard_widgets', [])

        components = {}
        for widget in widgets:
            components[widget['name']] = widget['params']

        return components
```

### With Context Data

```python
class OrderDetailView(ComponentPageView):
    template_name = "order_detail.html"

    def get_components(self):
        order_id = self.kwargs['pk']
        return {
            "order_editor": {"pk": order_id},
            "order_history": {"order_id": order_id},
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = Order.objects.get(pk=self.kwargs['pk'])
        return context
```

---

## Mixins

### CacheMixin

Add response caching.

```python
from component_framework.adapters.django_views import CacheMixin, ComponentView

class CachedView(CacheMixin, ComponentView):
    cache_timeout = 300  # 5 minutes

    def get_cache_key(self, name, params, state):
        user_id = self.request.user.id
        return f"component:{name}:{user_id}:{params.get('pk')}"
```

### RateLimitMixin

Add rate limiting (requires django-ratelimit).

```python
from component_framework.adapters.django_ratelimit import RateLimitMixin
from component_framework.adapters.django_views import ComponentView

class RateLimitedView(RateLimitMixin, ComponentView):
    rate_limit_key = "component"
    rate_limit_rate = "10/m"
```

### Custom Mixin

```python
class LoggingMixin:
    def dispatch_component(self, component, event, payload, state):
        logger.info(f"User {self.request.user} triggered {event}")
        return super().dispatch_component(component, event, payload, state)

class LoggedView(LoggingMixin, ComponentView):
    pass
```

---

## Customization

### Custom Parameter Injection

```python
class CustomParamView(ComponentView):
    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)

        # Add session data
        params['session_id'] = request.session.session_key

        # Add IP address
        params['ip_address'] = self.get_client_ip(request)

        # Add custom header
        params['api_key'] = request.headers.get('X-API-Key')

        return params

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
```

### Custom Response Format

```python
class APIView(ComponentView):
    def render_response(self, result):
        """Add API envelope."""
        response = {
            "success": True,
            "data": result,
            "timestamp": timezone.now().isoformat(),
        }
        return JsonResponse(response)
```

### Custom Error Handling

```python
class CustomErrorView(ComponentView):
    def handle_error(self, error, name):
        """Custom error responses."""
        logger.exception(f"Component error: {name}")

        if isinstance(error, ValidationError):
            return JsonResponse(
                {"error": "Validation failed", "details": error.messages},
                status=400
            )

        return JsonResponse(
            {"error": "Internal error", "component": name},
            status=500
        )
```

### Audit Trail

```python
class AuditedView(ComponentView):
    def post_process_result(self, result, component):
        """Log all component changes."""
        AuditLog.objects.create(
            user=self.request.user,
            component=component.__class__.__name__,
            action="update",
            data=result["state"]
        )
        return super().post_process_result(result, component)
```

---

## Examples

### E-commerce Admin

```python
class ProductAdminView(PermissionComponentView, CacheMixin):
    permission_required = 'shop.change_product'
    cache_timeout = 60

    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['is_admin'] = True
        params['can_delete'] = request.user.has_perm('shop.delete_product')
        return params
```

### User Dashboard

```python
class UserDashboard(LoginRequiredMixin, ComponentPageView):
    template_name = "user/dashboard.html"

    def get_components(self):
        user = self.request.user
        return {
            "profile": {"user_id": user.id},
            "recent_orders": {"user_id": user.id, "limit": 5},
            "recommendations": {"user_id": user.id},
        }
```

### Real-Time Collaboration

```python
class CollabView(AuthenticatedComponentView):
    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['broadcast'] = True  # Enable WebSocket broadcasting
        params['room_id'] = kwargs.get('room_id')
        return params
```

### Multi-Tenant

```python
class TenantView(ComponentView):
    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['tenant_id'] = request.tenant.id
        return params

    def get_component_class(self, name):
        """Filter components by tenant access."""
        component_cls = super().get_component_class(name)

        if not self.tenant_can_use_component(name):
            return None

        return component_cls

    def tenant_can_use_component(self, name):
        return name in self.request.tenant.allowed_components
```

---

## Best Practices

### 1. Use Appropriate Base Class

- `ComponentView` - General purpose
- `AuthenticatedComponentView` - User-specific components
- `PermissionComponentView` - Admin/privileged components
- `SingleComponentView` - Dedicated component endpoints
- `ComponentPageView` - Full page rendering

### 2. Inject Context, Don't Hardcode

```python
# ✅ Good
def get_component_params(self, request, **kwargs):
    params = super().get_component_params(request, **kwargs)
    params['user_id'] = request.user.id
    return params

# ❌ Bad
def post(self, request, name):
    params = {"user_id": 123}  # Hardcoded!
```

### 3. Layer Security

```python
class SecureView(
    LoginRequiredMixin,      # Require login
    PermissionRequiredMixin,  # Check permissions
    RateLimitMixin,           # Rate limit
    ComponentView
):
    permission_required = 'app.use_component'
    rate_limit_rate = "30/m"
```

### 4. Cache Appropriately

```python
class SmartCachedView(CacheMixin, ComponentView):
    def get_cache_key(self, name, params, state):
        # Cache per user + object
        return f"component:{name}:{self.request.user.id}:{params.get('pk')}"

    def post(self, request, name, **kwargs):
        # Skip cache for mutations
        data = self.parse_request_data(request)
        if data.get('event') in ['save', 'delete', 'update']:
            return ComponentView.post(self, request, name, **kwargs)

        return super().post(request, name, **kwargs)
```

---

## Comparison: FBV vs CBV

| Feature | FBV | CBV |
|---------|-----|-----|
| Simplicity | ✅ Simpler | More complex |
| Reusability | ❌ Limited | ✅ Excellent |
| Customization | ❌ Harder | ✅ Easy |
| Mixins | ❌ No | ✅ Yes |
| Inheritance | ❌ No | ✅ Yes |
| DRY | ❌ More duplication | ✅ Less duplication |
| Learning Curve | ✅ Easier | Steeper |

**Use FBV when:** Simple, one-off endpoints
**Use CBV when:** Need customization, reusability, or multiple similar endpoints

---

## Summary

CBVs provide:

- ✅ Better code reuse
- ✅ Easy customization via inheritance
- ✅ Mixin support
- ✅ Django's built-in auth mixins
- ✅ Cleaner organization
- ✅ Type hints support
- ✅ Testing-friendly

All the power of function-based views, with the flexibility of classes!
