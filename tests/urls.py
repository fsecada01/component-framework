"""URL configuration for tests."""

from django.urls import path

from component_framework.adapters.django_views import ComponentView, component_view

urlpatterns = [
    path("components/<str:name>/", component_view, name="component_endpoint"),
    path("cbv/components/<str:name>/", ComponentView.as_view(), name="component_cbv"),
]
