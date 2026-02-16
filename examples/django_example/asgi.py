"""ASGI config for Django component demo."""

import os
import sys
from pathlib import Path

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

# Add src to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_example.settings")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

# Import after Django setup
from component_framework.adapters.django_websocket import ComponentConsumer

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(
            [
                path("ws/", ComponentConsumer.as_asgi()),
            ]
        ),
    }
)
