"""Generic domain — Flask application entry point.

Loads domain spec from a mounted JSON file at runtime, builds the spec
via core.domain.build_spec(), and creates the Flask app.

The spec JSON is mounted at DOMAIN_SPEC_PATH (default /app/spec.json).
This allows a single Docker image to serve any number of domains —
each domain just mounts a different spec.json.
"""
import os, sys, json

# In Docker: /app is the project root
_PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/app")
sys.path.insert(0, _PROJECT_ROOT)

from core.app import create_app
from core.domain import build_spec


def load_spec():
    """Load domain spec from mounted JSON file and build a spec dict."""
    spec_path = os.environ.get("DOMAIN_SPEC_PATH", "/app/spec.json")
    with open(spec_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Required fields
    kwargs = {
        "slug": raw["slug"],
        "port": raw.get("port", 8766),
        "title_prefix": raw.get("title_prefix", raw["slug"]),
        "scout_label": raw.get("scout_label", raw.get("title_prefix", raw["slug"])),
        "agent_names": raw.get("agent_names", []),
        "theme_color": raw.get("theme_color", "#3b4f8c"),
    }

    # Optional fields — only pass if present in the JSON
    optional_fields = [
        "inbox_rel", "db_filename", "domain_key", "statuses",
        "extra_columns", "list_columns", "search", "intelligence_ttl_days",
        "default_entities", "default_data_sources", "target_types",
        "target_type_initial_data",
    ]
    for key in optional_fields:
        if key in raw and raw[key] is not None:
            kwargs[key] = raw[key]

    return build_spec(**kwargs)


SPEC = load_spec()
app = create_app(_PROJECT_ROOT, SPEC)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=SPEC["port"], debug=True)
