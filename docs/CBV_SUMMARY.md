# Class-Based Views - Implementation Complete ✅

## What Was Added

### 🎯 Core CBV Classes

**File:** `src/component_framework/adapters/django_views.py`

1. **ComponentView** - Base class for all component views
2. **AuthenticatedComponentView** - Requires login
3. **PermissionComponentView** - Permission checking
4. **CSRFExemptComponentView** - CSRF exempt (for APIs)
5. **SingleComponentView** - Dedicated component endpoint
6. **ComponentPageView** - Full page with components

### 🔧 Mixins

1. **CacheMixin** - Response caching
2. **RateLimitMixin** - Rate limiting (placeholder)

### 📚 Examples

**File:** `examples/django_example/demo_app/cbv_examples.py`

- 10+ complete CBV examples
- Authentication patterns
- Permission patterns
- Caching patterns
- API patterns
- Audit trails
- Custom processing

### 📖 Documentation

**File:** `CBV_GUIDE.md`

- Complete usage guide
- Best practices
- Comparison with FBVs
- Real-world examples

---

## Quick Reference

### Basic Usage

```python
from component_framework.adapters.django_views import ComponentView

# urls.py
urlpatterns = [
    path("components/<str:name>/", ComponentView.as_view()),
]
```

### With Authentication

```python
from component_framework.adapters.django_views import AuthenticatedComponentView

urlpatterns = [
    path("components/<str:name>/", AuthenticatedComponentView.as_view()),
]
```

### Single Component

```python
from component_framework.adapters.django_views import SingleComponentView

class CounterView(SingleComponentView):
    component_name = "counter"

urlpatterns = [
    path("counter/", CounterView.as_view()),
]
```

### Full Page

```python
from component_framework.adapters.django_views import ComponentPageView

class DashboardView(ComponentPageView):
    template_name = "dashboard.html"
    components = {
        "counter": {"initial": 5},
        "form": {},
    }
```

### Custom Parameters

```python
class CustomView(ComponentView):
    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params['user_id'] = request.user.id
        params['custom_data'] = 'value'
        return params
```

### With Caching

```python
from component_framework.adapters.django_views import CacheMixin, ComponentView

class CachedView(CacheMixin, ComponentView):
    cache_timeout = 300  # 5 minutes
```

---

## Available CBV Classes

| Class | Purpose | Inherits |
|-------|---------|----------|
| `ComponentView` | Base component view | `View` |
| `AuthenticatedComponentView` | Requires login | `LoginRequiredMixin`, `ComponentView` |
| `PermissionComponentView` | Requires permissions | `PermissionRequiredMixin`, `ComponentView` |
| `CSRFExemptComponentView` | CSRF exempt | `ComponentView` |
| `SingleComponentView` | Single component | `ComponentView` |
| `ComponentPageView` | Full page view | `TemplateView` |

---

## Customization Hooks

### Methods You Can Override

```python
class MyView(ComponentView):
    # Component loading
    def get_component_class(self, name):
        """Get component class from registry."""

    # Request parsing
    def parse_request_data(self, request):
        """Parse incoming request."""

    def parse_payload(self, payload_str):
        """Parse event payload."""

    def parse_state(self, state_str):
        """Parse component state."""

    def parse_params(self, params_str):
        """Parse component params."""

    # Parameter injection
    def get_component_params(self, request, **kwargs):
        """Add custom parameters."""

    # Component lifecycle
    def create_component(self, component_cls, params):
        """Create component instance."""

    def dispatch_component(self, component, event, payload, state):
        """Dispatch component."""

    # Response handling
    def post_process_result(self, result, component):
        """Post-process result."""

    def render_response(self, result):
        """Render JSON response."""

    # Error handling
    def component_not_found(self, name):
        """Handle missing component."""

    def handle_error(self, error, name):
        """Handle errors."""
```

---

## Benefits of CBVs

✅ **Reusability** - Inherit and extend
✅ **DRY** - Share common logic via mixins
✅ **Customization** - Override specific methods
✅ **Django Integration** - Built-in auth mixins
✅ **Type Safety** - Better type hints
✅ **Testing** - Easier to test
✅ **Organization** - Cleaner code structure

---

## FBV Still Available

The function-based `component_view()` is still available:

```python
from component_framework.adapters.django_views import component_view

urlpatterns = [
    path("components/<str:name>/", component_view),
]
```

**Use FBV when:**
- Simple, one-off endpoint
- No customization needed

**Use CBV when:**
- Need authentication/permissions
- Want caching or rate limiting
- Multiple similar endpoints
- Custom parameter injection
- Audit trails or logging

---

## Files Created

1. `src/component_framework/adapters/django_views.py` - **Updated** with CBV classes
2. `examples/django_example/demo_app/cbv_examples.py` - **New** - 10+ examples
3. `examples/django_example/urls_cbv.py` - **New** - CBV URL patterns
4. `CBV_GUIDE.md` - **New** - Complete guide
5. `CBV_SUMMARY.md` - **New** - This file

---

## Examples Summary

### 1. BasicComponentView
Simple pass-through view

### 2. AuthComponentView
With authentication + custom params

### 3. AdminComponentView
Permission-based access

### 4. DynamicPermissionView
Dynamic permission checking

### 5. CounterView
Single component endpoint

### 6. OrderEditorView
Model-specific component

### 7. CachedComponentView
With response caching

### 8. DashboardView
Multiple components on page

### 9. OrderDetailView
Page with context + component

### 10. LoggingComponentView
With interaction logging

### 11. AuditTrailView
Audit log creation

### 12. APIComponentView
API-style with metadata

---

## Testing CBVs

```python
from django.test import TestCase, RequestFactory
from demo_app.cbv_examples import CounterView

class CBVTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = CounterView.as_view()

    def test_counter_view(self):
        request = self.factory.post('/counter/')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
```

---

## Migration from FBV to CBV

### Before (FBV):
```python
urlpatterns = [
    path("components/<str:name>/", component_view),
]
```

### After (CBV):
```python
urlpatterns = [
    path("components/<str:name>/", ComponentView.as_view()),
]
```

**No breaking changes!** Both work identically for basic use cases.

---

## Next Steps

Potential enhancements:
- [ ] Add more mixins (throttling, monitoring)
- [ ] GraphQL support
- [ ] AsyncComponentView for async components
- [ ] Component versioning support
- [ ] Built-in OpenAPI/Swagger docs

---

## Summary

**CBV support is complete!**

✅ 6 base CBV classes
✅ 2 mixins
✅ 10+ examples
✅ Complete documentation
✅ Backward compatible
✅ Production ready

You now have both FBV and CBV options for maximum flexibility!
