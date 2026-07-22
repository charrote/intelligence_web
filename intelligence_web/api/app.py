"""API entry point - uses core.app.create_app factory."""

import os
import sys

# Add /app to Python path so 'core' module can be imported
sys.path.insert(0, '/app')

from core.domain import build_spec
from core.app import create_app

# Build domain spec
SPEC = build_spec(
    slug="intelligence_web",
    port=8766,
    title_prefix="情报管理系统",
    scout_label="制造情报采集",
    agent_names=["贾维斯", "美雪", "南希", "马格南"],
    theme_color="#722ed1",
    inbox_rel="../inbox/",
    db_filename="intelligence",
)

# Create app using factory
app = create_app("/app", SPEC)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8766, debug=True)