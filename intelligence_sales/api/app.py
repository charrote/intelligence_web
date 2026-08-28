"""Sales domain — Flask application entry point."""

import os, sys
# In Docker: /app is the project root. Local dev: project root is one level up.
if os.path.isdir("/app/api"):
    _PROJECT_ROOT = "/app"
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DOMAIN_DIR = _PROJECT_ROOT
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _DOMAIN_DIR)

from core.app import create_app
from domain_spec import SPEC

# Create app — init_db + migrate_db are called inside create_app
app = create_app(_PROJECT_ROOT, SPEC)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=SPEC["port"], debug=True)
