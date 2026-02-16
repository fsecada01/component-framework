"""WSGI config for Django component demo."""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

# Add src to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_example.settings")

application = get_wsgi_application()
