"""App configuration."""

from django.apps import AppConfig


class DemoAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "demo_app"

    def ready(self):
        """Import components when app is ready."""
        from . import components  # noqa
