"""WSGI entry point for Gunicorn."""
import os, sys
_DOMAIN_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DOMAIN_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _DOMAIN_DIR)

from intelligence_sales.api.app import app