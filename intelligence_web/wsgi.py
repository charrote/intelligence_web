"""WSGI entry point for Gunicorn."""
import os, sys

# In Docker: /app/intelligence_web/wsgi.py, /app/api/app.py
# The api directory is at /app/api/, core is at /app/core/
sys.path.insert(0, '/app')

from api.app import app