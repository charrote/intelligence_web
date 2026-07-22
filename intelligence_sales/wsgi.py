"""WSGI entry point for Gunicorn."""
import os, sys
# In Docker, /app is the project root
_PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/app")
sys.path.insert(0, _PROJECT_ROOT)

from api.app import app