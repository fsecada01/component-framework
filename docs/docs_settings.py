"""
Minimal Django settings for pdoc documentation generation.

This module is used only by docs/make.py so pdoc can import the Django
adapters without a real database or INSTALLED_APPS configuration.

It is NOT intended for running the application.
"""

SECRET_KEY = "docs-build-only-not-a-real-secret"
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]
DATABASES = {}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
