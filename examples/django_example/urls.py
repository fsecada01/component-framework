"""URL configuration for Django component demo."""

from django.contrib import admin
from django.urls import path

from component_framework.adapters.django_views import component_view
from demo_app import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Component endpoint
    path("components/<str:name>/", component_view, name="component_endpoint"),
    # Demo pages
    path("", views.index, name="index"),
    path("form-demo/", views.form_demo, name="form_demo"),
    path("model-demo/", views.model_demo, name="model_demo"),
    path("websocket-demo/", views.websocket_demo, name="websocket_demo"),
]
