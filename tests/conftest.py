"""Shared test configuration and fixtures."""

import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for tests."""
    if not settings.configured:
        settings.configure(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [],
                    "APP_DIRS": True,
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.request",
                        ],
                    },
                },
            ],
            ROOT_URLCONF="tests.urls",
            SECRET_KEY="test-secret-key-for-testing-only",
        )
        django.setup()
