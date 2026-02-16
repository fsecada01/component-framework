"""
Alternative URL configuration using Class-Based Views.

This demonstrates various ways to configure component endpoints using CBVs.
"""

from django.contrib import admin
from django.urls import path

from component_framework.adapters.django_views import (
    AuthenticatedComponentView,
    ComponentView,
    CSRFExemptComponentView,
    PermissionComponentView,
)
from demo_app import views
from demo_app.cbv_examples import (
    APIComponentView,
    CachedComponentView,
    CounterView,
    DashboardView,
    OrderDetailView,
    OrderEditorView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # ==================== Demo Pages ====================
    path("", views.index, name="index"),
    path("form-demo/", views.form_demo, name="form_demo"),
    path("model-demo/", views.model_demo, name="model_demo"),
    path("websocket-demo/", views.websocket_demo, name="websocket_demo"),
    # ==================== Basic Component Endpoint (CBV) ====================
    # Generic endpoint for all components
    path("components/<str:name>/", ComponentView.as_view(), name="component_endpoint"),
    # ==================== Authenticated Components ====================
    # Requires login
    path(
        "auth/components/<str:name>/",
        AuthenticatedComponentView.as_view(),
        name="auth_component",
    ),
    # ==================== Permission-Based Components ====================
    # Requires specific permissions
    path(
        "admin/components/<str:name>/",
        PermissionComponentView.as_view(),
        name="admin_component",
    ),
    # ==================== CSRF-Exempt for API/HTMX ====================
    # Use with caution!
    path(
        "api/components/<str:name>/",
        CSRFExemptComponentView.as_view(),
        name="api_component",
    ),
    # ==================== Single Component Views ====================
    # Dedicated endpoints for specific components
    path("counter/", CounterView.as_view(), name="counter"),
    path(
        "orders/<int:order_id>/edit/",
        OrderEditorView.as_view(),
        name="order_edit",
    ),
    # ==================== Cached Components ====================
    # With response caching
    path(
        "cached/components/<str:name>/",
        CachedComponentView.as_view(),
        name="cached_component",
    ),
    # ==================== API-Style Endpoints ====================
    # With API versioning and metadata
    path(
        "api/v1/components/<str:name>/",
        APIComponentView.as_view(),
        name="api_v1_component",
    ),
    # ==================== Page Views with Components ====================
    # Full page views that render components
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
]
